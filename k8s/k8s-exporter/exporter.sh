#!/usr/bin/env bash

VERBOSE=false
HOME_DIR=$(pwd)
NAMESPACE=""
RESORCE_LIST="configmaps secrets deployments statefulsets daemonsets services storageclasses pvc ingress"
FIELDS_LIST="metadata.annotations metadata.creationTimestamp metadata.generation metadata.selfLink metadata.resourceVersion metadata.uid status"

# Define help function
help() {
    echo "Usage: $0 [-n|--namespace user] [-v|--verbose]";
    echo "       $0 -h|--help";
    echo "Options:";
    echo "    -n | --namespace: full: all namespaces, user: ommits system nameapaces";
    echo "    -v | --verbose: output error messages"
    echo "    -h | --help: Display this help message.";
    exit 1;
}

confirm() {
    echo $1
    read -r -p "Output folder exists, Overwrite? [Y/n]" response
    if [[ $response =~ ^(yes|y| ) ]] || [[ -z $response ]]; then
        return 0
    else
        return 1
    fi
}

get_namespaces() {
    if [[ $1 == "user" ]]; then
        echo "Pulling user namespaces"
        kubectl get ns | grep -v "NAME\|kube-public\|kube-system" | cut -d " " -f 1 > $HOME_DIR/namespaces.txt
    elif [[ $1 == "full" ]]; then
        echo "Did not get namespace. Pulling all"
        kubectl get ns | grep -v NAME | cut -d " " -f 1 > $HOME_DIR/namespaces.txt
    else
        kubectl get ns $1 |grep -v NAME | cut -d " " -f 1 > $HOME_DIR/namespaces.txt
    fi
}

clean_yaml() {
    echo "Cleaning $1"
    for field in $FIELDS_LIST; do
        if [ "$VERBOSE" = ture ]; then
            docker run --rm -it -v ${PWD}:/workdir mikefarah/yq yq d --inplace $1 $field 2>/dev/null
        else
            docker run --rm -it -v ${PWD}:/workdir mikefarah/yq yq d --inplace $1 $field
        fi
    done
}

# Declare vars. Flags initalizing to 0.
while [[ -n $1 ]]; do
    case "$1" in
        -h|--help)
            shift;
            echo -e "This script exports k8s ymls from a cluster.\n"
            help;
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
        -v|--verbose)
            shift;
                VERBOSE=true
                shift;
            ;;
    esac
done

if [ -d $HOME_DIR/k8s_output ]; then
    confirm
    rm -rf $HOME_DIR/k8s_output namespaces.txt && mkdir -p $HOME_DIR/k8s_output
else
    mkdir -p $HOME_DIR/k8s_output
fi

if [ -z $NAMESPACE ]; then
    get_namespaces full
fi

if [ ! $(which docker) ]; then
    echo "Server has no docker installed. can't clean yamls"
fi

for ns in $(cat $HOME_DIR/namespaces.txt); do
    echo "Working on: $ns"
    mkdir -p $HOME_DIR/k8s_output/$ns && cd $HOME_DIR/k8s_output/$ns
    for resource in $RESORCE_LIST; do
        kubectl -n $ns get $resource | grep -v NAME | cut -d " " -f 1 > resource_items.txt
        echo $resource
        for item in $(cat resource_items.txt); do
            output_file=$resource
            output_file+="_$item"
            kubectl -n $ns get $resource/$item -o yaml > $output_file.yml
            if [ $(which docker) ]; then
                clean_yaml $output_file.yml
            fi
        done
    done
done
