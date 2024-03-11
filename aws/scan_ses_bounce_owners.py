#!/usr/bin/env python3

import logging
import pprint

import boto3
from botocore.config import Config as BotoConfig

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
for lib in ["botocore", "urllib3"]:
    log = logging.getLogger(lib)
    log.setLevel(logging.WARNING)

# Set up boto clients
# Use adaptive mode in an attempt to optimize retry back-off
boto_config = BotoConfig(
    retries={
        'mode': 'adaptive',  # default mode is legacy
    }
)
rsc_client = boto3.client('resource-explorer-2', config=boto_config)
ses_client = boto3.client('sesv2', config=boto_config)


def list_suppressed_emails():
    """
    Retrieve the SES suppression list and return the list of emails.
    """

    emails = []
    suppressed = ses_client.list_suppressed_destinations()
    for summary in suppressed['SuppressedDestinationSummaries']:
        emails.append(summary['EmailAddress'])
    logging.debug(f"Email list: {emails}")
    return emails


def find_owned_arns(owner):
    """
    Find all resources tagged with the given owner in the given account.
    """

    arns = []
    rsc_query = f'tag.value="{owner}"'
    rsc_search = rsc_client.get_paginator('search')
    for page in rsc_search.paginate(QueryString=rsc_query):
        for resource in page['Resources']:
            logging.debug(f"Found  {resource['OwningAccountId']}  {resource['Arn']}")
            arns.append(resource['Arn'])
    return arns


if __name__ == '__main__':
    email_list = list_suppressed_emails()
    if not email_list:
        logging.info("No suppressed emails")
    else:
        results = {}
        for email in email_list:
            logging.debug(f"Searching for {email}")
            owned = find_owned_arns(email)
            if owned:
                results[email] = owned

        if not results:
            logging.info("No resources found for any email")
        else:
            pprint.pp(results)
