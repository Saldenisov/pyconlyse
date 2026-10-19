from __future__ import print_function

import datetime
import json
import os
import threading


class AuditLog(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self._lock = threading.Lock()
        parent = os.path.dirname(self.path)
        if not os.path.isdir(parent):
            os.makedirs(parent)

    def write(self, event, **fields):
        record = {
            "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
            "event": str(event),
        }
        record.update(fields)
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self._lock:
            with open(self.path, "a") as stream:
                stream.write(encoded + "\n")
        return record
