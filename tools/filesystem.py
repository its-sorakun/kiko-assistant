# tools/filesystem.py - Native filesystem navigation, metadata extraction, and directory tree inspection
# Implementation details:
# Interacts directly with the Windows filesystem using os.scandir and Win32 file attribute APIs.
# Computes recursive directory footprints, tracks top largest files via in-memory min-heaps,
# resolves Windows environment variables and common user aliases, and manages OS-level file opening.

import os
import datetime
import heapq
import ctypes

def _format_size(size_bytes: int) -> str:
    """Format a byte integer into human-readable B, KB, MB, or GB strings."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"

def _normalize_target_path(path_str: str) -> str:
    """
    Expands user home shortcuts (~), Windows environment variables (%TEMP%, %APPDATA%),
    and resolves common conversational aliases like 'temp', 'downloads', 'desktop'.
    """
    path_clean = path_str.strip().strip("'\"")
    lower = path_clean.lower()
    if lower in ("temp", "tmp", "temp folder", "temp directory"):
        return os.environ.get("TEMP") or os.path.expandvars(r"%LOCALAPPDATA%\Temp")
    elif lower in ("windows temp", "system temp"):
        return r"C:\Windows\Temp"
    elif lower in ("downloads", "download"):
        return os.path.expanduser("~/Downloads")
    elif lower in ("desktop",):
        return os.path.expanduser("~/Desktop")
    elif lower in ("documents", "doc", "docs"):
        return os.path.expanduser("~/Documents")
    
    expanded = os.path.expandvars(os.path.expanduser(path_clean))
    return os.path.abspath(expanded)

def _scan_directory_stats(dir_path: str, max_files: int = 100000) -> tuple[int, int, int, list]:
    """
    Recursively scans a directory using os.scandir to aggregate total byte size, file count,
    directory count, and top largest files with minimal syscall overhead.
    Returns: (total_bytes, file_count, dir_count, largest_files_heap)
    """
    total_bytes = 0
    file_count = 0
    dir_count = 0
    largest_files = []

    stack = [dir_path]
    while stack and file_count < max_files:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        # Follow symlinks is False to avoid infinite loops and external boundary traversal
                        if entry.is_dir(follow_symlinks=False):
                            dir_count += 1
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            file_count += 1
                            stat = entry.stat(follow_symlinks=False)
                            sz = stat.st_size
                            total_bytes += sz
                            if len(largest_files) < 5:
                                heapq.heappush(largest_files, (sz, entry.path))
                            elif sz > largest_files[0][0]:
                                heapq.heapreplace(largest_files, (sz, entry.path))
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue

    largest_files.sort(key=lambda x: x[0], reverse=True)
    return total_bytes, file_count, dir_count, largest_files

def inspect_path(path: str) -> str:
    """
    Inspect comprehensive metadata, disk footprint, and statistics for any file or directory path.
    Supports environment variables ('%TEMP%', '%APPDATA%'), user shortcuts ('~/Downloads'),
    and common aliases ('temp', 'desktop', 'downloads').
    For directories: returns total recursive size, file/folder counts, and top 5 largest files.
    For files: returns exact size, timestamps (created, modified, accessed), and file attributes.
    """
    target = _normalize_target_path(path)
    if not os.path.exists(target):
        return f"Target path does not exist: {target} (resolved from '{path}')"

    try:
        stat_info = os.stat(target)
    except Exception as e:
        return f"Failed to access metadata for '{target}': {e}"

    created_time = datetime.datetime.fromtimestamp(stat_info.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    modified_time = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    # Directory inspection branch
    if os.path.isdir(target):
        total_bytes, f_count, d_count, top_files = _scan_directory_stats(target)
        output = [
            f"=== DIRECTORY INSPECTION: {target} ===",
            f"Total Recursive Size: {_format_size(total_bytes)} ({total_bytes:,} bytes)",
            f"Total Files: {f_count:,} | Total Subdirectories: {d_count:,}",
            f"Created: {created_time} | Last Modified: {modified_time}",
        ]
        if top_files:
            output.append("\nTop Largest Files in Directory:")
            for sz, p in top_files:
                rel = os.path.relpath(p, target)
                output.append(f"   -> {_format_size(sz):<10} : {rel}")
        return "\n".join(output)

    # File inspection branch
    else:
        sz = stat_info.st_size
        _, ext = os.path.splitext(target)
        ext_label = ext.lower() if ext else "No extension"

        attrs = []
        if os.name == 'nt':
            file_attrs = ctypes.windll.kernel32.GetFileAttributesW(target)
            if file_attrs != -1:
                if file_attrs & 0x01: attrs.append("Read-Only")
                if file_attrs & 0x02: attrs.append("Hidden")
                if file_attrs & 0x04: attrs.append("System")
                if file_attrs & 0x20: attrs.append("Archive")
                if file_attrs & 0x400: attrs.append("Reparse Point (Symlink/Junction)")

        attr_str = ", ".join(attrs) if attrs else "Normal"
        output = [
            f"=== FILE INSPECTION: {target} ===",
            f"Size: {_format_size(sz)} ({sz:,} bytes)",
            f"Extension / Type: {ext_label}",
            f"Attributes: {attr_str}",
            f"Created: {created_time}",
            f"Last Modified: {modified_time}",
            f"Last Accessed: {datetime.datetime.fromtimestamp(stat_info.st_atime).strftime('%Y-%m-%d %H:%M:%S')}"
        ]
        return "\n".join(output)

def list_directory_contents(folder_path: str) -> str:
    """
    List files and subdirectories inside a given folder with individual sizes, types, and timestamps.
    Use this to inspect what is inside a folder without opening it visually in Windows Explorer.
    Supports '~', environment variables (e.g., '~/Desktop', '%TEMP%'), and common aliases ('temp').
    """
    target = _normalize_target_path(folder_path)
    if not os.path.exists(target):
        return f"Target directory does not exist: {target}"
    if not os.path.isdir(target):
        return f"Target path is a file, not a directory: {target}. Use inspect_path to inspect it."

    try:
        entries = []
        with os.scandir(target) as it:
            for entry in it:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    stat = entry.stat(follow_symlinks=False)
                    mod_date = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    if is_dir:
                        entries.append(f"   [DIR]  {entry.name:<32} | Modified: {mod_date}")
                    else:
                        sz_str = _format_size(stat.st_size)
                        entries.append(f"   [FILE] {entry.name:<32} | {sz_str:>9} | Modified: {mod_date}")
                except (PermissionError, OSError):
                    entries.append(f"   [???]  {entry.name:<32} | Access Restricted")

        if not entries:
            return f"The directory '{target}' is empty."

        entries.sort()
        header = f"=== CONTENTS OF: {target} ({len(entries)} items) ==="
        return header + "\n" + "\n".join(entries[:100]) + ("\n... [TRUNCATED: more than 100 items]" if len(entries) > 100 else "")
    except PermissionError:
        return f"Access Denied: Windows is preventing read access to '{target}'."
    except Exception as e:
        return f"Failed to list contents: {str(e)}"

def open_directory(folder_path: str) -> str:
    """
    Open a specific folder visually using the native Windows Explorer.
    Supports '~', environment variables, and common aliases (e.g., '~/Documents', '%TEMP%').
    """
    target = _normalize_target_path(folder_path)
    if os.path.exists(target) and os.path.isdir(target):
        os.startfile(target)
        return f"Opened folder in Windows Explorer: {target}"
    elif os.path.exists(target):
        os.startfile(os.path.dirname(target))
        return f"Path is a file. Opened parent directory in Windows Explorer: {os.path.dirname(target)}"
    else:
        return f"Target directory does not exist: {target}"

def open_file(file_path: str) -> str:
    """
    Launch a specific file in its default associated Windows application.
    Supports '~' and environment variables (e.g., '~/Downloads/document.pdf').
    """
    target = _normalize_target_path(file_path)
    if os.path.exists(target):
        os.startfile(target)
        return f"Opened file: {target}"
    else:
        return f"Target file does not exist: {target}"

