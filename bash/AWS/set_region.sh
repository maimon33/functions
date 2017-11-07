#!/bin/bash
# Bash Menu Script Example

function set_veriable() { export AWS_DEFAULT_REGION=$1 
}

PS3='Select your region: '
options=("us-east-1" "eu-west-1" "eu-central-1" "Quit")
select opt in "${options[@]}"
do
    case $opt in
        "us-east-1")
            set_veriable $opt
            break
            ;;
        "eu-west-1")
            set_veriable $opt
            break
            ;;
        "eu-central-1")
            set_veriable $opt
            break
            ;;
        "Quit")
            break
            ;;
        *) echo invalid option;;
    esac
done