# tools/memory.py - Persistent memory cortex and semantic vector database interface
# Implementation details:
# Coordinates SQLite database operations for preferences, semantic memory vectors, and session persistence.

import sqlite3
import os 
import struct
import math
import datetime

# Source - https://stackoverflow.com/a/9271479
# Posted by paxdiablo, modified by community. See post 'Timeline' for change history
# Retrieved 2026-09-19, License - CC BY-SA 4.0

get_current_path = os.path.dirname(os.path.realpath(__file__))

db_path = os.path.join(get_current_path, '..', 'db', 'kiko_cortex.db')
con = sqlite3.connect(db_path)

cur = con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS core_preferences(key TEXT PRIMARY KEY, value TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS semantic_memory(id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, vector BLOB, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
cur.execute("CREATE TABLE IF NOT EXISTS chat_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
cur.execute("CREATE TABLE IF NOT EXISTS chat_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(session_id) REFERENCES chat_sessions(id))")

def memorize_preferences(key: str, value: str):
    """Memorize a core preference about senpai. Use this when senpai tells you to remember a personal preference."""
    data = (key, value)
    cur.execute("""
    INSERT OR REPLACE INTO core_preferences VALUES
        (?, ?)
    """, data)
    con.commit()

def get_all_preferences():
    fetched_rows = cur.execute("SELECT * FROM core_preferences")
    final_output = []
    for i in fetched_rows:
        final_output.append({
            "key": i[0],
            "value": i[1]
        })
    return final_output

def save_vector_memory(content: str, vector: list):
    """converts the vector list into a binary blob and stores it in the database."""
    # 'f' means a 32-bit float, so each value takes 4 bytes.
    struct_blob = struct.pack('f' * len(vector), *vector)
    data = (content, struct_blob)

    cur.execute("""
    INSERT into semantic_memory (content, vector) VALUES
        (?, ?)
    """, data)
    con.commit()

def recall_semantic_memory(query_vector: list):
    """retrieve the most similar vector memory to the query vector."""
    retrieved_data = cur.execute("SELECT content, vector FROM semantic_memory")

    best_score = -1.0
    best_content = None

    for i in retrieved_data:
        content = i[0]
        vector = struct.unpack('f' * 3072, i[1])
        
        # calculate cosine similarity between query_vector and vector
        dot_product = sum(a * b for a, b in zip(query_vector, vector))
        magnitude_query = math.sqrt(sum(a * a for a in query_vector))
        magnitude_vector = math.sqrt(sum(b * b for b in vector))
        
        if magnitude_query == 0 or magnitude_vector == 0:
            similarity = 0
        else:
            similarity = dot_product / (magnitude_query * magnitude_vector)
            
        if similarity > best_score:
            best_score = similarity
            best_content = content
            
    if best_score > 0.65:
        return best_content
    return None

def get_recent_interactions(limit: int = 3):
    """
    Retrieve the most recent conversational interactions in chronological order
    along with the timestamp of the last recorded interaction.
    """
    try:
        cur.execute("SELECT content, timestamp FROM semantic_memory ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        if not rows:
            return [], None
        last_timestamp = rows[0][1]
        rows.reverse()
        formatted_interactions = []
        for content, ts in rows:
            formatted_interactions.append({"content": content, "timestamp": ts})
        return formatted_interactions, last_timestamp
    except Exception:
        return [], None

def format_elapsed_time(last_timestamp_str: str) -> str:
    """
    Computes a human-readable duration string since the given UTC timestamp string.
    """
    try:
        last_dt = datetime.datetime.strptime(last_timestamp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        delta = now_dt - last_dt
        
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return "just moments ago"
            
        minutes = total_seconds // 60
        hours = minutes // 60
        days = hours // 24
        
        if days > 1:
            return f"{days} days ago"
        elif days == 1:
            return "yesterday (about 24 hours ago)"
        elif hours > 1:
            return f"about {hours} hours ago"
        elif hours == 1:
            return "about 1 hour ago"
        elif minutes > 1:
            return f"about {minutes} minutes ago"
        else:
            return "just a couple minutes ago"
    except Exception:
        return "recently"

def create_chat_session(title: str = "New Session"):
    cur.execute("INSERT INTO chat_sessions (title) VALUES (?)", (title,))
    con.commit()
    return cur.lastrowid

def get_chat_sessions():
    cur.execute("SELECT id, title, timestamp FROM chat_sessions ORDER BY timestamp DESC")
    return [{"id": row[0], "title": row[1], "timestamp": row[2]} for row in cur.fetchall()]

def save_chat_message(session_id: int, role: str, content: str):
    cur.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, role, content))
    con.commit()

def get_chat_messages(session_id: int):
    cur.execute("SELECT role, content, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
    return [{"role": row[0], "content": row[1], "timestamp": row[2]} for row in cur.fetchall()]

def delete_chat_session(session_id: int):
    cur.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    cur.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    con.commit()
