# -*- coding: utf-8 -*-
"""Install the pinned XP/Python 3.4 runtime without network access."""

from __future__ import print_function

import os
import struct
import sys
import traceback


BUNDLE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_PATH = os.path.join(BUNDLE_DIR, "install-offline.log")
PACKAGE_FILES = (
    "six-1.16.0-py2.py3-none-any.whl",
    "numpy-1.15.4-cp34-none-win32.whl",
    "nidaqmx-0.5.7-py2.py3-none-any.whl",
)


def log(message):
    line = str(message)
    print(line)
    with open(LOG_PATH, "a") as stream:
        stream.write(line + "\n")


def fail(message):
    log("ERROR: " + message)
    raise RuntimeError(message)


def validate_runtime():
    if sys.version_info[:2] != (3, 4):
        fail("Python 3.4 is required; found %s" % (sys.version,))
    if struct.calcsize("P") * 8 != 32:
        fail("32-bit Python is required")
    for filename in PACKAGE_FILES:
        path = os.path.join(BUNDLE_DIR, filename)
        if not os.path.isfile(path):
            fail("Missing offline package: %s" % filename)


def load_pip():
    try:
        import pip
        return pip
    except ImportError:
        log("pip is absent; bootstrapping bundled pip with ensurepip")
        import ensurepip
        ensurepip.bootstrap()
        import pip
        return pip


def install_packages(pip_module):
    paths = [os.path.join(BUNDLE_DIR, name) for name in PACKAGE_FILES]
    args = ["install", "--no-index", "--no-deps", "--upgrade"] + paths
    log("Installing pinned packages from local files only")
    result = pip_module.main(args)
    if result not in (None, 0):
        fail("pip returned exit code %s" % result)


def validate_imports():
    import nidaqmx
    import numpy
    import six
    log("Python: %s" % sys.version.replace("\n", " "))
    log("numpy: %s" % numpy.__version__)
    log("six: %s" % six.__version__)
    log("nidaqmx: %s" % getattr(nidaqmx, "__version__", "0.5.7"))


def main():
    with open(LOG_PATH, "w") as stream:
        stream.write("ELYSE XP Python offline installation\n")
    validate_runtime()
    pip_module = load_pip()
    install_packages(pip_module)
    validate_imports()
    log("INSTALLATION_OK")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        with open(LOG_PATH, "a") as stream:
            traceback.print_exc(file=stream)
        raise
