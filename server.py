import sys
import os
# pyrefly: ignore [missing-import]
import uvicorn
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
import time

# Ensure Kiko's tools are accessible
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from tools.memory import get_chat_sessions, get_chat_messages, create_chat_session, save_chat_message, delete_chat_session

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

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int):
    """Delete a chat session and its messages."""
    delete_chat_session(session_id)
    return {"status": "success"}

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

            # Fetch past session history for Gemini context
            past_messages = get_chat_messages(session_id)
            history = []
            from google.genai import types
            for msg in past_messages:
                # We skip the very last message since we just saved it and will pass it as the prompt
                if msg == past_messages[-1]: continue
                
                if msg['role'] == 'tool_execution':
                    continue
                    
                role = 'user' if msg['role'] == 'user' else 'model'
                history.append(types.Content(role=role, parts=[types.Part.from_text(text=msg['content'])]))

            # Import Kiko's brain
            import main
            import datetime
            
            # Send a "Thinking..." status
            await websocket.send_json({
                "type": "status",
                "message": "Kiko is thinking...",
                "status": "running"
            })
            
            try:
                # Vector Search for semantic memory
                embedding_response = main.client.models.embed_content(
                    model='gemini-embedding-2',
                    contents=user_msg
                )
                query_vector = embedding_response.embeddings[0].values
                from tools.memory import recall_semantic_memory, save_vector_memory
                memory_match = recall_semantic_memory(query_vector)

                current_time = datetime.datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S")
                time_context = f"[Current System Time: {current_time}]\n"
                
                augmented_prompt = f"{time_context}{user_msg}"
                if memory_match:
                    augmented_prompt = f"{time_context}Context from past conversation:\n{memory_match}\n\nUser: {user_msg}"

                import asyncio
                
                full_response_text = ""
                
                while True:
                    try:
                        # Create async chat session with history
                        chat = main.client.aio.chats.create(model=main.model_name, config=main.config, history=history)
                        
                        # Stream the response
                        response_stream = await chat.send_message_stream(augmented_prompt)
                        
                        iterator = response_stream.__aiter__()
                        first_chunk = await iterator.__anext__()
                        
                        # Clear the loader now that we successfully got the first token
                        await websocket.send_json({
                            "type": "status",
                            "message": "Kiko is thinking...",
                            "status": "completed"
                        })
                        
                        if getattr(first_chunk, 'function_calls', None):
                            for fc in getattr(first_chunk, 'function_calls', []):
                                save_chat_message(session_id, "tool_execution", fc.name)
                                await websocket.send_json({
                                    "type": "tool_execution",
                                    "tool": fc.name,
                                    "status": "running"
                                })
                                
                        if getattr(first_chunk, 'text', None):
                            await websocket.send_json({"type": "tool_execution", "status": "completed"})
                            full_response_text += getattr(first_chunk, 'text')
                            await websocket.send_json({"type": "token", "content": getattr(first_chunk, 'text')})
                            
                        async for chunk in iterator:
                            if getattr(chunk, 'function_calls', None):
                                for fc in getattr(chunk, 'function_calls', []):
                                    save_chat_message(session_id, "tool_execution", fc.name)
                                    await websocket.send_json({
                                        "type": "tool_execution",
                                        "tool": fc.name,
                                        "status": "running"
                                    })
                                    
                            if getattr(chunk, 'text', None):
                                await websocket.send_json({"type": "tool_execution", "status": "completed"})
                                full_response_text += getattr(chunk, 'text')
                                await websocket.send_json({"type": "token", "content": getattr(chunk, 'text')})
                                
                        break # exit the fallback loop if successful
                        
                    except StopAsyncIteration:
                        # Empty response but successful request
                        await websocket.send_json({
                            "type": "status",
                            "message": "Kiko is thinking...",
                            "status": "completed"
                        })
                        break
                    except Exception as e:
                        err_str = str(e).lower()
                        if "503" in err_str or "demand" in err_str or "not found" in err_str or "quota" in err_str:
                            next_index = (main.current_model_index + 1) % len(main.model_fallback_chain)
                            next_model = main.model_fallback_chain[next_index]
                            
                            print(f"   [⚠️ {main.model_name} failed (High Demand). Falling back to {next_model}...] (Web UI)")
                            
                            main.current_model_index = next_index
                            main.model_name = next_model
                            
                            # Clear current thinking/fallback status
                            await websocket.send_json({
                                "type": "status",
                                "message": "",
                                "status": "completed"
                            })
                            
                            # Notify UI of fallback
                            await websocket.send_json({
                                "type": "status",
                                "message": f"⚠️ High demand! Switching to {next_model}...",
                                "status": "running"
                            })
                            
                            await asyncio.sleep(2)
                            # Will loop back up and retry with the new model_name
                            
                        else:
                            raise e

                # Signal completion
                await websocket.send_json({
                    "type": "done"
                })
                
                # Save Kiko's final message to SQLite
                save_chat_message(session_id, "assistant", full_response_text)
                
                # Embed and save the interaction memory
                interaction_log = f"User: {user_msg}\nKiko: {full_response_text}"
                save_resp = main.client.models.embed_content(
                    model='gemini-embedding-2',
                    contents=interaction_log
                )
                save_vector_memory(interaction_log, save_resp.embeddings[0].values)

            except Exception as e:
                error_msg = f"Kiko encountered an error: {e}"
                await websocket.send_json({
                    "type": "token",
                    "content": error_msg
                })
                await websocket.send_json({"type": "done"})
                save_chat_message(session_id, "assistant", error_msg)

    except WebSocketDisconnect:
        print(f"Client disconnected from session {session_id}")

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
