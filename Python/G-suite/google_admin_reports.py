from __future__ import print_function
import os
import re
import sys
import json
import pickle
import os.path

from time import strftime
from prettytable import PrettyTable
from datetime import timedelta, datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

def _format_json(dictionary):
    return json.dumps(dictionary, indent=4, sort_keys=True)

def UsersList(date_request):
    SCOPES = ['https://www.googleapis.com/auth/admin.reports.usage.readonly']
    """Shows basic usage of the Admin SDK Reports API.
    Prints the time, email, and name of the last 10 login events in the domain.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token-user.pickle'):
        with open('token-user.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token-user.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('admin', 'reports_v1', credentials=creds)

    # Call the Admin SDK Reports API
    print('Getting User App Usage report')
    results = service.userUsageReport()
    usage = results.get(userKey="all", date=date_request)
    usage_report = usage.execute()
    # print(_format_json(usage_report))
    for user in usage_report["usageReports"]:
        for param in user["parameters"]:
            if param["name"] == "accounts:admin_set_name":
                username = param["stringValue"]
            if param["name"] == "accounts:used_quota_in_mb":
                total_usage_size = param["intValue"]
        x.add_row([username, total_usage_size])
    return

def TeamDriveList(driveId=None):
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token-drive.pickle'):
        with open('token-drive.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token-drive.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    
    if driveId:
        files_result = []
        page_token = None
        while True:
            try:
                param = {}
                param["supportsAllDrives"] = True
                param["includeItemsFromAllDrives"] = True
                param["corpora"] = "drive"
                param["driveId"] = driveId
                if page_token:
                    param['pageToken'] = page_token
                files = service.files().list(**param).execute()

                for item in files["files"]:
                    files_result.append(item)
                
                # Print progress
                sys.stdout.write(".{}".format(len(files_result)))
                sys.stdout.flush()

                page_token = files.get('nextPageToken')
                if not page_token:
                    break
            except errors.HttpError, error:
                print('An error occurred: {}'.format(error))
                break
        return(len(files_result))

    # Call the Drive v3
    drives_dict = {}
    results = service.teamdrives().list()
    items = results.execute()["teamDrives"]
    for drive in items:
        drives_dict[drive["id"]] = drive["name"]
    return(drives_dict)

if __name__ == '__main__':
    arg = sys.argv[1]
    if arg == 'users':
        try:
            if sys.argv[2]:
                p_format = re.compile('20\d\d-\d\d-\d\d')
                if p_format.match(sys.argv[2]):
                    date_request = sys.argv[2]
                else:
                    print("Bad date format")
                    sys.exit()
        except IndexError:
            date_request = (
                datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
            print("""Getting report for {}
You can specify a date to get report by day
Use format 'YYYY-MM-DD'\n""".format(date_request))
        x = PrettyTable()
        x.field_names = ["Username", "Drive Usage Mb"]
        try:
            UsersList(date_request)
        except:
            print("error")
            sys.exit()
        print(x)
    elif arg == 'drives':
        x = PrettyTable()
        x.field_names = ["TeamDrives", "# of Files"]
        for drive_id, drive_name in TeamDriveList().iteritems():
            print("Listing Drive: {}".format(drive_name))
            drive_files_count = TeamDriveList(driveId=drive_id)
            x.add_row([drive_name, drive_files_count])
            sys.stdout.write("\n")
            sys.stdout.flush()
        print(x)
    else:
        print("Missing arg!\nusers or drives must be passed as arg for script")

