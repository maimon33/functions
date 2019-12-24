#!/usr/bin/env bash

NAMESPACE="default"

function help(){
    echo "Usage: $0 [-n]--namespace default] [-c]--configmaps None] <FILE/FOLDER/S3_BUCKET>";
    echo "Examples: $0 -n elk -c env-config test.txt"
    echo " "
    echo "Options:";
    echo "    -h | --help: Display this help message.";
    exit 1;
}

# Declare vars. Flags initalizing to 0.
while [[ -n $1 ]]; do
  case "$1" in
    -h|--help)
        shift;
        echo -e "This script converts any AWS_S3 config file into configmaps content.\n"
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
    -c|--configmap)
        shift
          if [ "$1" ];
          then
              CONFIGMAP=$1;
              shift;
          else
            echo "Missing configmaps name!"
            exit 1
          fi
        ;;
    *)
      echo $1
      if [[ $1 == s3* ]]; then
        echo "Trying S3 bucket $1"
        mkdir -p source_dir
        aws s3 sync $1 source_dir/
        SOURCE="source_dir/*"
      elif [[ -f $1 ]]; then
        echo "Using source file: $1"
        SOURCE=$1
      elif [[ -d $1 ]]; then
        echo "Using source directory $1/"
        SOURCE="$1/*"
      else
        echo "File OR Directory not Found!"
        echo "Stopping..."
        exit 1
      fi
      shift;
      ;;
    esac
done

if [[ $(kubectl -n $NAMESPACE get configmaps $CONFIGMAP) == *NotFound* ]]; then
  echo "configmap not found!"
  exit 1
fi

for file in $SOURCE
do
  while IFS= read -r line
  do
    if [[ $(echo "$line" | sed -e 's/^[ \t]*//') == \#* ]]; then
      continue
    else
      VAR=`echo "$line" |cut -d "=" -f 1`
      VAR_VALUE=`echo "$line" |cut -d "=" -f 2`
      echo "Now patching configmap/$CONFIGMAP in namespace $NAMESPACE"
      echo "Adding $VAR: $VAR_VALUE to configmap"
      # Patch configmaps
      cat >./patch.json <<EOF
    {
      "data": {
          "$VAR": "$VAR_VALUE"
      }
    }
EOF
      kubectl patch configmap/$CONFIGMAP -n $NAMESPACE --type merge -p "$(cat patch.json)"
    fi
  done < $file
done
