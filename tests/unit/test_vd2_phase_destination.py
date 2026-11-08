from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'web/backend'))
from vd2_measurement_protocol import Vd2MeasurementProtocol, Vd2ProtocolError
from vd2_phase_destination import PhaseDestinations
from vd2_project_manifest import Vd2ProjectManifest


def request(root, sample='sample', phase='ABSORPTION'):
    return Vd2MeasurementProtocol._build_request(phase, 20, str(root), sample)


def existing(root, sample='sample'):
    source = root / sample / 'ABS.h5'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'previous measurement')
    return source


def test_review_does_not_create_directories_or_touch_existing_data(tmp_path):
    root = tmp_path / 'uncreated project'
    planner = PhaseDestinations()
    planned = planner.review(request(root))
    assert planned['conflict'] is False
    assert set(planned['choices']) == {'record'}
    assert not root.exists()
    assert planner.consume(planned['choices']['record']['token'], request(root)).his_path.endswith('ABS.his')
    assert not root.exists()


def test_collision_offers_new_version_and_numbered_folder_without_overwriting(tmp_path):
    old = existing(tmp_path)
    planner = PhaseDestinations()
    planned = planner.review(request(tmp_path))
    assert planned['conflict'] is True
    assert set(planned['choices']) == {'replace', 'new_folder'}
    assert planned['choices']['new_folder']['run_name'] == 'sample_2'
    target = planner.consume(planned['choices']['replace']['token'], request(tmp_path))
    assert target.run_name == 'sample'
    assert Path(target.his_path) == tmp_path / 'sample/.versions/ABSORPTION/2/ABS.his'
    assert old.read_bytes() == b'previous measurement'
    assert not Path(target.his_path).parent.exists()


def test_folder_numbering_skips_existing_paths_and_keeps_original_series(tmp_path):
    existing(tmp_path)
    (tmp_path / 'sample_2').mkdir()
    planner = PhaseDestinations()
    first = planner.review(request(tmp_path))
    assert first['choices']['new_folder']['run_name'] == 'sample_3'
    target = planner.consume(first['choices']['new_folder']['token'], request(tmp_path))
    journal = Vd2ProjectManifest()
    journal.prepare(target)
    next_plan = planner.review(request(tmp_path, 'sample_3'))
    assert next_plan['choices']['new_folder']['run_name'] == 'sample_4'


def test_changed_settings_changed_project_expired_or_replayed_review_never_resolves_to_a_write(tmp_path):
    old = existing(tmp_path)
    now = [0]
    planner = PhaseDestinations(clock=lambda: now[0])
    original = request(tmp_path)
    token = planner.review(original)['choices']['replace']['token']
    with pytest.raises(Vd2ProtocolError, match='settings changed'):
        planner.resolve(token, replace(original, frames_per_his=21))
    old.write_bytes(b'changed during review')
    with pytest.raises(Vd2ProtocolError, match='Project changed'):
        planner.consume(token, original)
    with pytest.raises(Vd2ProtocolError, match='expired'):
        planner.resolve(token, original)
    token = planner.review(original)['choices']['replace']['token']
    now[0] = 301
    with pytest.raises(Vd2ProtocolError, match='expired'):
        planner.resolve(token, original)


def test_a_claimed_target_directory_blocks_the_old_quote(tmp_path):
    existing(tmp_path)
    planner = PhaseDestinations()
    original = request(tmp_path)
    choice = planner.review(original)['choices']['replace']
    Path(choice['his_path']).parent.mkdir(parents=True)
    with pytest.raises(Vd2ProtocolError, match='claimed|changed'):
        planner.consume(choice['token'], original)
    updated = planner.review(original)
    assert '/3/' in Path(updated['choices']['replace']['his_path']).as_posix()


def test_a_long_sample_name_can_still_get_a_valid_numbered_folder(tmp_path):
    name = 'n' * 120
    existing(tmp_path, name)
    choice = PhaseDestinations().review(request(tmp_path, name))['choices']['new_folder']
    assert len(choice['run_name']) == 120
    assert choice['run_name'].endswith('_2')
