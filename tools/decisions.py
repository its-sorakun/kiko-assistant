# tools/decisions.py - Zero-token structured decision and routing engine using Gemini Decision 1
# Implementation details:
# Interfaces with Google's gemini-decision-1 model via the Decisions API (v1beta) to evaluate
# closed-set questions (binary noul, multiple-choice, or rubric scores) in a single pass.
# Bypasses text generation entirely, returning calibrated outcome probabilities with zero output token usage.

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Lazy client initialization to avoid unnecessary network calls on module import
_decisions_client = None

def get_decisions_client():
    """
    Returns a configured google.genai Client targeting the v1beta endpoint required by Decisions API.
    Reuses the client instance across requests.
    """
    global _decisions_client
    if _decisions_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_new_api_key_goes_here":
            raise ValueError("GEMINI_API_KEY is not configured in .env")
        _decisions_client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    return _decisions_client

# Default subsystem routing criteria mapped to Kiko's tool clusters
DEFAULT_ROUTING_CRITERIA = {
    "casual_chat": "Normal conversation, chit-chat, greetings, feelings, anime, or questions requiring no tool execution.",
    "spotify_music": "Playing, pausing, searching, controlling, or queuing music and playlists on Spotify.",
    "weather": "Inquiries about weather conditions, temperature, rain warnings, or forecasts.",
    "system_hardware": "Checking CPU usage, GPU temperature, RAM consumption, or hardware specs.",
    "window_screen": "Inspecting active window content, memory dump reading, or analyzing the visual screen.",
    "file_process": "Launching programs, killing processes, checking network ports, opening folders, or finding files.",
    "power_standby": "Commands to sleep, nap, enter standby mode, lock the PC, or shut down.",
    "web_research": "Real-world facts, current events, recent anime/movie releases, web searches, or PDF queries.",
    "notes_tasks": "Viewing, creating, updating, or deleting notes and to-dos in the local notes app."
}

def route_intent(user_input: str, custom_criteria: dict = None) -> dict:
    """
    Routes a user's prompt to the most relevant subsystem using gemini-decision-1.
    Returns a dictionary with:
      - 'choice': The selected category key
      - 'confidence': Model confidence score (0.0 to 1.0)
      - 'probabilities': Normalized probability distribution across all categories
      - 'total_input_tokens': Billed input token count (output tokens are always 0)
    """
    client = get_decisions_client()
    criteria = custom_criteria if custom_criteria is not None else DEFAULT_ROUTING_CRITERIA

    try:
        response = client.decisions.create(
            model="gemini-decision-1",
            input=user_input,
            questions={
                "target_subsystem": {
                    "type": "choice",
                    "instructions": "Which subsystem is best suited to handle this user prompt?",
                    "criteria": criteria
                }
            }
        )
        answer = response.answers.get("target_subsystem")
        if not answer:
            return {"choice": "casual_chat", "confidence": 0.0, "probabilities": {}, "error": "No answer returned"}
        
        return {
            "choice": answer.choice,
            "confidence": float(answer.confidence) if answer.confidence is not None else 0.0,
            "probabilities": {k: float(v) for k, v in (answer.probabilities or {}).items()},
            "total_input_tokens": getattr(response.usage, "total_input_tokens", 0)
        }
    except Exception as e:
        # Fall back gracefully so an API hiccup never breaks user interaction
        return {
            "choice": "casual_chat",
            "confidence": 0.0,
            "probabilities": {},
            "error": str(e)
        }

def evaluate_condition(input_text: str, question: str) -> tuple[bool, float]:
    """
    Evaluates a binary Yes/No question against an input string using a 'noul' question.
    Returns (is_true, probability).
    """
    client = get_decisions_client()
    try:
        response = client.decisions.create(
            model="gemini-decision-1",
            input=input_text,
            questions={
                "check": {
                    "type": "noul",
                    "instructions": question
                }
            }
        )
        answer = response.answers.get("check")
        if not answer:
            return (False, 0.0)
        
        prob = float(answer.noul) if hasattr(answer, "noul") and answer.noul is not None else 0.0
        return (prob >= 0.5, prob)
    except Exception:
        return (False, 0.0)

def evaluate_batch(input_text: str, questions_dict: dict) -> dict:
    """
    Evaluates multiple questions (noul, choice, score) in parallel against a single input.
    Input data is only billed once across all questions.
    """
    client = get_decisions_client()
    try:
        response = client.decisions.create(
            model="gemini-decision-1",
            input=input_text,
            questions=questions_dict
        )
        return {k: v for k, v in response.answers.items()}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Diagnostic test harness and latency benchmark
    import time
    
    test_queries = [
        "Can you play some synthwave on Spotify?",
        "Is it going to rain in Tokyo today?",
        "Why is my CPU running so hot right now?",
        "Hey Kiko, how are you feeling today?",
        "You can go to sleep now, Kiko. Good night!",
        "Kill the process on port 3000",
        "Who won the latest Formula 1 Grand Prix?"
    ]
    
    print("=== Testing Gemini Decisions API (gemini-decision-1) ===")
    for q in test_queries:
        t0 = time.time()
        res = route_intent(q)
        elapsed_ms = (time.time() - t0) * 1000
        choice = res.get("choice")
        conf = res.get("confidence", 0.0)
        tokens = res.get("total_input_tokens", 0)
        print(f"[{elapsed_ms:.0f}ms] '{q}'")
        print(f"   -> Category: {choice} (conf: {conf:.2%}, tokens: {tokens})\n")

