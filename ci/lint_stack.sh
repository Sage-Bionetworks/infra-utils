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

# util to print a generic list
print_list() {
  list=("$@")
  for item in "${list[@]}"
  do
    echo "${item}"
  done
}

# Get existing stack names from local files
get_local_stack_names() {
  stack_names=( $(grep -r -w -h 'stack_name:' ${PATH} | cut -d':' -f2 | awk '{$1=$1};1') )
  # echo "${stack_names[@]}"
}

# Get existing stack names from cloudformation
get_cf_stack_names() {
  stack_names=( $(aws cloudformation list-stacks \
      --query 'StackSummaries[?starts_with(StackStatus, `DELETE_COMPLETE`) != `true`].StackName' \
      --output text) )
  # echo "${stack_names[@]}"
}

# Get the newly added stack_name
get_new_stack_name() {
  diff_output=$(git diff HEAD~1 | grep '+stack_name:' || true)
  new_stack_name=${diff_output:13}
  # echo "${new_stack_name}"
}

# Verify new stack_name is unique
verify_unique() {
  for stack_name in "${stack_names[@]}"
  do
    if [ "${new_stack_name}" = "${stack_name}" ]; then
      echo "ERROR: new stack_name \"${new_stack_name}\" is not unique"
      echo "Existing stacks names:"
      print_list "${stack_names[@]}"
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


# main

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

if [ $# -eq 0 ]; then                          # Requires at least one argument
    exit_abnormal
fi

while getopts ":rl:" options; do
  case "${options}" in
    r) echo "R option"
       get_new_stack_name
       if [ ! -z "${new_stack_name}" ]; then
         verify_name_constraint
         get_cf_stack_names
         verify_unique
       fi
      ;;
    l) PATH=${OPTARG}
       get_new_stack_name
       if [ ! -z "${new_stack_name}" ]; then
         verify_name_constraint
         # get all stack names from the last commit
         ( git checkout HEAD~1 ) 2> /dev/null
         get_local_stack_names
         ( git checkout - ) 2> /dev/null
         verify_unique
       fi
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
