"""Web validation matches packaged camera wire, without XP runtime imports."""
import copy
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'web/backend'))
from acq_video_contract import validate_video_frame
from legacy.xp_acq_control.elyse_agent.federation_wire import validate_video_frame as portable
from tests.unit.test_acq_federated_video import video


@pytest.mark.parametrize('bridge', [False, True])
@pytest.mark.parametrize('change', [None, {'channel': 4294967295}, {'channel': True},
    {'simulated': True}, {'data': '@@@@'}, {'width': 3}, {'sequence': True},
    {'source_age_seconds': float('nan')}, {'source_session_id': 'unknown'},
    {'observed_utc': 'bad+00:00'}, {'processing': 'unqualified'}])
def test_camera_contract_parity(bridge, change):
    frame = video()
    if bridge:
        frame.update(source='labview_supervision_ni1409', source_session_id='b' * 32)
    frame.update(change or {})
    outcomes = []
    for validator in (portable, validate_video_frame):
        try:
            validator(copy.deepcopy(frame))
            outcomes.append(True)
        except (ValueError, TypeError):
            outcomes.append(False)
    assert outcomes[0] == outcomes[1]
