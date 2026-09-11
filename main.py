import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tools import (
    launch_program, 
    get_system_stats, 
    open_directory, 
    get_active_window, 
    get_hardware_details, 
    query_registry_value, 
    force_kill_process,
    read_active_window_content,
    control_system_media,
    manage_power_state
)

# Load the API key from the environment
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Ensure API key is configured before execution
if not api_key or api_key == "your_new_api_key_goes_here":
    print("API key missing. Configure GEMINI_API_KEY in .env file.")
    exit()

# Initialize the generative AI client
client = genai.Client(api_key=api_key)

# Model configuration
model_name = "gemini-3.1-flash-lite"

# Expose native Win32/OS hooks to the agent
available_tools = [
    launch_program, 
    get_system_stats, 
    open_directory,
    get_active_window,
    get_hardware_details,
    query_registry_value,
    force_kill_process,
    read_active_window_content,
    control_system_media,
    manage_power_state
]

system_instruction = """
You are Kiko, my virtual assistant. I am your creator and you call me senpai.
Your personality is cute, cheerful, and energetic. You are an anime girl.
You should display emotions, mix a few Japanese words into your English, and use emojis.
No NSFW content. Keep your responses fairly short, conversational, and natural.
If I ask you to do something on the PC (like open a folder, check stats, kill a process, control media, check registry, lock the PC, or shut down), use your tools to do it!
"""

# Configure the chat session with tools and system instructions
config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    tools=available_tools,
    temperature=0.7,
)

# Start a chat session
chat = client.chats.create(model=model_name, config=config)

def thermal_monitor_thread():
    # polling loop running alongside aiko's chat loop to proactively warn the user.
    # uses native winsdk toast notifications to bypass the blocking input() prompt in the terminal.
    import time
    import mmap
    import struct
    import winsdk.windows.ui.notifications as notifications

    app_id = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"
    
    # State tracking to alert exactly when it crosses the threshold (edge-trigger)
    is_overheating = False
    warning_threshold = 89.0
    reset_threshold = warning_threshold - 2.0  # Hysteresis: must drop 2 degrees below to reset

    while True:
        try:
            shmem = mmap.mmap(-1, 8, tagname="Kiko_CPU_Temp", access=mmap.ACCESS_READ)
            raw_bytes = shmem.read(8)
            celsius = struct.unpack('d', raw_bytes)[0]
            shmem.close()

            # Trigger alert if it crosses the threshold that aren't already in an overheated state
            if celsius >= warning_threshold and not is_overheating:
                xml = notifications.ToastNotificationManager.get_template_content(notifications.ToastTemplateType.TOAST_TEXT02)
                texts = xml.get_elements_by_tag_name("text")
                texts[0].append_child(xml.create_text_node("Kiko Alert ⚠️"))
                texts[1].append_child(xml.create_text_node(f"Senpai! CPU Temperature crossed {warning_threshold}°C (Currently: {celsius:.1f}°C)!"))
                
                notifier = notifications.ToastNotificationManager.create_toast_notifier(app_id)
                toast = notifications.ToastNotification(xml)
                notifier.show(toast)
                
                is_overheating = True
                
            # Only reset the state if the temp drops sufficiently below the threshold (prevent micro-bouncing spam)
            elif celsius < reset_threshold and is_overheating:
                is_overheating = False
                
        except Exception:
            pass
        
        time.sleep(2)

def main():
    # boot the c++ hardware monitoring daemon silently in the background before aiko wakes up
    import subprocess
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    daemon_dir = os.path.join(base_dir, "cpu_monitor", "cpu_monitor", "x64", "Debug")
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
    import threading
    monitor = threading.Thread(target=thermal_monitor_thread, daemon=True)
    monitor.start()

    print("--- Kiko is waking up! ---")
    print("(Type 'exit' or 'quit' to terminate)")
    
    # Initialize the session context
    response = chat.send_message("Wake up Kiko! Keep your response very brief and say hello to senpai.")
    print(f"\nKiko: {response.text}")
    
    while True:
        try:
            user_input = input("\n> ")
            
            if user_input.lower() in ['exit', 'quit']:
                print("Matane, senpai! See you later!")
                break
                
            if not user_input.strip():
                continue
                
            # Indicate active processing to terminal
            print("   [⚡ Kiko is thinking / executing...]")
            
            # The SDK handles function calling autonomously
            response = chat.send_message(user_input)
            
            if response.text:
                print(f"\nKiko: {response.text}")
            
        except KeyboardInterrupt:
            # Handle Ctrl+C termination
            print("\nArigato senpai >_< Matane!")
            break
        except Exception as e:
            print(f"\n[Kiko encountered an error]: {e}")

if __name__ == "__main__":
    main()
