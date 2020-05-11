from VIEW import GraphsView
from UTILITY import singleton
import logging
module_logger = logging.getLogger(__name__)


@singleton
class GraphsController():

    def __init__(self, in_model):
        """
        """
        self.logger = logging.getLogger("MAIN." + __name__)
        self.graphsModel = in_model

        self.graphsView = GraphsView(self, in_model=self.graphsModel)
        self.graphsView.show()
