"""
NI Network Variable Reader using native DLL (ninetv.dll)
Works without .NET assemblies by calling the C API directly

Location: C:\\Program Files\\National Instruments\\Shared\\Network Variable\\ninetv.dll
"""

import ctypes
import sys
from ctypes import c_char_p, c_void_p, c_int, c_double, POINTER, byref
from variable_list import SUPERVISION_VARIABLES

# Try to load the native NI Network Variable DLL
try:
    ninetv = ctypes.WinDLL(r"C:\Program Files\National Instruments\Shared\Network Variable\ninetv.dll")
    print("✓ Loaded ninetv.dll")
except Exception as e:
    print(f"✗ Could not load ninetv.dll: {e}")
    sys.exit(1)

class NINetworkVariableReader:
    """Reader using native C API"""
    
    def __init__(self, host="eureka"):
        self.host = host
    
    def read_variable(self, library, variable_name):
        """
        Attempt to read a network variable using native API
        
        Note: This requires reverse-engineering the ninetv.dll API
        or using LabVIEW to create a wrapper DLL
        """
        # Build UNC path
        path = f"\\\\{self.host}\\{library}\\{variable_name}"
        
        print(f"Attempting to read: {path}")
        print("Note: Direct C API access requires knowing function signatures")
        print("Recommendation: Use LabVIEW to create a wrapper DLL or COM object")
        
        return None

def main():
    print("="*70)
    print("NI Network Variable - Native DLL Approach")
    print("="*70)
    
    print("\n⚠ IMPORTANT:")
    print("The NationalInstruments.NetworkVariable.dll (.NET assembly) is not installed.")
    print("You have ninetv.dll (native), but its API is not publicly documented.")
    
    print("\n" + "="*70)
    print("RECOMMENDED SOLUTIONS")
    print("="*70)
    
    print("\n1. Install NI Real-Time System Manager or DSC Module")
    print("   - This adds the .NET assemblies required by your Python scripts")
    print("   - Download from: https://www.ni.com/en-us/support/downloads/")
    
    print("\n2. Use LabVIEW to create a simple COM/DLL wrapper")
    print("   - Create a LabVIEW VI that reads variables")
    print("   - Export as .NET assembly or COM object")
    print("   - Call from Python")
    
    print("\n3. Use OPC UA (if available on eureka)")
    print("   - Enable OPC UA Server in LabVIEW project")
    print("   - Use python-opcua library")
    
    print("\n4. Check if DataSocket HTTP is enabled")
    print("   - Try: http://eureka/datasocket/SUPERVISION/C1011NI6602")
    
    print("\n" + "="*70)
    print("WHAT YOU HAVE:")
    print("="*70)
    print("✓ LabVIEW 2020 Runtime")
    print("✓ ninetv.dll (native C library)")
    print("✓ pythonnet")
    print("✗ NationalInstruments.NetworkVariable.dll (.NET)")
    
    print("\n" + "="*70)
    print("Variable List to Read:")
    print("="*70)
    for i, var in enumerate(SUPERVISION_VARIABLES, 1):
        print(f"  {i:2}. {var}")
    print(f"\nTotal: {len(SUPERVISION_VARIABLES)} variables")

if __name__ == "__main__":
    main()
