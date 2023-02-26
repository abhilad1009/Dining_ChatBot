import boto3
import datetime
import dateutil.parser
import json
import logging
import math
import os
import time
from botocore.vendored import requests

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

table = dynamodb.Table('session_history')



def lambda_handler(event, context):
    
    os.environ['TZ'] = 'America/New_York'
    time.tzset()

    logger.debug('event.bot.name={}'.format(event['bot']['name']))
    
    return dispatch(event)



def dispatch(intent_request):

    # logger.debug(
    #     'dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))
    
    intent_name = intent_request['sessionState']['intent']['name']

    if intent_name == 'DiningSuggestionsIntent':
        return dining_intent_codehook(intent_request)
    elif intent_name == 'GreetingIntent' or intent_name == 'ThankYouIntent':
        return {'sessionState':{
                'sessionAttributes': intent_request['sessionState']['sessionAttributes'],
                'dialogAction': {
                    'type': 'Close',
                },
                'intent':{
                    'name':intent_name,
                    'state':"Fulfilled"
                }   
                
                }
            }

    raise Exception('Unidentified Intent: ' + intent_name)



def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {'sessionState':{
                'sessionAttributes': session_attributes,
                'dialogAction': {
                    'type': 'ElicitSlot',
                    'slotToElicit': slot_to_elicit,
                },
                'intent':{
                    'name': intent_name,
                    'slots': slots,
                    'state': 'InProgress'
                }
            },
            'messages':[
                message
            ]
    }



def build_validation_result(is_valid, violated_slot, message_content, restore=False):
    if message_content is None:
        return {
            "is_valid": is_valid,
            "violated_slot": violated_slot,
            'restore': restore
        }

    return {
        'is_valid': is_valid,
        'violated_slot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content},
        'restore' : restore
    }




def parse_time(h,m):
    try:
        h= int(h)
    except ValueError:
        h= float('nan')
    try:
        m= int(m)
    except ValueError:
        m= float('nan')
    return h,m
    
def validate_user_input(location, cuisine, num_people, time, email):
    if email is not None:
        response = table.get_item(Key={'email':email})
        if 'Item' in response.keys():
            msg = "Do you want to get suggestions for "+response['Item']['Cuisine']+" cuisine in "+response['Item']['Location']+" area from your last request? (yes/no)"
            return build_validation_result(True, None, msg, True)

    if location is not None and location.replace(" ","").lower() not in ["manhattan","newyork"]:
        # logger.debug(type(location))
        return build_validation_result(False,
                                       'Location',
                                       'We do not serve in this location. Please try another.')
    
    cuisines = ['chinese', 'indian', 'italian', 'japanese',
                'mediterranean', 'mexican', 'thai']
    if cuisine is not None and cuisine.replace(" ", "").lower() not in cuisines:
        return build_validation_result(False,
                                       'Cuisine',
                                       'We do not serve this cuisine. Please try another.')


    if num_people is not None:
        if int(num_people) < 0 or int(num_people) > 10:
            return build_validation_result(False,
                                           'People',
                                           'We can only accomodate 1-10 people. Please try again')

    if time is not None:
        if len(time) != 5:
            return build_validation_result(False, 'Time', 'Not a valid time')

        hour, minute = time.split(':')
        hour, minute = parse_time(hour, minute)

        if math.isnan(hour) or math.isnan(minute):
            return build_validation_result(False, 'Time', 'Not a valid time')

        if hour < 10 or hour > 21:
            return build_validation_result(False, 'Time',
                                           'Restaurant are open from 10 a.m. to 9 p.m. Can you specify a time in this range?')

    return build_validation_result(True, None, None)



def dining_intent_codehook(intent_request):

    slots = intent_request["sessionState"]['intent']['slots']

    email = None
    location=None
    cuisine=None
    num_people=None
    time = None
    restore = None

    # logger.debug(slots)
    if slots["Email"]!=None:
        email = slots["Email"]["value"]["resolvedValues"][0]
    if slots["Location"]!=None:
        location = slots["Location"]['value']["resolvedValues"][0]
    if slots["Cuisine"]!=None:
        cuisine = slots["Cuisine"]['value']["resolvedValues"][0]
    if slots["People"]!=None:
        num_people = slots["People"]["value"]["resolvedValues"][0]
    if slots["Time"]!=None:
        time = slots["Time"]["value"]["resolvedValues"][0]

    if slots["Restore"]!=None:
        restore = slots["Restore"]['value']["resolvedValues"][0]
        if restore.lower()=='yes':
            response = table.get_item(Key={'email': email})

            data = response['Item']
            msg = data

            sqs_client = boto3.client('sqs')

            queue_url = 'https://sqs.us-east-1.amazonaws.com/106988784213/DiningConcierge'

            response = sqs_client.send_message(QueueUrl=queue_url,
                                                MessageBody=json.dumps(msg))

            return {"sessionState":{
                    'sessionAttributes': intent_request['sessionState']['sessionAttributes'],
                        'dialogAction': {
                            'type': 'Close'},
                        'intent':{
                                    "name": intent_request['sessionState']['intent']['name'],
                                    'slots': slots,
                                    'state': 'Fulfilled'
                        }
                    }
                }


  

    source = intent_request["invocationSource"]



    if source == 'DialogCodeHook':
        slots = intent_request["sessionState"]['intent']['slots']
        validation_result = validate_user_input(location, cuisine, num_people, time, email)
        if validation_result['restore']==True and restore==None:
            return elicit_slot(intent_request['sessionState']['sessionAttributes'],
                        intent_request['sessionState']['intent']['name'],
                        slots,
                        "Restore",
                        validation_result['message'])
            
        if validation_result['is_valid'] == False:
            slots[validation_result['violated_slot']] = None
            return elicit_slot(intent_request['sessionState']['sessionAttributes'],
                               intent_request['sessionState']['intent']['name'],
                               slots,
                               validation_result['violated_slot'],
                               validation_result['message'])


        return {"sessionState":{
                    'sessionAttributes': intent_request['sessionState']['sessionAttributes'],
                    'dialogAction': {
                        'type': 'Delegate',
                    },
                    'intent': {
                            "name": intent_request['sessionState']['intent']['name'],
                            'slots': slots,
                            "state":"ReadyForFulfillment"}
                    }
        }
    
    msg = {"Location":location,"Cuisine": cuisine, "People":num_people, "Time":time , "email": email}

    sqs_client = boto3.client('sqs')

    queue_url = 'https://sqs.us-east-1.amazonaws.com/106988784213/DiningConcierge'

    response = sqs_client.send_message(QueueUrl=queue_url,
                                        MessageBody=json.dumps(msg))
    response = table.put_item(
                                Item=msg
                            )

    return {"sessionState":{
            'sessionAttributes': intent_request['sessionState']['sessionAttributes'],
                'dialogAction': {
                    'type': 'Close'},
                'intent':{
                            "name": intent_request['sessionState']['intent']['name'],
                            'slots': slots,
                            'state': 'Fulfilled'
                }
            }
        }



    # return {'sessionState':{
    #     'sessionAttributes': intent_request['sessionState']['sessionAttributes'],
    #     'dialogAction': {
    #         'type': 'Close',
    #     },
    #     'intent':{
    #         'name':intent_request['sessionState']['intent']['name'],
    #         'state':"Fulfilled"
    #     }   
    #     },
    #     "messages":[{'contentType': 'PlainText', 'content': "debug"}]
    # }