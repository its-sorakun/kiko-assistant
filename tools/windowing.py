# If the script runs in a terminal, the terminal inherently holds the "active" window focus. Drop down to user32.dll and crawl the Desktop Window Manager (DWM) Z-order stack downward to identify the actual underlying application.
import ctypes
import os
import psutil

def open_directory(folder_path: str) -> str:
    """
    Open a specific folder using the native Windows Explorer.
    """
    # Quick sanity check to make sure the folder actually exists
    if os.path.exists(folder_path):
        os.startfile(folder_path)
        return f"Opened folder: {folder_path}"
    else:
        return f"Target directory does not exist: {folder_path}"

def list_directory_contents(folder_path: str) -> str:
    """
    List all files and subdirectories inside a given folder, returning the result as text.
    Use this to 'see' what is inside a folder without opening it visually.
    """
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
    Attempt to read the contents of the currently active editor window.
    Instead of relying on bloated UI automation frameworks, this intercepts the DWM Z-order 
    to extract the window title, parses the active filename, and pulls the raw bytes directly from the physical disk.
    """
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    GW_HWNDNEXT = 2
    
    # Target known IDE/Editor signatures in window titles
    editor_signatures = ["Visual Studio Code", "Notepad", "Sublime Text", "Cursor", "Antigravity"]
    found_title = None
    
    # Crawl the Z-order to hunt down the nearest running code editor
    for _ in range(50):
        if not hwnd: break
        
        # Only check visible, non-minimized windows
        if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                title_buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, title_buf, length + 1)
                window_title = title_buf.value
                
                # Check if this window belongs to a known editor
                if any(sig in window_title for sig in editor_signatures):
                    found_title = window_title
                    break
                    
        hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
        
    if not found_title:
        return "Could not find any active (non-minimized) code editors in the Z-order stack to read from."
        
    # Parse common editor window title structures (e.g. "filename.py - workspace - Visual Studio Code" or "workspace - filename.py")
    parts = found_title.split(" - ")
    if not parts:
        return f"Window title too ambiguous to deduce filename: {found_title}"
        
    # The filename could be anywhere in the title depending on the IDE config.
    # iterate through the parts and find the first one that looks like a valid file (contains an extension or dot).
    raw_filename = None
    for part in parts:
        clean_part = part.strip().lstrip('*') # Strip the unsaved changes asterisk
        if "." in clean_part or clean_part.startswith("."):
            # Extract just the filename in case the IDE title contains the full absolute path
            raw_filename = os.path.basename(clean_part.replace("\\", "/"))
            break
            
    if not raw_filename:
        return f"Target IDE window '{found_title}' does not appear to have an active file open (could not extract a valid filename)."
        
    # Crawl the local filesystem to find the physical file
    target_path = None
    search_root = os.getcwd()
    
    for root, _, files in os.walk(search_root):
        # Skip heavy directories like .git or __pycache__ for speed
        if ".git" in root or "__pycache__" in root:
            continue
        if raw_filename in files:
            target_path = os.path.join(root, raw_filename)
            break
            
    if not target_path:
        return f"Extracted '{raw_filename}' from IDE title, but the physical file is missing from {search_root}."
        
    # Read the raw file directly off the disk
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Truncate to prevent token overflow on massive files
            if len(content) > 2000:
                content = content[:2000] + "\n... [FILE TRUNCATED]"
            return f"Deduced physical path from Z-order: {target_path}\n\n[FILE CONTENTS]\n{content}"
    except Exception as e:
        return f"Located {target_path} but kernel denied read access: {e}"
