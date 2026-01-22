from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QStackedLayout, QComboBox, QDateEdit, QGridLayout, QScrollArea, QGroupBox
)
from PyQt6.QtCore import Qt, QDate
from qasync import asyncSlot
import asyncio

from warehouse.controllers_material import (
    get_materials, update_material, get_material_batches, get_material_withdrawals,
    create_batch
)
from warehouse.controllers import get_all_users, create_withdrawal, get_active_item_withdrawals
from warehouse.models import MaterialType, Material
from warehouse.ui.material_form import MaterialFormDialog


class MaterialDetailDialog(QDialog):
    def __init__(self, material: Material, parent=None):
        super().__init__(parent)
        self.material = material
        self.edit_mode = False
        self.users_for_withdrawal = []
        if material.material_type == MaterialType.ITEM:
            title = "Dettagli Oggetto"
        else:
            title = "Dettagli Consumabile"
        self.setWindowTitle(title)
        self.resize(700, 800)

        main_layout = QVBoxLayout()
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(20)

        # Section 1: Details
        self.setup_details_section()

        # Section 2: Batches
        self.setup_batches_section()

        # Section 3: Withdrawals
        self.setup_withdrawals_section()
        
        self.content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        self.edit_button = QPushButton("Modifica")
        self.edit_button.clicked.connect(self.enable_edit_mode)
        main_layout.addWidget(self.edit_button)

        self.is_withdrawn = False
        if self.material.material_type == MaterialType.ITEM:
            self.actions_layout = QHBoxLayout()
            
            self.toggle_efficiency_btn = QPushButton()
            self.toggle_efficiency_btn.clicked.connect(self.toggle_efficiency)
            self.actions_layout.addWidget(self.toggle_efficiency_btn)
            
            self.withdraw_btn = QPushButton("Preleva Oggetto")
            self.withdraw_btn.clicked.connect(self.withdraw_item_action)
            self.actions_layout.addWidget(self.withdraw_btn)
            
            main_layout.addLayout(self.actions_layout)
            self.update_action_buttons()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.setEnabled(False)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

        self.setLayout(main_layout)

        self.load_related_data()
        self.load_users_for_withdrawal()

    def setup_details_section(self):
        group = QGroupBox("Dettagli")
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        id_label = QLabel(str(self.material.id) if self.material.id is not None else "")
        type_label = QLabel(self.material.material_type.value)

        self.denomination_label = QLabel(self.material.denomination)
        self.denomination_input = QLineEdit(self.material.denomination)
        self.denomination_stack = QStackedLayout()
        self.denomination_stack.addWidget(self.denomination_label)
        self.denomination_stack.addWidget(self.denomination_input)
        denomination_widget = QWidget()
        denomination_widget.setLayout(self.denomination_stack)

        self.ndc_label = QLabel(self.material.ndc or "")
        self.ndc_input = QLineEdit(self.material.ndc or "")
        self.ndc_stack = QStackedLayout()
        self.ndc_stack.addWidget(self.ndc_label)
        self.ndc_stack.addWidget(self.ndc_input)
        ndc_widget = QWidget()
        ndc_widget.setLayout(self.ndc_stack)

        self.part_number_label = QLabel(self.material.part_number or "")
        self.part_number_input = QLineEdit(self.material.part_number or "")
        self.part_number_stack = QStackedLayout()
        self.part_number_stack.addWidget(self.part_number_label)
        self.part_number_stack.addWidget(self.part_number_input)
        part_number_widget = QWidget()
        part_number_widget.setLayout(self.part_number_stack)

        self.serial_number_label = QLabel(self.material.serial_number or "")
        self.serial_number_input = QLineEdit(self.material.serial_number or "")
        self.serial_number_stack = QStackedLayout()
        self.serial_number_stack.addWidget(self.serial_number_label)
        self.serial_number_stack.addWidget(self.serial_number_input)
        serial_number_widget = QWidget()
        serial_number_widget.setLayout(self.serial_number_stack)

        self.code_label = QLabel(self.material.code or "")
        self.code_input = QLineEdit(self.material.code or "")
        self.code_stack = QStackedLayout()
        self.code_stack.addWidget(self.code_label)
        self.code_stack.addWidget(self.code_input)
        code_widget = QWidget()
        code_widget.setLayout(self.code_stack)

        self.image_label = QLabel(self.material.image_path or "" if self.material.image_path is not None else "")
        self.image_input = QLineEdit(self.material.image_path or "" if self.material.image_path is not None else "")
        self.image_stack = QStackedLayout()
        self.image_stack.addWidget(self.image_label)
        self.image_stack.addWidget(self.image_input)
        image_widget = QWidget()
        image_widget.setLayout(self.image_stack)
        
        # Location Field for Items
        self.location_label = QLabel("")
        self.location_input = QLineEdit("")
        self.location_stack = QStackedLayout()
        self.location_stack.addWidget(self.location_label)
        self.location_stack.addWidget(self.location_input)
        location_widget = QWidget()
        location_widget.setLayout(self.location_stack)

        form_layout.addRow("ID:", id_label)
        form_layout.addRow("Tipo:", type_label)
        form_layout.addRow("Denominazione:", denomination_widget)
        form_layout.addRow("NDC:", ndc_widget)
        form_layout.addRow("Part Number:", part_number_widget)
        form_layout.addRow("Numero di Serie:", serial_number_widget)
        form_layout.addRow("Codice:", code_widget)
        
        if self.material.material_type == MaterialType.ITEM:
            form_layout.addRow("Posizione:", location_widget)
            
        form_layout.addRow("Percorso Immagine:", image_widget)

        layout.addLayout(form_layout)
        group.setLayout(layout)
        self.content_layout.addWidget(group)

    def enable_edit_mode(self):
        if self.edit_mode:
            return
        self.edit_mode = True
        self.denomination_stack.setCurrentIndex(1)
        self.ndc_stack.setCurrentIndex(1)
        self.part_number_stack.setCurrentIndex(1)
        self.serial_number_stack.setCurrentIndex(1)
        self.code_stack.setCurrentIndex(1)
        self.image_stack.setCurrentIndex(1)
        if self.material.material_type == MaterialType.ITEM:
            self.location_stack.setCurrentIndex(1)
        self.save_button.setEnabled(True)
        self.edit_button.setEnabled(False)

    def setup_batches_section(self):
        if self.material.material_type == MaterialType.ITEM:
            return
            
        group = QGroupBox("Lotti")
        layout = QVBoxLayout()
        self.batches_table = QTableWidget()
        self.batches_table.setMinimumHeight(150)
        self.batches_table.setColumnCount(4)
        self.batches_table.setHorizontalHeaderLabels(["ID", "Scadenza", "Quantità", "Posizione"])
        self.batches_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.batches_table)

        if self.material.material_type == MaterialType.CONSUMABLE:
            form_layout = QFormLayout()
            form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
            
            self.new_batch_expiration = QDateEdit()
            self.new_batch_expiration.setDate(QDate.currentDate())
            self.new_batch_expiration.setCalendarPopup(True)
            self.new_batch_expiration.setDisplayFormat("yyyy-MM-dd")
            
            self.new_batch_amount = QLineEdit()
            self.new_batch_amount.setPlaceholderText("Quantità")
            
            self.new_batch_location = QLineEdit()
            self.new_batch_location.setPlaceholderText("Posizione")
            
            form_layout.addRow("Scadenza:", self.new_batch_expiration)
            form_layout.addRow("Quantità:", self.new_batch_amount)
            form_layout.addRow("Posizione:", self.new_batch_location)
            
            layout.addLayout(form_layout)
            
            self.add_batch_button = QPushButton("Aggiungi Lotto")
            self.add_batch_button.clicked.connect(self.add_batch)
            layout.addWidget(self.add_batch_button)

        group.setLayout(layout)
        self.content_layout.addWidget(group)

    @asyncSlot()
    async def add_batch(self, *args):
        self.add_batch_button.setEnabled(False)
        try:
            expiration = self.new_batch_expiration.date().toPyDate()
            amount_text = self.new_batch_amount.text().strip()
            location = self.new_batch_location.text().strip() or None
            
            if not amount_text.isdigit() or int(amount_text) <= 0:
                QMessageBox.warning(self, "Errore", "La quantità deve essere un numero intero positivo.")
                return

            amount = int(amount_text)
            
            await create_batch(
                material_id=self.material.id,
                expiration=expiration,
                amount=amount,
                location=location
            )
            
            # Refresh batches
            await self.load_related_data()
            
            # Reset form
            self.new_batch_amount.clear()
            self.new_batch_location.clear()
            self.new_batch_expiration.setDate(QDate.currentDate())
            
            QMessageBox.information(self, "Successo", "Lotto aggiunto con successo.")
            
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiungere il lotto: {e}")
        finally:
            self.add_batch_button.setEnabled(True)

    def setup_withdrawals_section(self):
        group = QGroupBox("Prelievi")
        layout = QVBoxLayout()
        self.withdrawals_table = QTableWidget()
        self.withdrawals_table.setMinimumHeight(150)
        self.withdrawals_table.setColumnCount(4)
        self.withdrawals_table.setHorizontalHeaderLabels(
            ["Data", "Utente", "Quantità", "Note"]
        )
        self.withdrawals_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.withdrawals_table)

        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.new_withdrawal_user_combo = QComboBox()
        self.new_withdrawal_amount_input = QLineEdit()
        self.new_withdrawal_notes_input = QLineEdit()

        form_layout.addRow("Utente:", self.new_withdrawal_user_combo)
        form_layout.addRow("Quantità:", self.new_withdrawal_amount_input)
        form_layout.addRow("Note:", self.new_withdrawal_notes_input)

        layout.addLayout(form_layout)

        self.add_withdrawal_button = QPushButton("Aggiungi Prelievo")
        self.add_withdrawal_button.clicked.connect(self.add_material_withdrawal)
        layout.addWidget(self.add_withdrawal_button)

        group.setLayout(layout)
        self.content_layout.addWidget(group)

    def update_action_buttons(self):
        if self.material.material_type != MaterialType.ITEM:
            return
            
        if self.material.is_efficient:
            self.toggle_efficiency_btn.setText("Segnala come Non Efficiente")
            # self.toggle_efficiency_btn.setStyleSheet("background-color: #ffcccc;") 
        else:
            self.toggle_efficiency_btn.setText("Segnala come Efficiente")
            # self.toggle_efficiency_btn.setStyleSheet("background-color: #ccffcc;") 
            
        if self.is_withdrawn:
            self.withdraw_btn.setEnabled(False)
            self.withdraw_btn.setText("Oggetto Prelevato")
        else:
            self.withdraw_btn.setEnabled(True)
            self.withdraw_btn.setText("Preleva Oggetto")

    @asyncSlot()
    async def toggle_efficiency(self):
        try:
            new_status = not self.material.is_efficient
            await update_material(self.material.id, is_efficient=new_status)
            self.material.is_efficient = new_status
            self.update_action_buttons()
            
            parent = self.parent()
            if hasattr(parent, "refresh_materials"):
                await parent.refresh_materials()
                
            QMessageBox.information(self, "Successo", f"Oggetto segnato come {'Efficiente' if new_status else 'Non Efficiente'}.")
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiornare lo stato: {e}")

    def withdraw_item_action(self):
        self.new_withdrawal_user_combo.setFocus()
        self.new_withdrawal_amount_input.setText("1")

    @asyncSlot()
    async def load_related_data(self, *args):
        try:
            # Load Batches
            batches = await get_material_batches(self.material.id)
            
            if self.material.material_type == MaterialType.ITEM:
                # For ITEM, populate location from the first batch
                if batches:
                    batch = batches[0]
                    self.location_label.setText(batch.location or "")
                    self.location_input.setText(batch.location or "")
            else:
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
            
            if self.material.material_type == MaterialType.ITEM and len(withdrawals_data) > 0:
                latest_withdrawal, _ = withdrawals_data[0]
                self.is_withdrawn = latest_withdrawal.return_date is None
                self.update_action_buttons()
                
        except Exception as e:
            QMessageBox.warning(self, "Errore Caricamento Dati", f"Impossibile caricare i dati correlati: {e}")

    @asyncSlot()
    async def load_users_for_withdrawal(self, *args):
        try:
            users = await get_all_users()
            self.users_for_withdrawal = users
            self.new_withdrawal_user_combo.clear()
            for user in users:
                label = f"{user.first_name} {user.last_name} [{user.custom_id}]"
                self.new_withdrawal_user_combo.addItem(label, user.id)
        except Exception as e:
            QMessageBox.warning(self, "Errore Caricamento Dati", f"Impossibile caricare gli utenti: {e}")

    @asyncSlot()
    async def add_material_withdrawal(self, *args):
        self.add_withdrawal_button.setEnabled(False)
        try:
            index = self.new_withdrawal_user_combo.currentIndex()
            if index < 0:
                QMessageBox.warning(
                    self, "Validation Error", "Please select a user."
                )
                return
            user_id = self.new_withdrawal_user_combo.currentData()

            amount_text = self.new_withdrawal_amount_input.text().strip()
            if not amount_text.isdigit() or int(amount_text) <= 0:
                QMessageBox.warning(
                    self, "Validation Error", "Amount must be a positive integer."
                )
                return
            amount = int(amount_text)

            notes = self.new_withdrawal_notes_input.text().strip() or None

            await create_withdrawal(
                user_id=user_id,
                material_id=self.material.id,
                amount=amount,
                notes=notes,
            )
            await self.load_related_data()
            self.new_withdrawal_amount_input.clear()
            self.new_withdrawal_notes_input.clear()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to create withdrawal: {e}"
            )
        finally:
            self.add_withdrawal_button.setEnabled(True)

    @asyncSlot()
    async def save_changes(self, *args):
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
                location=self.location_input.text().strip() or None if self.material.material_type == MaterialType.ITEM else None
            )
            self.material.denomination = updated.denomination
            self.material.ndc = updated.ndc
            self.material.part_number = updated.part_number
            self.material.serial_number = updated.serial_number
            self.material.code = updated.code
            self.material.image_path = updated.image_path
            
            if self.material.material_type == MaterialType.ITEM:
                new_loc = self.location_input.text().strip()
                self.location_label.setText(new_loc)
            
            parent = self.parent()
            if hasattr(parent, "refresh_materials"):
                parent.refresh_materials()
            QMessageBox.information(self, "Success", "Material updated successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update material: {str(e)}")
            self.buttons.setEnabled(True)

class MaterialItemWidget(QWidget):
    def __init__(self, material: Material):
        super().__init__()
        self.material = material
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Main info container
        info_layout = QGridLayout()
        info_layout.setVerticalSpacing(2)
        info_layout.setHorizontalSpacing(10)
        
        # Row 0: Denomination (Bold) spanning 2 columns
        name_label = QLabel(self.material.denomination)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(name_label, 0, 0, 1, 2)
        
        # Row 1: P/N and S/N
        if self.material.part_number:
            pn_label = QLabel(f"P/N: {self.material.part_number}")
            pn_label.setStyleSheet("color: #555;")
            info_layout.addWidget(pn_label, 1, 0)
            
        if self.material.serial_number:
            sn_label = QLabel(f"S/N: {self.material.serial_number}")
            sn_label.setStyleSheet("color: #555;")
            info_layout.addWidget(sn_label, 1, 1)
            
        # Row 2: NDC and Code
        current_row = 2
        
        if self.material.ndc:
            ndc_label = QLabel(f"NDC: {self.material.ndc}")
            ndc_label.setStyleSheet("color: #555;")
            info_layout.addWidget(ndc_label, current_row, 0)
        
        if self.material.code:
            code_label = QLabel(f"Code: {self.material.code}")
            code_label.setStyleSheet("color: #666; font-family: 'Courier New';")
            info_layout.addWidget(code_label, current_row, 1)

        layout.addLayout(info_layout, stretch=1)
        self.setLayout(layout)

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
        type_str = "Oggetti" if self.material_type == MaterialType.ITEM else "Consumabili"
        title_str = "Gestione " + type_str
        
        # Header
        header = QLabel(title_str)
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        self.layout.addWidget(header)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(f"Cerca {type_str}...")
        self.search_bar.textChanged.connect(self.filter_list) 
        self.layout.addWidget(self.search_bar)
        
        if self.material_type == MaterialType.ITEM:
            self.tabs = QTabWidget()
            
            self.list_efficient = QListWidget()
            self.list_efficient.itemActivated.connect(self.open_material_detail)
            self.tabs.addTab(self.list_efficient, "Efficienti")
            
            self.list_inefficient = QListWidget()
            self.list_inefficient.itemActivated.connect(self.open_material_detail)
            self.tabs.addTab(self.list_inefficient, "Non Efficienti")
            
            self.list_withdrawn = QListWidget()
            self.list_withdrawn.itemActivated.connect(self.open_material_detail)
            self.tabs.addTab(self.list_withdrawn, "Prelevati")
            
            self.layout.addWidget(self.tabs)
        else:
            self.material_list = QListWidget()
            self.material_list.itemActivated.connect(self.open_material_detail)
            self.layout.addWidget(self.material_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Aggiorna Lista")
        self.refresh_btn.clicked.connect(self.refresh_materials)
        btn_layout.addWidget(self.refresh_btn)
        
        add_btn_text = "Aggiungi Nuovo Oggetto" if self.material_type == MaterialType.ITEM else "Aggiungi Nuovo Consumabile"
        self.add_btn = QPushButton(add_btn_text)
        self.add_btn.clicked.connect(self.open_add_material_dialog)
        btn_layout.addWidget(self.add_btn)
        
        self.layout.addLayout(btn_layout)

    @asyncSlot()
    async def refresh_materials(self, *args):
        try:
            self.materials = await get_materials(self.material_type)
            active_withdrawals = set()
            if self.material_type == MaterialType.ITEM:
                active_withdrawals = await get_active_item_withdrawals()
            self.update_list(self.materials, active_withdrawals)
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile caricare i materiali: {str(e)}")

    def update_list(self, materials, active_withdrawals=None):
        if self.material_type == MaterialType.ITEM:
            self.list_efficient.clear()
            self.list_inefficient.clear()
            self.list_withdrawn.clear()
            
            for mat in materials:
                display_text = f"{mat.denomination}"
                if mat.part_number:
                    display_text += f" (PN: {mat.part_number})"
                
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, mat.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, display_text)
                
                widget = MaterialItemWidget(mat)
                item.setSizeHint(widget.sizeHint())
                
                if active_withdrawals and mat.id in active_withdrawals:
                    self.list_withdrawn.addItem(item)
                    self.list_withdrawn.setItemWidget(item, widget)
                elif getattr(mat, 'is_efficient', True):
                    self.list_efficient.addItem(item)
                    self.list_efficient.setItemWidget(item, widget)
                else:
                    self.list_inefficient.addItem(item)
                    self.list_inefficient.setItemWidget(item, widget)
            
            # Re-apply filter if needed
            self.filter_list(self.search_bar.text())
        else:
            self.material_list.clear()
            for mat in materials:
                display_text = f"{mat.denomination}"
                if mat.part_number:
                    display_text += f" (PN: {mat.part_number})"
                
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, mat.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, display_text)
                
                widget = MaterialItemWidget(mat)
                item.setSizeHint(widget.sizeHint())

                self.material_list.addItem(item)
                self.material_list.setItemWidget(item, widget)
            self.filter_list(self.search_bar.text())

    def filter_list(self, query):
        query = query.lower().strip()
        
        if self.material_type == MaterialType.ITEM:
            lists = [self.list_efficient, self.list_inefficient, self.list_withdrawn]
        else:
            lists = [self.material_list]
            
        for lst in lists:
            for i in range(lst.count()):
                item = lst.item(i)
                filter_text = item.data(Qt.ItemDataRole.UserRole + 1) or ""
                item.setHidden(query not in filter_text.lower())

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
