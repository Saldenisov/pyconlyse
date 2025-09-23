# -*- coding: utf-8 -*-
"""
Created on Wed Nov 16 09:23:52 2016

@author: saldenisov
"""


class MyException(Exception):
    def __init__(self, text):
        super().__init__(text)


class WrongExtensionError(MyException):
    def __init__(self, text):
        text = "Error! Wrong Extension. In this case it is not " + text
        MyException.__init__(self, text)


class DataSizeException(MyException):
    def __init__(self, text):
        text = "Exception! Wrong Data Size:  " + text
        MyException.__init__(self, text)
        
class WrongCommand(MyException):
    def __init__(self, text):
        text = "Error! Wrong Command:  " + text
        MyException.__init__(self, text)
        
class FittingError(MyException):
    def __init__(self, text):
        text = "Error during fitting of:  " + text
        MyException.__init__(self, text)      

