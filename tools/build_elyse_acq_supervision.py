"""Build a secret-free, stdlib-only Python 3.4 simulation package (modern host)."""
import argparse
import hashlib
import json
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "legacy/xp_acq_agent"

# Original agent, not a second server. No NI task adapters, binaries, keys, DBs.
FILES = {
    "README.md": "SUPERVISION.md",
    "main.py": "main.py",
    "config.xp.json": "config.xp.json",
    "config.simulation.xp.json": "config.simulation.xp.json",
    "config.simulation.everest.json": "config.simulation.everest.json",
    "supervision_server.py": "supervision_server.py",
    "generate_supervision_key.py": "generate_supervision_key.py",
    "start_supervision.bat": "start_supervision.bat",
    "start_supervision_local.bat": "start_supervision_local.bat",
    "elyse_agent/__init__.py": "elyse_agent/__init__.py",
    "elyse_agent/supervision_wire.py": "elyse_agent/supervision_wire.py",
    "elyse_agent/supervision_runtime.py": "elyse_agent/supervision_runtime.py",
    "elyse_agent/supervision_rpc.py": "elyse_agent/supervision_rpc.py",
    "elyse_agent/supervision_setpoints.py": "elyse_agent/supervision_setpoints.py",
    "elyse_agent/supervision_lifecycle.py": "elyse_agent/supervision_lifecycle.py",
    "elyse_agent/saved_xnode.py": "elyse_agent/saved_xnode.py",
    "elyse_agent/saved_timing.py": "elyse_agent/saved_timing.py",
    "elyse_agent/saved_ni6220.py": "elyse_agent/saved_ni6220.py",
    "elyse_agent/saved_initializer.py": "elyse_agent/saved_initializer.py",
    "elyse_agent/saved_cleanup.py": "elyse_agent/saved_cleanup.py",
    "elyse_agent/saved_requests.py": "elyse_agent/saved_requests.py",
    "elyse_agent/saved_dispatch.py": "elyse_agent/saved_dispatch.py",
    "elyse_agent/saved_psp_reads.py": "elyse_agent/saved_psp_reads.py",
    "elyse_agent/saved_sup_reads.py": "elyse_agent/saved_sup_reads.py",
    "elyse_agent/saved_stop.py": "elyse_agent/saved_stop.py",
    "elyse_agent/saved_numeric.py": "elyse_agent/saved_numeric.py",
    "elyse_agent/saved_card_init.py": "elyse_agent/saved_card_init.py",
    "elyse_agent/saved_card_replay.py": "elyse_agent/saved_card_replay.py",
    "tests/test_saved_card_replay.py": "tests/test_saved_card_replay.py",
    "tests/test_saved_card_replay_rpc.py": "tests/test_saved_card_replay_rpc.py",
    "elyse_agent/saved_sup_helpers.py": "elyse_agent/saved_sup_helpers.py",
    "elyse_agent/saved_sup_replay.py": "elyse_agent/saved_sup_replay.py",
    "elyse_agent/saved_acq_event_33620.py": "elyse_agent/saved_acq_event_33620.py",
    "elyse_agent/saved_sup_frequency.py": "elyse_agent/saved_sup_frequency.py",
    "elyse_agent/saved_acq_event_22879.py": "elyse_agent/saved_acq_event_22879.py",
    "elyse_agent/saved_sup_gain.py": "elyse_agent/saved_sup_gain.py",
    "tests/test_saved_acq_event_22879.py": "tests/test_saved_acq_event_22879.py",
    "tests/test_saved_sup_gain.py": "tests/test_saved_sup_gain.py",
    "tests/test_saved_next_events_rpc.py": "tests/test_saved_next_events_rpc.py",
    "tests/next_event_fixtures.py": "tests/next_event_fixtures.py",
    "data/saved_next_event_slices_contract.json": "data/saved_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_45123.py": "elyse_agent/saved_acq_event_45123.py",
    "elyse_agent/saved_sup_event_65050.py": "elyse_agent/saved_sup_event_65050.py",
    "tests/test_saved_acq_event_45123.py": "tests/test_saved_acq_event_45123.py",
    "tests/test_saved_sup_event_65050.py": "tests/test_saved_sup_event_65050.py",
    "tests/test_saved_fourth_next_events_rpc.py": "tests/test_saved_fourth_next_events_rpc.py",
    "tests/fourth_next_event_fixtures.py": "tests/fourth_next_event_fixtures.py",
    "data/saved_fourth_next_event_slices_contract.json": "data/saved_fourth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_34191.py": "elyse_agent/saved_acq_event_34191.py",
    "elyse_agent/saved_sup_event_38030.py": "elyse_agent/saved_sup_event_38030.py",
    "tests/test_saved_acq_event_34191.py": "tests/test_saved_acq_event_34191.py",
    "tests/test_saved_sup_event_38030.py": "tests/test_saved_sup_event_38030.py",
    "tests/test_saved_fifth_next_events_rpc.py": "tests/test_saved_fifth_next_events_rpc.py",
    "tests/fifth_next_event_fixtures.py": "tests/fifth_next_event_fixtures.py",
    "data/saved_fifth_next_event_slices_contract.json": "data/saved_fifth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_43634.py": "elyse_agent/saved_acq_event_43634.py",
    "elyse_agent/saved_sup_event_53716.py": "elyse_agent/saved_sup_event_53716.py",
    "tests/test_saved_acq_event_43634.py": "tests/test_saved_acq_event_43634.py",
    "tests/test_saved_sup_event_53716.py": "tests/test_saved_sup_event_53716.py",
    "tests/test_saved_sixth_next_events_rpc.py": "tests/test_saved_sixth_next_events_rpc.py",
    "tests/sixth_next_event_fixtures.py": "tests/sixth_next_event_fixtures.py",
    "tests/sup_event_53716_fixtures.py": "tests/sup_event_53716_fixtures.py",
    "data/saved_sixth_next_event_slices_contract.json": "data/saved_sixth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_31552.py": "elyse_agent/saved_acq_event_31552.py",
    "elyse_agent/saved_sup_event_18780.py": "elyse_agent/saved_sup_event_18780.py",
    "tests/test_saved_acq_event_31552.py": "tests/test_saved_acq_event_31552.py",
    "tests/test_saved_sup_event_18780.py": "tests/test_saved_sup_event_18780.py",
    "tests/test_saved_seventh_next_events_rpc.py": "tests/test_saved_seventh_next_events_rpc.py",
    "tests/seventh_next_event_fixtures.py": "tests/seventh_next_event_fixtures.py",
    "tests/sup_event_18780_fixtures.py": "tests/sup_event_18780_fixtures.py",
    "data/saved_seventh_next_event_slices_contract.json": "data/saved_seventh_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_48846.py": "elyse_agent/saved_acq_event_48846.py",
    "elyse_agent/saved_sup_event_33463.py": "elyse_agent/saved_sup_event_33463.py",
    "tests/test_saved_acq_event_48846.py": "tests/test_saved_acq_event_48846.py",
    "tests/test_saved_sup_event_33463.py": "tests/test_saved_sup_event_33463.py",
    "tests/test_saved_eighth_next_events_rpc.py": "tests/test_saved_eighth_next_events_rpc.py",
    "tests/eighth_next_event_fixtures.py": "tests/eighth_next_event_fixtures.py",
    "tests/sup_event_33463_fixtures.py": "tests/sup_event_33463_fixtures.py",
    "data/saved_eighth_next_event_slices_contract.json": "data/saved_eighth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_8896.py": "elyse_agent/saved_acq_event_8896.py",
    "elyse_agent/saved_sup_event_38707.py": "elyse_agent/saved_sup_event_38707.py",
    "tests/test_saved_acq_event_8896.py": "tests/test_saved_acq_event_8896.py",
    "tests/test_saved_sup_event_38707.py": "tests/test_saved_sup_event_38707.py",
    "tests/test_saved_ninth_next_events_rpc.py": "tests/test_saved_ninth_next_events_rpc.py",
    "tests/ninth_next_event_fixtures.py": "tests/ninth_next_event_fixtures.py",
    "tests/sup_event_38707_fixtures.py": "tests/sup_event_38707_fixtures.py",
    "data/saved_ninth_next_event_slices_contract.json": "data/saved_ninth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_23113.py": "elyse_agent/saved_acq_event_23113.py",
    "elyse_agent/saved_sup_event_5847.py": "elyse_agent/saved_sup_event_5847.py",
    "tests/test_saved_acq_event_23113.py": "tests/test_saved_acq_event_23113.py",
    "tests/test_saved_sup_event_5847.py": "tests/test_saved_sup_event_5847.py",
    "tests/test_saved_tenth_next_events_rpc.py": "tests/test_saved_tenth_next_events_rpc.py",
    "tests/tenth_next_event_fixtures.py": "tests/tenth_next_event_fixtures.py",
    "tests/sup_event_5847_fixtures.py": "tests/sup_event_5847_fixtures.py",
    "data/saved_tenth_next_event_slices_contract.json": "data/saved_tenth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_38732.py": "elyse_agent/saved_acq_event_38732.py",
    "elyse_agent/saved_sup_event_26490.py": "elyse_agent/saved_sup_event_26490.py",
    "tests/test_saved_acq_event_38732.py": "tests/test_saved_acq_event_38732.py",
    "tests/test_saved_sup_event_26490.py": "tests/test_saved_sup_event_26490.py",
    "tests/test_saved_eleventh_next_events_rpc.py": "tests/test_saved_eleventh_next_events_rpc.py",
    "tests/eleventh_next_event_fixtures.py": "tests/eleventh_next_event_fixtures.py",
    "tests/sup_event_26490_fixtures.py": "tests/sup_event_26490_fixtures.py",
    "data/saved_eleventh_next_event_slices_contract.json": "data/saved_eleventh_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_37991.py": "elyse_agent/saved_acq_event_37991.py",
    "elyse_agent/saved_sup_event_23880.py": "elyse_agent/saved_sup_event_23880.py",
    "tests/test_saved_acq_event_37991.py": "tests/test_saved_acq_event_37991.py",
    "tests/test_saved_sup_event_23880.py": "tests/test_saved_sup_event_23880.py",
    "tests/test_saved_twelfth_next_events_rpc.py": "tests/test_saved_twelfth_next_events_rpc.py",
    "tests/twelfth_next_event_fixtures.py": "tests/twelfth_next_event_fixtures.py",
    "tests/sup_event_23880_fixtures.py": "tests/sup_event_23880_fixtures.py",
    "data/saved_twelfth_next_event_slices_contract.json": "data/saved_twelfth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_17899.py": "elyse_agent/saved_acq_event_17899.py",
    "elyse_agent/saved_sup_event_53772.py": "elyse_agent/saved_sup_event_53772.py",
    "tests/test_saved_acq_event_17899.py": "tests/test_saved_acq_event_17899.py",
    "tests/test_saved_sup_event_53772.py": "tests/test_saved_sup_event_53772.py",
    "tests/test_saved_thirteenth_next_events_rpc.py": "tests/test_saved_thirteenth_next_events_rpc.py",
    "tests/thirteenth_next_event_fixtures.py": "tests/thirteenth_next_event_fixtures.py",
    "tests/sup_event_53772_fixtures.py": "tests/sup_event_53772_fixtures.py",
    "data/saved_thirteenth_next_event_slices_contract.json": "data/saved_thirteenth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_23143.py": "elyse_agent/saved_acq_event_23143.py",
    "elyse_agent/saved_sup_event_23770.py": "elyse_agent/saved_sup_event_23770.py",
    "tests/test_saved_acq_event_23143.py": "tests/test_saved_acq_event_23143.py",
    "tests/test_saved_sup_event_23770.py": "tests/test_saved_sup_event_23770.py",
    "tests/test_saved_fourteenth_next_events_rpc.py": "tests/test_saved_fourteenth_next_events_rpc.py",
    "tests/fourteenth_next_event_fixtures.py": "tests/fourteenth_next_event_fixtures.py",
    "tests/sup_event_23770_fixtures.py": "tests/sup_event_23770_fixtures.py",
    "data/saved_fourteenth_next_event_slices_contract.json": "data/saved_fourteenth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_35942.py": "elyse_agent/saved_acq_event_35942.py",
    "elyse_agent/saved_sup_event_56943.py": "elyse_agent/saved_sup_event_56943.py",
    "tests/test_saved_acq_event_35942.py": "tests/test_saved_acq_event_35942.py",
    "tests/test_saved_sup_event_56943.py": "tests/test_saved_sup_event_56943.py",
    "tests/test_saved_fifteenth_next_events_rpc.py": "tests/test_saved_fifteenth_next_events_rpc.py",
    "tests/fifteenth_next_event_fixtures.py": "tests/fifteenth_next_event_fixtures.py",
    "tests/sup_event_56943_fixtures.py": "tests/sup_event_56943_fixtures.py",
    "data/saved_fifteenth_next_event_slices_contract.json": "data/saved_fifteenth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_40079.py": "elyse_agent/saved_acq_event_40079.py",
    "elyse_agent/saved_sup_event_53656.py": "elyse_agent/saved_sup_event_53656.py",
    "tests/test_saved_acq_event_40079.py": "tests/test_saved_acq_event_40079.py",
    "tests/test_saved_sup_event_53656.py": "tests/test_saved_sup_event_53656.py",
    "tests/test_saved_sixteenth_next_events_rpc.py": "tests/test_saved_sixteenth_next_events_rpc.py",
    "tests/sixteenth_next_event_fixtures.py": "tests/sixteenth_next_event_fixtures.py",
    "tests/sup_event_53656_fixtures.py": "tests/sup_event_53656_fixtures.py",
    "data/saved_sixteenth_next_event_slices_contract.json": "data/saved_sixteenth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_42457.py": "elyse_agent/saved_acq_event_42457.py",
    "elyse_agent/saved_sup_event_47072.py": "elyse_agent/saved_sup_event_47072.py",
    "tests/test_saved_acq_event_42457.py": "tests/test_saved_acq_event_42457.py",
    "tests/test_saved_sup_event_47072.py": "tests/test_saved_sup_event_47072.py",
    "tests/test_saved_seventeenth_next_events_rpc.py": "tests/test_saved_seventeenth_next_events_rpc.py",
    "tests/seventeenth_next_event_fixtures.py": "tests/seventeenth_next_event_fixtures.py",
    "tests/sup_event_47072_fixtures.py": "tests/sup_event_47072_fixtures.py",
    "data/saved_seventeenth_next_event_slices_contract.json": "data/saved_seventeenth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_34531.py": "elyse_agent/saved_acq_event_34531.py",
    "elyse_agent/saved_sup_event_30817.py": "elyse_agent/saved_sup_event_30817.py",
    "tests/test_saved_acq_event_34531.py": "tests/test_saved_acq_event_34531.py",
    "tests/test_saved_sup_event_30817.py": "tests/test_saved_sup_event_30817.py",
    "tests/test_saved_eighteenth_next_events_rpc.py": "tests/test_saved_eighteenth_next_events_rpc.py",
    "tests/eighteenth_next_event_fixtures.py": "tests/eighteenth_next_event_fixtures.py",
    "tests/sup_event_30817_fixtures.py": "tests/sup_event_30817_fixtures.py",
    "data/saved_eighteenth_next_event_slices_contract.json": "data/saved_eighteenth_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_23449.py": "elyse_agent/saved_acq_event_23449.py",
    "elyse_agent/saved_sup_position_t3.py": "elyse_agent/saved_sup_position_t3.py",
    "tests/test_saved_acq_event_23449.py": "tests/test_saved_acq_event_23449.py",
    "tests/test_saved_sup_position_t3.py": "tests/test_saved_sup_position_t3.py",
    "tests/test_saved_third_next_events_rpc.py": "tests/test_saved_third_next_events_rpc.py",
    "tests/third_next_event_fixtures.py": "tests/third_next_event_fixtures.py",
    "data/saved_third_next_event_slices_contract.json": "data/saved_third_next_event_slices_contract.json",
    "elyse_agent/saved_acq_event_26012.py": "elyse_agent/saved_acq_event_26012.py",
    "elyse_agent/saved_sup_position_t2.py": "elyse_agent/saved_sup_position_t2.py",
    "tests/test_saved_acq_event_26012.py": "tests/test_saved_acq_event_26012.py",
    "tests/test_saved_sup_position_t2.py": "tests/test_saved_sup_position_t2.py",
    "tests/test_saved_second_next_events_rpc.py": "tests/test_saved_second_next_events_rpc.py",
    "tests/second_next_event_fixtures.py": "tests/second_next_event_fixtures.py",
    "data/saved_second_next_event_slices_contract.json": "data/saved_second_next_event_slices_contract.json",
    "tests/test_saved_acq_event_33620.py": "tests/test_saved_acq_event_33620.py",
    "tests/test_saved_sup_frequency.py": "tests/test_saved_sup_frequency.py",
    "tests/test_saved_events_rpc.py": "tests/test_saved_events_rpc.py",
    "tests/saved_event_fixtures.py": "tests/saved_event_fixtures.py",
    "data/saved_event_slices_contract.json": "data/saved_event_slices_contract.json",
    "tests/test_saved_sup_helpers.py": "tests/test_saved_sup_helpers.py",
    "tests/test_saved_sup_helpers_rpc.py": "tests/test_saved_sup_helpers_rpc.py",
    "data/saved_card_init_contract.json": "data/saved_card_init_contract.json",
    "data/saved_sup_helpers_contract.json": "data/saved_sup_helpers_contract.json",
    "data/saved_numeric_contract.json": "data/saved_numeric_contract.json",
    "tests/test_saved_numeric.py": "tests/test_saved_numeric.py",
    "tests/test_saved_numeric_rpc.py": "tests/test_saved_numeric_rpc.py",
    "data/supervision_lifecycle.json": "data/supervision_lifecycle.json",
    "data/supervision_procedures.json": "data/supervision_procedures.json",
    "data/saved_xnode_contract.json": "data/saved_xnode_contract.json",
    "data/saved_timing_contract.json": "data/saved_timing_contract.json",
    "data/saved_ni6220_contract.json": "data/saved_ni6220_contract.json",
    "data/saved_initializer_contract.json": "data/saved_initializer_contract.json",
    "data/saved_cleanup_contract.json": "data/saved_cleanup_contract.json",
    "data/saved_requests_contract.json": "data/saved_requests_contract.json",
    "data/saved_dispatch_contract.json": "data/saved_dispatch_contract.json",
    "data/saved_psp_reads_contract.json": "data/saved_psp_reads_contract.json",
    "data/saved_sup_reads_contract.json": "data/saved_sup_reads_contract.json",
    "data/saved_stop_contract.json": "data/saved_stop_contract.json",
    "tests/test_supervision_runtime.py": "tests/test_supervision_runtime.py",
    "tests/test_supervision_rpc.py": "tests/test_supervision_rpc.py",
    "tests/test_supervision_setpoints.py": "tests/test_supervision_setpoints.py",
    "tests/test_supervision_lifecycle.py": "tests/test_supervision_lifecycle.py",
    "tests/test_saved_xnode.py": "tests/test_saved_xnode.py",
    "tests/test_saved_xnode_rpc.py": "tests/test_saved_xnode_rpc.py",
    "tests/test_saved_timing.py": "tests/test_saved_timing.py",
    "tests/test_saved_timing_rpc.py": "tests/test_saved_timing_rpc.py",
    "tests/test_saved_ni6220.py": "tests/test_saved_ni6220.py",
    "tests/test_saved_ni6220_rpc.py": "tests/test_saved_ni6220_rpc.py",
    "tests/test_saved_initializer.py": "tests/test_saved_initializer.py",
    "tests/test_saved_initializer_rpc.py": "tests/test_saved_initializer_rpc.py",
    "tests/test_saved_cleanup.py": "tests/test_saved_cleanup.py",
    "tests/test_saved_cleanup_rpc.py": "tests/test_saved_cleanup_rpc.py",
    "tests/test_saved_requests.py": "tests/test_saved_requests.py",
    "tests/test_saved_requests_rpc.py": "tests/test_saved_requests_rpc.py",
    "tests/test_saved_dispatch.py": "tests/test_saved_dispatch.py",
    "tests/test_saved_dispatch_rpc.py": "tests/test_saved_dispatch_rpc.py",
    "tests/test_saved_psp_reads.py": "tests/test_saved_psp_reads.py",
    "tests/test_saved_psp_reads_rpc.py": "tests/test_saved_psp_reads_rpc.py",
    "tests/test_saved_sup_reads.py": "tests/test_saved_sup_reads.py",
    "tests/test_saved_sup_reads_rpc.py": "tests/test_saved_sup_reads_rpc.py",
    "tests/test_saved_stop.py": "tests/test_saved_stop.py",
    "tests/test_saved_stop_rpc.py": "tests/test_saved_stop_rpc.py",
}
for module in ("audit", "channel_registry", "commands", "config", "daqmx_backend", "errors",
               "protocol", "service", "simulator", "state", "psp_format"):
    FILES["elyse_agent/" + module + ".py"] = "elyse_agent/" + module + ".py"
for name in ("channel_map.csv", "calibration_map.csv", "ni6602_timing.csv"):
    FILES["data/" + name] = "data/" + name


def check_plan_parity():
    sys.path.insert(0, str(ROOT))
    from DeviceServers.control.elyse_acq.plans import PROCEDURE_PLANS
    from DeviceServers.control.elyse_acq.dps_bridge import DPS_FIELD_BY_ACQ_EVENT_CASE

    bundle = json.loads((AGENT / "data/supervision_procedures.json").read_text(encoding="utf-8"))
    if bundle.get("schema_version") != 1 or bundle.get("simulation_only") is not True:
        raise ValueError("Simulation-only plan bundle required")
    plans = bundle["plans"]
    if set(plans) != set(PROCEDURE_PLANS):
        raise ValueError("Portable procedure catalog is stale")
    for name, plan in PROCEDURE_PLANS.items():
        expected = dict(name=plan.name, legacy_event_case=plan.legacy_event_case,
                        dps_index=DPS_FIELD_BY_ACQ_EVENT_CASE[plan.legacy_event_case],
                        blocked_reason=("Magnet ownership unresolved; legacy DAQmx fallback forbidden"
                                        if plan.legacy_event_case in (16, 17, 25) else ""),
                        steps=json.loads(json.dumps([dict(asdict(step), operation=step.operation.value)
                                                    for step in plan.steps])))
        if plans[name] != expected:
            raise ValueError("Portable procedure/crosswalk differs: " + name)
    return plans


def build(output):
    plans = check_plan_parity()
    arrows = check_setpoint_parity()
    cycle = check_lifecycle_parity()
    xnodes = check_saved_xnode_contract()
    timing = check_saved_timing_contract()
    ni6220 = check_saved_ni6220_contract()
    initializer = check_saved_initializer_contract()
    cleanup = check_saved_cleanup_contract()
    requests = check_saved_requests_contract()
    dispatch = check_saved_dispatch_contract()
    reads = check_saved_psp_reads_contract()
    sup_reads = check_saved_sup_reads_contract()
    stop = check_saved_stop_contract()
    card_init = check_saved_helper_contract('saved_card_init_contract.json','saved_card_init.py',{'APP-01','APP-02','APP-04'})
    sup_helpers = check_saved_helper_contract('saved_sup_helpers_contract.json','saved_sup_helpers.py',{'APP-19','APP-21','APP-22'})
    event_slices = check_saved_event_slices_contract()
    next_event_slices = check_saved_next_event_slices_contract()
    second_next_event_slices = check_saved_second_next_event_slices_contract()
    third_next_event_slices = check_saved_third_next_event_slices_contract()
    eighteenth_next_event_slices = check_saved_eighteenth_next_event_slices_contract()
    seventeenth_next_event_slices = check_saved_seventeenth_next_event_slices_contract()
    sixteenth_next_event_slices = check_saved_sixteenth_next_event_slices_contract()
    fifteenth_next_event_slices = check_saved_fifteenth_next_event_slices_contract()
    fourteenth_next_event_slices = check_saved_fourteenth_next_event_slices_contract()
    thirteenth_next_event_slices = check_saved_thirteenth_next_event_slices_contract()
    twelfth_next_event_slices = check_saved_twelfth_next_event_slices_contract()
    eleventh_next_event_slices = check_saved_eleventh_next_event_slices_contract()
    tenth_next_event_slices = check_saved_tenth_next_event_slices_contract()
    ninth_next_event_slices = check_saved_ninth_next_event_slices_contract()
    eighth_next_event_slices = check_saved_eighth_next_event_slices_contract()
    seventh_next_event_slices = check_saved_seventh_next_event_slices_contract()
    sixth_next_event_slices = check_saved_sixth_next_event_slices_contract()
    fifth_next_event_slices = check_saved_fifth_next_event_slices_contract()
    fourth_next_event_slices = check_saved_fourth_next_event_slices_contract()
    contents = {name: (AGENT / source).read_bytes() for name, source in FILES.items()}
    manifest = dict(schema_version=1, python_minimum="3.4", mode="SIMULATION",
                    hardware_writes=False, physical_status="NOT_EXECUTED", default_endpoint="tcp://10.20.30.10:8765",
                    local_endpoint="tcp://127.0.0.1:8765", protocol="signed_agent_rpc_v1", entrypoint="main.py --supervision",
                    procedure_count=len(plans), admitted_procedure_count=len(plans),
                    reviewed_step_count=sum(len(p["steps"]) for p in plans.values()),
                    admitted_step_count=sum(len(p["steps"]) for p in plans.values()),
                    setpoint_arrow_count=len(arrows),
                    lifecycle_procedure_count=len(cycle), lifecycle_step_count=sum(len(p["steps"]) for p in cycle.values()),
                    saved_xnode_body_count=len(xnodes["sites"]),
                    saved_xnode_scope="ISOLATED_BODY_REPLAY", saved_xnode_telemetry_bound=False,
                    saved_timing_body_count=len(timing["sites"]),
                    saved_timing_scope="ISOLATED_BODY_REPLAY", scheduler_execution_qualified=False,
                    saved_ni6220_body_count=1, saved_ni6220_source_id=ni6220["source_id"],
                    saved_ni6220_scope="SUPPLIED_COMPLETED_READ_PROJECTION", daq_execution_qualified=False,
                    saved_initializer_frames=initializer['frame_uids'],
                    saved_initializer_scope="SUPPLIED_RETURN_CALLER_ROUTING", initializer_execution_qualified=False,
                    saved_cleanup_frame_uid=cleanup['uid'], saved_cleanup_scope="SUPPLIED_RETURN_CLEANUP_ROUTING",
                    resource_close_success_qualified=False,
                    saved_request_page_count=len(requests['pages']),
                    saved_acq_entry_gate_count=len(requests['acquisition_entries']),
                    saved_request_scope="SUPPLIED_SNAPSHOT_REQUEST_FACET", atomic_snapshots_qualified=False,
                    saved_dispatch_selector_uid=dispatch['selector_uid'], saved_dispatch_boolean_count=29,
                    saved_dispatch_scope="SUPPLIED_SNAPSHOT_PURE_FACETS", event_acknowledgement_qualified=False,
                    saved_psp_read_frame_uid=reads['uid'], saved_psp_read_site_count=len(reads['sites']),
                    saved_psp_read_scope="SUPPLIED_COMPLETED_FRAME_PSP_CALLER", native_psp_return_semantics_qualified=False,
                    saved_sup_read_site_count=len(sup_reads['sites']),
                    saved_sup_read_scope="SUPPLIED_COMPLETED_SUPERVISION_READ_SLICE", native_refnum_decoding_qualified=False,
                    saved_stop_runtime_loops=stop['runtime_loops'], saved_stop_scope="SUPPLIED_STOP_LOCAL_TRANSITIONS",
                    saved_stop_scheduler_execution_qualified=False, saved_stop_physical_response_qualified=False,
                    saved_card_initializer_sources=card_init['source_ids'], saved_card_initializer_scope='SUPPLIED_COMPLETED_RETURN_BODY',
                    saved_sup_helper_sources=sup_helpers['source_ids'], saved_sup_helper_scope='BOUNDED_SAVED_PURE_KERNEL',
                    saved_helper_whole_VI_equivalence=False, saved_helper_native_execution=False,
                    saved_event_slices=event_slices['sources'],
                    saved_next_event_slices=next_event_slices['sources'],
                    saved_second_next_event_slices=second_next_event_slices['sources'],
                    saved_third_next_event_slices=third_next_event_slices['sources'],
                    saved_eighteenth_next_event_slices=eighteenth_next_event_slices['sources'],
                    saved_seventeenth_next_event_slices=seventeenth_next_event_slices['sources'],
                    saved_sixteenth_next_event_slices=sixteenth_next_event_slices['sources'],
                    saved_fifteenth_next_event_slices=fifteenth_next_event_slices['sources'],
                    saved_fourteenth_next_event_slices=fourteenth_next_event_slices['sources'],
                    saved_thirteenth_next_event_slices=thirteenth_next_event_slices['sources'],
                    saved_twelfth_next_event_slices=twelfth_next_event_slices['sources'],
                    saved_eleventh_next_event_slices=eleventh_next_event_slices['sources'],
                    saved_tenth_next_event_slices=tenth_next_event_slices['sources'],
                    saved_ninth_next_event_slices=ninth_next_event_slices['sources'],
                    saved_eighth_next_event_slices=eighth_next_event_slices['sources'],
                    saved_seventh_next_event_slices=seventh_next_event_slices['sources'],
                    saved_sixth_next_event_slices=sixth_next_event_slices['sources'],
                    saved_fifth_next_event_slices=fifth_next_event_slices['sources'],
                    saved_fourth_next_event_slices=fourth_next_event_slices['sources'],
                    saved_event_slice_scope='SUPPLIED_SELECTED_EVENT_BODY',
                    saved_event_native_execution=False, saved_event_whole_equivalence=False,
                    files={name: hashlib.sha256(data).hexdigest() for name, data in contents.items()})
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 10, 7, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, data)
        item = zipfile.ZipInfo("manifest.json", date_time=(2026, 10, 7, 0, 0, 0))
        item.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(item, json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8"))
    print(str(output.resolve()))
    print("SIMULATION; {0} admitted procedures; {1} admitted steps; no hardware writes".format(
        manifest["admitted_procedure_count"], manifest["admitted_step_count"]))
    print("{0} named arrows; {1} lifecycle procedures / {2} synthetic steps".format(
        manifest["setpoint_arrow_count"], manifest["lifecycle_procedure_count"], manifest["lifecycle_step_count"]))
    print("SHA256 " + hashlib.sha256(output.read_bytes()).hexdigest())


def check_setpoint_parity():
    sys.path.insert(0, str(ROOT))
    from Supervision.python_reconstruction.src.supervision_reconstruction.domain.parameter_page_events import PARAMETER_RULES
    from legacy.xp_acq_agent.elyse_agent.supervision_setpoints import rules
    names = {"Page Fluides": "fluides", "Page HT": "ht", "Page HF": "hf"}
    expected = [dict(page=rule.page.value, control=rule.arrow, numeric_field=rule.numeric_field,
                     delta=rule.delta, native_limits=list(rule.limits) if rule.limits else None,
                     target=rule.controller + "." + rule.controller_field.split()[0],
                     procedure=f"setpoint.{names[rule.page.value]}.{rule.mask}") for rule in PARAMETER_RULES]
    if rules() != expected:
        raise ValueError("Portable setpoint rules differ from recovered Supervision arithmetic/crosswalk")
    return expected


def check_lifecycle_parity():
    sys.path.insert(0, str(ROOT))
    from tools.elyse_lifecycle_bundle import expected_bundle
    from legacy.xp_acq_agent.elyse_agent.supervision_lifecycle import load_bundle, plans
    if load_bundle() != expected_bundle():
        raise ValueError("Portable lifecycle facets differ from recovered native constants/frame order")
    return plans()


def check_saved_helper_contract(name,module,source_ids):
    value=json.loads((AGENT/'data'/name).read_text(encoding='utf-8'))
    if set(value['source_ids'])!=source_ids or value['whole_VI_equivalence'] is not False or value['native_execution'] is not False:
        raise ValueError('Exact bounded saved helper contract required')
    actual=hashlib.sha256((AGENT/'elyse_agent'/module).read_bytes()).hexdigest().upper()
    if actual!=value['implementation_sha256']:
        raise ValueError('Saved helper implementation differs from qualified contract')
    return value


def check_saved_event_slices_contract():
    expected = {('APP-00', '43', '33620', 'saved_acq_event_33620.py'),
                ('APP-17', '5909', '70866', 'saved_sup_frequency.py')}
    return _check_saved_event_slices_contract('saved_event_slices_contract.json', expected)


def check_saved_next_event_slices_contract():
    expected = {('APP-00', '43', '22879', 'saved_acq_event_22879.py'),
                ('APP-17', '5909', '56135', 'saved_sup_gain.py')}
    return _check_saved_event_slices_contract('saved_next_event_slices_contract.json', expected)


def check_saved_second_next_event_slices_contract():
    expected = {('APP-00', '43', '26012', 'saved_acq_event_26012.py'),
                ('APP-17', '5909', '71391', 'saved_sup_position_t2.py')}
    return _check_saved_event_slices_contract('saved_second_next_event_slices_contract.json', expected)


def check_saved_third_next_event_slices_contract():
    expected = {('APP-00', '43', '23449', 'saved_acq_event_23449.py'),
                ('APP-17', '5909', '73301', 'saved_sup_position_t3.py')}
    return _check_saved_event_slices_contract('saved_third_next_event_slices_contract.json', expected)


def check_saved_fourth_next_event_slices_contract():
    expected = {('APP-00', '43', '45123', 'saved_acq_event_45123.py'),
                ('APP-17', '5909', '65050', 'saved_sup_event_65050.py')}
    return _check_saved_event_slices_contract('saved_fourth_next_event_slices_contract.json', expected)


def check_saved_fifth_next_event_slices_contract():
    expected = {('APP-00', '43', '34191', 'saved_acq_event_34191.py'),
                ('APP-17', '5909', '38030', 'saved_sup_event_38030.py')}
    return _check_saved_event_slices_contract('saved_fifth_next_event_slices_contract.json', expected)


def check_saved_sixth_next_event_slices_contract():
    expected = {('APP-00', '43', '43634', 'saved_acq_event_43634.py'),
                ('APP-17', '5909', '53716', 'saved_sup_event_53716.py')}
    value = _check_saved_event_slices_contract('saved_sixth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_INTRINSIC_AND_STORAGE_BOUNDARIES' or any(row.get(flag) is not False for flag in ('native_range_comparison_mode_qualified', 'native_literal_serializer_qualified', 'event_selection_qualified', 'supplied_completion_is_feasible_native_trace')):
            raise ValueError('Explicit G67 open intrinsic/storage boundaries required')
    return value


def check_saved_seventh_next_event_slices_contract():
    expected = {('APP-00', '43', '31552', 'saved_acq_event_31552.py'),
                ('APP-17', '5909', '18780', 'saved_sup_event_18780.py')}
    value = _check_saved_event_slices_contract('saved_seventh_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_PROPERTY_VARIANT_FORMAT_STORAGE_AND_LOOP_INTRINSICS' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_variant_conversion_qualified', 'native_formatting_qualified', 'native_literal_serializer_qualified', 'native_loop_default_or_completion_qualified', 'native_error_case_selection_qualified', 'supplied_completion_is_feasible_native_trace')):
            raise ValueError('Explicit G68 open property/variant/format/storage/loop boundaries required')
    return value


def check_saved_eighth_next_event_slices_contract():
    expected = {('APP-00', '43', '48846', 'saved_acq_event_48846.py'),
                ('APP-17', '5909', '33463', 'saved_sup_event_33463.py')}
    value = _check_saved_event_slices_contract('saved_eighth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_PROPERTY_VARIANT_STORAGE_ARGMAX_RANGE_AND_ERRORCASE' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_variant_conversion_qualified', 'native_literal_serializer_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'supplied_completion_is_feasible_native_trace')):
            raise ValueError('Explicit G69 open property/variant/storage/argmax/range/ErrorCase boundaries required')
    return value


def check_saved_ninth_next_event_slices_contract():
    expected = {('APP-00', '43', '8896', 'saved_acq_event_8896.py'),
                ('APP-17', '5909', '38707', 'saved_sup_event_38707.py')}
    value = _check_saved_event_slices_contract('saved_ninth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_PROPERTY_STORAGE_RANGE_ERRORCASE_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace')):
            raise ValueError('Explicit G70 open property/storage/range/ErrorCase/native-leaf boundaries required')
    return value


def check_saved_tenth_next_event_slices_contract():
    expected = {('APP-00', '43', '23113', 'saved_acq_event_23113.py'),
                ('APP-17', '5909', '5847', 'saved_sup_event_5847.py')}
    value = _check_saved_event_slices_contract('saved_tenth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_PROPERTY_VARIANT_STORAGE_ARGMAX_RANGE_LOOP_ERRORCASE_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified')):
            raise ValueError('Explicit G71 open property/Variant/storage/argmax/range/loop/ErrorCase/native-leaf boundaries required')
    return value


def check_saved_eleventh_next_event_slices_contract():
    expected = {('APP-00', '43', '38732', 'saved_acq_event_38732.py'),
                ('APP-17', '5909', '26490', 'saved_sup_event_26490.py')}
    value = _check_saved_event_slices_contract('saved_eleventh_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_LITERAL_FIELD_BINDINGS_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified', 'native_field_index_selection_qualified', 'native_unwired_input_defaults_qualified')):
            raise ValueError('Explicit G72 open literal/field-index/snapshot/schedule/Wait/native-leaf boundaries required')
    return value


def check_saved_twelfth_next_event_slices_contract():
    expected = {('APP-00', '43', '37991', 'saved_acq_event_37991.py'),
                ('APP-17', '5909', '23880', 'saved_sup_event_23880.py')}
    value = _check_saved_event_slices_contract('saved_twelfth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_LITERAL_CALLEE_COERCION_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified', 'native_field_index_selection_qualified', 'native_unwired_input_defaults_qualified', 'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified')):
            raise ValueError('Explicit G73 open literal/callee/coercion/snapshot/schedule/Wait/native-leaf boundaries required')
    return value


def check_saved_thirteenth_next_event_slices_contract():
    expected = {('APP-00', '43', '17899', 'saved_acq_event_17899.py'),
                ('APP-17', '5909', '53772', 'saved_sup_event_53772.py')}
    value = _check_saved_event_slices_contract('saved_thirteenth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_LITERAL_CALLEE_COERCION_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified', 'native_field_index_selection_qualified', 'native_unwired_input_defaults_qualified', 'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified')):
            raise ValueError('Explicit G74 open literal/callee/coercion/snapshot/schedule/Wait/native-leaf boundaries required')
    return value


def check_saved_fourteenth_next_event_slices_contract():
    expected = {('APP-00', '43', '23143', 'saved_acq_event_23143.py'),
                ('APP-17', '5909', '23770', 'saved_sup_event_23770.py')}
    value = _check_saved_event_slices_contract('saved_fourteenth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_LITERAL_CALLEE_COERCION_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified', 'native_field_index_selection_qualified', 'native_unwired_input_defaults_qualified', 'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified')):
            raise ValueError('Explicit G75 open literal/callee/coercion/snapshot/schedule/Wait/native-leaf boundaries required')
    return value


def check_saved_fifteenth_next_event_slices_contract():
    expected = {('APP-00', '43', '35942', 'saved_acq_event_35942.py'),
                ('APP-17', '5909', '56943', 'saved_sup_event_56943.py')}
    value = _check_saved_event_slices_contract('saved_fifteenth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_LITERAL_CALLEE_COERCION_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified', 'native_field_index_selection_qualified', 'native_unwired_input_defaults_qualified', 'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified')):
            raise ValueError('Explicit G76 open literal/callee/coercion/snapshot/schedule/Wait/native-leaf boundaries required')
    return value


def check_saved_sixteenth_next_event_slices_contract():
    expected = {('APP-00', '43', '40079', 'saved_acq_event_40079.py'),
                ('APP-17', '5909', '53656', 'saved_sup_event_53656.py')}
    value = _check_saved_event_slices_contract('saved_sixteenth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_LITERAL_CALLEE_COERCION_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified', 'native_field_index_selection_qualified', 'native_unwired_input_defaults_qualified', 'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified')):
            raise ValueError('Explicit G77 open literal/callee/coercion/snapshot/schedule/Wait/native-leaf boundaries required')
    return value


def check_saved_seventeenth_next_event_slices_contract():
    expected = {('APP-00', '43', '42457', 'saved_acq_event_42457.py'),
                ('APP-17', '5909', '47072', 'saved_sup_event_47072.py')}
    value = _check_saved_event_slices_contract('saved_seventeenth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_LITERAL_CALLEE_COERCION_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified', 'native_field_index_selection_qualified', 'native_unwired_input_defaults_qualified', 'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified')):
            raise ValueError('Explicit G78 open literal/callee/coercion/snapshot/schedule/Wait/native-leaf boundaries required')
    return value


def check_saved_eighteenth_next_event_slices_contract():
    expected = {('APP-00', '43', '34531', 'saved_acq_event_34531.py'),
                ('APP-17', '5909', '30817', 'saved_sup_event_30817.py')}
    value = _check_saved_event_slices_contract('saved_eighteenth_next_event_slices_contract.json', expected)
    for row in value['sources']:
        if row.get('boundary_scope') != 'EXPLICIT_UNQUALIFIED_LITERAL_CALLEE_COERCION_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES' or any(row.get(flag) is not False for flag in ('event_selection_qualified', 'native_property_or_reference_validity_qualified', 'native_literal_serializer_qualified', 'native_range_mode_qualified', 'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified', 'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace', 'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified', 'native_loop_output_policy_qualified', 'native_field_index_selection_qualified', 'native_unwired_input_defaults_qualified', 'native_callee_equivalence_qualified', 'native_primitive_coercion_qualified')):
            raise ValueError('Explicit G79 open literal/callee/coercion/snapshot/schedule/Wait/native-leaf boundaries required')
    return value


def _check_saved_event_slices_contract(name, expected):
    value = json.loads((AGENT / 'data' / name).read_text(encoding='utf-8'))
    false_flags = ('native_execution', 'hardware_execution', 'PSP_execution', 'deployed',
                   'whole_event_equivalence', 'whole_business_scope_complete')
    if value.get('schema_version') != 1 or any(value.get(flag) is not False for flag in false_flags):
        raise ValueError('Bounded saved event slices required')
    if {(row['source_id'], row['event_uid'], row['frame_uid'], row['module']) for row in value['sources']} != expected or len(value['sources']) != 2:
        raise ValueError('Exact two saved event source identities required')
    for row in value['sources']:
        if row.get('scope') != 'SUPPLIED_SELECTED_EVENT_BODY' or row.get('native_execution') is not False or row.get('whole_event_equivalence') is not False:
            raise ValueError('Bounded saved event row required')
        data = (AGENT / 'elyse_agent' / row['module']).read_bytes()
        if hashlib.sha256(data).hexdigest().upper() != row['implementation_sha256']:
            raise ValueError('Saved event implementation changed: ' + row['module'])
        source = row['source_proof']
        data = Path(source['path']).read_bytes()
        if len(data) != source['bytes'] or hashlib.sha256(data).hexdigest().upper() != source['sha256']:
            raise ValueError('Saved event source proof changed: ' + row['source_id'])
        proof = json.loads(data)
        expected_versions = {
            'APP-00': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
            'APP-17': 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9',
        }
        if any(proof.get(key) != row[key] for key in ('source_id', 'event_uid', 'frame_uid')) or proof.get('source_version') != expected_versions[row['source_id']]:
            raise ValueError('Exact original source proof identity required')
        if name != 'saved_event_slices_contract.json' and row.get('source_version') != proof['source_version']:
            raise ValueError('Exact source version in next event row required')
        whole_flags = [proof[flag] for flag in ('whole_event_equivalence', 'whole_event_runtime_equivalence') if flag in proof]
        if proof.get('native_execution') is not False or not whole_flags or any(flag is not False for flag in whole_flags):
            raise ValueError('Source proof scope must remain bounded')
    return value


def check_saved_xnode_contract():
    """Validate packaged identities/wires against frozen source evidence.

    This checks metadata. Actual Python 3.4 body replays are recorded separately
    in python_alignment_20261008; packaging does not assert native equivalence.
    """
    sys.path.insert(0, str(ROOT))
    from legacy.xp_acq_agent.elyse_agent.saved_xnode import SUPPORTED_UIDS

    contract = json.loads((AGENT / "data/saved_xnode_contract.json").read_bytes())
    if contract["native_runtime_equivalence_qualified"] or contract["hardware_execution_allowed"]:
        raise ValueError("Saved XNode contract must remain bounded offline replay")
    sources = []
    for name in ("source_census", "source_comparison"):
        evidence = contract[name]
        raw = Path(evidence["path"]).read_bytes()
        if len(raw) != evidence["bytes"] or hashlib.sha256(raw).hexdigest().upper() != evidence["sha256"]:
            raise ValueError("Saved XNode source evidence changed: " + name)
        sources.append(json.loads(raw))
    census, comparisons = sources
    if tuple(site["uid"] for site in contract["sites"]) != SUPPORTED_UIDS:
        raise ValueError("Saved XNode UID catalog differs")
    for packaged, saved, replay in zip(contract["sites"], census["sites"], comparisons["sites"]):
        fields = ("uid", "parent", "frame")
        if any(packaged[k] != saved[k] for k in fields):
            raise ValueError("Saved XNode containment differs")
        if packaged["script"] != replay["saved_script"] or packaged["formula_uid"] != replay["formula_uid"]:
            raise ValueError("Saved XNode formula identity differs")
        expected_pairs = [{k: pair[k] for k in ("outer", "inner", "dco_uid", "direction", "wire_mappings")}
                          for pair in saved["pairs"]]
        if packaged["pairs"] != expected_pairs:
            raise ValueError("Saved XNode terminal/wire contract differs")
    return contract


def check_saved_timing_contract():
    """Pin exact source templates/borders; packaging does not qualify scheduling."""
    sys.path.insert(0, str(ROOT))
    from legacy.xp_acq_agent.elyse_agent.saved_timing import (
        SUPPORTED_UIDS, TIMING_FIELDS, evaluate_saved_timing, timing_to_json,
    )
    contract = json.loads((AGENT / "data/saved_timing_contract.json").read_bytes())
    for key in ("native_runtime_equivalence_qualified", "scheduler_execution_qualified",
                "runtime_defaults_qualified", "hardware_execution_allowed"):
        if contract[key] is not False:
            raise ValueError("Saved timing contract must remain isolated replay")
    pinned = contract["proof"]
    raw = Path(pinned["path"]).read_bytes()
    if len(raw) != pinned["bytes"] or hashlib.sha256(raw).hexdigest().upper() != pinned["sha256"]:
        raise ValueError("Saved timing source proof changed")
    proof = json.loads(raw)
    if tuple(site["uid"] for site in contract["sites"]) != SUPPORTED_UIDS:
        raise ValueError("Saved timing UID catalog differs")
    if tuple(field["name"] for field in contract["fields"]) != TIMING_FIELDS:
        raise ValueError("Saved Timing field order differs")
    for packaged, saved in zip(contract["sites"], proof["sites"]):
        if packaged["source_body"] != saved:
            raise ValueError("Saved timing source body differs")
        if saved["constant_uid"] and timing_to_json(evaluate_saved_timing(saved["uid"])) != saved["output"]:
            raise ValueError("Portable timing template differs from decoded source")
    return contract


def check_saved_ni6220_contract():
    """Validate saved shape/error metadata; no DAQ or native Mean execution."""
    contract = json.loads((AGENT / "data/saved_ni6220_contract.json").read_bytes())
    if contract["source_id"] != "APP-08" or contract["body_uid"] != "612":
        raise ValueError("Saved NI6220 identity differs")
    for key in ("native_mean_bitwise_equivalence", "daq_runtime_equivalence", "live_acquisition_bound", "hardware_execution_allowed"):
        if contract[key] is not False:
            raise ValueError("Saved NI6220 contract must remain supplied-return replay")
    pinned = contract["proof"]
    raw = Path(pinned["path"]).read_bytes()
    if len(raw) != pinned["bytes"] or hashlib.sha256(raw).hexdigest().upper() != pinned["sha256"]:
        raise ValueError("Saved NI6220 source proof changed")
    source = json.loads(raw)
    for key in ("source_id", "vi", "body_uid", "types", "wire_groups", "fixed_selector"):
        if source[key] != contract[key]:
            raise ValueError("Saved NI6220 source metadata differs: " + key)
    return contract


def check_saved_initializer_contract():
    """Exact source routing metadata; packaging does not execute initializer calls."""
    contract = json.loads((AGENT / 'data/saved_initializer_contract.json').read_bytes())
    if contract['source_id'] != 'APP-00' or contract['frame_uids'] != ['227', '133']:
        raise ValueError('Saved initializer identity differs')
    for key in ('native_runtime_equivalence', 'initializer_execution_qualified',
                'reference_validity_qualified', 'hardware_execution_allowed'):
        if contract[key] is not False:
            raise ValueError('Saved initializer must remain supplied-return routing')
    pinned = contract['proof']
    raw = Path(pinned['path']).read_bytes()
    if len(raw) != pinned['bytes'] or hashlib.sha256(raw).hexdigest().upper() != pinned['sha256']:
        raise ValueError('Saved initializer source proof changed')
    source = json.loads(raw)
    for key in ('source_id', 'frame_uids', 'vi', 'gates', 'task_banks'):
        if source[key] != contract[key]:
            raise ValueError('Saved initializer source metadata differs: ' + key)
    return contract


def check_saved_cleanup_contract():
    """Pin caller dependencies/constant tags; never execute close primitives."""
    contract=json.loads((AGENT/'data/saved_cleanup_contract.json').read_bytes())
    if contract['source_id']!='APP-00' or contract['uid']!='246':
        raise ValueError('Saved cleanup identity differs')
    for key in ('native_runtime_equivalence','resource_close_success_qualified','hardware_execution_allowed'):
        if contract[key] is not False:
            raise ValueError('Saved cleanup must remain supplied-return routing')
    pinned=contract['proof']
    raw=Path(pinned['path']).read_bytes()
    if len(raw)!=pinned['bytes'] or hashlib.sha256(raw).hexdigest().upper()!=pinned['sha256']:
        raise ValueError('Saved cleanup source proof changed')
    source=json.loads(raw)
    for key in ('source_id','uid','fixed_reference_tags','error_register','tpg_branches','stop_reset'):
        if source[key]!=contract[key]:
            raise ValueError('Saved cleanup source metadata differs:'+key)
    from legacy.xp_acq_agent.elyse_agent.saved_cleanup import FIXED_PSP_TAGS,TPG_BRANCHES
    if list(FIXED_PSP_TAGS)!=contract['fixed_reference_tags']['values']:
        raise ValueError('Portable cleanup fixed reference tags differ')
    for branch in contract['tpg_branches']:
        if TPG_BRANCHES[branch['bank']]!=(branch['call_uid'],branch['handler_uid']):
            raise ValueError('Portable TPG branch differs')
    return contract


def check_saved_requests_contract():
    contract=json.loads((AGENT/'data/saved_requests_contract.json').read_bytes())
    for key in ('native_runtime_equivalence','atomic_snapshots_qualified','psp_delivery_qualified','hardware_execution_allowed'):
        if contract[key] is not False:
            raise ValueError('Saved request contract must remain non-actuating snapshot replay')
    pinned=contract['proof']
    raw=Path(pinned['path']).read_bytes()
    if len(raw)!=pinned['bytes'] or hashlib.sha256(raw).hexdigest().upper()!=pinned['sha256']:
        raise ValueError('Saved request proof changed')
    source=json.loads(raw)
    if source['pages']!=contract['pages'] or source['acquisition_entries']!=contract['acquisition_entries']:
        raise ValueError('Saved request source facts changed')
    from legacy.xp_acq_agent.elyse_agent.saved_requests import PAGE_SPECS,procedure_entry_values
    for page in contract['pages']:
        expected=(page['frame_uid'],len(page['adjustment_terminal_uids']),tuple(m['dps_index'] for m in page['command_mapping']))
        if PAGE_SPECS[page['page']]!=expected:
            raise ValueError('Saved request pure field mapping changed')
    for entry in contract['acquisition_entries']:
        values=procedure_entry_values(entry['event_index'],True)
        if values[2]!=entry['duration'] or values[3]!=int(entry['registration']['regFlags']):
            raise ValueError('Saved Acquisition entry constant/flag changed')
    return contract


def check_saved_dispatch_contract():
    contract=json.loads((AGENT/'data/saved_dispatch_contract.json').read_bytes())
    for key in ('native_runtime_equivalence','atomic_snapshots_qualified','psp_delivery_qualified','hardware_execution_allowed'):
        if contract[key] is not False:
            raise ValueError('Saved dispatch must remain inert snapshot facets')
    pinned=contract['proof']
    raw=Path(pinned['path']).read_bytes()
    if len(raw)!=pinned['bytes'] or hashlib.sha256(raw).hexdigest().upper()!=pinned['sha256']:
        raise ValueError('Saved dispatch proof changed')
    source=json.loads(raw)
    if source['selector_uid']!=contract['selector_uid'] or source['branches']!=contract['branches'] or source['tails']!=contract['tails']:
        raise ValueError('Saved dispatch source facts changed')
    default=contract['default_selection']
    pinned=default['qualification']
    raw=Path(pinned['path']).read_bytes()
    if len(raw)!=pinned['bytes'] or hashlib.sha256(raw).hexdigest().upper()!=pinned['sha256']:
        raise ValueError('Saved dispatch static default proof changed')
    qualified=json.loads(raw)
    if qualified['status']!='PASS' or (qualified['qualified_saved_default_index'],qualified['qualified_default_frame_uid'])!=(0,'9471'):
        raise ValueError('Saved dispatch default selection changed')
    if default['assignment']!=qualified['source_body_assignment']:
        raise ValueError('Saved dispatch default source assignment changed')
    assignment=default['assignment']
    if (assignment['literal_terminal_uid'],assignment['literal_raw'],assignment['literal_value'],
        assignment['local_terminal_uid'],assignment['local_bank'],assignment['wire_uid'],assignment['ordered_wire_terminals'])!=('85221','0000',False,'19100',35,'42492',['85221','19100']):
        raise ValueError('Saved dispatch default wire correspondence changed')
    for key in ('binary_audit','native_match','native_static_image'):
        pinned=qualified[key]
        raw=Path(pinned['path']).read_bytes()
        if len(raw)!=pinned['bytes'] or hashlib.sha256(raw).hexdigest().upper()!=pinned['sha256']:
            raise ValueError('Saved dispatch static evidence changed:'+key)
    from legacy.xp_acq_agent.elyse_agent.saved_dispatch import TARGETS,TAILS
    if TARGETS!=tuple((b['ddo_uid'],b['event_index']) for b in contract['branches']):
        raise ValueError('Saved dispatch targets changed')
    for tail in contract['tails']:
        if TAILS[tail['event_index']]!=(tail['dps_index'],tail['publish_writer_uid'],tail['uri'],tail['reset_frame_uid'],tail['publish_frame_uid']):
            raise ValueError('Saved dispatch tail correspondence changed')
    return contract


def check_saved_psp_reads_contract():
    contract=json.loads((AGENT/'data/saved_psp_reads_contract.json').read_bytes())
    if (contract['source_id'],contract['uid'])!=('APP-00','10115'):
        raise ValueError('Saved PSP caller identity changed')
    for key in ('native_runtime_equivalence','atomic_snapshots_qualified','psp_delivery_qualified','hardware_execution_allowed'):
        if contract[key] is not False:
            raise ValueError('Saved PSP caller must remain explicit supplied-return replay')
    pinned=contract['proof']
    raw=Path(pinned['path']).read_bytes()
    if len(raw)!=pinned['bytes'] or hashlib.sha256(raw).hexdigest().upper()!=pinned['sha256']:
        raise ValueError('Saved PSP caller proof changed')
    proof=json.loads(raw)
    for field in ('sites','error_chain','final_fault'):
        if proof[field]!=contract[field]:
            raise ValueError('Saved PSP caller facts changed:'+field)
    from legacy.xp_acq_agent.elyse_agent.saved_psp_reads import SITES,URI_PREFIX
    expected=tuple((s['node_uid'],s['tag'],s['local_bank'],s['size'],
        float if s['element_family']=='NumFloat64' else bool) for s in proof['sites'])
    if SITES!=expected or any(URI_PREFIX+s['tag']!=s['uri'] for s in proof['sites']):
        raise ValueError('Portable PSP caller order/type/bank/URI correspondence changed')
    return contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)


def check_saved_sup_reads_contract():
    contract=json.loads((AGENT/'data/saved_sup_reads_contract.json').read_bytes())
    for key in ('native_runtime_equivalence','atomic_snapshots_qualified','psp_delivery_qualified','hardware_execution_allowed'):
        if contract[key] is not False:
            raise ValueError('Saved Supervision read slices must remain supplied-return replay')
    pinned=contract['proof'];raw=Path(pinned['path']).read_bytes()
    if len(raw)!=pinned['bytes'] or hashlib.sha256(raw).hexdigest().upper()!=pinned['sha256']:
        raise ValueError('Saved Supervision read proof changed')
    proof=json.loads(raw)
    if proof['sites']!=contract['sites'] or proof['sequence_local_crossing']!=contract['sequence_local_crossing']:
        raise ValueError('Saved Supervision reader wires/sequence local changed')
    from legacy.xp_acq_agent.elyse_agent.saved_sup_reads import CHAIN,INDEPENDENT,LOCALS
    if list(CHAIN)!=proof['chain_uids'] or INDEPENDENT!=proof['independent_node_uid']:
        raise ValueError('Portable Supervision reader source UIDs changed')
    if LOCALS!=tuple((s['local_name'],s['local_control_id']) for s in proof['sites'][:13]):
        raise ValueError('Portable Supervision local identities changed')
    return contract


def check_saved_stop_contract():
    contract=json.loads((AGENT/'data/saved_stop_contract.json').read_bytes())
    if any(contract[k] for k in ('native_execution','scheduler_qualified','physical_stop_qualified','hardware_execution_allowed')):
        raise ValueError('Saved stop transitions must remain supplied offline trace')
    item=contract['proof'];raw=Path(item['path']).read_bytes()
    if len(raw)!=item['bytes'] or hashlib.sha256(raw).hexdigest().upper()!=item['sha256']:
        raise ValueError('Saved stop source proof changed')
    proof=json.loads(raw)
    if contract['local_rows']!=proof['local_rows'] or contract['reset_stages']!=proof['reset_stages']:
        raise ValueError('Saved stop local mappings changed')
    from legacy.xp_acq_agent.elyse_agent.saved_stop import RUNTIME_LOOPS,ERROR_SITES,STOP_RESETS
    if list(RUNTIME_LOOPS)!=[r['uid'] for r in proof['loops']]:
        raise ValueError('Saved stop loop UIDs changed')
    rows={r['uid']:r for r in proof['local_rows']}
    for selector,(owner,writes) in ERROR_SITES.items():
        if selector not in {r['uid'] for r in proof['error_cases']} or owner not in RUNTIME_LOOPS:
            raise ValueError('Saved error selector/owner changed')
        for uid,bank,value in writes:
            if rows[uid]['local_bank']!=bank or rows[uid]['value'] is not value:
                raise ValueError('Saved error-arm writes changed')
    for stage,assignments in STOP_RESETS.items():
        if assignments!=tuple((rows[u]['local_bank'],rows[u]['value']) for u in proof['reset_stages'][stage]['writer_uids']):
            raise ValueError('Saved reset writes changed')
    return contract


if __name__ == "__main__":
    main()
