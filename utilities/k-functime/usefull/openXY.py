# -*- coding: utf-8 -*-
"""
Created on Wed Nov 16 09:18:13 2016

@author: saldenisov
"""
import os.path
import numpy as np


from .myexceptions import MyException,WrongExtensionError, DataSizeException, WrongCommand

def openXYtxt(command):
    """
    Exports data in double array from two-column XY txt-file tab-separated.
    """
    def openvalidfile(filename):
        with open(filename, encoding='utf-8') as file:
            data = np.loadtxt(file)
            if data.shape[1] != 2:
                if data.shape[1] > 2:
                    text = 'more than 2'
                elif data.shape[1] < 2:
                    text = 'less than 2'
                raise DataSizeException(text)
            elif data.shape[1] == 2:
                X = data[:,0]
                Y = data[:,1]
                if X[1] < X[0]:
                    X = X[::-1]
                    Y = Y[::-1]
        return X, Y

    X = []
    Y = []
    try:
        if len(command) == 1:
            filename = command[0]
        else:
            raise WrongCommand('No file_name, or to many parameters')
        
        if not os.path.isfile(filename):
            raise FileNotFoundError('File not found')

        if filename.endswith('.txt'):
            X, Y = openvalidfile(filename)
        else:
            raise WrongExtensionError('txt')
        return X, Y

    except (MyException, FileNotFoundError) as e:
        raise e

