#!/usr/bin/env bash

echo "path to file"

max_age_minutes=60
temp_key="temp_file"


if [ -f $temp_key ]; then
    if test $(find $temp_key -mmin +$max_age_minutes |egrep '.*'); then
        echo -e "temp_key older then $max_age_minutes Minutes\nYou need to open it again"
        rm -rf $temp_key
    else
        if [ $# == 0 ] ; then
            echo "SSH temp key is still valid"
            return 0
        else
            echo "Error finding temp key"
        fi
    fi
fi
