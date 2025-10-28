import requests
import time
import random
from datetime import datetime

class LiveMPAgent:
    def __init__(self, agent_id, platform_url):
        self.agent_id = agent_id
        self.platform_url = platform_url
        self.running = True
    
    def register(self):
        """Register with your live platform"""
        device_info = {
            'agent_id': self.agent_id,
            'phone_model': random.choice([
                'Samsung Galaxy S23', 'iPhone 14 Pro', 'Google Pixel 7', 
                'OnePlus 11', 'Xiaomi 13', 'Huawei P60'
            ]),
            'android_version': random.choice(['Android 13', 'Android 14', 'iOS 16', 'iOS 17']),
            'battery_level': random.randint(20, 100),
            'location': f"{random.uniform(-90, 90):.6f}, {random.uniform(-180, 180):.6f}"
        }
        
        try:
            response = requests.post(
                f"{self.platform_url}/api/agent/register",
                json=device_info,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            if response.status_code == 200:
                print(f"✅ SUCCESS: Registered {self.agent_id} with your live platform!")
                print(f"📡 Response: {response.json()}")
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
            return response.json()
        except Exception as e:
            print(f"💥 Connection error: {e}")
            return None
    
    def upload_screenshot(self):
        """Upload a fake screenshot"""
        try:
            # Create fake screenshot data
            screenshot_data = f"FAKE_SCREENSHOT_{self.agent_id}_{int(time.time())}".encode()
            
            files = {'screenshot': ('screen.jpg', screenshot_data, 'image/jpeg')}
            data = {'agent_id': self.agent_id}
            
            response = requests.post(
                f"{self.platform_url}/api/agent/upload_screenshot",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"📸 Screenshot uploaded successfully!")
            return response.status_code == 200
        except Exception as e:
            print(f"📸 Screenshot error: {e}")
            return False
    
    def upload_call(self):
        """Upload a fake call recording"""
        try:
            # Create fake call data
            call_data = f"FAKE_CALL_{self.agent_id}_{int(time.time())}".encode()
            
            files = {'audio': ('call.mp3', call_data, 'audio/mpeg')}
            data = {
                'agent_id': self.agent_id,
                'call_type': random.choice(['incoming', 'outgoing', 'missed']),
                'phone_number': f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}",
                'duration': random.randint(10, 300)
            }
            
            response = requests.post(
                f"{self.platform_url}/api/agent/upload_call",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"📞 Call recording uploaded successfully!")
            return response.status_code == 200
        except Exception as e:
            print(f"📞 Call upload error: {e}")
            return False
    
    def update_status(self):
        """Send status update"""
        try:
            status_data = {
                'agent_id': self.agent_id,
                'battery_level': random.randint(15, 95),
                'location': f"{random.uniform(-90, 90):.6f}, {random.uniform(-180, 180):.6f}"
            }
            
            response = requests.post(
                f"{self.platform_url}/api/agent/update_status",
                json=status_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"🔋 Status updated - Battery: {status_data['battery_level']}%")
            return response.status_code == 200
        except Exception as e:
            print(f"🔋 Status error: {e}")
            return False
    
    def check_commands(self):
        """Check for commands from your platform"""
        try:
            response = requests.get(
                f"{self.platform_url}/api/agent/check_commands/{self.agent_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                commands = response.json().get('commands', [])
                if commands:
                    print(f"🎯 Found {len(commands)} commands!")
                
                for cmd in commands:
                    print(f"⚡ Executing: {cmd['command']}")
                    
                    # Execute command based on type
                    if cmd['command'] == 'capture_screenshot':
                        self.upload_screenshot()
                    elif cmd['command'] == 'get_device_info':
                        self.register()
                    elif cmd['command'] == 'get_location':
                        self.update_status()
                    
                    # Mark command as completed
                    requests.post(
                        f"{self.platform_url}/api/agent/command_result",
                        json={'command_id': cmd['id'], 'result': f'Executed: {cmd["command"]}'}
                    )
                
                return len(commands)
            return 0
        except Exception as e:
            print(f"🎯 Command check error: {e}")
            return 0
    
    def start_surveillance(self):
        """Start the surveillance loop"""
        print("🎯 MP_AGENT - Live Surveillance Starting")
        print("=" * 50)
        print(f"🆔 Agent ID: {self.agent_id}")
        print(f"🌐 Platform: {self.platform_url}")
        print("=" * 50)
        
        # Initial registration
        if not self.register():
            print("❌ Initial registration failed. Retrying in 30 seconds...")
            time.sleep(30)
            if not self.register():
                print("💥 Cannot connect to platform. Exiting.")
                return
        
        cycle = 0
        while self.running:
            try:
                cycle += 1
                print(f"\n🔄 Cycle #{cycle} - {datetime.now().strftime('%H:%M:%S')}")
                print("-" * 40)
                
                # Check for commands
                command_count = self.check_commands()
                
                # Regular activities (every few cycles)
                if cycle % 3 == 0:
                    self.upload_screenshot()
                
                if cycle % 5 == 0:
                    self.upload_call()
                
                if cycle % 2 == 0:
                    self.update_status()
                
                # Re-register every 10 cycles
                if cycle % 10 == 0:
                    self.register()
                
                print(f"✅ Cycle #{cycle} completed")
                print(f"⏰ Next update in 30 seconds...")
                time.sleep(30)
                
            except KeyboardInterrupt:
                print("\n🛑 Stopped by user")
                break
            except Exception as e:
                print(f"💥 Cycle error: {e}")
                print("🔄 Retrying in 60 seconds...")
                time.sleep(60)

# ==== CONFIGURATION FOR YOUR LIVE PLATFORM ====
PLATFORM_URL = "https://mp-agent.onrender.com"  # Your live platform
AGENT_ID = "live_agent_001"  # Change this for multiple agents

if __name__ == "__main__":
    agent = LiveMPAgent(AGENT_ID, PLATFORM_URL)
    agent.start_surveillance()