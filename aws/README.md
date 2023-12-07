# Scripts for managing AWS

* [associate-jc-system.ps1](#associate-jc-systemps1)
* [install-jc-agent.ps1](#install-jc-agentps1)
* [install-ms-vc.ps1](#install-ms-vcps1)
* [nuke_bucket.py](#nuke_bucketpy)
* [set_account_policy.sh](#set_account_policysh)
* [set_env_vars_file.ps1](#set_env_vars_fileps1)
* [tag-instance-volume.ps1](#tag-instance-volumeps1)
* [tag_instance.ps1](#tag_instanceps1)
* [update_other_tag.py](#update_other_tagpy)


## associate-jc-system.ps1

### Dependencies

Assumes the following are installed through choco:
* jq: https://chocolatey.org/packages/jq

### Usage

```
associate-jc-system.ps1 -JcServiceApiKey XXXXXXXXXX -JcSystemsGroupId XXXXXXXXX -SynapseUserId 1234567
```

## install-jc-agent.ps1

### Source

https://github.com/TheJumpCloud/support/blob/master/scripts/windows/FixWindowsAgent.ps1


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

## update_other_tag.py

Set the value of CostCenterOther for a specified EC2 instance, including related resources in the same cloudformation stack
and/or service catalog product. This is useful for fixing typos when launching a service catalog product or for migrating a
cloudformation stack from one cost center to another. The CostCenterOther tag will only be updated if the CostCenter tag is
"Other / 000001" and the new value for CostCenterOther is valid.

### Dependencies

The following python packages are required:

* boto3
* requests

### Usage

#### Options

* -r --resource_id: (Required) Target resource to tag, e.g. EC2 instance name
* -t --tag_value:   (Required) New value for CostCenterOther tag

#### Environment Variables

* AWS_PROFILE:  (Required) Set AWS account based on ~/.aws/config
* MIPS_API_URL: (Optional) Overwrite default mips-api URL, https://mips-api.finops.sageit.org/tags?show_inactive_codes&disable_other_code

#### Example
```
AWS_PROFILE=org-sagebase-scipooldev update_other_tag.py -r i-061fee3df7b496cd5 -t "No Program / 000000"
```
