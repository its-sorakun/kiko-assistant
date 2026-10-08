import os
import requests
from typing import List, Dict, Any, Optional

NOTES_API_BASE_URL = "http://localhost:5000/api/v1"

def _get_headers() -> dict:
    api_key = os.getenv("NOTES_API_KEY")
    if not api_key:
        raise ValueError("NOTES_API_KEY environment variable is missing. Cannot authenticate with notes-web API.")
    return {"x-api-key": api_key}

def get_notes() -> List[Dict[str, Any]]:
    """
    Fetches all notes associated with your API key from the local notes-web application.
    Returns a list of note objects containing _id, title, content, and theme.
    """
    response = requests.get(f"{NOTES_API_BASE_URL}/notes", headers=_get_headers())
    response.raise_for_status()
    return response.json()

def create_note(title: str, content: str) -> Dict[str, Any]:
    """
    Creates a new note in the local notes-web application.
    
    Args:
        title: The title of the note.
        content: The raw markdown content of the note. Use standard markdown.
    """
    payload = {
        "title": title,
        "content": content,
        "theme": "string"
    }
    response = requests.post(f"{NOTES_API_BASE_URL}/notes", json=payload, headers=_get_headers())
    response.raise_for_status()
    return response.json()

def update_note(note_id: str, title: Optional[str] = None, content: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates an existing note in the local notes-web application by its unique _id.
    Note: This completely overwrites the provided fields, so you must provide the full updated strings.
    
    Args:
        note_id: The unique _id of the note to update.
        title: The new full title of the note (optional).
        content: The new full raw markdown content of the note (optional).
    """
    payload = {}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
        
    response = requests.put(f"{NOTES_API_BASE_URL}/notes/{note_id}", json=payload, headers=_get_headers())
    response.raise_for_status()
    return response.json()

def delete_note(note_id: str) -> Dict[str, str]:
    """
    Deletes a note from the local notes-web application by its unique _id.
    
    Args:
        note_id: The unique _id of the note to delete.
    """
    response = requests.delete(f"{NOTES_API_BASE_URL}/notes/{note_id}", headers=_get_headers())
    response.raise_for_status()
    return response.json()
