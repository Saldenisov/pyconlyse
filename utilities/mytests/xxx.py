class MsgGenerator:
    AVAILABLE_SERVICES = 10

    @property
    def AVAILABLE_SERVICES(self):
        return 0


print(MsgGenerator().AVAILABLE_SERVICES)