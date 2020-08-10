#!/bin/bash

files="$(ls -A ~/.kube/ | grep config)"
select filename in ${files}; do 
    SELECTED_CONFIG="${HOME}/.kube/${filename}"
    export KUBECONFIG="$SELECTED_CONFIG"
    echo "Now using: $SELECTED_CONFIG " && break; 
done