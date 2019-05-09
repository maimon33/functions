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
import re
import json
import time
import logging

from datetime import datetime
from datetime import timedelta

import boto3

from botocore.exceptions import ClientError

DATE_FORMAT = "%Y-%m-%dT%H.%M.%S"
LOGLEVEL = os.getenv('LOG_LEVEL', 'ERROR').strip()
INSTANCE_ID = os.getenv('INSTANCE_ID').split(",")
INSTANCE_NAME_PREFIX = os.getenv('INSTANCE_NAME_PREFIX').split(",")
COPIES_TO_KEEP = int(os.getenv('COPIES_TO_KEEP'))
SNS_TOPIC = os.getenv('SNS_TOPIC')
INTERVAL = os.getenv('INTERVAL').lower()


logger = logging.getLogger()
logger.setLevel(LOGLEVEL.upper())


def update_sns(instance_name, duration):
    sns_client = boto3.client('sns', region_name='eu-west-1')
    subject = 'AMI missing'.format(instance_name)
    response = sns_client.publish(
        TopicArn=SNS_TOPIC,
        Message=subject,
        Subject='No AMI have been create for {}, Last AMI created {} hours ago'.format(instance_name, duration),
    )
    
def lambda_handler(event, context):
    instance_dictionary = {}
    client = boto3.client('ec2')
    resource = boto3.resource('ec2')
    
    instances = client.describe_instances()
    images = resource.images.filter(Owners=['self'])
    
    if INTERVAL == "daily":
        hours_between_amis = 24
    elif INTERVAL == "weekly":
        hours_between_amis = 168
    else:
        hours_between_amis = 0
    
    # Get instance for the account
    for reservation in instances["Reservations"]:
        for instance in reservation["Instances"]:
            for tag in instance["Tags"]:
                if tag["Key"] == "Name" and tag["Value"] in INSTANCE_NAME_PREFIX:
                    instance_id = instance["InstanceId"]
                    instance_dictionary[instance_id] = []
    
    # Get AMIs for instanses requested
    for image in images:
        try:
            if image.name.split(" ")[2] in instance_dictionary.keys():
                instance_name = image.name.split(" ")[2]
                image_date = datetime.strptime(image.creation_date[:-5].replace(":","."), DATE_FORMAT).strftime(DATE_FORMAT)
                instance_dictionary[instance_name].append("{} {}".format(image_date, image.image_id))
        except Exception as e:
            print(e)
            continue
    
    # Sort Images by date and reverse to 
    for key, value in instance_dictionary.items():
        value.sort(reverse=True)
        
    # Create an AMI if the time has come
    for instance, snapshots in instance_dictionary.items():
        now = datetime.now().strftime(DATE_FORMAT)
        try:
            newest_ami_date = snapshots[0].split(" ")[0]
        except IndexError:
            newest_ami_date = (datetime.now() - timedelta(days=365)).strftime(DATE_FORMAT)
            
        difference = datetime.now().strptime(now, DATE_FORMAT) - datetime.strptime(newest_ami_date, DATE_FORMAT)

        if difference.total_seconds() / 3600 >= hours_between_amis:
            try:
                print("taking snapshot")
                creating = "true"
                client.create_image(InstanceId=instance, Name="Lambda - {} from {}".format(instance, now), Description="Lambda created AMI of instance {} from {}".format(instance, now), NoReboot=True, DryRun=False)
            except ClientError as e:
                creating = "true"
                print("AMI already being created")
        else:
            print("nothing to do")
            creating = "false"
            
        if difference.total_seconds() / 3600 > hours_between_amis + 1 and creating == "false":
            hours_since_last_ami = difference.total_seconds() / 3600
            update_sns(instance, hours_since_last_ami)
        else:
            print("all good - nothing to do")
        
    # Delete the oldest AMI if we exceed retention policy
    for instance, snapshots in instance_dictionary.items():
        ami_to_keep = COPIES_TO_KEEP - 1
        for ami in snapshots[ami_to_keep:]:
            ami_id = ami.split(" ")[1]
            try:
                ami_delete = client.deregister_image(DryRun=False, ImageId=ami_id)
            except ClientError as e:
                print(e)


if __name__ == '__main__':
    lambda_handler(None, None)
    