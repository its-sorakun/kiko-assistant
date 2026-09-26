import winreg

def get_location_permission_status() -> bool:
    """
    Checks if Windows location permissions are natively enabled for the current user.
    """
    try:
        # Hooks directly into the Windows ConsentStore Registry Hive
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location")
        value, _ = winreg.QueryValueEx(key, "Value")
        return value == "Allow"
    except Exception:
        # Default to False if the key doesn't exist or is completely locked down
        return False

def toggle_location_permission(enable: bool) -> str:
    """
    Toggles the native Windows location permission for the current user via the Registry.
    Pass True to enable, False to disable.
    """
    action = "Enabling" if enable else "Disabling"
    print(f"   [🔧 Kiko is {action} Windows Location Permissions in the Registry...]")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location", 0, winreg.KEY_SET_VALUE)
        val = "Allow" if enable else "Deny"
        winreg.SetValueEx(key, "Value", 0, winreg.REG_SZ, val)
        return f"Location permission successfully set to: {'Allow' if enable else 'Deny'}"
    except Exception as e:
        return f"Failed to modify location permission: {str(e)}"
