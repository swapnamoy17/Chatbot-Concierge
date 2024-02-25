import json
import boto3
import http.client
from urllib.parse import urlparse
import base64

dynamo_table = '' #DynamoDB Table Name (One that stores restaurant Info)
user_preferences_table = '' #DynamoDB Table name (One that stores user's previous restaurant suggestions)
elastic_search_url = "" #Elastic Search Domain URL
username = "" # Elastic Username
password = "" #Elastic Search Password
sqs_url = "" #SQS Queue Q1 URL
email_id = "" #Source EmailID

def get_message_from_sqs():
    sqs_client = boto3.client('sqs')
    response = sqs_client.receive_message(
        QueueUrl=sqs_url,
        MaxNumberOfMessages=1)
    if 'Messages' in response:
        message = response['Messages'][0]
        return message, sqs_client
    else:
        return None, sqs_client

def get_restaurant_ids(cuisine):
    url = urlparse(elastic_search_url + '/restaurants/_search')
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic " + base64.b64encode(bytes(username + ":" + password, "utf-8")).decode("utf-8")
    }
    
    query = json.dumps({
        "size": 7,
        "query": {
            "match": {
                "Cuisine": cuisine.lower()
            }
        }
    }).encode("utf-8")
    
    if url.scheme == 'https':
        conn = http.client.HTTPSConnection(url.netloc)
    else:
        conn = http.client.HTTPConnection(url.netloc)
    
    conn.request("POST", url.path, body=query, headers=headers)
    response = conn.getresponse()
    
    if response.status != 200:
        return []
    
    data = json.loads(response.read().decode())
    
    restaurant_ids = [hit['_source']['RestaurantID'] for hit in data['hits']['hits']]
    
    conn.close()
    
    return restaurant_ids

def connect_dynamo():
    database = boto3.resource('dynamodb')
    table = database.Table(dynamo_table)
    return table

#Fetch restaurant info from dynamoDB using ElasticSearch ids
def get_restaurants(table, restaurant_ids):
    restaurants = []

    for restaurant_id in restaurant_ids:
        response = table.get_item(
            Key={
                'id': restaurant_id 
            }
        )

        if 'Item' in response:
            restaurants.append(response['Item'])
    
    return restaurants

def construct_message(restaurants, location, cuisine, dining_date, dining_time, number_of_people, email):
    email_message = f"Hello! Here are my {cuisine.capitalize()} restaurant suggestions for {number_of_people} people, for {dining_date} at {dining_time}: <br><br>"
    index = 1
    for restaurant in restaurants:
        email_message += f"{index}. {restaurant['name']}, located at {restaurant['address']}. It has an average rating of {restaurant['rating']}. You can contact them on {restaurant['contact']}. <br><br>"
        index += 1
    email_message += f"Enjoy your meal!"

    return email_message

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

def delete_sqs_message(sqs, sqs_url, message):
    receipt_handle = message['ReceiptHandle']
    sqs.delete_message(QueueUrl=sqs_url, ReceiptHandle=receipt_handle)
    print("Deleted message successfully!")

#Add/update user preference in dynamoDB table 
def store_user_preferences(email, email_message):
    database = boto3.resource('dynamodb')
    table = database.Table(user_preferences_table)
    table.put_item(
        Item={
            'email_id': email,
            'message': email_message
        }
    )
    print("Successfully put the item!")
    
    
def lambda_handler(event, context):
    message, sqs_client = get_message_from_sqs()
    message_body = message['Body']
    message_json = json.loads(message_body)
    location = message_json.get('location')
    cuisine = message_json.get('cuisine')
    dining_date = message_json.get('dining_date')
    dining_time = message_json.get('dining_time')
    number_of_people = message_json.get('number_of_people')
    email = message_json.get('email')
    
    restaurant_ids = get_restaurant_ids(cuisine)
    table = connect_dynamo()
    restaurants = get_restaurants(table, restaurant_ids)
    
    email_message = construct_message(restaurants, location, cuisine, dining_date, dining_time, number_of_people, email)
    send_email(email, email_message)
    store_user_preferences(email, email_message)
    
    delete_sqs_message(sqs_client, sqs_url, message)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Successfully processed SQS messages.')
    }
