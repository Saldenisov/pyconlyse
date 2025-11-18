"""
LabVIEW Shared Variable Client using NI .NET APIs

Installation:
    pip install pythonnet

Requirements:
    - NI LabVIEW Runtime or LabVIEW installed
    - NI Measurement & Automation Explorer (MAX)
    - National Instruments assemblies in GAC
"""

import sys

try:
    import clr
    print("✓ pythonnet (clr) loaded successfully")
except ImportError:
    print("✗ pythonnet not installed. Run: pip install pythonnet")
    sys.exit(1)

try:
    # Add reference to NI assemblies
    clr.AddReference("NationalInstruments.NetworkVariable")
    clr.AddReference("NationalInstruments.Common")
    
    from NationalInstruments.NetworkVariable import (
        NetworkVariableBufferedSubscriber,
        NetworkVariableBufferedWriter,
        NetworkVariable
    )
    from NationalInstruments import NetworkVariableData
    
    print("✓ NI .NET assemblies loaded successfully")
    NI_AVAILABLE = True
    
except Exception as e:
    print(f"✗ Failed to load NI assemblies: {e}")
    print("\nPlease ensure:")
    print("  - LabVIEW Runtime or LabVIEW is installed")
    print("  - NI Variable Engine is installed")
    NI_AVAILABLE = False


class NIVariableManager:
    """Manage LabVIEW Shared Variables using NI .NET APIs"""
    
    def __init__(self, host="10.20.30.10"):
        self.host = host
        self.subscribers = {}
        self.writers = {}
        
    def read_variable(self, library_name, variable_name):
        """
        Read a shared variable value
        
        Args:
            library_name: Name of the variable library
            variable_name: Name of the variable
            
        Returns:
            Variable value or None
        """
        if not NI_AVAILABLE:
            print("NI assemblies not available")
            return None
        
        path = f"\\\\{self.host}\\{library_name}\\{variable_name}"
        print(f"Reading: {path}")
        
        try:
            # Create subscriber if doesn't exist
            if path not in self.subscribers:
                subscriber = NetworkVariableBufferedSubscriber(path)
                subscriber.Connect()
                self.subscribers[path] = subscriber
            else:
                subscriber = self.subscribers[path]
            
            # Read data
            data = subscriber.ReadData()
            value = data.GetValue()
            
            print(f"  ✓ Value: {value}")
            return value
            
        except Exception as e:
            print(f"  ✗ Read failed: {e}")
            return None
    
    def write_variable(self, library_name, variable_name, value):
        """
        Write a value to shared variable
        
        Args:
            library_name: Name of the variable library
            variable_name: Name of the variable
            value: Value to write
            
        Returns:
            True if successful, False otherwise
        """
        if not NI_AVAILABLE:
            print("NI assemblies not available")
            return False
        
        path = f"\\\\{self.host}\\{library_name}\\{variable_name}"
        print(f"Writing to: {path}")
        
        try:
            # Create writer if doesn't exist
            if path not in self.writers:
                writer = NetworkVariableBufferedWriter(path)
                writer.Connect()
                self.writers[path] = writer
            else:
                writer = self.writers[path]
            
            # Write data
            writer.WriteData(value)
            print(f"  ✓ Written: {value}")
            return True
            
        except Exception as e:
            print(f"  ✗ Write failed: {e}")
            return False
    
    def list_variables_from_url(self, url=None):
        """
        List variables from a DataSocket URL
        
        Args:
            url: DataSocket URL (e.g., "dstp://10.20.30.10/")
        """
        if url is None:
            url = f"dstp://{self.host}/"
        
        print(f"Attempting to browse: {url}")
        print("Note: This may require DataSocket Server running")
        
        # This would require DataSocket browser functionality
        # which may not be directly available in .NET API
        print("Direct browsing not implemented - you need to know variable names")
    
    def close(self):
        """Close all connections"""
        for sub in self.subscribers.values():
            try:
                sub.Disconnect()
            except:
                pass
        
        for writer in self.writers.values():
            try:
                writer.Disconnect()
            except:
                pass
        
        print("✓ All connections closed")


def example_usage():
    """Example usage with real variable from eureka server"""
    
    print("="*60)
    print("NI LabVIEW Variable Manager - .NET API")
    print("="*60)
    
    if not NI_AVAILABLE:
        print("\nCannot proceed without NI assemblies.")
        print("Install from: https://www.ni.com/en-us/support/downloads/software-products.html")
        return
    
    # Use hostname from PSP URL: ni.var.psp://eureka/SUPERVISION/C1011NI6602
    manager = NIVariableManager(host="eureka")
    
    print("\n" + "="*60)
    print("Example: Reading Your Variable")
    print("="*60)
    print("\nBased on: ni.var.psp://eureka/SUPERVISION/C1011NI6602")
    print("\nUsage:")
    print("  value = manager.read_variable('SUPERVISION', 'C1011NI6602')")
    
    # Uncomment when NI assemblies are available:
    # value = manager.read_variable('SUPERVISION', 'C1011NI6602')
    # print(f"  Value: {value}")
    
    print("\n" + "="*60)
    print("Example: Writing Variables")
    print("="*60)
    print("\nExample:")
    print("  manager.write_variable('SUPERVISION', 'C1011NI6602', 123.45)")
    
    # Uncomment to write:
    # manager.write_variable('SUPERVISION', 'C1011NI6602', new_value)
    
    manager.close()


def discover_via_datasocket():
    """
    Alternative: Use DataSocket protocol to discover variables
    Requires DataSocket Server enabled in LabVIEW
    """
    print("\n" + "="*60)
    print("Alternative: DataSocket Discovery")
    print("="*60)
    
    print("\nDataSocket URLs format:")
    print("  dstp://10.20.30.10/LibraryName/VariableName")
    print("\nYou can also access via NI MAX (Measurement & Automation Explorer)")
    print("or LabVIEW Distributed System Manager")


if __name__ == "__main__":
    example_usage()
    discover_via_datasocket()
    
    print("\n" + "="*60)
    print("Next Steps")
    print("="*60)
    print("\n1. Find your variable names using one of these methods:")
    print("   - Check LabVIEW VI on 10.20.30.10")
    print("   - Use NI MAX to browse shared variables")
    print("   - Check LabVIEW project (.lvproj) file")
    print("\n2. Once you know the names, use:")
    print("   manager = NIVariableManager('10.20.30.10')")
    print("   value = manager.read_variable('LibraryName', 'VariableName')")
    print("\n3. For continuous monitoring, create a subscriber loop")
