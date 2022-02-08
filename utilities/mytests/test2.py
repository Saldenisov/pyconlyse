# Set up a window with plot
import pyqtgraph as pg
win = pg.GraphicsLayoutWidget()
plt = win.addPlot()
plt.plot(x=[0, 0.1, 0.2, 0.3, 0.4], y=[1, 7, 2, 4, 3])

# Add a ViewBox below with two rectangles
vb = win.addViewBox(col=0, row=1)
r1 = pg.QtGui.QGraphicsRectItem(0, 0, 0.4, 1)
r1.setPen(pg.mkPen(None))
r1.setBrush(pg.mkBrush('r'))
vb.addItem(r1)
circle = pg.CircleROI([250, 250], [120, 120], pen=pg.mkPen('r',width=2))
vb.addItem(circle)

# Make the ViewBox flat
vb.setMaximumHeight(70)

# Force y-axis to be always auto-scaled
vb.setMouseEnabled(y=False)
vb.enableAutoRange(y=True)

# Force x-axis to match the plot above
vb.setXLink(plt)