#!/usr/bin/env python3
"""Deprecated: this path never restarts Netio servers."""


def main() -> int:
    print("DEPRECATED_DRY_RUN: Netio restart is disabled.")
    print("Use scripts/refactor/restart_tango_servers.py with exact --server, --target,")
    print("--expected-commit, --apply, and a human-created external approval TOML.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
