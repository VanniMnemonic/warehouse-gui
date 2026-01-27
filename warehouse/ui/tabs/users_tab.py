from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QStackedLayout, QComboBox, QGridLayout, QScrollArea, QGroupBox
)
from PyQt6.QtCore import Qt
from qasync import asyncSlot
import asyncio

from warehouse.controllers import (
    get_all_users,
    filter_users,
    update_user,
    get_user_withdrawals,
    create_withdrawal,
    get_user_dependencies,
    delete_user,
)
from warehouse.controllers_material import get_materials
from warehouse.models import User, MaterialType
from warehouse.ui.user_form import UserFormDialog
from warehouse.ui.components import BarcodeSearchComboBox


class UserDetailDialog(QDialog):
    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self.edit_mode = False
        self.materials_for_withdrawal = []
        self.setWindowTitle("Dettagli Utente")
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

        # Section 2: Withdrawals
        self.setup_withdrawals_section()

        self.content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        self.edit_button = QPushButton("Modifica")
        self.edit_button.clicked.connect(self.enable_edit_mode)
        main_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Elimina Utente")
        self.delete_button.setStyleSheet("background-color: #d32f2f; color: white;")
        self.delete_button.clicked.connect(self.delete_user_action)
        main_layout.addWidget(self.delete_button)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.setEnabled(False)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

        self.setLayout(main_layout)

        self.load_withdrawals()
        self.load_materials_for_withdrawal()

    def setup_details_section(self):
        group = QGroupBox("Dettagli")
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self.title_label = QLabel(self.user.title or "")
        self.title_input = QLineEdit(self.user.title or "")
        self.title_stack = QStackedLayout()
        self.title_stack.addWidget(self.title_label)
        self.title_stack.addWidget(self.title_input)
        title_widget = QWidget()
        title_widget.setLayout(self.title_stack)

        self.first_name_label = QLabel(self.user.first_name)
        self.first_name_input = QLineEdit(self.user.first_name)
        self.first_name_stack = QStackedLayout()
        self.first_name_stack.addWidget(self.first_name_label)
        self.first_name_stack.addWidget(self.first_name_input)
        first_name_widget = QWidget()
        first_name_widget.setLayout(self.first_name_stack)

        self.last_name_label = QLabel(self.user.last_name)
        self.last_name_input = QLineEdit(self.user.last_name)
        self.last_name_stack = QStackedLayout()
        self.last_name_stack.addWidget(self.last_name_label)
        self.last_name_stack.addWidget(self.last_name_input)
        last_name_widget = QWidget()
        last_name_widget.setLayout(self.last_name_stack)

        self.custom_id_label = QLabel(self.user.custom_id)

        self.code_label = QLabel(self.user.code or "")
        self.code_input = QLineEdit(self.user.code or "")
        self.code_stack = QStackedLayout()
        self.code_stack.addWidget(self.code_label)
        self.code_stack.addWidget(self.code_input)
        code_widget = QWidget()
        code_widget.setLayout(self.code_stack)

        self.workplace_label = QLabel(self.user.workplace or "")
        self.workplace_input = QLineEdit(self.user.workplace or "")
        self.workplace_stack = QStackedLayout()
        self.workplace_stack.addWidget(self.workplace_label)
        self.workplace_stack.addWidget(self.workplace_input)
        workplace_widget = QWidget()
        workplace_widget.setLayout(self.workplace_stack)

        self.mobile_label = QLabel(self.user.mobile or "")
        self.mobile_input = QLineEdit(self.user.mobile or "")
        self.mobile_stack = QStackedLayout()
        self.mobile_stack.addWidget(self.mobile_label)
        self.mobile_stack.addWidget(self.mobile_input)
        mobile_widget = QWidget()
        mobile_widget.setLayout(self.mobile_stack)

        self.email_label = QLabel(self.user.email or "")
        self.email_input = QLineEdit(self.user.email or "")
        self.email_stack = QStackedLayout()
        self.email_stack.addWidget(self.email_label)
        self.email_stack.addWidget(self.email_input)
        email_widget = QWidget()
        email_widget.setLayout(self.email_stack)

        self.notes_label = QLabel(self.user.notes or "")
        self.notes_label.setWordWrap(True)
        self.notes_input = QTextEdit()
        self.notes_input.setPlainText(self.user.notes or "")
        self.notes_stack = QStackedLayout()
        self.notes_stack.addWidget(self.notes_label)
        self.notes_stack.addWidget(self.notes_input)
        notes_widget = QWidget()
        notes_widget.setLayout(self.notes_stack)

        form_layout.addRow("Titolo:", title_widget)
        form_layout.addRow("Nome:", first_name_widget)
        form_layout.addRow("Cognome:", last_name_widget)
        form_layout.addRow("ID:", self.custom_id_label)
        form_layout.addRow("Codice (barcode):", code_widget)
        form_layout.addRow("Luogo di lavoro:", workplace_widget)
        form_layout.addRow("Cellulare:", mobile_widget)
        form_layout.addRow("Email:", email_widget)
        form_layout.addRow("Note:", notes_widget)

        layout.addLayout(form_layout)
        group.setLayout(layout)
        self.content_layout.addWidget(group)

    def enable_edit_mode(self):
        if self.edit_mode:
            return
        self.edit_mode = True
        self.title_stack.setCurrentIndex(1)
        self.first_name_stack.setCurrentIndex(1)
        self.last_name_stack.setCurrentIndex(1)
        self.code_stack.setCurrentIndex(1)
        self.workplace_stack.setCurrentIndex(1)
        self.mobile_stack.setCurrentIndex(1)
        self.email_stack.setCurrentIndex(1)
        self.notes_stack.setCurrentIndex(1)
        self.save_button.setEnabled(True)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    @asyncSlot()
    async def delete_user_action(self):
        try:
            withdrawal_count = await get_user_dependencies(self.user.id)
            
            msg = f"Sei sicuro di voler eliminare l'utente {self.user.first_name} {self.user.last_name}?"
            if withdrawal_count > 0:
                msg += f"\n\nATTENZIONE: Eliminando questo utente verranno eliminati anche {withdrawal_count} prelievi associati!"
            else:
                msg += "\n\nNessun prelievo associato verrà eliminato."
                
            reply = QMessageBox.question(
                self, 
                "Conferma Eliminazione", 
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                await delete_user(self.user.id)
                QMessageBox.information(self, "Eliminato", "Utente eliminato con successo.")
                
                parent = self.parent()
                if hasattr(parent, "refresh_users"):
                    parent.refresh_users()
                    
                self.accept() # Close dialog with Accepted result
                
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eliminare l'utente: {e}")

    def setup_withdrawals_section(self):
        group = QGroupBox("Prelievi")
        layout = QVBoxLayout()
        self.withdrawals_table = QTableWidget()
        self.withdrawals_table.setMinimumHeight(150)
        self.withdrawals_table.setColumnCount(4)
        self.withdrawals_table.setHorizontalHeaderLabels(
            ["Data", "Materiale", "Quantità", "Note"]
        )
        self.withdrawals_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.withdrawals_table)

        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.new_withdrawal_material_combo = BarcodeSearchComboBox()
        self.new_withdrawal_amount_input = QLineEdit()
        self.new_withdrawal_notes_input = QLineEdit()

        form_layout.addRow("Materiale:", self.new_withdrawal_material_combo)
        form_layout.addRow("Quantità:", self.new_withdrawal_amount_input)
        form_layout.addRow("Note:", self.new_withdrawal_notes_input)

        layout.addLayout(form_layout)

        self.add_withdrawal_button = QPushButton("Aggiungi Prelievo")
        self.add_withdrawal_button.clicked.connect(self.add_user_withdrawal)
        layout.addWidget(self.add_withdrawal_button)

        group.setLayout(layout)
        self.content_layout.addWidget(group)

    @asyncSlot()
    async def load_withdrawals(self, *args):
        try:
            # returns list of (Withdrawal, Material)
            withdrawals_data = await get_user_withdrawals(self.user.id)
            self.withdrawals_table.setRowCount(len(withdrawals_data))
            for i, (withdrawal, material) in enumerate(withdrawals_data):
                date_str = withdrawal.withdrawal_date.strftime("%Y-%m-%d %H:%M")
                material_str = material.denomination
                self.withdrawals_table.setItem(i, 0, QTableWidgetItem(date_str))
                self.withdrawals_table.setItem(i, 1, QTableWidgetItem(material_str))
                self.withdrawals_table.setItem(i, 2, QTableWidgetItem(str(withdrawal.amount)))
                self.withdrawals_table.setItem(i, 3, QTableWidgetItem(withdrawal.notes or ""))
        except Exception as e:
            QMessageBox.warning(self, "Errore Caricamento Dati", f"Impossibile caricare i prelievi: {e}")

    @asyncSlot()
    async def load_materials_for_withdrawal(self, *args):
        try:
            materials: list = []
            for m_type in (MaterialType.ITEM, MaterialType.CONSUMABLE):
                mats = await get_materials(m_type)
                materials.extend(mats)

            self.materials_for_withdrawal = materials
            self.new_withdrawal_material_combo.clear()
            for mat in materials:
                label = mat.denomination
                if mat.material_type == MaterialType.ITEM:
                    label += " [Oggetto]"
                else:
                    label += " [Consumabile]"
                
                # Build comprehensive search text
                search_text = (
                    f"{mat.denomination or ''} "
                    f"{mat.part_number or ''} "
                    f"{mat.ndc or ''} "
                    f"{mat.code or ''} "
                    f"{mat.serial_number or ''} "
                    f"{str(mat.id)}"
                )
                
                self.new_withdrawal_material_combo.addItem(label, mat.id, barcode=mat.code, search_text=search_text)
        except Exception as e:
            QMessageBox.warning(
                self, "Errore Caricamento Dati", f"Impossibile caricare i materiali: {e}"
            )

    @asyncSlot()
    async def add_user_withdrawal(self):
        self.add_withdrawal_button.setEnabled(False)
        try:
            index = self.new_withdrawal_material_combo.currentIndex()
            if index < 0:
                QMessageBox.warning(
                    self, "Validation Error", "Please select a material."
                )
                return
            material_id = self.new_withdrawal_material_combo.currentData()

            amount_text = self.new_withdrawal_amount_input.text().strip()
            if not amount_text.isdigit() or int(amount_text) <= 0:
                QMessageBox.warning(
                    self, "Validation Error", "Amount must be a positive integer."
                )
                return
            amount = int(amount_text)

            notes = self.new_withdrawal_notes_input.text().strip() or None

            await create_withdrawal(
                user_id=self.user.id,
                material_id=material_id,
                amount=amount,
                notes=notes,
            )
            await self.load_withdrawals()
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

        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()

        if not first_name or not last_name:
            QMessageBox.warning(self, "Validation Error", "First Name and Last Name are required.")
            self.buttons.setEnabled(True)
            return

        try:
            updated = await update_user(
                self.user.id,
                title=self.title_input.text().strip() or None,
                first_name=first_name,
                last_name=last_name,
                workplace=self.workplace_input.text().strip() or None,
                mobile=self.mobile_input.text().strip() or None,
                email=self.email_input.text().strip() or None,
                code=self.code_input.text().strip() or None,
                notes=self.notes_input.toPlainText().strip() or None,
            )
            self.user.title = updated.title
            self.user.first_name = updated.first_name
            self.user.last_name = updated.last_name
            self.user.workplace = updated.workplace
            self.user.mobile = updated.mobile
            self.user.email = updated.email
            self.user.code = updated.code
            self.user.notes = updated.notes
            parent = self.parent()
            if hasattr(parent, "refresh_users"):
                parent.refresh_users()
            QMessageBox.information(self, "Success", "User updated successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update user: {str(e)}")
            self.buttons.setEnabled(True)


class UserItemWidget(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Main info container
        info_layout = QGridLayout()
        info_layout.setVerticalSpacing(2)
        info_layout.setHorizontalSpacing(10) # Add some horizontal spacing
        
        # Row 0: Name (Bold) spanning 2 columns
        name_label = QLabel(f"{self.user.first_name} {self.user.last_name}")
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(name_label, 0, 0, 1, 2)
        
        # Row 1: ID and Workplace
        if self.user.custom_id:
            id_label = QLabel(f"ID: {self.user.custom_id}")
            id_label.setStyleSheet("color: #555;")
            info_layout.addWidget(id_label, 1, 0)
            
        if self.user.workplace:
            wp_label = QLabel(f"Luogo: {self.user.workplace}")
            wp_label.setStyleSheet("color: #555;")
            info_layout.addWidget(wp_label, 1, 1)
            
        # Row 2: Barcode
        if self.user.code:
            code_label = QLabel(f"Barcode: {self.user.code}")
            code_label.setStyleSheet("color: #666; font-family: 'Courier New';")
            info_layout.addWidget(code_label, 2, 0, 1, 2)
            
        layout.addLayout(info_layout, stretch=1)
        self.setLayout(layout)

class UsersTab(QWidget):
    def __init__(self):
        super().__init__()
        self.users = []
        self.layout = QVBoxLayout()
        self.setup_ui()
        self.setLayout(self.layout)
        
        # Load users
        self.refresh_users()

    def setup_ui(self):
        # Header
        header = QLabel("Gestione Utenti")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        self.layout.addWidget(header)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Cerca utenti (Nome, ID, Luogo di lavoro)...")
        self.search_bar.textChanged.connect(self.on_search_changed)
        self.layout.addWidget(self.search_bar)
        
        self.user_list = QListWidget()
        self.user_list.itemActivated.connect(self.open_user_detail)
        self.layout.addWidget(self.user_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Aggiorna Lista")
        self.refresh_btn.clicked.connect(self.refresh_users)
        btn_layout.addWidget(self.refresh_btn)
        
        self.add_btn = QPushButton("Aggiungi Nuovo Utente")
        self.add_btn.clicked.connect(self.open_add_user_dialog)
        btn_layout.addWidget(self.add_btn)
        
        self.layout.addLayout(btn_layout)

    @asyncSlot()
    async def refresh_users(self, *args):
        try:
            self.users = await get_all_users()
            self.update_list(self.users)
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile caricare gli utenti: {str(e)}")

    def update_list(self, users):
        self.user_list.clear()
        for user in users:
            # Keep text for filtering purposes
            display_text = f"[{user.custom_id}] {user.first_name} {user.last_name}"
            if user.workplace:
                display_text += f" - {user.workplace}"
            
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, user.id) # Store ID
            
            widget = UserItemWidget(user)
            item.setSizeHint(widget.sizeHint())
            
            self.user_list.addItem(item)
            self.user_list.setItemWidget(item, widget)

    def open_user_detail(self, item):
        user_id = item.data(Qt.ItemDataRole.UserRole)
        user = None
        for u in self.users:
            if u.id == user_id:
                user = u
                break
        if user is None:
            return
        dialog = UserDetailDialog(user, self)
        dialog.open()

    def on_search_changed(self, text):
        filtered = filter_users(text, self.users)
        self.update_list(filtered)

    @asyncSlot()
    async def open_add_user_dialog(self):
        dialog = UserFormDialog(self)
        
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        def on_finished(result):
            if not future.done():
                future.set_result(result)
                
        dialog.finished.connect(on_finished)
        dialog.open() 
        
        result = await future
        if result == QDialog.DialogCode.Accepted.value:
             await self.refresh_users()
             self.search_bar.clear()
             # We can't access MainWindow status bar easily here without passing reference
             # Maybe emit a signal? For now just silent update.
