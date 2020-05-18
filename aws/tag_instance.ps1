# For a Windows instance provisioned through the Service Catalog,
# uses the CloudFormation stack ID to look up the name assigned by the user
# to the provisioned product in Service Catalog, and tags the EC2 instance
# with that name.
#
# Usage:
#   tag_instance.ps1
#
# Note: assumes the following are installed through choco:
# jq: https://chocolatey.org/packages/jq
# awscli: https://chocolatey.org/packages/awscli

Function TagInstance() {
  Param(
    [String]$AwsRegion = $env:AWS_REGION,
    [String]$Ec2InstanceId = $env:EC2_INSTANCE_ID,
    [String]$ProductName = $env:PRODUCT_NAME
  )
  if(-not($AwsRegion)) { Throw "-AwsRegion is required" }
  if(-not($Ec2InstanceId)) { Throw "-Ec2InstanceId is required" }
  if(-not($ProductName)) { Throw "-ProductName is required" }

  # Tag instance with product name
  & aws.exe ec2 create-tags `
    --region $AwsRegion `
    --resources $Ec2InstanceId `
    --tags Key=Name,Value=$ProductName
}

$env:Path += ";$env:ProgramFiles\Amazon\AWSCLIV2"
$env:Path += ";C:\ProgramData\chocolatey\lib\jq\tools"

TagInstance
