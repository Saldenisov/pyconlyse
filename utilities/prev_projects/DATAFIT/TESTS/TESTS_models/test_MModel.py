'''
Created on 7 juil. 2016

@author: saldenisov
'''

import unittest

from ERRORS import GraphModelError
from MODEL import MModel


class TestMainModel(unittest.TestCase):

    def setUp(self):
        self.model = MModel()


    def test_create_graph_error(self):
        """
        For example wrong file name
        """
        filepath = 'C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\tests_files\\test_.img'
        with self.assertRaises(GraphModelError):
            self.model.create_graph(filepath)


if __name__ == '__main__':
    unittest.main()