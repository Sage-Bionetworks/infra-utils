#!/bin/bash
set -e
set -o pipefail

stack_names=$(aws --profile sandbox.cfservice cloudformation list-stacks \
      --query 'StackSummaries[?starts_with(StackStatus, `DELETE_COMPLETE`) != `true`].[StackName]' \
      --output text)
echo "${stack_names[@]}"
