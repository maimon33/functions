import re
import sys
import json
import datetime as Time

from datetime import datetime

import boto3

from botocore.exceptions import ClientError

AWS_REGIONS = []

ROLE_ARN = 'arn:aws:iam::{}:role/cloudtrail-reader'

try:
    print "Hi"
    prir = boto3.client("ec2").describe_regions()
    print dir(prir)
    print type(boto3.client("ec2").describe_regions())
    for region in boto3.client("ec2").describe_regions().values()[0]:
        AWS_REGIONS.append(region["RegionName"])
except ClientError as e:
    print('Failed to Authenticate your AWS account\n'
    'Review your boto credentials file at ~/.aws/credentials')
    sys.exit()

def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)

class AWSRanger(object):
    def __init__(self, accountid):
        response = boto3.client("sts").assume_role(DurationSeconds=3600, 
                                                ExternalId="cloudtrail-reader",
                                                RoleArn=ROLE_ARN.format(accountid),
                                                RoleSessionName="cloudtrail-reader")
        self.tmp_access_key = response["Credentials"]["AccessKeyId"]
        self.tmp_secret_key = response["Credentials"]["SecretAccessKey"]
        self.tmp_security_token = response["Credentials"]["SessionToken"]

    
    def aws_client(self, resource=False, region_name="eu-west-1", aws_service="ec2"):
        if aws_service == "cloudtrail":
            client = boto3.client("cloudtrail",
                                  aws_access_key_id=self.tmp_access_key, 
                                  aws_secret_access_key=self.tmp_secret_key, 
                                  aws_session_token=self.tmp_security_token)
            return client

        session = boto3.Session(aws_access_key_id=self.tmp_access_key, 
                                aws_secret_access_key=self.tmp_secret_key, 
                                aws_session_token=self.tmp_security_token)
      
        if resource:
            return session.resource(aws_service, region_name=region_name)
        else:
            return session.client(aws_service, region_name=region_name)

    def get_account_alias(self, accountid):
        try:
            return self.aws_client(aws_service="iam").list_account_aliases()["AccountAliases"][0]
        except IndexError:
            return accountid

    def get_cloudtrail_events(self, resourceid):
        short_actions_dict = {}
        action = {}
        inspect_event = []
        try:
            all_instance_events = self.aws_client(aws_service="cloudtrail").lookup_events(
                LookupAttributes=[{'AttributeKey': 'ResourceName', 'AttributeValue': resourceid}])
            for event in all_instance_events["Events"]:
                if event["EventName"] in ["StartInstances", "RunInstances"]:
                    action_time = re.search(r'eventTime\"\:\"(.*?)\"', event["CloudTrailEvent"]).group(1)
                    eventid = event["EventId"]
                    short_actions_dict[eventid] = action_time
                    inspect_event.append(event)
            events_list = sorted(short_actions_dict, key=short_actions_dict.__getitem__)
            for event in inspect_event:
                if event["EventId"] == events_list[0]:
                    last_action = re.search(r'eventName\"\:\"(.*?)\"', event["CloudTrailEvent"]).group(1)
                    action_time = re.search(r'eventTime\"\:\"(.*?)\"', event["CloudTrailEvent"]).group(1)
                    action["Action Type"] = last_action
                    action["Action Time"] = action_time
            return action
        except ClientError as e:
            return "Failed to search Cloudtrail"


if __name__ == "__main__":
    try:
        account = sys.argv[1]
        resorce_name = sys.argv[2]

        print "Now Working on account: {}".format(account)

        try:
            watcher = AWSRanger(account)
        except ClientError as e:
            print('Failed to Authenticate your AWS account\n'
            'Review your boto credentials file at ~/.aws/credentials')

        print watcher.get_cloudtrail_events(resorce_name)

    except KeyboardInterrupt:
        print "Aborted!"
