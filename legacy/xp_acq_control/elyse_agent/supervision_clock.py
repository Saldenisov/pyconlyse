"""Daily SuperVision clock sync with the authenticated Everest time source."""

import binascii
import ctypes
import datetime
import hashlib
import hmac
import json
import os
import re
import threading
import time
import urllib.request


CLOCK_PATH = "/api/elyse/supervision/clock"
EVEREST_CLOCK = "http://10.20.30.202:5000" + CLOCK_PATH
DAY_SECONDS = 86400
RETRY_SECONDS = 3600


def valid_nonce(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def clock_signature(key, nonce, utc_ms):
    message = "supervision-clock-v1\n{}\n{}".format(nonce, utc_ms).encode("ascii")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def read_clock_sample(key):
    nonce = binascii.hexlify(os.urandom(16)).decode("ascii")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.monotonic()
    with opener.open(EVEREST_CLOCK + "?nonce=" + nonce, timeout=2) as response:
        raw = response.read(1025)
    rtt = time.monotonic() - started
    if rtt > 1 or len(raw) > 1024:
        raise ValueError("Everest clock response exceeded its latency or size limit")
    sample = json.loads(raw.decode("ascii"))
    stamp = sample.get("utc_ms")
    signature = sample.get("signature")
    if (sample.get("nonce") != nonce or type(stamp) is not int or not valid_nonce(nonce)
            or not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature)
            or not hmac.compare_digest(signature, clock_signature(key, nonce, stamp))):
        raise ValueError("Everest clock response failed verification")
    return stamp / 1000.0 + rtt / 2 - time.time()


class SystemTime(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ushort) for name in (
        "year", "month", "weekday", "day", "hour", "minute", "second", "millisecond")]


def set_clock_offset(offset):
    utc = datetime.datetime.utcfromtimestamp(time.time() + offset)
    value = SystemTime(utc.year, utc.month, 0, utc.day, utc.hour, utc.minute,
                       utc.second, utc.microsecond // 1000)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel.SetSystemTime(ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())


def reconcile_clock(key, read=read_clock_sample, adjust=set_clock_offset):
    offsets = sorted(read(key) for _ in range(3))
    if offsets[-1] - offsets[0] > 0.5:
        raise ValueError("Everest clock samples disagree")
    offset = offsets[1]
    if not -60 <= offset <= 60:
        raise ValueError("SuperVision clock offset exceeds 60 seconds")
    if abs(offset) >= 1:
        adjust(offset)
        return dict(state="ADJUSTED", offset_seconds=offset)
    return dict(state="IN_SYNC", offset_seconds=offset)


class DailyClockSync(object):
    def __init__(self, key, report_path):
        self.key, self.report_path = key, report_path
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="SUP-daily-clock", daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop_event.set()

    def run(self):
        while not self.stop_event.is_set():
            try:
                result = reconcile_clock(self.key)
                interval = DAY_SECONDS
            except Exception as error:
                result = dict(state="ERROR", error=str(error))
                interval = RETRY_SECONDS
            result.update(checked_at_utc=datetime.datetime.utcnow().isoformat() + "Z",
                          next_check_seconds=interval)
            try:
                with open(self.report_path + ".new", "w", encoding="ascii") as destination:
                    json.dump(result, destination, sort_keys=True)
                os.replace(self.report_path + ".new", self.report_path)
            except OSError:
                pass
            self.stop_event.wait(interval)
