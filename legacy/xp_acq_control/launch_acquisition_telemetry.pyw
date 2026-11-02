"""Unified server and optional existing operator telemetry VI; no auto Initialize."""
from elyse_agent.acquisition_telemetry_launcher import main

if __name__ == '__main__':
    raise SystemExit(main(__file__))
