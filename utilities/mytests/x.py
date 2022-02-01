from tango import Database
db = Database()


devices = db.get_device_exported("*")

print(devices)