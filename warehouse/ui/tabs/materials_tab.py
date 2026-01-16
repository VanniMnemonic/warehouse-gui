from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from qasync import asyncSlot
import asyncio

from warehouse.controllers_material import (
    get_materials, update_material, get_material_batches, get_material_withdrawals
)
from warehouse.models import MaterialType, Material
from warehouse.ui.material_form import MaterialFormDialog


class MaterialDetailDialog(QDialog):
    def __init__(self, material: Material, parent=None):
        super().__init__(parent)
        self.material = material
        if material.material_type == MaterialType.ITEM:
            title = "Item Details"
        else:
            title = "Consumable Details"
        self.setWindowTitle(title)
        self.resize(600, 500)

        main_layout = QVBoxLayout()
        self.tabs = QTabWidget()

        # Tab 1: Details
        self.details_tab = QWidget()
        self.setup_details_tab()
        self.tabs.addTab(self.details_tab, "Details")

        # Tab 2: Batches
        self.batches_tab = QWidget()
        self.setup_batches_tab()
        self.tabs.addTab(self.batches_tab, "Batches")

        # Tab 3: Withdrawals
        self.withdrawals_tab = QWidget()
        self.setup_withdrawals_tab()
        self.tabs.addTab(self.withdrawals_tab, "Withdrawals")

        main_layout.addWidget(self.tabs)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save_changes)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

        self.setLayout(main_layout)
        
        # Load data
        self.load_related_data()

    def setup_details_tab(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        id_label = QLabel(str(self.material.id) if self.material.id is not None else "")
        type_label = QLabel(self.material.material_type.value)
        self.denomination_input = QLineEdit(self.material.denomination)
        self.ndc_input = QLineEdit(self.material.ndc or "")
        self.part_number_input = QLineEdit(self.material.part_number or "")
        self.serial_number_input = QLineEdit(self.material.serial_number or "")
        self.code_input = QLineEdit(self.material.code or "")
        self.image_input = QLineEdit(self.material.image_path or "" if self.material.image_path is not None else "")

        form_layout.addRow("ID:", id_label)
        form_layout.addRow("Type:", type_label)
        form_layout.addRow("Denomination:", self.denomination_input)
        form_layout.addRow("NDC:", self.ndc_input)
        form_layout.addRow("Part Number:", self.part_number_input)
        form_layout.addRow("Serial Number:", self.serial_number_input)
        form_layout.addRow("Code:", self.code_input)
        form_layout.addRow("Image Path:", self.image_input)

        layout.addLayout(form_layout)
        self.details_tab.setLayout(layout)

    def setup_batches_tab(self):
        layout = QVBoxLayout()
        self.batches_table = QTableWidget()
        self.batches_table.setColumnCount(4)
        self.batches_table.setHorizontalHeaderLabels(["ID", "Expiration", "Amount", "Location"])
        self.batches_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.batches_table)
        self.batches_tab.setLayout(layout)

    def setup_withdrawals_tab(self):
        layout = QVBoxLayout()
        self.withdrawals_table = QTableWidget()
        self.withdrawals_table.setColumnCount(4)
        self.withdrawals_table.setHorizontalHeaderLabels(["Date", "User", "Amount", "Notes"])
        self.withdrawals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.withdrawals_table)
        self.withdrawals_tab.setLayout(layout)

    @asyncSlot()
    async def load_related_data(self):
        try:
            # Load Batches
            batches = await get_material_batches(self.material.id)
            self.batches_table.setRowCount(len(batches))
            for i, batch in enumerate(batches):
                self.batches_table.setItem(i, 0, QTableWidgetItem(str(batch.id)))
                self.batches_table.setItem(i, 1, QTableWidgetItem(str(batch.expiration)))
                self.batches_table.setItem(i, 2, QTableWidgetItem(str(batch.amount)))
                self.batches_table.setItem(i, 3, QTableWidgetItem(batch.location or ""))

            # Load Withdrawals
            # returns list of (Withdrawal, User)
            withdrawals_data = await get_material_withdrawals(self.material.id)
            self.withdrawals_table.setRowCount(len(withdrawals_data))
            for i, (withdrawal, user) in enumerate(withdrawals_data):
                date_str = withdrawal.withdrawal_date.strftime("%Y-%m-%d %H:%M")
                user_str = f"{user.first_name} {user.last_name}"
                self.withdrawals_table.setItem(i, 0, QTableWidgetItem(date_str))
                self.withdrawals_table.setItem(i, 1, QTableWidgetItem(user_str))
                self.withdrawals_table.setItem(i, 2, QTableWidgetItem(str(withdrawal.amount)))
                self.withdrawals_table.setItem(i, 3, QTableWidgetItem(withdrawal.notes or ""))
                
        except Exception as e:
            QMessageBox.warning(self, "Data Load Error", f"Could not load related data: {e}")

    @asyncSlot()
    async def save_changes(self):
        self.buttons.setEnabled(False)

        denomination = self.denomination_input.text().strip()
        if not denomination:
            QMessageBox.warning(self, "Validation Error", "Denomination is required.")
            self.buttons.setEnabled(True)
            return

        try:
            updated = await update_material(
                self.material.id,
                denomination=denomination,
                ndc=self.ndc_input.text().strip() or None,
                part_number=self.part_number_input.text().strip() or None,
                serial_number=self.serial_number_input.text().strip() or None,
                code=self.code_input.text().strip() or None,
                image_path=self.image_input.text().strip() or None,
            )
            self.material.denomination = updated.denomination
            self.material.ndc = updated.ndc
            self.material.part_number = updated.part_number
            self.material.serial_number = updated.serial_number
            self.material.code = updated.code
            self.material.image_path = updated.image_path
            parent = self.parent()
            if hasattr(parent, "refresh_materials"):
                parent.refresh_materials()
            QMessageBox.information(self, "Success", "Material updated successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update material: {str(e)}")
            self.buttons.setEnabled(True)

class MaterialsTab(QWidget):
    def __init__(self, material_type: MaterialType):
        super().__init__()
        self.material_type = material_type
        self.materials = []
        self.layout = QVBoxLayout()
        self.setup_ui()
        self.setLayout(self.layout)
        
        # Load materials
        self.refresh_materials()

    def setup_ui(self):
        type_str = "Items" if self.material_type == MaterialType.ITEM else "Consumables"
        
        # Header
        header = QLabel(f"{type_str} Management")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        self.layout.addWidget(header)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(f"Search {type_str}...")
        # self.search_bar.textChanged.connect(self.on_search_changed) 
        self.layout.addWidget(self.search_bar)
        
        self.material_list = QListWidget()
        self.material_list.itemDoubleClicked.connect(self.open_material_detail)
        self.layout.addWidget(self.material_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.refresh_materials)
        btn_layout.addWidget(self.refresh_btn)
        
        self.add_btn = QPushButton(f"Add New {type_str[:-1]}") # Remove 's'
        self.add_btn.clicked.connect(self.open_add_material_dialog)
        btn_layout.addWidget(self.add_btn)
        
        self.layout.addLayout(btn_layout)

    @asyncSlot()
    async def refresh_materials(self):
        try:
            self.materials = await get_materials(self.material_type)
            self.update_list(self.materials)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load materials: {str(e)}")

    def update_list(self, materials):
        self.material_list.clear()
        for mat in materials:
            display_text = f"{mat.denomination}"
            if mat.part_number:
                display_text += f" (PN: {mat.part_number})"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, mat.id)
            self.material_list.addItem(item)

    def open_material_detail(self, item):
        material_id = item.data(Qt.ItemDataRole.UserRole)
        material = None
        for m in self.materials:
            if m.id == material_id:
                material = m
                break
        if material is None:
            return
        dialog = MaterialDetailDialog(material, self)
        dialog.open()

    @asyncSlot()
    async def open_add_material_dialog(self):
        dialog = MaterialFormDialog(self.material_type, self)
        
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        def on_finished(result):
            if not future.done():
                future.set_result(result)
                
        dialog.finished.connect(on_finished)
        dialog.open() 
        
        result = await future
        if result == QDialog.DialogCode.Accepted.value:
             await self.refresh_materials()
             self.search_bar.clear()
