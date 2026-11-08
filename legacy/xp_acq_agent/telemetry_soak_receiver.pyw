"""Manual synthetic-only test launcher. Does not start on import."""
import os
from elyse_agent.telemetry_soak import run_gui

if __name__ == '__main__':
    run_gui(os.path.dirname(os.path.abspath(__file__)))
