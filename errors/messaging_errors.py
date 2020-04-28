from .myexceptions import MyException


class MessengerError(MyException):
    def __init__(self, text):
        super().__init__(f'Messenger: {text}')


class MessageError(MyException):
    def __init__(self, text):
        super().__init__(f'Messenger: {text}')