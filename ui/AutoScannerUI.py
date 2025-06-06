# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '.\ui\AutoScanner.ui'
#
# Created by: PyQt5 UI code generator 5.15.11
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_AutoScanner(object):
    def setupUi(self, AutoScanner):
        AutoScanner.setObjectName("AutoScanner")
        AutoScanner.resize(400, 300)
        self.gridLayout = QtWidgets.QGridLayout(AutoScanner)
        self.gridLayout.setObjectName("gridLayout")
        self.combo_baudrate_scanner = QtWidgets.QComboBox(AutoScanner)
        self.combo_baudrate_scanner.setObjectName("combo_baudrate_scanner")
        self.gridLayout.addWidget(self.combo_baudrate_scanner, 0, 2, 1, 1)
        self.label_com_scanner = QtWidgets.QLabel(AutoScanner)
        self.label_com_scanner.setObjectName("label_com_scanner")
        self.gridLayout.addWidget(self.label_com_scanner, 0, 0, 1, 1)
        self.combo_comport_scanner = QtWidgets.QComboBox(AutoScanner)
        self.combo_comport_scanner.setMinimumSize(QtCore.QSize(0, 0))
        self.combo_comport_scanner.setObjectName("combo_comport_scanner")
        self.gridLayout.addWidget(self.combo_comport_scanner, 0, 1, 1, 1)
        self.label_message_scanner = QtWidgets.QLabel(AutoScanner)
        self.label_message_scanner.setObjectName("label_message_scanner")
        self.gridLayout.addWidget(self.label_message_scanner, 2, 0, 1, 1)
        self.line_message_scanner = QtWidgets.QLineEdit(AutoScanner)
        self.line_message_scanner.setObjectName("line_message_scanner")
        self.gridLayout.addWidget(self.line_message_scanner, 2, 1, 1, 2)
        self.btn_apply = QtWidgets.QPushButton(AutoScanner)
        self.btn_apply.setObjectName("btn_apply")
        self.gridLayout.addWidget(self.btn_apply, 5, 2, 1, 1)
        self.label_status_scanner = QtWidgets.QLabel(AutoScanner)
        self.label_status_scanner.setObjectName("label_status_scanner")
        self.gridLayout.addWidget(self.label_status_scanner, 3, 0, 1, 1)
        self.btn_open_scanner = QtWidgets.QPushButton(AutoScanner)
        self.btn_open_scanner.setObjectName("btn_open_scanner")
        self.gridLayout.addWidget(self.btn_open_scanner, 3, 1, 1, 2)
        self.btn_cancel = QtWidgets.QPushButton(AutoScanner)
        self.btn_cancel.setObjectName("btn_cancel")
        self.gridLayout.addWidget(self.btn_cancel, 5, 1, 1, 1)

        self.retranslateUi(AutoScanner)
        QtCore.QMetaObject.connectSlotsByName(AutoScanner)

    def retranslateUi(self, AutoScanner):
        _translate = QtCore.QCoreApplication.translate
        AutoScanner.setWindowTitle(_translate("AutoScanner", "AutoScanner"))
        self.label_com_scanner.setText(_translate("AutoScanner", "COM & BAUD"))
        self.label_message_scanner.setText(_translate("AutoScanner", "Model"))
        self.btn_apply.setText(_translate("AutoScanner", "Apply"))
        self.label_status_scanner.setText(_translate("AutoScanner", "Status Scaner"))
        self.btn_open_scanner.setText(_translate("AutoScanner", "Open"))
        self.btn_cancel.setText(_translate("AutoScanner", "Cancel"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    AutoScanner = QtWidgets.QWidget()
    ui = Ui_AutoScanner()
    ui.setupUi(AutoScanner)
    AutoScanner.show()
    sys.exit(app.exec_())
