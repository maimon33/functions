#!/usr/bin/python
import sys
import json

import boto3

from prettytable import PrettyTable
    
def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)
    
def aws_client(resource=True, region_name="us-east-1", aws_service="ec2"):
    session = boto3.Session()
    if resource:
        return session.resource(aws_service, region_name=region_name)
    else:
        return session.client(aws_service, region_name=region_name)

def get_all_regions():
    region_list = []
    response = aws_client(resource=False).describe_regions()['Regions']
    for region in response:
        region_api_id = region['Endpoint'].split('.')[1]
        region_list.append(region_api_id)
    return region_list

def get_peering_name(peering_dict):
    for tag in peering_dict["Tags"]:
        if tag["Key"] == "Name":
            return tag["Value"]

def get_side_info(peering_dict, side):
    vpc_id = peering_dict[side]["VpcId"]
    vpc_cidr = peering_dict[side]["CidrBlock"]
    vpc_region = peering_dict[side]["Region"]
    return vpc_id, vpc_cidr, vpc_region
    

if __name__ == "__main__":
    
    regions = get_all_regions()

    try:
        if "no" in sys.argv:
            no_name = True
        else:
            no_name = False    
        
        if sys.argv[1] in regions:
            regions = []
            regions.append(sys.argv[1])
    except IndexError:
        no_name = False

    try:
        for region in regions:
            peerings = aws_client(
                resource=False, region_name=region).describe_vpc_peering_connections()
            peering_count = len(peerings["VpcPeeringConnections"])
            if peering_count > 0:
                x = PrettyTable()
                x.field_names = ["peering name", "Local VPC", "Local cidr", "Remote region", "Remote VPC", "Remote cidr"]
                print("Peering connections in Region: {} ({})".format(region, peering_count))
                for peering in peerings["VpcPeeringConnections"]:
                    local_vpc = []
                    remote_vpc = []
                    if no_name:
                        peering_name = peering["VpcPeeringConnectionId"]
                    else:
                        peering_name = get_peering_name(peering)
                    accepter_info = get_side_info(peering, "AccepterVpcInfo")
                    requester_info = get_side_info(peering, "RequesterVpcInfo")
                    if region == accepter_info[2]:
                        local_vpc.append(accepter_info[0])
                        local_vpc.append(accepter_info[1])
                        remote_vpc.append(requester_info[2])
                        remote_vpc.append(requester_info[0])
                        remote_vpc.append(requester_info[1])
                    elif region == requester_info[2]:
                        remote_vpc.append(accepter_info[2])
                        remote_vpc.append(accepter_info[0])
                        remote_vpc.append(accepter_info[1])
                        local_vpc.append(requester_info[0])
                        local_vpc.append(requester_info[1])
                    x.add_row([peering_name, local_vpc[0], local_vpc[1], remote_vpc[0], remote_vpc[1], remote_vpc[2]])
                print(x)
    except KeyboardInterrupt:
        print("Aborted")