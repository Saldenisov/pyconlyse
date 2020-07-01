#!/usr/bin/env python
import os
import unittest


def load_tests(loader, tests, pattern):
    suite = unittest.defaultTestLoader.discover( os.path.join(thisdir, 'pylon_tests', 'utils'), pattern='*test.py')
    return suite

if __name__ == "__main__":
    unittest.main()