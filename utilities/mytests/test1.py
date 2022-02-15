# -*- coding: utf-8 -*-
"""
Demonstrate ability of ImageItem to be used as a canvas for painting with
the mouse.

"""
from PIL import Image
import numpy as np

im_frame = Image.open('C:\\dev\\pyconlyse\\bin\\icons\\layout.png')
np_frame = np.array(im_frame)

img_data = np.flipud(np.array(Image.open('C:\\dev\\pyconlyse\\bin\\icons\\layout.png')))

from pyqtgraph.Qt import QtCore, QtGui
import numpy as np
import pyqtgraph as pg

app = pg.mkQApp("Draw Example")

## Create window with GraphicsView widget
w = pg.GraphicsView()
w.show()
w.setWindowTitle('pyqtgraph example: Draw')

view = pg.ViewBox()
w.setCentralItem(view)

## Create image item
image = img_data.transpose([1, 0, 2])
img = pg.ImageItem(image)
view.addItem(img)

circle = pg.CircleROI([1850, 850], [120, 120], movable=False, resizable=False, pen=pg.mkPen('r', width=2))
view.addItem(circle)

view.setMouseEnabled(x=False,y=False)
view.enableAutoRange(x=True,y=True)


if __name__ == '__main__':
    pg.exec()