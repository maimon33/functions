#!/usr/bin/env bash

NAMESPACE="default"

# Helper functions
confirm() {
    echo $1
    read -r -p "Are you sure? [Y/n]" response
    if [[ $response =~ ^(yes|y| ) ]] || [[ -z $response ]]; then
        $@
    else
        return 1
    fi
}

# Define help function
function help(){
    echo "Usage: $0 [-n]--namespace default] [-d]--deployment None]";
    echo "       $0 -h|--help";
    echo "Options:";
    echo "    -n | --namespace: Namespacce to work on, default namespace will be used if not supplied)";
    echo "    -d | --deployment: Deployment name regex search, None to edit all deployments";
    echo "    -h | --help: Display this help message.";
    exit 1;
}

# Declare vars. Flags initalizing to 0.
while [[ -n $1 ]]; do
    case "$1" in
        -h|--help)
            shift;
            echo -e "This script scales up or down matching regex deployments.\n"
            help;
            ;;
        -n|--namespace)
            shift;
                if [ -n "$1" ]; 
                then
                    NAMESPACE="$1";
                    shift;
                fi
            ;;
        -d|--deployment)
            shift
                if [ -n "$1" ];
                then
                    DEPLOYMENTS_REGEX=$1
                    kubectl -n $NAMESPACE get deployments | grep $1 > deployments.txt
                    if [[ $(wc -l deployments.txt) < 1 ]];
                        then
                            echo "Search Regex didn't find. scaling all deployments"
                            kubectl -n $NAMESPACE get deployments > deployments.txt
                            shift
                        else
                            echo "Found"
                            shift
                    fi
                fi
    esac
done

if [ -z $DEPLOYMENTS_REGEX ]; then
  kubectl -n $NAMESPACE get deployments > deployments.txt
fi

for i in $(cat deployments.txt |grep -v NAME | cut -d " " -f 1)
do
  CURRENT_STATUS=$(cat deployments.txt |grep -w "$i " |tr -s " " | cut -d " " -f 3)
  echo "Current replica for $i is: $CURRENT_STATUS"
  read -p "Desired replicas? " -i $CURRENT_STATUS -e NEW_STATUS
  if [ $CURRENT_STATUS = $NEW_STATUS ]; then
    echo "No Change"
  else
    confirm
    kubectl -n $NAMESPACE scale --replicas=$NEW_STATUS $i
  fi
done

# Cleanup post run
rm -f deployments.txt
