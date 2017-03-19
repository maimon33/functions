#!/usr/bin/env bash

echo "Enter PATH to where you need to make the at"
read -p "Full PATH: " -e -i '' PATH_TO_FILE

echo "Enter the new IP"
read -p "IP: " -e -i '' NEW_IP

echo "Replaceing your current IP in conf files"
sed -i "s/\b\([0-9]\{1,3\}\.\)\{1,3\}[0-9]\{1,3\}\b/${NEW_IP}/g" ${PATH_TO_FILE}