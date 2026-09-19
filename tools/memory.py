# for memory stuffs, using sqlite3 and vector databases.
import sqlite3
import os 
import struct

# --- code snippet copied through stackoverflow and modified by me

# Source - https://stackoverflow.com/a/9271479
# Posted by paxdiablo, modified by community. See post 'Timeline' for change history
# Retrieved 2026-09-19, License - CC BY-SA 4.0

get_current_path = os.path.dirname(os.path.realpath(__file__))
# ---
db_path = os.path.join(get_current_path, '..', 'db', 'kiko_cortex.db')
con = sqlite3.connect(db_path)

# print(con)
cur = con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS core_preferences(key TEXT PRIMARY KEY, value TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS semantic_memory(id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, vector BLOB, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")

def memorize_preferences(key: str, value: str):
    """Memorize a core preference about senpai. Use this when senpai tells you to remember a personal preference."""
    data = (key, value)
    # insert or replace
    cur.execute("""
    INSERT OR REPLACE INTO core_preferences VALUES
        (?, ?)
    """, data)
    con.commit()

def get_all_preferences():
    fetched_rows = cur.execute("SELECT * FROM core_preferences")
    # return cur.fetchall()
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
    # print(data)

    cur.execute("""
    INSERT into semantic_memory (content, vector) VALUES
        (?, ?)
    """, data)
    con.commit()

def recall_semantic_memory(query_vector: list):
    """retrieve the most similar vector memory to the query vector."""
    struct_blob = struct.pack('f' * len(query_vector), *query_vector)

    
