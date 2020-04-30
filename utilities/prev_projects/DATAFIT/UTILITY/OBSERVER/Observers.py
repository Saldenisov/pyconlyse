from abc import ABCMeta, abstractmethod


class MObserver(metaclass=ABCMeta):
    """
    Absract superclass for all Mobservers
    """
    @abstractmethod
    def modelIsChanged(self):
        """
        Observer method which will be called
        when model is changed
        """
        pass


class GraphObserver(metaclass=ABCMeta):
    """
    Absract superclass for all Graphobservers
    """
    @abstractmethod
    def cursorsChanged(self):
        """
        Observer method which will be called
        when model is changed
        """
        pass

class GraphsObserver(metaclass=ABCMeta):
    """
    Absract superclass for all Graphsobservers
    """
    @abstractmethod
    def modelIsChanged(self):
        """
        Observer method which will be called
        when model is changed
        """
        pass


class FitObserver(metaclass=ABCMeta):
    """
    Absract superclass for all Fitobservers
    """
    @abstractmethod
    def modelIsChanged(self):
        """
        Observer method which will be called
        when model is changed
        """
        pass
