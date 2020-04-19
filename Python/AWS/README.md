# AWS Python general purpose scripts

## s3_zip_ship.py
Download all objects from any number of buckets (matching a prefix), archiving and migrating to a destination bucket

### Installation
Install required packages<br>
`pip install -r s3_zip_ship_requirements.txt`

### Usage
Get current state<br>
`python s3_zip_ship.py -s my-buckets -t`

## sg_export.py
Output all Security group rules of the default AWS region set in AWS creds

### Installation
Install required packages<br>
`pip install -r sg_export_requirements.txt`

### Usage
* Get rules in table format
```
python sg_export.py table
+----------------------+--------+----------------------+---------------------+
|       GroupId        | In/Out |  Source/Destination  | From Port - To Port |
+----------------------+--------+----------------------+---------------------+
|     sg-25ewgcdc      |   In   |     sg-11111111      |     27017-27017     |
| sg-3867548756453552r |   In   |      0.0.0.0/0       |        80-80        |
| sg-3867548756453552r |  Out   |      0.0.0.0/0       |       0-65535       |
+----------------------+--------+----------------------+---------------------+
```
* Get rules in table JSON
```
python sg_export.py json resolve
{
    "sg-84758745tusdfg": {
        "Group Name": "reporter-all-outbound",
        "rules": [
            "Outbound: 9000-9000, To: test-server",
            "Outbound: 6666-6666, To: more-server",
            "Outbound: 7150-7150, To: more2-server"
        ]
    },
    "sg-111111": {
        "Group Name": "mongo-server",
        "rules": [
            "Inbound: 27017-27017, From: test-aggregator"
        ]
    }
}
```
**You can "resolve" security group to names if you add resolve at the end of the command**
