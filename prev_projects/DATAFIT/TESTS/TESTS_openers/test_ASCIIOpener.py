'''
Created on 6 juil. 2016

@author: saldenisov
'''

import unittest
import numpy as np
from OPENER import asciiopener
from ERRORS.Myexceptions import NoSuchFileType


class TestASCIIOpener(unittest.TestCase):

    def test_tabsepfile_ASCIIOpener(self):
        """
        Two column tab-separated file
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_1.txt'
        file_open = asciiopener(filepath)
        self.assertEqual(len(file_open['timedelays']), 10)
        self.assertEqual(all(file_open['timedelays'] == np.arange(10)), True)


    def test_errorinfile_ASCIIOpener(self):
        """
        Error in file .->,
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_error.txt'
        with self.assertRaises(ValueError):
            asciiopener(filepath)

    def test_datfile_ASCIIOpener(self):
        """
        TRABS in dat format
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_2.txt'
        file_open = asciiopener(filepath)
        self.assertEqual(all(file_open['timedelays'] == [1, 2, 3, 4, 5]), True)
        self.assertEqual(all(file_open['wavelengths'] == [1, 2, 3, 4, 5]), True)
        check = file_open['data'] == np.ones((5,5))
        self.assertEqual(check.all(), True)

    def test_noexisting_ASCIIOpener(self):
        """
        Non-existing file
        """
        filepath = 'Non-existing.txt'
        with self.assertRaises(FileNotFoundError):
            asciiopener(filepath)

    def test_wrongtype_ASCIIOpener(self):
        """
        Wrong file type
        """
        filepath = 'Wrong file type.img'
        with self.assertRaises(NoSuchFileType):
            asciiopener(filepath)

    def test_csv_txt_ASCIIOpener(self):
        """
        CSV file in txt
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_4.txt'
        file_open = asciiopener(filepath)
        self.assertEqual(len(file_open['timedelays']), 10)
        self.assertEqual(all(file_open['timedelays'] == np.arange(10)), True)

    def test_csv_ASCIIOpener(self):
        """
        CSV file
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\testASCII_5.csv'
        file_open = asciiopener(filepath)
        self.assertEqual(len(file_open['timedelays']), 10)
        self.assertEqual(all(file_open['timedelays'] == np.arange(10)), True)


if __name__ == '__main__':
    unittest.main()