#!/usr/bin/env bash

echo "Enter PATH to where you need to make the at"
read -p "Full PATH: " -e -i '' PATH_TO_FILE

public_ip=$(/usr/bin/curl ipinfo.io/ip)
echo "Your current public IP is: ${public_IP}"

echo "Enter the new IP"
read -p "IP: " -e -i '${public_IP}' NEW_IP

echo "Replaceing your current IP in conf files"
sed -i "s/\b\([0-9]\{1,3\}\.\)\{1,3\}[0-9]\{1,3\}\b/${NEW_IP}/g" ${PATH_TO_FILE}