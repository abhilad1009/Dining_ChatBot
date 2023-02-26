import boto3
import json
import logging
import random
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


REGION = 'us-east-1'
HOST = 'search-restaurants-pdrqwv6zft457ctm6feeniwrga.us-east-1.es.amazonaws.com'
INDEX = 'restaurants'


def query(term):
    q = {'size': 100, 'query': {'multi_match': {'query': term}}}

    client = OpenSearch(hosts=[{
        'host': HOST,
        'port': 443
    }],
        http_auth=get_awsauth(REGION, 'es'),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection)

    res = client.search(index=INDEX, body=q)
    # print(res)

    hits = res['hits']['hits']
    results = []
    for hit in hits:
        results.append(hit['_source']['id'])

    return results


def get_awsauth(region, service):
    cred = boto3.Session().get_credentials()
    return AWS4Auth(cred.access_key,
                    cred.secret_key,
                    region,
                    service,
                    session_token=cred.token)

def lambda_handler(event, context):
    sqs_client = boto3.client("sqs")
    sqs_url = 'https://sqs.us-east-1.amazonaws.com/106988784213/DiningConcierge'
    response = sqs_client.receive_message(
        QueueUrl=sqs_url,
        AttributeNames=['SentTimestamp'],
        MessageAttributeNames=['All'],
        VisibilityTimeout=0,
        WaitTimeSeconds=0
    )
    try:
        messages = response['Messages']
    except:
        messages = None


    while messages:
        message_response = messages.pop()
        message = json.loads(message_response["Body"])

        location = message['Location']
        cuisine = message["Cuisine"]
        time = message["Time"]
        people = message["People"]
        email = message["email"]

        if not cuisine or not email:
            logger.debug("No Cuisine or Email key found in message")
            return


        # Elastic Search Query
        ids = query(cuisine)

        mailbody = 'Hello from Dining Concierge! Here are some {cuisine} restaurant suggestions in {location} for {people} people at {time}:\n'.format(
            cuisine=cuisine.capitalize(),
            location=location.capitalize(),
            people=people,
            time=time,
        )

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('yelp-restaurants')

        restaurant_id_indices = random.sample(ids,5)
        # logger.debug(restaurant_id_indices)
        

        idx = 1
        for curr_id in restaurant_id_indices:
             response = table.query(KeyConditionExpression=Key('id').eq(curr_id))
            #  logger.debug(response)
             if response is None:
                 continue
             item = response['Items'][0]
             rest_info = '' + str(idx) + '. '
             name = item["name"]
             address = " ".join(item["location"]["display_address"])
             rest_info += name + ', located at ' + address + ', \n'
             mailbody += rest_info
             idx += 1


        try:
            client = boto3.client('ses')
            response = client.send_email(
                Source='al4363@columbia.edu',
                Destination={
                    'ToAddresses': [
                        email,
                    ]},
                Message={
                'Subject' : {
                    'Data' : "Dining Concierge Restaurant Recommendations"
                },
                'Body' :{
                    'Text' :{
                        'Data' : mailbody
                    }
                }
                }
            )
        except KeyError:
            logger.debug("Error sending ")

        logger.debug("response - %s", json.dumps(response))
        logger.debug("Message = '%s' sent to Email = %s" %
                     (mailbody, email))

        sqs_client.delete_message(
            QueueUrl=sqs_url,
            ReceiptHandle=message_response['ReceiptHandle']
        )
        logger.debug('Processed and deleted message:',
                     json.dumps(message))

    return {
        'statusCode': 200,
        'body': json.dumps("LF2 executed and exited")
    }
