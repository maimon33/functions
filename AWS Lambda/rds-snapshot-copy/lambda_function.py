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
SNS_TOPIC = os.getenv('SNS_TOPIC')
DESTINATION_KMS_ID = os.getenv('DESTINATION_KMS_ID')
SOFT_ALERT_HOURS = int(os.getenv('SOFT_ALERT_HOURS'))
SNAPSHOTS_TO_KEEP = int(os.getenv('SNAPSHOTS_TO_KEEP'))
LAMBDA_NAME = os.getenv('AWS_LAMBDA_FUNCTION_NAME')

logger = logging.getLogger()
logger.setLevel(LOGLEVEL.upper())


def get_status(snapshot_id):
    return client.describe_db_snapshots(DBSnapshotIdentifier=snapshot_id)['DBSnapshots'][0]['Status']

def update_sns(snapshot_id):
    sns_client = boto3.client('sns', region_name='eu-west-1')
    response = sns_client.publish(
        TopicArn=SNS_TOPIC,
        Message='Sanpshot {} copied to {} Account'.format(snapshot_id, "Backup"),
        Subject='RDS Snapshot Update for Lambda:"{}"'.format(LAMBDA_NAME),
    )
    
def lambda_handler(event, context):
    snapshots_dict = {}
    my_db_snapshots = []
    client = boto3.client('rds')
    
    # Get Snapshots List and sort
    snapshots = client.describe_db_snapshots(IncludeShared=True)['DBSnapshots']
        
    for snapshot in snapshots:
        if PATTERN in snapshot["DBInstanceIdentifier"] and \
        snapshot["DBSnapshotIdentifier"].startswith("arn"):
            my_db_snapshots.append(snapshot["DBSnapshotIdentifier"])

    
    # Copy to destination region
    for snapshot in my_db_snapshots:
        try:
            rds_copy = client.copy_db_snapshot(
                SourceDBSnapshotIdentifier="{}".format(snapshot),
                TargetDBSnapshotIdentifier=snapshot.split(":")[6],
                KmsKeyId=DESTINATION_KMS_ID)
            update_sns(snapshot)
        except botocore.errorfactory.ClientError as e:
            print("Sanpshot already exist! No copying needed")
    
    
if __name__ == '__main__':
    lambda_handler(None, None)