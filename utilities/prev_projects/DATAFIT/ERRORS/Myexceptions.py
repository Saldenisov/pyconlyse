'''
Created on 4 juil. 2016

@author: saldenisov
'''


class MyException(Exception):
    def __init__(self, text):
        super().__init__(text)


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
    def __init__(self):
        MyException.__init__(self, "Unsupported file type")


class GraphModelError(MyException):
    def __init__(self):
        super().__init__("GraphModel creation error")


class OpenerError(MyException):
    def __init__(self):
        super().__init__("Opener did not work")


class NoSuchFittingFunction(MyException):
    def __init__(self):
        super().__init__("No such fitting function")

