# -*- coding: utf-8 -*-
"""Verify and extract the ELYSE simulator update from the redirected RDP drive."""

from __future__ import print_function

import hashlib
import os
import sys
import traceback
import zipfile


ARCHIVE_NAME = "xp_acq_agent_simulator_v3.zip"
EXPECTED_SHA256 = "A6806343BDE2EDF1C93B26948F11CBCC40FDD2D77A0CE66EEE9A947DC39E2DE0"
TARGET_ROOT = r"C:\xp_elyse_deployment\xp_elyse_deployment"
TARGET_NAME = "xp_acq_agent_simulator_v3"
LOG_PATH = os.path.join(TARGET_ROOT, "xp_acq_agent_simulator_v3.install.log")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_member(name):
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        raise RuntimeError("unsafe archive path: {0}".format(name))
    parts = [part for part in normalized.split("/") if part]
    if not parts or parts[0] != TARGET_NAME or ".." in parts:
        raise RuntimeError("unexpected archive path: {0}".format(name))


def main():
    source_dir = os.path.abspath(os.path.dirname(__file__))
    archive_path = os.path.join(source_dir, ARCHIVE_NAME)
    target_path = os.path.join(TARGET_ROOT, TARGET_NAME)
    if os.path.exists(target_path):
        raise RuntimeError("target already exists: {0}".format(target_path))
    actual_hash = sha256_file(archive_path)
    if actual_hash != EXPECTED_SHA256:
        raise RuntimeError("SHA256 mismatch: {0}".format(actual_hash))
    with zipfile.ZipFile(archive_path, "r") as archive:
        for info in archive.infolist():
            validate_member(info.filename)
        archive.extractall(TARGET_ROOT)
    with open(LOG_PATH, "w") as stream:
        stream.write("ARCHIVE={0}\n".format(archive_path))
        stream.write("SHA256={0}\n".format(actual_hash))
        stream.write("TARGET={0}\n".format(target_path))
        stream.write("EXTRACTION_OK\n")
    print("EXTRACTION_OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        with open(LOG_PATH, "w") as stream:
            traceback.print_exc(file=stream)
        raise
