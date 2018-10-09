'''
Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/apache2.0/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
'''

# delete_old_snapshots_aurora
# This Lambda function will delete snapshots that have expired and match the regex set in the PATTERN environment variable. It will also look for a matching timestamp in the following format: YYYY-MM-DD-HH-mm
# Set PATTERN to a regex that matches your Aurora cluster identifiers (by default: <instance_name>-cluster)
import os
import time
import json
import boto3
import logging
import botocore

from datetime import datetime, timedelta, timezone


LOGLEVEL = os.getenv('LOG_LEVEL', 'ERROR').strip()
DATE_FORMAT = "%Y-%m-%d-%H-%M"
PATTERN = os.getenv('PATTERN')
INTERVAL = int(os.getenv('INTERVAL'))
SNAPSHOTS_TO_KEEP = int(os.getenv('SNAPSHOTS_TO_KEEP'))
DESTINATION_REGION = os.getenv('DESTINATION_REGION')
DESTINATION_ACCOUNTS = os.getenv("DESTINATION_ACCOUNTS").split(",")
DESTINATION_KMS_ID = os.getenv('DESTINATION_KMS_ID')
USE_SNAPSHOT_ID = os.getenv('USE_SNAPSHOT_ID')
ACCOUNT_ID = boto3.client('sts').get_caller_identity().get('Account')
LAMBDA_NAME = os.getenv('AWS_LAMBDA_FUNCTION_NAME')

if os.getenv('REGION_OVERRIDE', 'NO') != 'NO':
    REGION = os.getenv('REGION_OVERRIDE').strip()
else:
    REGION = os.getenv('AWS_DEFAULT_REGION')

logger = logging.getLogger()
logger.setLevel(LOGLEVEL.upper())


def get_status(snapshot_id):
    return client.describe_db_snapshots(DBSnapshotIdentifier=snapshot_id)['DBSnapshots'][0]['Status']

def delete_snapshots_by_retention(client, snapshot_list, snapshot_to_keep):
    snapshot_list = snapshot_list[snapshot_to_keep:]
    for snapshot in snapshot_list:
        print("Deleting snapshot {}".format(snapshot))
        update_sns(snapshot, "delete")
        client.delete_db_snapshot(
            DBSnapshotIdentifier=snapshot
        )

def update_sns(snapshot_id, action):
    sns_client = boto3.client('sns', region_name='eu-west-1')
    if action == "delete":
        Subject = 'Sanpshot {} deleted'.format(snapshot_id)'
    elif action == "copy":
        subject = 'Sanpshot {} copied to {} Region'.format(snapshot_id, "Farnkfurt")'
    response = sns_client.publish(
        TopicArn=SNS_TOPIC,
        Message=subject,
        Subject='RDS Snapshot Update for Lambda:"{}"'.format(LAMBDA_NAME),
    )
    
def lambda_handler(event, context):
    snapshots_dict = {}
    my_db_snapshots = []
    snapshots_to_keep = []
    client = boto3.client('rds', region_name=REGION)
    
    
    # Get Snapshots List and sort
    snapshots = client.describe_db_snapshots(SnapshotType='manual')['DBSnapshots']
    
    if PATTERN and not 'None':
        snapshots = filter(lambda x: PATTERN in x.get('DBInstanceIdentifier'), snapshots)
        
    for snapshot in snapshots:
        if PATTERN in snapshot["DBInstanceIdentifier"]:
            if snapshot["Status"] == "creating":
                snapshots_dict[snapshot["DBSnapshotIdentifier"]] = "Still creating"
            else:
                my_db_snapshots.append(snapshot["DBSnapshotIdentifier"])
                snapshots_dict[snapshot["DBSnapshotIdentifier"]] = snapshot["SnapshotCreateTime"]
                
    my_db_snapshots.reverse()
    
    # Delete snapshots by retention policy
    short_retention = round(int(SNAPSHOTS_TO_KEEP)/4)
    print("Deleting from Region {}\n Keeping {} Snapshots".format(REGION, short_retention))
    delete_snapshots_by_retention(client, my_db_snapshots, short_retention)
        
    # Get last Snapshot ID and creation time
    last = sorted(snapshots_dict.keys())[-1]
    create_time = snapshots_dict[last]
    
    # If a snapshot is beaing created. skip Take Snapshot
    # Figure out if more than INTERVAL hours have apssed
    if create_time == "Still creating":
        pass
    else:
        time_since_last_backup = datetime.now(timezone.utc) - create_time
        snapshot_name = '{}-{}'.format(PATTERN, datetime.now(timezone.utc).strftime(DATE_FORMAT))
        if (INTERVAL * 3600) < time_since_last_backup.seconds:
            client.create_db_snapshot(
                DBSnapshotIdentifier=snapshot_name,
                DBInstanceIdentifier=PATTERN
            )
        
    # Change to Destination Region
    client = boto3.client('rds', region_name=DESTINATION_REGION)
    
    # Delete snapshots by retention policy
    print("Deleting from Region {}\n Keeping {} Snapshots".format(DESTINATION_REGION, SNAPSHOTS_TO_KEEP))
    delete_snapshots_by_retention(client, my_db_snapshots, SNAPSHOTS_TO_KEEP)
    
    # Copy to destination region
    try:
        rds_copy = client.copy_db_snapshot(
            SourceDBSnapshotIdentifier="arn:aws:rds:{}:{}:snapshot:{}".format(REGION, ACCOUNT_ID, last),
            TargetDBSnapshotIdentifier=last,
            KmsKeyId=DESTINATION_KMS_ID,
            SourceRegion=REGION)
        update_sns(last, "copy")
    except botocore.errorfactory.ClientError as e:
        # print(e)
        print("Sanpshot already exist! No copying needed")
    
    # Share snapshot with destination accounts
    print("Sharing Snapshots with accounts: {}".format(DESTINATION_ACCOUNTS))
    for snpahost in my_db_snapshots:
        # print("Now sharing snapshot {}".format(snapshot))
        for account in DESTINATION_ACCOUNTS:
            try:
                client.modify_db_snapshot_attribute(
                    DBSnapshotIdentifier=snpahost, 
                    AttributeName='restore', 
                    ValuesToAdd=[account])
            except botocore.errorfactory.ClientError as e:
                # print(e)
                print("Snapshot {} can't be shared".format(snapshot))
    
if __name__ == '__main__':
    lambda_handler(None, None)