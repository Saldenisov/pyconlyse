from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = REPO_ROOT / "web" / "pump_probe" / "config" / "v0_directline_dg645_recall8.json"
DEFAULT_DEVICE = "manip/sync/DG645"
DEFAULT_SLOT = 8

CHANNEL_NAMES = {
    0: "T0",
    1: "T1",
    2: "A",
    3: "B",
    4: "C",
    5: "D",
    6: "E",
    7: "F",
    8: "G",
    9: "H",
}

OUTPUT_NAMES = {
    0: "T0",
    1: "AB",
    2: "CD",
    3: "EF",
    4: "GH",
}

BASE_QUERIES = [
    "*IDN?",
    "TSRC?",
    "TRAT?",
    "TLVL?",
    "ADVT?",
    "HOLD?",
    "INHB?",
    "TIMB?",
    "BURM?",
    "BURC?",
    "BURD?",
    "BURP?",
    "BURT?",
    "SSBC?",
    "SSBD?",
    "SSBP?",
    "SSTR?",
    "SSTL?",
    "SSHD?",
]


def query_plan() -> list[str]:
    queries = list(BASE_QUERIES)
    queries.extend(f"PRES?{index}" for index in range(5))
    queries.extend(f"PHAS?{index}" for index in range(1, 5))
    queries.extend(f"SSPS?{index}" for index in range(5))
    queries.extend(f"SSPH?{index}" for index in range(1, 5))
    queries.extend(f"DLAY?{index}" for index in range(10))
    queries.extend(f"LINK?{index}" for index in range(2, 10))
    queries.extend(f"LAMP?{index}" for index in range(5))
    queries.extend(f"LOFF?{index}" for index in range(5))
    queries.extend(f"LPOL?{index}" for index in range(5))
    queries.extend(f"SSLA?{index}" for index in range(5))
    queries.extend(f"SSLO?{index}" for index in range(5))
    queries.extend(f"SSDL?{index}" for index in range(6, 10))
    return queries


def tango_device(name: str) -> DeviceProxy:
    from tango import DeviceProxy

    tango_host = os.environ.get("TANGO_HOST")
    if not tango_host:
        print("Warning: TANGO_HOST is not set; using Tango defaults")
    return DeviceProxy(name)


def scpi_write(dev: DeviceProxy, command: str) -> None:
    dev.command_inout("scpi_write", command)


def scpi_query(dev: DeviceProxy, command: str) -> str:
    return str(dev.command_inout("scpi_query", command)).strip()


def parse_delay(value: str) -> dict[str, Any]:
    reference, delay_s = [part.strip() for part in value.split(",", 1)]
    reference_index = int(float(reference))
    return {
        "reference": reference_index,
        "reference_name": CHANNEL_NAMES.get(reference_index, str(reference_index)),
        "delay_s": float(delay_s),
    }


def as_float(raw: dict[str, str], command: str) -> float:
    return float(raw[command])


def as_int(raw: dict[str, str], command: str) -> int:
    return int(float(raw[command]))


def build_settings(raw: dict[str, str]) -> dict[str, Any]:
    delays = {}
    for index in range(10):
        key = f"DLAY?{index}"
        if key not in raw:
            continue
        delays[CHANNEL_NAMES[index]] = {
            "channel": index,
            **parse_delay(raw[key]),
        }

    outputs = {}
    for index in range(5):
        name = OUTPUT_NAMES[index]
        outputs[name] = {
            "output": index,
            "amplitude_v": as_float(raw, f"LAMP?{index}"),
            "offset_v": as_float(raw, f"LOFF?{index}"),
            "polarity": as_int(raw, f"LPOL?{index}"),
            "step_amplitude_v": as_float(raw, f"SSLA?{index}"),
            "step_offset_v": as_float(raw, f"SSLO?{index}"),
        }

    return {
        "trigger": {
            "source": as_int(raw, "TSRC?"),
            "rate_hz": as_float(raw, "TRAT?"),
            "level_v": as_float(raw, "TLVL?"),
            "advanced_triggering": as_int(raw, "ADVT?"),
            "holdoff_s": as_float(raw, "HOLD?"),
            "inhibit_mode": as_int(raw, "INHB?"),
            "timebase": as_int(raw, "TIMB?"),
        },
        "burst": {
            "enabled": as_int(raw, "BURM?"),
            "count": as_int(raw, "BURC?"),
            "delay_s": as_float(raw, "BURD?"),
            "period_s": as_float(raw, "BURP?"),
            "t0_config": as_int(raw, "BURT?"),
        },
        "delays": delays,
        "outputs": outputs,
        "prescale": {str(index): as_int(raw, f"PRES?{index}") for index in range(5)},
        "phase": {str(index): as_int(raw, f"PHAS?{index}") for index in range(1, 5)},
        "step": {
            "burst_count": as_int(raw, "SSBC?"),
            "burst_delay_s": as_float(raw, "SSBD?"),
            "burst_period_s": as_float(raw, "SSBP?"),
            "trigger_rate_hz": as_float(raw, "SSTR?"),
            "trigger_level_v": as_float(raw, "SSTL?"),
            "holdoff_s": as_float(raw, "SSHD?"),
            "prescale": {str(index): as_int(raw, f"SSPS?{index}") for index in range(5)},
            "phase": {str(index): as_int(raw, f"SSPH?{index}") for index in range(1, 5)},
            "delay_s": {CHANNEL_NAMES[index]: as_float(raw, f"SSDL?{index}") for index in range(6, 10)},
        },
    }


def restore_commands(settings: dict[str, Any]) -> list[str]:
    trigger = settings["trigger"]
    burst = settings["burst"]
    step = settings["step"]

    commands = [
        f"TSRC {trigger['source']}",
        f"TRAT {trigger['rate_hz']:.12g}",
        f"TLVL {trigger['level_v']:.12g}",
        f"ADVT {trigger['advanced_triggering']}",
        f"HOLD {trigger['holdoff_s']:.12g}",
        f"INHB {trigger['inhibit_mode']}",
        f"TIMB {trigger['timebase']}",
        f"BURM {burst['enabled']}",
        f"BURC {burst['count']}",
        f"BURD {burst['delay_s']:.12g}",
        f"BURP {burst['period_s']:.12g}",
        f"BURT {burst['t0_config']}",
        f"SSBC {step['burst_count']}",
        f"SSBD {step['burst_delay_s']:.12g}",
        f"SSBP {step['burst_period_s']:.12g}",
        f"SSTR {step['trigger_rate_hz']:.12g}",
        f"SSTL {step['trigger_level_v']:.12g}",
        f"SSHD {step['holdoff_s']:.12g}",
    ]

    for key, value in settings["prescale"].items():
        commands.append(f"PRES {key},{value}")
    for key, value in settings["phase"].items():
        commands.append(f"PHAS {key},{value}")
    for key, value in step["prescale"].items():
        commands.append(f"SSPS {key},{value}")
    for key, value in step["phase"].items():
        commands.append(f"SSPH {key},{value}")

    name_to_index = {name: index for index, name in CHANNEL_NAMES.items()}
    for name, delay in settings["delays"].items():
        channel = name_to_index[name]
        commands.append(f"DLAY {channel},{delay['reference']},{delay['delay_s']:.12g}")

    output_to_index = {name: index for index, name in OUTPUT_NAMES.items()}
    for name, output in settings["outputs"].items():
        index = output_to_index[name]
        commands.extend(
            [
                f"LAMP {index},{output['amplitude_v']:.12g}",
                f"LOFF {index},{output['offset_v']:.12g}",
                f"LPOL {index},{output['polarity']}",
                f"SSLA {index},{output['step_amplitude_v']:.12g}",
                f"SSLO {index},{output['step_offset_v']:.12g}",
            ]
        )

    for name, value in step["delay_s"].items():
        commands.append(f"SSDL {name_to_index[name]},{value:.12g}")

    return commands


def capture(args: argparse.Namespace) -> None:
    dev = tango_device(args.device)
    scpi_write(dev, "*CLS")
    if not args.no_recall:
        scpi_write(dev, f"*RCL {args.slot}")
        time.sleep(args.wait_s)
        try:
            scpi_query(dev, "*OPC?")
        except Exception:
            pass

    raw: dict[str, str] = {}
    errors: dict[str, str] = {}
    for command in query_plan():
        try:
            raw[command] = scpi_query(dev, command)
        except Exception as exc:
            errors[command] = str(exc).splitlines()[0]

    settings = build_settings(raw)
    config = {
        "schema_version": 1,
        "experiment": "V0 DirectLine pump-probe",
        "description": "DG645 Recall 8 preset used by the V0 DirectLine experiment. It enables the boost/burst timing needed for acquisition.",
        "device": args.device,
        "recall_slot": args.slot,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "transport": "Tango scpi_query/scpi_write",
        "safety": {
            "startup_policy": "Do not send *RCL 8 from DS_DG645 startup. Apply this preset explicitly from the experiment configurator.",
            "save_policy": "Use *SAV 8 only after manual confirmation; it overwrites DG645 recall memory slot 8.",
        },
        "settings": settings,
        "restore": {
            "apply_commands": restore_commands(settings),
            "save_recall_slot_command": f"*SAV {args.slot}",
            "verification_queries": query_plan(),
        },
        "snapshot": {
            "raw_queries": raw,
            "query_errors": errors,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


def apply_config(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text(encoding="utf-8"))
    dev = None if args.dry_run else tango_device(args.device or config["device"])
    commands = config["restore"]["apply_commands"]

    for command in commands:
        if args.dry_run:
            print(command)
        else:
            assert dev is not None
            scpi_write(dev, command)

    if args.save_to_recall_slot:
        save_command = config["restore"]["save_recall_slot_command"]
        if args.dry_run:
            print(save_command)
        else:
            assert dev is not None
            scpi_write(dev, save_command)

    if not args.dry_run:
        print(f"Applied {len(commands)} commands from {args.config}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture/apply DG645 recall preset JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--device", default=DEFAULT_DEVICE)
    capture_parser.add_argument("--slot", type=int, default=DEFAULT_SLOT)
    capture_parser.add_argument("--output", type=Path, default=DEFAULT_CONFIG)
    capture_parser.add_argument("--wait-s", type=float, default=1.0)
    capture_parser.add_argument("--no-recall", action="store_true")
    capture_parser.set_defaults(func=capture)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    apply_parser.add_argument("--device", default="")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.add_argument("--save-to-recall-slot", action="store_true")
    apply_parser.set_defaults(func=apply_config)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
