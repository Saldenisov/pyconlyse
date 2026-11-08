"""Run the loopback-only offline SuperVision analysis service."""

import argparse
from pathlib import Path

from .application import OfflineSupervision
from .http import OfflineHTTPServer
from .store import ShadowJournal


def main() -> None:
    supervision = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--journal", type=Path, default=supervision / "offline_state/shadow.sqlite3")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    journal = ShadowJournal(args.journal)
    server = None
    try:
        app = OfflineSupervision(journal, supervision_root=supervision)
        server = OfflineHTTPServer(("127.0.0.1", args.port), app, supervision / "web_prototype")
        print(f"Offline SuperVision: http://127.0.0.1:{server.server_port}/ · NO HARDWARE EXECUTION", flush=True)
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        journal.close()


if __name__ == "__main__":
    main()
