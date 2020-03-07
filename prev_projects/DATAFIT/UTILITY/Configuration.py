'''
Created on 7 oct. 2015

@author: saldenisov
'''
from prev_projects.DATAFIT.ERRORS import ValidationFailed
from prev_projects.DATAFIT.HELPFUL import dict_of_dict_to_array

from configobj import ConfigObj
from validate import Validator

import os.path

import logging
module_logger = logging.getLogger(__name__)


class Configuration(object):
    """
    Creates main configuration
    """

    def __init__(self, path='C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\Settings\\'):
        self.logger = logging.getLogger("MAIN." + __name__)
        self._path_configspec = path + 'configspec.ini'
        self._path_config = path + 'config_main.ini'
        self._config = {}

        try:
            if not os.path.isfile(self._path_configspec):
                raise FileNotFoundError('File of configuration spec not found')
            if not os.path.isfile(self._path_config):
                raise FileNotFoundError('File of configuration not found')

            configspec = ConfigObj(self._path_configspec, interpolation=False, 
                                   list_values=False, _inspec=True)

            self._config = ConfigObj(self._path_config,
                                     configspec=configspec)

            val = Validator()

            result = self._config.validate(val)

            if not isinstance(result, dict):
                success = result
            else:
                success = all(dict_of_dict_to_array(result))

            if not success:
                raise ValidationFailed

        except (FileNotFoundError, ValidationFailed) as e:
            self.logger.error(e)
            raise

    @property
    def config(self):
        return self._config
