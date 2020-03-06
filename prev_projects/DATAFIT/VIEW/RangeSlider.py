import sys
from PyQt5 import QtCore, QtGui, QtWidgets

try:
    _fromUtf8 = str
except AttributeError:
    _fromUtf8 = lambda s: s

__all__ = ['QRangeSlider']

DEFAULT_CSS = """
QRangeSlider * {
    border: 0px;
    padding: 0px;
}
QRangeSlider #Head {
    background: #222;
}
QRangeSlider #Span {
    background: #393;
}
QRangeSlider #Span:active {
    background: #282;
}
QRangeSlider #Tail {
}
QRangeSlider > QSplitter::handle {
    background: #950;
}
QRangeSlider > QSplitter::handle:vertical {
    height: 5px;
}
QRangeSlider > QSplitter::handle:pressed {
    background: #ca5;
}

"""


def scale(val, src, dst):
    """
    Scale the given value from the scale of src to the scale of dst.
    """
    return int(((val - src[0]) / float(src[1] - src[0])) * (dst[1] - dst[0]) + dst[0])


class Ui_Form(object):
    """
    default range slider form
    """

    def setupUi(self, Form, size_pixels):
        Form.setObjectName(_fromUtf8("QRangeSlider"))
        Form.resize(size_pixels, 10)
        Form.setStyleSheet(_fromUtf8(DEFAULT_CSS))
        Form.setStyleSheet(DEFAULT_CSS)

        self.layout = QtWidgets.QHBoxLayout(Form)

        self.splitter = QtWidgets.QSplitter(Form)
        self.splitter.setMinimumSize(QtCore.QSize(0, 0))
        self.splitter.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.splitter.setOrientation(QtCore.Qt.Horizontal)

        self._head = QtWidgets.QGroupBox(self.splitter)

        self._handle = QtWidgets.QGroupBox(self.splitter)

        self._tail = QtWidgets.QGroupBox(self.splitter)

        self.layout.addWidget(self.splitter)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(QtWidgets.QApplication.translate(
            "QRangeSlider", "QRangeSlider", None))


class Element(QtWidgets.QGroupBox):

    def __init__(self, parent, main):
        super(Element, self).__init__(parent)
        self.main = main

    def setStyleSheet(self, style):
        """redirect style to parent groupbox"""
        self.parent().setStyleSheet(style)

    def textColor(self):
        """text paint color"""
        return getattr(self, '__textColor', QtGui.QColor(125, 125, 125))

    def setTextColor(self, color):
        """set the text paint color"""
        if type(color) == tuple and len(color) == 3:
            color = QtGui.QColor(color[0], color[1], color[2])
        elif type(color) == int:
            color = QtGui.QColor(color, color, color)
        setattr(self, '__textColor', color)

    def paintEvent(self, event):
        """overrides paint event to handle text"""
        qp = QtGui.QPainter()
        qp.begin(self)
        if self.main.drawValues():
            self.drawText(event, qp)
        qp.end()


class Head(Element):
    """area before the handle"""

    def __init__(self, parent, main):
        super(Head, self).__init__(parent, main)

    def drawText(self, event, qp):
        qp.setPen(self.textColor())
        qp.setFont(QtGui.QFont('Arial', 10))
        qp.drawText(event.rect(), QtCore.Qt.AlignLeft, str(self.main.min()))


class Tail(Element):
    """area after the handle"""

    def __init__(self, parent, main):
        super(Tail, self).__init__(parent, main)

    def drawText(self, event, qp):
        qp.setPen(self.textColor())
        qp.setFont(QtGui.QFont('Arial', 10))
        qp.drawText(event.rect(), QtCore.Qt.AlignRight, str(self.main.max()))


class Handle(Element):
    """handle area"""

    def __init__(self, parent, main):
        super(Handle, self).__init__(parent, main)

    def drawText(self, event, qp):
        qp.setPen(self.textColor())
        qp.setFont(QtGui.QFont('Arial', 10))
        qp.drawText(event.rect(), QtCore.Qt.AlignLeft, str(self.main.start()))
        qp.drawText(event.rect(), QtCore.Qt.AlignRight, str(self.main.end()))

    def mouseMoveEvent(self, event):
        event.accept()
        mx = event.globalX()
        _mx = getattr(self, '__mx', None)

        if not _mx:
            setattr(self, '__mx', mx)
            dx = 0
        else:
            dx = mx - _mx

        setattr(self, '__mx', mx)

        if dx == 0:
            event.ignore()
            return
        elif dx > 0:
            dx = 1
        elif dx < 0:
            dx = -1

        s = self.main.start() + dx
        e = self.main.end() + dx
        if s >= self.main.min() and e <= self.main.max():
            self.main.setRange(s, e)


class QRangeSlider(QtWidgets.QWidget, Ui_Form):
    """
    The QRangeSlider class implements a horizontal range slider widget.

    Inherits QWidget.

    Methods
        * __init__ (self, QWidget parent = None)
        * bool drawValues (self)
        * int end (self)
        * (int, int) getRange (self)
        * int max (self)
        * int min (self)
        * int start (self)
        * setBackgroundStyle (self, QString styleSheet)
        * setDrawValues (self, bool draw)
        * setEnd (self, int end)
        * setStart (self, int start)
        * setRange (self, int start, int end)
        * setSpanStyle (self, QString styleSheet)

    Signals
        * endValueChanged (int)
        * maxValueChanged (int)
        * minValueChanged (int)
        * startValueChanged (int)

    Customizing QRangeSlider

    You can style the range slider as below:
    ::
        QRangeSlider * {
            border: 0px;
            padding: 0px;
        }
        QRangeSlider #Head {
            background: #222;
        }
        QRangeSlider #Span {
            background: #393;
        }
        QRangeSlider #Span:active {
            background: #282;
        }
        QRangeSlider #Tail {
            background: #222;
        }

    Styling the range slider handles follows QSplitter options:
    ::
        QRangeSlider > QSplitter::handle {
            background: #393;
        }
        QRangeSlider > QSplitter::handle:vertical {
            height: 1px;
        }
        QRangeSlider > QSplitter::handle:pressed {
            background: #ca5;
        }

    """
    # define splitter indices
    _SPLIT_START = 1
    _SPLIT_END = 2

    # signals
    minValueChanged = QtCore.pyqtSignal(int)
    maxValueChanged = QtCore.pyqtSignal(int)
    startValueChanged = QtCore.pyqtSignal(int)
    endValueChanged = QtCore.pyqtSignal(int)
    ValueChanged = QtCore.pyqtSignal(int, int, int)

    def __init__(self, min, max, start, end, size_pixels, parent=None, *args, **kwargs):
        """Create a new QRangeSlider instance.

            :param parent: QWidget parent
            :return: New QRangeSlider instance.

        """
        super(QRangeSlider, self).__init__(parent)
        self.setupUi(self, size_pixels)
        self.setMouseTracking(False)
        self.splitter_width = size_pixels
        min = int(min)
        max = int(max)
        start = int(start)
        end = int(end)

        self.splitter.setChildrenCollapsible(True)
        self.splitter.setCollapsible(1, True)

        self.splitter.splitterMoved.connect(self.handleMoveSplitter)

        # handle layout
        self._handle_layout = QtWidgets.QHBoxLayout()
        self._handle_layout.setSpacing(0)
        self._handle_layout.setContentsMargins(0, 10, 0, 0)
        self._handle.setLayout(self._handle_layout)
        self.handle = Handle(self._handle, main=self)
        self.handle.setTextColor((150, 255, 150))
        self._handle_layout.addWidget(self.handle)

        # defaults
        self.setMin(min)
        self.setMax(max)
        self.setStart(start)
        self.setEnd(end)
        self.setDrawValues(True)

        self.update_Sliderpos()

    def update_Sliderpos(self):

        start = self.valueToPos(self.start())
        end = self.valueToPos(self.end())

        self.splitter.setSizes([start, end, self.splitter_width - end])

    def setMin(self, value):
        """sets minimum value"""
        assert type(value) is int
        setattr(self, '__min', value)
        self.minValueChanged.emit(value)

    def setMax(self, value):
        """sets maximum value"""
        assert type(value) is int
        setattr(self, '__max', value)
        self.maxValueChanged.emit(value)

    def _setStart(self, value):
        """stores the start value only"""
        setattr(self, '__start', value)
        self.startValueChanged.emit(value)

    def setStart(self, value):
        """sets the range slider start value"""
        assert type(value) is int

        self._setStart(value)

    def _setEnd(self, value):
        """stores the end value only"""
        setattr(self, '__end', value)
        self.endValueChanged.emit(value)

    def setEnd(self, value):
        """set the range slider end value"""
        assert type(value) is int

        self._setEnd(value)

    def start(self):
        """:return: range slider start value"""
        return getattr(self, '__start', None)

    def end(self):
        """:return: range slider end value"""
        return getattr(self, '__end', None)

    def min(self):
        """:return: minimum value"""
        return getattr(self, '__min', None)

    def max(self):
        """:return: maximum value"""
        return getattr(self, '__max', None)

    def drawValues(self):
        """:return: True if slider values will be drawn"""
        return getattr(self, '__drawValues', None)

    def setDrawValues(self, draw):
        """sets draw values boolean to draw slider values"""
        assert type(draw) is bool
        setattr(self, '__drawValues', draw)

    def getRange(self):
        """:return: the start and end values as a tuple"""
        return (self.start(), self.end())

    def setRange(self, start, end):
        """set the start and end values"""
        self.setStart(start)
        self.setEnd(end)

    def keyPressEvent(self, event):
        """overrides key press event to move range left and right"""
        key = event.key()
        if key == QtCore.Qt.Key_Left:
            s = self.start() - 1
            e = self.end() - 1
        elif key == QtCore.Qt.Key_Right:
            s = self.start() + 1
            e = self.end() + 1
        else:
            event.ignore()
            return
        event.accept()
        if s >= self.min() and e <= self.max():
            self.setRange(s, e)

    def setBackgroundStyle(self, style):
        """sets background style"""
        self._tail.setStyleSheet(style)
        self._head.setStyleSheet(style)

    def setSpanStyle(self, style):
        """sets range span handle style"""
        self._handle.setStyleSheet(style)

    def valueToPos(self, value):
        """converts slider value to local pixel x coord"""

        return scale(value, (self.min(), self.max()), (0, self.splitter_width))

    def posToValue(self, xpos):
        """converts local pixel x coord to slider value"""
        return scale(xpos, (0, self.splitter_width), (self.min(), self.max()))

    def handleMoveSplitter(self, xpos, index):
        """private method for handling moving splitter handles"""

        self.splitter_width = self.splitter.width()

        if index == self._SPLIT_START:
            v = self.posToValue(xpos)
            if v >= self.max():
                v = self.max()
            self._setStart(v)

        elif index == self._SPLIT_END:
            v = self.posToValue(xpos + 5)
            if v >= self.max():
                v = self.max()

            self._setEnd(v)
        self.ValueChanged.emit(index, self.start(), self.end())
