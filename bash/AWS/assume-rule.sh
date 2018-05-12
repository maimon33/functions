#!/usr/bin/env bash

ACCOUNT_ID=$1
ROLE_NAME=$2

set_creds ()
{
	local creds=`aws sts assume-role --role-arn "arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME" --role-session-name "role-temp" --query '[Credentials.AccessKeyId, Credentials.SecretAccessKey, Credentials.SessionToken]' --output text`
export AWS_ACCESS_KEY_ID="`echo $creds | awk ' {print $1} '`"
export AWS_SECRET_ACCESS_KEY="`echo $creds | awk ' {print $2} '`"
export AWS_SESSION_TOKEN="`echo $creds | awk ' {print $3} '`"

}

set_creds 