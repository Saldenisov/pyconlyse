from devices.devices import Client


class SuperUser(Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def description(self):
        return "SuperUser Client"

