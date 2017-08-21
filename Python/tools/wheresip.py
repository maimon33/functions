#!/usr/bin/env python

import os
import sys
import json

import googlemaps
from geoip import geolite2


CONFIG_PATH = '{0}/google-dev-api.cfg'.format(os.getenv("HOME"))

with open(CONFIG_PATH) as config_file:
    cfg = json.load(config_file)["Google Developer API"]


def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)

def convert_ip_to_coordinates(ip):
    if geolite2.lookup(ip) is None:
        print "Can't locate IP"
        sys.exit(1)
    else:
        return geolite2.lookup(ip)

def break_dict(dictionary, index):
    try:
        return dictionary[0]['address_components'][index]['long_name']
    except IndexError:
        return "Out of scope"

def convert_coordinates_to_address(ip, depth):
    match = convert_ip_to_coordinates(ip)
    gmaps = googlemaps.Client(key=cfg["Dev API"])

    locations = []
    depth = int(depth)
    for scale in range(8, 0, -1):
        fetch_location = break_dict(gmaps.reverse_geocode(match.location), scale)
        if fetch_location != "Out of scope":
            if fetch_location.isdigit():
                continue
            else:
                locations.append(fetch_location)
        else:
            scale -= 1
    locations = locations[:depth]
    return ("%s, " * len(locations) % tuple(locations))[:-2]


if __name__ == "__main__":
    try:
        if int(sys.argv[2]) > 7:
            print "Can't zoom in that close..."
            sys.argv[2] = 6
    except IndexError as error:
        sys.argv.append(2)
    print convert_coordinates_to_address(sys.argv[1], sys.argv[2])