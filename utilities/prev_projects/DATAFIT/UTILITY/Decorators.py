# -*- coding: utf-8 -*-
"""
Created on Tue Mar 29 22:43:52 2016

@author: saldenisov
"""

import functools


def once(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        if inner.called:
            return True
        if not inner.called:
            inner.result = func(*args, **kwargs)
            inner.called = True
            return False

    inner.called = False
    return inner


class singleton:
    def __init__(self, cls):
        self.cls = cls
        self.instance = None

    def __call__(self, *args, **kwargs):
        if not self.instance:
            self.instance = self.cls(*args, **kwargs)
        return self.instance
