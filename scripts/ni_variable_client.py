import socket
import struct
import time

class NIVariableClient:
    """
    Client for reading/writing LabVIEW Shared Variables via NI-PSP protocol (port 3580)
    """
    
    def __init__(self, host="10.20.30.10", port=3580):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        
    def connect(self):
        """Connect to NI PSP Server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))
            self.connected = True
            print(f"✓ Connected to NI PSP Server at {self.host}:{self.port}")
            
            # Try to get initial handshake
            self._handshake()
            return True
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            self.connected = False
            return False
    
    def _handshake(self):
        """Perform initial handshake with PSP server"""
        try:
            # Send initial query
            # NI-PSP protocol handshake (simplified)
            handshake = b'\x00\x00\x00\x01'  # Version/greeting
            self.sock.send(handshake)
            
            # Receive response
            response = self.sock.recv(1024)
            if response:
                print(f"  Server response: {len(response)} bytes")
                print(f"  Raw: {response[:50].hex()}")
            
        except socket.timeout:
            print("  No handshake response (timeout)")
        except Exception as e:
            print(f"  Handshake warning: {e}")
    
    def list_variables(self):
        """
        Attempt to list available variables
        This is protocol-specific and may need adjustment
        """
        if not self.connected:
            print("Not connected. Call connect() first.")
            return []
        
        try:
            # Common PSP list command patterns
            list_commands = [
                b'\x01\x00\x00\x00',  # List command
                b'LIST\x00',
                b'ENUM\x00',
            ]
            
            variables = []
            
            for cmd in list_commands:
                try:
                    self.sock.send(cmd)
                    self.sock.settimeout(2)
                    response = self.sock.recv(4096)
                    
                    if response and len(response) > 4:
                        print(f"\nResponse to {cmd.hex()}:")
                        print(f"  Length: {len(response)} bytes")
                        print(f"  Hex: {response[:100].hex()}")
                        
                        # Try to parse as string
                        try:
                            text = response.decode('utf-8', errors='ignore')
                            if text.strip():
                                print(f"  Text: {text[:200]}")
                                variables.append(text)
                        except:
                            pass
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"  Command failed: {e}")
                    continue
            
            return variables
            
        except Exception as e:
            print(f"List variables failed: {e}")
            return []
    
    def read_variable(self, variable_path):
        """
        Read a variable value
        variable_path format: "\\\\hostname\\LibraryName\\VariableName"
        """
        if not self.connected:
            print("Not connected. Call connect() first.")
            return None
        
        try:
            # Encode variable path
            path_bytes = variable_path.encode('utf-8')
            
            # Build read request (protocol-specific)
            request = struct.pack('<I', len(path_bytes)) + path_bytes
            
            self.sock.send(request)
            response = self.sock.recv(4096)
            
            if response:
                print(f"Read response: {len(response)} bytes")
                return self._parse_value(response)
            
        except Exception as e:
            print(f"Read failed: {e}")
            return None
    
    def _parse_value(self, data):
        """Parse value from response data"""
        try:
            # Try different data types
            if len(data) >= 4:
                # Try as float
                try:
                    val = struct.unpack('<f', data[:4])[0]
                    return val
                except:
                    pass
                
                # Try as int
                try:
                    val = struct.unpack('<i', data[:4])[0]
                    return val
                except:
                    pass
            
            # Try as string
            try:
                return data.decode('utf-8', errors='ignore')
            except:
                pass
            
            return data.hex()
            
        except Exception as e:
            print(f"Parse error: {e}")
            return None
    
    def probe_protocol(self):
        """
        Send various probe commands to understand the protocol
        """
        if not self.connected:
            print("Not connected. Call connect() first.")
            return
        
        print("\n" + "="*60)
        print("Protocol Probing")
        print("="*60)
        
        probes = {
            "Version query": b'\x00\x00\x00\x00',
            "List variables": b'\x01\x00\x00\x00',
            "Status query": b'\xFF\x00\x00\x00',
            "Help": b'HELP\x00',
            "List": b'LIST\x00',
            "Enum": b'ENUM\x00',
            "Query": b'?\x00',
        }
        
        for name, probe in probes.items():
            print(f"\n{name}: {probe.hex()}")
            try:
                self.sock.send(probe)
                self.sock.settimeout(1)
                response = self.sock.recv(4096)
                
                if response:
                    print(f"  ✓ Response ({len(response)} bytes):")
                    print(f"    Hex: {response[:80].hex()}")
                    text = response.decode('utf-8', errors='ignore').strip()
                    if text and len(text) > 0:
                        print(f"    Text: {text[:150]}")
                else:
                    print(f"  ✗ No response")
                    
            except socket.timeout:
                print(f"  ✗ Timeout")
            except Exception as e:
                print(f"  ✗ Error: {e}")
            
            time.sleep(0.2)
    
    def disconnect(self):
        """Close connection"""
        if self.sock:
            self.sock.close()
            self.connected = False
            print("✓ Disconnected")


def main():
    print("="*60)
    print("NI LabVIEW Variable Client - PSP Protocol")
    print("="*60)
    
    client = NIVariableClient(host="10.20.30.10", port=3580)
    
    if client.connect():
        print("\n--- Probing Protocol ---")
        client.probe_protocol()
        
        print("\n--- Attempting to List Variables ---")
        variables = client.list_variables()
        
        if variables:
            print(f"\nFound {len(variables)} variable(s)")
            for var in variables:
                print(f"  - {var}")
        else:
            print("\nNo variables found via automatic discovery.")
            print("\nTo read a specific variable, use:")
            print("  client.read_variable('\\\\\\\\10.20.30.10\\\\YourLibrary\\\\YourVariable')")
        
        client.disconnect()
    else:
        print("\nConnection failed. Please check:")
        print("- LabVIEW Shared Variable Engine is running")
        print("- Firewall allows port 3580")
        print("- Network connectivity to 10.20.30.10")


if __name__ == "__main__":
    main()
