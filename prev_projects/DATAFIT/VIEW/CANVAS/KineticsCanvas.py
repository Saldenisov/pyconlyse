from VIEW.CANVAS import MyMplCanvas
from itertools import islice

import matplotlib.pyplot as plt


class KineticsCanvas(MyMplCanvas):

    def __init__(self, *args, **kwargs):
        self.alpha = 0.7
        MyMplCanvas.__init__(self, *args, **kwargs)

    def compute_initial_figure(self, data_model):
        self.model = data_model

        self.dataplot = self.Fig.add_subplot(111)

        self.dataplot.axhline(y=0, color='black')

        self.draw_figure_first()

        self.N_lines = 3

        self.dataplot.grid(True)

        self.dataplot.set_xlabel('Time Delay, ~s')
        self.dataplot.set_ylabel('Intensity')
        self.dataplot.set_title('Kinetics')

        self.draw()

    def draw_figure_total(self):
        pfrom, pto = self.model.get_from_to()
        timedelays = self.model.timedelays

        self.draw_figure_first()
        color_index = 0

        items = islice(self.model.kinetics.items(), 1, None)

        for key, data in items:
            color = self._colors[(color_index + 1) % len(self._colors)]
            label = data[0] + ' key:' + str(key)
            self.dataplot.plot(timedelays, data[1], color,
                               label=label,
                               picker=5)
            self.dataplot.plot(timedelays[pfrom:pto], data[1][pfrom:pto], 'r-',
                               alpha=self.alpha)


    def draw_figure_first(self):
        pfrom, pto = self.model.get_from_to()
        timedelays = self.model.timedelays

        data = self.model.kinetics['dynamic']

        self.dataplot.plot(timedelays, data[1], 'b', label=data[0])
        self.dataplot.plot(timedelays[pfrom:pto], data[1][pfrom:pto], 'r-',
                           alpha=self.alpha)


    def update_figure(self):
        """
        Removes all lines, and draws updated kinetics
        """
        # if number of kinetics in model did not change
        # update just last lines
        if len(self.dataplot.lines) - 1 == len(self.model.kinetics.keys()) * 2:
            self.dataplot.lines[-1].remove()
            self.dataplot.lines[-1].remove()
            self.draw_figure_first()
        # delete all and redraw
        else:
            n = int((len(self.dataplot.lines) - 1) / 2)
            for _ in range(n):
                self.dataplot.lines[-1].remove()
                self.dataplot.lines[-1].remove()
            self.draw_figure_total()

        self.dataplot.relim()

        self.dataplot.autoscale_view(True, True, True)

        self.draw()
