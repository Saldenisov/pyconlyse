import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import QThread, pyqtSignal
import time


class WorkerThread(QThread):
    # Define a signal to send data from the worker thread to the main thread
    data_signal = pyqtSignal(str)

    def run(self):
        # Function to run in a separate thread
        time.sleep(5)
        self.data_signal.emit("Worker Thread Done!")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.resize(300, 300)
        self.setWindowTitle("MainWindow")

        # Create a vertical layout for the widgets
        layout = QVBoxLayout()

        # Create a label
        self.label = QLabel("Running in Main Thread")
        layout.addWidget(self.label)

        # Create a button
        self.button = QPushButton("Start Worker Thread")
        self.button.clicked.connect(self.startWorkerThread)
        layout.addWidget(self.button)

        # Create a widget to hold the layout
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def startWorkerThread(self):
        # Start the worker thread
        self.thread = WorkerThread()
        self.thread.data_signal.connect(self.updateLabel)
        self.thread.start()

    def updateLabel(self, text):
        # Update the label with the data from the worker thread
        self.label.setText(text)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
