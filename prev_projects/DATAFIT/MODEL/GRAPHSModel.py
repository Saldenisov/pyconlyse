from UTILITY import singleton
import logging
module_logger = logging.getLogger(__name__)


@singleton
class GRAPHSModel:
    """
    Class GRAPHSModel is model of Data used for working with Graphs.
    Model contains method of registration, deleting, notification of observers
    and methods managing these Data.
    """

    def __init__(self):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.__graphsObservers = []
        self.__error = None

    @property
    def Observers(self):
        return self.observers

    @Observers.setter
    def Observers(self, val):
        self.observers = val

    @property
    def error(self):
        return self.__error

    @error.setter
    def error(self, value):
        self.__error = value

    def addObserver(self, inObserver):
        self.__graphsObservers.append(inObserver)

    def removeObserver(self, inObserver):
        self.__graphsObservers.remove(inObserver)

    def notifyObservers(self):
        for x in self.__graphsObservers:
            x.ModelIsChanged(type(self))
