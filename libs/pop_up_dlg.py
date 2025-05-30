from PyQt5.QtWidgets import QWidget, QApplication, QDialog, QLabel, QPushButton, QLineEdit
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

import os
import sys
import serial
import serial.tools
import serial.tools.list_ports
sys.path.append("./ui")
sys.path.append("libs")
sys.path.append("./")


from PopUpUI import Ui_PopUp
from serial_controller import SerialController
from logger import Logger
from canvas import WindowCanvas, Canvas
from shape import Shape
from ui_utils import load_style_sheet, update_style, add_scroll, ndarray2pixmap
from libs.constants import *

class PopUpDlg(QDialog):
    """
    Dialog for scanner controller popup with message, comport, and baudrate display,
    along with employee code input and Pass/Fail buttons.
    """
    confirmResult = pyqtSignal(str, bool)  # Result signal: employee_code, is_pass

    def __init__(self, message="", comport="", baudrate="", parent=None):
        super().__init__(parent)
        self.ui = Ui_PopUp()
        self.ui.setupUi(self)
        # Initialize variables
        self.message = message
        self.comport = comport
        self.baudrate = baudrate
        self.result_value = "FAIL"  # Default result value

        self.initUI()
        self.connectUI()
        self.updateValues()
    
    def initUI(self):
        self.ui.btn_pass.setProperty("class", "success")
        self.ui.btn_fail.setProperty("class", "danger")

        self.ui.line_mnv.setReadOnly(True)

    def connectUI(self):
        """Connect UI signals to slots"""
        self.ui.btn_pass.clicked.connect(self.on_click_pass)
        self.ui.btn_fail.clicked.connect(self.on_click_fail)
        
    def updateValues(self):
        """Update UI with the provided values"""
        self.ui.label_message.setText(self.message)
        self.ui.label_comport_value.setText(self.comport)
        self.ui.label_baudrate_value.setText(self.baudrate)
    
    def on_click_pass(self):
        """Handle Pass button click"""
        employee_code = self.ui.line_mnv.text()
        if employee_code:
            self.result_value = "PASS"  # Set result to PASS when Pass button is clicked
            self.accept()
        else:
            # If no employee code is entered, don't close the dialog
            self.ui.label_message.setText("Please enter employee code")

    
    def on_click_fail(self):
        """Handle Fail button click"""
        employee_code = self.ui.line_mnv.text()
        if employee_code:
            self.result_value = "FAIL"  # Set result to FAIL when Fail button is clicked
            self.accept()
        else:
            # If no employee code is entered, don't close the dialog
            self.ui.label_message.setText("Please enter employee code")


    def popUp(self):
        return self.result_value if self.exec_() else ""

    def wait_data_received_from_scanner_controller(self, data):
        try:
            if len(data) == 8:
                self.ui.line_mnv.setText(data)
        except Exception as e:
            print(f"Error processing scanner value: {e}")
        
    def closeEvent(self, event):
        print("closed")
        pass
        

# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = PopUpDlg(
        message="Scan QR Code", 
        comport="COM11", 
        baudrate="9600"
    )
    
    # Example of connecting to the result signal
    def handle_result(employee_code, is_pass):
        result = "PASS" if is_pass else "FAIL"
        print(f"Employee: {employee_code}, Result: {result}")
    
    dialog.confirmResult.connect(handle_result)
    ret = dialog.popUp()
    print(ret)
        
    sys.exit(0)