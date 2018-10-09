'''
Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/apache2.0/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
'''

# delete_old_snapshots_aurora
# This Lambda function will delete snapshots that have expired and match the regex set in the PATTERN environment variable. It will also look for a matching timestamp in the following format: YYYY-MM-DD-HH-mm
# Set PATTERN to a regex that matches your Aurora cluster identifiers (by default: <instance_name>-cluster)
import boto3
from datetime import datetime
import time
import os
import logging
import re
import json

LOGLEVEL = os.getenv('LOG_LEVEL', 'ERROR').strip()
PATTERN = os.getenv('PATTERN', 'ALL_CLUSTERS')
USE_SNAPSHOT_ID = os.getenv('USE_SNAPSHOT_ID', 'NO')
RETENTION_DAYS = int(os.getenv('FULL_BACKUPS_DAYS'))
RETENTION_DAYS_EXTENDED = int(os.getenv('DAILY_BACUPS_DAYS'))
LAMBDA_NAME = os.getenv('AWS_LAMBDA_FUNCTION_NAME')

if os.getenv('REGION_OVERRIDE', 'NO') != 'NO':
    REGION = os.getenv('REGION_OVERRIDE').strip()
else:
    REGION = os.getenv('AWS_DEFAULT_REGION')


logger = logging.getLogger()
logger.setLevel(LOGLEVEL.upper())


def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)
    
def get_status(snapshot_id):
    return client.describe_db_snapshots(DBSnapshotIdentifier=snapshot_id)['DBSnapshots'][0]['Status']
    
def update_sns(snapshot_id):
    sns_client = boto3.client('sns', region_name='eu-west-1')
    response = sns_client.publish(
        TopicArn=SNS_TOPIC,
        Message='Sanpshot {} deleted from {} Account'.format(snapshot_id, "Backup"),
        Subject='RDS Snapshot Update for Lambda:"{}"'.format(LAMBDA_NAME),
    )


def lambda_handler(event, context):
    snapshots_dict = {}
    pending_delete = 0
    client = boto3.client('rds', region_name=REGION)
    response = client.describe_db_snapshots(SnapshotType='manual')

    for snapshot in response["DBSnapshots"]:

        if USE_SNAPSHOT_ID == "YES":
            # Get creation date from snapshot id
            snapshot_id = snapshot["DBSnapshotIdentifier"]
            creation_date = datetime.strptime(snapshot_id.split("prodmysql-replica-")[1], "%Y-%m-%d-%H-%M")
            creation_date = creation_date.strftime("%Y-%m-%d")
        else:
            try:
                creation_date = snapshot["SnapshotCreateTime"].strftime("%Y-%m-%d")
            except KeyError:
                print("No backups today")
        
        if snapshot['Status'] == "available":
            if creation_date in snapshots_dict:
                snapshots_dict[creation_date].append(snapshot["DBSnapshotIdentifier"])
            else:
                snapshots_dict[creation_date] = [snapshot["DBSnapshotIdentifier"]]    
            
    for day in snapshots_dict:
        
        now = datetime.now().strftime("%Y-%m-%d")
        difference = datetime.now().strptime(now, "%Y-%m-%d") - datetime.strptime(day, "%Y-%m-%d")
        
        # if we are past RETENTION_DAYS, keep one
        if difference.days > RETENTION_DAYS:
            for snapshot in snapshots_dict[day][1:]:
                # Delete snapshots, keep just one per day past this period
                print("Deleting Snapshot: {}".format(snapshot))
                client.delete_db_snapshot(DBSnapshotIdentifier=snapshot)
                update_sns(snapshot)
                print("Snapshot {} Deleted.".format(snapshot))

        # if we are past RETENTION_DAYS_EXTENDED, Delete all
        if difference.days > RETENTION_DAYS_EXTENDED:
            for snapshot in snapshots_dict[day]:
                # Delete all snapshots past retention
                print("Deleting Snapshot: {}".format(snapshot))
                client.delete_db_snapshot(DBSnapshotIdentifier=snapshot)
                update_sns(snapshot)
                print("Snapshot {} Deleted.".format(snapshot))


if __name__ == '__main__':
    lambda_handler(None, None)