# tools/power.py - Windows system power state management

# Invokes native OS power state routines via shutdown.exe and user32.dll. 
# Unlocking the PC programmatically is restricted by the Secure Attention Sequence (SAS) and the Winlogon sandbox.
import subprocess
import ctypes

def manage_power_state(action: str) -> str:
    """
    Control the system power state. 
    Supported actions: 'shutdown', 'restart', 'lock'.
    Note: 'unlock' is fundamentally blocked by the OS architecture.
    """
    action = action.lower()
    try:
        if action == "shutdown":
            # /s = shutdown, /t 0 = zero second timeout (immediate)
            subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
            return "Shutdown signal sent to NT Kernel."
        elif action == "restart":
            # /r = restart, /t 0 = zero second timeout
            subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
            return "Restart signal sent to NT Kernel."
        elif action == "lock":
            # Direct Win32 API call to lock the active session
            ctypes.windll.user32.LockWorkStation()
            return "Workstation locked successfully."
        else:
            return "Invalid power state action. Supported: 'shutdown', 'restart', 'lock'."
    except Exception as e:
        return f"Power state change failed: {e}"
