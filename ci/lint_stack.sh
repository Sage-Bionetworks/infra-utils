# Cloudformation does not allow provisioning stacks with duplicate names.
# This script helps ensure that stack names for newly provisioned
# resources are unique.
#!/bin/bash
set -e
set -o pipefail

# Name can only contain alpha, number or hyphens, 1st char must be alpha.
# TODO - need to add the following constraints:
#   cannot contain square bracket characters
#   string length must be less than 128 characters
STACK_NAME_CONSTRAINT="^[a-zA-Z][a-zA-Z0-9.-][^_~\`/{},.\"()\"+=\\<>?:;|!@#$%^&*[:space:]]*$"

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

# Verify that new stack_name contains valid chars and is a certain length
verify_name_constraint() {
  if [[ ! $new_stack_name =~ $STACK_NAME_CONSTRAINT ]]; then
    echo "ERROR: Stack name \"${new_stack_name}\" contains invalid characters"
    echo "A stack name can contain only alphanumeric characters (case sensitive) and hyphens."
    echo "It must start with an alphabetic character and cannot be longer than 128 characters."
    exit 1
  fi
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
      verify_name_constraint
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
