"""Operator launcher for the telemetry-only Python 3.4 shared-state bridge."""
import os

from elyse_agent.shared_state_receiver import run_gui

if __name__ == "__main__":
    run_gui(os.path.dirname(os.path.abspath(__file__)))
