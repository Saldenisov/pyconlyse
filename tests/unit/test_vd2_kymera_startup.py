"""Shutter ownership handoff from the Kymera SDK default to direct VD2."""

from types import SimpleNamespace

import pytest

from web.backend.vd2_tango_optics import prepare_direct_shutter


class Kymera:
    def __init__(self, state, *, accept_write=True):
        self.shutter = state
        self.accept_write = accept_write
        self.writes = []

    def read_attribute(self, name):
        assert name == "shutter"
        return SimpleNamespace(value=self.shutter)

    def write_attribute(self, name, value):
        self.writes.append((name, value))
        if self.accept_write:
            self.shutter = value


def test_external_bnc_startup_is_closed_and_verified():
    kymera = Kymera("External BNC")
    assert prepare_direct_shutter(kymera) == "Closed"
    assert kymera.writes == [("shutter", "Closed")]


@pytest.mark.parametrize("shutter", ["Closed", "Open"])
def test_explicit_shutter_mode_is_retained(shutter):
    kymera = Kymera(shutter)
    assert prepare_direct_shutter(kymera) == shutter
    assert kymera.writes == []


def test_external_mode_write_without_closed_readback_is_rejected():
    kymera = Kymera("External BNC", accept_write=False)
    with pytest.raises(RuntimeError, match="did not confirm Closed"):
        prepare_direct_shutter(kymera)
    assert kymera.writes == [("shutter", "Closed")]


@pytest.mark.parametrize("shutter", [None, "Unknown", ""])
def test_unknown_shutter_mode_blocks_preparation(shutter):
    kymera = Kymera(shutter)
    with pytest.raises(RuntimeError, match="unavailable"):
        prepare_direct_shutter(kymera)
    assert kymera.writes == []
