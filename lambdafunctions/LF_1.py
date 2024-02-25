import boto3
import json
import datetime
import dateutil.parser
import os
import time
import math

os.environ['TZ'] = 'America/New_York'
time.tzset()

sqs = boto3.client('sqs')
queue_url = '' #SQS queue URL
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('') #DynamoDB Table Name (One that stores user's previous restaurant suggestions) 
email_id = "" #Source Email ID
                
MAX_PPL = 30
LOCATION_PROMPT = 'What is your dining location preference?'
CUISINE_PROMPT = 'What type of cuisine are you interested in [indian, mexican, italian, chinese, japanese]?'
CUISINE_PREF_PROMPT = 'You have previously used out chatbot concierge. Do you want to go ahead with your previous preferences?'
DATE_PROMPT = 'A few more to go. What date?'
TIME_PROMPT = 'What time?'
NPPL_PROMPT = 'For how many people?'
EMAIL_PROMPT = 'What is your email address?'
WRONG_LOCATION = 'Sorry, but currently our app is not in service at the given location. Please choose Manhattan.'
WRONG_CUISINE = 'Please choose from [indian, mexican, italian, chinese, japanese] cuisines!'
WRONG_DATE = 'I did not understand that, what date would you like to book?'
PAST_DATE = 'That date has gone buddy! Please choose a valid date.'
WRONG_NPEOPLE = f'Maximum {MAX_PPL} people allowed. Try again'
WRONG_TIME = 'Thats not a valid time'
OUTSIDE_BUSINESS_TIME = 'Our business hours are from 11 a.m. to 7 p.m. Can you specify a time during this range?'
CLOSING_PROMPT = 'You’re all set. Expect my suggestions shortly! Have a good day.'

#Slot Validations
def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False

def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')

def is_valid_location(location):
    valid_locations = ['manhattan']
    return location.lower() in valid_locations
    
def is_valid_cuisine(cuisine):
    valid_cuisines = ['indian', 'mexican', 'italian', 'chinese', 'japanese']
    return cuisine.lower() in valid_cuisines

def is_valid_date(date):
    if not isvalid_date(date):
        return -1
    elif datetime.datetime.strptime(date, '%Y-%m-%d').date() < datetime.date.today():
        return 0
    return 1
    
def is_valid_time(time):
    if len(time) != 5:
        return -1
        
    hour, minute = time.split(':')
    hour, minute = parse_int(hour), parse_int(minute)
    if math.isnan(hour) or math.isnan(minute):
        return -1

    if hour < 11 or hour > 19:
        return 0

#Sending email to users who chose to go with their previous preferences
def send_email(email, email_message):
    ses = boto3.client('ses')
    response = ses.send_email(
        Source=email_id,
        Destination={'ToAddresses': [email]},
        ReplyToAddresses=[email_id],
        Message={
            'Subject': {'Data': 'Dining Conceirge Recommendations', 'Charset': 'utf-8'},
            'Body': {
                'Text': {'Data': email_message, 'Charset': 'utf-8'},
                'Html': {'Data': email_message, 'Charset': 'utf-8'}
            }
        }
    )

#Slot elicitation and fulfillment for DiningSuggestionIntent
def handle_dining_suggestions_intent(event):
    slots = event['sessionState']['intent']['slots']
    
    # Check if all required slots are filled
    location = try_ex(lambda: slots['Location']['value']['interpretedValue'])
    cuisine = try_ex(lambda: slots['Cuisine']['value']['interpretedValue'])
    cuisine_pref = try_ex(lambda: slots['CuisinePref']['value']['interpretedValue'])
    dining_time = try_ex(lambda: slots['Time']['value']['interpretedValue'])
    dining_date = try_ex(lambda: slots['Date']['value']['interpretedValue'])
    number_of_people = try_ex(lambda: slots['nPeople']['value']['interpretedValue'])
    email = try_ex(lambda: slots['Email']['value']['interpretedValue'])
    
    if cuisine_pref == 'Yes':
        response = table.get_item(
        Key={
            'email_id': email
            }
        )
        restaurants = response['Item']['message']
        send_email(email, restaurants)
        return close(event, 'Fulfilled', CLOSING_PROMPT)
    
    if email and not cuisine_pref:
        response = table.get_item(
        Key={
            'email_id': email
            }
        )
        if 'Item' in response:
            return elicit_slot(event, 'CuisinePref', CUISINE_PREF_PROMPT)
    elif email == None:
        return elicit_slot(event, 'Email', EMAIL_PROMPT)
        
    if location:
        if not is_valid_location(location):
            return elicit_slot(event, 'Location', WRONG_LOCATION)
    else:
        return elicit_slot(event, 'Location', LOCATION_PROMPT)
    
    if cuisine: 
        if not is_valid_cuisine(cuisine):
            return elicit_slot(event, 'Cuisine', WRONG_CUISINE)
    else:
        return elicit_slot(event, 'Cuisine', CUISINE_PROMPT)
        
    if dining_date:
        valid_date = is_valid_date(dining_date)
        if valid_date == -1:
            return elicit_slot(event, 'Date', WRONG_DATE)
        elif valid_date == 0:
            return elicit_slot(event, 'Date', PAST_DATE)
    else:
        return elicit_slot(event, 'Date', DATE_PROMPT)
    
    if dining_time:
        valid_time = is_valid_time(dining_time)
        if valid_time == -1:
            return elicit_slot(event, 'Time', WRONG_TIME)
        elif valid_time == 0:
            return elicit_slot(event, 'Time', OUTSIDE_BUSINESS_TIME)
    else:
        return elicit_slot(event, 'Time', TIME_PROMPT)
            
    if number_of_people:
        number_of_people = int(number_of_people)
        if number_of_people > MAX_PPL or number_of_people <= 0:
            return elicit_slot(event, 'nPeople', WRONG_NPEOPLE)
    else:
        return elicit_slot(event, 'nPeople', NPPL_PROMPT)
        
    sqs_send_msg(location, cuisine, dining_date, dining_time, number_of_people, email)
    
    return close(event, 'Fulfilled', CLOSING_PROMPT)
    
#Adding the restaurant search parameters to Q1
def sqs_send_msg(location, cuisine, dining_date, dining_time, number_of_people, email):
    
    message = {
        'location': location,
        'cuisine': cuisine,
        'dining_date': dining_date,
        'dining_time': dining_time,
        'number_of_people': number_of_people,
        'email': email
    }
    
    message_body = json.dumps(message)
    
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=message_body
    )
    
    print(f'SQS msg sent: {message}')
    
    
def elicit_slot(event, slot_to_elicit, message):
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'ElicitSlot',
                'slotToElicit': slot_to_elicit
            },
            'intent': event['sessionState']['intent']
        },
        'messages': [{
            'contentType': 'PlainText',
            'content': message
        }],
    }

def close(event, fulfillment_state, message):
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'Close',
                'fulfillmentState': fulfillment_state
            },
            'intent': event['sessionState']['intent']
        },
        'messages': [{
            'contentType': 'PlainText',
            'content': message
        }]
    }

def try_ex(func):
    try:
        return func()
    except:
        return None

def lambda_handler(event, context):
    intent_name = event['sessionState']['intent']['name']

    if intent_name == "GreetingIntent":
        message = "Hi there, how can I help?"
    elif intent_name == "ThankYouIntent":
        message = "You're welcome!"
    elif intent_name == "DiningSuggestionsIntent":
        return handle_dining_suggestions_intent(event)

    return {
              "sessionState": {
                "dialogAction": {
                  "type": "Close"
                },
                "intent": {
                  "name": intent_name,
                  "state": "Fulfilled"
                }
              },
              "messages": [{
                "contentType": "PlainText",
                "content": message
              }]
            }



