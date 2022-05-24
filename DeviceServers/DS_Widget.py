from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueCheckBox
from taurus import Device
from taurus.external.qt import Qt
from PyQt5 import QtWidgets
from enum import Enum
from abc import abstractmethod
from threading import Thread

class VisType(Enum):
    MIN = 'min'
    FULL = 'full'


class DS_General_Widget(Qt.QWidget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        """
        width: number of devices in a row
        """
        super().__init__(parent)
        self.dev_name = device_name
        print(f'Creating widget for {self.dev_name}...')
        self.parent = parent
        self.vis_type = vis_type
        self.layout_main = Qt.QVBoxLayout()
        setattr(self, f'ds_{self.dev_name}', Device(self.dev_name))
        setattr(self, f'lo_group_{1}', Qt.QHBoxLayout())
        self.layout_main.addLayout(getattr(self, f'lo_group_{1}'))
        self.setLayout(self.layout_main)
        self.widget_active = False

        self.before_ds()

        if self.vis_type == VisType.FULL:
            self.register_DS_full()
        elif self.vis_type == VisType.MIN:
            self.register_DS_min()

        # self.ds_sync = Device('elyse/clocks/sync_main')
        # self.ds_sync.subscribe_event("sync", tango.EventType.CHANGE_EVENT, self.sync_listener)

        print(f'Widget for {self.dev_name} is created.')


    def before_ds(self):
        pass

    @abstractmethod
    def register_DS_full(self, group_number=1):
        self.register_full_layouts()

    @abstractmethod
    def register_DS_min(self, group_number=1):
        self.register_min_layouts()

    def set_state_status(self, short=True):
        dev_name = self.dev_name
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        widgets = [TaurusLabel(), TaurusLed(), TaurusLabel(), TaurusValueCheckBox()]
        i = 1
        for s in widgets:
            setattr(self, f's{i}_{dev_name}', s)
            i += 1
        s1: TaurusLabel = getattr(self, f's1_{dev_name}')
        s2 = getattr(self, f's2_{dev_name}')
        s3 = getattr(self, f's3_{dev_name}')
        s4 = getattr(self, f's4_{dev_name}')

        s1.model = f'{dev_name}/device_friendly_name'
        s2.model = f'{dev_name}/state'
        s4.model = f'{dev_name}/alway_on'
        lo_status.addWidget(s2)
        lo_status.addWidget(s1)
        lo_status.addWidget(s4)
        if not short:
            s3.model = f'{dev_name}/status'
            lo_status.addWidget(s3)

        hspacer = QtWidgets.QSpacerItem(0, 40, QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Minimum)
        lo_status.addSpacerItem(hspacer)

    @abstractmethod
    def register_full_layouts(self):
        setattr(self, f'layout_main_{self.dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_status_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_info_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_error_info_{self.dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_buttons_{self.dev_name}', Qt.QHBoxLayout())

    @abstractmethod
    def register_min_layouts(self):
        setattr(self, f'layout_main_{self.dev_name}', Qt.QVBoxLayout())
        setattr(self, f'layout_status_{self.dev_name}', Qt.QHBoxLayout())

    @property
    def ds(self):
        ds: Device = getattr(self, f'ds_{self.dev_name}')
        return ds

    @abstractmethod
    def set_the_control_value(self, value):
        pass

    def execute_action(self, value, device: Device, func_name, threaded=False):
        if threaded:
            ex_thread = Thread(target=self.execute_action, args=[value, device, func_name])
            ex_thread.start()
        else:
            func = getattr(device, func_name)
            func(value)

    # def sync_listener(self, event):
    #     val = self.ds_sync.sync
    #     self.sync_count.setText(f'Count: {val}')
