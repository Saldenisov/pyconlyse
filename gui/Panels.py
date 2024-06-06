from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon, QMouseEvent, QKeyEvent
from PyQt5.QtCore import Qt
from taurus.qt.qtgui.input import TaurusValueCheckBox
from abc import abstractmethod
import pyqtgraph as pg
import numpy as np
from utilities.datastructures.mes_independent.measurments_dataclass import DataXY, GammaSpectrometerBG, \
    GammaSpectrometerBlank, GammaSpectrometerMeasurement
from DeviceServers.STANDA.DS_STANDA_Widget import Standa_motor
from DeviceServers.BASLER.DS_BASLER_Widget import Basler_camera
from DeviceServers.ANDOR_CCD.DS_ANDOR_CCD_Widget import ANDOR_CCD
from DeviceServers.AVANTES_CCD.DS_AVANTES_CCD_Widget import AVANTES_CCD
from DeviceServers.NETIO.DS_NETIO_Widget import Netio_pdu
from DeviceServers.Experiment.DS_Experiment_Widget import Experiment
from DeviceServers.OWIS.DS_OWIS_widget import OWIS_motor
from DeviceServers.TopDirect.DS_TOPDIRECT_Widget import TopDirect_Motor
from DeviceServers.LaserPointing.DS_LaserPointing_Widget import LaserPointing
from DeviceServers.ARCHIVE.DS_ARCHIVE_Widget import Archive
from DeviceServers.DS_Widget import DS_General_Widget
from DeviceServers.DS_Widget import VisType


class GeneralPanel(QtWidgets.QWidget):

    def __init__(self, choice, widget_class: DS_General_Widget, title='', icon: QIcon = None, width=2,
                 vis_type=VisType.FULL, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vis_type = vis_type
        self.widgets = {}

        if title:
            self.setWindowTitle(title)
        if icon:
            self.setWindowIcon(icon)

        self.layout_main = QtWidgets.QVBoxLayout()

        self.width = width
        self.number_ds = len(choice)
        self.active_widget = ''

        number_lo = 1 if self.number_ds // self.width == 0 else self.number_ds // width

        for lo_i in range(number_lo):
            setattr(self, f'lo_DS_widget_{lo_i}', QtWidgets.QHBoxLayout())
            lo: QtWidgets.QLayout = getattr(self, f'lo_DS_widget_{lo_i}')
            self.layout_main.addLayout(lo)
            separator = QtWidgets.QFrame()
            separator.setFrameShape(QtWidgets.QFrame.HLine)
            separator.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            separator.setLineWidth(3)
            self.layout_main.addWidget(separator)

        self.widget_creation(choice, widget_class)
        self.label_active_widget = QtWidgets.QLabel(f'Active widget: {self.active_widget}') 
        self.layout_main.addWidget(self.label_active_widget)
        self.setLayout(self.layout_main)

    def add_widget(self, name, widget):
        self.widgets[name] = widget

    def widget_creation(self, choice, widget_class):
        i = 0
        for dev_name in choice:
            group_number = i // self.width
            if dev_name:
                lo: Qt.QLayout = getattr(self, f'lo_DS_widget_{group_number}')
                setattr(self, f'{dev_name}', widget_class(dev_name, self, self.vis_type))
                s_m = getattr(self, f'{dev_name}')
                self.add_widget(f'{dev_name}', s_m)
                hspacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
                lo.addWidget(s_m)
                lo.addSpacerItem(hspacer)
            i += 1

    def update_active_widget(self):
        self.label_active_widget.setText(self.active_widget)


class StandaPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Standa_motor:
            raise Exception(f'Wrong widget class {widget_class} is passed.')

        super().__init__(choice=choice, widget_class=widget_class, title=title, icon=icon, width=width, *args, **kwargs)
        self.move_step = 1

    def update_active_widget(self):
        super(StandaPanel, self).update_active_widget()
        for w_name, widget in self.widgets.items():
            if w_name != self.active_widget:
                widget.setStyleSheet("")
                widget.widget_active = False
            else:
                widget.widget_active = True


class TopDirectPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != TopDirect_Motor:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice=choice, widget_class=widget_class, title=title, icon=icon, width=width, *args, **kwargs)
        self.move_step = 1

    def keyPressEvent(self, event: QKeyEvent):
        if self.active_widget:
            ds_widget = self.widgets[self.active_widget]
            pos = float(ds_widget.pos_widget.text())
            if event.key() in [Qt.Key_Left, Qt.Key_Down, Qt.Key_Right, Qt.Key_Up]:
                if event.key() in [Qt.Key_Left, Qt.Key_Down]:
                    pos = pos - self.move_step
                elif event.key() in [Qt.Key_Right, Qt.Key_Up]:
                    pos = pos + self.move_step
                ds_widget.wheel.setValue(pos)
                ds_real = getattr(ds_widget, f'ds_{self.active_widget}')
                ds_real.move_axis_abs(pos)

    def update_background_widgets(self):
        for w_name, widget in self.widgets.items():
            if w_name != self.active_widget:
                widget.setStyleSheet("")


class OWISPanel(GeneralPanel):
    """
    This class determines the panel for OWIS PS90 multi-axes controller.
    """

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=1, *args, **kwargs):
        if widget_class != OWIS_motor:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice=choice, widget_class=widget_class, title=title, icon=icon, width=width, *args, **kwargs)
        self.move_step = 1
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

    def widget_creation(self, choice, widget_class):
        i = 0
        for dev_name, axes in choice:
            group_number = i // self.width
            if dev_name:
                lo: Qt.QLayout = getattr(self, f'lo_DS_widget_{group_number}')
                setattr(self, f'{dev_name}', widget_class(dev_name, axes, self, self.vis_type))
                s_m = getattr(self, f'{dev_name}')
                self.add_widget(f'{dev_name}', s_m)
                lo.addWidget(s_m)
            i += 1

    def context_menu(self):
        pass


class NetioPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Netio_pdu:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ExperimentPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Experiment:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class BaslerPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Basler_camera:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ANDOR_CCDPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != ANDOR_CCD:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class AVANTES_CCDPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != AVANTES_CCD:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)
        self.spectrometer_clicked = False
        button_spectometer_control = QtWidgets.QPushButton('Spectrometer Control')
        button_spectometer_control.clicked.connect(self.add_spectrometer)
        self.layout_main.addWidget(button_spectometer_control)

    def sync_type(self, rb_measure: QtWidgets.QRadioButton, rb_bg: QtWidgets.QRadioButton, ds):
        if rb_measure.isChecked():
            ds.bg_measurement = 0
        elif rb_bg.isChecked():
            ds.bg_measurement = 1

    def add_spectrometer(self):
        if not self.spectrometer_clicked:
            layout_spectrometer = QtWidgets.QVBoxLayout()
            layout_spectrometer.addWidget(QtWidgets.QLabel('Spectrometer control'))

            layout_spectrometer.addSpacerItem(QtWidgets.QSpacerItem(0, 5, QtWidgets.QSizePolicy.Expanding,
                                                                    QtWidgets.QSizePolicy.Minimum))

            lo_sig_ref = QtWidgets.QHBoxLayout()
            lo_sig_ref.addWidget(QtWidgets.QLabel('Signal spectrometer'))
            cb_signal = QtWidgets.QComboBox()
            cb_signal.addItems(list(self.widgets.keys()))
            cb_signal.setCurrentIndex(0)
            lo_sig_ref.addWidget(cb_signal)
            lo_sig_ref.addWidget(QtWidgets.QLabel('Reference spectrometer'))
            cb_ref = QtWidgets.QComboBox()
            cb_ref.addItems(list(self.widgets.keys()))
            cb_ref.setCurrentIndex(len(self.widgets) - 1)
            lo_sig_ref.addWidget(cb_ref)
            rb_group = QtWidgets.QGroupBox('Sync for:')
            rb_lo = QtWidgets.QHBoxLayout()
            rb_bg = QtWidgets.QRadioButton('BG')
            rb_measurement = QtWidgets.QRadioButton('Measurement')
            rb_measurement.setChecked(True)
            rb_measurement.toggled.connect(lambda:self.sync_type(rb_measurement, rb_bg,
                                                                 self.widgets[list(self.widgets.keys())[0]]))
            rb_bg.toggled.connect(lambda:self.sync_type(rb_measurement, rb_bg,
                                                        self.widgets[list(self.widgets.keys())[0]]))
            rb_lo.addWidget(rb_bg)
            rb_lo.addWidget(rb_measurement)
            rb_group.setLayout(rb_lo)
            lo_sig_ref.addWidget(rb_group)

            lo_controls = QtWidgets.QHBoxLayout()
            button_measure_bg = QtWidgets.QPushButton('Measure BG')
            button_measure_blank = QtWidgets.QPushButton('Measure Blank')
            button_measure_sample = QtWidgets.QPushButton('Measure Sample Once')
            button_measure_cyclic = QtWidgets.QPushButton('Measure Sample Cyclic')
            lo_controls.addWidget(button_measure_bg)
            lo_controls.addWidget(button_measure_blank)
            lo_controls.addWidget(button_measure_sample)
            lo_controls.addWidget(button_measure_cyclic)

            # parameters
            lo_parameters = QtWidgets.QHBoxLayout()
            lo_parameters.addWidget(QtWidgets.QLabel('Average'))
            sb_average = QtWidgets.QSpinBox()
            sb_average.setValue(3)
            lo_parameters.addWidget(sb_average)
            lo_parameters.addWidget(QtWidgets.QLabel('Exposure, us'))
            dsb_exposure = QtWidgets.QDoubleSpinBox()
            dsb_exposure.setMinimum(20)
            dsb_exposure.setMaximum(1000000.0)
            dsb_exposure.setValue(500.0)
            lo_parameters.addWidget(dsb_exposure)
            lo_parameters.addWidget(QtWidgets.QLabel('Every n sec'))
            sb_every_sec = QtWidgets.QSpinBox()
            sb_every_sec.setValue(5)
            lo_parameters.addWidget(sb_every_sec)
            lo_parameters.addWidget(QtWidgets.QLabel('N measurement'))
            sb_n_measurements = QtWidgets.QSpinBox()
            sb_n_measurements.setValue(100)
            lo_parameters.addWidget(sb_n_measurements)


            # Image
            lo_image = QtWidgets.QHBoxLayout()
            view = pg.GraphicsLayoutWidget(parent=self, title='DATA')
            pg.setConfigOptions(antialias=True)

            self.plot_od = view.addPlot(title="Spectra", row=0, column=0)
            self.plot_od.curves = []

            self.plot_od.setLabel('left', "O.D.", units='counts')
            self.plot_od.setLabel('bottom', "Wavelength", units='nm')
            self.add_curve(self.plot_od, DataXY(X=np.arange(200, 800, 1), Y=np.zeros(600)))  # spectra

            view.setMinimumSize(450, 250)

            lo_image_buttons = QtWidgets.QVBoxLayout()
            button_clear_image = QtWidgets.QPushButton('Clear all')
            lo_image_buttons.addWidget(button_clear_image)

            lo_image.addWidget(view)
            lo_image.addLayout(lo_image_buttons)

            # data
            lo_data = QtWidgets.QHBoxLayout()
            lo_data.addWidget(QtWidgets.QLabel('Name of sample:'))
            le_data_name = QtWidgets.QLineEdit()
            lo_data.addWidget(le_data_name)
            button_save_data = QtWidgets.QPushButton('Save')
            lo_data.addWidget(button_save_data)


            layout_spectrometer.addLayout(lo_sig_ref)
            layout_spectrometer.addLayout(lo_controls)
            layout_spectrometer.addLayout(lo_parameters)
            layout_spectrometer.addLayout(lo_image)
            layout_spectrometer.addLayout(lo_data)



            self.layout_main.addLayout(layout_spectrometer)
            self.spectrometer_clicked = True
        else:
            pass

    def measure_bg(self):
        ref = np.zeros(2000)

    def update_curve(self, plot, i, data: DataXY):
        plot.curves[i].setData(data.X, data.Y)

    def add_curve(self, plot, data: DataXY):  # add a curve
        plot.curves.append(plot.plot(data.X, data.Y))

    def del_curve(self, plot, i):
        plot.curves[i].clear()


class LaserPointingPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != LaserPointing:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ArchivePanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Archive:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)
