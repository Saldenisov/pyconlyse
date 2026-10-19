#!/usr/bin/env python
"""Compatibility launcher for the EXISTING acquisition agent, not another server.

New invocations should use main.py --supervision. The old independent HTTP
prototype is no longer launched by this entry point.
"""
from __future__ import print_function

import os
import sys
from main import main as agent_main


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    defaults = ["--supervision"]
    if "--config" not in arguments:
        defaults += ["--config", os.path.join(os.path.dirname(__file__), "config.simulation.xp.json")]
    return agent_main(defaults + arguments)


if __name__ == "__main__":
    raise SystemExit(main())
