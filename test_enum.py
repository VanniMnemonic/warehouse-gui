from PyQt6.QtWidgets import QDialog, QApplication
import sys

app = QApplication(sys.argv)
print(f"Accepted value: {QDialog.DialogCode.Accepted.value}")
print(f"Comparison with 1: {QDialog.DialogCode.Accepted == 1}")
print(f"Comparison with value: {QDialog.DialogCode.Accepted.value == 1}")
