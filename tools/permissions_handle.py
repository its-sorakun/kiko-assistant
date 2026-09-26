import winreg

def get_location_permission_status() -> bool:
    """
    Checks if Windows location permissions are natively enabled for the current user.
    """
    try:
        # Check global device setting (HKLM)
        key_lm = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location")
        val_lm, _ = winreg.QueryValueEx(key_lm, "Value")
        
        # Check per-user setting (HKCU)
        key_cu = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location")
        val_cu, _ = winreg.QueryValueEx(key_cu, "Value")
        
        return val_lm == "Allow" and val_cu == "Allow"
    except Exception:
        # Default to False if the keys don't exist or are completely locked down
        return False

def toggle_location_permission(enable: bool) -> str:
    """
    Toggles the native Windows location permission for the current user via the Registry.
    Pass True to enable, False to disable.
    """
    action = "Enabling" if enable else "Disabling"
    print(f"   [🔧 Kiko is {action} Windows Location Permissions in the Registry...]")
    try:
        val = "Allow" if enable else "Deny"
        
        # Toggle Global Device Level (HKLM)
        key_lm = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key_lm, "Value", 0, winreg.REG_SZ, val)
        
        # Toggle Per-User Level (HKCU)
        key_cu = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key_cu, "Value", 0, winreg.REG_SZ, val)
        
        return f"Location permissions successfully set to: {'Allow' if enable else 'Deny'} (Device and User levels)"
    except Exception as e:
        return f"Failed to modify location permissions: {str(e)}"
