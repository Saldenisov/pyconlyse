"""Separate cold control-capable server; no automatic card initialization."""
from elyse_agent.acquisition_control_gui import main

if __name__ == "__main__":
    raise SystemExit(main(__file__))
