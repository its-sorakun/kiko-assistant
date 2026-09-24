# Copyright (C) 2026 Senpai
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Direct native Win32 registry reads. Using winreg instead of powershell wrappers to keep execution fast and avoid spawning heavy subprocesses just to read a string value.
import winreg

def query_registry_value(hive: str, key_path: str, value_name: str) -> str:
    """
    Read a specific value directly from the Windows Registry.
    Example hive parameters: HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE
    """
    hives = {
        "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
        "HKEY_USERS": winreg.HKEY_USERS
    }
    
    target_hive = hives.get(hive.upper())
    if not target_hive:
        return f"Invalid registry hive: {hive}"
        
    try:
        # Access the registry key strictly in read-only mode (KEY_READ)
        with winreg.OpenKey(target_hive, key_path, 0, winreg.KEY_READ) as key:
            value, reg_type = winreg.QueryValueEx(key, value_name)
            return f"Registry query successful. Value: {value}"
    except FileNotFoundError:
        return f"Registry path or value not found: {key_path}\\\\{value_name}"
    except PermissionError:
        return "Insufficient permissions to read that registry key."
    except Exception as e:
        return f"Registry query failed: {e}"
