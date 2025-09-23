# -*- coding: utf-8 -*-
"""
Created on Sat Nov 19 21:54:46 2016

@author: saldenisov
"""

import functools
import collections
import numpy as np
from itertools import tee

def setvalue(textin, textout):
    com=input(textin)
    com=str.split(com)[0]
    try:
        var = float(com)
        print(textout % var)
        return var
    except ValueError:
        raise
        
def nmtoJ(wavelength):
    '''
    wavelength in nanometers
    '''
    h = 6.62 * 10**-34
    c = 3 * 10**8
    
    return h * c / wavelength * 10**9
    
def testifallin(what, where):
    if isinstance(what , collections.Iterable) and isinstance(where, collections.Iterable):
        ar = []
        for item in what:
            if item in where:
                ar.append(True)
            else:
                ar.append(False)
        res = all(ar)
        return res
    else:
        return False
    
# Not used
def storeintargs(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if kwargs['Old'] == False and wrapper.checked == False:
            wrapper.initargs = args
            wrapper.kwargs = kwargs
            wrapper.checked = True
            return func(*args, **kwargs)
        elif kwargs['Old'] == True and wrapper.checked == True:
            wrapper.checked = False
            return wrapper.initargs, wrapper.kwargs
            
        return func(*args, **kwargs)
    wrapper.initargs = []
    wrapper.kwargs = {}
    wrapper.checked = False
    return wrapper
            

def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)   
    
def elongarray(a, N=1):
    """
    array evenly adds N elements between two neighbouring elements
    returns new numpy array and old positions
    """
    newar = [a[0]]
    oldpos = [0]
    pos = 0
    for s1, s2 in pairwise(a):
        for i in range(1,(N+1)):
            dif = (s2 - s1) / (N + 1)
            pos += 1
            newar.append(s1 + dif * i)
        pos += 1
        newar.append(s2)
        oldpos.append(pos)
        
    return np.array(newar), np.array(oldpos)
        
   

def commandsubstitution(commands, dev=True):
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper():
            com = ''
            if commands:
                com = commands.pop(0)
                return com
            else:
                return func() 
        return wrapper if dev else func
    return decorator
    
#commands = [['set','EXP','expthymine10mM.txt'],
#            ['set','Cq'],
#            ['set','pulse_w'],
#            ['fit'],
#            ['calc'],
#            ['save', 'Fit'],
#            ['q']
#            ]  

commands = [['set','EXP','exp.txt'],
            ['fit'],
            ['save', 'Fit'],['quit']
            ] 

@commandsubstitution(commands, dev=True)
def inputcommand(commands=[]):
    com = input('Write a command: ')
    com = " ".join(com.split()) 
    command = str.split(com)
    return command
    
