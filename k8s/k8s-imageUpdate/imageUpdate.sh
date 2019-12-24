#!/usr/bin/env bash

VERBOSE=false
HOME_DIR=$(pwd)
GCR_REPO="eu.gcr.io/solutions-dev"
RESORCE_LIST="deployments statefulsets daemonsets"

# Define help function
help() {
    echo "Usage: $0 [-n|--namespace user] [-q|--quite] [-d|--deploy] IMAGE_NAME IMAGE_TAG";
    echo "       $0 -h|--help";
    echo "Options:";
    echo "    -h | --help: Display this help message.";
    exit 1;
}

confirm() {
    echo $1
    echo -e "You are about to update all resource the use Image: $1.\nWith new TAG: $2"
    read -r -p "Continue? [Y/n]" response
    if [[ $response =~ ^(yes|y|Y| ) ]] || [[ -z $response ]]; then
        return 0
    else
        return 1
    fi
}

get_namespaces() {
    if [[ $1 == "fdna" ]]; then
        echo "Pulling user namespaces"
        kubectl get ns | grep -v "NAME\|kube-public\|kube-system" | cut -d " " -f 1 > $HOME_DIR/namespaces.txt
    elif [[ $1 == "full" ]]; then
        echo "Did not get namespace. Pulling all"
        kubectl get ns | grep -v NAME | cut -d " " -f 1 > $HOME_DIR/namespaces.txt
    else
        kubectl get ns $1 |grep -v NAME | cut -d " " -f 1 > $HOME_DIR/namespaces.txt
    fi
}

# Declare vars. Flags initalizing to 0.
while [[ -n $1 ]]; do
    case "$1" in
        -h|--help)
            shift;
            echo -e "This script update images with new tags.\n"
            help;
            ;;
        -q|--quite)
            shift
            NO_PROMPT=true;
            ;;
        
        -n|--namespace)
            shift;
                if [ -n "$1" ]; then
                    echo $1
                    NAMESPACE=$1;
                    get_namespaces $1;
                    shift;
                fi
            ;;
        -d|--deploy)
            shift
                if [ "$NO_PROMPT" != true ]; then
                    confirm $1 $2
                fi

                for ns in $(cat $HOME_DIR/namespaces.txt); do
                    echo "Working on: $ns"
                    for resource in $RESORCE_LIST; do
                        if [[ $(kubectl -n $ns get $resource -o wide |grep $1 |cut -d " " -f 1 2> /dev/null) ]]; then
                            kubectl -n $ns get $resource -o wide |grep $1 |cut -d " " -f 1 > resource_to_update
                            for item in $(cat resource_to_update); do
                                echo "$resource/$item $item=$GCR_REPO/$1:$2"
                                # kubectl -n $ns set image $resource/$item $item=$GCR_REPO/$1:$2
                            done
                        fi
                    done
                done
                exit 0
                ;;
    esac
done