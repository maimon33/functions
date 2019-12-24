#!/usr/bin/env bash

START=\$(date +%s)
while [ "\$(curl -s -o /dev/null -w ''%{http_code}'' https://www.google.com)" != "200" ]; do
    echo -n .
    sleep 60
    
    if [ \$(( \$(date +%s) - \$START )) -gt 1800 ] ; then
        exit 1
    fi
done