'''
Created on 7 juin 2016

@author: saldenisov
'''
import os

from utilities import configurations
from utilities.errors.myexceptions import ValidationFailed


import logging
module_logger = logging.getLogger(__name__)


class Mmodel:
    """
    Class Mmodel...
    """

    def __init__(self, app_folder, developing=False):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.observers = []
        self.DL_connected = False
        try:
            self.mconfig = configurations(os.path.join(app_folder, 'settings')).get
            self.developing = self.mconfig['General']['devmode']
        except (FileNotFoundError, ValidationFailed) as e:
            self.logger.error(e)
            raise
    
    def turn_off(self):
        #Disconnect stepmotors
        pass

    def update_config(self):
        """
        updates configuration file by overwriting it
        """
        self.mconfig.write()
        self.config_changed()
    
    def add_observer(self, inObserver):
        self.observers.append(inObserver)

    def remove_observer(self, inObserver):
        self.observers.remove(inObserver)
        
    def config_changed(self):
        self.notify_observers()

    def notify_observers(self):
        for x in self.observers:
            x.model_is_changed()