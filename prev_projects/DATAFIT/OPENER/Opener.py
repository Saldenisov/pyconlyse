'''
Created on 17 avr. 2015

@author: saldenisov 
'''

from OPENER import hamamatsuopener, asciiopener
from ERRORS import NoSuchFileType, OpenerError

import logging
import os.path

module_looger = logging.getLogger(__name__)


class Opener:
    '''
    Opener is used to open data file depending file type
    and collect Data as a numpy double array, time_array
    and wavelength_array as numpy arrays.
    *.IMG, Wavelength explicit format (*.dat, *.''), XY (*.txt, *.csv)
    '''

    def __init__(self, filepath=None):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.__filepath = filepath
        self.__filetype = None
        self.__reader = None
        self.__data = None
        self.__timedelays = None
        self.__wavelengths = None
        # Set reader
        self.__set_reader()

    def read_data(self, reader=None):
        """
        Read file and updates self.data, self.wavelengths,
        self.timedelays
        """
        if not reader:
            reader = self.__reader
        else:
            self.__reader = reader

        try:
            file_opened = reader(self.filepath)
        except (NoSuchFileType, FileNotFoundError, RuntimeError, ValueError) as e:
            self.logger.error(e)
            raise OpenerError
        else:
            self.__data = file_opened['data']
            self.__timedelays = file_opened['timedelays']
            self.__wavelengths = file_opened['wavelengths']
            self.logger.info('Data were loaded: ' + self.filepath)

    def __set_reader(self, filepath=None):
        try:
            if not filepath:
                filepath = self.filepath
            fileextension = os.path.splitext(self.filepath)[1]
            if fileextension == '.dat' \
               or fileextension == '.txt' \
               or fileextension == '.csv':
                self.__reader = asciiopener
            elif fileextension == '.img':
                self.__reader = hamamatsuopener
            else:
                raise NoSuchFileType
        except NoSuchFileType as e:
            self.logger.error(e)
            raise OpenerError

    @property
    def filepath(self):
        return self.__filepath

    @filepath.setter
    def filepath(self, filepath):
        self.__filepath = filepath

    @property
    def data(self):
        return self.__data

    @property
    def timedelays(self):
        return self.__timedelays

    @property
    def wavelengths(self):
        return self.__wavelengths
