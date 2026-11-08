"""Create a new random shared key without displaying or overwriting secrets."""
from __future__ import print_function
import argparse
import binascii
import os


def main():
    parser = argparse.ArgumentParser(description="Create private ACQ HTTP shared key")
    parser.add_argument("path", help="new key file; existing files are never overwritten")
    args = parser.parse_args()
    path = os.path.abspath(args.path)
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(binascii.hexlify(os.urandom(32)) + b"\n")
    print("Created key file: {0}; value not displayed".format(path))


if __name__ == "__main__":
    main()
