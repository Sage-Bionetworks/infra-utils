# Cloudformation does not allow provisioning stacks with duplicate names.
# This script helps ensure that stack names for newly provisioned
# resources are unique.
# NOTE: paths are setup to work on Ubuntu 14.04 (trusty) distro
#!/bin/bash
set -e
set -o pipefail

# Get all existing stack names
get_stack_names() {
  ( /usr/bin/git checkout HEAD~1 ) 2> /dev/null
  grep_outputs=( $(/bin/grep -r -w -h 'stack_name:' ${PATH}) )
  stack_names=("${grep_outputs[@]/'stack_name: '}")
  #echo "${stack_names[@]}"
}

# Get the newly added stack_name
get_new_stack_name() {
  ( /usr/bin/git checkout - ) 2> /dev/null
  diff_output=$(/usr/bin/git diff HEAD~1|/bin/grep '+stack_name:' || true)
  new_stack_name=${diff_output:13}
  #echo "${new_stack_name}"
}

# Verify new stack_name is a unique
verify_unique() {
  for stack_name in "${stack_names[@]}"
  do
    if [ "${new_stack_name}" = "${stack_name}" ]; then
      echo "ERROR: new stack_name \"${new_stack_name}\" is not unique"
      exit 1
     fi
  done
}

usage() {                                      # Function: Print a help message.
  echo "Usage: $0 [ -p PATH ]" 1>&2
}

exit_abnormal() {                              # Function: Exit with error.
  usage
  exit 1
}

if [ $# -eq 0 ]; then
    exit_abnormal
fi

while getopts ":p:" options; do
  case "${options}" in
    p)
      PATH=${OPTARG}
      get_stack_names
      get_new_stack_name
      verify_unique
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
