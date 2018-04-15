#!/usr/bin/env bash

sudo pip install virtualenv
sudo pip install virtualenvwrapper
if ! printenv |grep -q WORKON_HOME; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "export WORKON_HOME=/home/assi/Envs" >> ~/.bash_profile
    else
        echo "export WORKON_HOME=/home/assi/Envs" >> ~/.bashrc
    fi
fi

sudo update-alternatives --install /usr/bin/python python /usr/bin/python2.7 1
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.5 2
sudo update-alternatives --set python /usr/bin/python3.5