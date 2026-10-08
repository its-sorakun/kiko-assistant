import sys
import os
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import time

# Ensure Kiko's tools are accessible
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from tools.memory import get_chat_sessions, get_chat_messages, create_chat_session, save_chat_message

app = FastAPI()

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the web UI statically
ui_dir = os.path.join(os.path.dirname(__file__), "ui")
if not os.path.exists(ui_dir):
    os.makedirs(ui_dir)

app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")

@app.get("/")
async def root():
    # Redirect root to the UI
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url='/ui/index.html')

@app.get("/api/sessions")
async def fetch_sessions():
    """Retrieve all chat sessions from SQLite for the sidebar."""
    return get_chat_sessions()

@app.get("/api/sessions/{session_id}")
async def fetch_session_messages(session_id: int):
    """Retrieve all messages for a given session."""
    return get_chat_messages(session_id)

@app.post("/api/sessions")
async def new_session():
    """Create a new chat session."""
    session_id = create_chat_session(f"Arc {time.strftime('%Y-%m-%d %H:%M')}")
    return {"id": session_id}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: int):
    await websocket.accept()
    try:
        while True:
            # Receive message from frontend
            data = await websocket.receive_text()
            user_msg = data
            
            # Save user message to SQLite
            save_chat_message(session_id, "user", user_msg)
            
            # TODO: Integrate with Gemini / main Kiko logic here.
            # For now, echo back to establish the architecture structure.
            
            # Example tool execution block (Transparency!)
            await websocket.send_json({
                "type": "tool_execution",
                "tool": "mft_search",
                "status": "running"
            })
            
            time.sleep(1) # Simulate tool run
            
            await websocket.send_json({
                "type": "tool_execution",
                "tool": "mft_search",
                "status": "completed",
                "result": "Found 3 files."
            })
            
            # Example text streaming
            response_text = f"Senpai, you said: '{user_msg}'. I am currently running on the FastAPI backend! My Gemini core hasn't been connected to this websocket route yet, but my architecture is ready!"
            
            # Stream the response back token by token (simulation)
            for word in response_text.split(" "):
                await websocket.send_json({
                    "type": "token",
                    "content": word + " "
                })
                time.sleep(0.05)
                
            # Signal completion
            await websocket.send_json({
                "type": "done"
            })
            
            # Save Kiko's final message to SQLite
            save_chat_message(session_id, "assistant", response_text)

    except WebSocketDisconnect:
        print(f"Client disconnected from session {session_id}")

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
