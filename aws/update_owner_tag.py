import argparse
import logging

import boto3


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
for lib in ["botocore", "urllib3"]:
    log = logging.getLogger(lib)
    log.setLevel(logging.WARNING)

tag_client = boto3.client('resourcegroupstaggingapi')


def _find_tagged_arns(tag, value):
    """
    Find all resources tagged with the same cloudformation stack
    """

    found = []
    tag_filter = {
        "Key": tag,
        "Values": [value, ]
    }

    pager = tag_client.get_paginator("get_resources")
    for page in pager.paginate(TagFilters=[tag_filter, ]):
        _list = page['ResourceTagMappingList']
        for item in _list:
            found.append(item["ResourceARN"])

    return found


def replace_owner_tag(old_value, new_value):
    """
    Update the owner tag value on all resources with a matching tag.

    There are two possible resource tags that may contain a resource owner.
    For each owner tag, search for all resources with a tag value matching the
    former owner, and then update the tag value to the new owner on all matches.
    """

    # loop over each possible owner tag
    for owner_tag in ["OwnerEmail", "synapse:email"]:
        # find all resources with a matching tag value
        arns = _find_tagged_arns(owner_tag, old_value)
        logging.info(f"ARNs found for tag {owner_tag}: {arns}")
        if not arns:
            continue

        # replace tag value on found resources
        logging.info(f"Setting new tag value '{new_value}' on {arns}")
        result = tag_client.tag_resources(ResourceARNList=arns,
                                          Tags={owner_tag: new_value})
        failed = result["FailedResourcesMap"]
        if failed:
            logging.error(f"Failed Resources: {failed}")


def cli():
    """
    Command Line Interface

    Options
        old-email: Existing tag value to match on
        new-email: New tag value to set

    Environment Variables
        AWS_PROFILE:    Set AWS account based on ~/.aws/config

    Example
        AWS_PROFILE=org-sagebase-scicomp update_owner_tag.py -o "foo@sagebase.org" -n "bar@sagebase.org"
    """

    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument("-o", "--old-email",
                            required=True,
                            help="Owner tag value to replace")

    arg_parser.add_argument("-n", "--new-email",
                            required=True,
                            help="New tag value for Owner")

    args = arg_parser.parse_args()
    logging.debug(f"Args: {args}")

    if not args.old_email:
        logging.error("Old tag value cannot be empty")

    elif not args.new_email:
        logging.error("New tag value cannot be empty")

    else:
        replace_owner_tag(args.old_email, args.new_email)


if __name__ == '__main__':
    cli()
