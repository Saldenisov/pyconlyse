from OPENER import Opener
from ERRORS import GraphModelError, OpenerError
from ANALYSIS import correct_cursors_pos
from UTILITY import Orddict as Odict
from itertools import islice

import numpy as np
import logging
module_logger = logging.getLogger(__name__)


class GraphModel:
    """
    Class GraphModel is model of datastructures used for working with Graphs.
    Model contains method of registration, deleting, notification of observers
    and methods managing these datastructures.
    """

    def __init__(self,
                 filepath='C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\test2.img',
                 parent_model=None):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.__fits = []
        self.observers = []
        self.__filepath = filepath
        self.__data = [[]]
        self.__timedelays = None
        self.__wavelengths = None
        self.__cursors = {}
        self.__parentmodel = parent_model
        self.__kinetics = Odict()
        self._kinetics_id = 0
        self.__spectra = Odict()
        self._spectrum_id = 0
        self._set_all_data()

    def _set_all_data(self):
        try:
            """
            """
            file_opened = Opener(self.filepath)
            file_opened.read_data()
        except OpenerError as e:
            """
            """
            self.logger.error(e)
            raise GraphModelError
        else:
            self.data = file_opened.data
            self.timedelays = file_opened.timedelays
            self.wavelengths = file_opened.wavelengths
            wave_len = len(self.wavelengths)
            time_len = len(self.timedelays)
            self.cursors = {'x1': int(0.05 * wave_len - 1),
                            'x2': int(0.95 * wave_len - 1),
                            'y1': int(0.05 * time_len - 1),
                            'y2': int(0.95 * time_len - 1)}
            # adds first dynamic kinetics to kinetics Odict
            name_x = self.form_name(self.cursors, 'x')
            name_y = self.form_name(self.cursors, 'y')
            self.kinetics['dynamic'] = (name_x, self.calc_kinetics(), self.cursors)
            # adds first dynamic spectrum to spectra Odict
            self.spectra['dynamic'] = (name_y, self.calc_spectrum(), self.cursors)

    def form_name(self, cursors=None, name=None):
        """
        form_name exclusive name for kinetics or spectrum from cursors
        positions
        """
        if not cursors:
            cursors = self.cursors

        td = self.timedelays
        wl = self.wavelengths
        x1 = wl[cursors['x1']]
        x2 = wl[cursors['x2']-1]
        y1 = td[cursors['y1']]
        y2 = td[cursors['y2']-1]

        if not name:
            return "x1:" + str(x1) +" x2:" + str(x2) + " y1:" + str(y1) +" y2:" + str(y2)
        elif name == 'x':
            return "x1:" + str(x1) +" x2:" + str(x2)
        elif name == 'y':
            return "y1:" + str(y1) +" y2:" + str(y2)

    def get_from_to(self):
        """
        return tuple (from, to) in pixels
        """
        pfrom = self.cursors['y1']
        pto = self.cursors['y2']

        return pfrom, pto

    def calc_kinetics(self, cursors=None):
        """
        return kinetics according to cursors position
        """
        if not cursors:
            cursors = self.cursors

        x1p = cursors['x1']
        x2p = cursors['x2']
        y1p = cursors['y1']
        y2p = cursors['y2']

        if(x1p == 0 and x2p == 0 and y1p == 0 and y2p == 0):
            x1p = 0
            x2p = len(self.data[1]) - 1
            y1p = 0
            y2p = len(self.data[:, 1]) - 1

        kinetics = np.zeros(len(self.timedelays))

        for i in range(x1p, x2p):
            kinetics += self.data[:, i]

        kinetics = kinetics / (x2p - x1p)

        return kinetics

    def calc_spectrum(self, cursors=None):
        """
        return spectrum according to cursors position
        """
        if not cursors:
            cursors = self.cursors

        x1p = cursors['x1']
        x2p = cursors['x2']
        y1p = cursors['y1']
        y2p = cursors['y2']

        if(x1p == 0 and x2p == 0 and y1p == 0 and y2p == 0):
            x1p = 0
            x2p = len(self.data[1])
            y1p = 0
            y2p = len(self.data[:, 1])

        spectrum = np.zeros(len(self.wavelengths))

        for i in range(y1p, y2p):
            spectrum += self.data[i]

        spectrum = spectrum / (y2p - y1p)

        return spectrum

    def add_kinetics(self):
        if not self._kinetics_id in self.kinetics:
            name = self.form_name(name='y')
            self.kinetics = (name, self.calc_kinetics(), self.cursors)
            self.notifyObservers(who='kinetics')

    def add_spectrum(self):
        if not self._spectrum_id in self.spectra:
            name = self.form_name(name='x')
            self.spectra = (name, self.calc_spectrum(), self.cursors)
            self.notifyObservers(who='spectra')

    def delete_kinetics(self, key_del=None):
        """
        delete last entry in kinetics Odict
        """
        if key_del == None:
            if len(self.kinetics) > 1:
                key_del = self.kinetics.last
                del self.kinetics[key_del]

        else:
            if len(self.kinetics) > 1:
                del self.kinetics[key_del]

        self.notifyObservers()

    def delete_spectrum(self, key_del=None):
        """
        delete last entry in kinetics Odict
        """
        if key_del == None:
            if len(self.spectra) > 1:
                key_del = self.spectra.last
                del self.spectra[key_del]

        else:
            if len(self.spectra) > 1:
                del self.spectra[key_del]

        self.notifyObservers()

    def update_cursors(self, values, real=False):
        data = self.data
        wavelength = self.wavelengths
        timedelays = self.timedelays
        xdata_clicked, xdata_realeased, ydata_clicked, ydata_realeased = values

        if real:
            x1, x2 = np.sort([xdata_clicked, xdata_realeased])
            x1p, x2p = [(np.searchsorted(wavelength, x1, side='right')),
                        (np.searchsorted(wavelength, x2, side='right'))]
            y1, y2 = np.sort([ydata_clicked, ydata_realeased])
            y1p, y2p = [(np.searchsorted(timedelays, y1, side='right')),
                        (np.searchsorted(timedelays, y2, side='right'))]
        else:
            x1p, x2p = np.sort([xdata_clicked, xdata_realeased])
            y1p, y2p = np.sort([ydata_clicked, ydata_realeased])

        data_rows, data_columns = self.data.shape
        cursors = correct_cursors_pos({'x1': x1p,
                                       'y1': y1p,
                                       'x2': x2p,
                                       'y2': y2p},
                                        data_rows,
                                        data_columns)
        # if y cursors are changed
        if not [cursors['y1'], cursors['y2']] == [self.cursors['y1'], self.cursors['y2']]:
            # take first spectrum and update it
            name = self.form_name(cursors, name='y')
            self.spectra['dynamic'] = (name, self.calc_spectrum(cursors), cursors)
        # if x cursors are changed
        if not [cursors['x1'], cursors['x2']] == [self.cursors['x1'], self.cursors['x2']]:
            # take first kinetics and update it
            name = self.form_name(cursors, name='x')
            self.kinetics['dynamic'] = (name, self.calc_kinetics(cursors), cursors)

        self.cursors = cursors
        self.notifyObservers()

    def copy_data(self, X, Y, key=None):
        """
        Y equals either to spectrum or kinetics
        """
        if key:
            curve = Y[key]
            var = np.vstack([X, curve])
        else:
            var = np.vstack([X, Y['dynamic'][1]])
            values = islice(Y.values(), 1, None)
            for val in values:
                var= np.row_stack([var, val[1]])

        return var

    @property
    def parentmodel(self):
        return self.__parentmodel

    @property
    def filepath(self):
        return self.__filepath

    @property
    def data(self):
        return self.__data

    @data.setter
    def data(self, value):
        self.__data = value

    @property
    def wavelengths(self):
        return self.__wavelengths

    @wavelengths.setter
    def wavelengths(self, value):
        self.__wavelengths = value

    @property
    def timedelays(self):
        return self.__timedelays

    @timedelays.setter
    def timedelays(self, value):
        self.__timedelays = value

    @property
    def cursors(self):
        """
        Return cursors positions in pixels
        {'x1': val1, 'x2': val2, 'y1': val3, 'y2': val4}
        """
        return self.__cursors

    @cursors.setter
    def cursors(self, value):
        """
        Set cursors positions in pixels
        {'x1': val1, 'x2': val2, 'y1': val3, 'y2': val4}
        """
        self.__cursors = value

    @property
    def kinetics(self):
        return self.__kinetics

    @kinetics.setter
    def kinetics(self, value):
        if isinstance(value, tuple):
            self.__kinetics[self._kinetics_id] = value
            self._kinetics_id += 1
        else:
            self.logger.info('Could not add to kinetics, value != tuple')

    @property
    def spectra(self):
        return self.__spectra

    @spectra.setter
    def spectra(self, value):
        if isinstance(value, tuple):
            self.__spectra[self._spectrum_id] = value
            self._spectrum_id += 1
        else:
            self.logger.info('Could not add to spectra, value != tuple')

    def addFit(self, fit_controller):
        """
        Add __Fit controller
        """
        self.__fits.append(fit_controller)

    @property
    def fits(self):
        return self.__fits

    def removeFits(self, indexes):
        for index in sorted(indexes, reverse=True):
            try:
                self.__fits[index].view.close()
                self.__fits.pop(index)
            except KeyError as e:
                self.logger.error(e)

    def addObserver(self, inObserver):
        self.observers.append(inObserver)

    def removeObserver(self, inObserver):
        self.observers.remove(inObserver)

    def notifyObservers(self, who=None):
        for x in self.observers:
            x.cursorsChanged(who)
