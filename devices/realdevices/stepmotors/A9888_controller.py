"""
CLI for controlling 5V NEWPORT steppers with A9888
in reality 12V is supplied, thus is really important to
disable controller and switch off for doulbe protection
so current does not run during waiting time

4 axis are controlled at this moment with this peace of code
INSTEAD of RPi.GPIO -> gpiozero will be used, since it could be installed
under windows with no problems
"""


import gpiozero
from devices.devices import Service
import logging
import ctypes
from time import sleep
from deprecated import deprecated

module_logger = logging.getLogger(__name__)


class Newport_4axis(Service):

    # TODO: verfiy correct numbering, since in gpiozero the different strategy is used
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _setup_pins(self):
        pass

    def _enable_controller(self):
        GPIO.output(enable_pin, 0)
        sleep(0.05)

    def _disable_controller(self):
        GPIO.output(enable_pin, 1)
        sleep(0.05)

    def _direction(self, orientation='top'):
        if orientation == 'top':
            GPIO.output(DIR_pin, 1)
        elif orientation == 'bottom':
            GPIO.output(DIR_pin, 0)
        sleep(0.05)

    def _deactivate_all_relay(self):
        pass
        sleep(0.1)

    def _activate_relay(self, n):
        """
        activate relay #n
        :return:
        """
        pass

    def move_to(self, n_steps, axis):
        pass

    def get_pos(self, axis):
        pass


    def activate(self):
        super().activate()

    def deactivate(self):
        super().deactivate()

    def messenger_settings(self):
        super().messenger_settings()

    def description(self):
        pass

    def available_public_functions(self):
        super().available_public_functions()