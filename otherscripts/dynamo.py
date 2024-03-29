import requests
from datetime import datetime
import boto3
from decimal import Decimal
import json

class RestaurantData:
    def __init__(self):
        self.restaurant_ids = set()

    def is_empty(self, value):
        return not value or len(str(value)) == 0

    #Formatting data fetched from yelp
    def _format_data(self, entry, cuisine):
        formatted = {}
        self.restaurant_ids.add(entry['id'])

        formatted['id'] = entry['id']
        formatted['insertedAtTimestamp'] = str(datetime.now())
        formatted['cuisine_type'] = 'indian' if cuisine == 'indpak' else cuisine
        formatted['name'] = entry['name']
        formatted['url'] = entry['url']

        if not self.is_empty(entry.get("rating")):
            formatted["rating"] = Decimal(str(entry["rating"]))
        if not self.is_empty(entry.get("coordinates")):
            formatted["latitude"] = Decimal(str(entry["coordinates"]["latitude"]))
            formatted["longitude"] = Decimal(str(entry["coordinates"]["longitude"]))
        if not self.is_empty(entry.get("phone")):
            formatted["contact"] = entry["phone"]
        if not self.is_empty(entry.get("review_count")):
            formatted["review_count"] = entry["review_count"]
        if not self.is_empty(entry.get("price")):
            formatted["price"] = entry["price"]

        if entry.get('location'):
            address = "".join(entry['location']['display_address'])
            formatted['address'] = address
            formatted["zip_code"] = entry['location']['zip_code']

        return formatted

    def fetch_yelp_data(self, api, api_key):
        headers = {"Authorization": "Bearer " + api_key}
        cuisines = ['indpak', 'italian', 'mexican', 'chinese', 'japanese']
        location = 'manhattan'
        all_data = []

        for cuisine in cuisines:
            total_entries = 50
            offset = 0
            while total_entries > 0:
                params = {
                    'location': location,
                    'categories': cuisine,
                    'limit': 50,
                    'offset': offset
                }
                response = requests.get(api, headers=headers, params=params).json()
                if response.get("businesses"):
                    for entry in response["businesses"]:
                        if entry['id'] in self.restaurant_ids:
                            continue
                        all_data.append(self._format_data(entry, cuisine))
                    total_entries -= len(response["businesses"])
                    offset += len(response["businesses"])
                else:
                    break

        return all_data

    def store_data(self, restaurant_data):
        dynamodb = boto3.resource('dynamodb',
                                  aws_access_key_id='',
                                  aws_secret_access_key='',
                                  region_name='us-east-1')
        table = dynamodb.Table('')                      #DynamoDB Table Name (One that stores restaurant Info)
        for data in restaurant_data:
            table.put_item(Item=data)
    
    #generating json that will be imported into ElasticSearch
    def generate_elasticsearch_json(self, restaurant_data):
        es_data = []
        for data in restaurant_data:
            es_entry = {
                'RestaurantID': data['id'],       
                'Cuisine': data['cuisine_type']  
            }
            index_action = {
                "index": {
                    "_index": "restaurants",  
                    "_id": data['id'] 
                }
            }
            es_data.append(index_action)
            es_data.append(es_entry)
        
        with open('elasticsearch_data.json', 'w') as file:
            for entry in es_data:
                file.write(json.dumps(entry) + '\n')


if __name__ == '__main__':
    api_url = 'https://api.yelp.com/v3/businesses/search'
    api_access_key = ''      #yelp API access key

    processor = RestaurantData()
    data = processor.fetch_yelp_data(api_url, api_access_key)
    processor.store_data(data)
    processor.generate_elasticsearch_json(data)