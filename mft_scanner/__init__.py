import os
import subprocess

def perform_global_search(filename: str) -> str:
    """Scans the raw NTFS Master File Table (MFT) across the C: drive to locate a file instantly."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(current_dir, 'fast_search.exe')

    if not os.path.exists(exe_path):
        return f"CRITICAL ERROR: Native MFT scanner executable not found at {exe_path}. Compilation required."

    try:
        # Capture stdout as text to parse the raw Win32 console output directly
        result = subprocess.run(
            [exe_path, "C:", filename],
            capture_output=True,
            text=True,
            check=True
        )
        
        output = result.stdout.strip()
        
        if not output:
            return f"No matches found for '{filename}' in the Master File Table."
            
        return output
        
    except subprocess.CalledProcessError as e:
        # Return stdout natively to expose underlying Win32 DeviceIoControl failures (e.g., lack of Admin privileges)
        return f"MFT Scanner failed with exit code {e.returncode}. Output: {e.stdout.strip()}"
    except Exception as e:
        return f"Subprocess invocation failed: {str(e)}"
