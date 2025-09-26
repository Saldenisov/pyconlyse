# -*- coding: utf-8 -*-
"""
Created on Tue Dec 13 10:20:40 2016

@author: saldenisov
"""

def a(b):
    b=b
    def c():
        return b*b
    print(c())