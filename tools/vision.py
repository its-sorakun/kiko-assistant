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
        # 1. Attempt DXGI Capture
        subprocess.run([capture_tool, output_bmp], capture_output=True, text=True, check=True)
        if os.path.exists(output_bmp):
            img = Image.open(output_bmp)
            
            # Heuristic: Check if the DXGI capture is a solid black screen (MPO / Anti-Cheat blocking)
            from PIL import ImageStat
            stat = ImageStat.Stat(img)
            # If the average pixel value across RGB is extremely close to 0, it's essentially pitch black
            if sum(stat.mean[:3]) < 1.0:
                print(f"   [⚠️ DXGI returned a black screen (MPO/Anti-Cheat). Falling back to GDI BitBlt...]")
                use_gdi_fallback = True
        else:
            use_gdi_fallback = True

    except subprocess.CalledProcessError:
        print(f"   [⚠️ DXGI capture failed. Falling back to GDI BitBlt...]")
        use_gdi_fallback = True

    if use_gdi_fallback or img is None:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True)
        
    try:
        # Send to the lightweight vision model
        # The user requested gemini-3.5-flash-lite
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=[prompt, img]
        )
        
        return f"Vision Analysis Result:\n{response.text}"
        
    except Exception as e:
        return f"Error analyzing screen: {str(e)}"
