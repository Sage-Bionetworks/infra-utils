#########################################################################################
#
# Install Google Chrome
#
#########################################################################################

$INSTALLER_URL="http://dl.google.com/chrome/install/latest/chrome_installer.exe"
$INSTALLER_PATH="$env:TEMP\chrome_installer.exe"

Function DownloadChromeInstaller() {
    (New-Object System.Net.WebClient).DownloadFile("${INSTALLER_URL}", "${INSTALLER_PATH}")
}

Function InstallerExists() {
    Test-Path ${INSTALLER_PATH}
}

Function InstallChrome() {
    $params = ("${INSTALLER_PATH}", "/silent", "/install")
    Invoke-Expression "$params"
}

Function DownloadAndInstall()
{

    DownloadChromeInstaller

    if (InstallerExists)
    {
        Write-Host " complete."

        Write-Host -nonewline "Installing chrome..."
        InstallChrome
        $exitCode = $?

        Write-Host " complete. (exit code=$exitCode)"

        if ($exitCode -ne $true)
        {
            Write-Error "Chrome installation failed."
            exit 1
        }
        else
        {
            Write-Host "`n* * * SUCCESS! Chrome installation complete. * * *"
        }
    }
    else
    {
        Write-Error "Could not download agent installer from ${AGENT_INSTALLER_URL}. Install FAILED."
        exit 1
    }
}

DownloadAndInstall
