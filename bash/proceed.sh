#!/bin/bash

function proceed () {
    read -r -p "proceed? [Y/n]" response;
    if [[ $response =~ ^(yes|y| ) ]] || [[ -z $response ]]; then
        return 0;
    else
        return 1;
    fi
}
