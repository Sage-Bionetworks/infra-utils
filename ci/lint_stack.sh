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

# Get all existing stack names
get_existing_stacks() {
  stack_names=( $(aws cloudformation list-stacks \
      --query 'StackSummaries[?starts_with(StackStatus, `DELETE_COMPLETE`) != `true`].StackName' \
      --output text) )
  #echo "${stack_names[@]}"
}

# Get the newly added stack_name
get_new_stack_name() {
  diff_output=$(/usr/bin/git diff HEAD~1|/bin/grep '+stack_name:' || true)
  new_stack_name=${diff_output:13}
  #echo "${new_stack_name}"
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
get_new_stack_name
if [ ! -z "${new_stack_name}" ]; then
  verify_name_constraint
  get_existing_stacks
  verify_unique
fi
