from collections import deque
from pathlib import Path
import sys
app_folder = Path(__file__).resolve().parents[0]
sys.path.append(str(app_folder))
import numpy as np
import pyqtgraph as pg
from dataclasses import dataclass, field
from typing import List, Dict
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
from data_classes import *
uint8 = np.dtype('uint8')
int16 = np.dtype('int16')
float32 = np.dtype('float32')

import logging
logger = logging.getLogger('root')





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
            parent_archive: Experiment = parent.parent_archive
            parent_archive.del_curve(parent, res)


class Experiment(DS_General_Widget):

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.structure = {}
        self.dataset_name = ''
        self.translation_stage = TranslationStages()
        self.sample_holder = SampleHolder()
        self.settings = Settings()
        self.projects: Dict[str, str] = {}
        self.measurements: Dict[str, str] = {}

        super().__init__(device_name, parent, vis_type)

    def register_DS_full(self, group_number=1):
        super().register_DS_full()
        dev_name = self.dev_name

        ds: Device = getattr(self, f'ds_{dev_name}')
        lo_group: Qt.QHBoxLayout = getattr(self, f'lo_group_{group_number}')

        lo_device: Qt.QLayout = getattr(self, f'layout_main_{dev_name}')
        lo_status: Qt.QLayout = getattr(self, f'layout_status_{dev_name}')
        lo_control: Qt.QLayout = getattr(self, f'layout_control_{dev_name}')

        # State and status
        self.set_state_status(False)

        # Set Experimental control zone
        from DeviceServers.Experiment.ui_experiment import Ui_experiment_widget

        self.ui = Ui_experiment_widget()
        self.ui.setupUi(self)
        # C:/dev/pyconlyse/DeviceServers/Experiment/

        # Sample holder
        available_cell_holders: Dict[str, Dict[str, float]] = eval(self.ds.available_cell_holders)
        group_box = self.ui.groupBox_positions_samples
        _translate = QtCore.QCoreApplication.translate
        for sample_holder_name, positions in available_cell_holders.items():
            rb = QtWidgets.QRadioButton(self.ui.groupBox_sample_holder_type)
            rb.setText(_translate("experiment_widget", f"{sample_holder_name}"))
            setattr(self.ui, f'sample_holder_{sample_holder_name}', rb)
            rb.toggled.connect(partial(self.rb_clicked_sample_holder, rb.text()))
            self.ui.horizontalLayout_samples.addWidget(rb)
        rb.setChecked(True)

        lo_control.addLayout(self.ui.horizontalLayout_experimental_widget)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_control)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        self.register_DS_full(group_number)

    def register_full_layouts(self):
        super().register_full_layouts()
        setattr(self, f'layout_control_{self.dev_name}', Qt.QHBoxLayout())

    def register_min_layouts(self):
        self.register_full_layouts()

    def rb_clicked_sample_holder(self, value: str):
        available_cell_holders: Dict[str, Dict[str, float]] = eval(self.ds.available_cell_holders)
        param = available_cell_holders[value]
        _translate = QtCore.QCoreApplication.translate

        count = self.ui.horizontalLayout_samples_pos.count()
        if count != 1:
            for i in reversed(range(self.ui.horizontalLayout_samples_pos.count())):
                widget = self.ui.horizontalLayout_samples_pos.itemAt(i).widget()
                widget.deleteLater()

        for name, pos in param.items():
            rb = QtWidgets.QRadioButton(self.ui.groupBox_positions_samples)
            rb.setText(_translate("experiment_widget", f"{name}:{pos}"))
            rb.toggled.connect(partial(self.rb_clicked_pos, pos))
            self.ui.horizontalLayout_samples_pos.addWidget(rb)


    def rb_clicked_pos(self, pos: float):
        self.translation_stage.sc.move_axis_abs(float)