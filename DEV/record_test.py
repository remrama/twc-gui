from PyQt5 import QtCore, QtWidgets
from PyQt5 import QtMultimedia


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec_())
