# -*- coding: utf-8 -*-
"""
Created on Sat Nov 19 20:49:51 2016

@author: saldenisov
"""
import numpy as np
from scipy.optimize import curve_fit
from scipy.optimize.optimize import OptimizeWarning
from scipy.signal import fftconvolve
import matplotlib.pyplot as plt
from usefull import FittingError
from usefull import elongarray

import functools
def howmany(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.calls += 1
        if wrapper.calls % 50 == 0:
            print(wrapper.__name__ + ' is called ' + str(wrapper.calls) + ' times')
            ar = args[1:]
            print(ar)
        return func(*args, **kwargs)
    wrapper.calls = 0
    return wrapper


def fitbimolreactimedep(Xexp,
                    Yexp,
                    guess,
                    bounds,
                    sigmaG,
                    CqG,
                    extraN=4,
                    method='dogbox'):
    sigma = sigmaG * 10**-12
    Cq = CqG / 1000
    res = elongarray(Xexp, N=extraN)
    xnew = res[0]
    oldpos = res[1]
    dt = xnew[2] - xnew[1]
    
    def gaussian(x, x0):
        res = 1 / (2 * 3.14 * sigma) * np.exp(-(x - x0)**2 / (2 * sigma**2))
        return res
    
    @howmany
    def fitfunc(x, *args):
        A, t0, D, R, tau, part = args
        D = D * 10**-8
        R = R * 10**-9
        #ks = ks * 10**9
        Ce1 = 0
        Ce2 = 0
        t0 = t0 * 10**-12
        Yt = [Ce1 + Ce2]
        ts = t0 - 1.177 * sigma

        for t in xnew:
            if t>ts:
                k = 4 * 3.14 * D * R * (1 + R / (np.sqrt(4 * 3.14 * D * (t-ts)))) * 1000 * 6.02 * 10**23
            else:
                k = 0
            Ce1 = (part* A * gaussian(t, t0) -  k * Ce1 * Cq) * dt + Ce1
            Ce2 = ((1-part) * A * gaussian(t, t0) - Ce2*10**12 / tau) * dt + Ce2
            Yt.append(Ce1 + Ce2)

        Yt = np.array(Yt)[oldpos]
        #plt.plot(x, Yt)
        #plt.plot(x, Yexp)
        #plt.show()

        return Yt
        
    @howmany
    def fitfuncconv(x, *args):
        A, t0, D, R = args
        t0 = t0 * 10**-12
        D = D * 10**-9
        R = R * 10**-9
        Gaus = A * gaussian(x, t0)
        Exp = np.exp(-4 * 3.14 * D * R * Cq * 6.02 * 10**23 * (1 + 2 * R / (np.sqrt(3.14 * D * x))) * x)
        con = fftconvolve(Gaus, Exp)[0: len(Gaus)]

        return con

    try:
        coeffs, _ = curve_fit(f=fitfunc,
                              xdata=Xexp,
                              ydata=Yexp,
                              p0=guess,
                              bounds=bounds,
                              method=method)
        print("Success fit")

    except (ValueError, Exception):
        coeffs = np.ones(6)
        raise FittingError('Bimolecular reaction time dependence')
    except OptimizeWarning:
        raise
    finally:
        Coeffs = dict(zip(('A','t0','D', 'R', 'tau', 'part'), coeffs))
        print(Coeffs)
        return Coeffs, fitfunc(Xexp, *coeffs)
    
    
def fitrising(Xexp,
                    Yexp,
                    guess,
                    bounds,
                    extraN=2,
                    method='dogbox'):
    res = elongarray(Xexp, N=extraN)
    xnew = res[0]
    oldpos = res[1]
    dt = xnew[2] - xnew[1]
    
    def gaussian(x, x0, sigma):
        res = 1 / (2 * 3.14 * sigma) * np.exp(-(x - x0)**2 / (2 * sigma**2))
        return res
    
    @howmany
    def fit(x, *args):
        A, t0, tau, part, sigma, y0 = args
        Ce1 = 0
        Ce2 = 0
        Yt = [Ce1+Ce2]
        ts = t0 - 1.177 * sigma

        for t in xnew:
            Gaus = A * gaussian(t, t0, sigma)
            Ce1 = (part * Gaus -  Ce1 / tau) * dt + Ce1
            Ce2 = ((1-part) * Gaus + Ce1 / tau) * dt + Ce2
            Yt.append(Ce2+y0)

        Yt = np.array(Yt)[oldpos]
        #plt.plot(x, Yt)
        #plt.plot(x, Yexp)
        #plt.show()

        return Yt
        

    try:
        coeffs, _ = curve_fit(f=fit,
                              xdata=Xexp,
                              ydata=Yexp,
                              p0=guess,
                              bounds=bounds,
                              method=method)
        print("Success fit")

    except (ValueError, Exception):
        coeffs = np.ones(6)
        raise FittingError('Bimolecular reaction time dependence')
    except OptimizeWarning:
        raise
    finally:
        Coeffs = dict(zip(('A','t0', 'tau', 'part', 'sigma', 'y0'), coeffs))
        print(Coeffs)
        return Coeffs, fit(Xexp, *coeffs)
    
def fitdecay(Xexp,
                    Yexp,
                    guess,
                    bounds,
                    extraN=2,
                    method='dogbox'):
    res = elongarray(Xexp, N=extraN)
    xnew = res[0]
    oldpos = res[1]
    dt = xnew[2] - xnew[1]
    
    def gaussian(x, x0, sigma):
        res = 1 / (2 * 3.14 * sigma) * np.exp(-(x - x0)**2 / (2 * sigma**2))
        return res
    
    @howmany
    def fitfunc(x, *args):
        A, t0, tau, sigma, y0 = args
        Ce1 = 0
        Yt = [Ce1+y0]
        ts = t0 - 1.177 * sigma

        for t in xnew:
            Gaus = A * gaussian(t, t0, sigma)
            Ce1 = (Gaus -  Ce1 / tau) * dt + Ce1
            Yt.append(Ce1+y0)

        Yt = np.array(Yt)[oldpos]
        #plt.plot(x, Yt)
        #plt.plot(x, Yexp)
        #plt.show()

        return Yt
        

    try:
        coeffs, _ = curve_fit(f=fitfunc,
                              xdata=Xexp,
                              ydata=Yexp,
                              p0=guess,
                              bounds=bounds,
                              method=method)
        print("Success fit")

    except (ValueError, Exception):
        coeffs = np.ones(5)
        raise FittingError('monoexp did not work')
    except OptimizeWarning:
        raise
    finally:
        Coeffs = dict(zip(('A','t0', 'tau', 'sigma','y0'), coeffs))
        print(Coeffs)
        return Coeffs, fitfunc(Xexp, *coeffs)
    
    
def fitbidecay(Xexp,
                    Yexp,
                    guess,
                    bounds,
                    extraN=2,
                    method='dogbox'):
    res = elongarray(Xexp, N=extraN)
    xnew = res[0]
    oldpos = res[1]
    dt = xnew[2] - xnew[1]
    
    def gaussian(x, x0, sigma):
        res = 1 / (2 * 3.14 * sigma) * np.exp(-(x - x0)**2 / (2 * sigma**2))
        return res
    
    @howmany
    def fitfunc(x, *args):
        A, t0, tau1, tau2, part, sigma, y0 = args
        Ce1 = 0 
        Ce2 = 0
        Yt = [Ce1+Ce2+y0]
        ts = t0 - 1.177 * sigma

        for t in xnew:
            Gaus = A * gaussian(t, t0, sigma)
            Ce1 = (Gaus * part  -  Ce1 / tau1) * dt + Ce1
            Ce2 = (Gaus * (1-part)  -  Ce2 / tau2) * dt + Ce2
            Yt.append(Ce1+Ce2+y0)

        Yt = np.array(Yt)[oldpos]
        #plt.plot(x, Yt)
        #plt.plot(x, Yexp)
        #plt.show()

        return Yt
        

    try:
        coeffs, _ = curve_fit(f=fitfunc,
                              xdata=Xexp,
                              ydata=Yexp,
                              p0=guess,
                              bounds=bounds,
                              method=method)
        print("Success fit")

    except (ValueError, Exception):
        coeffs = np.ones(7)
        raise FittingError('bitexp did not work')
    except OptimizeWarning:
        raise
    finally:
        Coeffs = dict(zip(('A','t0', 'tau1',' tau2', 'part', 'sigma','y0'), coeffs))
        return Coeffs, fitfunc(Xexp, *coeffs)
    
    
def fitABC(Xexp,Yexp, guess, bounds,
                    extraN=2,
                    method='dogbox'):
    res = elongarray(Xexp, N=extraN)
    xnew = res[0]
    oldpos = res[1]
    dt = xnew[2] - xnew[1]
    
    def gaussian(x, x0, sigma):
        res = 1 / (2 * 3.14 * sigma) * np.exp(-(x - x0)**2 / (2 * sigma**2))
        return res
    
    @howmany
    def fitfunc(x, *args):
        A, t0, tau1, tau2, sigma, y0 = args
        Ca = 0
        Cb = 0
        Yt = [Cb+y0]
        ts = t0 - 1.177 * sigma

        for t in xnew:
            Gaus = A * gaussian(t, t0, sigma)
            Ca = (Gaus -  Ca / tau1) * dt + Ca
            Cb = (Ca / tau1 - Cb / tau2) * dt + Cb
            Yt.append(Cb + y0)

        Yt = np.array(Yt)[oldpos]
        #plt.plot(x, Yt)
        #plt.plot(x, Yexp)
        #plt.show()

        return Yt
        

    try:
        coeffs, _ = curve_fit(f=fitfunc,
                              xdata=Xexp,
                              ydata=Yexp,
                              p0=guess,
                              bounds=bounds,
                              method=method)
        print("Success fit")

    except (ValueError, Exception) as e:
        print(f'fitABC did not work {e}')
        coeffs = np.ones(6) 
        raise FittingError('fitABC did not work')
        
    except OptimizeWarning:
        raise
    finally:
        Coeffs = dict(zip(('A','t0', 'tau1',' tau2', 'sigma','y0'), coeffs))
        return Coeffs, fitfunc(Xexp, *coeffs)   

def fitAABC(Xexp,Yexp, guess, bounds,
                    extraN=2,
                    method='dogbox'):
    res = elongarray(Xexp, N=extraN)
    xnew = res[0]
    oldpos = res[1]
    dt = xnew[2] - xnew[1]
    
    def gaussian(x, x0, sigma):
        res = 1 / (2 * 3.14 * sigma) * np.exp(-(x - x0)**2 / (2 * sigma**2))
        return res
    
    @howmany
    def fitfunc(x, *args):
        A, t0, tau1, tau2, sigma, y0 = args
        Ca = 0
        Cb = 0
        Yt = [Cb+y0]
        ts = t0 - 1.177 * sigma

        for t in xnew:
            Gaus = A * gaussian(t, t0, sigma)
            Ca = (Gaus -  2 * Ca * Ca / tau1) * dt + Ca
            Cb = (2 * Ca * Ca / tau1 - Cb  / tau2) * dt + Cb
            Yt.append(Cb + y0)

        Yt = np.array(Yt)[oldpos]
        #plt.plot(x, Yt)
        #plt.plot(x, Yexp)
        #plt.show()

        return Yt
        

    try:
        coeffs, _ = curve_fit(f=fitfunc,
                              xdata=Xexp,
                              ydata=Yexp,
                              p0=guess,
                              bounds=bounds,
                              method=method)
        print("Success fit")

    except (ValueError, Exception) as e:
        print(f'fitABC did not work {e}')
        coeffs = np.ones(6) 
        raise FittingError('fitABC did not work')
        
    except OptimizeWarning:
        raise
    finally:
        Coeffs = dict(zip(('A','t0', 'tau1',' tau2', 'sigma','y0'), coeffs))
        return Coeffs, fitfunc(Xexp, *coeffs)   