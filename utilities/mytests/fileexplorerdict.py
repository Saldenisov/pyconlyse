from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem


class ViewTree(QTreeWidget):

    def __init__(self, value):
        super().__init__()
        self.clicked.connect(self.click)

        def fill_item(item, value):
            def new_item(parent, key, val=None):
                child = QTreeWidgetItem([key])
                if not isinstance(val, str):
                    fill_item(child, val)
                parent.addChild(child)
                child.setExpanded(True)

            if not value:
                return
            elif isinstance(value, dict):
                for key, val in sorted(value.items()):
                    if key not in ['dirs', 'files']:
                        new_item(item, str(key), val)
                    else:
                        fill_item(item, val)
            elif isinstance(value, (list, tuple)):
                for val in value:
                    text = (str(val) if not isinstance(val, (dict, list, tuple))
                            else '[%s]' % type(val).__name__)
                    new_item(item, text, val)
            else:
                new_item(item, str(value))

        fill_item(self.invisibleRootItem(), value)

    def click(self, item: QModelIndex):
        path = []
        path.append(item.data())
        parent = item.parent()
        while parent.data():
            path.append(parent.data())
            parent = parent.parent()
        path = path[::-1]
        

if __name__ == '__main__':
    app = QApplication([])
    v1 = {'key1': 'value1', '2': {'10': 10}, 'key3': [1, 2, 3, {1: 3, 7: 9}]}
    v2 = {'dirs':
              {'C:\\':
                   {'dirs':
                        {'dev': {'dirs': {},
                                 'files': ['device_start.py', 'test.py']}},
                    'files': []}},
          'files': []}
    v3 = {'dirs':
              {'C:\\': {'dirs': {},
                        'files': ['device_start.py', 'test.py']}},

          'files': []}
    window = ViewTree(v2)
    window.show()
    app.exec_()