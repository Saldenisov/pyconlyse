"""
Created on 10 Jan 2017

@author: Sergey Denisov
"""
from functools import wraps
from typing import Any
from time import sleep


def once(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if inner.called:
            print(func.__name__ + ' already done')
            return None
        if not inner.called:
            inner.called = True
            return func(*args, **kwargs)
    inner.called = False
    return inner


@once
def a():
    print('Privet')

a()
a()
