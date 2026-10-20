"""One retained Tango read flight, including potentially blocking creation.

Import is inert. The application owns one service shared by all requests. A
caller waits only until the original flight deadline. A blocked daemon worker
is NOT killed, abandoned or replaced: later requests fail promptly until it
actually exits. Late replies are discarded, never cached for a later request.
Only the injected factory/source provider may know Tango; no command API exists.
"""
import math
import os
import threading
import time


DEVICE = "tango://10.20.30.202:10000/elyse/acquisition/runtime"


class RuntimeReadUnavailable(RuntimeError):
    pass


class _Flight:
    def __init__(self, started, deadline):
        self.started, self.deadline = started, deadline
        self.done = threading.Event()
        self.thread = None
        self.expired = False
        self.result = None
        self.error = None


class RuntimeAttributeReader:
    """Single-flight service; independent complete reads, never a value cache."""
    def __init__(self, proxy_factory, direct_source, timeout=2.0, clock=time.monotonic):
        if not callable(proxy_factory) or not callable(direct_source) or not callable(clock):
            raise ValueError("Injected read-only Tango boundaries required")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 2:
            raise ValueError("Runtime web read wait must be in (0, 2] seconds")
        self._factory, self._source, self._clock = proxy_factory, direct_source, clock
        self._timeout = timeout
        self._pid = os.getpid()
        self._lock = threading.RLock()
        self._flight = None
        self._closed = False

    def _now(self):
        value = self._clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise RuntimeReadUnavailable("Invalid runtime web read clock")
        return value

    def _remaining(self, flight):
        now = self._now()
        if now < flight.started:
            raise RuntimeReadUnavailable("Runtime web read clock moved backwards")
        return min(self._timeout, max(0.0, flight.deadline - now))

    def _execute(self, flight):
        try:
            proxy = self._factory(DEVICE)
            proxy.set_timeout_millis(1500)
            proxy.set_source(self._source())  # Proxy-local DEV, no device write.
            state, attribute = proxy.read_attributes(["State", "runtime_json"])
            if state.has_failed or attribute.has_failed:
                raise RuntimeReadUnavailable("Tango runtime attributes unavailable")
            completed = self._now()
            elapsed = completed - flight.started
            with self._lock:
                if self._closed or flight.expired or completed > flight.deadline or elapsed < 0:
                    flight.expired = True
                    flight.error = RuntimeReadUnavailable("Late runtime reply discarded")
                else:
                    flight.result = (attribute.value, str(state.value), elapsed)
        except Exception as error:
            with self._lock:
                flight.error = error
                flight.result = None
        finally:
            flight.done.set()

    def read(self):
        # Normal deployment is Windows. A pre-fork consumer must not inherit
        # an old thread/lock and silently manufacture a second read owner.
        if os.getpid() != self._pid:
            raise RuntimeReadUnavailable("Runtime web reader inherited across processes")
        with self._lock:
            if self._closed:
                raise RuntimeReadUnavailable("Runtime web reader closed")
            current = self._flight
            if current is not None and current.thread.is_alive():
                if current.expired or current.done.is_set():
                    raise RuntimeReadUnavailable("Previous runtime read still owns its worker")
                flight = current  # Coalesce only concurrent, unexpired callers.
            else:
                started = self._now()
                flight = _Flight(started, started + self._timeout)
                self._flight = flight
                flight.thread = threading.Thread(target=self._execute, args=(flight,),
                                                  name="ACQ-runtime-web-read", daemon=True)
                flight.thread.start()
            try:
                remaining = self._remaining(flight)
            except Exception:
                flight.expired = True
                flight.result = None
                raise
        try:
            completed = flight.done.wait(remaining)
            if completed:
                # Completion means all I/O ended; wait for actual thread exit
                # too, avoiding an immediate caller racing the epilogue.
                flight.thread.join(self._remaining(flight))
            with self._lock:
                now = self._now()
                if not completed or now > flight.deadline or now < flight.started or flight.expired:
                    raise RuntimeReadUnavailable("Runtime web read caller deadline exceeded")
                if flight.error is not None:
                    raise RuntimeReadUnavailable("Runtime Tango read failed") from flight.error
                if flight.result is None:
                    raise RuntimeReadUnavailable("Runtime Tango read returned no current reply")
                raw, state, worker_elapsed = flight.result
                # Include caller/coalesced-thread scheduling after the worker
                # completed, not merely the proxy I/O duration.
                return raw, state, max(worker_elapsed, now - flight.started)
        except Exception:
            with self._lock:
                flight.expired = True
                flight.result = None
            raise

    def close(self, join_timeout=0.1):
        """Tests/app shutdown may stop admission; blocked worker stays owned."""
        if os.getpid() != self._pid:
            return False
        with self._lock:
            self._closed = True
            flight = self._flight
            if flight is not None:
                flight.expired = True
                flight.result = None
        if flight is None:
            return True
        if flight.thread is not threading.current_thread():
            flight.thread.join(join_timeout)
        return not flight.thread.is_alive()
