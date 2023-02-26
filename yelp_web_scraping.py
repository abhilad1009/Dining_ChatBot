
from __future__ import print_function

import argparse
import urllib
import pprint
import requests
import json
import sys


from urllib.parse import quote
from urllib.parse import urlencode
from urllib.error import HTTPError





API_KEY= "jWJ50fMAXC-U-St1QtpBvhIjZlcZ77UiBb3ObEObKoWjrl7xfLFlVLZYlRGfJpL4HxUZuV-f8_8RBMPWAPNEgin1DswWcEihGo4i_z6QHLZvcaTKHuIt6JcWOrryY3Yx" 



myapihost = 'https://api.yelp.com'
mysearchpath = '/v3/businesses/search'
mybusinesspath = '/v3/businesses/'  


DEFAULT_CUISINE = 'indian restaurants'
DEFAULT_LOCATION = 'Manhattan'
mysearchlimit = 50


def request(host, path, api_key, url_params=None):
    url_params = url_params or {}
    url = '{0}{1}'.format(host, quote(path.encode('utf8')))
    headers = {
        'Authorization': 'Bearer %s' % api_key,
    }

   

    response = requests.request('GET', url, headers=headers, params=url_params)
    with open('mediterranean_restaurants.json', 'a') as openfile:
        json.dump(response.json(), openfile)
	
    return response.json()


def search(api_key, term, location, OFFSET):
    

    url_params = {
        'term': term.replace(' ', '+'),
        'location': location.replace(' ', '+'),
        'limit': mysearchlimit,
        'offset': OFFSET
    }
    return request(myapihost, mysearchpath, api_key, url_params=url_params)


def retrieve_business(api_key, business_id):
    
    business_path = mybusinesspath + business_id

    return request(myapihost, business_path, api_key)


def query_api(term, location):
    for i in range(26):
        curr_offset = i*50
        response = search(API_KEY, term, location,curr_offset)
        
        businesses = response.get('businesses')
        
        if not businesses:
            print(u'There were no businesses for {0} in {1} found.'.format(term, location))
            return

        business_id = businesses[0]['id']
        response = retrieve_business(API_KEY, business_id)

      


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-q', '--term', dest='term', default=DEFAULT_CUISINE,
                        type=str, help='Search term')
    parser.add_argument('-l', '--location', dest='location',
                        default=DEFAULT_LOCATION, type=str,
                        help='Search location')

    input_args = parser.parse_args()

    try:
        query_api(input_args.term, input_args.location)
        
        
    except HTTPError as error:
        sys.exit(
            'HTTP error was encountered {0} on {1}:\n {2}'.format(
                error.code,
                error.url,
                error.read(),
            )
        )


if __name__ == '__main__':
    main()
