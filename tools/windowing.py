# If the script runs in a terminal, the terminal inherently holds the "active" window focus. Drop down to user32.dll and crawl the Desktop Window Manager (DWM) Z-order stack downward to identify the actual underlying application.
import ctypes
import os
import psutil

def open_directory(folder_path: str) -> str:
    """
    Open a specific folder using the native Windows Explorer.
    You can use '~' to represent the user's home directory (e.g., '~/Documents').
    """
    folder_path = os.path.expanduser(folder_path)
    # Quick sanity check to make sure the folder actually exists
    if os.path.exists(folder_path):
        os.startfile(folder_path)
        return f"Opened folder: {folder_path}"
    else:
        return f"Target directory does not exist: {folder_path}"

def open_file(file_path: str) -> str:
    """
    Launch a specific file in its default associated application.
    You can use '~' to represent the user's home directory (e.g., '~/Downloads/file.pdf').
    """
    file_path = os.path.expanduser(file_path)
    if os.path.exists(file_path):
        os.startfile(file_path)
        return f"Opened file: {file_path}"
    else:
        return f"Target file does not exist: {file_path}"

def list_directory_contents(folder_path: str) -> str:
    """
    List all files and subdirectories inside a given folder, returning the result as text.
    Use this to 'see' what is inside a folder without opening it visually.
    You can use '~' to represent the user's home directory (e.g., '~/Desktop').
    """
    folder_path = os.path.expanduser(folder_path)
    if not os.path.exists(folder_path):
        return f"Target directory does not exist: {folder_path}"
    
    try:
        entries = os.listdir(folder_path)
        if not entries:
            return f"The directory '{folder_path}' is empty."
        
        return f"Contents of '{folder_path}':\n" + "\n".join(f"- {e}" for e in entries)
    except PermissionError:
        return f"Access Denied: Windows is preventing you from reading '{folder_path}'."
    except Exception as e:
        return f"Failed to list contents: {str(e)}"

def get_active_window() -> str:
    """
    Traverse the Desktop Window Manager Z-order stack to find the active application window.
    Bypasses the command prompt window itself if executed from a terminal.
    """
    user32 = ctypes.windll.user32
    
    # 2 corresponds to GW_HWNDNEXT (the window below the specified window)
    GW_HWNDNEXT = 2 
    
    # Fetch the window currently holding focus (likely the terminal running this script)
    hwnd = user32.GetForegroundWindow()
    
    # Determine the process ID of the current foreground window
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    current_pid = os.getpid()
    
    # Fallback in case the terminal wrapper has a different PID (like Windows Terminal)
    # Check if window is visible and has a title to find a legitimate background app
    if pid.value == current_pid or "cmd.exe" in psutil.Process(pid.value).name().lower() or "windowsterminal.exe" in psutil.Process(pid.value).name().lower():
        # Crawl down the DWM Z-order stack
        while hwnd:
            hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
            if user32.IsWindowVisible(hwnd):
                
                # If we hit the bare desktop shell, they are looking at the desktop!
                cls_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls_buf, 256)
                if cls_buf.value in ("WorkerW", "Progman"):
                    return "The Windows Desktop (No active applications)"
                
                # Otherwise, look for a non-minimized window with a title
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0 and not user32.IsIconic(hwnd):
                    break

    if not hwnd:
        return "Could not determine the active background window."

    # Extract the title of the target window
    length = user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    
    return f"The underlying active window is: {buff.value}"

def read_active_window_content() -> str:
    """
    Attempt to read the contents of the currently active window.
    For code editors, it deduces the filename and reads directly from disk for instant speed.
    For all other GUI applications (browsers, discord, etc.), it hooks into the native Microsoft
    UI Automation API to scrape the visible accessibility text tree.
    """
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    GW_HWNDNEXT = 2
    
    editor_signatures = ["Visual Studio Code", "Notepad", "Sublime Text", "Cursor", "Antigravity"]
    found_editor_title = None
    target_hwnd = None
    fallback_title = None
    
    current_pid = os.getpid()
    
    # Crawl the Z-order to hunt down the nearest running app
    for _ in range(50):
        if not hwnd: break
        
        # Only check visible, non-minimized windows
        if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            # Check if this window belongs to us (the terminal)
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            try:
                proc = psutil.Process(pid.value)
                proc_name = proc.name().lower()
            except:
                proc_name = ""
                
            if pid.value == current_pid or "cmd.exe" in proc_name or "windowsterminal.exe" in proc_name:
                pass # skip terminal wrapper
            else:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    title_buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, title_buf, length + 1)
                    window_title = title_buf.value
                    
                    # Ignore the raw desktop shell
                    cls_buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, cls_buf, 256)
                    if cls_buf.value not in ("WorkerW", "Progman"):
                        if not target_hwnd:
                            target_hwnd = hwnd
                            fallback_title = window_title
                        
                        # Check if this window belongs to a known editor
                        if any(sig in window_title for sig in editor_signatures):
                            found_editor_title = window_title
                            target_hwnd = hwnd # prioritize editor if found
                            break
                    
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
        
    if not target_hwnd:
        return "Could not find any active (non-minimized) GUI applications in the Z-order stack."
        
    # --- STAGE 1: Fast Physical Disk Extraction for Code Editors ---
    if found_editor_title:
        parts = found_editor_title.split(" - ")
        raw_filename = None
        for part in parts:
            clean_part = part.strip().lstrip('*')
            if "." in clean_part or clean_part.startswith("."):
                raw_filename = os.path.basename(clean_part.replace("\\", "/"))
                break
                
        if raw_filename:
            target_path = None
            search_root = os.getcwd()
            
            for root, _, files in os.walk(search_root):
                if ".git" in root or "__pycache__" in root:
                    continue
                if raw_filename in files:
                    target_path = os.path.join(root, raw_filename)
                    break
                    
            if target_path:
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if len(content) > 3000:
                            content = content[:3000] + "\n... [FILE TRUNCATED]"
                        return f"Deduced physical path from IDE Z-order: {target_path}\n\n[FILE CONTENTS]\n{content}"
                except Exception as e:
                    pass # Fallback to UIA if read fails
                    
    # --- STAGE 2: UI Automation API Fallback ---
    # If not an editor, or physical read failed, fallback to native accessibility tree
    try:
        import uiautomation as auto
    except ImportError:
        return f"Identified target window '{fallback_title or found_editor_title}', but 'uiautomation' is not installed to read generic GUIs."
        
    print(f"   [⚡ Kiko is hooking into native UIAutomation for window: {fallback_title or found_editor_title}...]")
    
    # We must configure auto to not block too long
    auto.SetGlobalSearchTimeout(3)
    
    window_control = auto.WindowControl(searchDepth=1, Handle=target_hwnd)
    if not window_control.Exists(0, 0):
        return f"Could not bind UIA to target window '{fallback_title or found_editor_title}'."
        
    texts = []
    # Walk the tree with max depth to prevent freezing on DOM-heavy apps like Discord/Chrome
    try:
        for control, depth in auto.WalkControl(window_control, maxDepth=10):
            if control.ControlType in (auto.ControlType.TextControl, auto.ControlType.DocumentControl, auto.ControlType.EditControl):
                try:
                    name = control.Name
                    # Sometimes Edit controls use 'Value' pattern instead of 'Name'
                    if not name and control.ControlType == auto.ControlType.EditControl:
                        try:
                            name = control.GetValuePattern().Value
                        except:
                            pass
                    
                    if name and name.strip():
                        texts.append(name.strip())
                except:
                    pass
    except Exception as e:
        print(f"   [⚠️ UIA WalkControl interrupted: {e}]")
                
    raw_text = "\n".join(texts)
    
    if not raw_text.strip():
        return f"Target window '{fallback_title or found_editor_title}' did not expose any readable UIA Text elements. It may be rendering a custom canvas instead of native controls."
        
    if len(raw_text) > 4000:
        raw_text = raw_text[:4000] + "\n... [TRUNCATED FOR MEMORY]"
        
    return f"Extracted via native UI Automation from '{fallback_title or found_editor_title}':\n\n{raw_text}"
