#!/bin/python

import os
import requests

import boto3


ACCESS_KEY = os.environ.get['AWS_ACCESS_KEY_ID']
SECRET_KEY = os.environ.get['AWS_SECRET_ACCESS_KEY']
TARGET_GROUP_ARN = '<Your target group ARN here>'
REGION_NAME = 'eu-west-1'


response = requests.get('http://169.254.169.254/latest/meta-data/instance-id')
INSTANCE_ID = response.text

client = boto3.client('elbv2',
                      aws_access_key_id=ACCESS_KEY,
                      aws_secret_access_key=SECRET_KEY,
                      region_name=REGION_NAME)

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
