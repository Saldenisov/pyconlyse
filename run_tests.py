#!/usr/bin/env python3
"""
PyConlyse Test Runner

This script provides a convenient way to run all tests in the organized test structure.
Run with different options to target specific test categories.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit             # Run only unit tests  
    python run_tests.py --integration      # Run only integration tests
    python run_tests.py --device-servers   # Run only device server tests
    python run_tests.py --gui              # Run only GUI tests
    python run_tests.py --utilities        # Run only utility tests
    python run_tests.py --verbose          # Run with verbose output
    python run_tests.py --pattern "test_*" # Run tests matching pattern
"""

import argparse
import os
import sys
import unittest
import subprocess
from pathlib import Path

def discover_and_run_tests(test_dir, pattern="test*.py", verbosity=1):
    """Discover and run tests in the specified directory."""
    if not os.path.exists(test_dir):
        print(f"Test directory {test_dir} does not exist.")
        return False
    
    loader = unittest.TestLoader()
    suite = loader.discover(test_dir, pattern=pattern)
    
    if suite.countTestCases() == 0:
        print(f"No tests found in {test_dir}")
        return True
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def main():
    parser = argparse.ArgumentParser(description="Run PyConlyse tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--device-servers", action="store_true", help="Run device server tests")
    parser.add_argument("--gui", action="store_true", help="Run GUI tests")
    parser.add_argument("--utilities", action="store_true", help="Run utility tests")
    parser.add_argument("--legacy", action="store_true", help="Run legacy tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--pattern", default="test*.py", help="Test file pattern")
    
    args = parser.parse_args()
    
    # Get the project root directory
    project_root = Path(__file__).parent
    tests_dir = project_root / "tests"
    
    verbosity = 2 if args.verbose else 1
    success = True
    
    # If no specific test category is specified, run all tests
    if not any([args.unit, args.integration, args.device_servers, 
                args.gui, args.utilities, args.legacy]):
        print("Running all tests...")
        success = discover_and_run_tests(str(tests_dir), args.pattern, verbosity)
    else:
        # Run specific test categories
        if args.unit:
            print("Running unit tests...")
            success &= discover_and_run_tests(str(tests_dir / "unit"), args.pattern, verbosity)
        
        if args.integration:
            print("Running integration tests...")
            success &= discover_and_run_tests(str(tests_dir / "integration"), args.pattern, verbosity)
        
        if args.device_servers:
            print("Running device server tests...")
            success &= discover_and_run_tests(str(tests_dir / "device_servers"), args.pattern, verbosity)
        
        if args.gui:
            print("Running GUI tests...")
            success &= discover_and_run_tests(str(tests_dir / "gui"), args.pattern, verbosity)
        
        if args.utilities:
            print("Running utility tests...")
            success &= discover_and_run_tests(str(tests_dir / "utilities"), args.pattern, verbosity)
        
        if args.legacy:
            print("Running legacy tests...")
            success &= discover_and_run_tests(str(tests_dir / "legacy"), args.pattern, verbosity)
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()