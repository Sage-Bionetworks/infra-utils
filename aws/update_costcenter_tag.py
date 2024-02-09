import argparse
import logging
import os

import boto3
import boto3.session
import requests


# setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
for lib in ["botocore", "urllib3"]:
    log = logging.getLogger(lib)
    log.setLevel(logging.WARNING)

# setup boto session
boto_sess = boto3.session.Session()
sts_client = boto_sess.client('sts')
tag_client = boto_sess.client('resourcegroupstaggingapi')


def _aws_user_tags(tag_list):
    """
    Create a flat dictionary of specific tags from the deeply-nested
    dictionary of tags returned by the API.
    """
    user_tags = {}
    for tag in tag_list:
        if tag['Key'] in [
            'CostCenter',
            'CostCenterOther',
            'aws:cloudformation:stack-id',
            'aws:servicecatalog:provisionedProductArn',
        ]:
            user_tags[tag['Key']] = tag['Value']
    return user_tags


def _mip_valid_tags():
    """
    Query our microservice for a list of valid tags
    """
    # by default allow inactive codes but not "Other"
    _default_url = "https://mips-api.finops.sageit.org/tags?show_inactive_codes&disable_other_code"
    api_url = os.environ.get('MIPS_API_URL', _default_url)

    json_data = requests.get(api_url)
    json_data.raise_for_status()
    return json_data.json()


def _resource_tags(resource):
    """
    Get all tags associated with the given ARN or EC2 ID
    """

    res_arn = None
    results = []

    if resource.startswith("arn:"):
        res_arn = resource

    elif resource.startswith("i-"):
        region = boto_sess.region_name
        account = sts_client.get_caller_identity()["Account"]
        res_arn = f"arn:aws:ec2:{region}:{account}:instance/{resource}"

    else:
        raise ValueError(f"Unknown resource type: {resource}")

    data = tag_client.get_resources(ResourceARNList=[res_arn, ])
    logging.debug(data)
    for tag_map in data["ResourceTagMappingList"]:
        results.append(tag_map["Tags"])

    if len(results) == 0:
        raise ValueError(f"Resource not found: {res_arn}")

    if len(results) > 1:
        raise ValueError(f"Found multiple resources: {results}")

    return results[0]


def _get_related_arns(tags, tag):
    """
    Find all resources tagged with the same tag value, such as in the
    same cloudformation stack or provisioned service catalog product.
    """

    found = []

    if tag not in tags:
        # nothing to match on, return empty list
        return found

    value = tags[tag]
    tag_filter = {
        "Key": tag,
        "Values": [value, ]
    }

    pager = tag_client.get_paginator("get_resources")
    for page in pager.paginate(TagFilters=[tag_filter, ]):
        _list = page['ResourceTagMappingList']
        for item in _list:
            if tag.endswith("Arn") and item["ResourceARN"] == value:
                # This would cause an Invalid ARN error when apply tags
                continue
            found.append(item["ResourceARN"])

    return found


def update_tags(res_id, new_value):
    """
    Add or update the CostCenter or CostCenterOther tag value on the given
    resource. If the current CostCenter is set to Other, update the
    CostCenterOther tag, otherwise update the CostCenter tag.

    If the given resource is tagged with a cloudformation stack or a
    provisioned service catalog product, then also apply the new tag
    value to all other resources in the stack or product.
    """

    # look up resource tags
    _tags = _resource_tags(res_id)
    tags = _aws_user_tags(_tags)
    logging.info(f"Existing resource tags: {tags}")

    # new tags to apply
    new_tags = {
        "CostCenter": new_value,
    }

    # if CostCenter is Other, update CostCenterOther instead
    if "CostCenter" in tags:
        if tags["CostCenter"].startswith("Other"):
            logging.debug("CostCenter is Other, updating CostCenterOther")
            new_tags = {
                "CostCenter": "Other / 000001",
                "CostCenterOther": new_value,
            }

    # get a list of valid tags
    valid_tags = _mip_valid_tags()
    logging.debug(f"Valid tag values: {valid_tags}")

    # check that the given tag is valid
    if new_value not in valid_tags:
        raise ValueError(f"Tag value {new_value} is not a valid cost center")

    # look for associated resources
    cfn_items = _get_related_arns(tags, "aws:cloudformation:stack-id")
    logging.info(f"CFN stack ARNs: {cfn_items}")
    sc_items = _get_related_arns(tags, "aws:servicecatalog:provisionedProductArn")
    logging.info(f"SC Product ARNs: {sc_items}")
    items = list(set(sc_items).union(cfn_items))  # drop duplicates

    # update tag value on those resources
    logging.info(f"Tagging {items} with {new_tags}")
    result = tag_client.tag_resources(ResourceARNList=items, Tags=new_tags)

    # log any failures
    failed = result["FailedResourcesMap"]
    if failed:
        logging.error(f"Failed to tag: {failed}")

    # remove CostCenterOther if were not explicitly setting a value for it
    if "CostCenterOther" not in new_tags:
        logging.info(f"Untagging 'CostCenterOther' on {items}")
        result = tag_client.untag_resources(ResourceARNList=items,
                                            TagKeys=["CostCenterOther", ])

    # log any more failures
    failed = result["FailedResourcesMap"]
    if failed:
        logging.error(f"Failed to untag: {failed}")


def cli():
    """
    Command Line Interface

    Options
        resource_id:    Target resource to tag, e.g. EC2 instance name
        tag_value:      New value for cost center tag

    Environment Variables
        AWS_PROFILE:    Set AWS account based on ~/.aws/config
        MIPS_API_URL:   Overwrite default mips-api URL

    Example
        AWS_PROFILE=org-sagebase-scipooldev update_other_tag.py -r i-061fee3df7b496cd5 -t "No Program / 000000"
    """

    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument("-r", "--resource",
                            required=True,
                            help="Resource ARN or EC2 instance ID")

    arg_parser.add_argument("-t", "--tag-value",
                            required=True,
                            help="Value for CostCenterOther tag")

    args = arg_parser.parse_args()
    logging.info(f"Args: {args}")

    update_tags(args.resource, args.tag_value)


if __name__ == '__main__':
    cli()
