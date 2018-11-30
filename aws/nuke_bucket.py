# This is script is used to delete an S3 bucket.
# It will also delete a bucket with versioning enabled.

from __future__ import print_function

import argparse
import sys

import boto3
from botocore.exceptions import ClientError


def delete_bucket(bucket_name, profile=None):
    """Delete a bucket (and all object versions)."""
    kwargs = {}
    if profile:
        kwargs['profile_name'] = profile

    session = boto3.Session(**kwargs)
    print('Deleting {} ...'.format(bucket_name), end='')

    try:
        s3 = session.resource(service_name='s3')
        bucket = s3.Bucket(bucket_name)
        bucket.object_versions.delete()
        bucket.delete()
    except ClientError as ex:
        print('error: {}'.format(ex.response['Error']))
        sys.exit(1)

    print('done')


def _parse_args():
    """A helper for parsing command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument('bucket_name', help='The bucket name to delete.')
    parser.add_argument('-p', '--profile', default='',
                        help='Use a specific profile for bucket operations. '
                             'Default: "default" profile in ~/.aws/config or '
                             'AWS_PROFILE environment variable')
    return parser.parse_args()


def _main():
    """Script execution handler."""
    args = _parse_args()
    delete_bucket(args.bucket_name, profile=args.profile)


if __name__ == '__main__':
    _main()

