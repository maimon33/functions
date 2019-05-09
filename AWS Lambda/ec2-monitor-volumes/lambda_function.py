'''
Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/apache2.0/

or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
'''

import os
import json
import logging
import datetime

import boto3

from datetime import datetime
from datetime import timedelta
from botocore.exceptions import ClientError

LOGLEVEL = os.getenv('LOG_LEVEL', 'ERROR').strip()
INSTACE_NAME = os.getenv('INSTACE_NAME')
INTERVAL = os.getenv('ALERT_RATE')


logger = logging.getLogger()
logger.setLevel(LOGLEVEL.upper())

def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)

def lambda_handler(event, context):
    dnow = datetime.now()
    instance_dictionary = {}
    client = boto3.client('ec2')
    watch = boto3.client('cloudwatch')
    
    instances = client.describe_instances()
    
    root_list = []
    instance_list = []
    
    # Get root volumes for the instances of interest
    for reservation in instances["Reservations"]:
        for instance in reservation["Instances"]:
            instance_dict = {}
            volume_dict = {}

            try:
                if instance["Tags"]:
                    pass
            except KeyError:
                continue

            for tag in instance["Tags"]:
                if INSTACE_NAME in tag["Value"] and tag["Key"] == "Name":
                    instance_list.append(instance["InstanceId"])
                    root_device = instance["RootDeviceName"]
                    for device in instance["BlockDeviceMappings"]:
                        if device["DeviceName"] == root_device:
                            volume_dict[root_device] = device["Ebs"]["VolumeId"]
                            instance_dict[instance["InstanceId"]] = volume_dict
                            root_list.append(instance_dict)

    response = watch.get_metric_statistics(
            Namespace='AWS/EBS',
            MetricName='BurstBalance',
            Dimensions=[
                {
                    'Name': 'VolumeId',
                    'Value': 'vol-0dd916669f9f767c0'
                },
            ],
            StartTime=dnow+timedelta(hours=-5),
            EndTime=dnow,
            Period=300,
            Statistics=['Average']
        )

    # print(response["Datapoints"])
    for pick in response["Datapoints"]:
        t = pick["Timestamp"]
        timestamp = t.strftime('%Y/%m/%d-%H:%M')
        print(timestamp, pick["Average"])
    
    for instance in root_list:
        for instance_id, volume in instance.items():
            for dev_name, volume_id in volume.items():
                pass
                # volume = resource.Volume(volume_id)
                # print(volume.describe_attribute())
                # volume_burst = client.describe_volumes(VolumeIds=[volume_id])
                # print(volume_burst.viewkeys())
                # break
                # print(client.describe_volumes(VolumeIds=[volume_id]))
                # print(volume_id)
            
        # volume_burst = client.describe_volumes(VolumeIds=[device["Ebs"]["VolumeId"]])
    
                
if __name__ == '__main__':
    lambda_handler(None, None)
    