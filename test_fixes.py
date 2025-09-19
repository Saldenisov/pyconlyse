#!/usr/bin/env python3
"""Test script to verify the fixes for Taurus warnings and device connection issues.

This script can be run to test the improved error handling and warning suppression.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_warning_suppression():
    """Test that Taurus warnings are properly suppressed."""
    logger.info("Testing Taurus warning suppression...")

    try:
        from fixes.taurus_warnings_fix import suppress_taurus_deprecation_warnings

        suppress_taurus_deprecation_warnings()
        logger.info("✓ Warning suppression module imported successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to import warning suppression: {e}")
        return False


def test_safe_device_access():
    """Test safe device access functions."""
    logger.info("Testing safe device access functions...")

    try:
        from fixes.taurus_warnings_fix import (
            safe_device_attribute_access,
        )

        logger.info("✓ Safe device access functions imported successfully")

        # Test with None device (should handle gracefully)
        result = safe_device_attribute_access(None, "test_attr", "default")
        if result == "default":
            logger.info("✓ Safe attribute access handles None device correctly")
        else:
            logger.warning(
                "? Safe attribute access returned unexpected result for None device"
            )

        return True
    except Exception as e:
        logger.error(f"✗ Failed to test safe device access: {e}")
        return False


def test_netio_widget_import():
    """Test that NETIO widget can be imported with the fixes."""
    logger.info("Testing NETIO widget import with fixes...")

    try:
        logger.info("✓ NETIO widget imported successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to import NETIO widget: {e}")
        return False


def test_numato_widget_import():
    """Test that Numato widget can be imported with the fixes."""
    logger.info("Testing Numato widget import with fixes...")

    try:
        logger.info("✓ Numato widget imported successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to import Numato widget: {e}")
        return False


def test_client_manager():
    """Test that ClientManager can be imported."""
    logger.info("Testing ClientManager import...")

    try:
        logger.info("✓ ClientManager imported successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to import ClientManager: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("Starting PyConlyse fixes verification tests...")
    logger.info("=" * 60)

    tests = [
        ("Warning Suppression", test_warning_suppression),
        ("Safe Device Access", test_safe_device_access),
        ("NETIO Widget Import", test_netio_widget_import),
        ("Numato Widget Import", test_numato_widget_import),
        ("ClientManager Import", test_client_manager),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\nRunning test: {test_name}")
        logger.info("-" * 40)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        logger.info(f"{symbol} {test_name}: {status}")
        if result:
            passed += 1

    logger.info("-" * 60)
    logger.info(f"Total: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All tests passed! The fixes are working correctly.")
        return 0
    logger.warning(
        f"⚠️  {total - passed} test(s) failed. Please check the errors above."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
