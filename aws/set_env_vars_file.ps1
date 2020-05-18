# Creates a file that when sourced will set environment variables that are
# commonly needed on CloudFormation EC2 initialization
#
# Usage:
#   set_env_vars.ps1 -StackId arn:aws:cloudformation:us-east-1:237179673806:stack/SC-237179673806-pp-skslwogrplibk/4c472ab0-573f-11ea-8cef-0abf94ca9997
#
# Note: assumes the following are installed through choco:
# jq: https://chocolatey.org/packages/jq
# awscli: https://chocolatey.org/packages/awscli

# Get vars from flag or env var
Param(
    [String]$StackId = $env:STACK_ID
)
if(-not($StackId)) { Throw "-StackId is required" }

Function SetEnvVars() {
  $SYNAPSE_USERPROFILE_ENDPOINT = "https://repo-prod.prod.sagebase.org/repo/v1/userProfile"
  $SYNAPSE_DOMAIN_NAME = "synapse.org"
  $EC2_INSTANCE_IDENTITY_DOC_URI = "http://169.254.169.254/latest/dynamic/instance-identity/document"
  $AWS_REGION = (Invoke-WebRequest -Uri $EC2_INSTANCE_IDENTITY_DOC_URI -UseBasicParsing).Content | jq .region -r
  $EC2_METADATA_URI = "http://169.254.169.254/latest/meta-data"
  $EC2_INSTANCE_ID = (Invoke-WebRequest -Uri $EC2_METADATA_URI/instance-id -UseBasicParsing).Content
  $ROOT_DISK_ID = & aws.exe ec2 describe-volumes `
    --region $AWS_REGION `
    --filters Name=attachment.instance-id,Values=$EC2_INSTANCE_ID `
    --query Volumes[].VolumeId --out text
  $EC2_INSTANCE_TAGS = & aws.exe --region $AWS_REGION `
    ec2 describe-tags `
    --filters Name=resource-id,Values=$EC2_INSTANCE_ID

  Function ExtractTagValue([String] $KeyName) {
    $EC2_INSTANCE_TAGS | jq -j --arg KEYNAME "$KeyName" '.Tags[] | select(.Key == $KEYNAME).Value '
  }

  $DEPARTMENT = ExtractTagValue -KeyName Department
  $PROJECT = ExtractTagValue -KeyName Project

  # provisioningPrincipalArn tag is only available when accessed thru Synapse IDP
  # need to lookup the Synapse user name from the ID to get the ONNER_EMAIL
  $PROVISIONING_PRINCIPAL_ARN = ExtractTagValue -KeyName 'aws:servicecatalog:provisioningPrincipalArn'
  if (-not ([string]::IsNullOrEmpty($PROVISIONING_PRINCIPAL_ARN))) {
    $SYNAPSE_USER_ID = $PROVISIONING_PRINCIPAL_ARN -replace '.*\/'
    $SYNAPSE_USERNAME = (Invoke-RestMethod -Uri "$SYNAPSE_USERPROFILE_ENDPOINT/$SYNAPSE_USER_ID").userName
    $OWNER_EMAIL = "$SYNAPSE_USERNAME@$SYNAPSE_DOMAIN_NAME"
  } else {
    $OWNER_EMAIL = ExtractTagValue -KeyName OwnerEmail
  }


  # Get segment of STACK_ID after last forward-slash
  $ResourceId = $StackId -replace '.*\/'

  # Search for provisioned product
  $Products = & aws.exe servicecatalog search-provisioned-products `
    --region $AWS_REGION `
    --filters SearchQuery=$ResourceId

  # Check return value and verify only one product was returned
  $Num_Products = echo "$Products" | jq '.TotalResultsCount'
  If ([string]::IsNullOrEmpty($Num_Products)) {
    throw "Invalid response from servicecatalog"
  }

  If (-NOT ($Num_Products -eq 1)) {
    throw "There are $Num_Products provisioned products, cannot isolate a name for tagging."
  }

  # Get the provisioned product name
  $ProductName = echo "$Products" | jq -r '.ProvisionedProducts[0].Name'

  $FileString = @"
    `$env:AWS_REGION` = "$AWS_REGION"
    `$env:EC2_INSTANCE_ID` = "$EC2_INSTANCE_ID"
    `$env:ROOT_DISK_ID` = "$ROOT_DISK_ID"
    `$env:DEPARTMENT` = "$DEPARTMENT"
    `$env:PROJECT` = "$PROJECT"
    `$env:OWNER_EMAIL` = "$OWNER_EMAIL"
    `$env:SYNAPSE_USER_ID` = "$SYNAPSE_USER_ID"
    `$env:SYNAPSE_USERNAME` = "$SYNAPSE_USERNAME"
    `$env:STACK_ID` = "$StackId"
    `$env:PRODUCT_NAME` = "$ProductName"
"@
  Set-Content -Path C:\scripts\instance_env_vars.ps1 -Value $FileString

}

$env:Path += ";$env:ProgramFiles\Amazon\AWSCLIV2"
$env:Path += ";C:\ProgramData\chocolatey\lib\jq\tools"

SetEnvVars
