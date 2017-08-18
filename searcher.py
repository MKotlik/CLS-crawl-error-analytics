import requests
from pprint import pprint

ENDPOINT = "https://www.googleapis.com/customsearch/v1?"


def load_config(filename='config.cfg'):
    with open(filename) as config:
        conf_line = config.readline()
        if conf_line == "" or conf_line == "\n":
            print "SEARCHER: loading from config failed. Check format."
            return None
        else:
            parts = conf_line.split("=")
            if len(parts) != 2 or parts[0].strip().lower() != "api_key":
                print "SEARCHER: loading from config failed. Check format."
                return None
            else:
                api_key = parts[1].strip()
                return api_key


def get_base_url(api_key, engineID):
    if api_key is None:
        print "SEARCHER ERROR: please load Google API Key from config file"
        return None
    return ENDPOINT + "key=" + api_key + "&cx=" + engineID


def search(base_url, query):
    if base_url is None:
        print "SEARCHER ERROR: please load Google API Key from config file"
        return None
    resp = requests.get(base_url, {"q": query})
    if resp.status_code != 200:
        # Check for NoneType when calling func to check for error
        print "SEARCHER ERROR - Code: " + str(resp.status_code)
        print "SEARCHER ERROR - Message: "
        pprint(resp.json())
        return None
    resp_dict = resp.json()
    if resp_dict['searchInformation']['totalResults'] == '0':
        return []
    results = []
    for item in resp_dict['items']:
        results.append({'title': item['title'], 'link': item['link']})
    return results
