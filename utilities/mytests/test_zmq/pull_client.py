import numpy as np
import zmq
from functools import partial
from threading import Thread
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout, \
    QDoubleSpinBox, QGridLayout, QScrollArea, QSpacerItem, QSizePolicy
from PyQt5.QtCore import QThread, pyqtSignal
from typing import List


class WorkerThread(QThread):
    # Define a signal to send data from the worker thread to the main thread
    data_signal = pyqtSignal(str)

    def run(self):
        # Function to run in a separate thread
        context = zmq.Context()
        socket = context.socket(zmq.PULL)
        socket.bind("tcp://127.0.0.1:5555")

        while True:
            message: str = socket.recv().decode('utf-8')
            self.data_signal.emit(message)

        socket.close()
        context.destroy()


class TabWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pull = True
        # Set up the tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs_widgets = {}
        self.layouts = {}
        self.tabs_elements = {}
        self.startWorkerThread()
        # set the title
        self.setWindowTitle("ELYSE control")

        width = 800
        height = 500

        # setting the minimum size
        self.setMinimumSize(width, height)

        self.primary = True

        context = zmq.Context()
        self.socket = context.socket(zmq.PUSH)
        self.socket.connect("tcp://127.0.0.1:5556")

    def startWorkerThread(self):
        # Start the worker thread
        self.thread = WorkerThread()
        self.thread.data_signal.connect(self.update)
        self.thread.start()

    def update(self, message: str):
        msg = eval(message)
        for card in msg:
            for elem in card:
                split = elem.split('/')
                if len(split) <= 3:
                    continue
                tab_name = '/'.join(split[0:2])
                elem_name = '/'.join(split[-3:-1])

                if f'tab_{tab_name}' not in self.tabs_widgets:
                    self.add_tab(tab_name)

                if f'tab_{tab_name}_label_{elem_name}' not in self.tabs_elements:
                    self.add_element(elem_name, tab_name, elem)
                else:
                    self.update_element(tab_name, elem_name, elem)

    def add_tab(self, name):
        """
        "elyse/sync/NI6071E/delay/0.000000"
        """
        tab = QWidget()
        layout = QVBoxLayout(self)
        scrollbar = QScrollArea(widgetResizable=True)
        scrollbar.setWidget(tab)
        tab.setLayout(layout)
        self.tabs.addTab(scrollbar, name)
        self.tabs_widgets[f'tab_{name}'] = tab
        self.layouts[f'layout_{name}'] = layout

    def add_element(self, element_name, tab_name, element_value: str):
        split = element_value.split('/')
        if len(split) > 3:
            label = QLabel()
            text = '/'.join(split[-3:])
            val = float(split[-1])
            sb = QDoubleSpinBox()
            sb.setValue(val)
            sb.valueChanged.connect(partial(self.change_sb_value, tab_name, element_name))
            label.setText(text)
            elem_name = '/'.join(split[-3:-1])
            self.tabs_elements[f'tab_{tab_name}_label_{elem_name}'] = label
            self.tabs_elements[f'tab_{tab_name}_sb_{elem_name}'] = sb
            layout: QVBoxLayout = self.layouts[f'layout_{tab_name}']
            lo_h = QHBoxLayout()
            lo_h.addWidget(label)
            spacer_h1 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
            # lo_h.addItem(spacer_h1)
            lo_h.addWidget(sb)
            spacer_h2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
            lo_h.addItem(spacer_h2)
            layout.addLayout(lo_h)

    def update_element(self, tab_name: str, elem_name: str, value: str):
        split = value.split('/')
        text = '/'.join(split[-3:])
        label = self.tabs_elements[f'tab_{tab_name}_label_{elem_name}']
        label.setText(text)

    def change_sb_value(self, tab_name, elem_name):
        sb: QDoubleSpinBox = self.tabs_elements[f'tab_{tab_name}_sb_{elem_name}']
        if not self.primary:
            val = f'{tab_name}/{elem_name}/{sb.value()}'
            self.socket.send(val.encode('utf-8'))
            print(f'{tab_name}/{elem_name}/{sb.value()}')
        else:
            self.primary = False

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TabWindow()
    window.show()
    sys.exit(app.exec_())



