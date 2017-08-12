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
    return dictionary[0]['address_components'][index]['long_name']

def convert_coordinates_to_address(ip, depth):
    match = convert_ip_to_coordinates(ip)
    gmaps = googlemaps.Client(key=cfg["Dev API"])

    locations = []
    scales = range(7, 0, -1)
    depth = int(depth)
    while int(depth) > 0:
        try:
            break_dict(gmaps.reverse_geocode(match.location), depth)
            print break_dict(gmaps.reverse_geocode(match.location), scales[depth])
            if break_dict(gmaps.reverse_geocode(match.location), scales[depth]) == None:
                print "Yo"
            # if break_dict(gmaps.reverse_geocode(match.location), scales[depth]).isdigit():
            #     depth -= 1
            #     continue
            # else:
            locations.insert(0, (break_dict(gmaps.reverse_geocode(match.location), scales[depth])))
            depth -= 1
        except IndexError:
            depth -= 1
    return "%s, " * len(locations) % tuple(locations)


if __name__ == "__main__":
    try:
        sys.argv[2]
    except IndexError as error:
        sys.argv.append(2)
    print convert_coordinates_to_address(sys.argv[1], sys.argv[2])