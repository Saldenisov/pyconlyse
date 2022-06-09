

class MyException(Exception):
    def __init__(self, text):
        super().__init__(text)


class DLLerror(MyException):
    def __init__(self, text):
        MyException.__init__(self, "DLL error:" + text)