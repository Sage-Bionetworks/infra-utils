# Apply tags to a volume of a windows EC2 instance
# Usage:
#   tag-instance-volume.ps1 -AwsRegion us-east-1 -StackName mystack -Department CompOnc -Project SysBio -OwnerEmail jsmith@acme.com

# Get vars from flag or env var
Param(
    [String]$AwsRegion = $env:AWS_REGION,
    [String]$StackName = $env:STACK_NAME,
    [String]$Department = $env:DEPARTMENT,
    [String]$Project = $env:PROJECT,
    [String]$OwnerEmail = $env:OWNER_EMAIL
)
if(-not($AwsRegion)) { Throw "-AwsRegion is required" }
if(-not($StackName)) { Throw "-StackName is required" }
if(-not($Department)) { Throw "-Department is required" }
if(-not($Project)) { Throw "-Project is required" }
if(-not($OwnerEmail)) { Throw "-OwnerEmail is required" }

$EC2_METADATA_URI = "http://169.254.169.254/latest/meta-data"

Function TagRootVolume() {
    $EC2_INSTANCE_ID = (Invoke-WebRequest -Uri $EC2_METADATA_URI/instance-id -UseBasicParsing).Content
    Write-Host "EC2_INSTANCE_ID = $EC2_INSTANCE_ID"

    $ROOT_DISK_ID = & aws.exe ec2 describe-volumes `
                      --region $AwsRegion `
                      --filters Name=attachment.instance-id,Values=$EC2_INSTANCE_ID `
                      --query Volumes[].VolumeId `
                      --out text
    Write-Host "ROOT_DISTK_ID = $ROOT_DISK_ID"

    & aws.exe ec2 create-tags `
      --region $AwsRegion `
      --resources $ROOT_DISK_ID `
      --tags Key=Name,Value=$EC2_INSTANCE_ID-root `
        Key=cloudformation:stack-name,Value=$StackName `
        Key=Department,Value=$Department `
        Key=Project,Value=$Project `
        Key=OwnerEmail,Value=$OwnerEmail
}

$env:Path += ";$env:ProgramFiles\Amazon\AWSCLIV2;$env:ProgramFiles\Amazon\AWSCLI\bin"

TagRootVolume
