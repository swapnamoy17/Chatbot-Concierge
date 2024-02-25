# Chatbot Concierge #

## Frontend ##
1. Replace `frontend/assets/js/sdk/apigClient.js` with your own SDK file from API
   Gateway.

## Lambda Functions ##

1. LF0: (index.mjs): Add the Lex V2 BotAliasID and BotID
2. LF1: Add SQS Queue Q1 URL, DynamoDB Table Name and source emailID.
3. LF2: Add SQS Queue Q1 URL, DynamDB Table Name, source emailID and ElasticSearch details.

## OtherScripts ##

1. dynamo.py: Fetches restaurant information from yelp, stores it in DynamoDB and creates import json for ElasticSearch.
              Add DynamoDB Table Name and YELP API Access Key.

