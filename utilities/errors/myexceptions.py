"""
Created on 14 May 2017

@author: Sergey Denisov
"""


class MyException(Exception):
    def __init__(self, text):
        super().__init__(text)


class NoSuchFileType(MyException):
    def __init__(self):
        MyException.__init__(self, "Unsupported file type")


class DeviceError(Exception):
    def __init__(self, text, device_name='Device'):
        super().__init__(f'{device_name}: {text}')


class ThinkerError(Exception):
    def __init__(self, text):
        super().__init__(f'Thinker: {text}')


class ThinkerEventError(Exception):
    def __init__(self, text):
        super().__init__(f'ThinkerEvent: {text}')


class MsgError(Exception):
    def __init__(self, text):
        super().__init__(f'MsgError during msg generation: {text}')


class MsgComNotKnown(Exception):
    def __init__(self, text):
        super().__init__(f'Command: {text} is not known')


class CannotTreatLogic(Exception):
    def __init__(self, text):
        super().__init__(f'Cannot treat logic, something is missing in {text}')


class WrongServiceGiven(Exception):
    def __init__(self, text):
        super().__init__(f'Wrong service is passed: {text}')


class ThinkerError(MyException):
    def __init__(self, text):
        super().__init__(f'{text}')


class ThinkerErrorReact(MyException):
    def __init__(self, text):
        if text != '':
            super().__init__(f'Thinker error in react function: {text}')
        else:
            super().__init__('Thinker error in react function')


class ThinkerEventFuncError(MyException):
    def __init__(self, event):
        super().__init__(f'Thinker event {event.name} error in logic function.')


class WrongAddress(MyException):
    def __init__(self, text):
        super().__init__(f'Wrong address port: {text}')


class WrongInfoType(MyException):
    def __init__(self, extra):
        super().__init__(f'Wrong info type is passed: {extra}')


class WrondDictDataStructure(MyException):
    def __init__(self):
        super().__init__('Wrong dictionary passed')


class ConfigCannotBeSet(MyException):
    def __init__(self):
        super().__init__('Config cannot be set')


class CannotmoveDL(MyException):
    def __init__(self):
        super().__init__('stepmotors cannot be moved')


class EmptyConfiguration(MyException):
    def __init__(self):
        MyException.__init__(self, "Configuration is empty")


class FittingError(MyException):
    def __init__(self):
        MyException.__init__(self, "Fitting MsgError")


class ValidationFailed(MyException):
    def __init__(self):
        MyException.__init__(self, "Validation failed")


class NoSuchFileType(MyException):
    def __init__(self, text=None):
        if not text:
            MyException.__init__(self, "Unsupported file type.")
        else:
            MyException.__init__(self, f"Unsupported file type {text}.")


class GraphModelError(MyException):
    def __init__(self):
        super().__init__("GraphModel creation error")


class OpenerError(MyException):
    def __init__(self):
        super().__init__("Opener did not work")


class NoSuchFittingFunction(MyException):
    def __init__(self):
        super().__init__("No such fitting function")


class DLLIsBlocked(MyException):
    def __init__(self):
        super().__init__("DLL is blocked")