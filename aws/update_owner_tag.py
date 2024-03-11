import argparse
import logging

import boto3


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
for lib in ["botocore", "urllib3"]:
    log = logging.getLogger(lib)
    log.setLevel(logging.WARNING)

try:
    tag_client = boto3.client('resourcegroupstaggingapi')
except Exception as exc:
    logging.error("Unable to create tag client")

owner_tags = [
    "OwnerEmail",
    "synapse:email",
]


def _find_tagged_arns(tag, value):
    """
    Find all resources tagged with the same cloudformation stack
    """

    found = []
    tag_filter = {
        "Key": tag,
        "Values": [value, ]
    }

    try:
        pager = tag_client.get_paginator("get_resources")
        for page in pager.paginate(TagFilters=[tag_filter, ]):
            _list = page['ResourceTagMappingList']
            for item in _list:
                found.append(item["ResourceARN"])
    except Exception as exc:
        # logging.exception(exc)
        logging.error("Unable to list resources")

    return found


def process_owner_tag(old_value, new_value=None):
    """
    Find all resources with a matching owner tag, and optionally update the tag
    value on all found resources.

    There are multiple resource tags that may contain the resource owner.
    For each owner tag, search for all resources with a tag value matching the
    former owner, and if a new value was given then update the tag on all matches.
    """

    # loop over each possible owner tag
    for owner_tag in owner_tags:
        # find all resources with a matching tag value
        arns = _find_tagged_arns(owner_tag, old_value)
        if not arns:
            continue
        logging.info(f"ARNs found where '{owner_tag}' == '{old_value}': {arns}")

        if new_value is not None:
            # replace tag value on found resources
            logging.info(f"Setting new tag value '{new_value}'")
            result = tag_client.tag_resources(ResourceARNList=arns,
                                              Tags={owner_tag: new_value})
            failed = result["FailedResourcesMap"]
            if failed:
                logging.error(f"Failed Resources: {failed}")


def cli():
    """
    Command Line Interface

    Options
        current-owner: Existing tag value to match on (required)
        new-owner: New tag value to set (optional)

    Environment Variables
        AWS_PROFILE:    Set AWS account based on ~/.aws/config

    Examples
        # List matching resources
        AWS_PROFILE=org-sagebase-scicomp update_owner_tag.py -c "foo@sagebase.org"

        # Update tag values on matching resources
        AWS_PROFILE=org-sagebase-scicomp update_owner_tag.py -c "foo@sagebase.org" -n "bar@sagebase.org"
    """

    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument("-c", "--current-owner",
                            required=True,
                            help="Owner tag value to search for")

    arg_parser.add_argument("-n", "--new-owner",
                            required=False,
                            help="New tag value to set")

    args = arg_parser.parse_args()
    logging.debug(f"Args: {args}")

    if not args.current_owner:
        logging.error("Old tag value cannot be empty.")

    elif not args.new_owner:
        logging.info("No new tag value provided, "
                     "only searching for matching resources.")
        process_owner_tag(args.current_owner)

    else:
        logging.info(f"Replacing '{args.current_owner}' with '{args.new_owner}'")
        process_owner_tag(args.current_owner, args.new_owner)


if __name__ == '__main__':
    cli()
