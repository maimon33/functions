#!/usr/local/bin/python3
from __future__ import print_function

import sys
import json
import boto3

import argparse
from prettytable import PrettyTable

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=str, default="json")
parser.add_argument("--vpc", type=str)
parser.add_argument("--resolve", action=argparse.BooleanOptionalAction)
parser.add_argument("--risk", action=argparse.BooleanOptionalAction)
args = parser.parse_args()

def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)

def export_sg(output, resolve_group_names=False, risk=False, vpc=False):
	#Explicitly declaring variables here grants them global scope
	cidr_block = ""
	ip_protpcol = ""
	from_port = ""
	to_port = ""
	from_source = ""
	group_dict = {}
	group_names = {}

	x = PrettyTable()
	x.field_names = ["VPC ID", "GroupId", "In/Out", "Source/Destination", "From Port - To Port"]

	ec2 = boto3.client('ec2')
	sgs = ec2.describe_security_groups()["SecurityGroups"]

	if resolve_group_names:
		for sg in sgs:
			group_id = sg['GroupId']
			group_name = sg["GroupName"]
			group_names[group_id] = group_name

	if risk:
		print("Listing only inbound public rules")

	for sg in sgs:
		group_id = sg['GroupId']
		group_vpc = sg['VpcId']
		group_name = sg["GroupName"]
		if group_id not in group_dict:
			group_dict[group_id] = {}
			group_dict[group_id]["Group Name"] = group_name
			group_dict[group_id]["rules"] = []

		# InBound permissions ##########################################
		inbound = sg['IpPermissions']
		# print("%s,%s,%s" % ("","","Inbound"))
		for rule in inbound:
			if rule['IpProtocol'] == "-1":
				traffic_type="All Trafic"
				ip_protpcol="All"
				to_port="All"
			else:
				ip_protpcol = rule['IpProtocol']
				from_port=rule['FromPort']
				to_port=rule['ToPort']
				#If ICMP, report "N/A" for port #
				if to_port == -1:
					to_port = "N/A"

			#Is source/target an IP v4?
			if len(rule['IpRanges']) > 0:
				for ip_range in rule['IpRanges']:
					cidr_block = ip_range['CidrIp']
					if risk:
						if cidr_block == "0.0.0.0/0":
							related_address = cidr_block
						else:
							pass
					else:
						related_address = cidr_block

			#Is source/target an IP v6?
			if len(rule['Ipv6Ranges']) > 0:
				for ip_range in rule['Ipv6Ranges']:
					cidr_block = ip_range['CidrIpv6']
					related_address = cidr_block

			#Is source/target a security group?
			if not risk:
				if len(rule['UserIdGroupPairs']) > 0:
					for source in rule['UserIdGroupPairs']:
						from_source = source['GroupId']
						if resolve_group_names:
							related_address = group_names[from_source]
						else:
							related_address = from_source
			try:
				group_dict[group_id]["rules"].append("Inbound: {}-{}, From: {}".format(from_port, to_port, related_address))
				if vpc:
					if vpc == group_vpc:
						x.add_row([group_vpc, group_id, "In", related_address, "{}-{}".format(from_port, to_port)])
				else:
					x.add_row([group_vpc, group_id, "In", related_address, "{}-{}".format(from_port, to_port)])
			except UnboundLocalError:
				# Not a risky rule
				pass

		if not risk:
			# OutBound permissions ##########################################
			outbound = sg['IpPermissionsEgress']
			# print("%s,%s,%s" % ("","","Outbound"))
			for rule in outbound:
				if rule['IpProtocol'] == "-1":
					traffic_type="All Trafic"
					ip_protpcol="All"
					to_port="All"
				else:
					ip_protpcol = rule['IpProtocol']
					from_port=rule['FromPort']
					to_port=rule['ToPort']
					#If ICMP, report "N/A" for port #
					if to_port == -1:
						to_port = "N/A"

				#Is source/target an IP v4?
				if len(rule['IpRanges']) > 0:
					for ip_range in rule['IpRanges']:
						cidr_block = ip_range['CidrIp']
						related_address = cidr_block

				#Is source/target an IP v6?
				if len(rule['Ipv6Ranges']) > 0:
					for ip_range in rule['Ipv6Ranges']:
						cidr_block = ip_range['CidrIpv6']
						related_address = cidr_block

				#Is source/target a security group?
				if len(rule['UserIdGroupPairs']) > 0:
					for source in rule['UserIdGroupPairs']:
						from_source = source['GroupId']
						if resolve_group_names:
							related_address = group_names[from_source]
						else:
							related_address = from_source
				group_dict[group_id]["rules"].append("Outbound: {}-{}, To: {}".format(from_port, to_port, related_address))
				x.add_row([group_id, "Out", related_address, "{}-{}".format(from_port, to_port)])
	if output == "t":
		return x
	else:
		return _format_json(group_dict)

if args.output == "json":
	print(export_sg("j", args.resolve, args.risk, args.vpc))
else:
	print(export_sg("t", args.resolve, args.risk, args.vpc))
