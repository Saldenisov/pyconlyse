"""Import-inert read-only class-based device catalog service."""


class DeviceCatalogService:
    """Build device catalog rows from injected database and state readers."""

    def list_class_devices(
        self,
        database,
        class_names,
        probe_state,
        read_state,
        *,
        deduplicate,
    ):
        """List Tango classes while preserving per-class and state-read fallbacks."""
        seen = set()
        devices = []
        for class_name in class_names:
            try:
                class_devices = database.get_device_name("*", class_name)
            except Exception:
                continue

            for raw_device_name in class_devices:
                device_name = str(raw_device_name)
                if deduplicate and device_name in seen:
                    continue
                if deduplicate:
                    seen.add(device_name)

                state = "UNKNOWN"
                available = True
                if probe_state:
                    try:
                        state = read_state(device_name)
                    except Exception:
                        available = False

                devices.append(
                    {
                        "name": device_name,
                        "class": class_name,
                        "state": state,
                        "available": available,
                    }
                )

        devices.sort(key=lambda item: item["name"])
        return devices
