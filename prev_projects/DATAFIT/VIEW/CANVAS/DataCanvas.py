from VIEW.CANVAS import MyMplCanvas
import numpy as np

class DataCanvas(MyMplCanvas):
    """
    Represents 2D data map using matplotlib imshow
    """
    def __init__(self, *args, **kwargs):
        MyMplCanvas.__init__(self, *args, **kwargs)

    def compute_initial_figure(self, data_model,
                               figure_name=None):
        self.model = data_model
        data = data_model.data
        wavelengths = data_model.wavelengths
        timedelays = data_model.timedelays
        self.maxv = np.max(data)
        if self.maxv < 1:
            data = data * 1000000.0
            self.maxv = self.maxv * 1000000
        self.minv = np.min(data)

        interpolation = 'none'
        self.dataplot = self.Fig.add_subplot(111)
        self.image = self.dataplot.imshow(data,
                                          extent=[wavelengths[0],
                                                  wavelengths[-1],
                                                  timedelays[-1],
                                                  timedelays[0]],
                                          aspect='auto',
                                          vmin=self.minv,
                                          vmax=self.maxv,
                                          interpolation=interpolation)
        self.dataplot.grid(True)

        self.dataplot.set_xlabel('Wavelength, nm')
        self.dataplot.set_ylabel('Time delay, ~s')
        # self.dataplot.set_title(figure_name)

        self.Fig.colorbar(self.image)

    def update_figure(self):
        k = len(self.dataplot.lines)
        if k > 2:
            for _ in range(k):
                self.dataplot.lines[-1].remove()
        cur = self.model.cursors
        self.dataplot.axhline(y=self.model.timedelays[cur['y1']], color='r')
        self.dataplot.axhline(y=self.model.timedelays[cur['y2']-1], color='r')
        self.dataplot.axvline(x=self.model.wavelengths[cur['x1']], color='r')
        self.dataplot.axvline(x=self.model.wavelengths[cur['x2']-1], color='r')

        self.draw()

    def update_limits(self, minv, maxv):
        """
        update vmin and vmax of imshow
        """
        self.image.set_clim(vmin=minv, vmax=maxv)

        self.draw()
