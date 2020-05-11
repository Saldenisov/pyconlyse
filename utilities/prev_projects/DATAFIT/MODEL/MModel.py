from UTILITY import Configuration
from MODEL import GraphModel
from CONTROLLER import GraphController
from ERRORS import GraphModelError, ValidationFailed

import os
import logging
module_logger = logging.getLogger(__name__)


class MModel:
    """
    Class MModel (Main Model) is upper level datastructures model_str

    It operates with datastructures files
    """

    def __init__(self, root='D:\\DATA',
                 config_path='C:\\Users\\saldenisov\\Dropbox\\Python\\DATAFIT\\Settings\\',
                 developping=True):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.__files = {}
        self.__graphs = {}
        self.__all_graphs = []
        self.__root = ''
        self.__config = None
        self.observers = []

        self.root = root
        self.dev = developping
        """
        Configuration
        """
        try:
            configuration = Configuration(path=config_path)
            self.__config = configuration.config
        except (FileNotFoundError, ValidationFailed) as e:
            self.logger.error(e)
            raise

    @property
    def config(self):
        return self.__config

    @property
    def root(self):
        return self.__root

    @root.setter
    def root(self, val):
        if os.path.isdir(val):
            self.__root = val
        else:
            self.__root = 'C:\\'

    @property
    def files(self):
        return self.__files

    @files.setter
    def files(self, val):
        self.__files = val

    def add_file(self, filename):
        if os.path.isfile(filename):
            self.files[filename] = filename
            self.logger.info('File is added: ' + filename)
            self.notifyObservers(filename)
        else:
            self.logger.info('File does not exist, nothing is being added')

    def remove_file(self, filename):
        try:
            del self.files[filename]
            if self.graphs:
                self.remove_graph(filename)
                self.logger.info('File is deleted: ' + filename)
        except KeyError as e:
            self.logger.error(e)

    @property
    def graphs(self):
        return self.__graphs

    @graphs.setter
    def graphs(self, val):
        self.__graphs = val

    @property
    def all_graphs(self):
        return self.__all_graphs

    @all_graphs.setter
    def all_graphs(self, val):
        self.__all_graphs = val

    def create_graph(self, filepath):
        """
        If there is a graph with a filepath -
        show it in another case create a new graph.
        """

        if filepath in self.graphs:
            self.graphs[filepath].view.show()

        else:
            param = self.config['Views']['GraphCanvas']['Default']
            try:
                model = GraphModel(filepath=filepath,
                                   parent_model=self)
            except GraphModelError as e:
                self.logger.error(e)
                raise
            else:
                graphcontroller = GraphController(model, param)
                self.add_graph(graphcontroller)
                self.logger.info('File is opened: '+ filepath)


    def add_graph(self, graph):
        self.graphs[graph.model.filepath] = graph

    def remove_graph(self, filename):
        try:
            self.graphs[filename].view.close()
            del self.graphs[filename]
        except KeyError as key_e:
            self.logger.error('in remove_graph KeyError: ' + str(key_e))

    def addObserver(self, inObserver):
        self.observers.append(inObserver)

    def removeObserver(self, inObserver):
        self.observers.remove(inObserver)

    def notifyObservers(self, file=None):
        for x in self.observers:
            x.modelIsChanged(file)
