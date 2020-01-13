class device:

    def __init__(self, id=10):
        self.id = 10


class controller:

    def __init__(self, dev: device):
        self.device = dev


class serv(device, controller):

    def __init__(self, id):
        device.__init__(self, id=id)
        controller.__init__(self, self.device)


a = serv(id=20)
print(a.id)