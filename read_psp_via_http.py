"""
Simple HTTP wrapper for reading PSP variables

SETUP REQUIRED ON EUREKA (10.20.30.2):
Create a simple LabVIEW VI that:
1. Listens on HTTP port (e.g., 8080)
2. Receives GET /read?var=VARNAME
3. Reads PSP variable locally using Network Variable nodes
4. Returns JSON: {"variable": "VARNAME", "value": 123.45}

Then this Python script can read all variables remotely!
"""

import requests
import json
from variable_list import SUPERVISION_VARIABLES
from datetime import datetime


class HTTPPSPReader:
    """Read PSP variables via simple HTTP wrapper on eureka"""
    
    def __init__(self, host="eureka", port=8080):
        self.base_url = f"http://{host}:{port}"
    
    def read_variable(self, var_name):
        """Read a single variable via HTTP"""
        try:
            response = requests.get(
                f"{self.base_url}/read",
                params={'var': var_name},
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            return data.get('value')
        except Exception as e:
            print(f"Error reading {var_name}: {e}")
            return None
    
    def read_all_variables(self, var_list):
        """Read multiple variables"""
        results = {}
        
        for var_name in var_list:
            value = self.read_variable(var_name)
            results[var_name] = value
            if value is not None:
                print(f"✓ {var_name:20s} = {value}")
            else:
                print(f"✗ {var_name:20s} - failed")
        
        return results
    
    def save_snapshot(self, results, filename="psp_snapshot.json"):
        """Save results to JSON"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'host': 'eureka',
            'library': 'SUPERVISION',
            'variables': results
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✓ Saved to {filename}")


def print_labview_vi_instructions():
    """Instructions for creating the LabVIEW wrapper"""
    print("="*70)
    print("CREATE THIS SIMPLE VI ON EUREKA:")
    print("="*70)
    print("""
VI Name: PSP_HTTP_Server.vi

Block Diagram:
1. While Loop
2. HTTP Server VI from Web Services palette:
   - Start HTTP Server (port 8080)
   - Read Request
3. Parse query string to get variable name
4. Use Network Variable Read node:
   - Path: \\\\localhost\\SUPERVISION\\[variable_name]
5. Create JSON response:
   - {"variable": "[name]", "value": [value]}
6. Send HTTP Response

Front Panel:
- String Indicator: Shows requests
- Stop Button

Alternative - Even Simpler:
Use LabVIEW Web Services to create REST API endpoint automatically!

1. File > New > Web Service
2. Add HTTP Method VI
3. Input: Variable name (String)
4. Output: Value (Double)
5. Deploy to localhost:8080

Then access from Python as shown in this script!
    """)


def alternative_solutions():
    """Show alternative solutions"""
    print("\n" + "="*70)
    print("ALTERNATIVE SOLUTIONS")
    print("="*70)
    
    print("""
1. SSH + LabVIEW CLI (if SSH enabled on eureka):
   - SSH to eureka
   - Run LabVIEW VI via command line
   - Capture output
   
2. Windows Remote Desktop to eureka:
   - Run Python scripts directly on eureka
   - DAQmx access is local there
   
3. Install NI DSC Module on this PC:
   - Download from ni.com
   - Adds NationalInstruments.NetworkVariable.dll
   - Use existing test_read_all.py script
   
4. Network Share + File Polling:
   - LabVIEW on eureka writes values to CSV/JSON file
   - Share folder via SMB
   - Python reads file from network share
   - Simple but not real-time
    """)


def test_direct_psp_connection():
    """Test if we can connect to PSP port"""
    import socket
    
    print("="*70)
    print("Testing PSP Connection")
    print("="*70)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(("eureka", 3580))
        print("✓ Connected to eureka:3580 (PSP port)")
        print("  PSP server is running!")
        print("  You just need a way to read the variables...")
        sock.close()
        return True
    except Exception as e:
        print(f"✗ Cannot connect: {e}")
        return False


def main():
    print("="*70)
    print("Read PSP Variables via HTTP Wrapper")
    print("="*70)
    
    # Test PSP connection
    test_direct_psp_connection()
    
    # Show setup instructions
    print_labview_vi_instructions()
    
    # Show alternatives
    alternative_solutions()
    
    print("\n" + "="*70)
    print("READY TO USE (after LabVIEW HTTP wrapper is created):")
    print("="*70)
    print("""
# Usage example:
reader = HTTPPSPReader(host="eureka", port=8080)
results = reader.read_all_variables(SUPERVISION_VARIABLES)
reader.save_snapshot(results)
    """)


if __name__ == "__main__":
    main()
