from collections import deque

import numpy as np
import pyqtgraph as pg
from taurus import Device
from taurus.core import TaurusDevState
from taurus.external.qt import Qt, QtCore
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueSpinBox, TaurusValueComboBox
from tango import DevState
from datetime import datetime
from PyQt5 import QtWidgets
from PyQt5.QtCore import QDate
from functools import partial
import zlib
import msgpack
from numpy import array
from utilities.datastructures.mes_independent.measurments_dataclass import ArchiveData, Scalar, Array, DataXY, DataXYb
from DeviceServers.DS_Widget import DS_General_Widget, VisType

uint8 = np.dtype('uint8')
int16 = np.dtype('int16')
float32 = np.dtype('float32')


class ViewTree(QtWidgets.QTreeWidget):
    def __init__(self):
        super().__init__()

    def fill_items(self, item, value):
        self.clean_tree()
        self.fill_item(item, value)

    def fill_item(self, item, value):

        def new_item(parent, text, val=None):
            child = QtWidgets.QTreeWidgetItem([text])
            self.fill_item(child, val)
            parent.addChild(child)
            child.setExpanded(True)

        if value is None:
            return
        elif isinstance(value, dict):
            for key, val in sorted(value.items()):
                new_item(item, str(key), val)
        elif isinstance(value, (list, tuple)):
            for val in value:
                text = (str(val) if not isinstance(val, (dict, list, tuple))
                        else '[%s]' % type(val).__name__)
                new_item(item, text, val)
        else:
            new_item(item, str(value))

    def clean_tree(self):
        parent = self.invisibleRootItem()
        for i in reversed(range(parent.childCount())):
            parent.removeChild(parent.child(i))


# Bar Graph class
class LegendItemClickable(pg.LegendItem):

    def __init__(self, *args, **kwargs):
        super(LegendItemClickable, self).__init__()

    # creating a mouse double click event
    def mouseDoubleClickEvent(self, e):
        y = e.pos().y()
        res = None
        for item, label in self.items:
            y_item = item.pos().y()
            if abs(y_item - y) <= 9:
                res = label.text
                break
        if res:
            print(f'Deleting {res}')
            self.removeItem(res)
            parent: pg.plot = self.parentItem()
            parent_archive: Archive = parent.parent_archive
            parent_archive.del_curve(parent, res)


class Archive(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.structure = {}
        self.dataset_name = ''
        super().__init__(device_name, parent, vis_type)

    def register_DS_full(self, group_number=1):
        super(Archive, self).register_DS_full()
        dev_name = self.dev_name

        ds: Device = getattr(self, f'ds_{dev_name}')
        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_buttons: Qt.QLayout = getattr(self, f'layout_buttons_{dev_name}')
        lo_parameters: Qt.QLayout = getattr(self, f'layout_parameters_{dev_name}')
        lo_calendar: Qt.QLayout = getattr(self, f'layout_calendar_{dev_name}')
        lo_image: Qt.QLayout = getattr(self, f'layout_image_{dev_name}')

        # State and status
        self.set_state_status(False)

        # Set image
        self.set_image(lo_image)

        # Calendar
        self.calendar = QtWidgets.QCalendarWidget(parent=self)
        self.calendar.clicked.connect(self.structure_update)
        layout_v_all_trees = QtWidgets.QVBoxLayout()
        layout_h_tree = QtWidgets.QHBoxLayout()
        layout_h_tree_selectors = QtWidgets.QHBoxLayout()

        self.tree_structure = ViewTree()
        self.tree_structure.setMinimumWidth(450)
        self.tree_structure.setMinimumHeight(300)
        self.tree_structure.itemClicked.connect(self.get_dataset_info)
        self.tree_structure.itemDoubleClicked.connect(self.get_dataset)

        self.tree_devices = ViewTree()
        self.tree_devices.setMinimumWidth(300)
        self.tree_devices.setMinimumHeight(300)
        self.tree_devices.itemClicked.connect(self.get_dataset_info)
        self.tree_devices.itemDoubleClicked.connect(self.get_dataset)

        self.projects_cb = QtWidgets.QCheckBox('Projects')
        self.projects_cb.setChecked(True)
        self.devices_cb = QtWidgets.QCheckBox('Devices')
        self.devices_cb.setChecked(True)
        self.date_cb = QtWidgets.QCheckBox('Selected date?')
        self.projects_cb.clicked.connect(self.structure_update)
        self.devices_cb.clicked.connect(self.structure_update)
        self.date_cb.clicked.connect(self.structure_update)

        layout_h_tree_selectors.addWidget(self.projects_cb)
        layout_h_tree_selectors.addWidget(self.devices_cb)
        layout_h_tree_selectors.addWidget(self.date_cb)
        layout_h_tree.addWidget(self.tree_structure)
        layout_h_tree.addWidget(self.tree_devices)
        layout_v_all_trees.addLayout(layout_h_tree)
        layout_v_all_trees.addLayout(layout_h_tree_selectors)
        self.selected_object = QtWidgets.QLabel(self.dataset_name)
        layout_v_all_trees.addWidget(self.selected_object)

        layout_data_selection = QtWidgets.QHBoxLayout()
        self.dataset_info = QtWidgets.QLabel('')
        layout_data_selection.addWidget(self.dataset_info)
        self.average_data = QtWidgets.QSpinBox()
        self.average_data.setMinimum(1)
        self.average_data.setMaximum(20)
        self.average_data.setMaximumWidth(40)
        layout_data_selection.addWidget(self.average_data)
        self.date_from = QtWidgets.QDateTimeEdit()
        self.date_to = QtWidgets.QDateTimeEdit()
        self.date_to.setDate(datetime.now())
        self.date_to.setTime(datetime.now().time())
        layout_data_selection.addWidget(self.date_from)
        layout_data_selection.addWidget(self.date_to)
        self.button_set_dates = QtWidgets.QPushButton('Dates Min/Max')
        self.button_set_dates.clicked.connect(self.min_max_dates)
        layout_data_selection.addWidget(self.button_set_dates)
        layout_v_all_trees.addLayout(layout_data_selection)

        lo_calendar.addWidget(self.calendar)
        lo_calendar.addLayout(layout_v_all_trees)

        # Buttons and commands
        setattr(self, f'button_on_{dev_name}', TaurusCommandButton(command='turn_on'))
        button_on: TaurusCommandButton = getattr(self, f'button_on_{dev_name}')
        button_on.setModel(dev_name)

        setattr(self, f'button_off_{dev_name}', TaurusCommandButton(command='turn_off'))
        button_off: TaurusCommandButton = getattr(self, f'button_off_{dev_name}')
        button_off.setModel(dev_name)

        self.button_tree_structure = QtWidgets.QPushButton('Archive Tree')
        self.button_tree_structure.clicked.connect(self.fill_tree_structure)
        self.button_structure_device = QtWidgets.QPushButton('Device Archive')
        self.button_structure_device.clicked.connect(self.fill_device_tree_structure)

        lo_buttons.addWidget(button_on)
        lo_buttons.addWidget(button_off)
        lo_buttons.addWidget(self.button_tree_structure)
        lo_buttons.addWidget(self.button_structure_device)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_parameters)
        lo_device.addLayout(lo_calendar)
        lo_device.addLayout(lo_image)
        lo_group.addLayout(lo_device)

    def min_max_dates(self):
        if self.dataset_name:
            min_max_timestamps = eval(self.ds.get_object_timestamps(self.dataset_name))

            self.date_from.setDate(datetime.fromtimestamp(min_max_timestamps[0]))
            self.date_to.setDate(datetime.fromtimestamp(min_max_timestamps[1]))

    @staticmethod
    def check_if_date(s: str):
        try:
            datetime.strptime(s, '%Y-%m-%d')
            return True
        except TypeError:
            return False

    def get_dataset_info(self, item: QtWidgets.QTreeWidgetItem):
        def construct_name(item: QtWidgets.QTreeWidgetItem, s):
            parent = item.parent()
            if parent:
                s.append(parent.text(0))
                s = construct_name(parent, s)
            return s
        path = construct_name(item, [item.text(0)])
        if not self.check_if_date(path[-1]):
            path.append('any_date')
        path.reverse()
        if not self.date_cb.isChecked():
            path[0] = 'any_date'
        self.dataset_name = '/'.join(path)
        self.selected_object.setText(self.dataset_name)
        info = self.ds.get_info_object(self.dataset_name)
        self.dataset_info.setText(info)

    def get_dataset(self, item: QtWidgets.QTreeWidgetItem):
        def construct_name(item: QtWidgets.QTreeWidgetItem, s):
            parent = item.parent()
            if parent:
                s.append(parent.text(0))
                s = construct_name(parent, s)
            return s
        path = construct_name(item, [item.text(0)])
        if not self.check_if_date(path[-1]):
            path.append('any_date')
        path.reverse()
        dataset_name = '/'.join(path)
        print(f'Getting dataset {dataset_name}.')
        average = str(self.average_data.value())
        date_from = self.date_from.dateTime().toPyDateTime().timestamp()
        date_to = self.date_from.dateTime().toPython().timestamp()
        data_string = self.ds.get_data([dataset_name, '-1', '-1', average])
        if data_string:
            data_bytes = eval(data_string)
            data_d = zlib.decompress(data_bytes)
            data_d = msgpack.unpackb(data_d, strict_map_key=False)
            data_d: DataXYb = eval(data_d)

            data = DataXY(X=np.frombuffer(data_d.X, dtype=data_d.Xdtype),
                          Y=np.frombuffer(data_d.Y, dtype=data_d.Ydtype),
                          name=data_d.name)
            self.add_curve(self.plot, data)

    def add_curve(self, plot: pg.PlotItem, data: DataXY): # add a curve
        p = plot.plot(data.X, data.Y)
        plot.curves.append(p)
        plot.curves_names[data.name] = len(plot.curves) - 1
        self.legend.addItem(p, data.name)

    def del_curve(self, plot: pg.PlotItem, name):
        idx = plot.curves_names[name]
        plot.curves[idx].clear()
        plot.replot()

    def set_image(self, lo_image):
        self.view = pg.GraphicsLayoutWidget(parent=self, title='DATA')
        pg.setConfigOptions(antialias=True)

        self.plot = self.view.addPlot(title="Spectra", row=0, column=0, axisItems={'bottom': pg.DateAxisItem()})
        self.plot.parent_archive = self
        self.plot.setLabel('left', "Data", units='')
        self.plot.setLabel('bottom', "Timestamp", units='')
        self.plot.curves_names = {}

        self.view.setMinimumSize(500, 450)

        self.legend = LegendItemClickable((80, 60), offset=(70, 20))
        self.legend.setParentItem(self.plot)
        lo_image.addWidget(self.view)

    def register_DS_min(self, group_number=1):
        self.register_DS_full(group_number)

    def register_full_layouts(self):
        super(Archive, self).register_full_layouts()
        setattr(self, f'layout_parameters_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_calendar_{self.dev_name}', Qt.QHBoxLayout())
        setattr(self, f'layout_image_{self.dev_name}',  QtWidgets.QHBoxLayout())

    def register_min_layouts(self):
        self.register_full_layouts()

    def get_structure(self):
        structure = self.ds.archive_structure
        self.structure = eval(structure)

    def fill_device_tree_structure(self):
        self.get_structure()
        device_structure = self.form_device_tree_structure()
        self.tree_devices.fill_items(self.tree_devices.invisibleRootItem(), device_structure)

    def fill_tree_structure(self):
        self.get_structure()
        structure = self.form_main_tree_structure()
        self.tree_structure.fill_items(self.tree_structure.invisibleRootItem(), structure)

    def form_device_tree_structure(self):
        from copy import deepcopy
        date_s = '...'
        if not self.structure:
            self.get_structure()
        try:
            date_structure = deepcopy(self.structure)
            device_structure = {}
            for date, value in date_structure.items():
                device_structure.update(value)

        except KeyError:
            print(f'Such date {date_s} is not present in Archive.')
        finally:
            return device_structure

    def form_main_tree_structure(self, date=None):
        from copy import deepcopy
        date_structure = {}
        date_s = '...'
        if not self.structure:
            self.get_structure()
        try:
            if self.date_cb.isChecked() and date:
                date_s = date.toString('yyyy-MM-dd')
                date_structure[date_s] = deepcopy(self.structure[date_s])
            else:
                date_structure = deepcopy(self.structure)

            if not self.projects_cb.isChecked():
                to_del = []
                for date_key, value in date_structure.items():
                    if 'projects' in value:
                        to_del.append(date_key)
                if to_del:
                    for key in to_del:
                        del date_structure[key]['projects']

            if not self.devices_cb.isChecked():
                to_del = []
                for date_key, value in date_structure.items():
                    for loc_key in value.keys():
                        if loc_key != 'projects':
                            to_del.append((date_key, loc_key))
                if to_del:
                    for date_key, loc_key in to_del:
                        del date_structure[date_key][loc_key]

        except KeyError:
            print(f'Such date {date_s} is not present in Archive.')
        finally:
            return date_structure

    def structure_update(self):
        self.fill_tree_structure()
        self.fill_device_tree_structure()
