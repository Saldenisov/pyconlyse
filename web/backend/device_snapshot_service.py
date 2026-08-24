"""Import-inert read-only device discovery and snapshot cache service."""

import threading
import time
from typing import Callable


class DeviceSnapshotService:
    """Build and cache read-only Tango device-list snapshots.

    Tango construction and per-device proxy/retry behavior are injected by the
    HTTP layer. Importing this module therefore performs no Tango, Flask, or
    background-thread work.
    """

    def __init__(
        self,
        database_factory: Callable[[], object],
        read_device_snapshot: Callable[[str, object, object], tuple[str, object, object]],
        *,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        thread_factory: Callable[..., threading.Thread] = threading.Thread,
    ):
        self._database_factory = database_factory
        self._read_device_snapshot = read_device_snapshot
        self._clock = clock
        self._sleeper = sleeper
        self._thread_factory = thread_factory
        self._cache = {}
        self._cache_lock = threading.RLock()
        self._refreshing = set()
        self._monitor_started = False
        self._monitor_lock = threading.Lock()

    def collect(self, probe_state, include_dserver, include_admin):
        """Read one coherent device snapshot without retaining a Tango client."""
        database = self._database_factory()
        device_list = []
        for raw_device_name in database.get_device_exported("*"):
            device_name = str(raw_device_name)
            lower_name = device_name.lower()
            if not include_dserver and lower_name.startswith("dserver/"):
                continue
            if not include_admin and lower_name.startswith("tango/admin/"):
                continue

            server_name = None
            dev_class = None
            state = "UNKNOWN"
            available = True
            try:
                info = database.get_device_info(device_name)
                server_name = getattr(info, "ds_full_name", None) or getattr(info, "server", None)
                dev_class = getattr(info, "class_name", None)
            except Exception:
                pass

            if probe_state:
                try:
                    state, server_name, dev_class = self._read_device_snapshot(
                        device_name,
                        server_name,
                        dev_class,
                    )
                except Exception:
                    available = False

            device_list.append(
                {
                    "name": device_name,
                    "state": state,
                    "server": server_name,
                    "class": dev_class,
                    "available": available,
                }
            )

        device_list.sort(key=lambda item: str(item.get("name", "")))
        return device_list

    def refresh(self, cache_key):
        """Refresh one cache key and always release its one-flight marker."""
        probe_state, include_dserver, include_admin = cache_key
        try:
            devices = self.collect(probe_state, include_dserver, include_admin)
            with self._cache_lock:
                self._cache[cache_key] = {"ts": self._clock(), "devices": devices}
        finally:
            with self._cache_lock:
                self._refreshing.discard(cache_key)

    def schedule_refresh(self, cache_key):
        """Start at most one daemon refresh for one cache key."""
        with self._cache_lock:
            if cache_key in self._refreshing:
                return False
            self._refreshing.add(cache_key)

        thread = self._thread_factory(
            target=self.refresh,
            args=(cache_key,),
            name=f"tango-device-snapshot-{cache_key[0]}",
            daemon=True,
        )
        thread.start()
        return True

    def get_snapshot(
        self,
        probe_state,
        include_dserver,
        include_admin,
        *,
        refresh=False,
        stale_ok=False,
        cache_ttl_s=4.0,
        schedule_refresh=None,
    ):
        """Return a fresh or cached snapshot with established response metadata."""
        cache_key = (probe_state, include_dserver, include_admin)
        now = self._clock()
        with self._cache_lock:
            cached_entry = self._cache.get(cache_key)
            refreshing = cache_key in self._refreshing

        is_cached = (
            not refresh
            and cached_entry
            and (
                stale_ok
                or (now - cached_entry.get("ts", 0)) <= max(cache_ttl_s, 0.0)
            )
        )
        if is_cached:
            if stale_ok and not refreshing:
                (schedule_refresh or self.schedule_refresh)(cache_key)
            return {
                "devices": cached_entry.get("devices", []),
                "cached": True,
                "probe_state": probe_state,
                "snapshot_age_s": round(now - cached_entry.get("ts", now), 3),
                "refreshing": refreshing,
            }

        devices = self.collect(probe_state, include_dserver, include_admin)
        with self._cache_lock:
            self._cache[cache_key] = {"ts": now, "devices": devices}
        return {
            "devices": devices,
            "cached": False,
            "probe_state": probe_state,
        }

    def start_monitor(self, interval_s=10.0):
        """Start the one-shot snapshot warmer without import side effects."""
        with self._monitor_lock:
            if self._monitor_started:
                return False
            self._monitor_started = True

        cache_key = (True, True, True)
        interval = max(5.0, float(interval_s))

        def monitor():
            while True:
                self.schedule_refresh(cache_key)
                self._sleeper(interval)

        thread = self._thread_factory(
            target=monitor,
            name="tango-device-snapshot-monitor",
            daemon=True,
        )
        thread.start()
        return True
