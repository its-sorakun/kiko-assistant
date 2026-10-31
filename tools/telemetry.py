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
        # Gemini 3 - Official Models
        'gemini-3.8-flash': 'Gemini 3.8 Flash',
        'gemini-3.8-live': 'Gemini 3.8 Live',
        'gemini-3.8-live-extended-thinking': 'Gemini 3.8 Live Extended Thinking',
        'gemini-3.8-flash-tts': 'Gemini 3.8 Flash TTS',
        'gemini-3.8-flash-lite-tts': 'Gemini 3.8 Flash-Lite TTS',
        'gemini-3.6-flash': 'Gemini 3.6 Flash',
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

def list_available_models() -> str:
    """
    List all supported AI models that Kiko has access to switch between.
    Call this whenever the user asks what models are available or what models Kiko can use.
    """
    try:
        import sys
        fallback_list = []
        active_model = ""
        if 'main' in sys.modules:
            main_mod = sys.modules['main']
            fallback_list = getattr(main_mod, 'model_fallback_chain', [])
            active_model = getattr(main_mod, 'model_name', '')
            
        if not fallback_list:
            fallback_list = [
                'gemini-3.6-flash',
                'gemini-3.8-flash',
                'gemini-3.5-flash-lite',
                'gemini-3.1-flash-lite',
                'gemini-3-flash-preview',
                'gemini-3.1-pro-preview',
                'gemini-nano-banana-2.1',
                'gemini-3.1-flash-image',
                'gemini-3.1-flash-lite-image',
                'gemini-3-pro-image',
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
        import sys
        if 'main' not in sys.modules:
            return "Cannot switch models: Core orchestrator module is not loaded."
            
        main_mod = sys.modules['main']
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
        }
        cleaned_query = query.replace("gemini", "").replace("-", " ").strip()
        for spec_slug, purpose in specialized_models.items():
            cleaned_spec = spec_slug.replace("gemini", "").replace("-", " ").strip()
            if spec_slug == query or (cleaned_query and cleaned_query in cleaned_spec):
                return f"Model '{spec_slug}' ({format_model_name(spec_slug)}) is specifically dedicated to {purpose} and does not support standard conversational tool-calling. Please choose a conversational Gemini 3 model like Gemini 3.8 Flash, Gemini 3.6 Flash, or Gemini 3.5 Flash-Lite."

        # Exact slug match first
        for idx, m in enumerate(allowed_models):
            if m.lower() == query:
                matched = m
                matched_idx = idx
                break
                
        # Fuzzy matching against slug or formatted title
        if not matched:
            for idx, m in enumerate(allowed_models):
                formatted = format_model_name(m).lower()
                cleaned_m = m.replace("gemini", "").replace("-", " ").strip()
                if query in m.lower() or query in formatted or (cleaned_query and cleaned_query in cleaned_m):
                    matched = m
                    matched_idx = idx
                    break
                    
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

