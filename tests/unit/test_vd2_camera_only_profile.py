"""Camera-only startup profile admission and RemoteEx isolation."""
import pytest

from DeviceServers.cameras.hamamatsu_streak.camera_only_profile import checked_camera_only_ini
from DeviceServers.cameras.hamamatsu_streak.hamamatsu_streak_controller import HamamatsuStreakController


def test_camera_only_ini_requires_disabled_spectrograph_and_generator(tmp_path):
    profile = tmp_path / "VD2_RemoteEx.hwp"
    ini = tmp_path / "RemoteEx.INI"
    ini.write_text(f"[Init]\nHWprofile={profile}\n", encoding="utf-16")
    devices = "[External devices]\nUseDeviceType1=-1\nUseDeviceType2=0\nUseDeviceType3=0\nUseDeviceType4=0\nUseDeviceType5=0\n"
    profile.write_text(devices, encoding="utf-16")
    assert checked_camera_only_ini(str(ini)) == str(ini)
    profile.write_text(devices.replace("UseDeviceType3=0", "UseDeviceType3=-1"), encoding="utf-16")
    with pytest.raises(ValueError, match="only the streak camera"):
        checked_camera_only_ini(str(ini))


@pytest.mark.parametrize("command", ["DevParamGet(Spec,Wavelength)", "DevParamSet(Del,Burst Mode,On)", "AppStart()"])
def test_camera_only_controller_rejects_external_or_replacement_command(command):
    controller = HamamatsuStreakController(None)
    controller.camera_only = True
    with pytest.raises(ValueError):
        controller.execute_raw(command)
