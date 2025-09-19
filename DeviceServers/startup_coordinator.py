#!/usr/bin/env python3
"""Startup delay coordinator for DS_Basler_camera
Prevents concurrent camera initialization conflicts by staggering startups
"""

import tempfile
import time
from pathlib import Path


class StartupCoordinator:
    """Coordinates staggered startup delays for camera device servers"""

    def __init__(self, device_type="basler_camera"):
        self.device_type = device_type
        self.lock_dir = Path(tempfile.gettempdir()) / "pyconlyse_startup_locks"
        self.lock_dir.mkdir(exist_ok=True)
        self.counter_file = self.lock_dir / f"{device_type}_startup_counter.txt"
        self.base_delay = 5  # 5 seconds per instance

    def get_startup_delay(self):
        """Get the startup delay for this instance (0, 5, 10, 15... seconds)"""
        try:
            # Create or read counter file with file locking
            counter = self._get_and_increment_counter()
            delay_seconds = counter * self.base_delay

            print(f"[StartupCoordinator] This is instance #{counter + 1}")
            print(f"[StartupCoordinator] Startup delay: {delay_seconds} seconds")

            return delay_seconds

        except Exception as e:
            print(f"[StartupCoordinator] Error calculating delay: {e}")
            return 0  # Default to no delay on error

    def _get_and_increment_counter(self):
        """Atomically read and increment the startup counter (Windows-compatible)"""
        max_retries = 10
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                # Read current counter
                if self.counter_file.exists():
                    try:
                        with open(self.counter_file) as f:
                            counter = int(f.read().strip())
                    except (OSError, ValueError):
                        counter = 0
                else:
                    counter = 0

                # Write incremented counter
                with open(self.counter_file, "w") as f:
                    f.write(str(counter + 1))

                return counter

            except OSError as e:
                # File is being used by another process, retry
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                    continue
                print(f"[StartupCoordinator] Failed to access counter file: {e}")
                # Fallback: use timestamp-based approach
                return int(time.time()) % 4

    def cleanup_on_shutdown(self):
        """Clean up counter on normal shutdown"""
        try:
            if self.counter_file.exists():
                # Decrement counter
                with open(self.counter_file) as f:
                    counter = int(f.read().strip())

                new_counter = max(0, counter - 1)
                with open(self.counter_file, "w") as f:
                    f.write(str(new_counter))

                print(f"[StartupCoordinator] Decremented counter to {new_counter}")

        except Exception as e:
            print(f"[StartupCoordinator] Cleanup error: {e}")


def wait_for_startup_delay(device_type="basler_camera"):
    """Convenience function to add startup delay"""
    coordinator = StartupCoordinator(device_type)
    delay = coordinator.get_startup_delay()

    if delay > 0:
        print(f"[Startup Delay] Waiting {delay} seconds to avoid conflicts...")
        for i in range(delay, 0, -1):
            print(f"[Startup Delay] Starting in {i} seconds...")
            time.sleep(1)
        print("[Startup Delay] Delay complete, proceeding with initialization")

    return coordinator
