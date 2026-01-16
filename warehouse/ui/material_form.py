from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox, 
    QMessageBox
)
from qasync import asyncSlot
from warehouse.models import MaterialType
from warehouse.controllers_material import create_material

class MaterialFormDialog(QDialog):
    def __init__(self, material_type: MaterialType, parent=None):
        super().__init__(parent)
        self.material_type = material_type
        type_str = "Item" if material_type == MaterialType.ITEM else "Consumable"
        self.setWindowTitle(f"Add New {type_str}")
        self.resize(400, 400)
        
        self.layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        
        # Fields
        self.denomination_input = QLineEdit()
        self.ndc_input = QLineEdit()
        self.part_number_input = QLineEdit()
        self.serial_number_input = QLineEdit()
        self.code_input = QLineEdit()
        
        self.form_layout.addRow("Denomination *:", self.denomination_input)
        self.form_layout.addRow("NDC:", self.ndc_input)
        self.form_layout.addRow("Part Number:", self.part_number_input)
        self.form_layout.addRow("Serial Number:", self.serial_number_input)
        self.form_layout.addRow("Code:", self.code_input)
        
        self.layout.addLayout(self.form_layout)
        
        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        # Manual connection for async handling
        self.buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.accept_data)
        self.buttons.rejected.connect(self.reject)
        
        self.layout.addWidget(self.buttons)
        self.setLayout(self.layout)

    @asyncSlot()
    async def accept_data(self):
        self.buttons.setEnabled(False)
        
        denomination = self.denomination_input.text().strip()
        
        if not denomination:
            QMessageBox.warning(self, "Validation Error", "Denomination is required.")
            self.buttons.setEnabled(True)
            return

        try:
            material = await create_material(
                material_type=self.material_type,
                denomination=denomination,
                ndc=self.ndc_input.text().strip() or None,
                part_number=self.part_number_input.text().strip() or None,
                serial_number=self.serial_number_input.text().strip() or None,
                code=self.code_input.text().strip() or None
            )
            QMessageBox.information(self, "Success", f"{self.material_type.value.capitalize()} created successfully!")
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create material: {str(e)}")
            self.buttons.setEnabled(True)
