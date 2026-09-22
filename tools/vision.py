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
    Captures the current frame buffer of the screen (using DXGI Desktop Duplication)
    and passes it to a vision LLM alongside your prompt.
    Use this to "look" at the user's screen when they ask for help in a game or want you to see something visually.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    capture_tool = os.path.join(base_dir, "tools", "dxgi_capture", "dxgi_capture.exe")
    output_bmp = os.path.join(base_dir, "scratch", "screenshot.bmp")

    print(f"\n   [👀 Kiko is looking at the screen natively via DXGI...]")
    
    try:
        # Run the C++ capture tool
        subprocess.run([capture_tool, output_bmp], capture_output=True, text=True, check=True)
        
        if not os.path.exists(output_bmp):
            return "Error: Could not capture the screen. The C++ tool failed to generate the BMP."
            
        # Load the image
        img = Image.open(output_bmp)
        
        # Send to the lightweight vision model
        # The user requested gemini-3.5-flash-lite
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=[prompt, img]
        )
        
        return f"Vision Analysis Result:\n{response.text}"
        
    except subprocess.CalledProcessError as e:
        return f"Error executing DXGI capture: {e.stderr}"
    except Exception as e:
        return f"Error analyzing screen: {str(e)}"
