#!/usr/bin/env bash

VERSION=$1

echo $VERSION

pip install https://github.com/cloudify-cosmo/cloudify-dsl-parser/archive/$VERSION.zip
pip install https://github.com/cloudify-cosmo/cloudify-rest-client/archive/$VERSION.zip
pip install https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/$VERSION.zip
pip install https://github.com/cloudify-cosmo/cloudify-cli/archive/$VERSION.zip