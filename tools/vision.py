# tools/vision.py - Multimodal frame buffer capture and vision model inference
# Implementation details:
# Interfaces with the DXGI screen capture daemon, captures Windows desktop frames via IPC shared memory,
# extracts local image files, and coordinates Gemini multimodal vision queries with model fallbacks and timeouts.

import subprocess
import os
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key, http_options={'timeout': 15000})

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

    # Downscale multi-monitor / ultra-high-resolution screen captures if exceeding 2560px
    if img and (img.width > 2560 or img.height > 2560):
        img.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
        
    try:
        fallback_chain = [
            'gemini-3.5-flash-lite',
            'gemini-3.5-flash',
            'gemini-3.6-flash',
            'gemini-3.1-flash-lite',
        ]
        response = None
        
        for m in fallback_chain:
            try:
                chat = client.chats.create(model=m)
                response = chat.send_message([prompt, img])
                break # Success
            except Exception as e:
                err_str = str(e).lower()
                is_recoverable = any(term in err_str for term in [
                    "503", "500", "502", "504", "demand", "not found", "quota",
                    "429", "resource_exhausted", "internal", "server error",
                    "unavailable", "overloaded", "deadline", "timeout"
                ])
                if is_recoverable:
                    reason = "quota / demand limit" if ("quota" in err_str or "429" in err_str or "demand" in err_str) else "transient error"
                    print(f"   [⚠️ {m} hit {reason}. Falling back...]")
                    continue
                else:
                    return f"Error analyzing screen: {str(e)}"
                    
        if not response:
            return "Error: All models in the fallback chain are experiencing high demand or are unavailable."
            
        return f"Vision Analysis Result:\n{response.text}"
        
    except Exception as e:
        return f"Error analyzing screen: {str(e)}"

def analyze_image(image_path: str, prompt: str = "Analyze and describe this image in detail.") -> str:
    """
    Analyzes an image file on disk and passes it to a vision LLM alongside the prompt.
    Use this when an image file or attachment is provided or referenced.
    """
    try:
        image_path = image_path.strip('\'"')
        if not os.path.isabs(image_path):
            image_path = os.path.abspath(image_path)

        if not os.path.exists(image_path):
            return f"Error: Image file not found at {image_path}"
            
        print(f"\n   [🖼️ Kiko is inspecting image: {os.path.basename(image_path)}...]")
        img = Image.open(image_path)
        
        # Optimize oversized images to prevent network upload saturation and socket timeouts
        max_dimension = 2048
        if img.width > max_dimension or img.height > max_dimension:
            orig_size = (img.width, img.height)
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            print(f"   [⚡ Downscaled oversized image from {orig_size[0]}x{orig_size[1]} to {img.width}x{img.height} for rapid API inference]")

        fallback_chain = [
            'gemini-3.5-flash-lite',
            'gemini-3.5-flash',
            'gemini-3.6-flash',
            'gemini-3.1-flash-lite',
        ]
        response = None
        
        for m in fallback_chain:
            try:
                chat = client.chats.create(model=m)
                response = chat.send_message([prompt, img])
                break # Success
            except Exception as e:
                err_str = str(e).lower()
                is_recoverable = any(term in err_str for term in [
                    "503", "500", "502", "504", "demand", "not found", "quota",
                    "429", "resource_exhausted", "internal", "server error",
                    "unavailable", "overloaded", "deadline", "timeout"
                ])
                if is_recoverable:
                    reason = "quota / demand limit" if ("quota" in err_str or "429" in err_str or "demand" in err_str) else "transient error"
                    print(f"   [⚠️ {m} hit {reason}. Falling back...]")
                    continue
                else:
                    return f"Error analyzing image: {str(e)}"
                    
        if not response:
            return "Error: All models in the fallback chain are experiencing high demand or are unavailable."
            
        return f"Image Analysis Result:\n{response.text}"
        
    except Exception as e:
        return f"Error analyzing image: {str(e)}"
