from devices.devices import Client

class SuperUser(Client):
    # TODO: all functions must realized for consistency reasons
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def description(self):
        return "SuperUser Client"

