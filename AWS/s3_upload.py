#!/bin/python

import os
import time
import boto3


ACCESS_KEY = os.environ['AWS_ACCESS_KEY_ID']
SECRET_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
BUCKET_NAME = ''
BASE_PATH = ''

s3 = boto3.resource('s3',
                        aws_access_key_id=ACCESS_KEY,
                        aws_secret_access_key=SECRET_KEY)


def s3_upload(data):
    current_minute = time.strftime("%Y/%m/%d/%I:%M")
    s3.Bucket(bucket_name).put_object(
        Key='{0}/{1}'.format(BASE_PATH, current_minute), Body=data)


s3_upload(data)