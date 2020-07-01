import logging

import numpy as np
from ANALYSIS import Fit
from ERRORS import NoSuchFittingFunction, FittingError

module_logger = logging.getLogger(__name__)


class FitModel:

    def __init__(self,
                 X,
                 Y,
                 fitparam):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.__parameters = fitparam
        self.__X = np.array(X)
        self.__Y = np.array(Y)
        from_p = self.parameters['cursors']['y1']
        to_p = self.parameters['cursors']['y2'] + 1
        self.__fit = np.zeros(len(Y))[from_p:to_p]
        self.__coeffs = {}
        self.observers = []
        self.factor_norm = np.max(np.abs(self.Y))

    def do_fit(self):
        model_dict = self.parameters['fitmodel']
        if not self.parameters['Norm']:
            factor_norm = 1
        else:
            factor_norm = np.max(np.abs(self.Y))

        fit_ = Fit(self.X,
                   self.Y / factor_norm,
                   self.parameters)
        try:
            if model_dict['model'] == 'distFRET_Gaussian':
                function = '_distFRET_Gaussian'
            else:
                function = None

            self.coeffs, self.fit = fit_.dofit(pulse=model_dict['pulse'],
                                               constrained=model_dict['constrained'],
                                               iterat=not model_dict['conv'],
                                               model=model_dict['model'], func=function)

            self.notifyObservers()

        except (ValueError, NoSuchFittingFunction, FittingError) as e:
            self.logger.error(e)
            raise

    def form_model_name(self):
        """
        form model_name according to self.parameters['fitmodel']
        {'conv': True, 'constrained': True, 'pulse': True, 'model_d': '1exp'}
        """
        model_d = self.parameters['fitmodel']
        model_name = ''
        if model_d['pulse']:
            model_name += 'pulse'
        model_name += '_' + model_d['model']
        if model_d['constrained']:
            model_name += '_constrained'
        if model_d['conv']:
            model_name += '_conv'
        else:
            model_name += '_iter'

        return model_name

    def copy_data(self, norm=False):
        """
        copy fit
        """
        if not self.parameters['Norm']:
            norm = 1
        else:
            norm = self.factor_norm

        from_p = self.parameters['cursors']['y1']
        to_p = self.parameters['cursors']['y2'] + 1

        var = np.vstack([self.X, self.Y/norm])

        if len(self.X) != len(self.X[from_p:to_p]):
            a = np.empty(len(self.X) - (to_p - from_p))
            b = np.empty(len(self.X) - (to_p - from_p))
            a.fill(None)
            b.fill(None)
            x = np.append(self.X[from_p:to_p], a)
            fit = np.append(self.fit, b)

        else:
            x = self.X[from_p:to_p]
            fit = self.fit

        var = np.vstack([var, x, fit])

        return var

    @property
    def parameters(self):
        return self.__parameters

    @parameters.setter
    def parameters(self, value):
        self.__parameters = value

    @property
    def X(self):
        return self.__X

    @X.setter
    def X(self, value):
        self.__X = value

    @property
    def Y(self):
        return self.__Y

    @Y.setter
    def Y(self, value):
        self.__Y = value

    @property
    def fit(self):
        return self.__fit

    @fit.setter
    def fit(self, value):
        self.__fit = value

    @property
    def coeffs(self):
        return self.__coeffs

    @coeffs.setter
    def coeffs(self, value):
        self.__coeffs = value

    def addObserver(self, inObserver):
        self.observers.append(inObserver)

    def removeObserver(self, inObserver):
        self.observers.remove(inObserver)

    def notifyObservers(self):
        for x in self.observers:
            x.modelIsChanged()
