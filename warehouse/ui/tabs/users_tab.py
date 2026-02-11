from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QTextEdit, QTabWidget, QStackedLayout, QGridLayout, QScrollArea, QGroupBox
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
    return_withdrawal_item
)
from warehouse.controllers_material import get_materials
from warehouse.models import User, MaterialType
from warehouse.ui.user_form import UserFormDialog
from warehouse.ui.components import BarcodeSearchComboBox
from warehouse.ui.colors import AppColors
from warehouse.ui.tabs.withdrawals_tab import WithdrawalItemWidget, ReturnDialog


class UserDetailDialog(QDialog):
    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self.edit_mode = False
        self.materials_for_withdrawal = []
        self.setWindowTitle(f"Dettagli Utente: {user.first_name} {user.last_name}")
        self.resize(800, 700)

        main_layout = QVBoxLayout()
        
        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Details
        self.details_tab = QWidget()
        self.details_layout = QVBoxLayout(self.details_tab)
        self.setup_details_tab()
        self.tabs.addTab(self.details_tab, "Dettagli")

        # Tab 2: Withdrawals List
        self.withdrawals_list_tab = QWidget()
        self.withdrawals_list_layout = QVBoxLayout(self.withdrawals_list_tab)
        self.setup_withdrawals_list_tab()
        self.tabs.addTab(self.withdrawals_list_tab, "Lista Prelievi")

        # Tab 3: New Withdrawal
        self.new_withdrawal_tab = QWidget()
        self.new_withdrawal_layout = QVBoxLayout(self.new_withdrawal_tab)
        self.setup_new_withdrawal_tab()
        self.tabs.addTab(self.new_withdrawal_tab, "Nuovo Prelievo")

        # Bottom Buttons (Edit, Delete, Save/Cancel)
        bottom_layout = QHBoxLayout()
        
        self.edit_button = QPushButton("Modifica Dati")
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        bottom_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Elimina Utente")
        self.delete_button.setStyleSheet(AppColors.danger_button_style())
        self.delete_button.clicked.connect(self.delete_user_action)
        bottom_layout.addWidget(self.delete_button)
        
        bottom_layout.addStretch()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Salva")
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.setVisible(False)
        
        self.close_button = self.buttons.button(QDialogButtonBox.StandardButton.Close)
        self.close_button.setText("Chiudi")
        
        self.buttons.rejected.connect(self.reject)
        bottom_layout.addWidget(self.buttons)
        
        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

        self.load_withdrawals()
        self.load_materials_for_withdrawal()

    def setup_details_tab(self):
        # Using a ScrollArea for details in case the screen is small
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content = QWidget()
        # Apply compact style to all QLineEdits in this form
        content.setStyleSheet("QLineEdit { margin: 0px; padding: 2px; }")
        layout = QVBoxLayout(content)
        # Use QVBoxLayout with grouped widgets for precise spacing control
        details_layout = QVBoxLayout()
        details_layout.setSpacing(15)  # Space between groups (Field + Label)

        # Helper for stacked fields (consistent with Materials Tab)
        def create_stacked_field(value, placeholder=""):
            label = QLabel(str(value) if value else "-")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            # Match padding/border of QLineEdit to align text baseline
            label.setStyleSheet("padding: 2px; margin: 0px; border: 1px solid transparent;")
            
            edit = QLineEdit(str(value) if value else "")
            edit.setPlaceholderText(placeholder)
            # Compact style for input to match label height better
            edit.setStyleSheet("QLineEdit { margin: 0px; padding: 2px; border: 1px solid #CCCCCC; border-radius: 3px; }")
            
            stack = QStackedLayout()
            stack.setContentsMargins(0, 0, 0, 0)
            stack.addWidget(label)
            stack.addWidget(edit)
            
            widget = QWidget()
            widget.setLayout(stack)
            return label, edit, stack, widget

        def create_field_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {AppColors.GREY}; font-size: 11px;")
            return lbl
        
        def add_field_group(label_text, widget):
            container = QWidget()
            l = QVBoxLayout(container)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(2) # Very tight spacing between Label and Field
            
            l.addWidget(create_field_label(label_text))
            l.addWidget(widget)
            details_layout.addWidget(container)

        self.title_lbl, self.title_input, self.title_stack, title_widget = create_stacked_field(self.user.title)
        self.first_name_lbl, self.first_name_input, self.first_name_stack, first_name_widget = create_stacked_field(self.user.first_name)
        self.last_name_lbl, self.last_name_input, self.last_name_stack, last_name_widget = create_stacked_field(self.user.last_name)
        
        # ID field removed as requested
        
        self.code_lbl, self.code_input, self.code_stack, code_widget = create_stacked_field(self.user.code)
        self.workplace_lbl, self.workplace_input, self.workplace_stack, workplace_widget = create_stacked_field(self.user.workplace)
        self.mobile_lbl, self.mobile_input, self.mobile_stack, mobile_widget = create_stacked_field(self.user.mobile)
        self.email_lbl, self.email_input, self.email_stack, email_widget = create_stacked_field(self.user.email)
        
        self.notes_label = QLabel(self.user.notes or "")
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet("padding: 2px; margin: 0px; border: 1px solid transparent;")
        
        self.notes_input = QTextEdit()
        self.notes_input.setPlainText(self.user.notes or "")
        self.notes_input.setStyleSheet("margin: 0px; padding: 2px; border: 1px solid #CCCCCC; border-radius: 3px;")
        
        self.notes_stack = QStackedLayout()
        self.notes_stack.setContentsMargins(0, 0, 0, 0)
        self.notes_stack.addWidget(self.notes_label)
        self.notes_stack.addWidget(self.notes_input)
        notes_widget = QWidget()
        notes_widget.setLayout(self.notes_stack)

        add_field_group("Titolo", title_widget)
        add_field_group("Nome", first_name_widget)
        add_field_group("Cognome", last_name_widget)
        add_field_group("Codice (barcode)", code_widget)
        add_field_group("Luogo di lavoro", workplace_widget)
        add_field_group("Cellulare", mobile_widget)
        add_field_group("Email", email_widget)
        add_field_group("Note", notes_widget)

        layout.addLayout(details_layout)
        layout.addStretch()
        scroll.setWidget(content)
        self.details_layout.addWidget(scroll)

    def toggle_edit_mode(self):
        if self.edit_mode:
            # Cancel Edit Mode
            self.edit_mode = False
            
            # Reset values
            self.title_input.setText(self.user.title or "")
            self.first_name_input.setText(self.user.first_name)
            self.last_name_input.setText(self.user.last_name)
            self.code_input.setText(self.user.code or "")
            self.workplace_input.setText(self.user.workplace or "")
            self.mobile_input.setText(self.user.mobile or "")
            self.email_input.setText(self.user.email or "")
            self.notes_input.setPlainText(self.user.notes or "")
            
            # Reset stacks
            self.title_stack.setCurrentIndex(0)
            self.first_name_stack.setCurrentIndex(0)
            self.last_name_stack.setCurrentIndex(0)
            self.code_stack.setCurrentIndex(0)
            self.workplace_stack.setCurrentIndex(0)
            self.mobile_stack.setCurrentIndex(0)
            self.email_stack.setCurrentIndex(0)
            self.notes_stack.setCurrentIndex(0)
            
            self.save_button.setVisible(False)
            self.close_button.setVisible(True)
            self.edit_button.setText("Modifica Dati")
            self.delete_button.setEnabled(True)
        else:
            # Enable Edit Mode
            self.edit_mode = True
            self.title_stack.setCurrentIndex(1)
            self.first_name_stack.setCurrentIndex(1)
            self.last_name_stack.setCurrentIndex(1)
            self.code_stack.setCurrentIndex(1)
            self.workplace_stack.setCurrentIndex(1)
            self.mobile_stack.setCurrentIndex(1)
            self.email_stack.setCurrentIndex(1)
            self.notes_stack.setCurrentIndex(1)
            
            self.save_button.setVisible(True)
            self.save_button.setEnabled(True)
            self.close_button.setVisible(False)
            self.edit_button.setText("Annulla")
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
                    await parent.refresh_users()
                    
                self.accept() # Close dialog with Accepted result
                
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eliminare l'utente: {e}")

    def setup_withdrawals_list_tab(self):
        self.withdrawals_list = QListWidget()
        self.withdrawals_list.setSpacing(2)
        self.withdrawals_list_layout.addWidget(self.withdrawals_list)

    def setup_new_withdrawal_tab(self):
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        
        self.new_withdrawal_material_combo = BarcodeSearchComboBox()
        
        # Search Input matching MaterialDetailDialog pattern
        self.material_search_input = QLineEdit()
        self.material_search_input.setPlaceholderText("Cerca materiale in tutti i campi...")
        self.material_search_input.textChanged.connect(self.new_withdrawal_material_combo.setEditText)
        self.material_search_input.textChanged.connect(self.reset_search_check)
        self.material_search_input.returnPressed.connect(self.on_material_search_return)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.material_search_input)
        
        self.search_check_label = QLabel("✅")
        self.search_check_label.setStyleSheet(f"color: {AppColors.SUCCESS}; font-weight: bold; font-size: 16px;")
        self.search_check_label.hide()
        search_layout.addWidget(self.search_check_label)
        
        form_layout.addRow("Cerca:", search_layout)

        self.new_withdrawal_amount_input = QLineEdit()
        self.new_withdrawal_notes_input = QLineEdit()

        form_layout.addRow("Materiale:", self.new_withdrawal_material_combo)
        form_layout.addRow("Quantità:", self.new_withdrawal_amount_input)
        form_layout.addRow("Note:", self.new_withdrawal_notes_input)

        self.new_withdrawal_layout.addLayout(form_layout)

        self.add_withdrawal_button = QPushButton("Aggiungi Prelievo")
        self.add_withdrawal_button.clicked.connect(self.add_user_withdrawal)
        self.new_withdrawal_layout.addWidget(self.add_withdrawal_button)
        
        self.new_withdrawal_layout.addStretch()

    def reset_search_check(self):
        self.search_check_label.hide()

    def on_material_search_return(self):
        # Access the proxy model from the custom combo box
        proxy = self.new_withdrawal_material_combo.proxy_model
        if proxy.rowCount() == 1:
            # Get the index in the proxy model (row 0, column 0)
            proxy_index = proxy.index(0, 0)
            # Map it back to the source model index
            source_index = proxy.mapToSource(proxy_index)
            # Set the combo box selection
            self.new_withdrawal_material_combo.setCurrentIndex(source_index.row())
            # Show success indicator
            self.search_check_label.show()
            # Optional: move focus to next field
            self.new_withdrawal_amount_input.setFocus()

    @asyncSlot()
    async def load_withdrawals(self, *args):
        try:
            # returns list of (Withdrawal, Material)
            withdrawals_data = await get_user_withdrawals(self.user.id)
            self.withdrawals_list.clear()
            
            # Sort by date descending
            withdrawals_data.sort(key=lambda x: x[0].withdrawal_date, reverse=True)
            
            for withdrawal, material in withdrawals_data:
                item_widget = WithdrawalItemWidget(withdrawal, self.user, material)
                item_widget.return_requested.connect(self.handle_return_request)
                
                item = QListWidgetItem(self.withdrawals_list)
                item.setSizeHint(item_widget.sizeHint())
                self.withdrawals_list.addItem(item)
                self.withdrawals_list.setItemWidget(item, item_widget)
                
        except Exception as e:
            QMessageBox.warning(self, "Errore Caricamento Dati", f"Impossibile caricare i prelievi: {e}")

    @asyncSlot()
    async def handle_return_request(self, withdrawal_id: int):
        dialog = ReturnDialog(self)
        if dialog.exec():
            is_efficient = dialog.is_efficient()
            try:
                await return_withdrawal_item(withdrawal_id, is_efficient)
                QMessageBox.information(self, "Successo", "Attrezzatura restituita con successo.")
                await self.load_withdrawals()
                
                # Notify parent to refresh if needed
                parent = self.parent()
                if hasattr(parent, "refresh_users"):
                    await parent.refresh_users()
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Errore durante la restituzione: {e}")

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
                    label += " [Attrezzatura]"
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
                    self, "Errore", "Seleziona un materiale."
                )
                return
            material_id = self.new_withdrawal_material_combo.currentData()

            amount_text = self.new_withdrawal_amount_input.text().strip()
            if not amount_text.isdigit() or int(amount_text) <= 0:
                QMessageBox.warning(
                    self, "Errore", "La quantità deve essere un numero intero positivo."
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
            self.new_withdrawal_material_combo.setCurrentIndex(-1)
            self.material_search_input.clear()
            
            QMessageBox.information(self, "Successo", "Prelievo aggiunto con successo.")
        except Exception as e:
            QMessageBox.critical(
                self, "Errore", f"Impossibile creare il prelievo: {e}"
            )
        finally:
            self.add_withdrawal_button.setEnabled(True)

    @asyncSlot()
    async def save_changes(self, *args):
        self.buttons.setEnabled(False)

        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()

        if not first_name or not last_name:
            QMessageBox.warning(self, "Errore", "Nome e Cognome sono obbligatori.")
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
                await parent.refresh_users()
            QMessageBox.information(self, "Successo", "Utente aggiornato con successo.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiornare l'utente: {str(e)}")
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
        dialog.finished.connect(self.refresh_users)
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
