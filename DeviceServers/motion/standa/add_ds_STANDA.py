import argparse

from tango import Database, DbDevInfo

db = Database()

ALIGNMENT_STANDA_DEVICES = {
    "elyse/motorized_devices/mm1_x",
    "elyse/motorized_devices/mm1_y",
    "elyse/motorized_devices/mm2_x",
    "elyse/motorized_devices/mm2_y",
    "manip/v0/mm3_x",
    "manip/v0/mm3_y",
    "manip/v0/mm4_x",
    "manip/v0/mm4_y",
}

ALIGNMENT_STANDA_POWER_PROPERTIES = {
    "power_dependency_device": "manip/V0/PDU_VO",
    "power_dependency_output_id": 3,
    "power_on_settle_seconds": 5.0,
    # A powered Standa DS must be immediately usable after startup or recovery.
    "power_dependency_auto_turn_on": 1,
}

STANDA_RELIABILITY_PROPERTIES = {
    # One host-level scan is shared briefly by all Standa server processes.
    "usb_discovery_lock_timeout_s": 15.0,
    "usb_discovery_cache_ttl_s": 30.0,
    # Retry only idempotent reads after libximc resets its transmission state.
    "usb_read_retry_count": 1,
    "usb_read_retry_delay_s": 0.05,
    # Vendor recommendation for command_wait_for_stop; 5 ms doubled traffic.
    "wait_time": 10,
    "resume_connection_after_loss": 1,
    # Open, verify, stop safely, and read the axis position during DS startup.
    "initialize_on_startup": 1,
    # These controllers are local COM/USB devices; network probing adds noise.
    "enumerate_network_devices": 0,
}

names = {
    "00003D73": [
        "ELYSE/motorized_devices",
        "StandaI_X",
        "MM1_X",
        [-10, 0, 10],
        [-300, 300],
        15731,
        ["step", 1],
    ],
    "00003D6A": [
        "ELYSE/motorized_devices",
        "StandaI_Y",
        "MM1_Y",
        [-10, 0, 10],
        [-300, 300],
        15722,
        ["step", 1],
    ],
    "000043D6": [
        "ELYSE/motorized_devices",
        "StandaII_X",
        "MM2_X",
        [-10, 0, 10],
        [-300, 300],
        17366,
        ["step", 1],
    ],
    "000043CF": [
        "ELYSE/motorized_devices",
        "StandaII_Y",
        "MM2_Y",
        [-10, 0, 10],
        [-300, 300],
        17359,
        ["step", 1],
    ],
    "00003D98": [
        "manip/V0",
        "StandaIII_X",
        "MM3_X",
        [-10, 0, 10],
        [-300, 300],
        15768,
        ["step", 1],
    ],
    "00003D8F": [
        "manip/V0",
        "StandaIII_Y",
        "MM3_Y",
        [-10, 0, 10],
        [-300, 300],
        15759,
        ["step", 1],
    ],
    "000043F3": [
        "manip/V0",
        "IrisExp_1",
        "DV01",
        [0, 5, 10, 15, 25, 40, 100],
        [0, 100],
        17395,
        ["%", 20.61],
    ],
    "000043D9": [
        "manip/V0",
        "IrisExp_2",
        "DV02",
        [0, 5, 10, 15, 25, 40, 100],
        [0, 100],
        17369,
        ["%", 21.85],
    ],
    "00004A38": [
        "manip/V0",
        "IrisExp_3",
        "DV03",
        [0, 5, 10, 15, 25, 40, 100],
        [0, 100],
        19000,
        ["%", 22.46],
    ],
    "00004A3E": [
        "manip/V0",
        "IrisExp_4",
        "DV04",
        [0, 5, 10, 15, 25, 40, 100],
        [0, 100],
        19006,
        ["%", 22.38],
    ],
    "000043CA": [
        "manip/V0",
        "ShutterExp_1",
        "S1",
        [-1, 1],
        [-1.1, 1.1],
        17354,
        ["state", 1250],
    ],
    "000043FE": [
        "manip/V0",
        "ShutterExp_2",
        "S2",
        [-1, 1],
        [-1.1, 1.1],
        17406,
        ["state", 1250],
    ],
    "00004A15": [
        "manip/V0",
        "ShutterOPA",
        "S3",
        [-1, 1],
        [-1.1, 1.1],
        18965,
        ["state", 1250],
    ],
    "00004A10": [
        "manip/V0",
        "Flipper_1",
        "F1",
        [-1, 1],
        [-1.1, 1.1],
        18960,
        ["state", 1250],
    ],
    "00007A58": [
        "manip/V0",
        "Lambda_2_Exp",
        "L-2_1",
        [0, 5, 10, 15, 20, 50, 100],
        [0, 100],
        31320,
        ["%", 37.00],
    ],
    "00003B37": [
        "manip/V0",
        "StandaIV_X",
        "MM4_X",
        [-10, 0, 10],
        [-300, 300],
        15159,
        ["step", 1],
    ],
    "00003B1B": [
        "manip/V0",
        "StandaIV_Y",
        "MM4_Y",
        [-10, 0, 10],
        [-300, 300],
        15131,
        ["step", 1],
    ],
    "00004402": [
        "manip/V0",
        "OPA_output_X",
        "OPA_X",
        [-10, 0, 10],
        [-300, 300],
        17410,
        ["step", 1],
    ],
    "000043D4": [
        "manip/V0",
        "OPA_output_Y",
        "OPA_Y",
        [-10, 0, 10],
        [-300, 300],
        17364,
        ["step", 1],
    ],
    "000043E3": [
        "manip/V0",
        "translation_stage_SC_mirror",
        "TS_SC_m",
        [-3, 0, 3],
        [0, 15],
        17379,
        ["mm", 833.3333],
    ],
    "000043DE": [
        "manip/V0",
        "translation_stage_OPA_m",
        "TS_OPA_m",
        [-10, 0, 10],
        [-100, 100],
        17374,
        ["mm", 833.3333],
    ],
    "000043F5": [
        "ELYSE/motorized_devices",
        "IrisElyse_1",
        "DE1",
        [0, 9.2, 15, 20, 25, 40, 100],
        [0, 100],
        17397,
        ["%", 21.59],
    ],
    "000043FC": [
        "ELYSE/motorized_devices",
        "IrisElyse_2",
        "DE2",
        [0, 10, 15, 20, 25, 40, 100],
        [0, 100],
        17404,
        ["%", 22.32],
    ],
    "00003B20": [
        "ELYSE/motorized_devices",
        "ELYSE_X",
        "MME_X",
        [-10, 0, 10],
        [-300, 300],
        15136,
        ["step", 1],
    ],
    "00003B1C": [
        "ELYSE/motorized_devices",
        "ELYSE_Y",
        "MME_Y",
        [-10, 0, 10],
        [-300, 300],
        15132,
        ["step", 1],
    ],
}


def register_alignment_standa_power_dependencies(database=None):
    """Register the shared output-3 dependency for exactly eight mount axes."""

    target_db = database or db
    for device_name in sorted(ALIGNMENT_STANDA_DEVICES):
        target_db.put_device_property(
            device_name, dict(ALIGNMENT_STANDA_POWER_PROPERTIES)
        )


def register_standa_reliability_properties(database=None):
    """Apply transport reliability defaults to every registered Standa axis."""

    target_db = database or db
    for val in names.values():
        target_db.put_device_property(
            f"{val[0]}/{val[2]}", dict(STANDA_RELIABILITY_PROPERTIES)
        )


def main(power_dependencies_only=False, reliability_properties_only=False):
    if power_dependencies_only:
        register_alignment_standa_power_dependencies()
        return
    if reliability_properties_only:
        register_standa_reliability_properties()
        return

    i = 1
    a = []
    for uri, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f"{val[0]}/{val[2]}"
        dev_info.name = dev_name
        dev_info._class = "DS_Standa_Motor"
        dev_info.server = f"DS_Standa_Motor/{i}_{val[2]}"
        a.append(f"{i}_{val[2]}")
        db.add_device(dev_info)
        properties = {
            "ip_address": "10.20.30.204",
            "uri": uri,
            "friendly_name": val[1],
            "wait_time": 10,
            "server_id": i,
            "preset_pos": val[3],
            "limit_min": val[4][0],
            "limit_max": val[4][1],
            "real_pos": 0.0,
            "device_id": val[5],
            "unit": val[6][0],
            "conversion": val[6][1],
            "always_on": 1,
            **STANDA_RELIABILITY_PROPERTIES,
        }
        if dev_name.lower() in ALIGNMENT_STANDA_DEVICES:
            properties.update(ALIGNMENT_STANDA_POWER_PROPERTIES)
        db.put_device_property(dev_name, properties)

        i += 1
    # print(a)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--power-dependencies-only",
        action="store_true",
        help="Only register PDU output 3 for the eight alignment Standas.",
    )
    parser.add_argument(
        "--reliability-properties-only",
        action="store_true",
        help="Only register the Standa transport reliability properties.",
    )
    args = parser.parse_args()
    main(
        power_dependencies_only=args.power_dependencies_only,
        reliability_properties_only=args.reliability_properties_only,
    )
