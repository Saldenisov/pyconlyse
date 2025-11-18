"""
Access LabVIEW Shared Variables via COM/ActiveX

Since LabVIEW 2020 is installed, we can use COM to access variables
"""

import win32com.client
import sys

try:
    import win32com.client
    print("✓ pywin32 available")
    PYWIN32_AVAILABLE = True
except ImportError:
    print("✗ pywin32 not installed")
    print("Install with: pip install pywin32")
    PYWIN32_AVAILABLE = False


def test_labview_com():
    """Try to access LabVIEW via COM"""
    if not PYWIN32_AVAILABLE:
        return False
    
    try:
        # Try to create LabVIEW Application object
        print("\nAttempting to connect to LabVIEW via COM...")
        lv = win32com.client.Dispatch("LabVIEW.Application")
        print(f"✓ Connected to LabVIEW")
        print(f"  Version: {lv.Version}")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to connect to LabVIEW COM: {e}")
        return False


def test_datasocket_com():
    """Try DataSocket ActiveX"""
    if not PYWIN32_AVAILABLE:
        return False
    
    try:
        print("\nAttempting DataSocket COM...")
        ds = win32com.client.Dispatch("DataSocket")
        print("✓ DataSocket COM available")
        
        # Try to connect to a variable
        url = "ni.var.psp://eureka/SUPERVISION/C1011NI6602"
        print(f"\nTrying to read: {url}")
        
        ds.URL = url
        ds.Connect()
        value = ds.Data
        
        print(f"✓ Value: {value}")
        ds.Disconnect()
        
        return True
        
    except Exception as e:
        print(f"✗ DataSocket failed: {e}")
        return False


def read_variable_via_datasocket(var_url):
    """
    Read a variable using DataSocket COM
    
    Args:
        var_url: Full URL like "ni.var.psp://eureka/SUPERVISION/C1011NI6602"
    """
    if not PYWIN32_AVAILABLE:
        print("pywin32 not available")
        return None
    
    try:
        ds = win32com.client.Dispatch("DataSocket")
        ds.URL = var_url
        ds.Connect()
        value = ds.Data
        ds.Disconnect()
        return value
    except Exception as e:
        print(f"Error reading {var_url}: {e}")
        return None


def read_all_supervision_variables():
    """Read all SUPERVISION variables via DataSocket"""
    if not PYWIN32_AVAILABLE:
        print("pywin32 not available")
        return {}
    
    from variable_list import SUPERVISION_VARIABLES
    
    results = {}
    
    print(f"\nReading {len(SUPERVISION_VARIABLES)} variables...")
    print("="*70)
    
    for var_name in SUPERVISION_VARIABLES:
        url = f"ni.var.psp://eureka/SUPERVISION/{var_name}"
        
        try:
            ds = win32com.client.Dispatch("DataSocket")
            ds.URL = url
            ds.Connect()
            value = ds.Data
            ds.Disconnect()
            
            results[var_name] = value
            print(f"✓ {var_name:20} = {value}")
            
        except Exception as e:
            print(f"✗ {var_name:20} - {e}")
            results[var_name] = None
    
    print("="*70)
    successful = sum(1 for v in results.values() if v is not None)
    print(f"Successfully read: {successful}/{len(SUPERVISION_VARIABLES)}")
    
    return results


def main():
    print("="*70)
    print("LabVIEW Variable Access via COM/ActiveX")
    print("="*70)
    
    if not PYWIN32_AVAILABLE:
        print("\nInstall pywin32 first:")
        print("  pip install pywin32")
        return
    
    # Test connections
    test_labview_com()
    
    if test_datasocket_com():
        print("\n✓ DataSocket working! Reading all variables...")
        results = read_all_supervision_variables()
        
        # Save results
        if results:
            import json
            from datetime import datetime
            
            output = {
                'timestamp': datetime.now().isoformat(),
                'method': 'DataSocket COM',
                'host': 'eureka',
                'library': 'SUPERVISION',
                'variables': results
            }
            
            with open('supervision_datasocket.json', 'w') as f:
                json.dump(output, f, indent=2)
            
            print(f"\n✓ Saved to supervision_datasocket.json")


if __name__ == "__main__":
    main()
