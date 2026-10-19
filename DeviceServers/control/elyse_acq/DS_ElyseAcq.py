#!/usr/bin/env python
"""Tango facade for the ELYSE acquisition procedure controller.

Only simulation mode is enabled in this first implementation. A production
adapter must fail closed until channel polarity, interlocks, and safe defaults
have been commissioned against the physical installation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PYCONLYSE_ROOT = Path(__file__).resolve().parents[3]
if str(_PYCONLYSE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYCONLYSE_ROOT))

from tango import AttrWriteType, DevState
from tango.server import attribute, command, device_property, run

try:
    from DeviceServers.base.DS_general import DS_General
except ModuleNotFoundError:
    from DeviceServers.base.general import DS_General

from DeviceServers.control.elyse_acq.engine import (
    ProcedureController,
    ProcedureEngine,
)
from DeviceServers.control.elyse_acq.plans import PROCEDURE_PLANS
from DeviceServers.control.elyse_acq.simulator import SimulatedHardware


class DS_ElyseAcq(DS_General):
    _version_ = "0.1"
    _model_ = "ELYSE ACQ procedure controller"

    simulation_mode = device_property(dtype=int, default_value=1)
    allow_hardware = device_property(dtype=int, default_value=0)

    def init_device(self):
        self._adapter = SimulatedHardware()
        self._engine = ProcedureEngine(self._adapter)
        self._controller = ProcedureController(self._engine)
        super().init_device()
        if not bool(int(self.simulation_mode or 0)) or bool(
            int(self.allow_hardware or 0)
        ):
            self.set_state(DevState.FAULT)
            self.set_status(
                "Production hardware adapter is intentionally disabled pending "
                "polarity and interlock commissioning."
            )
            return
        self.set_state(DevState.STANDBY)
        self.set_status("Simulation mode; no hardware writes are possible.")

    def find_device(self):
        self._device_id_internal = 1
        self._uri = b"simulation://elyse-acq"
        return 0

    @attribute(dtype=str, access=AttrWriteType.READ)
    def procedure_state_json(self) -> str:
        return json.dumps(self._engine.snapshot().as_dict(), indent=2)

    @attribute(dtype=str, access=AttrWriteType.READ)
    def hardware_snapshot_json(self) -> str:
        return json.dumps(self._adapter.snapshot(), indent=2)

    @command(dtype_out=str)
    def list_procedures_json(self) -> str:
        return json.dumps(
            [
                {
                    "name": item.name,
                    "legacy_event_case": item.legacy_event_case,
                    "description": item.description,
                    "step_count": len(item.steps),
                }
                for item in PROCEDURE_PLANS.values()
            ],
            indent=2,
        )

    @command(dtype_in=str, dtype_out=str)
    def execute_procedure_json(self, payload: str) -> str:
        request = json.loads(payload)
        if not isinstance(request, dict) or set(request) != {
            "intent_id",
            "procedure",
        }:
            raise ValueError(
                "payload must contain exactly intent_id and procedure"
            )
        snapshot = self._controller.submit(
            str(request["procedure"]), str(request["intent_id"])
        )
        self.set_state(DevState.RUNNING)
        return json.dumps(snapshot.as_dict(), indent=2)

    @command(dtype_out=str)
    def cancel_procedure(self) -> str:
        return json.dumps(self._controller.cancel().as_dict(), indent=2)

    @command(dtype_out=str)
    def get_procedure_trace_json(self) -> str:
        return self._engine.trace_json()


def main(args=None):
    return run((DS_ElyseAcq,), args=args)


if __name__ == "__main__":
    main()
