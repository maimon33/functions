# Google Admin reports

This script gives general usage reports on User usage and TeamDrive files count<br>
For this script to run you'll need to enable [Reports API](https://developers.google.com/admin-sdk/reports/v1/quickstart/python)

Durring first run for each report [users, drives], you'll need to authenticate the API via browser which is logged in with your Google profile

Prerequisite packages for the Python script
```
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Users Apps Usage
Usage:<br>
`python google_admin_reports.py users`

### TeamDrive Usage (Files count only)
Usage:<br>
`python google_admin_reports.py drives`
