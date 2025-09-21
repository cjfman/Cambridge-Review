import json
import os
import requests

class AddressMap:
    def __init__(self, api_key, cache_path=None, *, verbose=False):
        self.api_key    = api_key
        self.cache_path = cache_path
        self.cache      = {}
        self.updated    = False
        self.verbose    = verbose
        if self.cache_path:
            self.load()

    def load(self):
        if not os.path.isfile(self.cache_path):
            print(f"Can't load address cache file '{self.cache_path}'")
            return

        try:
            with open(self.cache_path, encoding='utf8') as f:
                self.cache = json.load(f)
        except Exception as e:
            print(f"Failed to load address cache file '{self.cache_path}': {e}")

    def save(self):
        if not self.updated:
            if self.verbose:
                print("Cache wasn't updated. Not writing to file")
            return

        print("Cache changed size. Writing cache to file")
        try:
            with open(self.cache_path, 'w', encoding='utf8') as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            print(f"Failed to save address cache file '{self.cache_path}': {e}")

    def query_address(self, addr):
        if addr in self.cache:
            return self.cache[addr]

        if not self.api_key:
            print("Cannot access google maps API without an access key")
            return None

        coord = utils.address_to_coordinates(addr, self.api_key)
        print(f"{addr} >> {coord}")
        self.cache[addr] = coord
        self.updated = True
        return coord

    def __getitem__(self, key):
        if key not in self.cache:
            val = self.query_address(key)
            if val:
                self.cache[key] = val

            return val

        return self.cache[key]

    def __setitem__(self, key, value):
        self.updated = True
        self.cache[key] = value

    def __contains__(self, item):
        return (item in self.cache)


def address_to_coordinates(address, key, *, quiet=True):
    #url = f"https://maps.googleapis.com/maps/api/geocode/json?address=1600+AmphitheatreParkway,+Mountain+View,+CA&key={key}"
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    if not quiet:
        print(f"Making API request to {url}")

    ## Make the request
    resp = requests.get(url=url, params={
        'address': address.replace(' ', '+'),
        'key': key,
    })
    data = resp.json()
    if 'status' not in data or data['status'] != 'OK':
        if not quiet:
            print("Got bad response")
            print(data)

        return None

    ## There should be at least one result
    if not data['results']:
        if not quiet:
            print("Didn't find any results")

        return None

    ## Use the first result
    location = data['results'][0]['geometry']['location']
    return (location['lat'], location['lng'])
