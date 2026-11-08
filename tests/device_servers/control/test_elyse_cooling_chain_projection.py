"""Offline request/status/raw-input chain; no PSP or hardware is accessed."""

import unittest

from DeviceServers.control.elyse_acq.acq_status_projection import (
    project_cooling_flow_trip_local_completion,
    project_cooling_start_local_completion,
    project_general_modulator_stop_local_completion,
    project_timeout_remote_eps_ingest,
)
from DeviceServers.control.elyse_acq.dps_bridge import first_asserted_dps_request
from DeviceServers.control.elyse_acq.interlocks import cooling_flow_trip
from DeviceServers.control.elyse_acq.supervision_requests import (
    project_page_fluides_dps_write,
)
from DeviceServers.control.elyse_acq.supervision_status import (
    project_fluides_raw_display_flags,
    project_modulator_stage_ok_from_eps,
)


class CoolingChainProjectionTests(unittest.TestCase):
    def test_start_request_then_raw_flow_trip_changes_only_proven_flags(self):
        request = project_page_fluides_dps_write(
            [False] * 29, [False] * 4, [True, False]
        )
        self.assertEqual(first_asserted_dps_request(request[:24]).legacy_event_case, 3)

        eps, dps = project_cooling_start_local_completion(
            [False] * 77, request
        )
        self.assertTrue(eps[2])   # literal software cooling OK
        self.assertTrue(eps[8])   # literal software GENERAL Mod. OK
        self.assertTrue(project_modulator_stage_ok_from_eps(eps)["GENERAL MOD OK"])
        self.assertFalse(dps[0])  # start request cleared in event 3

        c3, c4 = [False] * 56, [False] * 64
        c3[6] = True
        c4[19] = True
        page = project_fluides_raw_display_flags(c3, c4)
        self.assertFalse(page["Canon 220V"])
        self.assertTrue(page["Section 220V"])
        self.assertTrue(page["Canon débimètre"])
        self.assertTrue(cooling_flow_trip(c4, c3))

        eps, dps = project_cooling_flow_trip_local_completion(eps, dps)
        self.assertTrue(eps[1])   # cooling start fault flag
        self.assertFalse(eps[2])  # cooling OK cleared
        self.assertTrue(eps[5])   # cooling stop OK assigned
        self.assertTrue(eps[8])   # no assignment to GENERAL Mod. OK here
        self.assertTrue(project_modulator_stage_ok_from_eps(eps)["GENERAL MOD OK"])
        self.assertFalse(dps[1])

        eps, dps = project_general_modulator_stop_local_completion(eps, dps)
        self.assertFalse(project_modulator_stage_ok_from_eps(eps)["GENERAL MOD OK"])
        self.assertTrue(eps[11])  # general-stop OK software status

    def test_non_trip_raw_snapshot_does_not_project_trip_status(self):
        c3, c4 = [True] * 56, [False] * 64
        c4[19] = True
        self.assertFalse(cooling_flow_trip(c4, c3))
        page = project_fluides_raw_display_flags(c3, c4)
        self.assertTrue(page["Canon 220V"])
        self.assertTrue(page["Section 220V"])

    def test_optional_remote_eps_ingest_changes_state_before_flow_trip_frame(self):
        started_eps, dps = project_cooling_start_local_completion(
            [False] * 77, [False] * 29
        )
        self.assertTrue(started_eps[8])
        remote_snapshot = [False] * 77
        ingested_eps = project_timeout_remote_eps_ingest(remote_snapshot)
        tripped_eps, _ = project_cooling_flow_trip_local_completion(
            ingested_eps, dps
        )
        self.assertFalse(tripped_eps[8])  # inherited from supplied remote snapshot
        self.assertTrue(tripped_eps[1])
        self.assertFalse(tripped_eps[2])


if __name__ == "__main__":
    unittest.main()
