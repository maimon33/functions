#!/usr/bin/env bash

timeout 1 sudo whoami
if [ "$(echo $?)" == "124" ]; then echo "Sorry, you are not root." && exit 1; fi