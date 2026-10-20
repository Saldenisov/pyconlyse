"""Cold GUI entrypoint. No NI tasks until explicit Initialize acquisition."""
import os
import sys

from elyse_agent.acquisition_gui import main


if __name__ == "__main__":
    sys.exit(main(os.path.abspath(__file__)))
