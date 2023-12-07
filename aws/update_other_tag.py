import argparse
import logging
import os

import boto3
import requests


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
for lib in ["botocore", "urllib3"]:
    log = logging.getLogger(lib)
    log.setLevel(logging.WARNING)

ec2_client = boto3.client('ec2')
tag_client = boto3.client('resourcegroupstaggingapi')


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


def _resource_lookup(res_id):
    """
    Describe resource details of the given EC2 instance

    TODO: support non-reserved instances; once we hit our monthly reservation,
        the schema returned by ec2_client may change
    TODO: support other types of resources (so far Cost Explorer has
        only reported EC2 instances missing tags)
    """

    results = []
    data = ec2_client.describe_instances(InstanceIds=[res_id, ])

    if data:
        logging.debug(data)
        for reservation in data["Reservations"]:
            for instance in reservation["Instances"]:
                results.append(instance)

    if len(results) == 0:
        raise ValueError(f"Resource not found: {res_id}")

    if len(results) > 1:
        raise ValueError(f"Found multiple resources: {data}")

    return results[0]


def _get_cfn_stack_arns(stack_id):
    """
    Find all resources tagged with the same cloudformation stack
    """

    found = []
    cfn_filter = {
        "Key": "aws:cloudformation:stack-id",
        "Values": [stack_id, ]
    }

    pager = tag_client.get_paginator("get_resources")
    for page in pager.paginate(TagFilters=[cfn_filter, ]):
        _list = page['ResourceTagMappingList']
        for item in _list:
            found.append(item["ResourceARN"])

    return found


def _get_sc_product_arns(product_id):
    """
    Find all resources tagged with the same provisioned product
    """

    found = []
    sc_filter = {
        "Key": "aws:servicecatalog:provisionedProductArn",
        "Values": [product_id, ]
    }

    pager = tag_client.get_paginator("get_resources")
    for page in pager.paginate(TagFilters=[sc_filter, ]):
        _list = page['ResourceTagMappingList']
        for item in _list:
            if item["ResourceARN"] == product_id:
                # This would cause an Invalid ARN error when applying the tag
                continue
            found.append(item["ResourceARN"])

    return found


def add_other_tag(res_id, other_value):
    """
    Update the CostCenterOther tag value on the given resource.

    If the given resource is tagged with a cloudformation stack or a
    provisioned service catalog product, then also apply the new tag
    value to all other resources in the stack or product.

    Also validate that the CostCenter tag is set to Other, and that the
    new value for CostCenterOther is valid.
    """

    # look up resource id
    item = _resource_lookup(res_id)
    tags = _aws_user_tags(item['Tags'])
    logging.info(f"Tags: {tags}")

    # check that CostCenter is Other
    if "CostCenter" not in tags:
        raise ValueError(f"Resource {res_id} does not have a CostCenter tag")

    cost_center = tags["CostCenter"]
    if cost_center != "Other / 000001":
        raise ValueError(f"Unexpected CostCenter '{cost_center}'")

    # check for an existing CostCenterOther tag
    if "CostCenterOther" in tags:
        if tags["CostCenterOther"] == other_value:
            logging.info(f"CostCenterOther is already set to {other_value}")
            return

    # get a list of valid tags
    valid_tags = _mip_valid_tags()
    logging.debug(f"Valid tag values: {valid_tags}")

    # check that the given tag is valid
    if other_value not in valid_tags:
        raise ValueError(f"Tag value {other_value} is not valid for CostCenterOther")

    # look for associated resources
    cfn_items = _get_cfn_stack_arns(tags["aws:cloudformation:stack-id"])
    logging.info(f"Stack ARNs: {cfn_items}")
    sc_items = _get_sc_product_arns(tags["aws:servicecatalog:provisionedProductArn"])
    logging.info(f"SC Product ARNs: {sc_items}")
    items = list(set(sc_items).union(cfn_items))  # drop duplicates

    # update tag value on those resources
    logging.info(f"Tagging {items}")
    result = tag_client.tag_resources(ResourceARNList=items,
                                      Tags={"CostCenterOther": other_value})
    failed = result["FailedResourcesMap"]
    if failed:
        logging.error(f"Failed Resources: {failed}")


def cli():
    """
    Command Line Interface

    Options
        resource_id:    Target resource to tag, e.g. EC2 instance name
        tag_value:      New value for CostCenterOther tag

    Environment Variables
        AWS_PROFILE:    Set AWS account based on ~/.aws/config
        MIPS_API_URL:   Overwrite default mips-api URL

    Example
        AWS_PROFILE=org-sagebase-scipooldev update_other_tag.py -r i-061fee3df7b496cd5 -t "No Program / 000000"
    """

    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument("-r", "--resource-id",
                            required=True,
                            help="Resource ID")

    arg_parser.add_argument("-t", "--tag-value",
                            required=True,
                            help="Value for CostCenterOther tag")

    args = arg_parser.parse_args()
    logging.info(f"Args: {args}")

    add_other_tag(args.resource_id, args.tag_value)


if __name__ == '__main__':
    cli()
