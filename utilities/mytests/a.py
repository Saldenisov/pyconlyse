from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)

dialog = QFileDialog()
foo_dir = dialog.getExistingDirectory(None, 'Select an awesome directory')
print(foo_dir)

sys.exit(app.exec_())