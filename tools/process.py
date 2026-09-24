# Copyright (C) 2026 Senpai
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Bypassing the standard 'start' shell command to avoid ugly GUI dialogs when an executable is missing, instead, resolve physical paths natively by crawling the Uninstall registry hives and launching detached processes.
import os
import shutil
import subprocess
import winreg

def launch_program(app_name: str) -> str:
    """
    Attempt to launch a program natively without relying on the shell 'start' command,
    which triggers ugly GUI error dialogs if the binary is missing.
    Resolves execution via PATH, Uninstall registries, and App Paths directly.
    """
    # 1. Native PATH resolution
    executable = shutil.which(app_name)
    if executable:
        try:
            subprocess.Popen([executable], creationflags=0x00000008, close_fds=True)
            return f"Launched {app_name} natively from PATH: {executable}"
        except Exception as e:
            return f"Failed to execute {executable}: {e}"

    # 2. Deep Registry Crawl for physical executable
    search_hives = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    
    found_path = None
    for hive, key_path in search_hives:
        if found_path: break
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as parent_key:
                num_subkeys = winreg.QueryInfoKey(parent_key)[0]
                for i in range(num_subkeys):
                    try:
                        subkey_name = winreg.EnumKey(parent_key, i)
                        with winreg.OpenKey(parent_key, subkey_name, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as subkey:
                            display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                            if app_name.lower() in display_name.lower():
                                # Match found! Extract the executable path from DisplayIcon
                                try:
                                    icon_path, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                    found_path = icon_path.split(',')[0].strip('"')
                                    break
                                except FileNotFoundError:
                                    pass
                    except OSError:
                        continue
        except OSError:
            continue
            
    if found_path and os.path.exists(found_path):
        try:
            # Launch detached GUI process cleanly
            subprocess.Popen([found_path], creationflags=0x00000008, close_fds=True)
            return f"Located and launched {app_name} via Registry: {found_path}"
        except Exception as e:
            return f"Found {app_name} at {found_path} but kernel execution failed: {e}"
            
    # 3. Direct App Paths Registry fallback (mimics 'start' behavior without the error dialog)
    app_exe = app_name if app_name.lower().endswith(".exe") else f"{app_name}.exe"
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        try:
            with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{app_exe}", 0, winreg.KEY_READ) as key:
                app_path, _ = winreg.QueryValueEx(key, "")
                if os.path.exists(app_path):
                    subprocess.Popen([app_path], creationflags=0x00000008, close_fds=True)
                    return f"Launched via App Paths: {app_path}"
        except OSError:
            continue
            
    return f"Failed to locate {app_name} in PATH, Uninstall Registries, or App Paths."

def force_kill_process(process_name: str) -> str:
    """
    Drop a kernel-level termination signal to forcefully wipe a process from memory.
    Useful for hung or unresponsive applications.
    """
    try:
        # /F denotes force, /IM specifies image name
        subprocess.run(["taskkill", "/F", "/IM", process_name], capture_output=True, text=True, check=True)
        return f"Termination signal sent. {process_name} has been forcefully killed."
    except subprocess.CalledProcessError as e:
        return f"Failed to kill {process_name}. Process may not be running or execution requires elevated privileges."
