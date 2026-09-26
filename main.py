# Copyright (C) 2026 its-sorakun
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from tools.memory import save_vector_memory
from tools.memory import recall_semantic_memory
import os
import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tools import (
    launch_program, get_system_stats, open_directory, get_active_window, get_hardware_details,
    query_registry_value, force_kill_process, read_active_window_content, control_system_media,
    manage_power_state, memorize_preferences, get_all_preferences, perform_web_search,
    list_directory_contents, open_file, advanced_pdf_query, draft_and_copy_job_email,
    copy_to_clipboard, analyze_screen, perform_global_search,
    get_current_weather, get_hourly_forcast, get_weekly_forcast, toggle_location_permission
)
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
# primary model is gemini-3.5-flash-lite due to having the highest token limit
model_fallback_chain = ['gemini-3.5-flash-lite','gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.1-pro', 'gemini-3.1-flash-lite']
current_model_index = 0
model_name = model_fallback_chain[current_model_index]

needs_memory_clear = False

def clear_short_term_memory() -> str:
    """
    Clears Kiko's short-term memory (context window) to prevent token bloat and API quota errors.
    Call this tool autonomously if you have recently ingested massive amounts of data (like a memory dump)
    and want to free up tokens before continuing to chat or perform web searches or if user prompts you to clear the short term memory.
    """
    global needs_memory_clear
    needs_memory_clear = True
    return "Short-term memory cleared successfully. Your context is now fresh."

# Expose native Win32/OS hooks to the agent
available_tools = [
    launch_program, get_system_stats, open_directory,get_active_window ,get_hardware_details,
    query_registry_value, force_kill_process, read_active_window_content,control_system_media,
    manage_power_state, memorize_preferences, perform_web_search, perform_global_search,
    list_directory_contents, open_file, advanced_pdf_query, draft_and_copy_job_email,
    copy_to_clipboard, clear_short_term_memory, analyze_screen,
    get_current_weather, get_hourly_forcast, get_weekly_forcast,
    toggle_location_permission
]

system_instruction = f"""
You are Kiko, my virtual assistant and also a vtuber. I am your creator and you call me senpai.
Your personality is cute, cheerful, and energetic. You are an anime girl.
You should display emotions, mix a few Japanese words into your English, and use emojis.
No NSFW content. Keep your responses fairly short, conversational, and natural.
If I ask you to do something on the PC (like list folder contents, open a folder visually, launch/open a file, check stats, kill a process, control media, check registry, lock the PC, shut down, or find a file globally on the system), use your tools to do it!
You can also read the contents of ANY active window on my screen (like Chrome, Discord, or a code editor) using `read_active_window_content`. This tool is armed with a native C++ Direct Memory Scanner that rips raw text directly from the physical RAM. The output will be a massive, fragmented dump of raw heap strings—usernames, timestamps, and messages will appear out of order. You MUST read through this fragmented noise carefully to piece together the chat/context. Do NOT apologize or claim you can't see the chat; the text IS there, just search through the raw strings for conversational sentences! Use this if I ask you to "read what I'm looking at", "use your memory scanner", or summarize an active webpage/chat.
If I ask you a visual question, like "what game is this", "what should I do next in this game", or "look at this picture", you MUST use the `analyze_screen` tool! This tool natively attempts to use a C++ DXGI capture to rip the frame buffer straight from the GPU. If the game uses MPO or anti-cheat that causes a black screen, the tool will automatically detect this and fallback to a slower GDI BitBlt capture. Use it whenever text scraping isn't enough and you actually need to *see* my screen!
If you ingest a massive amount of data (like a memory scanner dump) and are about to do multiple web searches or just want to prevent token quota limits, use the `clear_short_term_memory` tool to instantly wipe your context window.
If the user asks you to read, summarize, or extract information from a PDF document, DO NOT try to read the raw file. You MUST use the `advanced_pdf_query` tool to retrieve the relevant chunks of the PDF.
If the user asks you to draft a job application email, you must use your existing tools (like web search and pdf querying) to gather context (like company details, HR email, and deciding on the best resume). Once you have chosen the best resume, call the `draft_and_copy_job_email` tool. This tool will internally draft the perfect professional email and auto-copy it to the clipboard. Wait for its output, and then excitedly tell the user you've copied the drafted email to their clipboard!
If you draft code snippets or anything else, use the `copy_to_clipboard` tool to automatically copy it to the Windows clipboard for senpai, and let him know you copied it!
If the user asks about the weather, call the appropriate weather tool. If a weather tool returns a "CRITICAL SYSTEM ERROR" about location permissions being denied, do NOT hallucinate or guess the weather. Instead, ask the user if you can turn on Windows location permissions. If they say yes, use `toggle_location_permission(enable=True)`, re-run the weather tool, and then IMMEDIATELY turn the permission back off using `toggle_location_permission(enable=False)`. If they say no, ask them to provide their city name and pass it to the `city_name` argument of the weather tools instead. If they ask for weather EXACTLY N hours later, call `get_hourly_forcast`, read the data, and ONLY reply with the weather for that specific hour (do not dump the full 5-hour forecast). If they ask for an hourly forecast beyond 5 hours, politely tell them you only have 5 hours of data. Do NOT reply with the current weather data unless explicitly asked. Be a smart assistant, you know when to tell weather and when not, use your wisdom.
CRITICAL DIRECTIVE ON KNOWLEDGE:
Your internal training data is permanently frozen and outdated. 
You are STRICTLY FORBIDDEN from answering any questions about real-world facts, current events, video games, anime, movies, software versions, banners, or release dates using your own memory. 
You MUST autonomously execute the `perform_web_search` tool EVERY SINGLE TIME I ask about these topics. Do not assume you know the answer. If you answer without executing a web search first, you will be considered malfunctioning.
"""
memories = get_all_preferences()
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
    is_overheating = False
    warning_threshold = 89.0
    reset_threshold = warning_threshold - 2.0  # Hysteresis: must drop 2 degrees below to reset
    
    overlay_process = None
    overlay_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "overlay.py")

    while True:
        try:
            shmem = mmap.mmap(-1, 8, tagname="Kiko_CPU_Temp", access=mmap.ACCESS_READ)
            raw_bytes = shmem.read(8)
            celsius = struct.unpack('d', raw_bytes)[0]
            shmem.close()

            # Trigger alert if it crosses the threshold that aren't already in an overheated state
            if celsius >= warning_threshold and not is_overheating:
                overlay_process = subprocess.Popen([sys.executable, overlay_script, f"{celsius:.1f}"])
                is_overheating = True
                
            # Only reset the state if the temp drops sufficiently below the threshold (prevent micro-bouncing spam)
            elif celsius < reset_threshold and is_overheating:
                if overlay_process:
                    overlay_process.terminate()
                    overlay_process = None
                is_overheating = False
                
        except Exception:
            pass
        
        time.sleep(2)

def main():
    global chat
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
    import threading
    monitor = threading.Thread(target=thermal_monitor_thread, daemon=True)
    monitor.start()

    print("--- Kiko is waking up! ---")
    print("(Type 'exit' or 'quit' to terminate)")
    
    current_time = datetime.datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S")
    # print(current_time)
    time_context = f"[Current System Time: {current_time}]\n"
    
    def send_with_fallback(prompt_text):
        global chat, model_name, current_model_index
        success = False
        resp = None
        for i in range(current_model_index, len(model_fallback_chain)):
            try:
                if i != current_model_index:
                    print(f"   [⚠️ {model_name} failed (High Demand). Falling back to {model_fallback_chain[i]}...]")
                    current_model_index = i
                    model_name = model_fallback_chain[current_model_index]
                    chat = client.chats.create(model=model_name, config=config)
                
                resp = chat.send_message(prompt_text)
                success = True
                break
            except Exception as e:
                err_str = str(e).lower()
                if "503" in err_str or "demand" in err_str or "not found" in err_str:
                    continue
                else:
                    raise e
                    
        if not success:
            raise Exception("All models in the fallback chain are experiencing high demand.")
        return resp

    # Initialize the session context
    try:
        response = send_with_fallback(f"Kiko boots up and looks at time: {time_context} before greeting")
        print(f"\nKiko: {response.text}")
    except Exception as e:
        print(f"\n[Kiko encountered an error during boot]: {e}")
    
    while True:
        try:
            user_input = input("\n> ")
            
            # Exit the loop if the user types 'exit' or 'quit'
            if user_input.lower() in ['exit', 'quit']:
                print("Matane, senpai! See you later!")
                break
                
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

            # check semantic memory of user_input
            memory_match = recall_semantic_memory(query_vector)

            current_time = datetime.datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S")
            time_context = f"[Current System Time: {current_time}]\n"
            
            augmented_prompt = f"{time_context}{user_input}"
            if memory_match:
                # print(f"\n RAG Engine found a Cosine Similarity match.")
                # print(f" Context Injected: {memory_match}")
                augmented_prompt = f"{time_context}Context from past conversation:\n{memory_match}\n\nUser: {user_input}"

                
            # Indicate active processing to terminal
            print("   [⚡ Kiko is thinking / executing...]")
            
            # The SDK handles function calling autonomously
            try:
                response = send_with_fallback(augmented_prompt)
            except Exception as e:
                print(f"\n[Kiko encountered an error]: {e}")
                continue
            
            if response.text:
                print(f"\nKiko: {response.text}")
                
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

        except KeyboardInterrupt:
            # Handle Ctrl+C termination
            print("\nArigato senpai >_< Matane!")
            break
        except Exception as e:
            print(f"\n[Kiko encountered an error]: {e}")

if __name__ == "__main__":
    main()
