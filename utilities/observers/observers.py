from abc import ABCMeta, abstractmethod


class MainObserver(metaclass=ABCMeta):
    """
    Abstract superclass for observers
    """
    @abstractmethod
    def model_is_changed(self):
        pass


class DLObserver(metaclass=ABCMeta):
    """
    Abstract superclass for observers
    """
    @abstractmethod
    def model_is_changed(self):
        pass


class SettingsObserver(metaclass=ABCMeta):
    """
    Abstract superclass for observers
    """
    @abstractmethod
    def model_is_changed(self):
        pass


class MObserver(metaclass=ABCMeta):
    @abstractmethod
    def model_is_changed(self):
        pass
