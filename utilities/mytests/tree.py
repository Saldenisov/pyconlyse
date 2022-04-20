from PyQt5.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem


class ViewTree(QTreeWidget):
    def __init__(self, value):
        super().__init__()

        def fill_item(item, value):
            def new_item(parent, text, val=None):
                child = QTreeWidgetItem([text])
                fill_item(child, val)
                parent.addChild(child)
                child.setExpanded(True)

            if value is None:
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

    import h5py

    p = {}

    with h5py.File("E:\\data\\h5\\Data_pyconlyse_1.hdf5", 'a') as h5f:
        def fill_keys(d, obj):
            if len(obj.keys()) == 0:
                return None
            else:
                for key in obj.keys():
                    if isinstance(obj[key], h5py.Dataset):
                        d[key] = None
                    else:
                        d[key] = {}
                        d[key] = fill_keys(d[key], obj[key])
                return d


        p = fill_keys(p, h5f)

    window = ViewTree(p)
    window.show()
    app.exec_()