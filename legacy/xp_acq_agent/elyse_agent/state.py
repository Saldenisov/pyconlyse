from __future__ import division

import datetime
import threading
import time


class AgentState(object):
    def __init__(self, config):
        self._lock = threading.RLock()
        self._started_monotonic = time.time()
        self._started_utc = datetime.datetime.utcnow().isoformat() + "Z"
        self._request_count = 0
        self._last_discovery = None
        self._config = dict(config)

    def count_request(self):
        with self._lock:
            self._request_count += 1

    def record_discovery(self, result):
        with self._lock:
            self._last_discovery = result

    def snapshot(self):
        with self._lock:
            return {
                "agent_name": self._config["agent_name"],
                "mode": self._config["mode"],
                "started_utc": self._started_utc,
                "uptime_seconds": round(time.time() - self._started_monotonic, 3),
                "request_count": self._request_count,
                "input_task_creation_allowed": bool(
                    self._config.get("allow_input_task_creation", False)
                ),
                "hardware_writes_allowed": False,
                "last_discovery": self._last_discovery,
            }
