#!/bin/bash
set -ex

# install app
pip install --exists-action a "sceptre<2.0"
# install contributions
mkdir resolvers
wget https://raw.githubusercontent.com/cloudreach/sceptre/v1/contrib/ssm-resolver/ssm.py -O resolvers/ssm.py
wget https://raw.githubusercontent.com/cloudreach/sceptre/v1/contrib/kms-resolver/kms.py -O resolvers/kms.py
