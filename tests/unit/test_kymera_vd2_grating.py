"""Software-only SDK model: numeric selection, metadata and unit contracts."""

import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from tests._tango_stub import install_tango_stub


class _CollectionMonkeyPatch:
    def setitem(self, mapping, key, value):
        mapping[key] = value


install_tango_stub(_CollectionMonkeyPatch())

from DeviceServers.spectrographs.andor.DS_ANDOR_SPECTROGRAPH import DS_ANDOR_SPECTROGRAPH


def make_device(*, current=1, blaze="800", selected=2, powered=True):
    moves = []
    state = {"grating": current}

    def select(index):
        moves.append(index)
        state["grating"] = selected

    sdk = SimpleNamespace(
        get_grating=lambda: state["grating"],
        set_grating=select,
        get_grating_info=lambda index: (150.0, blaze, 0, 0),
    )
    device = SimpleNamespace(
        spectrograph=sdk,
        _get_lifecycle_lock=nullcontext,
        _power_dependency_allows_hardware_operation=lambda **kwargs: powered,
        refresh_calibration_axis=lambda: None,
        _parse_blaze_nm=DS_ANDOR_SPECTROGRAPH._parse_blaze_nm,
    )
    return device, moves


def test_physical_index_two_is_selected_and_blaze_remains_in_nm():
    device, moves = make_device()
    result = json.loads(DS_ANDOR_SPECTROGRAPH.PrepareVD2Grating(device))
    assert moves == [2]
    assert result == {"grating": 2, "ruling": 150.0, "blaze": 800.0}
    assert device.blaze_wavelength_nm_value == 800.0


def test_verified_index_two_is_not_moved_again():
    device, moves = make_device(current=2)
    DS_ANDOR_SPECTROGRAPH.PrepareVD2Grating(device)
    assert moves == []


@pytest.mark.parametrize("blaze", ["300", "nan", "invalid"])
def test_wrong_target_metadata_fails_before_motion(blaze):
    device, moves = make_device(blaze=blaze)
    with pytest.raises((RuntimeError, ValueError)):
        DS_ANDOR_SPECTROGRAPH.PrepareVD2Grating(device)
    assert moves == []


def test_wrong_selection_readback_is_rejected():
    device, moves = make_device(selected=1)
    with pytest.raises(RuntimeError, match="selected grating 1"):
        DS_ANDOR_SPECTROGRAPH.PrepareVD2Grating(device)
    assert moves == [2]


def test_unconfirmed_power_is_rejected_before_sdk_access():
    device, moves = make_device(powered=False)
    with pytest.raises(RuntimeError, match="power"):
        DS_ANDOR_SPECTROGRAPH.PrepareVD2Grating(device)
    assert moves == []


def test_legacy_blaze_attribute_uses_the_sdk_nm_contract():
    device, _ = make_device()
    device.current_grating = 2
    DS_ANDOR_SPECTROGRAPH._read_grating_info(device, device.spectrograph)
    assert device.blaze_wavelength_nm_value == 800.0


@pytest.mark.parametrize("value", ["800nm", "800 nm", "800.0NM", "800", 800.0])
def test_sdk_blaze_string_contract(value):
    device, _ = make_device(blaze=value)
    assert json.loads(DS_ANDOR_SPECTROGRAPH.PrepareVD2Grating(device))["blaze"] == 800.0


@pytest.mark.parametrize("serials, expected_index", [(["KY-3804"], 0), (["UV-123", "KY-3804"], 1)])
def test_serial_identity_survives_enumeration_changes(monkeypatch, serials, expected_index):
    opened = []
    sdk = SimpleNamespace(get_device_info=lambda: SimpleNamespace(serial_number="KY-3804"))
    andor = SimpleNamespace(
        list_shamrock_spectrographs=lambda: serials,
        ShamrockSpectrograph=lambda idx: opened.append(idx) or sdk,
    )
    monkeypatch.setitem(DS_ANDOR_SPECTROGRAPH._create_spectrograph.__globals__, "get_andor_module", lambda **kwargs: andor)
    device = SimpleNamespace(
        dll_path="", shamrock_dll_path="", spectrograph_index=1,
        spectrograph_serial="KY-3804", _coerce_int=DS_ANDOR_SPECTROGRAPH._coerce_int,
    )
    assert DS_ANDOR_SPECTROGRAPH._create_spectrograph(device) is sdk
    assert opened == [expected_index]


@pytest.mark.parametrize("serials", [["UV-123"], ["KY-3804", "KY-3804"]])
def test_missing_or_duplicate_identity_never_opens_another_instrument(monkeypatch, serials):
    opened = []
    andor = SimpleNamespace(
        list_shamrock_spectrographs=lambda: serials,
        ShamrockSpectrograph=lambda idx: opened.append(idx),
    )
    monkeypatch.setitem(DS_ANDOR_SPECTROGRAPH._create_spectrograph.__globals__, "get_andor_module", lambda **kwargs: andor)
    device = SimpleNamespace(
        dll_path="", shamrock_dll_path="", spectrograph_index=1,
        spectrograph_serial="KY-3804", _coerce_int=DS_ANDOR_SPECTROGRAPH._coerce_int,
    )
    with pytest.raises(RuntimeError, match="not uniquely available"):
        DS_ANDOR_SPECTROGRAPH._create_spectrograph(device)
    assert opened == []


def test_identity_change_during_open_closes_sdk_without_configuring(monkeypatch):
    closed = []
    sdk = SimpleNamespace(
        get_device_info=lambda: SimpleNamespace(serial_number="UV-123"),
        close=lambda: closed.append(True),
    )
    andor = SimpleNamespace(
        list_shamrock_spectrographs=lambda: ["KY-3804"],
        ShamrockSpectrograph=lambda idx: sdk,
    )
    monkeypatch.setitem(DS_ANDOR_SPECTROGRAPH._create_spectrograph.__globals__, "get_andor_module", lambda **kwargs: andor)
    device = SimpleNamespace(
        dll_path="", shamrock_dll_path="", spectrograph_index=0,
        spectrograph_serial="KY-3804", _coerce_int=DS_ANDOR_SPECTROGRAPH._coerce_int,
    )
    with pytest.raises(RuntimeError, match="identity changed"):
        DS_ANDOR_SPECTROGRAPH._create_spectrograph(device)
    assert closed == [True]
