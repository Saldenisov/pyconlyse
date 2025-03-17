import os
import PyTango

# Set the TANGO_HOST environment variable
os.environ['TANGO_HOST'] = 'everest:10000'

def list_starters():
    # Connect to the Tango DB.
    db = PyTango.Database()
    # Retrieve all exported devices
    devices = db.get_device_exported("class=Starter")
    print(devices)
    # Filter for devices that belong to the admin group (adjust filtering as needed)
    starters = [dev for dev in devices if dev.startswith("tango/admin/")]
    return starters

def check_starters():
    starters = list_starters()
    if not starters:
        print("No starters found in Tango DB.")
        return

    for starter_name in starters:
        try:
            # Create a proxy for each starter device
            dev = PyTango.DeviceProxy(starter_name)
            state = dev.state()
            print(f"Starter {starter_name} is {state}")
        except PyTango.DevFailed as e:
            print(f"Starter {starter_name} is not running or unreachable.")
            for error in e.args:
                print("Error:", error.desc)

if __name__ == '__main__':
    check_starters()
