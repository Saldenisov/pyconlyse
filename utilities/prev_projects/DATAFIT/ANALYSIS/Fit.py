'''
Created on 12 aoÃ»t 2015

@author: saldenisov
'''
import logging

import numpy as np
from ANALYSIS.MyMath import gaussian, exp, exp2, stretch_exp
from ERRORS import NoSuchFittingFunction, FittingError
from scipy import integrate
from scipy.optimize import curve_fit
from scipy.optimize.optimize import OptimizeWarning
from scipy.signal import fftconvolve

module_logger = logging.getLogger(__name__)


class Fit(object):
    '''
    Fit is used to do fitting of curve Y=f(X) using
    func model
    '''

    def __init__(self, X, Y, parameters):
        '''
        Initial settings
        '''
        self.logger = logging.getLogger("MAIN." + __name__)
        self.from_p = parameters['cursors']['y1']
        self.to_p = parameters['cursors']['y2'] + 1
        self.method = parameters['method']
        self.X_full = np.asarray(X)
        self.X = X[self.from_p:self.to_p]
        self.Y_full = np.asarray(Y)
        self.Y = Y[self.from_p:self.to_p]
        self.variables = parameters['variables']

        _bounds = []
        self.guess = []
        for item in self.variables:
            self.guess.append(parameters['guess'][item])
            _bounds.append(parameters['bounds'][item])

        _min = [i[0] for i in _bounds]
        _max = [i[1] for i in _bounds]
        self.bounds = (_min, _max)

        self.coeffs = {}

    def dofit(self, pulse=False, constrained=False, iterat=False,
                      func=None, model='1exp'):
        """
        Fitting with exponential functions +/-
        constraints
        """
        def _1exp(x, *args):
            y0, A, tau = args
            sig = A * exp(x, tau) + y0
            return sig

        def _2exp(x, *args):
            y0, a1, tau1, a2, tau2 = args
            sig = a1 * exp(x, tau1) + a2 * exp(x, tau2) + y0
            return sig

        def _1exp_stretched(x, *args):
            y0, A, tau, beta = args
            sig = A * self.stretch_exp(x, tau, beta) + y0
            return sig

        def pulse_1exp(x, *args):
            y0, A, sigma, x0, tau = args
            Gaus = gaussian(x, A, sigma, x0)
            Exp = exp(x-x[0], tau)
            con = fftconvolve(Gaus, Exp)[0: len(Gaus)]
            return (con + y0)

        def pulse_1exp_iter(x, *args):
            y0, A, sigma, x0, tau = args
            signal = np.zeros(len(x))
            N1t = np.zeros(len(x))
            N1t1 = np.zeros(len(x))
            Gaus = gaussian(x, A, sigma, x0)
            for i in range(len(x)):
                if i == 0:
                    signal[i] = 0 + y0
                if i > 0:
                    dx = x[i] - x[i - 1]
                    N1t1[i] = (Gaus[i] - N1t[i - 1] / tau) * dx + N1t[i - 1]
                    N1t[i] = N1t1[i]
                    signal[i] = N1t1[i] + y0

            return signal[self.from_p:self.to_p]

        def pulse_2exp(x, *args):
            y0, A, sigma, x0, tau1, tau2, a1, a2 = args
            Gaus = gaussian(x, A, sigma, x0)
            Exp = exp2(x-x[0], a1, tau1, a2, tau2)
            con = fftconvolve(Gaus, Exp)[0:len(Gaus)]
            return (con + y0)

        def pulse_2exp_iter(x, *args):
            y0, A, sigma, x0, tau1, tau2, a1, a2 = args
            signal = np.zeros(len(x))
            N1t = np.zeros(len(x))
            N1t1 = np.zeros(len(x))
            N2t = np.zeros(len(x))
            N2t1 = np.zeros(len(x))
            Gaus = gaussian(x, A, sigma, x0)
            for i in range(len(x)):
                if i == 0:
                    signal[i] = 0 + y0
                if i > 0:
                    dx = x[i] - x[i - 1]
                    N1t1[i] = (a1 * Gaus[i] - N1t[i - 1] / tau1) * dx
                    + N1t[i - 1]
                    N1t[i] = N1t1[i]
                    N2t1[i] = (a2 * Gaus[i] - N2t[i - 1] / tau2) * dx
                    + N2t[i - 1]
                    N2t[i] = N2t1[i]
                    signal[i] = N1t1[i] + N2t1[i] + y0

            return signal[self.from_p:self.to_p]

        def pulse_1exp_stretched(x, *args):
            y0, A, sigma, x0, tau, beta = args
            Gaus = gaussian(x, A, sigma, x0)
            Exp = stretch_exp(x-x[0], tau, beta)
            con = fftconvolve(Gaus, Exp)[0:len(Gaus)]
            return (con + y0)

        def _distFRET_Gaussian(x, *args):
            y0, A, mu, sigma = args
            tauD = 170
            Fdist = 21
            step = 0.1
            distance = np.arange(0.01, 25, step)
            Gaus = gaussian(distance, A, sigma, mu)
            sig = []
            for time in x:
                Decay = np.exp(-time/tauD - time/tauD * (Fdist / distance)**6)
                res = Decay * Gaus
                sig.append(integrate.trapz(res, dx=step) + y0)
            return np.array(sig)

        if not func:
            model = '_' + model
            if pulse:
                model = "pulse" + model
            if not pulse:
                X = self.X - self.X[0]
            else:
                X = self.X
            if iterat:
                model = model + '_iter'
                X = self.X_full
            try:
                func = locals()[model]
            except KeyError as e:
                self.logger.error(e + ' function is not defined')
                raise NoSuchFittingFunction
        else:
            func = locals()[func]
            X = self.X

        bounds_local = self.bounds
        if not constrained:
            bounds_local = (-np.inf, np.inf)
            model_local = model
        else:
            model_local = model + '_constrained'

        try:
            coeffs, _ = curve_fit(f=func,
                                  xdata=X,
                                  ydata=self.Y,
                                  p0=self.guess,
                                  bounds=bounds_local,
                                  method=self.method)
            self.logger.info(model_local + " Success")

        except (ValueError, Exception) as e:
            self.logger.error(str(e) + model_local)
            coeffs = np.ones(len(self.variables))
            raise FittingError
        except OptimizeWarning:
            self.logger.info('OptimizeWarning: ' + model_local)
            raise
        finally:
            self.coeffs = dict(zip(self.variables, coeffs))
            return self.coeffs, func(X, *coeffs)
