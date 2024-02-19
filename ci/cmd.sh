#!/bin/bash
set -e
set -o pipefail

# Gets the command name without path
cmd(){ echo `basename $0`; }

usage() {                                      # Function: Print a help message.
echo "\
usage: `cmd` [ -r ] [ -l PATH ]
-r Verify against cloudformation
-l Verify against local files in PATH
"
}

exit_abnormal() {                              # Function: Exit with error.
  usage
  exit 1
}

if [ $# -eq 0 ]; then
    exit_abnormal
fi

while getopts ":rl:" options; do
  case "${options}" in
    r) echo "R option"
      ;;
    l) PATH=${OPTARG}
      ;;
    :)                            # If expected argument omitted:
      echo "Error: -${OPTARG} requires an argument."
      exit_abnormal
      ;;
    *)                            # If unknown (any other) option:
      exit_abnormal
      ;;
  esac
done
