import sqlite3
from datetime import datetime

DB_NAME = "claramd.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS symptom_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symptom TEXT,
            explanation TEXT,
            emergency TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_history(symptom, explanation, emergency):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Extract the first 200 characters of the AI explanation
    truncated_explanation = explanation
    if len(explanation) > 200:
        truncated_explanation = explanation[:197] + "..."
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO symptom_history (symptom, explanation, emergency, timestamp)
        VALUES (?, ?, ?, ?)
    """, (symptom, truncated_explanation, emergency, timestamp))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, symptom, explanation, emergency FROM symptom_history ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_history():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM symptom_history")
    conn.commit()
    conn.close()
