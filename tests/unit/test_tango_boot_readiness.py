"""Boot readiness must reject stale exports and respect automatic server scope."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PATH = Path(__file__).resolve().parents[2] / 'bin/windows_startup/probe_tango_readiness.py'
SPEC = importlib.util.spec_from_file_location('boot_readiness', PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.fixture
def rig(monkeypatch):
    database = Mock()
    database.get_host_server_list.return_value = ['DS_Zaber/1_Zaber', 'DS_Standa_Motor/disabled']
    database.get_server_info.side_effect = lambda name: SimpleNamespace(mode=0 if 'disabled' in name else 1, level=1)
    starter = Mock()
    server = Mock()
    factory = Mock(side_effect=lambda name: starter if name == 'tango/admin/elysium2' else server)
    monkeypatch.setitem(sys.modules, 'tango', SimpleNamespace(Database=lambda: database, DeviceProxy=factory))
    return database, starter, server, factory


def test_ready_checks_live_admin_endpoint_and_excludes_disabled_servers(rig, capsys):
    database, starter, server, factory = rig
    probe._controlled_servers_ready('tango/admin/elysium2')
    assert [call.args[0] for call in factory.call_args_list] == ['tango/admin/elysium2', 'dserver/DS_Zaber/1_Zaber']
    server.ping.assert_called_once()
    server.state.assert_not_called()
    assert 'count=1' in capsys.readouterr().out


def test_stale_export_is_not_ready_even_when_starter_reports_running(rig):
    rig[2].ping.side_effect = RuntimeError('connection refused')
    with pytest.raises(RuntimeError, match='DS_Zaber/1_Zaber: connection refused'):
        probe._controlled_servers_ready('tango/admin/elysium2')


def test_no_automatic_servers_is_not_success(rig):
    rig[0].get_host_server_list.return_value = []
    with pytest.raises(RuntimeError, match='No automatic servers configured'):
        probe._controlled_servers_ready('tango/admin/elysium2')


def test_starts_only_stopped_automatic_servers(rig):
    rig[1].command_inout.return_value = ['DS_Zaber/1_Zaber']
    probe._start_controlled_servers('tango/admin/elysium2')
    assert rig[1].command_inout.call_args_list[0].args == ('DevGetStopServers', False)
    assert rig[1].command_inout.call_args_list[1].args == ('DevStart', 'DS_Zaber/1_Zaber')


def test_database_timeout_is_bounded_and_errors_propagate(rig):
    rig[0].get_server_list.side_effect = RuntimeError('database unavailable')
    with pytest.raises(RuntimeError, match='database unavailable'):
        probe._database_ready()
    rig[0].set_timeout_millis.assert_called_once_with(2500)
