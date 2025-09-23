from tango import AttrWriteType, DispLevel
from tango.server import attribute

from DeviceServers.General.DS_general import DS_General


class DS_SYNC_GENERAL(DS_General):
    RULES = {**DS_General.RULES}

    def init_device(self):
        self.sync_impulse = 0
        super(DS_SYNC_GENERAL, self).init_device()

    @attribute(
        label="Sync impulse",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Give the sync impulse of main clock",
        polling_period=25,
        abs_change=1,
    )
    def sync(self):
        return self.sync_impulse
