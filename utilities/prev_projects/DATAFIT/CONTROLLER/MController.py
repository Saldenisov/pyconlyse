import logging
from os.path import isfile, exists

from PyQt5.QtWidgets import (QMessageBox,
                             QApplication,
                             QFileDialog)
from VIEW import MView

module_logger = logging.getLogger(__name__)


class MController():
    """
    Class MController is a controller
    which coordinates work between
    MView (Main View) and MModel (Main Model).
    """

    def __init__(self, in_model):
        """
        """
        self.logger = logging.getLogger("MAIN." + __name__)
        self.model = in_model

        self.view = MView(self, in_model=self.model, root=self.model.root)
        self.view.show()

        if self.model.dev:
            self.model.add_file(self.model.config['developping_file'])
            self.lfiles_doubleclicked()

    def tree_doubleclicked(self, signal):
        try:
            x = self.view.ui.tree.selectedIndexes()
            for i in range(0, len(x), 4):
                file_path = self.view.ui.tree.model().filePath(x[i])

                if isfile(file_path) and exists(file_path) and \
                   file_path not in self.model.files:
                    self.model.add_file(file_path)
        except:
            self.logger.error('MsgError in picking files from Tree')

    def delete_clicked(self):
        listItems = self.view.ui.list_Files.selectedItems()
        if not listItems:
            self.logger.info('Nothing is selected to Delete')
        for item in listItems:
            self.view.ui.list_Files.setCurrentItem(item)
            file_path_to_remove = self.view.ui.list_Files.currentItem().text()
            self.view.ui.list_Files.takeItem(
                self.view.ui.list_Files.row(item))
            self.model.remove_file(file_path_to_remove)

    def up_clicked(self):
        listItems = self.view.ui.list_Files.selectedItems()
        if not listItems:
            return
        for item in listItems:
            self.view.ui.list_Files.setCurrentItem(item)
            currentRow = self.view.ui.list_Files.currentRow()
            if currentRow != 0:
                currentItem = self.view.ui.list_Files.takeItem(currentRow)
                self.view.ui.list_Files.insertItem(
                    currentRow - 1, currentItem)
                self.view.ui.list_Files.item(currentRow - 1).setSelected(True)

    def down_clicked(self):
        listItems = self.view.ui.list_Files.selectedItems()
        number_of_items = self.view.ui.list_Files.count()
        if not listItems:
            return
        for item in listItems:
            self.view.ui.list_Files.setCurrentItem(item)
            currentRow = self.view.ui.list_Files.currentRow()
            if currentRow != number_of_items - 1:
                currentItem = self.view.ui.list_Files.takeItem(currentRow)
                self.view.ui.list_Files.insertItem(
                    currentRow + 1, currentItem)
                self.view.ui.list_Files.item(currentRow + 1).setSelected(True)

    def lfiles_doubleclicked(self):
        if self.model.dev:
            list_files = self.view.ui.list_Files
            first_item = self.view.ui.list_Files.item(0)
            filepath = first_item.text()
            self.model.dev = False
        else:
            filepath = self.view.ui.list_Files.currentItem().text()

        self.model.create_graph(filepath)

    def graphs_clicked(self):
        pass
        #=======================================================================
        # try:
        #     if not self.model.All_graphs:
        #         model = GRAPHSModel()
        #         graphscontroller = GraphsController(model)
        #         self.model.All_graphs = graphscontroller
        #     else:
        #         self.model.All_graphs.graphsView.show()
        # except Exception as e:
        #     self.logger.error(e, 'graphs could not be created')
        #=======================================================================

    def closeEvent(self, event):
        self.hide()
        print('Close')
        QApplication.quit()

    def help_clicked(self):
        QMessageBox.information(self.view,
                                'Help',
                                """For any help contact:\n
                                Dr. Sergey A. Denisov\n
                                saldenisov@gmail.com""")

    def author_clicked(self):
        QMessageBox.information(self.view,
                                'Author information',
                                """Author: Dr. Sergey A. Denisov\n
                                e-mail: saldenisov@gmail.com\n
                                telephone: +33625252159""")

    def settings_clicked(self):
        QMessageBox.information(self.view,
                                'Settings',
                                """Edit settings files manually in settings
                                 folder""")

    def dir_clicked(self):
        try:
            dialog = QFileDialog()
            dialog.setFileMode(QFileDialog.Directory)
            dialog.setOption(QFileDialog.ShowDirsOnly, True)
            dialog.exec()
            r = dialog.selectedFiles()[0]
            self.view.ui.tree.setRootIndex(self.view.ui.tree_model.index(r))
        except:
            self.logger.error('New Dir could be set')

    def quit(self):
        self.logger.info('Closing application')
        QApplication.quit()
