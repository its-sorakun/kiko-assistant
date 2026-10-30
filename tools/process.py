# tools/process.py - Native executable path crawler, port socket inspector, and process termination

# Bypasses the standard 'start' shell command to avoid GUI error dialogs when an executable is missing. Resolves physical paths natively by crawling Uninstall registry hives and App Paths to launch detached GUI processes. Inspects network sockets via psutil with netstat fallback to map listening ports to PIDs, and issues kernel-level termination signals using taskkill against process names or PIDs.
import os
import shutil
import subprocess
import winreg
import psutil

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

def _find_pids_on_port(port: int) -> list[int]:
    """
    Internal helper to locate process IDs associated with a specific network port.
    Evaluates via psutil net_connections first, falling back to netstat -ano.
    """
    pids = set()
    try:
        for c in psutil.net_connections(kind='inet'):
            if c.laddr and c.laddr.port == port and c.pid:
                pids.add(c.pid)
    except Exception:
        pass
        
    if not pids:
        for proto in ['tcp', 'udp']:
            try:
                out = subprocess.check_output(['netstat', '-ano', '-p', proto], text=True, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        local_addr = parts[1]
                        if local_addr.endswith(f':{port}') or local_addr == f'*:{port}':
                            pid_str = parts[-1]
                            if pid_str.isdigit() and int(pid_str) > 0:
                                pids.add(int(pid_str))
            except Exception:
                pass
                
    return sorted(list(pids))

def get_process_by_port(port: int) -> str:
    """
    Inspect active network sockets to identify which process is currently listening on or using a specific port.
    Returns the process name, PID, socket status, and executable path if accessible.
    """
    pids = _find_pids_on_port(port)
    if not pids:
        return f"No active process found listening on or bound to port {port}."
        
    details = []
    for pid in pids:
        if pid in (0, 4):
            details.append(f"System Kernel Process (PID: {pid})")
            continue
        try:
            p = psutil.Process(pid)
            name = p.name()
            exe = p.exe() if hasattr(p, 'exe') else "Unknown"
            details.append(f"{name} (PID: {pid}, Path: {exe})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            details.append(f"Unknown Process (PID: {pid}, Access Restricted)")
            
    return f"Port {port} is occupied by: {'; '.join(details)}"

def kill_process_by_port(port: int) -> str:
    """
    Locate the process listening on or bound to a specific network port and forcefully terminate it.
    Resolves the PID from network sockets and sends a kernel-level termination signal (taskkill /F /PID).
    """
    pids = _find_pids_on_port(port)
    if not pids:
        return f"No active process found listening on or bound to port {port}."
        
    critical_names = {"system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe"}
    results = []
    for pid in pids:
        if pid in (0, 4):
            return f"Refusing to kill critical Windows system process (PID: {pid}) on port {port} to prevent OS crash."
            
        proc_name = f"PID {pid}"
        try:
            p = psutil.Process(pid)
            proc_name = p.name()
            if proc_name.lower() in critical_names:
                return f"Refusing to kill critical system process '{proc_name}' (PID: {pid}) on port {port}."
        except Exception:
            pass
            
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, check=True)
            results.append(f"{proc_name} (PID: {pid})")
        except subprocess.CalledProcessError as e:
            return f"Failed to terminate {proc_name} (PID: {pid}) on port {port}. Error: {e.stderr.strip() or e}"
            
    return f"Successfully terminated process(es) on port {port}: {', '.join(results)}."

def force_kill_process(target: str) -> str:
    """
    Drop a kernel-level termination signal to forcefully wipe a process from memory.
    Accepts either an executable image name (e.g. 'discord.exe' or 'node') or a numeric PID (e.g. '14220').
    Useful for hung or unresponsive applications.
    """
    target = target.strip()
    if not target:
        return "No process name or PID specified for termination."
        
    try:
        if target.isdigit():
            pid = int(target)
            if pid in (0, 4):
                return f"Refusing to terminate critical system PID {pid}."
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, check=True)
            return f"Termination signal sent. Process with PID {pid} has been forcefully killed."
        else:
            image_name = target if target.lower().endswith(".exe") else f"{target}.exe"
            subprocess.run(["taskkill", "/F", "/IM", image_name], capture_output=True, text=True, check=True)
            return f"Termination signal sent. {image_name} has been forcefully killed."
    except subprocess.CalledProcessError as e:
        return f"Failed to kill {target}. Process may not be running or execution requires elevated privileges."
