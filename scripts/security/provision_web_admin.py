"""Provision or replace a PYCONLYSE web account without exposing a password.

The generated JSON file is consumed through PYCONLYSE_AUTH_USERS_FILE.  The
password is read with getpass and is never accepted as a command-line option.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import tempfile
from pathlib import Path

from werkzeug.security import generate_password_hash


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="sad")
    parser.add_argument("--role", action="append", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load_accounts(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Existing account file must contain a JSON object")
    return data


def _password() -> str:
    first = getpass.getpass("New password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        raise RuntimeError("Passwords do not match")
    if len(first) < 12:
        raise RuntimeError("Password must contain at least 12 characters")
    return first


def _atomic_write(path: Path, accounts: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent), text=True
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(accounts, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    args = _arguments()
    output = args.output.expanduser().resolve()
    username = args.username.strip()
    roles = args.role or ["admin"]
    if not username:
        raise RuntimeError("Username must not be empty")
    if not all(role.strip() for role in roles):
        raise RuntimeError("Roles must not be empty")

    accounts = _load_accounts(output)
    accounts[username] = {
        "password_hash": generate_password_hash(_password(), method="scrypt"),
        "roles": list(dict.fromkeys(role.strip() for role in roles)),
    }
    _atomic_write(output, accounts)
    print(f"Provisioned {username!r} in {output}")
    print(f"Set PYCONLYSE_AUTH_USERS_FILE={output}")
    if os.name == "nt":
        print(
            "Restrict this file's Windows ACL to the web-service account and administrators."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
