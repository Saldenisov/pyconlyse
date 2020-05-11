'''
Created on 6 juil. 2016

@author: saldenisov
'''

import unittest
import numpy as np
from OPENER import hamamatsuopener
from ERRORS.Myexceptions import NoSuchFileType
from struct import error as StructError


class TestHamamatsuFileOpener(unittest.TestCase):

    def test_imgfile_HamamatsuOpener(self):
        """
        '.img' format
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\test.img'
        file_open = hamamatsuopener(filepath)
        self.assertEqual(len(file_open['timedelays']), 512)
        self.assertEqual(len(file_open['wavelengths']), 512)

    def test_errorimgfile_HamamatsuOpener(self):
        """
        '.img' format error
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\test_error.img'
        with self.assertRaises(RuntimeError):
            hamamatsuopener(filepath)

    def test_noexisting_HamamatsuOpener(self):
        """
        Non-existing file
        """
        filepath = 'testASCII_2.img'
        with self.assertRaises(FileNotFoundError):
            hamamatsuopener(filepath)

    def test_wrongtype_HamamatsuOpener(self):
        """
        Wrong file type
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_1.txt'
        with self.assertRaises(NoSuchFileType):
            hamamatsuopener(filepath)

if __name__ == '__main__':
    unittest.main()