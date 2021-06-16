from matplotlib import gridspec
from numpy import zeros
from VIEW.CANVAS import MyMplCanvas


class FitCanvas(MyMplCanvas):

    def __init__(self, *args, **kwargs):
        MyMplCanvas.__init__(self, *args, **kwargs)

    def compute_initial_figure(self, fitmodel):
        self.fitmodel = fitmodel
        timedelays = fitmodel.X
        signal = fitmodel.Y
        fit = fitmodel.fit
        from_p = fitmodel.parameters['cursors']['y1']
        to_p = fitmodel.parameters['cursors']['y2'] + 1

        self.coff = 1

        self.ymin = min(signal)
        self.ymax = max(signal)
        self.ymin_pos = min(abs(signal))
        if self.ymin_pos == 0:
            self.ymin_pos = self.ymax * 0.001

        gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])

        self.dataplot = self.Fig.add_subplot(gs[0])
        self.residual = self.Fig.add_subplot(gs[1])

        self.dataplot.plot(timedelays, signal, 'b')
        self.dataplot.plot(timedelays[from_p:to_p], signal[from_p:to_p], 'r')
        self.dataplot.plot(timedelays[from_p:to_p], fit, 'g')

        self.residual.plot(timedelays,
                           zeros(len(timedelays)), 'black')
        self.residual.plot(timedelays[from_p:to_p],
                           (signal[from_p:to_p] - fit), 'g')

        self.dataplot.axhline(y=0, color='black')

        self.dataplot.grid(True)
        self.residual.grid(True)

        self.residual.set_xlabel('Time Delay, ~s')
        self.dataplot.set_ylabel('Intensity')
        self.residual.set_ylabel('Residual')

    def set_fitting_param(self, model, variables):
        if model == 'Gauss_1exp_conv' or model == 'Gauss_1exp_conv_constrained' or model == 'Gauss_1exp_iter_constrained' or model == 'Gauss_1exp_iter':
            y0 = str(round(variables['y0'], 2))
            A = str(round(variables['A'], 2))
            sigma = str(round(variables['sigma'], 2))
            x0 = str(round(variables['x0'], 2))
            tau = str(round(variables['tau'], 2))
            self.dataplot.set_title(
                r'Fit equation: $Y=\frac{1}{%(sigma)s \cdot \sqrt{2\pi}} \exp(-\frac{(t-%(x0)s)^2}{2 \cdot %(sigma)s ^2}) \ast %(A)s \cdot \exp(-\frac{t}{%(tau)s})+%(y0)s$' % vars(), y=1.04)

        elif model == 'Gauss_2exp_conv' or model == 'Gauss_2exp_conv_constrained':

            y0 = str(round(variables['y0'], 2))
            sigma = str(round(variables['sigma'], 2))
            x0 = str(round(variables['x0'], 2))
            tau1 = str(round(variables['tau1'], 2))
            tau2 = str(round(variables['tau2'], 2))
            A1 = str(round(variables['a1'], 2))
            A2 = str(round(variables['a2'], 2))
            self.dataplot.set_title(
                r'equation: $Y=\frac{1}{%(sigma)s \cdot \sqrt{2\pi}} \exp(-\frac{(t-%(x0)s)^2}{2 \cdot %(sigma)s ^2}) \ast (%(A1)s \cdot \exp(-\frac{(t-%(x0)s}{%(tau1)s})+%(A2)s \cdot \exp(-\frac{(t-%(x0)s}{%(tau2)s}))+%(y0)s$' % vars(), y=1.04)
        else:
            self.text = self.dataplot.text(5, 8, 'Unknown...', fontsize=12)

    def scale_update(self, logX=False, logY=False, Norm=False):
        if Norm:
            self.coff = max(abs(self.fitmodel.Y))
        else:
            self.coff = 1

        if logX:
            self.dataplot.set_xscale('log')
        else:
            self.dataplot.set_xscale('linear')
            self.dataplot.autoscale_view(True, True, True)

        if logY:
            self.dataplot.set_yscale('log')
            self.dataplot.set_ylim(ymin=(self.ymin_pos) / self.coff)
            self.dataplot.set_ylim(ymax=self.ymax / self.coff)
        else:
            self.dataplot.set_yscale('linear')
            self.dataplot.set_ylim(ymin=self.ymin / self.coff)
            self.dataplot.set_ylim(ymax=self.ymax / self.coff)
            self.dataplot.autoscale_view(True, True, True)

        self.draw()

    def update_figure(self,
                      logX=False,
                      logY=False,
                      Norm=False):
        model = "CHANGE IT"
        variables = self.fitmodel.parameters['variables']

        timedelays = self.fitmodel.X
        signal = self.fitmodel.Y
        fit = self.fitmodel.fit
        from_p = self.fitmodel.parameters['cursors']['y1']
        to_p = self.fitmodel.parameters['cursors']['y2'] + 1

        self.dataplot.lines[-1].remove()
        self.dataplot.lines[-1].remove()
        self.dataplot.lines[-1].remove()
        self.dataplot.lines[-1].remove()

        self.residual.lines[-1].remove()

        #self.set_fitting_param(model, variables)

        self.dataplot.relim()
        self.residual.relim()

        self.scale_update(logX, logY, Norm)

        self.residual.autoscale_view(True, True, True)


        self.dataplot.plot(timedelays,
                           signal / self.coff, 'b')
        self.dataplot.plot(timedelays[from_p:to_p],
                           signal[from_p:to_p] / self.coff, 'r')
        t = timedelays[from_p:to_p]
        self.dataplot.plot(t, fit, 'g')

        self.dataplot.axhline(y=0, color='black')

        self.residual.plot(timedelays[from_p:to_p],
                           (signal[from_p:to_p] / self.coff - fit), 'g')

        self.draw()
