"""
Test Runner
===========

Run all unit tests for the dual OD application.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_tests(verbosity=2):
    """Run all unit tests.
    
    Parameters
    ----------
    verbosity : int
        Test output verbosity (1=minimal, 2=detailed)
        
    Returns
    -------
    bool
        True if all tests passed
    """
    # Discover and run all tests in the tests directory
    loader = unittest.TestLoader()
    tests_dir = Path(__file__).parent
    suite = loader.discover(str(tests_dir), pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
