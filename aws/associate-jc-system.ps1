# Associate a Windows EC2 instance with a jumpcloud user
# Usage:
#   associate-jc-system.ps1 -JcServiceApiKey XXXXXXXXXX \
#           -JcSystemsGroupId XXXXXXXXX -OwnerEmail joe.smith@sagebase.org
#
# Note: assumes jq is installed thru choco, https://chocolatey.org/packages/jq

# Get jumpcloud info from flag or env var
Param(
    [String]$JcSystemsGroupId = $env:JC_SYSTEMS_GROUP_ID,
    [String]$JcServiceApiKey = $env:JC_SERVICE_API_KEY,
    [String]$OwnerEmail = $env:OWNER_EMAIL
)
if(-not($JcSystemsGroupId)) { Throw "-JcSystemsGroupId is required" }
if(-not($JcServiceApiKey)) { Throw "-JcServiceApiKey is required" }
if(-not($OwnerEmail)) { Throw "-OwnerEmail is required" }

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

# Get the User ID that match an email address from a list of JC users
# synapse.org emails are stored in a JC custom user attribute
Function Get-JCUserId {
    Param($Users, $Email)
    if ($Email.Contains("synapse.org")) {
        foreach ($User in $Users) {
            foreach ($Attribute in $User.attributes) {
                if ($Attribute.name -match "SynapseEmail" -and $Attribute.value -match $Email) {
                    $UserId = $User._id
                }
            }
        }
    } else {
        foreach ($User in $Users) {
            if ($User.email -eq $Email) {
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
  $JcUserId = (Get-JCUserId -Users $JcUsers -Email $OwnerEmail)
  Write-Host "JcUserId = $JcUserId"
  if (-not ([string]::IsNullOrEmpty($JcUserId))) {
      Add-JCSystemUser -SystemID $JcSystemId -UserId $JcUserId -Administrator $True
  }
}


$env:Path += ";C:\ProgramData\chocolatey\lib\jq\tools"

InstallPowershellModule
ServiceConnect
UserAccessSystem