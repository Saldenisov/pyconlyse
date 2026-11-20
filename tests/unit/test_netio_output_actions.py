"""Partial writes preserve unrelated outlets on NETIO FW 2.4.4."""
import pytest
import ast
import json
from pathlib import Path
from threading import RLock
import requests

from DeviceServers.power.netio.output_actions import output_actions, parse_snapshot


def test_no_change_outlets_are_omitted_instead_of_silently_ignored_by_old_firmware():
    # This models the observed FW 2.4.4 reply: HTTP 200, unchanged outputs if
    # an Action 5 appears anywhere in the payload.
    states = {1: 0, 2: 0, 3: 1, 4: 1}
    payload = output_actions([1, 2, 3, 4], [5, 1, 5, 5])
    if all(item['Action'] != 5 for item in payload):
        states.update({item['ID']: item['Action'] for item in payload})
    assert payload == [{'ID': 2, 'Action': 1}]
    assert states == {1: 0, 2: 1, 3: 1, 4: 1}


def test_ids_are_not_inferred_from_array_positions_and_shutdown_keeps_other_outlets():
    assert output_actions([3, 1, 4, 2], [5, 5, 5, 0]) == [{'ID': 2, 'Action': 0}]


def test_no_change_and_readback_ignore_actions_produce_no_write():
    assert output_actions([1, 2], [5, 6]) == []


@pytest.mark.parametrize('ids,actions', [([1, 2], [1]), ([1, 1], [0, 1]), ([], []), ([0], [1]), ([1], [7])])
def test_invalid_payload_never_reaches_partial_write(ids, actions):
    with pytest.raises(ValueError):
        output_actions(ids, actions)


@pytest.mark.parametrize('version', ['2.4.4', '3.0.1', '4.0.5', '5.3.3'])
def test_legacy_and_current_firmware_metadata_and_optional_tags(version):
    snapshot = parse_snapshot({'Agent':{'SerialNumber':'PDU1','Model':'4PS','Version':version},
                               'Outputs':[{'ID':2,'Name':'DG645','State':1}]})
    assert snapshot['firmware'] == version and snapshot['serial'] == 'PDU1'
    assert snapshot['ids'] == [2] and snapshot['states'] == [1]
    assert snapshot['actions'] == [6] and snapshot['delays'] == [0]


@pytest.mark.parametrize('payload', [{}, {'Agent':{},'Outputs':[]},
    {'Agent':{'SerialNumber':'PDU1'},'Outputs':[{'ID':1,'Name':'X','State':5}]},
    {'Agent':{'SerialNumber':'PDU1'},'Outputs':[{'ID':1,'Name':'X','State':0},{'ID':1,'Name':'X','State':1}]}])
def test_invalid_api_reply_never_becomes_a_valid_output_cache(payload):
    with pytest.raises(ValueError):
        parse_snapshot(payload)


def native_driver():
    """Exercise the actual Tango driver methods without importing Tango."""
    path = Path(__file__).parents[2] / 'DeviceServers/power/netio/DS_Netio_pdu.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DS_Netio_pdu')
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in
               {'set_channels_states_local', '__set_attributes_netio'}]
    for method in methods: method.decorator_list = []
    cls.bases = []; cls.keywords = []; cls.body = methods
    namespace = dict(requests=requests, output_actions=output_actions, parse_snapshot=parse_snapshot,
                     time=lambda:123.0, List=list, Union=__import__('typing').Union)
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(path),'exec'),namespace)
    driver = namespace['DS_Netio_pdu']()
    driver._ids, driver._states, driver._netio_serial = [1,2,3,4], [0,0,1,1], 'PDU1'
    driver._netio_read_at = 0
    driver._get_lifecycle_lock = lambda:RLock()
    driver.form_archive_data = lambda *args, **kwargs: None
    driver.write_to_archive = lambda data: None
    return driver


def test_actual_tango_driver_sends_one_partial_write_and_records_native_identity():
    driver = native_driver()
    sent = []
    def send(payload):
        sent.append(payload)
        response = requests.Response(); response.status_code = 200
        response._content = json.dumps({'Agent':{'SerialNumber':'PDU1','Model':'4PS','Version':'5.3.3'},
            'Outputs':[{'ID':i,'Name':str(i),'State':state} for i,state in zip([1,2,3,4],[0,1,1,1])]}).encode()
        return response
    driver._send_request = send
    assert driver.set_channels_states_local([5,1,5,5]) == 0
    assert sent == [{'Outputs':[{'ID':2,'Action':1}]}]
    assert driver._states == [0,1,1,1] and driver._netio_firmware == '5.3.3'
    assert driver._netio_read_at == 123


def test_uncertain_write_is_reported_once_without_automatic_replay():
    driver = native_driver(); sent=[]
    driver._send_request = lambda payload: sent.append(payload) or False
    with pytest.raises(RuntimeError,match='outcome unknown'):
        driver.set_channels_states_local([5,1,5,5])
    assert len(sent) == 1 and driver._states == [0,0,1,1]


def test_http_success_with_unchanged_output_is_not_reported_as_success():
    driver = native_driver(); sent = []
    response = requests.Response(); response.status_code = 200
    response._content = json.dumps({'Agent':{'SerialNumber':'PDU1'}, 'Outputs':[
        {'ID':i,'Name':str(i),'State':s} for i,s in zip([1,2,3,4],[0,0,1,1])]}).encode()
    driver._send_request = lambda payload: sent.append(payload) or response
    with pytest.raises(RuntimeError,match='state not confirmed'):
        driver.set_channels_states_local([5,1,5,5])
    assert len(sent) == 1 and driver._states == [0,0,1,1]


def test_all_untouched_outputs_only_refresh_and_never_post():
    driver = native_driver(); reads = []
    driver.get_channels_state_local = lambda: reads.append(True) or 0
    driver._send_request = lambda payload: pytest.fail('No-change request must not write')
    assert driver.set_channels_states_local([5,6,5,6]) == 0
    assert reads == [True]
