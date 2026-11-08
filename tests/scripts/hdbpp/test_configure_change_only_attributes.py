from scripts.hdbpp.configure_change_only_attributes import (
    PROFILES,
    configure_attribute,
)


class FakeManager:
    def __init__(self):
        self.writes = []
        self.commands = []

    def write_attribute(self, name, value):
        self.writes.append((name, value))

    def command_inout(self, name, *args):
        self.commands.append((name, args))


def test_acceptance_profile_is_small_and_disposable():
    assert PROFILES["acceptance"] == (
        "test/hdbpp/probe/value",
        "test/hdbpp/probe/sequence",
        "test/hdbpp/probe/last_changed_at_utc",
    )


def test_configuration_uses_code_push_and_no_period():
    manager = FakeManager()
    configure_attribute(manager, "test/hdbpp/probe/value", "archiving/hdbpp/es01")
    assert ("SetPollingPeriod", 0) in manager.writes
    assert ("SetPeriodEvent", 0) in manager.writes
    assert ("SetCodePushedEvent", True) in manager.writes
    assert manager.commands == [("AttributeAdd", ())]


def test_laser_pointing_session_profile_keeps_both_controllers_separate():
    attributes = PROFILES["laser-pointing-sessions"]
    assert "manip/v0/laserpointing-cam1/alignment_reference_json" in attributes
    assert "manip/v0/laserpointing-cam2/alignment_reference_json" in attributes
    assert "manip/v0/laserpointing-cam1/automatic_search_history" not in attributes
