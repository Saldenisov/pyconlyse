"""
Remote DAQmx Access - Multiple Approaches

For accessing DAQmx cards on remote machine (eureka / 10.20.30.22)
"""

import nidaqmx
from nidaqmx.system import System

def try_remote_daqmx_direct(remote_host):
    """
    Try to access remote DAQmx device directly
    
    Requires:
    - NI-DAQmx Remote Configuration enabled on remote machine
    - Firewall rules allowing DAQmx network access
    """
    print(f"Attempting direct remote DAQmx access to {remote_host}...")
    
    try:
        # Try to access remote device by hostname
        remote_device_name = f"{remote_host}/Dev1"  # Common default name
        
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(f"{remote_device_name}/ai0")
            value = task.read()
            print(f"✓ Success! Read value: {value}")
            return True
            
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def use_psp_variables_approach():
    """
    Recommended: Use PSP variables published by LabVIEW
    
    The remote LabVIEW system reads DAQmx and publishes via PSP.
    This is the standard NI approach for remote access.
    """
    print("\n" + "="*70)
    print("RECOMMENDED APPROACH: PSP Variables")
    print("="*70)
    
    print("""
The remote LabVIEW system on eureka (10.20.30.22) is:
1. Reading DAQmx cards locally
2. Publishing values as PSP network variables
3. Making them available at: ni.var.psp://eureka/SUPERVISION/...

This is the STANDARD way to access remote DAQmx data.

To read these variables from Python, you need:

Option A: Install NI DSC Module / Real-Time System Manager
   - Adds NationalInstruments.NetworkVariable.dll
   - Then use: test_read_all.py

Option B: Create a LabVIEW COM/DLL wrapper on eureka
   - Simple VI that exposes a COM interface
   - Call from Python via win32com

Option C: Enable OPC UA on eureka LabVIEW project
   - Install: pip install opcua
   - Connect to: opc.tcp://eureka:4840

Option D: Enable DataSocket HTTP on eureka
   - Access via: http://eureka:3580/datasocket/SUPERVISION/...
   - Use standard Python requests library
    """)


def try_datasocket_http(remote_host):
    """Try to access via DataSocket HTTP protocol"""
    import urllib.request
    
    print(f"\nTrying DataSocket HTTP on {remote_host}...")
    
    # DataSocket typically uses port 3580
    test_urls = [
        f"http://{remote_host}:3580/",
        f"http://{remote_host}/datasocket/",
    ]
    
    for url in test_urls:
        try:
            print(f"  Testing: {url}")
            response = urllib.request.urlopen(url, timeout=3)
            content = response.read()
            print(f"  ✓ Server responded! ({len(content)} bytes)")
            print(f"    Content preview: {content[:200]}")
            return True
        except Exception as e:
            print(f"  ✗ {e}")
    
    return False


def check_remote_system_configuration(remote_host):
    """Check what services are running on remote system"""
    import socket
    
    print(f"\n" + "="*70)
    print(f"Checking Remote System: {remote_host}")
    print("="*70)
    
    ports_to_check = {
        3580: "NI PSP / DataSocket",
        4840: "OPC UA",
        80: "HTTP",
        443: "HTTPS",
        135: "RPC (for remote DAQmx)",
        6000: "NI MAX Remote Access"
    }
    
    for port, service in ports_to_check.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((remote_host, port))
        sock.close()
        
        status = "✓ OPEN" if result == 0 else "✗ closed"
        print(f"  Port {port:5d} ({service:25s}): {status}")


def create_labview_wrapper_guide():
    """Instructions for creating LabVIEW wrapper"""
    print("\n" + "="*70)
    print("SOLUTION: Create Simple LabVIEW COM Wrapper on Eureka")
    print("="*70)
    
    print("""
Since you have LabVIEW 2020 on eureka, create a simple wrapper:

1. On eureka, create a new VI: ReadVariables.vi
   
2. Add inputs/outputs:
   - Input: Variable Name (String Array)
   - Output: Values (Double Array)
   
3. Use Network Variable nodes to read PSP variables

4. Build as .NET Assembly:
   - Tools > Build Specifications > .NET Interop Assembly
   - Enable COM visibility
   
5. Register on eureka:
   - regasm YourAssembly.dll /codebase
   
6. From Python (this machine):
   - import win32com.client
   - obj = win32com.client.Dispatch("YourAssembly.ReadVariables")
   - values = obj.ReadVariables(["C1011NI6602", "C1201TAG"])

This gives you remote access without installing DSC Module!
    """)


def main():
    print("="*70)
    print("Remote DAQmx Access Options")
    print("="*70)
    
    remote_host = "10.20.30.22"  # eureka
    
    # Check what's available
    check_remote_system_configuration(remote_host)
    
    # Try different approaches
    print("\n" + "="*70)
    print("Testing Access Methods")
    print("="*70)
    
    # Method 1: Direct remote DAQmx (usually requires configuration)
    try_remote_daqmx_direct(remote_host)
    
    # Method 2: DataSocket HTTP
    try_datasocket_http(remote_host)
    
    # Show recommended approaches
    use_psp_variables_approach()
    
    # Show LabVIEW wrapper solution
    create_labview_wrapper_guide()


if __name__ == "__main__":
    main()
