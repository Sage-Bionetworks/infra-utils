# Scripts for managing AWS

* [associate-jc-system.ps1](#associate-jc-systemps1)
* [install-ms-vc.ps1](#install-ms-vcps1)
* [nuke_bucket.py](#nuke_bucketpy)
* [set_account_policy.sh](#set_account_policysh)
* [set_env_vars_file.ps1](#set_env_vars_fileps1)
* [tag-instance-volume.ps1](#tag-instance-volumeps1)
* [tag_instance.ps1](#tag_instanceps1)
* [update_costcenter_tag.py](#update_costcenter_tagpy)
* [update_owner_tag.py](#update_owner_tagpy)


## associate-jc-system.ps1

### Dependencies

Assumes the following are installed through choco:
* jq: https://chocolatey.org/packages/jq

### Usage

```
associate-jc-system.ps1 -JcServiceApiKey XXXXXXXXXX -JcSystemsGroupId XXXXXXXXX -SynapseUserId 1234567
```

## install-ms-vc.ps1

### Usage

To be documented


## nuke_bucket.py

### Dependencies

* boto3

### Usage

To be documented


## set_account_policy.sh

### Dependencies

* `awscli`

### Usage

To be documented


## set_env_vars_file.ps1

### Dependencies

Assumes the following are installed through choco:
* jq: https://chocolatey.org/packages/jq
* awscli: https://chocolatey.org/packages/awscli

### Usage

```
set_env_vars.ps1 -StackId arn:aws:cloudformation:us-east-1:237179673806:stack/SC-237179673806-pp-skslwogrplibk/4c472ab0-573f-11ea-8cef-0abf94ca9997
```

## tag-instance-volume.ps1

### Dependencies

Assumes the following are installed through choco:
* awscli: https://chocolatey.org/packages/awscli

### Usage

```
tag-instance-volume.ps1 -AwsRegion us-east-1 -StackName mystack -Department CompOnc -Project SysBio -OwnerEmail jsmith@acme.com
```


## tag_instance.ps1

### Dependencies

Assumes the following are installed through choco:
* jq: https://chocolatey.org/packages/jq
* awscli: https://chocolatey.org/packages/awscli

### Usage

```
tag_instance.ps1
```


## update_costcenter_tag.py

Set the value of CostCenter and/or CostCenterOther for a specified resource,
including related resources in the same cloudformation stack and/or service
catalog product. The specified resource can be either an EC2 instance-id, or an
arbitrary ARN.

The CostCenterOther tag should only have a value when the CostCenter tag is
"Other / 000001", but we are unable to enforce this in service catalog. And so
the CostCenterOther tag will only be updated if the CostCenter tag on the
specified resource starts with "Other", otherwise the CostCenter tag will be
updated and the CostCenterOther tag will be removed if present.

In addition to being useful for correcting service catalog tags, this script is
also useful for migrating existing cloudformation stacks from one cost center to
another.

### Dependencies

The following python packages are required:

* boto3
* requests

### Usage

#### Options

* -r --resource:  (Required) Target resource to tag, either an ARN or an EC2 instance ID
* -t --tag_value: (Required) New cost center value to set

#### Environment Variables

* AWS_PROFILE:  (Required) Set AWS account based on ~/.aws/config
* MIPS_API_URL: (Optional) Overwrite default mips-api URL, https://mips-api.finops.sageit.org/tags?show_inactive_codes&disable_other_code

#### Example

```
AWS_PROFILE=org-sagebase-scipooldev update_other_tag.py -r i-061fee3df7b496cd5 -t "No Program / 000000"
```


## update_owner_tag.py

Perform a search and replace on the owner tags `OwnerEmail` and `synapse:email` across all resources in the current account.
This is useful for transferring ownership of resources. The old tag value cannot be the empty string.

### Dependencies

The following python packages are required:

* boto3

### Usage

#### Options

* -o --old-email:  (Required) Existing tag value to match on
* -n --new-email:  (Required) New tag value to set

#### Environment Variables

* AWS_PROFILE: (Required) Set AWS account based on `~/.aws/config`

#### Example

```
AWS_PROFILE=org-sagebase-scicomp update_owner_tag.py -o "foo@sagebase.org" -n "bar@sagebase.org"
```
