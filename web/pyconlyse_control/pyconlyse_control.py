import tango


class PyconlyseController:
    def __init__(self):
        self.device_proxy = None  # tango.DeviceProxy("your/device/name")

    def read_attribute(self, attribute_name):
        return self.device_proxy.read_attribute(attribute_name).value

    def write_attribute(self, attribute_name, value):
        self.device_proxy.write_attribute(attribute_name, value)
