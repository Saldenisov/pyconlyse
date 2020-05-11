'''
Created on 7 oct. 2015

@author: saldenisov
'''
import logging
import os.path
from configparser import ConfigParser

from configobj import ConfigObj, flatten_errors
from validate import Validator

from utilities.errors.myexceptions import ValidationFailed, ConfigCannotBeSet

module_logger = logging.getLogger(__name__)


class configurationSD():
    """
    Parse configuration file
    """
    # TODO: the configurationSD is shit...must be redone completly
    def __init__(self, parent):
        self.logger = logging.getLogger(parent.__class__.__name__ + '.' + __name__ )
        self.logger.info('Configuration is created')
        self._config = {}

    def add_config(self, name: str, path_config=None, config_text=None) -> None:
        self._config[name] = ConfigParser()
        try:
            if path_config:
                self._config[name].read(str(path_config))
            elif config_text:
                self._config[name].read_string(config_text)
            else:
                raise ConfigCannotBeSet
            self.logger.info('Configuration is added with success')
        except Exception as e:
            self.logger.error(e)
            raise ConfigCannotBeSet

    def get(self, name: str) -> ConfigParser:
        try:
            return self._config[name]
        except KeyError as e:
            self.logger.error(e)

    def config_to_dict(self, name: str) -> dict:
        config = self.get(name)
        sections_dict = {}
        sections = config.sections()

        for section in sections:
            options = config.options(section)
            temp_dict = {}
            for option in options:
                temp_dict[option] = config.get(section, option)
            sections_dict[section] = temp_dict

        return sections_dict


class сonfiguration_validation:
    """
    Parse configuration file and check with respect
    to config specification
    """
    def __init__(self, parent, config_path):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        name, ext = os.path.splitext(config_path)
        self._path_config_spec = name + '_spec' + ext
        self._path_config = config_path
        self._config = {}

        try:
            if not os.path.isfile(self._path_config_spec):
                raise FileNotFoundError('File of configuration spec not found')
            if not os.path.isfile(self._path_config):
                raise FileNotFoundError('File of configuration not found')

            config_spec = ConfigObj(self._path_config_spec, interpolation=False,
                                   list_values=True, _inspec=True)

            self._config = ConfigObj(self._path_config,
                                     configspec=config_spec)

            val = Validator()

            results = self._config.validate(val)

            if results != True:
                for (section_list, key, _) in flatten_errors(self._config, results):
                    if key is not None:
                        print ('The "%s" key in the section "%s" failed validation' % (key, ', '.join(section_list)))
                    else:
                        print('The following section was missing:%s ' % ', '.join(section_list))
                        raise ValidationFailed

            #===================================================================
            # map = {}
            # for (name, value) in zip(self._config['map1'], self._config['map2']):
            #     map[name] = value
            # self._config['MAP'] = map
            #===================================================================

        except (FileNotFoundError, ValidationFailed) as e:
            self.logger.error(e)
            raise

    @property
    def value(self):
        return self._config
