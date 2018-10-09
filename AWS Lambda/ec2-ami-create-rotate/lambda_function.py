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

import boto3

from botocore.exceptions import ClientError

DATE_FORMAT = "%Y-%m-%d"
LOGLEVEL = os.getenv('LOG_LEVEL', 'ERROR').strip()
INSTANCE_ID = os.getenv('INSTANCE_ID').split(",")
COPYS_TO_KEEP = int(os.getenv('COPYS_TO_KEEP'))
INTERVAL = os.getenv('INTERVAL').lower()


logger = logging.getLogger()
logger.setLevel(LOGLEVEL.upper())


def lambda_handler(event, context):
    instance_dictionary = {}
    client = boto3.client('ec2')
    resource = boto3.resource('ec2')
    
    instances = client.describe_instances()
    images = resource.images.filter(Owners=['self'])
    
    if INTERVAL == "daily":
        hours_between_amis = 24
    elif INTERVAL == weekly:
        hours_between_amis = 168
    else:
        hours_between_amis = 0
    
    # Get instance for the account
    for reservation in instances["Reservations"]:
        for instance in reservation["Instances"]:
            if instance["InstanceId"] in INSTANCE_ID:
                instance_id = instance["InstanceId"]
                instance_dictionary[instance_id] = []
            else:
                print("Instance Not Found!")
    
    # Get AMIs for instanses requested
    for image in images:
        for target_instance in INSTANCE_ID:
            try:
                instance_name = image.name.split(" ")[2]
                image_date = image.name.split(" ")[4]
            except:
                continue
            
            if instance_name in instance_dictionary.keys():
                ami_list = instance_dictionary[instance_name]
                ami_list.append("{} {}".format(image_date, image.image_id))
                instance_dictionary[instance_name] = ami_list
                
    # Sort Images by date and reverse to 
    for key, value in instance_dictionary.items():
        value.sort(reverse=True)
        
    # Create an AMI if the time has come
    for instance, snapshots in instance_dictionary.items():
        now = datetime.now().strftime("%Y-%m-%d")
        newest_ami_date = snapshots[0].split(" ")[0]
        difference = datetime.now().strptime(now, "%Y-%m-%d") - datetime.strptime(newest_ami_date, "%Y-%m-%d")
        if difference.days > hours_between_amis / 24:
            try:
                client.create_image(InstanceId=instance_id, Name="Lambda - " + instance + " from " + now, Description="Lambda created AMI of instance " + instance + " from " + now, NoReboot=True, DryRun=False)
            except ClientError as e:
                print("AMI already being created")
        else:
            print("nothing to do")
        
    # Delete the oldest AMI if we exceed retention policy
    for instance, snapshots in instance_dictionary.items():
        ami_to_keep = COPYS_TO_KEEP - 1
        for ami in snapshots[ami_to_keep:]:
            ami_id = ami.split(" ")[1]
            try:
                ami_delete = client.deregister_image(DryRun=False, ImageId=ami_id)
            except ClientError as e:
                print(e)


if __name__ == '__main__':
    lambda_handler(None, None)
    