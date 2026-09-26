[CmdletBinding()]
Param ( [Parameter(Mandatory=$true)][ValidateSet('Off', 'On')][string]$BluetoothStatus )

Add-Type -AssemblyName System.Runtime.WindowsRuntime

# Safely extract the AsTask extension method via reflection for PowerShell 5.1 compatibility
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

# Fetch Radios via WinRT
$radiosTask = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]::GetRadiosAsync()
$radios = $asTask.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]).Invoke($null, @($radiosTask)).Result

$bluetooth = $radios | Where-Object { $_.Kind -eq "Bluetooth" }

if (-not $bluetooth) {
    Write-Error "CRITICAL SYSTEM ERROR: No Bluetooth Radio found."
    exit 1
}

$stateTarget = if ($BluetoothStatus -eq 'On') { [Windows.Devices.Radios.RadioState]::On } else { [Windows.Devices.Radios.RadioState]::Off }

# Execute State Change
$stateTask = $bluetooth.SetStateAsync($stateTarget)
$res = $asTask.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]).Invoke($null, @($stateTask)).Result

if ($res -eq 'Allowed') {
    Write-Output "Successfully toggled master radio state to $BluetoothStatus."
} else {
    Write-Error "CRITICAL SYSTEM ERROR: Windows blocked the radio toggle (Status: $res). Ensure 'Let apps control device radios' is enabled in Privacy Settings."
    exit 1
}
