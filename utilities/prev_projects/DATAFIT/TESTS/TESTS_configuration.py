'''
Created on 4 juil. 2016

@author: saldenisov
'''

import unittest
from UTILITY import Configuration

class TestConfiguration(unittest.TestCase):

    def test_conf(self):
        conf = Configuration()
        self.assertNotEqual(conf.config, dict())
        self.assertEqual(conf.config['Fitting']['_1exp']['guess']['y0'], 0.0)
        self.assertEqual((conf.config['Fitting']['_1exp']['bounds']['y0'] == [0.0, 0.01]), True)

if __name__ == '__main__':
    unittest.main()