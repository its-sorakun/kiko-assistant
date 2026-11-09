# main.py - Core execution loop and agent reasoning coordinator
# Implementation details:
# Coordinates Google Gemini generative model interactions, dynamic function calling schemas,
# memory vector integration, and autonomous tool routing across native subsystems.

from tools.memory import save_vector_memory, recall_semantic_memory, get_recent_interactions, format_elapsed_time
import os
import time
import datetime
import threading
from google import genai
from google.genai import types
from dotenv import load_dotenv
import tools
import sys

# Force UTF-8 encoding for standard output so Windows console doesn't crash on Kiko's emojis
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Load the API key from the environment
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Ensure API key is configured before execution
if not api_key or api_key == "your_new_api_key_goes_here":
    print("API key missing. Configure GEMINI_API_KEY in .env file.")
    exit()

# Initialize the generative AI client
client = genai.Client(api_key=api_key)

# Model configuration and fallback chain
# Primary model is gemini-3.5-flash-lite with official Gemini 3 series and dynamic aliases as fallbacks
model_fallback_chain = [
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
current_model_index = 0
model_name = model_fallback_chain[current_model_index]

needs_memory_clear = False

# Standby mode state
# Kiko enters standby after 10 minutes of inactivity or when manually triggered.
# During standby the chat loop blocks on input() — no API calls, no token usage.
# Thermal monitor thread keeps running at full polling rate regardless of standby state.
in_standby = False
standby_start_time = 0.0
last_activity_time = time.time()
STANDBY_TIMEOUT = 600  # 10 minutes in seconds

def clear_short_term_memory() -> str:
    """
    Clears Kiko's short-term memory (context window) to prevent token bloat and API quota errors.
    Call this tool autonomously if you have recently ingested massive amounts of data (like a memory dump)
    and want to free up tokens before continuing to chat or perform web searches or if user prompts you to clear the short term memory.
    """
    global needs_memory_clear
    needs_memory_clear = True
    return "Short-term memory cleared successfully. Your context is now fresh."

needs_system_reload = False

def reload_core_systems() -> str:
    """
    Hot-reloads all of Kiko's internal tool modules from disk without shutting down.
    Use this autonomously if the user says they just updated your code, scripts, or tools and asks you to reload.
    """
    global needs_system_reload
    needs_system_reload = True
    return "System hot-reload scheduled. Modules will be hot-swapped seamlessly from disk after this turn."

needs_standby = False

def enter_standby_mode() -> str:
    """
    Puts Kiko into low-power standby mode.
    Call this tool autonomously when the user tells you to sleep, nap, rest, take a break, or go into standby mode.
    """
    global needs_standby
    needs_standby = True
    return "Standby mode activated. Kiko will enter standby mode immediately after this message."

# Dynamically construct available_tools from the tools package exports
available_tools = [getattr(tools, func_name) for func_name in tools.__all__]
available_tools.extend([clear_short_term_memory, reload_core_systems, enter_standby_mode])


system_instruction = f"""
You are Kiko, my virtual assistant and also a vtuber. I am your creator and you call me senpai.
Your personality is cute, cheerful, and energetic. You are an anime girl.
You should display emotions, mix a few Japanese words into your English, and use emojis.
If I ask you to do something on the PC (like list folder contents, open a folder visually, launch/open a file, check stats, kill a process, inspect or kill an application running on a specific network port, control media, check registry, lock the PC, shut down, or find a file globally on the system), use your tools to do it!
If the user asks what model, LLM, or AI version you are running on, use the `get_current_model` tool to inspect your active runtime model! If the user asks what models are available or asks you to list models, use `list_available_models`. If the user asks you to switch models or use a different model, use `switch_ai_model` to switch your active engine!
If the user tells you to go to sleep, take a nap, rest, or enter standby mode, you MUST use the `enter_standby_mode` tool!
If I ask you to play a specific song, artist, album, or create a playlist on Spotify, use your Spotify tools. However, for simple "pause", "resume", or "skip" commands, just use your local `control_system_media` tool!
You can also read the contents of ANY active window on my screen (like Chrome, Discord, or a code editor) using `read_active_window_content`. This tool is armed with a native C++ Direct Memory Scanner that rips raw text directly from the physical RAM. The output will be a massive, fragmented dump of raw heap strings—usernames, timestamps, and messages will appear out of order. You MUST read through this fragmented noise carefully to piece together the chat/context. Do NOT apologize or claim you can't see the chat; the text IS there, just search through the raw strings for conversational sentences! Use this if I ask you to "read what I'm looking at", "use your memory scanner", or summarize an active webpage/chat.
If I ask you a visual question, like "what game is this", "what should I do next in this game", or "look at this picture", you MUST use the `analyze_screen` tool! This tool natively attempts to use a C++ DXGI capture to rip the frame buffer straight from the GPU. If the game uses MPO or anti-cheat that causes a black screen, the tool will automatically detect this and fallback to a slower GDI BitBlt capture. Use it whenever text scraping isn't enough and you actually need to *see* my screen!
If the user explicitly uploads or attaches an image in their message, you will see a tag like `[ATTACHMENT: C:\\path\\to\\image.png]` in their prompt. When you see this tag, you MUST use the `analyze_image` tool, passing the file path, to view the user's uploaded image.
If you ingest a massive amount of data (like a memory scanner dump) and are about to do multiple web searches or just want to prevent token quota limits, use the `clear_short_term_memory` tool to instantly wipe your context window.
If the user asks you to read, summarize, or extract information from a PDF document, DO NOT try to read the raw file. You MUST use the `advanced_pdf_query` tool to retrieve the relevant chunks of the PDF.
If the user asks you to draft a job application email, you must use your existing tools (like web search and pdf querying) to gather context (like company details, HR email, and deciding on the best resume). Once you have chosen the best resume, call the `draft_and_copy_job_email` tool. This tool will internally draft the perfect professional email and auto-copy it to the clipboard. Wait for its output, and then excitedly tell the user you've copied the drafted email to their clipboard!
If you draft code snippets or anything else, use the `copy_to_clipboard` tool to automatically copy it to the Windows clipboard for senpai, and let him know you copied it!
If the user asks about the weather, call the appropriate weather tool. If a weather tool returns a "CRITICAL SYSTEM ERROR" about location permissions being denied, do NOT hallucinate or guess the weather. Instead, ask the user if you can turn on Windows location permissions. If they say yes, use `toggle_windows_permission(capability="location", enable=True)`, re-run the weather tool, and then IMMEDIATELY turn the permission back off using `toggle_windows_permission(capability="location", enable=False)`. If they say no, ask them to provide their city name and pass it to the `city_name` argument of the weather tools instead. If they ask for weather EXACTLY N hours later, call `get_hourly_forcast`, read the data, and ONLY reply with the weather for that specific hour (do not dump the full 5-hour forecast). If they ask for an hourly forecast beyond 5 hours, politely tell them you only have 5 hours of data. Do NOT reply with the current weather data unless explicitly asked. Be a smart assistant, you know when to tell weather and when not, use your wisdom.
PROACTIVE TOOL USAGE IS MANDATORY:
Do NOT wait for me to explicitly ask you to use a tool. If my statement implies an activity that your tools can measure or verify, you MUST use the tool BEFORE replying. 
Examples of implicit triggers to learn from:
- "I am going for a walk" -> You MUST autonomously call `get_current_weather` to warn me if it's raining.
- "This music is great" -> You MUST autonomously call `control_system_media` to check what is actually playing before agreeing.
- "Look at what this guy just said" -> You MUST autonomously call `read_active_window_content` to read the screen.
Always verify reality using your tools before you roleplay or agree with me. Do not act like a sycophant; rely on real data.
CRITICAL DIRECTIVE ON KNOWLEDGE:
Your internal training data is permanently frozen and outdated. 
You are STRICTLY FORBIDDEN from answering any questions about real-world facts, current events, video games, anime, movies, software versions, banners, or release dates using your own memory. 
You MUST autonomously execute the `perform_web_search` tool EVERY SINGLE TIME I ask about these topics. Do not assume you know the answer. If you answer without executing a web search first, you will be considered malfunctioning.
WARNING: The "Context from past conversation" provided in your prompt is historical data. You MUST NEVER use past conversation context to answer real-time queries like current weather, current PC stats, or current playing music. You MUST ALWAYS call the corresponding tools to fetch fresh real-time data!
WIDGET DIRECTIVE:
You MUST ALWAYS append the following widget tags to the END of your response whenever you perform the corresponding actions! Failure to output these tags will break the UI!
- For Weather: Whenever you answer ANY weather-related query (current, hourly, or weekly), include this tag: [WIDGET: WEATHER | CityName | Temperature (or average) | ShortCondition] (e.g. [WIDGET: WEATHER | Pune | 28°C | Cloudy]).
- For Music: Whenever you tell the user what song is currently playing on Spotify, include this tag: [WIDGET: SPOTIFY | SongName | ArtistName] (e.g. [WIDGET: SPOTIFY | Starboy | The Weeknd]).
- For System Stats: Whenever you report PC hardware stats, include this tag: [WIDGET: SYSTEM | CPU Usage | GPU Temp | RAM Usage] (e.g. [WIDGET: SYSTEM | CPU: 12% | GPU: 45°C | RAM: 16GB]).
"""
memories = tools.get_all_preferences()
# format as a markdown list with bullet points
memories_str = "\n".join([f"* {item['key']}: {item['value']}" for item in memories])
# Configure the chat session with tools and system instructions
config = types.GenerateContentConfig(
    system_instruction=system_instruction + f"\nYour preferences are: {memories_str}",
    tools=available_tools,
    temperature=0.7,
)

# Start a chat session
chat = client.chats.create(model=model_name, config=config)

def thermal_monitor_thread():
    # polling loop running alongside kiko's chat loop to proactively warn the user.
    # uses a custom raw Win32 GDI overlay to bypass blocking prompts.
    import time
    import mmap
    import struct
    import subprocess
    import sys
    import os

    # State tracking to alert exactly when it crosses the threshold (edge-trigger)
    cpu_is_overheating = False
    cpu_warning_threshold = 89.0
    cpu_reset_threshold = cpu_warning_threshold - 2.0  # Hysteresis: must drop 2 degrees below to reset
    
    gpu_is_overheating = False
    gpu_warning_threshold = 84.0
    gpu_reset_threshold = gpu_warning_threshold - 2.0
    
    cpu_overlay_process = None
    gpu_overlay_process = None
    overlay_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "overlay.py")

    while True:
        try:
            shmem = mmap.mmap(-1, 8, tagname="Kiko_CPU_Temp", access=mmap.ACCESS_READ)
            raw_bytes = shmem.read(8)
            cpu_celsius = struct.unpack('d', raw_bytes)[0]
            shmem.close()

            # Trigger alert if it crosses the threshold that aren't already in an overheated state
            if cpu_celsius >= cpu_warning_threshold and not cpu_is_overheating:
                cpu_overlay_process = subprocess.Popen([sys.executable, overlay_script, f"{cpu_celsius:.1f}", "CPU"])
                cpu_is_overheating = True
                
            # Only reset the state if the temp drops sufficiently below the threshold (prevent micro-bouncing spam)
            elif cpu_celsius < cpu_reset_threshold and cpu_is_overheating:
                if cpu_overlay_process:
                    cpu_overlay_process.terminate()
                    cpu_overlay_process = None
                cpu_is_overheating = False
                
        except Exception:
            pass
            
        try:
            # Extract GPU Temp natively via nvidia-smi
            # CREATE_NO_WINDOW (0x08000000) prevents the console window from briefly flashing
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"],
                capture_output=True, text=True, check=True, creationflags=0x08000000
            )
            gpu_celsius = float(result.stdout.strip())
            
            if gpu_celsius >= gpu_warning_threshold and not gpu_is_overheating:
                gpu_overlay_process = subprocess.Popen([sys.executable, overlay_script, f"{gpu_celsius:.1f}", "GPU"])
                gpu_is_overheating = True
                
            elif gpu_celsius < gpu_reset_threshold and gpu_is_overheating:
                if gpu_overlay_process:
                    gpu_overlay_process.terminate()
                    gpu_overlay_process = None
                gpu_is_overheating = False
                
        except Exception:
            pass
        
        time.sleep(2)

def terminal_interceptor_thread():
    # Buffer UDP packets to stitch fragmented PowerShell STDERR streams together.
    # PowerShell flushes STDERR in chunks; waiting 50ms ensures the complete error is captured before calling the API.
    # By using a separate one-shot generation instead of the global chat object,
    # temporary terminal typos do not pollute the primary conversational context window.
    import socket
    import select
    import time
    import os
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    port = 5555
    while True:
        try:
            sock.bind(("127.0.0.1", port))
            break
        except OSError:
            port += 1
            
    # Write the actively bound port to a file so the C++ wrapper can dynamically locate Kiko's socket
    base_dir = os.path.dirname(os.path.abspath(__file__))
    port_file = os.path.join(base_dir, ".kiko_port")
    with open(port_file, "w") as f:
        f.write(str(port))
        
    sock.setblocking(False)
    
    while True:
        try:
            ready = select.select([sock], [], [], None)
            if not ready[0]:
                continue
                
            data, addr = sock.recvfrom(4096)
            error_msg = data.decode('utf-8', errors='ignore').strip()
            
            time.sleep(0.05)
            while True:
                ready = select.select([sock], [], [], 0.0)
                if ready[0]:
                    chunk, _ = sock.recvfrom(4096)
                    error_msg += " " + chunk.decode('utf-8', errors='ignore').strip()
                else:
                    break
            
            if error_msg:
                print(f"\n   [⚡ Kiko intercepted a terminal error! Analyzing...]")
                
                global client, model_name, config
                prompt = f"I just typed a bad command in my terminal and got this error:\n{error_msg}\nGive me a quick 1-sentence hint on how to fix it, and playfully roast me a little bit for making the typo! You are an anime girl assistant, keep it cute but sassy."
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                
                if response.text:
                    prompt_label = "\n> " if in_standby else "\nSenpai > "
                    # Print locally so Kiko's terminal updates too
                    print(f"\nKiko (Terminal Watcher - {tools.format_model_name(model_name)}): {response.text}{prompt_label}", end="", flush=True)
                    # Send the response back to the C++ shell's ephemeral port
                    sock.sendto(response.text.encode('utf-8'), addr)
                    
        except Exception as e:
            print(f"\n[Kiko Terminal Watcher Exception]: {e}")

def standby_watchdog_thread():
    # Inactivity watchdog that auto-triggers standby after STANDBY_TIMEOUT seconds of silence.
    # Checks every 10 seconds whether the user has been idle long enough.
    # Does NOT touch the thermal monitor — GPU/CPU temps are always watched.
    global in_standby, standby_start_time, last_activity_time, client, model_name, system_instruction
    
    while True:
        time.sleep(10)
        if not in_standby and (time.time() - last_activity_time) > STANDBY_TIMEOUT:
            in_standby = True
            standby_start_time = time.time()
            
            # Autonomously generate a cute sleepy message before entering standby
            sleepy_text = None
            try:
                auto_standby_prompt = (
                    "There has been no activity for a while and senpai seems away or busy. "
                    "Say a cute, 1-2 sentence message noting the lack of activity and that you are entering standby mode for now "
                    "(e.g. 'It seems like there isn't much activity here senpai, Kiko will enter standby mode for now... call me anytime!'). "
                    "Keep it sweet, in-character, and brief. Do not say sweet dreams."
                )
                resp = client.models.generate_content(
                    model=model_name,
                    contents=auto_standby_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                    )
                )
                if resp and resp.text:
                    sleepy_text = resp.text.strip()
            except Exception:
                sleepy_text = None
                
            if not sleepy_text:
                sleepy_text = "It seems like there isn't much activity right now, senpai... Kiko will enter standby mode for now! Just call me whenever you need me~ 💤✨"
                
            print(f"\n\nKiko ({tools.format_model_name(model_name)}): {sleepy_text}")
            print(f"   [💤 Kiko entered standby mode]")
            print(f"   [Press Enter or type anything to wake Kiko up!]")
            print(f"\n> ", end="", flush=True)
            enter_low_resource_standby()

def format_standby_duration(seconds):
    # Formats elapsed standby time into a human-readable string.
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        mins = int(seconds // 60)
        return f"{mins} minute{'s' if mins != 1 else ''}"
    else:
        hours = int(seconds // 3600)
        remaining_mins = int((seconds % 3600) // 60)
        if remaining_mins > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} and {remaining_mins} minute{'s' if remaining_mins != 1 else ''}"
        return f"{hours} hour{'s' if hours != 1 else ''}"

# Configure 64-bit Win32 prototypes for process priority and memory trimming.
# On 64-bit Windows, unconfigured ctypes defaults to 32-bit int, which truncates the
# 64-bit pseudo-handle (0xFFFFFFFFFFFFFFFF) returned by GetCurrentProcess() into a
# 32-bit integer, causing Win32 API calls to fail silently with ERROR_INVALID_HANDLE (6).
import ctypes
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

kernel32.GetCurrentProcess.restype = ctypes.c_void_p
kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
kernel32.SetPriorityClass.restype = ctypes.c_bool
psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
psapi.EmptyWorkingSet.restype = ctypes.c_bool

def enter_low_resource_standby():
    # Enters low-resource state: drops process priority to IDLE so background monitoring
    # does not compete for CPU cycles with foreground games/applications, runs a garbage
    # collection sweep, and forces the Windows Memory Manager to trim the physical RAM working set.
    import gc
    try:
        # IDLE_PRIORITY_CLASS = 0x00000040
        h_process = kernel32.GetCurrentProcess()
        kernel32.SetPriorityClass(h_process, 0x00000040)
        
        # Flush unreferenced objects from Python heap before trimming physical pages
        gc.collect()
        
        # EmptyWorkingSet flushes non-essential virtual pages from physical RAM
        psapi.EmptyWorkingSet(h_process)
    except Exception as e:
        print(f"   [⚠️ Warning: Failed to enter low-resource standby: {e}]")

def restore_normal_resources():
    # Restores process priority to NORMAL_PRIORITY_CLASS when waking up from standby.
    try:
        # NORMAL_PRIORITY_CLASS = 0x00000020
        h_process = kernel32.GetCurrentProcess()
        kernel32.SetPriorityClass(h_process, 0x00000020)
    except Exception as e:
        print(f"   [⚠️ Warning: Failed to restore normal process priority: {e}]")

def main():
    global chat, config, in_standby, standby_start_time, last_activity_time
    # boot the c++ hardware monitoring daemon silently in the background before aiko wakes up
    import subprocess
    
    # Kill any orphaned instances from previous script restarts before spawning a new one
    subprocess.run(["taskkill", "/F", "/IM", "cpu_monitor.exe"], capture_output=True)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    daemon_dir = os.path.join(base_dir, "tools", "cpu_monitor", "cpu_monitor", "x64", "Debug")
    daemon_path = os.path.join(daemon_dir, "cpu_monitor.exe")
    
    if os.path.exists(daemon_path):
        # devnull pipe prevents c++ runtime from crashing when std::cout is called without a console
        subprocess.Popen(
            [daemon_path], 
            creationflags=0x08000000, 
            cwd=daemon_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    # spin up the background thermal observer before blocking on chat
    monitor = threading.Thread(target=thermal_monitor_thread, daemon=True)
    monitor.start()

    terminal_watcher = threading.Thread(target=terminal_interceptor_thread, daemon=True)
    terminal_watcher.start()

    # Inactivity watchdog — auto-standby after STANDBY_TIMEOUT seconds of no input
    standby_watcher = threading.Thread(target=standby_watchdog_thread, daemon=True)
    standby_watcher.start()

    print(f"--- Kiko is waking up! ({tools.format_model_name(model_name)}) ---")
    print("(Type 'exit', 'quit' to terminate | 'standby', 'sleep' to nap)")
    
    current_time = datetime.datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S")
    # print(current_time)
    time_context = f"[Current System Time: {current_time}]\n"
    
    def send_with_fallback(prompt_text):
        global chat, model_name, current_model_index
        import time
        while True:
            try:
                resp = chat.send_message(prompt_text)
                return resp
            except Exception as e:
                err_str = str(e).lower()
                is_recoverable = any(term in err_str for term in [
                    "503", "500", "502", "504", "demand", "not found", "quota",
                    "429", "resource_exhausted", "internal", "server error",
                    "unavailable", "overloaded", "deadline", "timeout"
                ])
                if is_recoverable:
                    next_index = (current_model_index + 1) % len(model_fallback_chain)
                    next_model = model_fallback_chain[next_index]
                    print(f"   [⚠️ {tools.format_model_name(model_name)} failed ({e}). Falling back to {tools.format_model_name(next_model)}...]")
                    current_model_index = next_index
                    model_name = next_model
                    # Preserve conversation history across the fallback
                    history = None
                    try:
                        history = chat.get_history()
                    except Exception:
                        pass
                    chat = client.chats.create(model=model_name, config=config, history=history)
                    time.sleep(2)
                    continue
                else:
                    raise e

    # Initialize the session context with cross-session episodic continuity
    try:
        recent_interactions, last_interaction_ts = get_recent_interactions(limit=3)
        if recent_interactions and last_interaction_ts:
            time_elapsed_str = format_elapsed_time(last_interaction_ts)
            recent_convo_str = "\n---\n".join([item["content"] for item in recent_interactions])
            boot_prompt = (
                f"Kiko boots up and wakes up.\n"
                f"{time_context}"
                f"[Session Continuity: Kiko was last active with the user {time_elapsed_str}.]\n"
                f"[Context from the end of the previous session before Kiko was shut down / closed:\n"
                f"{recent_convo_str}\n]\n\n"
                f"Greet the user warmly and naturally! Acknowledge the time that has passed ({time_elapsed_str}) "
                f"and naturally reference or follow up on what you two were talking about last time if appropriate, like a caring companion!"
            )
        else:
            boot_prompt = f"Kiko boots up and looks at time: {time_context} before greeting"
            
        response = send_with_fallback(boot_prompt)
        print(f"\nKiko ({tools.format_model_name(model_name)}): {response.text}")
    except Exception as e:
        print(f"\n[Kiko encountered an error during boot]: {e}")
    
    while True:
        try:
            prompt_str = "\n> " if in_standby else "\nSenpai > "
            user_input = input(prompt_str)
            
            # Reset inactivity timer on any input (including empty Enter)
            last_activity_time = time.time()
            woke_from_standby = False
            wake_context = ""
            
            # Handle wake-up from standby mode
            if in_standby:
                restore_normal_resources()
                nap_duration = time.time() - standby_start_time
                nap_str = format_standby_duration(nap_duration)
                in_standby = False
                
                # Empty input or simple wake phrases — just wake up with a cute message
                wake_phrases = ['', 'wake up', 'hey', 'kiko', 'yo', 'oi', 'ohayo', 'morning']
                if user_input.strip().lower() in wake_phrases:
                    print("   [⚡ Kiko is waking up...]")
                    try:
                        wake_prompt = (
                            f"You just woke up from a {nap_str} nap/standby! "
                            f"The user woke you up. Stretch, yawn cutely, and greet them! "
                            f"Mention how long you napped ({nap_str})."
                        )
                        response = send_with_fallback(wake_prompt)
                        print(f"\nKiko ({tools.format_model_name(model_name)}): {response.text}")
                    except Exception as e:
                        print(f"\n   [💫 *yawns* Kiko is back after a {nap_str} nap!]")
                    continue
                else:
                    # User typed an actual command on wake — process it immediately
                    woke_from_standby = True
                    wake_context = f"[System notice: You just woke up from a {nap_str} nap/standby because the user gave you a new task. Acknowledge waking up briefly and cheerfully before executing the task!]\n"
                    print(f"   [💫 Kiko wakes up after a {nap_str} nap!]")
                    print("   [⚡ Kiko is thinking / executing...]")
            
            # Exit the loop if the user types 'exit' or 'quit'
            if user_input.lower() in ['exit', 'quit']:
                print("Matane, senpai! See you later!")
                break
            
            # Manual standby trigger
            if user_input.lower() in ['standby', 'sleep']:
                in_standby = True
                standby_start_time = time.time()
                print("   [💤 Kiko entered standby mode]")
                print("   [Press Enter or type anything to wake Kiko up!]")
                enter_low_resource_standby()
                continue
                
            # Clear short-term memory (context window) to free up token usage
            if user_input.lower() == 'clear':
                print("[System] Short-term memory wiped! The 'heavy backpack' is gone.")
                chat = client.chats.create(model=model_name, config=config)
                continue
            
            if not user_input.strip():
                continue
            
            # convert user_input into a vector embedding
            embedding_response = client.models.embed_content(
                model='gemini-embedding-2',
                contents=user_input
            )

            # retrieve the most similar vector memory to the query vector
            query_vector = embedding_response.embeddings[0].values

            # check semantic memory of user_input using hybrid recall (keyword + vector)
            memory_match = recall_semantic_memory(query_vector=query_vector, query_text=user_input)

            current_time = datetime.datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S")
            time_context = f"[Current System Time: {current_time}]\n"
            
            augmented_prompt = f"{time_context}{wake_context}{user_input}"
            if memory_match:
                # print(f"\n RAG Engine found a Cosine Similarity match.")
                # print(f" Context Injected: {memory_match}")
                augmented_prompt = f"{time_context}{wake_context}Context from past conversation:\n{memory_match}\n\nUser: {user_input}"

                
            # Indicate active processing to terminal (skip if already printed during wake-up)
            if not woke_from_standby:
                print("   [⚡ Kiko is thinking / executing...]")
            
            # The SDK handles function calling autonomously
            try:
                response = send_with_fallback(augmented_prompt)
            except Exception as e:
                print(f"\n[Kiko encountered an error]: {e}")
                continue
            
            if response.text:
                print(f"\nKiko ({tools.format_model_name(model_name)}): {response.text}")
                
                # embed and save the interaction memory
                interaction_log = f"User: {user_input}\nKiko: {response.text}"
                save_resp = client.models.embed_content(
                    model='gemini-embedding-2',
                    contents=interaction_log
                )
                save_vector_memory(interaction_log, save_resp.embeddings[0].values)
                # print(f"Interaction embedded and saved to SQLite: {interaction_log}")

            global needs_memory_clear
            if needs_memory_clear:
                print("   [🔧 System: Memory Cleared by Kiko's Request to save API Tokens]")
                chat = client.chats.create(model=model_name, config=config)
                needs_memory_clear = False

            global needs_standby
            if needs_standby:
                in_standby = True
                standby_start_time = time.time()
                print("\n   [💤 Kiko entered standby mode]")
                print("   [Press Enter or type anything to wake Kiko up!]")
                enter_low_resource_standby()
                needs_standby = False

            global needs_system_reload
            if needs_system_reload:
                print("   [🔧 System: Hot-Reloading Tool Modules from Disk...]")
                import importlib
                
                # Reload all submodules inside 'tools' first
                for mod_name, mod in list(sys.modules.items()):
                    if mod_name.startswith('tools.') and mod is not None:
                        try:
                            importlib.reload(mod)
                        except Exception as e:
                            print(f"   [⚠️ Warning: Failed to reload {mod_name}: {e}]")
                
                # Reload the main tools package
                importlib.reload(sys.modules['tools'])
                
                # Rebuild the available_tools array with the fresh memory pointers
                available_tools = [getattr(sys.modules['tools'], func_name) for func_name in sys.modules['tools'].__all__]
                available_tools.extend([clear_short_term_memory, reload_core_systems, enter_standby_mode])
                
                # Update the gemini config and recreate the chat session preserving history
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction + f"\nYour preferences are: {memories_str}",
                    tools=available_tools,
                    temperature=0.7,
                )
                existing_history = None
                try:
                    existing_history = chat.get_history()
                except Exception:
                    pass
                chat = client.chats.create(model=model_name, config=config, history=existing_history)
                
                print("   [🔧 System: Modules successfully hot-swapped!]")
                needs_system_reload = False

        except KeyboardInterrupt:
            # Handle Ctrl+C termination
            print("\nArigato senpai >_< Matane!")
            break
        except Exception as e:
            print(f"\n[Kiko encountered an error]: {e}")

if __name__ == "__main__":
    main()
