"""Configuration defaults and physical constants for V0 pump-probe."""

from pathlib import Path

PIXELS = 512
STAGE_MIN_MM = -900.0
STAGE_MAX_MM = 100.0
MM_PER_PS = 0.0749481145
STAGE_SPEED_MM_PER_SEC = 1.0
ACCELERATOR_HZ = 5.0
# The CCD is triggered at accelerator cadence; each trigger produces a 3-shot burst.
SPECTROMETER_HZ = 5.0
SPECTROMETER_BURST = 3
LAMP_DRIFT_FRACTION = 0.00015
DARK_DRIFT_COUNTS = 3.5
READ_NOISE_COUNTS = 3.0
SIGNAL_RANDOM_COUNTS = 5
REFERENCE_RANDOM_COUNTS = 5
BACKGROUND_RANDOM_COUNTS = 3
OD_NOISE_SCALE = 0.0020
OD_COMMON_OSCILLATION = 0.0011
DEFAULT_DATA_ROOT = "smb://10.20.30.202/e/DATA_VD"
DEFAULT_DG645_RECALL_CONFIG = str(Path(__file__).resolve().parents[1] / "pump_probe" / "config" / "v0_directline_dg645_recall8.json")
DEFAULT_HARDWARE_CONFIG = {
    "control_mode": "emulator",
    "owis_aggregator_device": "manip/general/DS_OWIS_Aggregator",
    "owis_backend_device": "manip/general/DS_OWIS_PS90_IP",
    "delay_line_axis": 3,
    "delay_line_label": "Delay line long",
    "delay_line_device_name": "manip/V0/DLl1_V0",
    "sample_stage_axis": 1,
    "sample_stage_label": "Sample holder V0",
    "sample_stage_device_name": "manip/V0/DLs_V0",
    "andor_device": "manip/CR/ANDOR_CCD1",
    "dg645_device": "manip/sync/DG645",
    "dg645_recall_config": DEFAULT_DG645_RECALL_CONFIG,
    "dg645_preflight_policy": "apply_recall_then_verify",
    "daqmx_device": "control/DAQ/DAQMX_1",
    "daqmx_counter_channel": "ELYSE Pulse Counter",
}

REQUIRED_NETIO_OUTPUTS = [
    {"key": "uv_vis", "label": "UV-visible detector", "device": "manip/SD1/PDU_SD1", "output_id": 1},
    {"key": "dg645", "label": "DG645", "device": "manip/SD2/PDU_SD2", "output_id": 2},
    {"key": "power_control", "label": "Power control", "device": "manip/SD2/PDU_SD2", "output_id": 3},
    {"key": "power_current", "label": "Power current", "device": "manip/SD2/PDU_SD2", "output_id": 4},
]
