"""
LabVIEW Shared Variable Client using OPC UA

Installation:
    pip install opcua

Note: LabVIEW can publish variables via OPC UA Server
Check if OPC UA is enabled in your LabVIEW setup
"""

import sys

try:
    from opcua import Client, ua
    print("✓ opcua library loaded")
    OPCUA_AVAILABLE = True
except ImportError:
    print("✗ opcua not installed. Run: pip install opcua")
    OPCUA_AVAILABLE = False
    sys.exit(1)


class OPCUAVariableClient:
    """Connect to LabVIEW variables via OPC UA"""
    
    def __init__(self, host="10.20.30.10", port=4840):
        self.url = f"opc.tcp://{host}:{port}"
        self.client = None
        self.connected = False
        
    def connect(self):
        """Connect to OPC UA server"""
        try:
            print(f"Connecting to {self.url}...")
            self.client = Client(self.url)
            self.client.connect()
            self.connected = True
            print(f"✓ Connected to OPC UA server")
            
            # Get server info
            server_name = self.client.get_server_node().get_browse_name()
            print(f"  Server: {server_name}")
            
            return True
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            self.connected = False
            return False
    
    def browse_variables(self, node=None, indent=0):
        """
        Recursively browse all variables in the OPC UA server
        
        Args:
            node: Starting node (None = root)
            indent: Indentation level for display
        """
        if not self.connected:
            print("Not connected. Call connect() first.")
            return []
        
        if node is None:
            node = self.client.get_objects_node()
        
        variables = []
        
        try:
            for child in node.get_children():
                try:
                    browse_name = child.get_browse_name().Name
                    node_class = child.get_node_class()
                    
                    prefix = "  " * indent
                    
                    if node_class == ua.NodeClass.Variable:
                        try:
                            value = child.get_value()
                            data_type = child.get_data_type_as_variant_type()
                            print(f"{prefix}📊 {browse_name} = {value} (type: {data_type})")
                            variables.append({
                                'name': browse_name,
                                'node': child,
                                'value': value,
                                'path': child.nodeid.to_string()
                            })
                        except:
                            print(f"{prefix}📊 {browse_name} (unreadable)")
                            variables.append({
                                'name': browse_name,
                                'node': child,
                                'value': None,
                                'path': child.nodeid.to_string()
                            })
                    
                    elif node_class == ua.NodeClass.Object:
                        print(f"{prefix}📁 {browse_name}/")
                        # Recursively browse objects
                        child_vars = self.browse_variables(child, indent + 1)
                        variables.extend(child_vars)
                        
                except Exception as e:
                    print(f"{prefix}⚠ Error browsing child: {e}")
                    continue
                    
        except Exception as e:
            print(f"Browse error: {e}")
        
        return variables
    
    def read_variable(self, node_id):
        """Read a specific variable by NodeId"""
        if not self.connected:
            print("Not connected. Call connect() first.")
            return None
        
        try:
            node = self.client.get_node(node_id)
            value = node.get_value()
            return value
        except Exception as e:
            print(f"Read failed: {e}")
            return None
    
    def write_variable(self, node_id, value):
        """Write a value to a variable"""
        if not self.connected:
            print("Not connected. Call connect() first.")
            return False
        
        try:
            node = self.client.get_node(node_id)
            node.set_value(value)
            print(f"✓ Written: {value}")
            return True
        except Exception as e:
            print(f"Write failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        if self.client:
            self.client.disconnect()
            self.connected = False
            print("✓ Disconnected")


def try_multiple_ports(host="10.20.30.10"):
    """Try common OPC UA ports"""
    common_ports = [4840, 4841, 4842, 62541, 62548]
    
    print("="*60)
    print("Scanning for OPC UA servers...")
    print("="*60)
    
    for port in common_ports:
        print(f"\nTrying port {port}...")
        client = OPCUAVariableClient(host, port)
        if client.connect():
            print(f"\n✓ Found OPC UA server on port {port}!")
            return client
        
    print("\n✗ No OPC UA server found on common ports")
    return None


def main():
    print("="*60)
    print("LabVIEW Variable Discovery via OPC UA")
    print("="*60)
    
    # Try to find OPC UA server
    client = try_multiple_ports("10.20.30.10")
    
    if client:
        print("\n" + "="*60)
        print("Browsing Variables")
        print("="*60)
        
        variables = client.browse_variables()
        
        print("\n" + "="*60)
        print(f"Summary: Found {len(variables)} variable(s)")
        print("="*60)
        
        if variables:
            print("\nVariable list:")
            for var in variables:
                print(f"  - {var['name']}: {var['value']}")
                print(f"    NodeId: {var['path']}")
        
        client.disconnect()
    else:
        print("\n" + "="*60)
        print("OPC UA Not Available")
        print("="*60)
        print("\nPossible reasons:")
        print("  1. OPC UA Server not enabled in LabVIEW")
        print("  2. Using DataSocket/PSP protocol instead")
        print("  3. Different port configuration")
        
        print("\n" + "="*60)
        print("Alternative: DataSocket/PSP Protocol")
        print("="*60)
        print("\nSince port 3580 is open, LabVIEW is using PSP protocol.")
        print("You need to either:")
        print("  1. Install NI software on this machine:")
        print("     - NI LabVIEW Runtime")
        print("     - NI Measurement & Automation Explorer (MAX)")
        print("  2. Or enable OPC UA on the LabVIEW server")
        print("  3. Or use remote connection from a machine with NI software")


if __name__ == "__main__":
    if not OPCUA_AVAILABLE:
        print("Install opcua: pip install opcua")
    else:
        main()
