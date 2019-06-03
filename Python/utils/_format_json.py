import json

def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)