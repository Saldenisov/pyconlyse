'''
Created on 23 avr. 2015

@author: saldenisov
'''

# import logging
import os

import numpy as np
from ERRORS import NoSuchFileType


# module_logger = logging.getLogger(__name__)


def asciiopener(filepath):
    '''
    Works as an opener for datastructures files: '.csv' and (tab- and
    ',' seperated) '.txt' files
    Two columns datastructures and multicolumn datastructures used for TRABS representation
    Wavelength(first column) vs Timedelay (first row) -->
    0    0    1    2    3    4    5    ...
    400    0    0    0    0    0
    401    0    0    0    0    0
    402    0    0    0    0    0
    ...    0    0    0    0    0
    '''
    try:
        fileextension = os.path.splitext(filepath)[1]
        if fileextension not in ('.csv', '.txt', '.dat'):
            raise NoSuchFileType
        try:
            # try to open file with tab-sep delimiter
            with open(filepath, encoding='utf-8') as file:
                data = np.loadtxt(file)
        except ValueError:
            # in case of ',' delimiter try this
            try:
                with open(filepath, encoding='utf-8') as file:
                    data = np.loadtxt(file, delimiter=',')
            except ValueError:
                raise

        # in case of two columns datastructures: (X, Y)
        if data.shape[1] == 2:
            timedelays = data[:, 0]
            # adds wavelength array in order to present datastructures as a map
            N = 100
            wavelengths = np.arange(400, 400 + N +1, dtype=float)
            _data = np.transpose(np.repeat([data[:, 1]], N + 1, 0))

        # in case of matrix datastructures representation (e.g. TRABS)
        if data.shape[1] > 5:
            timedelays = np.delete(data[0], 0)
            wavelengths = np.delete(data[:, 0], 0)
            _data = np.delete(np.delete(data, 0, axis=0), 0, axis=1)
            _data = np.transpose(_data)

    except (FileNotFoundError, NoSuchFileType):
        raise
    return {'datastructures': _data,
            'timedelays': timedelays,
            'wavelengths': wavelengths}

#===============================================================================
# class ASCIIOpener(object):
#     '''
#     Works as an opener for datastructures files: '.csv' and (tab- and
#     ',' seperated) '.txt' files
# 
#     Two columns datastructures and multicolumn datastructures used for TRABS representation
#     Wavelength(first column) vs Timedelay (first row) -->
#     0    0    1    2    3    4    5    ...
#     400    0    0    0    0    0
#     401    0    0    0    0    0
#     402    0    0    0    0    0
#     ...    0    0    0    0    0
#     '''
# 
#     def __init__(self, filepath):
#         self.logger = logging.getLogger("MAIN." + __name__)
#         self.__filepath = filepath
#         self.__data = None
#         self.__timedelays = None
#         self.__wavelengths = None
# 
#     def read_data(self):
#         try:
#             fileextension = os.path.splitext(self.filepath)[1]
#             if fileextension not in ('.csv', '.txt', '.dat'):
#                 raise NoSuchFileType
# 
#             try:
#                 with open(self.filepath, encoding='utf-8') as file:
#                     datastructures = np.loadtxt(file)
#             except ValueError:
#                 # in case of ',' delimiter try this
#                 with open(self.filepath, encoding='utf-8') as file:
#                     datastructures = np.loadtxt(file, delimiter=',')
# 
#             # in case of two columns datastructures: (X, Y)
#             if datastructures.shape[1] == 2:
#                 self.__timedelays = datastructures[:, 0]
#                 # adds wavelength array in order to present datastructures as a map
#                 self.__wavelengths = np.arange(400, 501, dtype=float)
#                 self.__data = np.repeat([datastructures[:, 1]], 100, 0)
# 
#             # in case of matrix datastructures representation (e.g. TRABS)
#             if datastructures.shape[1] > 5:
#                 self.__timedelays = np.delete(datastructures[0], 0)
#                 self.__wavelengths = np.delete(datastructures[:, 0], 0)
#                 self.__data = np.delete(np.delete(datastructures, 0, axis=0), 0, axis=1)
# 
#         except (FileNotFoundError, NoSuchFileType) as e:
#             self.logger.error(e)
#             raise
# 
#     @property
#     def filepath(self):
#         return self.__filepath
# 
#     @property
#     def datastructures(self):
#         return self.__data
# 
#     @property
#     def timedelays(self):
#         return self.__timedelays
# 
#     @property
#     def wavelengths(self):
#         return self.__wavelengths
#===============================================================================
