# PowerShell script to run Tango device servers with omniORB configuration
# Usage: .\run-device-server.ps1 <python_script> <instance_name> [additional_args]
# Example: .\run-device-server.ps1 "DeviceServers\power\netio\DS_Netio_pdu.py" "1_V0"

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptPath,
    
    [Parameter(Mandatory=$true)]
    [string]$InstanceName,
    
    [Parameter(ValueFromRemainingArguments)]
    [string[]]$AdditionalArgs
)

# Set the working directory to the project root
Set-Location "C:\dev\pyconlyse"

# Build the command arguments
$ConfigFile = "C:\dev\pyconlyse\OMNIORB.CFG"
$Arguments = @($ScriptPath, $InstanceName, "-ORBconfigFile", $ConfigFile) + $AdditionalArgs

# Run the device server
Write-Host "Starting device server: $ScriptPath $InstanceName" -ForegroundColor Green
Write-Host "Using omniORB config: $ConfigFile" -ForegroundColor Yellow

poetry run python @Arguments