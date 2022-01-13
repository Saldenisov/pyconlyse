import unittest

from pylonemutestcase import PylonEmuTestCase


class ImportTestSuite(PylonEmuTestCase):
    # These are only "mounted" into the pylon namespace. So we ensure these are available here also
    def test_import_exceptions(self):
        pass


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
