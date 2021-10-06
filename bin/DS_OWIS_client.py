import sys
from taurus.qt.qtgui.input import TaurusValueLineEdit, TaurusValueSpinBox, TaurusWheelEdit
from taurus import Device
from taurus.external.qt import Qt
from taurus.qt.qtgui.application import TaurusApplication
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed


class Owis_panel(Qt.QWidget):
    def __init__(self, devices_names, window='', parent=None):
        super().__init__(parent)
        self.layout_main = Qt.QHBoxLayout()

        for dev_name in devices_names:
            ds = Device(dev_name)

            setattr(self, f'l_min_{dev_name}', float(ds.get_property('limit_min')['limit_min'][0]))
            setattr(self, f'l_max_{dev_name}', float(ds.get_property('limit_max')['limit_max'][0]))
            l_min, l_max = getattr(self, f'l_min_{dev_name}'), getattr(self, f'l_max_{dev_name}')

            setattr(self, f'layout_main_{dev_name}', Qt.QVBoxLayout())
            setattr(self, f'layout_status_{dev_name}', Qt.QHBoxLayout())
            setattr(self, f'layout_pos_{dev_name}', Qt.QHBoxLayout())
            lo_main: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
            lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
            lo_pos: Qt.QLayout = getattr(self, f'layout_pos_{dev_name}')
            lo_main.addLayout(lo_status)
            lo_main.addLayout(lo_pos)

            widgets = [TaurusLabel(), TaurusLed(), TaurusLabel()]
            i = 1
            for s in widgets:
                setattr(self, f's{i}_{dev_name}', s)
                i += 1
            s1 = getattr(self, f's1_{dev_name}')
            s2 = getattr(self, f's2_{dev_name}')
            s3 = getattr(self, f's3_{dev_name}')
            s1.model = f'{dev_name}/uri'
            s2.model = f'{dev_name}/state'
            s3.model = f'{dev_name}/status'
            lo_status.addWidget(s1)
            lo_status.addWidget(s2)
            lo_status.addWidget(s3)

            widgets = [TaurusLabel(), TaurusLabel(), TaurusWheelEdit(), TaurusLabel()]
            i = 1
            for w in widgets:
                name = f'w{i}_{dev_name}'
                setattr(self, f'{name}', w)
                i += 1
            w1 = getattr(self, f'w{1}_{dev_name}')
            w2 = getattr(self, f'w{2}_{dev_name}')
            w3 = getattr(self, f'w{3}_{dev_name}')
            w4 = getattr(self, f'w{4}_{dev_name}')

            w3.setMinValue(l_min)
            w3.setMaxValue(l_max)
            w3._setDigits(3)

            lo_pos.addWidget(w1)
            lo_pos.addWidget(w2)
            lo_pos.addWidget(w3)
            lo_pos.addWidget(w4)

            w1.model, w1.bgRole = f'{dev_name}/position#label', ''
            w2.model = f'{dev_name}/position'
            w3.model = f'{dev_name}/position'
            w4.model, w4.bgRole = f'{dev_name}/position#rvalue.units', ''

            self.layout_main.addLayout(lo_main)

        self.setLayout(self.layout_main)
        self.setWindowTitle(window)
        self.show()

def main():
    app = TaurusApplication(sys.argv, cmd_line_parser=None,)
    p = Owis_panel(["manip/VD2/DLs_VD2", "manip/V0/DLs_V0", "manip/V0/DLl1_V0", "manip/V0/DLl2_V0"], 'OWIS')
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
