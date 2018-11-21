# This script assumes that you already have the awscli installed and
# profiles setup for using the cli
#!/bin/bash
set -ex

wget https://github.com/Sage-Bionetworks/infra-utils/archive/master.zip -O /tmp/infra-utils.zip
unzip -j -n /tmp/infra-utils.zip -x "infra-utils-master/.gitignore" "infra-utils-master/LICENSE" "infra-utils-master/*.md" "infra-utils-master/aws/*"
./setup_sceptre.sh || travis_terminate 1

