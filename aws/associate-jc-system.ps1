# Associate a Windows EC2 instance with a jumpcloud user
# Usage:
#   associate-jc-system.ps1 -JcServiceApiKey XXXXXXXXXX \
#           -JcSystemsGroupId XXXXXXXXX -SynapseUserId 1234567
#
# Note: assumes jq is installed thru choco, https://chocolatey.org/packages/jq

# Get jumpcloud info from flag or env var
Param(
    [String]$JcSystemsGroupId = $env:JC_SYSTEMS_GROUP_ID,
    [String]$JcServiceApiKey = $env:JC_SERVICE_API_KEY,
    [String]$SynapseUserId = $env:SYNAPSE_USER_ID
)
if(-not($JcSystemsGroupId)) { Throw "-JcSystemsGroupId is required" }
if(-not($JcServiceApiKey)) { Throw "-JcServiceApiKey is required" }
if(-not($SynapseUserId)) { Throw "-SynapseUserId is required" }

# JC powershell module, https://github.com/TheJumpCloud/support/wiki
Function InstallPowershellModule() {
  Install-Module -Name JumpCloud -Force
  Import-Module -Name JumpCloud -Force
}

Function ServiceConnect() {
  Connect-JCOnline $JcServiceApiKey -force
}

# Give a user group access to a system
Function AssociateJcSystem() {
  $JcSystemId = Get-Content $env:ProgramFiles\JumpCloud\Plugins\Contrib\jcagent.conf | jq -r '.systemKey'
  Write-Host "JcSystemId = $JcSystemId"
  Add-JCSystemGroupMember -SystemID $JcSystemId -ByID -GroupID $JcSystemsGroupId
}

# Get the JC User ID that maps to a Synapse ID
# Synapse IDs are stored in a JC custom user attribute
Function Get-JCUserId {
    # Users is a list of JC users
    # Attribute is the custom user attribute name
    # Match is the JC Attribute value to match
    Param($Users, $Attribute, $Match)
    foreach ($User in $Users) {
        foreach ($attrib in $User.attributes) {
            if ($attrib.name -match $Attribute -and $attrib.value -match $Match) {
                $UserId = $User._id
            }
        }
    }
    return $UserId
}

# Give a user access to a system
Function UserAccessSystem() {
  $JcSystemId = Get-Content $env:ProgramFiles\JumpCloud\Plugins\Contrib\jcagent.conf | jq -r '.systemKey'
  Write-Host "JcSystemId = $JcSystemId"
  $JcUsers = (Get-JCUser -returnProperties email,attributes)
  $JcUserId = (Get-JCUserId -Users $JcUsers -Attribute "SynapseUserId" -Match $SynapseUserId)
  Write-Host "JcUserId = $JcUserId"
  if (-not ([string]::IsNullOrEmpty($JcUserId))) {
      Add-JCSystemUser -SystemID $JcSystemId -UserId $JcUserId -Administrator $True
  }
}


$env:Path += ";C:\ProgramData\chocolatey\lib\jq\tools"

InstallPowershellModule
ServiceConnect
UserAccessSystem
