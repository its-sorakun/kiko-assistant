# Could have used C++ but I chose python, but Why Python winreg instead of C++ WinRT?
# I did some online research and found out that Windows permissions (Location, Camera, Mic) are enforced by the Capability Access Manager Service (camsvc), which reads its policies directly from the ConsentStore registry hive and official WinRT APIs (e.g., AppCapability::RequestAccessAsync) only allow an application to request permission for itself, Microsoft does not expose a public C++ API to globally flip the master OS toggle for all applications.
# The only native way to globally toggle the master OS switch (mimicking the Windows Settings UI) is to forcefully overwrite the ConsentStore keys. 
# Doing this in C++ merely acts as a wrapper around RegOpenKeyEx/RegSetValueEx, which introduces compilation overhead without exposing any lower-level kernel behavior. 
# Python's built-in winreg hits the exact same configuration store natively with zero ceremony, using C++ to achieve the same result would be nothing but over engineering.

import winreg

def get_windows_permission_status(capability: str) -> bool:
    """
    Checks if Windows permissions for a specific capability (e.g., 'location', 'webcam', 'microphone') 
    are natively enabled across both the device and current user levels.
    """
    try:
        # Check global device setting (HKLM)
        key_lm = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, fr"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{capability}")
        val_lm, _ = winreg.QueryValueEx(key_lm, "Value")
        
        # Check per-user setting (HKCU)
        key_cu = winreg.OpenKey(winreg.HKEY_CURRENT_USER, fr"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{capability}")
        val_cu, _ = winreg.QueryValueEx(key_cu, "Value")
        
        return val_lm == "Allow" and val_cu == "Allow"
    except Exception:
        # Default to False if the keys don't exist or are completely locked down
        return False

def toggle_windows_permission(capability: str, enable: bool) -> str:
    """
    Toggles native Windows permission for a specific capability (e.g., 'location', 'webcam', 'microphone')
    for both the device (HKLM) and the current user (HKCU) via the Registry.
    Pass True to enable, False to disable.
    """
    action = "Enabling" if enable else "Disabling"
    print(f"   [🔧 Kiko is {action} Windows '{capability}' Permissions in the Registry...]")
    try:
        val = "Allow" if enable else "Deny"
        
        # Toggle Global Device Level (HKLM)
        key_lm = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, fr"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{capability}", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key_lm, "Value", 0, winreg.REG_SZ, val)
        
        # Toggle Per-User Level (HKCU)
        key_cu = winreg.OpenKey(winreg.HKEY_CURRENT_USER, fr"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{capability}", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key_cu, "Value", 0, winreg.REG_SZ, val)
        
        return f"'{capability}' permissions successfully set to: {'Allow' if enable else 'Deny'} (Device and User levels)"
    except Exception as e:
        return f"Failed to modify '{capability}' permissions: {str(e)}"
