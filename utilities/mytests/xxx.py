from tango import Database

db = Database()
device = db.get_device_exported("*")