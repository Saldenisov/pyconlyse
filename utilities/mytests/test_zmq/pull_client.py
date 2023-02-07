import numpy as np
import zmq
from functools import partial
from threading import Thread
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout, \
    QDoubleSpinBox, QGridLayout, QScrollArea
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
        self.tabs_names = {}
        self.startWorkerThread()
        # set the title
        self.setWindowTitle("ELYSE control")

        width = 800
        height = 500

        # setting the minimum size
        self.setMinimumSize(width, height)

    def startWorkerThread(self):
        # Start the worker thread
        self.thread = WorkerThread()
        self.thread.data_signal.connect(self.update)
        self.thread.start()

    def update(self, message: str):
        msg = eval(message)
        for msg_part in msg:
            name = '/'.join(msg_part[0].split('/')[0:2])
            if name not in self.tabs_names:
                self.add_tab(name, msg_part)

    def add_tab(self, name, values):
        """
        "elyse/sync/NI6071E/delay/0.000000"
        """
        tab = QWidget()
        setattr(self, f'tab_{name}', tab)
        layout = QVBoxLayout(self)
        scrollbar = QScrollArea(widgetResizable=True)
        scrollbar.setWidget(tab)
        for value in values:
            label = QLabel()
            split = value.split('/')
            if len(split) <= 3:
                continue
            text = '/'.join(split[-3:-1])
            val = float(split[-1])
            lo_h = QHBoxLayout()
            sb = QDoubleSpinBox()
            sb.setValue(val)
            label.setText(text)
            lo_h.addWidget(label)
            lo_h.addWidget(sb)
            layout.addLayout(lo_h)
        tab.setLayout(layout)
        self.tabs.addTab(scrollbar, name)
        self.tabs_names[name] = tab

    def update_tab(self, name, values):
        pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TabWindow()
    window.show()
    sys.exit(app.exec_())



