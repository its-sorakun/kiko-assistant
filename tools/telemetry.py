# tools/telemetry.py - Hardware telemetry probing and thermal sensor extraction

# Grabbing CPU/RAM via psutil is straightforward, but thermal data is restricted in Windows user-space. Attempting to probe ACPI thermal zones natively via WMI here. Be aware that without a Ring-0 kernel driver, most modern desktop motherboards will silently block this read.
import psutil
import subprocess

def get_system_stats() -> str:
    """
    Check the PC's vitals: CPU, RAM, and GPU usage/temps.
    """
    cpu_usage = psutil.cpu_percent(interval=0.1)
    
    ram = psutil.virtual_memory()
    total_ram_gb = round(ram.total / (1024 ** 3), 1)
    used_ram_gb = round(ram.used / (1024 ** 3), 1)
    
    # bypass user-space wmi limitations by reading the exact 8-byte memory block
    # exposed by background c++ daemon, which polls smu via a ring-0 driver.
    cpu_temp = "N/A (Daemon offline)"
    try:
        import mmap
        import struct
        
        # -1 maps to system paging file instead of a physical disk file
        shmem = mmap.mmap(-1, 8, tagname="Kiko_CPU_Temp", access=mmap.ACCESS_READ)
        
        # c++ daemon writes a double (8 bytes). 'd' unpacks to a python float.
        raw_bytes = shmem.read(8)
        celsius = struct.unpack('d', raw_bytes)[0]
        
        # 0.0 indicates startup signal from the daemon before the first hardware poll
        if celsius > 0.0:
            cpu_temp = f"{celsius:.1f}C"
            
        shmem.close()
    except Exception:
        # shared memory missing indicates daemon is offline
        # main.py is responsible for orchestrating the daemon lifecycle during boot
        pass


    # Extract GPU Temp natively via nvidia-smi (if NVIDIA driver is present)
    gpu_temp = "N/A"
    try:
        cmd = ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=0x08000000)
        if result.stdout.strip():
            gpu_temp = f"{result.stdout.strip()}C"
    except Exception:
        pass
    
    return f"CPU Usage: {cpu_usage}% (Temp: {cpu_temp}). RAM: {used_ram_gb}GB / {total_ram_gb}GB ({ram.percent}%). GPU Temp: {gpu_temp}"

def get_hardware_details() -> str:
    """
    Retrieve underlying hardware specifications bypassing high-level wrappers.
    Queries the Common Information Model (CIM) for read-only hardware data.
    """
    try:
        # Request read-only hardware specifications directly from the OS
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product | ConvertTo-Json -Compress"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Hardware CIM Data: {result.stdout.strip()}"
    except subprocess.CalledProcessError as e:
        return f"Failed to retrieve hardware details: {e.stderr}"

def format_model_name(model_slug: str) -> str:
    """
    Format internal model identifier slugs into clean, human-readable display titles.
    Maps canonical Gemini and Gemma model names while providing title-case transformation fallback.
    """
    mapping = {
        'gemini-3.6-flash': 'Gemini 3.6 Flash',
        'gemini-3.8-flash': 'Gemini 3.8 Flash',
        'gemini-flash-latest': 'Gemini Flash Latest',
        'gemini-flash-lite-latest': 'Gemini Flash Lite',
        'gemini-3.7-flash': 'Gemini 3.7 Flash',
        'gemini-3-flash-preview': 'Gemini 3 Flash Preview',
        'gemini-pro-latest': 'Gemini Pro Latest',
        'gemma-4-26b-a4b-it': 'Gemma 4 26B',
    }
    if model_slug in mapping:
        return mapping[model_slug]
    return ' '.join(word.capitalize() for word in model_slug.replace('-', ' ').split())

def get_current_model() -> str:
    """
    Retrieve the AI model name that Kiko is currently operating on.
    Bypasses static hardcoding by inspecting the runtime state of the active model orchestrator.
    """
    try:
        import sys
        if 'main' in sys.modules:
            main_mod = sys.modules['main']
            active_model = getattr(main_mod, 'model_name', 'Unknown')
            model_index = getattr(main_mod, 'current_model_index', 0)
            fallback_list = getattr(main_mod, 'model_fallback_chain', [])
            total = len(fallback_list)
            formatted = format_model_name(active_model)
            return f"Currently running on model {formatted} ({active_model}, index {model_index + 1} of {total} in fallback chain)."
        return f"Currently running on model: {format_model_name('gemini-3.6-flash')}"
    except Exception as e:
        return f"Failed to inspect active model: {e}"

