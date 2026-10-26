"""One cold local SuperVision orchestrator; no card initialization at startup."""
import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from elyse_agent.supervision_gui import main
    main(os.path.abspath(__file__))
