#!/usr/bin/env python

import os
import sys
import json
import time
import shutil

import boto3
import click
import zipfile
import botocore

from prettytable import PrettyTable
from botocore.exceptions import ClientError, NoRegionError
from pkg_resources import resource_filename

DEFAULT_REGION="eu-west-1"

def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)

def aws_client(region, resource=False, aws_service="s3"):
    try:
        if resource:
            return boto3.resource(aws_service, region_name=region)
        else:
            return boto3.client(aws_service, region_name=region)
    except:
        print "client failed"

def list_objects(region, prefix):
    buckets_dict = {}
    buckets = aws_client(region).list_buckets()["Buckets"]
    for bucket in buckets:
        bucket_name = bucket["Name"]
        if bucket_name.startswith(prefix):
            buckets_dict[bucket_name] = ""
            buckets_list = []
            objects = aws_client(region).list_objects(Bucket=bucket_name)
            try:
                for s3_object in objects["Contents"]:
                    if not s3_object["Key"].endswith("/"):
                        object_dict = {}
                        object_dict[s3_object["Key"]] = s3_object["Size"]
                        buckets_list.append(object_dict)
                        buckets_dict[bucket_name] = buckets_list
            except KeyError:
                buckets_dict[bucket_name] = 0
            print "Finshed Processing bucket: {}".format(bucket["Name"])
    return buckets_dict

def table_create(source_dict, destination_dict):
    x = PrettyTable()
    x.field_names = ["Bucket Name", "# of Files", "New Files", "Total New Files Size"]
    # Compare dicts
    archive_list = []
    for bucket, objects in destination_dict.iteritems():
        if objects != 0:
            archive_list.append(objects.keys()[0])
    for bucket, objects in source_dict.iteritems():
        buckets_items = 0
        buckets_new_items = 0
        buckets_new_size = 0
        # List buckets items
        for s3_object in objects:
            buckets_items += 1
            # Checking if exists in destination bucket
            full_archive_object_name = "{}/{}.zip".format(bucket, s3_object.keys()[0])
            if full_archive_object_name not in archive_list:
                buckets_new_items += 1
                buckets_new_size += s3_object.values()[0]
        # Converts to Megabytes
        buckets_new_size_mb = buckets_new_size / 1000 / 1000
        x.add_row([bucket, buckets_items, buckets_new_items, "{}M".format(buckets_new_size_mb)])
    return x

def create_download_list(source_dict, destination_dict):
    archive_list = []
    download_list = []
    for bucket, objects in destination_dict.iteritems():
        if objects != 0:
            archive_list.append(objects.keys()[0])
    for bucket, objects in source_dict.iteritems():
        for s3_object in objects:
            s3_object_dict = {}
            if "{}/{}.zip".format(bucket, s3_object.keys()[0]) not in archive_list:
                s3_object_dict["Name"] = s3_object.keys()[0]
                s3_object_dict["Bucket"] = bucket
                for archive_item in source_dict[bucket]:
                    if archive_item.keys()[0] == s3_object.keys()[0]:
                        s3_object_dict["Size"] = archive_item.values()[0]
                download_list.append(s3_object_dict)
    return download_list

def archive_item(file_name, zip_path):
    zf = zipfile.ZipFile(zip_path, mode='w')
    zf.write(file_name)
    zf.close()

def upload_object(region, file_name, bucket):
    target_object_name = "{}.zip".format(file_name)
    aws_client(region, resource=True).upload_file(
        file_name, bucket, target_object_name)

def download_objects(region, download_list, limit):
    downloaded_list = []
    zip_list = []
    storage_limit = limit * 1000 * 1000
    current_storage_used = 0
    for download_object in download_list:
        if current_storage_used > storage_limit:
            print "Clearing used storage"
            shutil.rmtree(download_object["Bucket"])
        
        object_name = download_object["Name"]
        object_local = "{}/{}".format(download_object["Bucket"], download_object["Name"])
        object_zip = "{}/{}.zip".format(download_object["Bucket"], download_object["Name"])
        try:
            # Create Directory structure
            os.makedirs(os.path.dirname(object_local))
        except OSError:
            pass
        if len(download_list) != len(downloaded_list):
            try:
                aws_client(region, resource=True).Bucket(
                    download_object["Bucket"]).download_file(
                        object_name, object_local)
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == "404":
                    print("The object does not exist.")
                else:
                    raise
            downloaded_list.append(object_local)
            archive_item(object_local, object_zip)
            zip_list.append(object_zip)
            upload_object(region, object_zip, download_object["Bucket"])
            current_storage_used += os.path.getsize(object_local)
            current_storage_used += os.path.getsize(object_zip)


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower(),
    ignore_unknown_options=True)

@click.command(context_settings=CLICK_CONTEXT_SETTINGS)
@click.option('-s',
              '--source_buckets_prefix',
              help='prefix of source Buckets')
@click.option('-d',
              '--destination_bucket',
              help='Name of Destination Bucket')
@click.option('-l',
              '--limit_disc',
              default=10,
              help='Disc usgae limit. Amount in Gb')
@click.option('-t',
              '--test',
              is_flag=True,
              help="Get objects count in SRC buckets and compare to DST")
def archive(source_buckets_prefix, destination_bucket, limit_disc, test):
    """Convert EC2 on-demand instance to spot instance with one command
    """
    
    if destination_bucket and source_buckets_prefix:
        source_dict = list_objects(DEFAULT_REGION, source_buckets_prefix)
        destination_dict = list_objects(DEFAULT_REGION, destination_bucket)
    else:
        print "Missing source or destination buckets"
        sys.exit()

    if test:
        print table_create(source_dict, destination_dict)
        sys.exit()
    
    download_list = create_download_list(source_dict, destination_dict)

    download_objects(DEFAULT_REGION, download_list, limit_disc)
    

if __name__ == "__main__":
    archive()