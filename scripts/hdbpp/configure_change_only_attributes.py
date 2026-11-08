"""Configure code-pushed HDB++ attributes without periodic heartbeat samples.

The command is a dry run unless ``--apply`` is supplied.  The initial
``acceptance`` profile must pass before the health-monitor profile is applied.
"""

from __future__ import annotations

import argparse
import json


PROFILES = {
    "acceptance": (
        "test/hdbpp/probe/value",
        "test/hdbpp/probe/sequence",
        "test/hdbpp/probe/last_changed_at_utc",
    ),
    "health-monitor": (
        "sys/health/elyse/last_transition_json",
        "sys/health/elyse/last_critical_event_json",
        "sys/health/elyse/unreachable_devices_json",
        "sys/health/elyse/transition_count",
        "sys/health/elyse/critical_event_count",
    ),
    "laser-pointing-sessions": (
        "manip/v0/laserpointing-cam1/alignment_session_event_json",
        "manip/v0/laserpointing-cam1/alignment_session_event_count",
        "manip/v0/laserpointing-cam1/alignment_reference_json",
        "manip/v0/laserpointing-cam1/alignment_reference_revision",
        "manip/v0/laserpointing-cam2/alignment_session_event_json",
        "manip/v0/laserpointing-cam2/alignment_session_event_count",
        "manip/v0/laserpointing-cam2/alignment_reference_json",
        "manip/v0/laserpointing-cam2/alignment_reference_revision",
    ),
}


def _existing_attributes(configuration_manager) -> set[str]:
    try:
        values = configuration_manager.command_inout("AttributeSearch", "")
    except Exception:
        values = ()
    return {str(value).lower() for value in values or ()}


def configure_attribute(configuration_manager, attribute_name: str, archiver: str):
    configuration_manager.write_attribute("SetAttributeName", attribute_name)
    configuration_manager.write_attribute("SetPollingPeriod", 0)
    configuration_manager.write_attribute("SetAbsoluteEvent", 0.0)
    configuration_manager.write_attribute("SetRelativeEvent", 0.0)
    configuration_manager.write_attribute("SetPeriodEvent", 0)
    configuration_manager.write_attribute("SetCodePushedEvent", True)
    configuration_manager.write_attribute("SetArchiver", archiver)
    configuration_manager.write_attribute("SetTTL", 0)
    configuration_manager.write_attribute("SetStrategy", "ALWAYS")
    configuration_manager.command_inout("AttributeAdd")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--configuration-manager", default="archiving/hdbpp/cm")
    parser.add_argument("--archiver", default="archiving/hdbpp/es01")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    attributes = PROFILES[args.profile]
    print(
        json.dumps(
            {
                "profile": args.profile,
                "periodic_archiving": False,
                "code_pushed_archive_events": True,
                "attributes": attributes,
            },
            indent=2,
        )
    )
    if not args.apply:
        print("Dry run only; pass --apply after HDB++ acceptance prerequisites pass.")
        return 0

    from tango import DeviceProxy

    manager = DeviceProxy(args.configuration_manager)
    existing = _existing_attributes(manager)
    for attribute_name in attributes:
        if attribute_name.lower() in existing:
            print(f"Already configured: {attribute_name}")
            continue
        configure_attribute(manager, attribute_name, args.archiver)
        print(f"Configured change-only: {attribute_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
