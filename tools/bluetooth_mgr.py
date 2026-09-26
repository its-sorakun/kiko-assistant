import subprocess
import json
import os

BT_MANAGER_EXE = os.path.join(os.path.dirname(__file__), 'bt_manager', 'bt_manager.exe')

def get_bluetooth_devices() -> list:
    """
    Returns a list of paired Bluetooth devices and their connection status.
    Uses the native C++ bt_manager.exe to query the Win32 Bluetooth stack.
    """
    if not os.path.exists(BT_MANAGER_EXE):
        return [{"error": "C++ Bluetooth Manager not compiled."}]
        
    try:
        result = subprocess.run([BT_MANAGER_EXE, "list"], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        return [{"error": f"Process failed: {e.stderr}"}]
    except json.JSONDecodeError:
        return [{"error": "Failed to parse Bluetooth output."}]
    except Exception as e:
        return [{"error": str(e)}]

def connect_bluetooth_device(mac_address: str, connect: bool = True) -> str:
    """
    Tricks the Windows Kernel into connecting or disconnecting to a Bluetooth device (e.g. headphones) 
    by forcefully asserting the Audio Sink service via bluetoothapis.dll.
    
    Args:
        mac_address: The MAC address of the device to connect/disconnect (e.g., "AB:CD:EF:12:34:56").
        connect: True to connect, False to disconnect.
    """
    if not os.path.exists(BT_MANAGER_EXE):
        return "CRITICAL SYSTEM ERROR: bt_manager.exe not compiled."
        
    action = "connect" if connect else "disconnect"
    try:
        result = subprocess.run([BT_MANAGER_EXE, action, mac_address], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"CRITICAL SYSTEM ERROR: Process failed: {e.stderr}"
    except Exception as e:
        return f"CRITICAL SYSTEM ERROR: {str(e)}"

def toggle_bluetooth_power(enable: bool) -> str:
    """
    Toggles the master hardware power state of the Bluetooth Radio ON or OFF.
    Executes a PowerShell script to safely proxy the WinRT COM calls, preventing Python from crashing.
    """
    action = "On" if enable else "Off"
    ps_script = os.path.join(os.path.dirname(__file__), 'bt_manager', 'ToggleBluetooth.ps1')
    
    if not os.path.exists(ps_script):
        return "CRITICAL SYSTEM ERROR: ToggleBluetooth.ps1 script is missing."
        
    print(f"Kiko is trying to turn {action.upper()} the Bluetooth radio natively...", flush=True)
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_script, "-BluetoothStatus", action],
            capture_output=True, text=True, check=True
        )
        return f"Successfully toggled Bluetooth radio to {action} via PowerShell proxy."
    except subprocess.CalledProcessError as e:
        return f"CRITICAL SYSTEM ERROR: PowerShell toggle failed. {e.stderr}"
    except Exception as e:
        return f"CRITICAL SYSTEM ERROR: {str(e)}"
