# Copyright (C) 2026 its-sorakun
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import subprocess
import os
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def analyze_screen(prompt: str) -> str:
    """
    Captures the current frame buffer of the screen and passes it to a vision LLM alongside your prompt.
    It natively uses DXGI Desktop Duplication, but features a dynamic heuristic to fallback to GDI BitBlt
    if it detects an MPO or Anti-Cheat black screen.
    Use this to "look" at the user's screen when they ask for help in a game or want you to see something visually.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    capture_tool = os.path.join(base_dir, "tools", "dxgi_capture", "dxgi_capture.exe")
    output_bmp = os.path.join(base_dir, "scratch", "screenshot.bmp")

    print(f"\n   [👀 Kiko is trying to look at the screen natively via DXGI...]")
    
    img = None
    use_gdi_fallback = False

    try:
        import mmap
        import struct

        # Allocate 35MB to safely fit uncompressed 4K/Ultra-Wide raw frames.
        MAX_SIZE = 35 * 1024 * 1024 
        map_name = "Local\\KikoDXGIFrame"

        # Passing -1 forces Windows to allocate the mapping in the system page file (RAM) instead of tracking a physical file.
        shm = mmap.mmap(-1, MAX_SIZE, tagname=map_name, access=mmap.ACCESS_WRITE)

        # Spawning the capture tool inherits this memory mapping. The OS keeps the block alive as long as this handle remains open.
        subprocess.run([capture_tool, map_name], capture_output=True, text=True, check=True)
        
        shm.seek(0)
        
        # The C++ tool writes the display dimensions at the 0x0 offset before dumping the raw buffer.
        width, height = struct.unpack('ii', shm.read(8))
        
        pixel_size = width * height * 4
        raw_pixels = shm.read(pixel_size)
        
        # Reconstruct the physical pixel grid natively without incurring SSD I/O.
        img = Image.frombytes("RGBA", (width, height), raw_pixels, "raw", "BGRA")
        
        # Heuristic: Check if the DXGI capture is a solid black screen (MPO / Anti-Cheat blocking)
        from PIL import ImageStat
        stat = ImageStat.Stat(img)
        
        # If the average pixel value across RGB is extremely close to 0, it's essentially pitch black
        if sum(stat.mean[:3]) < 1.0:
            print(f"   [⚠️ DXGI returned a black screen (MPO/Anti-Cheat). Falling back to GDI BitBlt...]")
            use_gdi_fallback = True

    except subprocess.CalledProcessError:
        print(f"   [⚠️ DXGI capture failed. Falling back to GDI BitBlt...]")
        use_gdi_fallback = True

    if use_gdi_fallback or img is None:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True)
        
    try:
        fallback_chain = ['gemini-3.5-flash-lite','gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.1-pro', 'gemini-3.1-flash-lite']
        response = None
        
        for m in fallback_chain:
            try:
                chat = client.chats.create(model=m)
                response = chat.send_message([prompt, img])
                break # Success
            except Exception as e:
                err_str = str(e).lower()
                if "503" in err_str or "demand" in err_str or "not found" in err_str:
                    print(f"   [⚠️ {m} failed (High Demand/Unavailable). Falling back...]")
                    continue
                else:
                    return f"Error analyzing screen: {str(e)}"
                    
        if not response:
            return "Error: All models in the fallback chain are experiencing high demand or are unavailable."
            
        return f"Vision Analysis Result:\n{response.text}"
        
    except Exception as e:
        return f"Error analyzing screen: {str(e)}"
