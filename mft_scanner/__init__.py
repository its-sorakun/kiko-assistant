import os
import subprocess
import psutil

def perform_global_search(filename: str) -> str:
    """Scans the raw NTFS Master File Table (MFT) across all attached drives to locate a file instantly."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(current_dir, 'fast_search.exe')

    if not os.path.exists(exe_path):
        return f"CRITICAL ERROR: Native MFT scanner executable not found at {exe_path}. Compilation required."

    drives = [p.device.strip('\\') for p in psutil.disk_partitions() if 'NTFS' in p.fstype.upper()]
    if not drives:
        drives = ["C:"] # fallback
        
    all_outputs = []
    
    for drive in drives:
        try:
            print(f"   [⚡ Kiko is scanning the Master File Table on {drive} for: '{filename}'...]")
            # Capture stdout as text to parse the raw Win32 console output directly
            result = subprocess.run(
                [exe_path, drive, filename],
                capture_output=True,
                text=True,
                check=True
            )
            
            output = result.stdout.strip()
            if output:
                all_outputs.append(output)
                
        except subprocess.CalledProcessError as e:
            # Return stdout natively to expose underlying Win32 DeviceIoControl failures (e.g., lack of Admin privileges)
            # We append it as an error message but keep scanning other drives
            all_outputs.append(f"[{drive}] Scanner failed with exit code {e.returncode}. Output: {e.stdout.strip()}")
        except Exception as e:
            all_outputs.append(f"[{drive}] Subprocess invocation failed: {str(e)}")

    if not all_outputs or all([msg.startswith("[") for msg in all_outputs if "Scanner failed" in msg]):
        return f"No matches found for '{filename}' across all attached drives.\n" + "\n".join(all_outputs)
        
    return "\n".join(all_outputs)
