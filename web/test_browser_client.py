# test_browser_client.py - Test script for browser client functionality
import requests
import json
import time
from datetime import datetime

class BrowserClientTester:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.token = None
    
    def login(self, username="admin", password="password"):
        """Test login and get authentication token"""
        print("🔐 Testing authentication...")
        
        login_data = {
            "username": username,
            "password": password
        }
        
        response = self.session.post(f"{self.base_url}/api/login", json=login_data)
        
        if response.status_code == 200:
            print("✅ Authentication successful")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    
    def test_device_list(self):
        """Test device listing endpoint"""
        print("\n📋 Testing device list...")
        
        response = self.session.get(f"{self.base_url}/api/devices")
        
        if response.status_code == 200:
            data = response.json()
            devices = data.get('devices', [])
            print(f"✅ Found {len(devices)} devices")
            
            for device in devices[:3]:  # Show first 3 devices
                print(f"   - {device['name']} ({device['class']}) - {device['state']}")
            
            return devices
        else:
            print(f"❌ Device list failed: {response.status_code}")
            return []
    
    def test_device_info(self, device_name):
        """Test device information endpoint"""
        print(f"\n🔍 Testing device info for {device_name}...")
        
        response = self.session.get(f"{self.base_url}/api/device/{device_name}/info")
        
        if response.status_code == 200:
            data = response.json()
            device_info = data.get('device_info', {})
            
            print(f"✅ Device info retrieved")
            print(f"   - State: {device_info.get('state')}")
            print(f"   - Connected: {device_info.get('connected')}")
            print(f"   - Attributes: {len(device_info.get('attributes', {}))}")
            print(f"   - Commands: {len(device_info.get('commands', {}))}")
            
            return device_info
        else:
            print(f"❌ Device info failed: {response.status_code}")
            return None
    
    def test_attribute_read(self, device_name, attribute_name):
        """Test attribute reading"""
        print(f"\n📖 Testing attribute read: {device_name}/{attribute_name}...")
        
        response = self.session.get(f"{self.base_url}/api/device/{device_name}/attribute/{attribute_name}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Attribute read successful")
            print(f"   - Value: {data.get('value')}")
            print(f"   - Quality: {data.get('quality')}")
            
            return data
        else:
            print(f"❌ Attribute read failed: {response.status_code}")
            return None
    
    def test_command_execution(self, device_name, command_name):
        """Test command execution"""
        print(f"\n⚡ Testing command execution: {device_name}/{command_name}...")
        
        response = self.session.post(
            f"{self.base_url}/api/device/{device_name}/command/{command_name}",
            json={}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Command executed successfully")
            print(f"   - Result: {data.get('result')}")
            
            return data
        else:
            print(f"❌ Command execution failed: {response.status_code}")
            return None
    
    def test_itest_psu_endpoints(self, device_name):
        """Test iTest PSU specific endpoints"""
        print(f"\n⚡ Testing iTest PSU endpoints for {device_name}...")
        
        # Test GET current readings
        response = self.session.get(f"{self.base_url}/api/device/itest/{device_name}/current")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ iTest PSU readings:")
            print(f"   - Current Setpoint: {data.get('current_setpoint', 'N/A')} A")
            print(f"   - Measured Current: {data.get('measured_current', 'N/A')} A")
            print(f"   - Measured Voltage: {data.get('measured_voltage', 'N/A')} V")
            
            # Test fine increment
            increment_response = self.session.post(
                f"{self.base_url}/api/device/itest/{device_name}/current",
                json={"action": "inc_fine"}
            )
            
            if increment_response.status_code == 200:
                inc_data = increment_response.json()
                print(f"✅ Fine increment successful: {inc_data.get('current_setpoint')} A")
                return True
            else:
                print(f"❌ Fine increment failed: {increment_response.status_code}")
        else:
            print(f"❌ iTest PSU readings failed: {response.status_code}")
        
        return False
    
    def run_full_test(self):
        """Run comprehensive test suite"""
        print("🚀 Starting Browser Client Test Suite")
        print("=" * 50)
        
        # Test authentication
        if not self.login():
            print("❌ Test suite aborted - authentication failed")
            return
        
        # Test device listing
        devices = self.test_device_list()
        if not devices:
            print("❌ Test suite aborted - no devices found")
            return
        
        # Test device info for first available device
        available_devices = [d for d in devices if d.get('available', False)]
        
        if available_devices:
            test_device = available_devices[0]
            device_name = test_device['name']
            
            # Test device info
            device_info = self.test_device_info(device_name)
            
            if device_info:
                # Test attribute reading (try common attributes)
                attributes = device_info.get('attributes', {})
                if attributes:
                    first_attr = list(attributes.keys())[0]
                    self.test_attribute_read(device_name, first_attr)
                
                # Test command execution (try State command if available)
                commands = device_info.get('commands', {})
                if 'State' in commands:
                    self.test_command_execution(device_name, 'State')
                
                # Test iTest PSU specific endpoints if applicable
                if 'itest' in device_name.lower() or 'psu' in device_name.lower():
                    self.test_itest_psu_endpoints(device_name)
        
        print("\n" + "=" * 50)
        print("🎉 Test suite completed!")
        print("\nNext steps:")
        print("1. Open http://localhost:3000/devices in your browser")
        print("2. Select a device from the sidebar")
        print("3. Try the real-time monitoring feature")
        print("4. Test device control through the web interface")

if __name__ == "__main__":
    tester = BrowserClientTester()
    tester.run_full_test()