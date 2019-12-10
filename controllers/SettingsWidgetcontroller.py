'''
Created on 12 May 2017

@author: Sergey Denisov
'''


from views.SettingsGUIview import SettingsView
from re import split

import logging
module_logger = logging.getLogger(__name__)


MAP = {'G': 'General', 'L': 'Long', 'S': 'Short', 'Ranges': 'Ranges', 
       'Acc': 'Accelerations', 'Vel': 'Velocities', 'MC': 'Motor_Currents', 
       'Dim': 'Dimensions', 'Pitches': 'Pitches',
       'min': 'min', 'max': 'max', 'zero': 'zero', 'X': 'X', 'Y': 'Y', 'Z': 'Z',
       'A': 'A', 'SAxisvel': 'Single_Axis_vel','XD': 'XD', 'YD': 'YD', 'ZD': 'ZD',
       'AD': 'AD', 'cells': 'Cells_pos'}

class SettingsContoller():
    """
    """

    def __init__(self, in_model):
        """
        """
        self.logger = logging.getLogger("MAIN." + __name__)
        self.model = in_model
        self.view = SettingsView(self, in_model=self.model)
        #self.view.show()

           
    def buttonsavesettings_clicked(self, widgets):
        """
        Update configurations (settings) in setting model and main model
        """
        MAP = self.model.mmodel.get['MAP']
        #long delay line settings update
        try:
            for widget in widgets:
                name = widget.objectName()
                name_s = split('_', name)[1:]
                f = MAP[name_s[2]]
                s = MAP[name_s[0]]
                t = MAP[name_s[1]]
                self.model.get['stepmotors'][f][s][t] = float(widget.text())
        except Exception as e:
            self.logger.error(str(e) + ' Did not save')
            
        
        #short delay line settings update

        #update mconfig in main model
        self.model.mmodel.get = self.model.get
        self.model.mmodel.update_config()
