# tools/permissions_handle.py - Windows Capability Access Manager permission controller
# Implementation details:
# Interacts directly with the Windows ConsentStore registry keys across HKLM and HKCU to query and toggle
# system-wide hardware and privacy capabilities (webcam, microphone, location) without external binaries.

import winreg

CAPABILITY_ALIASES = {
    "camera": "webcam",
    "cam": "webcam",
    "webcam": "webcam",
    "video": "webcam",
    "mic": "microphone",
    "microphone": "microphone",
    "audio": "microphone",
    "location": "location",
    "gps": "location",
    "bluetooth": "bluetooth",
    "radios": "radios",
    "radio": "radios",
    "contacts": "contacts",
    "calendar": "appointments",
    "appointments": "appointments",
    "diagnostics": "appDiagnostics",
    "appdiagnostics": "appDiagnostics",
    "activity": "activity",
    "phone": "phoneCall",
    "phonecall": "phoneCall",
    "cellular": "cellularData",
    "cellulardata": "cellularData",
    "documents": "documentsLibrary",
    "pictures": "picturesLibrary",
    "videos": "videosLibrary"
}

def resolve_capability_key(capability: str) -> str:
    """Normalizes natural capability names to the underlying Windows ConsentStore subkey."""
    clean_name = capability.strip().lower()
    return CAPABILITY_ALIASES.get(clean_name, clean_name)

def get_windows_permission_status(capability: str) -> bool:
    """
    Checks if Windows permissions for a specific capability (e.g., 'camera', 'location', 'microphone') 
    are natively enabled across either the device or user levels.
    """
    target = resolve_capability_key(capability)
    status = False
    
    # Check HKLM
    try:
        key_lm = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, fr"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{target}")
        val_lm, _ = winreg.QueryValueEx(key_lm, "Value")
        winreg.CloseKey(key_lm)
        if val_lm == "Allow":
            status = True
    except Exception:
        pass
        
    # Check HKCU
    try:
        key_cu = winreg.OpenKey(winreg.HKEY_CURRENT_USER, fr"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{target}")
        val_cu, _ = winreg.QueryValueEx(key_cu, "Value")
        winreg.CloseKey(key_cu)
        if val_cu == "Allow":
            status = True
    except Exception:
        pass

    return status

def toggle_windows_permission(capability: str, enable: bool) -> str:
    """
    Toggles native Windows permission for a specific capability (e.g., 'camera', 'webcam', 'microphone', 'location')
    for both the device (HKLM) and the current user (HKCU) via the Registry.
    Pass True to enable, False to disable.
    """
    target = resolve_capability_key(capability)
    action = "Enabling" if enable else "Disabling"
    val = "Allow" if enable else "Deny"
    print(f"   [🔧 Kiko is {action} Windows '{capability}' (registry key: {target}) permissions...]")
    
    success_scopes = []
    errors = []
    
    # Toggle Global Device Level (HKLM)
    try:
        key_lm = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, fr"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{target}", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key_lm, "Value", 0, winreg.REG_SZ, val)
        winreg.CloseKey(key_lm)
        success_scopes.append("Device (HKLM)")
    except Exception as e:
        errors.append(f"Device: {e}")
        
    # Toggle Per-User Level (HKCU)
    try:
        key_cu = winreg.OpenKey(winreg.HKEY_CURRENT_USER, fr"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{target}", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key_cu, "Value", 0, winreg.REG_SZ, val)
        winreg.CloseKey(key_cu)
        success_scopes.append("User (HKCU)")
    except Exception as e:
        errors.append(f"User: {e}")
        
    if success_scopes:
        scopes_str = " and ".join(success_scopes)
        return f"'{capability}' permissions successfully set to '{val}' across {scopes_str}."
    else:
        return f"Failed to modify '{capability}' permissions. Registry errors: {'; '.join(errors)}"
