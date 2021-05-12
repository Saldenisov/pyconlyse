import logging

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (QListWidgetItem,
                             QApplication,
                             QFileDialog)
from numpy import searchsorted, transpose, vstack, column_stack, append, savetxt
from CONTROLLER.FitController import FitController
from HELPFUL import ndarray_tostring
from MODEL import FitModel
from VIEW import GraphView

module_logger = logging.getLogger(__name__)


class GraphController():
    """
    Class GraphController is a controller
    which coordinates work between view and model.
    """

    def __init__(self, in_model, param):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.model = in_model
        self.view = GraphView(self, in_parameters=param)
        self.view.show()
        self.model.notifyObservers()
        self.clipboard = QApplication.clipboard()
        self.axhline_SEL = False
        self.axhline_SEL_index = 1
        self.ctr_pressed = False
        self.line_picked = {'kinetics': None, 'spectrum': None}

        if self.model.parentmodel.dev:
            self.fit_clicked()

    def onselectrect(self, eclick, erelease):
        if not self.axhline_SEL:
            self.update_selected_area(eclick.xdata,
                                      erelease.xdata,
                                      eclick.ydata,
                                      erelease.ydata,
                                      real=True)

    def update_selected_area(self, xdata_clicked, xdata_realeased,
                             ydata_clicked, ydata_realeased, real=False):

        self.model.update_cursors((xdata_clicked, xdata_realeased,
                                   ydata_clicked, ydata_realeased),
                                  real=real)

    def on_pick_kinetics(self, event):
        label = event.artist._label
        # key: find pos of ':' in label of line
        pos = label.find('key:')
        # obtain key from _label of line
        if pos != -1:
            key = int(label[pos+4:])
            if self.line_picked['kinetics'] == None:
                self.line_picked['kinetics'] = key
                self.logger.info('kinetics line selected:' + label)
                self.view.statusBar().showMessage('kinetics line selected:' + label, 2000)
            else:
                self.line_picked['kinetics'] = None
                self.logger.info('kinetics line unselected:' + label)
                self.view.statusBar().showMessage('kinetics line unselected:' + label, 2000)

    def on_pick_spectrum(self, event):
        label = event.artist._label
        # key: find pos of ':' in label of line
        pos = label.find('key:')
        # obtain key from _label of line
        if pos != -1:
            key = int(label[pos+4:])
            if self.line_picked['spectrum'] == None:
                self.line_picked['spectrum'] = key
                self.logger.info('spectrum line selected:' + label)
                self.view.statusBar().showMessage('spectrum line selected:' + label, 2000)
            else:
                self.line_picked['spectrum'] = None
                self.logger.info('spectrum line unselected:' + label)
                self.view.statusBar().showMessage('spectrum line unselected:' + label, 2000)

    def key_pressed_kinetics(self, event):
        try:
            if event.key == 'ctrl+c':
                key = self.line_picked['kinetics']
                var = transpose(self.model.copy_data(X=self.model.timedelays,
                                                     Y=self.model.kinetics,
                                                     key=key))
                s = ndarray_tostring(var)
                self.clipboard.setText(s)

            elif event.key == 'ctrl+a':
                self.model.add_kinetics()

            elif event.key == 'delete':
                if self.line_picked['kinetics'] == None:
                    self.model.delete_kinetics()
                else:
                    self.model.delete_kinetics(key_del=self.line_picked['kinetics']) 
        except Exception as e:
            self.logger.error(e)

    def key_pressed_spectra(self, event):
        if event.key == 'ctrl+c':
            key = self.line_picked['spectrum']
            var = transpose(self.model.copy_data(X=self.model.wavelengths,
                                                 Y=self.model.spectra,
                                                 key=key))
            s = ndarray_tostring(var)
            self.clipboard.setText(s)

        elif event.key == 'ctrl+a':
            self.model.add_spectrum()

        elif event.key == 'delete':
            if self.line_picked['spectrum'] == None:
                self.model.delete_spectrum()
            else:
                self.model.delete_spectrum(key_del=self.line_picked['spectrum'])

    def key_pressed(self, event):
        #=======================================================================
        # if event.key in ['A', 'a']:
        #     try:
        #         if self.view.ui.RS.active:
        #             self.view.ui.RS.set_active(False)
        #             self.view.statusBar().showMessage("RectangleSelector deactivated.", 1000)
        #             print(' RectangleSelector deactivated.')
        #         else:
        #             self.view.ui.RS.set_active(True)
        #             self.view.statusBar().showMessage("RectangleSelector activated.", 1000)
        #             print(' RectangleSelector activated.')
        #     except Exception as e:
        #         self.logger.error(str(e))
        #=======================================================================
        try:
            if event.key == 'control':
                self.view.statusBar().showMessage("Ctrl pressed", 2000)
                self.ctr_pressed = True
                self.view.ui.cursor_data.visible = False

            elif event.key == 'ctrl+c':
                data = transpose(self.model.data)
                timedelays = self.model.timedelays
                wavelengths = append(0, self.model.wavelengths)
                data = vstack([timedelays, data])
                data = column_stack([wavelengths, data])
                s = ndarray_tostring(data)
                self.clipboard.setText(s)
        except Exception as e:
            self.logger.error(e)

    def key_released(self, event):
        if event.key == 'control':
            self.view.statusBar().showMessage("Ctrl released", 2000)
            self.ctr_pressed = False
            self.axhline_SEL = False
            self.view.ui.cursor_data.visible = True

    def mouse_pressed(self, event):
        self.axhline_SEL = False
        cursors = self.model.cursors
        min_dist = 20
        key = None
        keyX = None
        keyY = None

        if self.ctr_pressed:
            wavelength = self.model.wavelengths
            timedelays = self.model.timedelays
            xpos, ypos = [(searchsorted(wavelength,
                                        event.xdata,
                                        side='right')),
                          (searchsorted(timedelays,
                                        event.ydata,
                                        side='right'))]

            if abs(xpos - cursors['x1']) < min_dist:
                keyX = 'x1'
                self.axhline_SEL = True

            elif abs(xpos - cursors['x2']) < min_dist:
                keyX = 'x2'
                self.axhline_SEL = True

            if abs(ypos - cursors['y1']) < min_dist:
                keyY = 'y1'
                self.axhline_SEL = True

            elif abs(ypos - cursors['y2']) < min_dist:
                keyY = 'y2'
                self.axhline_SEL = True

            if self.axhline_SEL:

                if keyX and keyY:
                    if abs(xpos - cursors[keyX]) > abs(ypos - cursors[keyY]):
                        key = keyY

                    if abs(xpos - cursors[keyX]) < abs(ypos - cursors[keyY]):
                        key = keyX

                else:
                    if keyX:
                        key = keyX
                    else:
                        key = keyY

                if key == 'x1':
                    self.axhline_SEL_index = 1

                elif key == 'x2':
                    self.axhline_SEL_index = 2

                elif key == 'y1':
                    self.axhline_SEL_index = 3

                elif key == 'y2':
                    self.axhline_SEL_index = 4

    def mouse_moved(self, event):
        modifiers = QtGui.QGuiApplication.keyboardModifiers()
        axhline_SEL_index = self.axhline_SEL_index
        if modifiers == QtCore.Qt.ControlModifier:
            if self.axhline_SEL:
                cursors = self.model.cursors
                timedelays = self.model.timedelays
                wavelengths = self.model.wavelengths

                if axhline_SEL_index == 1:
                    pos = searchsorted(wavelengths, event.xdata, side='right')
                    self.update_selected_area(pos,
                                              cursors['x2'],
                                              cursors['y1'],
                                              cursors['y2'])

                elif axhline_SEL_index == 2:
                    pos = searchsorted(wavelengths, event.xdata, side='right')
                    self.update_selected_area(cursors['x1'],
                                              pos,
                                              cursors['y1'],
                                              cursors['y2'])

                elif axhline_SEL_index == 3:
                    pos = searchsorted(timedelays, event.ydata, side='right')
                    self.update_selected_area(cursors['x1'],
                                              cursors['x2'],
                                              pos,
                                              cursors['y2'])

                elif axhline_SEL_index == 4:
                    pos = searchsorted(timedelays, event.ydata, side='right')
                    self.update_selected_area(cursors['x1'],
                                              cursors['x2'],
                                              cursors['y1'],
                                              pos)

    def slider_moved_X(self, index_slider, start, end):
        self.update_selected_area(start, end,
                                  self.model.cursors['y1'],
                                  self.model.cursors['y2'])

    def slider_moved_Y(self, index_slider, start, end):
        self.update_selected_area(self.model.cursors['x1'],
                                  self.model.cursors['x2'],
                                  start, end)

    def slider_colorbar_moved(self, index_slider, start, end):
        self.view.ui.datacanvas.update_limits(minv=start, maxv=end)

    def fit_clicked(self):
        """
        Handles event generated, when the button "Fit" is pressed.
        """
        fit_model_dict = {'pulse': self.view.ui.checkbox_pulse.isChecked(),
                          'constrained': self.view.ui.checkbox_constrained.isChecked(),
                          'conv': self.view.ui.checkbox_conv.isChecked(),
                          'model': self.view.ui.combobox_Fit.currentText()}

        guess, bounds, parameters_order = self.fit_model_init(fit_model_dict)

        timedelays = self.model.timedelays
        kinetics = self.model.kinetics['dynamic'][1]
        norm_factor = self.model.parentmodel.config['Views']['FitCanvas']['Norm']

        fitparam = dict(zip(['fitmodel', 'guess', 'bounds',
                             'variables', 'Norm', 'method',
                             'filepath', 'cursors'],
                            [fit_model_dict, guess, bounds,
                             parameters_order, norm_factor,
                             self.view.ui.combobox_Method.currentText(),
                             self.model.filepath,
                             self.model.cursors]))

        try:
            fitmodel = FitModel(X=timedelays,
                                Y=kinetics,
                                fitparam=fitparam)
            fitcontroller = FitController(fitmodel)
        except (Exception, RuntimeError) as e:
            self.logger.error(e)
        finally:
            self.model.addFit(fitcontroller)
            x = len(self.model.fits)
            fitmodel = ''
            for key, value in fit_model_dict.items():
                fitmodel = fitmodel + key + ': ' + str(value) + '; '
            fitmodel = fitmodel[:-1]
            self.view.ui.list_fits.addItem(QListWidgetItem(str(x) + ': ' + fitmodel))

        try:
            fitcontroller.model.do_fit()
        except Exception as e:
            self.logger.error('Try another function')

    def delete_clicked(self):
        """
        Handles event generated,  when the button "Delete" is pressed.
        """
        listItems = self.view.ui.list_fits.selectedItems()
        del_Fits_indexes = []
        if not listItems:
            return
        i = 0
        for item in listItems:
            self.view.ui.list_fits.setCurrentItem(item)
            index = self.view.ui.list_fits.currentRow() + i
            i += 1
            del_Fits_indexes.append(index)
            self.view.ui.list_fits.takeItem(
                self.view.ui.list_fits.row(item))

        self.model.removeFits(del_Fits_indexes)

    def save_clicked(self):
        data = transpose(self.model.data)
        timedelays = self.model.timedelays
        wavelengths = append(0, self.model.wavelengths)
        data = vstack([timedelays, data])
        data = column_stack([wavelengths, data])
        fdialog = QFileDialog(self.view)
        fdialog.setDirectory('C:')
        filename = fdialog.getSaveFileName(self.view, 'Save 2D map', '',"Images (*.dat)")[0]
        try:
            savetxt(filename, data, delimiter='\t', fmt="%s")
        except Exception as e:
            print(e)

    def lfits_clicked(self):
        """
        Handles event called, when user click on the item of the list of Fits.
        """
        index = self.view.ui.list_fits.currentRow()
        a = self.model.fits[index]
        a.view.show()

    def quit_clicked(self, event):
        close_fits = self.model.fits
        if close_fits:
            for fit in close_fits:
                fit.view.hide()
        self.view.hide()

    def fit_model_init(self, fit_model):
        """
        Fills guess, bounds, variables according to fit_model
        """
        parent_model = self.model.parentmodel
        if fit_model['pulse']:
            model = 'pulse_' + fit_model['model']
        else:
            model = '_' + fit_model['model']

        try:
            guess = parent_model.config['Fitting'][model]['guess']
            bounds = parent_model.config['Fitting'][model]['bounds']
            variables = parent_model.config['Fitting'][model]['variables']
        except KeyError as e:
            self.logger.error(str(e) + 'Check config file, model names')
            raise

        return guess, bounds, variables
