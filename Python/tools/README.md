# Misc Tools

### whereisip
Get the physical location based on Google GeoIP translation.

This tool reqires two extrnal Python packages
```
pip install python-geoip-geolite2
pip install -U googlemaps
```

To use Google Developer API you'll need to get API key. [here](https://developers.google.com/maps/documentation/geocoding/start)<br>
Once you have the key place it in _*.cfg_ like so:
```$xslt
{
  "Google Developer API": {
    "Dev API": "AIrt78tyhgig...*"
    }
  }
```

__usage__<br> 
```
$ python wheresip.py 98.138.253.109
Sunnyvale, Bay Trail
```

