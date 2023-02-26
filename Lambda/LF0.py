import boto3
import json
import string
import random

client = boto3.client('lexv2-runtime')


def lambda_handler(event, context):
    user_message = event['messages'][0]['unstructured']['text']

    print("Message from user: "+user_message)
    sessid = ''.join(random.choices(string.ascii_lowercase +
                             string.digits, k=6))
    
    response = client.recognize_text(botId='MKTNG5NTST',
                                     botAliasId='SSSCQKSBKR',
                                     localeId='en_US',
                                     sessionId=sessid,
                                     text=user_message)

    bot_message = response.get("messages", [])

    if bot_message:
        print("Message from bot: "+bot_message[0]['content'])
        resp = {'statusCode': 200, 'messages': [{
        'type': 'unstructured',
        'unstructured': {
          'text': bot_message[0]['content']
        }
      }]}
        return resp

    else:
        return {'statusCode': 200, 'messages': [{
        'type': 'unstructured',
        'unstructured': {
          'text': 'Something went wrong'
        }
      }]}