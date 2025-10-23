"""
Quick test: Read all SUPERVISION variables

Usage:
    python test_read_all.py

Requirements:
    - NI LabVIEW Runtime installed
    - pythonnet installed
    - Network access to eureka
"""

try:
    import clr
    clr.AddReference("NationalInstruments.NetworkVariable")
    from NationalInstruments.NetworkVariable import NetworkVariableBufferedSubscriber
    
    from variable_list import SUPERVISION_VARIABLES
    
    print("="*70)
    print(f"Reading {len(SUPERVISION_VARIABLES)} variables from eureka/SUPERVISION")
    print("="*70)
    
    results = {}
    
    for var_name in SUPERVISION_VARIABLES:
        path = f"\\\\eureka\\SUPERVISION\\{var_name}"
        
        try:
            subscriber = NetworkVariableBufferedSubscriber(path)
            subscriber.Connect()
            
            data = subscriber.ReadData()
            value = data.GetValue()
            
            results[var_name] = value
            print(f"✓ {var_name:20} = {value}")
            
            subscriber.Disconnect()
            
        except Exception as e:
            print(f"✗ {var_name:20} - Error: {e}")
            results[var_name] = None
    
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print(f"Total variables: {len(SUPERVISION_VARIABLES)}")
    print(f"Successfully read: {sum(1 for v in results.values() if v is not None)}")
    print(f"Errors: {sum(1 for v in results.values() if v is None)}")
    
    # Save to file
    import json
    from datetime import datetime
    
    output = {
        'timestamp': datetime.now().isoformat(),
        'host': 'eureka',
        'library': 'SUPERVISION',
        'variables': results
    }
    
    with open('supervision_snapshot.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Saved snapshot to supervision_snapshot.json")

except ImportError as e:
    print(f"✗ Import error: {e}")
    print("\nPlease install:")
    print("  pip install pythonnet")
    print("  NI LabVIEW Runtime from ni.com")

except Exception as e:
    print(f"✗ Error: {e}")
    print("\nMake sure:")
    print("  - NI LabVIEW Runtime is installed")
    print("  - Network connection to eureka is active")
    print("  - Variable names are correct")
