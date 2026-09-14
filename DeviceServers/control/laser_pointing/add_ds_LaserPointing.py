import json
from collections import OrderedDict as od

from tango import Database, DbDevInfo

db = Database()


names = {
    "LaserPointingV0_Cam1": [
        "manip/V0",
        "LaserPointing-Cam1",
        "Cam1",
        {
            "Camera": "manip/V0/Cam1_V0",
            "MainLaserDiaphragm1": "elyse/motorized_devices/de1",
            "Shutter1": "manip/V0/s1",
            "CrimpingDiaphragm1": "manip/V0/dv01",
            "CrimpingDiaphragm2": "manip/V0/dv02",
            "ActuatorX1": "elyse/motorized_devices/mm1_x",
            "ActuatorY1": "elyse/motorized_devices/mm1_y",
            "ActuatorX2": "elyse/motorized_devices/mm2_x",
            "ActuatorY2": "elyse/motorized_devices/mm2_y",
            "HalfWavePlate1": "manip/V0/L-2_1",
        },
        od(
            {
                "Laser Parameters": ("MainLaserDiaphragm1", "HalfWavePlate1"),
                "Shutters": ("Shutter1"),
                "Crimping Diaphragms": ("CrimpingDiaphragm1", "CrimpingDiaphragm2"),
                "Actuators 1": ("ActuatorX1", "ActuatorY1"),
                "Actuators 2": ("ActuatorX2", "ActuatorY2"),
            }
        ),
        # Basler1 optical sequence: points 1-3 close the first downstream
        # diaphragm; points 4-6 close the second. The Elyse entry diaphragm is
        # held near 10% for a small, accurately positioned beam.
        od(
            {
                "point1": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": -1,
                    "CrimpingDiaphragm1": 40,
                    "CrimpingDiaphragm2": 60,
                    "HalfWavePlate1": 100,
                },
                "point2": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": -1,
                    "CrimpingDiaphragm1": 20,
                    "CrimpingDiaphragm2": 60,
                    "HalfWavePlate1": 100,
                },
                "point3": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": -1,
                    "CrimpingDiaphragm1": 10,
                    "CrimpingDiaphragm2": 60,
                    "HalfWavePlate1": 100,
                },
                "point4": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": -1,
                    "CrimpingDiaphragm1": 60,
                    "CrimpingDiaphragm2": 40,
                    "HalfWavePlate1": 100,
                },
                "point5": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": -1,
                    "CrimpingDiaphragm1": 60,
                    "CrimpingDiaphragm2": 20,
                    "HalfWavePlate1": 100,
                },
                "point6": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": -1,
                    "CrimpingDiaphragm1": 60,
                    "CrimpingDiaphragm2": 10,
                    "HalfWavePlate1": 100,
                },
            }
        ),
        {"group1": ("point1", "point3"), "group2": ("point4", "point6")},
    ],
    "LaserPointingV0_Cam2": [
        "manip/V0",
        "LaserPointing-Cam2",
        "Cam2",
        {
            "Camera": "manip/V0/Cam2_V0",
            "MainLaserDiaphragm1": "elyse/motorized_devices/de1",
            "MainLaserDiaphragm2": "manip/V0/dv01",
            "Shutter1": "manip/V0/s1",
            "Shutter2": "manip/V0/s2",
            "CrimpingDiaphragm1": "manip/V0/dv02",
            "CrimpingDiaphragm2": "manip/V0/dv03",
            "ActuatorX3": "manip/V0/mm3_x",
            "ActuatorY3": "manip/V0/mm3_y",
            "ActuatorX4": "manip/V0/mm4_x",
            "ActuatorY4": "manip/V0/mm4_y",
            "HalfWavePlate1": "manip/V0/L-2_1",
            # Route through the OWIS Aggregator: axis 3 is the long delay line
            # (backed by DS_OWIS_PS90_IP - the 3-axis TCP controller).
            "TranslationStage1": ("manip/general/DS_OWIS_Aggregator", [3]),
        },
        od(
            {
                "Laser Parameters": (
                    "MainLaserDiaphragm1",
                    "MainLaserDiaphragm2",
                    "HalfWavePlate1",
                ),
                "Shutters": ("Shutter1", "Shutter2"),
                "Crimping Diaphragms": ("CrimpingDiaphragm1", "CrimpingDiaphragm2"),
                "Actuators 1": ("ActuatorX3", "ActuatorY3"),
                "Actuators 2": ("ActuatorX4", "ActuatorY4"),
                "Translation stages": ("TranslationStage1"),
            }
        ),
        # Basler2 optical sequence: points 1-3 observe the near propagation
        # plane; points 4-6 move the translation stage to -700 for a more
        # sensitive, long-distance position/angle constraint.
        od(
            {
                "point1": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": 1,
                    "Shutter2": -1,
                    "MainLaserDiaphragm2": 80,
                    "HalfWavePlate1": 100,
                    "TranslationStage1": (3, 0),
                    "CrimpingDiaphragm1": 30,
                    "CrimpingDiaphragm2": 40,
                },
                "point2": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": 1,
                    "Shutter2": -1,
                    "MainLaserDiaphragm2": 80,
                    "HalfWavePlate1": 100,
                    "TranslationStage1": (3, 0),
                    "CrimpingDiaphragm1": 30,
                    "CrimpingDiaphragm2": 20,
                },
                "point3": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": 1,
                    "Shutter2": -1,
                    "MainLaserDiaphragm2": 80,
                    "HalfWavePlate1": 100,
                    "TranslationStage1": (3, 0),
                    "CrimpingDiaphragm1": 30,
                    "CrimpingDiaphragm2": 10,
                },
                "point4": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": 1,
                    "Shutter2": -1,
                    "MainLaserDiaphragm2": 80,
                    "HalfWavePlate1": 100,
                    "TranslationStage1": (3, -700),
                    "CrimpingDiaphragm1": 30,
                    "CrimpingDiaphragm2": 40,
                },
                "point5": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": 1,
                    "Shutter2": -1,
                    "MainLaserDiaphragm2": 80,
                    "HalfWavePlate1": 100,
                    "TranslationStage1": (3, -700),
                    "CrimpingDiaphragm1": 30,
                    "CrimpingDiaphragm2": 20,
                },
                "point6": {
                    "MainLaserDiaphragm1": 9.2,
                    "Shutter1": 1,
                    "Shutter2": -1,
                    "MainLaserDiaphragm2": 80,
                    "HalfWavePlate1": 100,
                    "TranslationStage1": (3, -700),
                    "CrimpingDiaphragm1": 30,
                    "CrimpingDiaphragm2": 10,
                },
                "working": {
                    "MainLaserDiaphragm1": 100,
                    "Shutter1": 1,
                    "Shutter2": -1,
                    "MainLaserDiaphragm2": 100,
                    "HalfWavePlate1": 20.5,
                    "TranslationStage1": (3, 0),
                    "CrimpingDiaphragm1": 100,
                    "CrimpingDiaphragm2": 100,
                },
            }
        ),
        {"group1": ("point1", "point3"), "group2": ("point4", "point6")},
    ],
    "LaserPointingV0_Cam3": [
        "manip/V0",
        "LaserPointing-Cam3",
        "Cam3",
        {
            "Camera": "manip/V0/Cam3_V0",
            "MainLaserDiaphragm1": "elyse/motorized_devices/de1",
            "MainLaserDiaphragm2": "manip/V0/dv01",
            "Shutter1": "manip/V0/s1",
            "Shutter2": "manip/V0/s2",
            "CrimpingDiaphragm1": "manip/V0/dv02",
            "CrimpingDiaphragm2": "manip/V0/dv03",
            "ActuatorX3": "manip/V0/mm3_x",
            "ActuatorY3": "manip/V0/mm3_y",
            "ActuatorX4": "manip/V0/mm4_x",
            "ActuatorY4": "manip/V0/mm4_y",
            "HalfWavePlate1": "manip/V0/L-2_1",
            # Route through the OWIS Aggregator: axis 3 is the long delay line
            # (backed by DS_OWIS_PS90_IP - the 3-axis TCP controller).
            "TranslationStage1": ("manip/general/DS_OWIS_Aggregator", [3]),
        },
        od(
            {
                "Laser Parameters": (
                    "MainLaserDiaphragm1",
                    "MainLaserDiaphragm2",
                    "HalfWavePlate1",
                ),
                "Shutters": ("Shutter1", "Shutter2"),
                "Crimping Diaphragms": ("CrimpingDiaphragm1", "CrimpingDiaphragm2"),
                "Actuators 1": ("ActuatorX3", "ActuatorY3"),
                "Actuators 2": ("ActuatorX4", "ActuatorY4"),
                "Translation stages": ("TranslationStage1"),
            }
        ),
        od(
            {
                "starting_point": {
                    "MainLaserDiaphragm": 9.2,
                    "Shutter1": -1,
                    "CrimpingDiaphragm": 20,
                }
            }
        ),
        {},
    ],
}


def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f"{val[0]}/{val[1]}"
        dev_info.name = dev_name
        dev_info._class = "DS_LaserPointing"
        dev_info.server = f"DS_LaserPointing/{i}_{val[2]}"
        db.add_device(dev_info)
        db.put_device_property(
            dev_name,
            {
                "device_id": dev_id,
                "friendly_name": val[1],
                "server_id": i,
                "ds_dict": str(val[3]),
                "groups": str(val[4]),
                "controller_rules": str(val[5]),
                "pid_groups": str(val[6]),
                "automatic_search_defaults": json.dumps(
                    {
                        "mode": "sensitive",
                        "initial_step": 10.0,
                        "minimum_step": 2.0,
                        "step_schedule": [10.0, 6.0, 2.0],
                        "radius": 30.0,
                        "tolerance_px": 2.0,
                        "minimum_improvement_px": 0.1,
                        "unchanged_response_tolerance_px": 0.25,
                        "probe_repetitions": 3,
                        "max_evaluations": 16,
                        "max_cycles": 2,
                        "samples": 3,
                        "sample_interval_s": 0.2,
                        "camera_frame_wait_s": 0.25,
                        "motion_timeout_s": 180.0,
                        "motion_poll_s": 0.2,
                        "position_tolerance": 0.05,
                        "position_stable_reads": 2,
                        "groups": [],
                        "point_pairs": {},
                        "restore_point": "",
                    }
                ),
            },
        )
        i += 1


if __name__ == "__main__":
    main()
