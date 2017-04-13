#!/bin/python

import os
import requests

import boto3


ACCESS_KEY = os.environ.get['AWS_ACCESS_KEY_ID']
SECRET_KEY = os.environ.get['AWS_SECRET_ACCESS_KEY']
TARGET_GROUP_ARN = <ENTER YOUR ELB NAME HERE>


response = requests.get('http://169.254.169.254/latest/meta-data/instance-id')
INSTANCE_ID = response.text

client = boto3.client('elb',
                      aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY,
                      region_name='eu-west-1')

def add_instance_to_elb():
    client.register_targets(
        TargetGroupArn=TARGET_GROUP_ARN,
        Targets=[
            {
                'Id': INSTANCE_ID,
                'Port': 80
            },
        ]
    )

add_instance_to_elb()
