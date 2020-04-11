from PyQt5.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem


class ViewTree(QTreeWidget):

    def __init__(self, value):
        super().__init__()

        def fill_item(item, value):

            def new_item(parent, key, val=None):
                child = QTreeWidgetItem([key])
                fill_item(child, val)
                parent.addChild(child)
                child.setExpanded(False)

            if not value:
                return
            elif isinstance(value, dict):
                for key, val in sorted(value.items()):
                    new_item(item, str(key), val)
            elif isinstance(value, (list, tuple)):
                for val in value:
                    text = (str(val) if not isinstance(val, (dict, list, tuple))
                            else '[%s]' % type(val).__name__)
                    new_item(item, text, val)
            else:
                new_item(item, str(value))

        fill_item(self.invisibleRootItem(), value)

if __name__ == '__main__':
    app = QApplication([])
    window = ViewTree({'key1': 'value1', '2': {'10':10} ,'key3': [1,2,3, { 1: 3, 7 : 9}]})
    window.show()
    app.exec_()