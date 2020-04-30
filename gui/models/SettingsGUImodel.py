'''
Created on 12 May 2017

@author: Sergey Denisov
'''

import logging
module_logger = logging.getLogger(__name__)


class Settingsmodel():
    """

    """

    def __init__(self, mainmodel):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.observers = []



    def add_observer(self, inObserver):
        self.observers.append(inObserver)

    def remove_observer(self, inObserver):
        self.observers.remove(inObserver)

    def change_config(self,command):
        pass

    def notify_observers(self):
        pass
