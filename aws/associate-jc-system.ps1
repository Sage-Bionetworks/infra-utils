# Associate a Windows EC2 instance with a jumpcloud system group
# Usage:
#   associate-jc-system.ps1 -JcServiceApiKey XXXXXXXXXX -JcSystemsGroupId XXXXXXXXX

# Get jumpcloud info from flag or env var
Param(
    [String]$JcSystemsGroupId = $env:JC_SYSTEMS_GROUP_ID,
    [String]$JcServiceApiKey = $env:JC_SERVICE_API_KEY
)
if(-not($JcSystemsGroupId)) { Throw "-JcSystemsGroupId is required" }
if(-not($JcServiceApiKey)) { Throw "-JcServiceApiKey is required" }

# JC powershell module, https://github.com/TheJumpCloud/support/wiki
Function InstallPowershellModule() {
  Install-Module -Name JumpCloud -Force
  Import-Module -Name JumpCloud -Force
}

Function AssociateJcSystem() {
  Connect-JCOnline $JcServiceApiKey -force
  # assumes jq is installed thru choco, https://chocolatey.org/packages/jq
  $JcSystemId = Get-Content $env:ProgramFiles\JumpCloud\Plugins\Contrib\jcagent.conf | jq -r '.systemKey'
  Add-JCSystemGroupMember -SystemID $JcSystemId -ByID -GroupID $JcSystemsGroupId
}

$env:Path += ";C:\ProgramData\chocolatey\lib\jq\tools"

InstallPowershellModule

AssociateJcSystem
