'''
Created on 6 juil. 2016

@author: saldenisov
'''

import unittest
import numpy as np
from OPENER import Opener
from ERRORS.Myexceptions import NoSuchFileType, OpenerError


class TestOpener(unittest.TestCase):

    def test_tabsepfile_Opener(self):
        """
        Two column tab-separated file
        """
        filepath1 = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_1.txt'
        file_open = Opener(filepath1)
        file_open.read_data()
        self.assertEqual(len(file_open.timedelays), 10)
        self.assertEqual(all(file_open.timedelays == np.arange(10)), True)

    def test_datfile_Opener(self):
        """
        TRABS in dat format
        """
        filepath2 = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_2.txt'
        file_open = Opener(filepath2)
        file_open.read_data()
        self.assertEqual(all(file_open.timedelays == [1, 2, 3, 4, 5]), True)
        self.assertEqual(all(file_open.wavelengths == [1, 2, 3, 4, 5]), True)
        check = file_open.data == np.ones((5,5))
        self.assertEqual(check.all(), True)

    def test_errorinfile_Opener(self):
        """
        MsgError in file .->,
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_error.txt'
        file_open = Opener(filepath)
        with self.assertRaises(OpenerError):
            file_open.read_data()

    def test_noexisting_Opener(self):
        """
        Non-existing file
        """
        filepath3 = 'testASCII_2.txt'

        with self.assertRaises(OpenerError):
            file_open = Opener(filepath3)
            file_open.read_data()

    def test_wrongtype_Opener(self):
        """
        Wrong type file
        """
        filepath3 = 'testASCII_2.docx'

        with self.assertRaises(OpenerError):
            file_open = Opener(filepath3)
            file_open.read_data()

    def test_imgfile_HamamatsuOpener(self):
        """
        '.img' format
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\test.img'
        file_open = Opener(filepath)
        file_open.read_data()
        self.assertEqual(len(file_open.timedelays), 512)
        self.assertEqual(len(file_open.wavelengths), 512)


if __name__ == '__main__':
    unittest.main()