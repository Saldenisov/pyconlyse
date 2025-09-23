import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLineEdit, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtSql import QSqlDatabase, QSqlQuery


class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.name_edit = QLineEdit(self)
        self.age_edit = QLineEdit(self)
        self.gender_edit = QLineEdit(self)
        self.name_label = QLabel("Name:", self)
        self.age_label = QLabel("Age:", self)
        self.gender_label = QLabel("Gender:", self)
        self.submit_button = QPushButton("Submit", self)
        self.submit_button.clicked.connect(self.submitData)

        layout = QVBoxLayout(self)
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.age_label)
        layout.addWidget(self.age_edit)
        layout.addWidget(self.gender_label)
        layout.addWidget(self.gender_edit)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)
        self.setWindowTitle("SQLite Database Example")
        self.show()

    from PyQt5.QtWidgets import QMessageBox

    def submitData(self):
        name = self.name_edit.text()
        age = self.age_edit.text()
        gender = self.gender_edit.text()

        # connect to the database
        db = QSqlDatabase.addDatabase("QSQLITE")
        db.setDatabaseName("data.db")
        db.open()

        # create table if it doesn't exist
        query = QSqlQuery()
        query.exec_("""CREATE TABLE IF NOT EXISTS data (
                      name TEXT,
                      age INTEGER,
                      gender CHAR(1))""")

        # insert data into table
        query.prepare("INSERT INTO data (name, age, gender) VALUES (:name, :age, :gender)")
        query.bindValue(":name", name)
        query.bindValue(":age", age)
        query.bindValue(":gender", gender)
        query.exec_()

        db.close()
        self.name_edit.clear()
        self.age_edit.clear()
        self.gender_edit.clear()

        # display message to confirm data was inserted
        # QMessageBox.information(self, 'Success', 'Data inserted successfully')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())

