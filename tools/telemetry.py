# tools/telemetry.py - Hardware telemetry probing, inventory inspection, and thermal sensor extraction
# Implementation details:
# Probes hardware vitals, queries Common Information Model (CIM) and psutil for detailed system specifications,
# extracts CPU thermal metrics via shared memory IPC from a C++ driver daemon, reads GPU status via nvidia-smi,
# and coordinates runtime AI model inspection and switching.

# Grabbing CPU/RAM via psutil is straightforward, but thermal data is restricted in Windows user-space. Attempting to probe ACPI thermal zones natively via WMI here. Be aware that without a Ring-0 kernel driver, most modern desktop motherboards will silently block this read.
import json
import os
import platform
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

# In-memory cache for static hardware specifications to avoid repetitive 2-second CIM process spawns
_cached_hardware_specs = None

def _probe_static_hardware(force_refresh: bool = False) -> dict:
    """
    Queries the Windows Common Information Model (CIM) via PowerShell to retrieve static hardware specifications.
    Consolidates computer system, motherboard, processor, video controllers, physical memory sticks, and
    storage drives into a single JSON payload to minimize process spawn overhead.
    """
    global _cached_hardware_specs
    if _cached_hardware_specs is not None and not force_refresh:
        return _cached_hardware_specs

    script = (
        "@{"
        "Computer = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model; "
        "Motherboard = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product; "
        "Processor = Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed; "
        "Video = @(Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion); "
        "Memory = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer, Capacity, Speed, PartNumber); "
        "Disks = @(Get-CimInstance Win32_DiskDrive | Select-Object Model, Size, MediaType) "
        "} | ConvertTo-Json -Depth 3"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=True,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        data = json.loads(result.stdout)
        _cached_hardware_specs = data
        return data
    except Exception as e:
        return {"error": f"Failed to probe static hardware via CIM: {e}"}

def _resolve_amd_igpu_model(cpu_name: str) -> str:
    """
    Resolves the marketing model of AMD integrated graphics (e.g. Radeon 660M) when the
    Windows driver INF genericizes the adapter name to 'AMD Radeon(TM) Graphics'.
    Correlates the CPU generation and Compute Unit (CU) tier.
    """
    cpu_upper = cpu_name.upper()
    # Rembrandt (Zen 3+ / RDNA 2) - 6000 and 7035 mobile series
    if any(k in cpu_upper for k in ["7535", "6600"]):
        return "AMD Radeon 660M (RDNA 2, 6 CUs)"
    elif any(k in cpu_upper for k in ["7735", "7736", "6800", "6900", "6980"]):
        return "AMD Radeon 680M (RDNA 2, 12 CUs)"
    # Phoenix / Hawk Point (Zen 4 / RDNA 3) - 7040 and 8040 mobile series
    elif any(k in cpu_upper for k in ["7540", "7640", "8540", "8640", "8645"]):
        return "AMD Radeon 760M (RDNA 3, 8 CUs)"
    elif any(k in cpu_upper for k in ["7840", "7940", "8840", "8845", "8945"]):
        return "AMD Radeon 780M (RDNA 3, 12 CUs)"
    # Strix Point (Zen 5 / RDNA 3.5)
    elif "HX 370" in cpu_upper:
        return "AMD Radeon 890M (RDNA 3.5, 16 CUs)"
    elif "HX 365" in cpu_upper:
        return "AMD Radeon 880M (RDNA 3.5, 12 CUs)"
    # Cezanne / Barcelo / Renoir / Lucienne (Zen 3 / Zen 2 Vega)
    elif any(k in cpu_upper for k in ["5600", "5500", "4600", "4500"]):
        return "AMD Radeon Vega 7"
    elif any(k in cpu_upper for k in ["5800", "5700", "4800", "4700"]):
        return "AMD Radeon Vega 8"
    return ""

def get_hardware_details(force_refresh: bool = False) -> str:
    """
    Retrieve comprehensive hardware specifications and system architecture of the host PC.
    Returns details on CPU (model, cores, threads), GPUs (dedicated and integrated, VRAM), RAM (total, speed, sticks),
    storage drives (models, partitions, free space), machine model (laptop or desktop chassis), OS, and battery status.
    Uses in-memory caching to return specs instantly after the initial probe. Set force_refresh=True to re-probe.
    """
    raw = _probe_static_hardware(force_refresh=force_refresh)
    if "error" in raw:
        return raw["error"]

    def _ensure_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            return [val]
        return []

    comp = raw.get("Computer") or {}
    proc = raw.get("Processor") or {}
    videos = _ensure_list(raw.get("Video"))
    mems = _ensure_list(raw.get("Memory"))
    disks = _ensure_list(raw.get("Disks"))

    output_lines = [
        "=== SYSTEM HARDWARE SPECIFICATIONS ===",
        f"Host System: {comp.get('Manufacturer', 'Unknown')} {comp.get('Model', 'Unknown')}",
        f"OS: {platform.system()} {platform.release()} (Build {platform.version()}) [{platform.machine()}]",
        f"CPU: {proc.get('Name', 'Unknown').strip()}",
        f"   -> Cores: {proc.get('NumberOfCores', 'N/A')} Physical | Threads: {proc.get('NumberOfLogicalProcessors', 'N/A')} Logical"
    ]

    gpu_descriptions = []
    for video in videos:
        name = video.get("Name", "Unknown")
        # If Windows driver reports generic 'AMD Radeon(TM) Graphics', correlate with CPU to resolve exact iGPU marketing model
        if "AMD Radeon" in name and ("Graphics" in name or "(TM)" in name):
            resolved_igpu = _resolve_amd_igpu_model(proc.get("Name", ""))
            if resolved_igpu:
                name = resolved_igpu

        ram_bytes = video.get("AdapterRAM") or 0
        if ram_bytes > 0:
            ram_gb = round(ram_bytes / (1024 ** 3), 1)
            vram_label = f"{ram_gb}GB VRAM" if ram_gb >= 1 else f"{round(ram_bytes / (1024 ** 2))}MB VRAM"
        else:
            vram_label = "Shared VRAM"
        gpu_descriptions.append(f"{name} ({vram_label})")
    output_lines.append("GPU(s): " + (" | ".join(gpu_descriptions) if gpu_descriptions else "None detected"))

    # Live memory metrics from psutil combined with physical stick descriptors from CIM
    vm = psutil.virtual_memory()
    total_ram = round(vm.total / (1024 ** 3), 1)
    avail_ram = round(vm.available / (1024 ** 3), 1)
    output_lines.append(f"RAM: {total_ram}GB Installed ({avail_ram}GB Currently Available)")
    for i, mem in enumerate(mems, 1):
        cap = round((mem.get("Capacity") or 0) / (1024 ** 3), 1)
        speed = mem.get("Speed", "N/A")
        mfg = (mem.get("Manufacturer") or "Unknown").strip()
        part = (mem.get("PartNumber") or "").strip()
        output_lines.append(f"   -> Slot {i}: {cap}GB @ {speed}MT/s ({mfg} {part})")

    output_lines.append("Storage Drives & Partitions:")
    for disk in disks:
        size_gb = round((disk.get("Size") or 0) / (1024 ** 3), 1)
        output_lines.append(f"   -> Physical Drive: {disk.get('Model', 'Unknown')} ({size_gb}GB)")
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            output_lines.append(
                f"   -> Partition {part.device} ({part.fstype}): "
                f"{usage.free / (1024 ** 3):.1f}GB Free / {usage.total / (1024 ** 3):.1f}GB Total "
                f"({100 - usage.percent:.1f}% free)"
            )
        except Exception:
            pass

    battery = psutil.sensors_battery()
    if battery:
        state = "AC Power Connected" if battery.power_plugged else "Running on Battery"
        output_lines.append(f"Power: Battery at {battery.percent}% ({state})")
    else:
        output_lines.append("Power: Desktop AC (No battery)")

    return "\n".join(output_lines)

def format_model_name(model_slug: str) -> str:
    """
    Format internal model identifier slugs into clean, human-readable display titles.
    Maps canonical Gemini and Gemma model names while providing title-case transformation fallback.
    """
    mapping = {
        # Gemini 3 - Official Models
        'gemini-3.8-flash': 'Gemini 3.8 Flash',
        'gemini-3.8-live': 'Gemini 3.8 Live',
        'gemini-3.8-live-extended-thinking': 'Gemini 3.8 Live Extended Thinking',
        'gemini-3.8-flash-tts': 'Gemini 3.8 Flash TTS',
        'gemini-3.8-flash-lite-tts': 'Gemini 3.8 Flash-Lite TTS',
        'gemini-3.6-flash': 'Gemini 3.6 Flash',
        'gemini-3.5-flash': 'Gemini 3.5 Flash',
        'gemini-3.5-flash-lite': 'Gemini 3.5 Flash-Lite',
        'gemini-3.1-flash-lite': 'Gemini 3.1 Flash-Lite',
        'gemini-nano-banana-2.1': 'Nano Banana 2.1',
        'gemini-3.1-flash-image': 'Nano Banana 2',
        'gemini-3.1-flash-lite-image': 'Nano Banana 2 Lite',
        'gemini-3-pro-image': 'Nano Banana Pro',
        'gemini-3.5-transcribe': 'Gemini 3.5 Transcribe',
        'gemini-3.5-transcribe-live': 'Gemini 3.5 Transcribe Live',
        'gemini-omni-1.1-flash': 'Gemini Omni Flash',
        'gemini-3.1-pro-preview': 'Gemini 3.1 Pro Preview',
        'gemini-3-flash-preview': 'Gemini 3 Flash Preview',
        'gemini-3.5-live-translate-preview': 'Gemini 3.5 Live Translate',
        'gemini-3.1-flash-live-preview': 'Gemini 3.1 Flash Live Preview',
        'gemini-3.1-flash-tts-preview': 'Gemini 3.1 Flash TTS Preview',
        # Dynamic Gemini Aliases and Other Generations
        'gemini-flash-latest': 'Gemini Flash Latest',
        'gemini-flash-lite-latest': 'Gemini Flash Lite',
        'gemini-pro-latest': 'Gemini Pro Latest',
        'gemini-4-argon': 'Gemini 4 Argon',
        'gemma-4-26b-a4b-it': 'Gemma 4 26B',
    }
    if model_slug in mapping:
        return mapping[model_slug]
    return ' '.join(word.capitalize() for word in model_slug.replace('-', ' ').split())

def _get_main_module():
    """
    Locates the active main orchestrator module regardless of whether Kiko was launched
    via the terminal CLI (where the entry script is registered under '__main__')
    or via the web server/test harnesses (where it is imported as 'main').
    """
    import sys
    for mod_name in ('main', '__main__'):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, 'model_fallback_chain'):
            return mod
    return None

def get_current_model() -> str:
    """
    Retrieve the AI model name that Kiko is currently operating on.
    Bypasses static hardcoding by inspecting the runtime state of the active model orchestrator.
    """
    try:
        main_mod = _get_main_module()
        if main_mod:
            active_model = getattr(main_mod, 'model_name', 'Unknown')
            model_index = getattr(main_mod, 'current_model_index', 0)
            fallback_list = getattr(main_mod, 'model_fallback_chain', [])
            total = len(fallback_list)
            formatted = format_model_name(active_model)
            return f"Currently running on model {formatted} ({active_model}, index {model_index + 1} of {total} in fallback chain)."
        return f"Currently running on model: {format_model_name('gemini-3.5-flash-lite')}"
    except Exception as e:
        return f"Failed to inspect active model: {e}"

def list_available_models() -> str:
    """
    List all supported AI models that Kiko has access to switch between.
    Call this whenever the user asks what models are available or what models Kiko can use.
    """
    try:
        main_mod = _get_main_module()
        fallback_list = []
        active_model = ""
        if main_mod:
            fallback_list = getattr(main_mod, 'model_fallback_chain', [])
            active_model = getattr(main_mod, 'model_name', '')
            
        if not fallback_list:
            fallback_list = [
                'gemini-3.5-flash-lite',
                'gemini-3.6-flash',
                'gemini-3.8-flash',
                'gemini-3.1-flash-lite',
                'gemini-3-flash-preview',
                'gemini-3.1-pro-preview',
                'gemini-omni-1.1-flash',
                'gemini-flash-latest',
                'gemini-flash-lite-latest',
                'gemini-pro-latest',
                'gemini-4-argon',
                'gemma-4-26b-a4b-it',
            ]
            
        lines = ["Available AI Models:"]
        for idx, m in enumerate(fallback_list, 1):
            title = format_model_name(m)
            status = " [ACTIVE]" if m == active_model else ""
            lines.append(f"{idx}. {title} (`{m}`){status}")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list models: {e}"

def switch_ai_model(target_model: str) -> str:
    """
    Switch Kiko's active AI model to a specified available model from her verified list.
    Fuzzy-matches input strings against permitted models to prevent 404/quota errors.
    Recreates the active chat session with existing history preserved to prevent context loss.
    """
    try:
        import difflib
        main_mod = _get_main_module()
        if not main_mod:
            return "Cannot switch models: Core orchestrator module is not loaded."
            
        allowed_models = getattr(main_mod, 'model_fallback_chain', [])
        
        query = target_model.strip().lower()
        # Check specialized models first
        specialized_models = {
            'gemini-3.8-live': 'real-time bidirectional Live API (WebSockets)',
            'gemini-3.8-live-extended-thinking': 'real-time bidirectional Live API with thinking',
            'gemini-3.5-live-translate-preview': 'real-time speech translation',
            'gemini-3.1-flash-live-preview': 'real-time Live API preview',
            'gemini-3.8-flash-tts': 'direct audio text-to-speech generation',
            'gemini-3.8-flash-lite-tts': 'fast audio text-to-speech generation',
            'gemini-3.1-flash-tts-preview': 'audio text-to-speech generation',
            'gemini-3.5-transcribe': 'audio speech-to-text transcription',
            'gemini-3.5-transcribe-live': 'real-time speech transcription',
            'gemini-nano-banana-2.1': 'image generation and editing',
            'gemini-3.1-flash-image': 'image generation and editing',
            'gemini-3.1-flash-lite-image': 'fast image generation and editing',
            'gemini-3-pro-image': 'high-fidelity image generation and editing',
        }
        cleaned_query = query.replace("gemini", "").replace("-", " ").strip()
        for spec_slug, purpose in specialized_models.items():
            cleaned_spec = spec_slug.replace("gemini", "").replace("-", " ").strip()
            if spec_slug == query or (cleaned_query and cleaned_query in cleaned_spec):
                return f"Model '{spec_slug}' ({format_model_name(spec_slug)}) is specifically dedicated to {purpose} and does not support standard conversational tool-calling. Please choose a conversational Gemini 3 model like Gemini 3.8 Flash, Gemini 3.6 Flash, or Gemini 3.5 Flash-Lite."

        matched = None
        matched_idx = -1

        # Exact slug match first
        for idx, m in enumerate(allowed_models):
            if m.lower() == query:
                matched = m
                matched_idx = idx
                break
                
        # Substring matching against slug or formatted title
        if not matched:
            for idx, m in enumerate(allowed_models):
                formatted = format_model_name(m).lower()
                cleaned_m = m.replace("gemini", "").replace("-", " ").strip()
                if query in m.lower() or query in formatted or (cleaned_query and cleaned_query in cleaned_m):
                    matched = m
                    matched_idx = idx
                    break

        # Fuzzy matching with difflib to handle typos like 'gemmma 4'
        if not matched:
            best_ratio = 0.0
            best_candidate = None
            best_idx = -1
            for idx, m in enumerate(allowed_models):
                formatted = format_model_name(m).lower()
                cleaned_m = m.replace("gemini", "").replace("-", " ").strip()
                
                ratio_slug = difflib.SequenceMatcher(None, query, m.lower()).ratio()
                ratio_formatted = difflib.SequenceMatcher(None, query, formatted).ratio()
                ratio_cleaned = difflib.SequenceMatcher(None, cleaned_query, cleaned_m).ratio() if cleaned_query else 0.0
                
                candidate_max = max(ratio_slug, ratio_formatted, ratio_cleaned)
                if candidate_max > best_ratio:
                    best_ratio = candidate_max
                    best_candidate = m
                    best_idx = idx
                    
            if best_candidate and best_ratio >= 0.6:
                matched = best_candidate
                matched_idx = best_idx
                    
        if not matched:
            allowed_str = ", ".join(f"`{m}` ({format_model_name(m)})" for m in allowed_models)
            return f"Model '{target_model}' is not in the allowed list to avoid 404/quota errors. Allowed models are: {allowed_str}"
            
        # Update runtime model state
        main_mod.model_name = matched
        main_mod.current_model_index = matched_idx
        
        # If terminal chat instance exists, preserve conversation history across the engine swap
        if hasattr(main_mod, 'chat') and main_mod.chat:
            try:
                history = main_mod.chat.get_history()
                main_mod.chat = main_mod.client.chats.create(
                    model=matched,
                    config=main_mod.config,
                    history=history
                )
            except Exception:
                # If history extraction fails, recreate clean session with identical config
                main_mod.chat = main_mod.client.chats.create(
                    model=matched,
                    config=main_mod.config
                )
                
        display = format_model_name(matched)
        return f"Successfully switched active AI engine to {display} (`{matched}`)."
    except Exception as e:
        return f"Failed to switch AI model: {e}"

