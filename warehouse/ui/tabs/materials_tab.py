from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QMessageBox, QDialog, QFormLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QGridLayout, QScrollArea, QGroupBox, QStackedLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QDate, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
from qasync import asyncSlot
import asyncio
import os
import uuid
from datetime import timedelta
from warehouse.utils import get_base_path

from warehouse.controllers_material import (
    get_materials, update_material, get_material_batches, get_material_withdrawals,
    create_batch, get_material_dependencies, delete_material, get_consumable_stocks
)
from warehouse.controllers import get_all_users, create_withdrawal, get_active_item_withdrawals, return_withdrawal_item
from warehouse.models import MaterialType, Material
from warehouse.ui.material_form import MaterialFormDialog, ImageDropWidget
from warehouse.ui.components import BarcodeSearchComboBox
from warehouse.ui.tabs.withdrawals_tab import ReturnDialog


from warehouse.ui.colors import AppColors

class BatchItemWidget(QWidget):
    def __init__(self, batch, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Info
        info_layout = QVBoxLayout()
        expiration_lbl = QLabel(f"Scadenza: {batch.expiration}")
        expiration_lbl.setStyleSheet("font-weight: bold;")
        
        amount_lbl = QLabel(f"Quantità: {batch.amount}")
        location_lbl = QLabel(f"Posizione: {batch.location or '-'}")
        
        info_layout.addWidget(expiration_lbl)
        info_layout.addWidget(amount_lbl)
        info_layout.addWidget(location_lbl)
        
        layout.addLayout(info_layout)
        
        # Status (Expired?)
        today = QDate.currentDate().toPyDate()
        if batch.expiration < today:
            status_lbl = QLabel("SCADUTO")
            status_lbl.setStyleSheet(AppColors.danger_style())
            layout.addWidget(status_lbl)
        elif batch.expiration <= today + timedelta(days=30):
            status_lbl = QLabel("IN SCADENZA")
            status_lbl.setStyleSheet(AppColors.warning_style())
            layout.addWidget(status_lbl)

class MaterialWithdrawalItemWidget(QWidget):
    return_requested = pyqtSignal(int)

    def __init__(self, withdrawal, user, material, parent=None):
        super().__init__(parent)
        self.withdrawal = withdrawal
        self.user = user
        self.material = material
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # User Info
        user_info = QVBoxLayout()
        user_lbl = QLabel(f"Utente: {user.first_name} {user.last_name}")
        user_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        date_lbl = QLabel(f"Data: {withdrawal.withdrawal_date.strftime('%Y-%m-%d %H:%M')}")
        
        user_info.addWidget(user_lbl)
        user_info.addWidget(date_lbl)
        layout.addLayout(user_info, stretch=1)
        
        # Amount & Notes
        details_layout = QVBoxLayout()
        amount_lbl = QLabel(f"Quantità: {withdrawal.amount}")
        amount_lbl.setStyleSheet(f"color: {AppColors.TEAL}; font-weight: bold;")
        details_layout.addWidget(amount_lbl)
        
        if withdrawal.notes:
            notes_lbl = QLabel(f"Note: {withdrawal.notes}")
            notes_lbl.setStyleSheet(f"color: {AppColors.GREY}; font-style: italic;")
            details_layout.addWidget(notes_lbl)
            
        layout.addLayout(details_layout, stretch=1)
        
        # Return Status / Action
        status_layout = QVBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        if self.material.material_type == MaterialType.ITEM:
            if withdrawal.return_date:
                ret_lbl = QLabel(f"Restituito:\n{withdrawal.return_date.strftime('%Y-%m-%d')}")
                ret_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                status_layout.addWidget(ret_lbl)
                
                eff_text = "Efficiente" if withdrawal.efficient_at_return else "Inefficiente"
                eff_lbl = QLabel(eff_text)
                eff_lbl.setStyleSheet(f"color: {AppColors.SUCCESS if withdrawal.efficient_at_return else AppColors.DANGER}; font-weight: bold;")
                eff_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                status_layout.addWidget(eff_lbl)
            else:
                # Active - Show Return Button
                btn_return = QPushButton("Restituisci")
                btn_return.setFixedWidth(100)
                btn_return.clicked.connect(lambda: self.return_requested.emit(self.withdrawal.id))
                status_layout.addWidget(btn_return)
                
                # Highlight active withdrawal
                active_lbl = QLabel("IN USO")
                active_lbl.setStyleSheet(f"color: {AppColors.WARNING}; font-weight: bold; border: 1px solid {AppColors.WARNING}; padding: 4px; border-radius: 4px;")
                active_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                status_layout.addWidget(active_lbl)
        else:
            # Consumable
            pass
            
        layout.addLayout(status_layout)


class MaterialDetailDialog(QDialog):
    def __init__(self, material: Material, parent=None):
        super().__init__(parent)
        self.material = material
        self.users_for_withdrawal = []
        self.edit_mode = False
        
        if material.material_type == MaterialType.ITEM:
            title = "Dettagli Attrezzatura"
        else:
            title = "Dettagli Consumabile"
        self.setWindowTitle(title)
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
        
        # Tab 2: Batches (Only for Consumables)
        if self.material.material_type == MaterialType.CONSUMABLE:
            self.batches_tab = QWidget()
            self.batches_layout = QVBoxLayout(self.batches_tab)
            self.setup_batches_tab()
            self.tabs.addTab(self.batches_tab, "Gestione Lotti")

        # Tab 3: Withdrawals History
        self.withdrawals_list_tab = QWidget()
        self.withdrawals_list_layout = QVBoxLayout(self.withdrawals_list_tab)
        self.setup_withdrawals_list_tab()
        self.tabs.addTab(self.withdrawals_list_tab, "Lista Prelievi")

        # Tab 4: New Withdrawal
        self.new_withdrawal_tab = QWidget()
        self.new_withdrawal_layout = QVBoxLayout(self.new_withdrawal_tab)
        self.setup_new_withdrawal_tab()
        self.tabs.addTab(self.new_withdrawal_tab, "Nuovo Prelievo")

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        
        self.edit_button = QPushButton("Modifica Dati")
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        bottom_layout.addWidget(self.edit_button)
        
        if self.material.material_type == MaterialType.ITEM:
            self.toggle_efficiency_btn = QPushButton()
            self.toggle_efficiency_btn.clicked.connect(self.toggle_efficiency)
            self.update_efficiency_button()
            bottom_layout.addWidget(self.toggle_efficiency_btn)

        self.delete_button = QPushButton("Elimina")
        self.delete_button.setStyleSheet(AppColors.danger_button_style())
        self.delete_button.clicked.connect(self.delete_material_action)
        bottom_layout.addWidget(self.delete_button)
        
        bottom_layout.addStretch()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Salva")
        self.close_button = self.buttons.button(QDialogButtonBox.StandardButton.Close)
        self.close_button.setText("Chiudi")
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.setVisible(False)
        self.buttons.rejected.connect(self.reject)
        bottom_layout.addWidget(self.buttons)
        
        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

        self.load_related_data()
        self.load_users_for_withdrawal()

    def update_efficiency_button(self):
        if self.material.is_efficient:
            self.toggle_efficiency_btn.setText("Segnala come Non Efficiente")
            self.toggle_efficiency_btn.setStyleSheet(f"color: {AppColors.DANGER};")
        else:
            self.toggle_efficiency_btn.setText("Segnala come Efficiente")
            self.toggle_efficiency_btn.setStyleSheet(f"color: {AppColors.SUCCESS};")

    def setup_details_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content = QWidget()
        content.setStyleSheet("QLineEdit { margin: 0px; padding: 2px; }")
        layout = QVBoxLayout(content)
        
        # Top section: Image and Basic Info
        top_layout = QHBoxLayout()
        
        # Image Section
        self.image_stack = QStackedLayout()
        
        # View Mode Image
        self.image_view = QLabel()
        self.image_view.setFixedSize(200, 200)
        self.image_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_view.setStyleSheet(f"border: 1px solid {AppColors.GREY}; background-color: #f9f9f9; border-radius: 8px;")
        self.update_image_view()
        
        # Edit Mode Image
        self.image_edit = ImageDropWidget()
        self.image_edit.setFixedSize(200, 200)
        if self.material.image_path:
             full_path = os.path.join(get_base_path(), self.material.image_path)
             if os.path.exists(full_path):
                 self.image_edit.load_image(full_path)
        
        self.image_container = QWidget()
        self.image_stack.addWidget(self.image_view)
        self.image_stack.addWidget(self.image_edit)
        self.image_container.setLayout(self.image_stack)
        self.image_container.setFixedSize(200, 200)
        
        top_layout.addWidget(self.image_container, 0, Qt.AlignmentFlag.AlignTop)
        
        # Basic Info Form
        details_layout = QVBoxLayout()
        details_layout.setSpacing(15)  # Space between groups (Field + Label)

        # Helper for stacked fields
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

        self.denomination_lbl, self.denomination_input, self.denomination_stack, denomination_widget = create_stacked_field(self.material.denomination)
        self.ndc_lbl, self.ndc_input, self.ndc_stack, ndc_widget = create_stacked_field(self.material.ndc)
        self.part_lbl, self.part_input, self.part_stack, part_widget = create_stacked_field(self.material.part_number)
        self.serial_lbl, self.serial_input, self.serial_stack, serial_widget = create_stacked_field(self.material.serial_number)
        self.code_lbl, self.code_input, self.code_stack, code_widget = create_stacked_field(self.material.code)
        
        add_field_group("Denominazione", denomination_widget)
        add_field_group("NDC", ndc_widget)
        add_field_group("Part Number", part_widget)
        add_field_group("S/N", serial_widget)
        add_field_group("Codice", code_widget)
        
        if self.material.material_type == MaterialType.CONSUMABLE:
             self.min_stock_lbl, self.min_stock_input, self.min_stock_stack, min_stock_widget = create_stacked_field(self.material.min_stock)
             add_field_group("Scorta Minima", min_stock_widget)
        
        if self.material.material_type == MaterialType.ITEM:
            self.location_lbl, self.location_input, self.location_stack, location_widget = create_stacked_field("", "Posizione")
            add_field_group("Posizione", location_widget)

        top_layout.addLayout(details_layout)
        layout.addLayout(top_layout)
        layout.addStretch()
        
        scroll.setWidget(content)
        self.details_layout.addWidget(scroll)
    def update_image_view(self):
        if self.material.image_path:
            full_path = os.path.join(get_base_path(), self.material.image_path)
            if os.path.exists(full_path):
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        200, 200,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.image_view.setPixmap(scaled)
                else:
                    self.image_view.setText("Immagine non valida")
            else:
                self.image_view.setText("File non trovato")
        else:
            self.image_view.setText("Nessuna immagine")

    def toggle_edit_mode(self):
        if self.edit_mode:
            # Cancel Edit Mode
            self.edit_mode = False
            
            # Reset values
            self.denomination_input.setText(self.material.denomination)
            self.ndc_input.setText(self.material.ndc or "")
            self.part_input.setText(self.material.part_number or "")
            self.serial_input.setText(self.material.serial_number or "")
            self.code_input.setText(self.material.code or "")
            
            if hasattr(self, 'min_stock_input'):
                self.min_stock_input.setText(str(self.material.min_stock))
            if hasattr(self, 'location_input'):
                self.location_input.setText("") 
            
            # Reset Image
            if self.material.image_path:
                 full_path = os.path.join(get_base_path(), self.material.image_path)
                 if os.path.exists(full_path):
                     self.image_edit.load_image(full_path)
                 else:
                     self.image_edit.setText("\n\nTrascina qui l'immagine\no Clicca per Selezionare\n\n")
                     self.image_edit.current_image_path = None
            else:
                self.image_edit.setText("\n\nTrascina qui l'immagine\no Clicca per Selezionare\n\n")
                self.image_edit.current_image_path = None
            
            # Reset stacks
            self.image_stack.setCurrentIndex(0)
            self.denomination_stack.setCurrentIndex(0)
            self.ndc_stack.setCurrentIndex(0)
            self.part_stack.setCurrentIndex(0)
            self.serial_stack.setCurrentIndex(0)
            self.code_stack.setCurrentIndex(0)
            
            if hasattr(self, 'min_stock_stack'):
                self.min_stock_stack.setCurrentIndex(0)
            if hasattr(self, 'location_stack'):
                self.location_stack.setCurrentIndex(0)
                
            self.save_button.setVisible(False)
            self.close_button.setVisible(True)
            self.edit_button.setText("Modifica Dati")
            self.delete_button.setEnabled(True)
        else:
            # Enable Edit Mode
            self.edit_mode = True
            self.image_stack.setCurrentIndex(1)
            self.denomination_stack.setCurrentIndex(1)
            self.ndc_stack.setCurrentIndex(1)
            self.part_stack.setCurrentIndex(1)
            self.serial_stack.setCurrentIndex(1)
            self.code_stack.setCurrentIndex(1)
            
            if hasattr(self, 'min_stock_stack'):
                self.min_stock_stack.setCurrentIndex(1)
            if hasattr(self, 'location_stack'):
                self.location_stack.setCurrentIndex(1)
                
            self.save_button.setVisible(True)
            self.save_button.setEnabled(True)
            self.close_button.setVisible(False)
            self.edit_button.setText("Annulla")
            self.delete_button.setEnabled(False)

    def setup_batches_tab(self):
        self.batches_list = QListWidget()
        self.batches_list.setSpacing(2)
        self.batches_layout.addWidget(self.batches_list)
        
        # Add Batch Form
        form_group = QGroupBox("Nuovo Lotto")
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
        
        form_group.setLayout(form_layout)
        self.batches_layout.addWidget(form_group)
        
        self.add_batch_button = QPushButton("Aggiungi Lotto")
        self.add_batch_button.clicked.connect(self.add_batch)
        self.batches_layout.addWidget(self.add_batch_button)

    def setup_withdrawals_list_tab(self):
        self.withdrawals_list = QListWidget()
        self.withdrawals_list.setSpacing(2)
        self.withdrawals_list_layout.addWidget(self.withdrawals_list)

    def setup_new_withdrawal_tab(self):
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self.new_withdrawal_user_combo = BarcodeSearchComboBox()
        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("Cerca utente in tutti i campi...")
        self.user_search_input.textChanged.connect(self.new_withdrawal_user_combo.setEditText)
        self.user_search_input.textChanged.connect(self.reset_search_check)
        self.user_search_input.returnPressed.connect(self.on_user_search_return)

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.user_search_input)
        
        self.search_check_label = QLabel("✅")
        self.search_check_label.setStyleSheet(f"color: {AppColors.SUCCESS}; font-weight: bold; font-size: 16px;")
        self.search_check_label.hide()
        search_layout.addWidget(self.search_check_label)

        form_layout.addRow("Cerca:", search_layout)
        self.new_withdrawal_amount_input = QLineEdit()
        self.new_withdrawal_notes_input = QLineEdit()

        form_layout.addRow("Utente:", self.new_withdrawal_user_combo)
        form_layout.addRow("Quantità:", self.new_withdrawal_amount_input)
        form_layout.addRow("Note:", self.new_withdrawal_notes_input)

        self.new_withdrawal_layout.addLayout(form_layout)

        self.add_withdrawal_button = QPushButton("Aggiungi Prelievo")
        self.add_withdrawal_button.clicked.connect(self.add_material_withdrawal)
        self.new_withdrawal_layout.addWidget(self.add_withdrawal_button)
        
        self.new_withdrawal_layout.addStretch()

    @asyncSlot()
    async def toggle_efficiency(self):
        try:
            new_status = not self.material.is_efficient
            await update_material(self.material.id, is_efficient=new_status)
            self.material.is_efficient = new_status
            self.update_efficiency_button()
            
            parent = self.parent()
            if hasattr(parent, "refresh_materials"):
                await parent.refresh_materials()
                
            QMessageBox.information(self, "Successo", f"Attrezzatura segnata come {'Efficiente' if new_status else 'Non Efficiente'}.")
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiornare lo stato: {e}")

    def withdraw_item_action(self):
        self.tabs.setCurrentWidget(self.new_withdrawal_tab)
        self.new_withdrawal_user_combo.setFocus()
        self.new_withdrawal_amount_input.setText("1")

    @asyncSlot()
    async def delete_material_action(self):
        try:
            batch_count, withdrawal_count = await get_material_dependencies(self.material.id)
            total_deps = batch_count + withdrawal_count
            
            msg = f"Sei sicuro di voler eliminare {self.material.denomination}?"
            if total_deps > 0:
                msg += f"\n\nATTENZIONE: Eliminando questo elemento verranno eliminati anche {batch_count} lotti e {withdrawal_count} prelievi associati!"
            else:
                msg += "\n\nNessun dato associato verrà eliminato."
                
            reply = QMessageBox.question(
                self, 
                "Conferma Eliminazione", 
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                await delete_material(self.material.id)
                QMessageBox.information(self, "Eliminato", "Elemento eliminato con successo.")
                
                parent = self.parent()
                if hasattr(parent, "refresh_materials"):
                    await parent.refresh_materials()
                    
                self.accept()
                
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eliminare l'elemento: {e}")

    @asyncSlot()
    async def add_batch(self):
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
            
            await self.load_related_data()
            
            # Reset form
            self.new_batch_amount.clear()
            self.new_batch_location.clear()
            self.new_batch_expiration.setDate(QDate.currentDate())
            
            parent = self.parent()
            if hasattr(parent, "refresh_materials"):
                await parent.refresh_materials()
                
            QMessageBox.information(self, "Successo", "Lotto aggiunto con successo.")
            
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiungere il lotto: {e}")
        finally:
            self.add_batch_button.setEnabled(True)

    @asyncSlot()
    async def load_related_data(self, *args):
        try:
            # Load Batches (only if Consumable)
            if self.material.material_type == MaterialType.CONSUMABLE:
                batches = await get_material_batches(self.material.id)
                self.batches_list.clear()
                
                # Sort by expiration
                batches.sort(key=lambda x: x.expiration)
                
                for batch in batches:
                    item_widget = BatchItemWidget(batch)
                    item = QListWidgetItem(self.batches_list)
                    item.setSizeHint(item_widget.sizeHint())
                    self.batches_list.addItem(item)
                    self.batches_list.setItemWidget(item, item_widget)
            
            elif self.material.material_type == MaterialType.ITEM:
                # For ITEM, populate location from the first batch if exists (usually 1 batch per item if tracked that way)
                batches = await get_material_batches(self.material.id)
                if batches:
                    batch = batches[0]
                    self.location_lbl.setText(batch.location or "-")
                    self.location_input.setText(batch.location or "")

            # Load Withdrawals
            # returns list of (Withdrawal, User)
            withdrawals_data = await get_material_withdrawals(self.material.id)
            self.withdrawals_list.clear()
            
            # Sort by date descending
            withdrawals_data.sort(key=lambda x: x[0].withdrawal_date, reverse=True)
            
            for withdrawal, user in withdrawals_data:
                item_widget = MaterialWithdrawalItemWidget(withdrawal, user, self.material)
                item_widget.return_requested.connect(self.handle_return)
                item = QListWidgetItem(self.withdrawals_list)
                item.setSizeHint(item_widget.sizeHint())
                self.withdrawals_list.addItem(item)
                self.withdrawals_list.setItemWidget(item, item_widget)
            
        except Exception as e:
            QMessageBox.warning(self, "Errore Caricamento Dati", f"Impossibile caricare i dati correlati: {e}")

    @asyncSlot()
    async def handle_return(self, withdrawal_id):
        dialog = ReturnDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            efficient = dialog.is_efficient()
            try:
                await return_withdrawal_item(withdrawal_id, efficient)
                
                # Update local material state
                self.material.is_efficient = efficient
                self.update_efficiency_button()
                
                QMessageBox.information(self, "Successo", "Attrezzatura restituita con successo.")
                
                # Refresh withdrawals list
                await self.load_related_data()
                
                # Refresh parent list
                parent = self.parent()
                if hasattr(parent, "refresh_materials"):
                    await parent.refresh_materials()
                    
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile restituire l'attrezzatura: {e}")

    @asyncSlot()
    async def load_users_for_withdrawal(self, *args):
        try:
            users = await get_all_users()
            self.users_for_withdrawal = users
            self.new_withdrawal_user_combo.clear()
            for user in users:
                label = f"{user.first_name} {user.last_name} [{user.custom_id}]"
                
                # Build comprehensive search text
                search_text = (
                    f"{user.first_name} {user.last_name} "
                    f"{user.custom_id or ''} "
                    f"{user.workplace or ''} "
                    f"{user.mobile or ''} "
                    f"{user.email or ''} "
                    f"{user.code or ''}"
                )
                
                self.new_withdrawal_user_combo.addItem(label, user.id, barcode=user.code, search_text=search_text)
        except Exception as e:
            QMessageBox.warning(self, "Errore Caricamento Dati", f"Impossibile caricare gli utenti: {e}")

    def reset_search_check(self):
        self.search_check_label.hide()

    def on_user_search_return(self):
        # Access the proxy model from the custom combo box
        proxy = self.new_withdrawal_user_combo.proxy_model
        if proxy.rowCount() == 1:
            # Get the index in the proxy model (row 0, column 0)
            proxy_index = proxy.index(0, 0)
            # Map it back to the source model index
            source_index = proxy.mapToSource(proxy_index)
            # Set the combo box selection
            self.new_withdrawal_user_combo.setCurrentIndex(source_index.row())
            # Show success indicator
            self.search_check_label.show()
            # Optional: move focus to next field
            self.new_withdrawal_amount_input.setFocus()

    @asyncSlot()
    async def add_material_withdrawal(self, *args):
        self.add_withdrawal_button.setEnabled(False)
        try:
            index = self.new_withdrawal_user_combo.currentIndex()
            if index < 0:
                QMessageBox.warning(self, "Errore", "Seleziona un utente.")
                return
            
            user_id = self.new_withdrawal_user_combo.itemData(index)
            if not user_id:
                QMessageBox.warning(self, "Errore", "Utente non valido.")
                return

            amount_text = self.new_withdrawal_amount_input.text().strip()
            if not amount_text.isdigit() or int(amount_text) <= 0:
                QMessageBox.warning(self, "Errore", "La quantità deve essere un numero intero positivo.")
                return
            
            amount = int(amount_text)
            
            # Check availability if it's a consumable
            if self.material.material_type == MaterialType.CONSUMABLE:
                 batches = await get_material_batches(self.material.id)
                 total_stock = sum(b.amount for b in batches)
                 withdrawals = await get_material_withdrawals(self.material.id)
                 total_withdrawn = sum(w[0].amount for w in withdrawals)
                 available = total_stock - total_withdrawn
                 
                 if amount > available:
                     QMessageBox.warning(self, "Attenzione", f"Quantità non disponibile. Disponibile: {available}")
                     return

            notes = self.new_withdrawal_notes_input.text().strip() or None

            await create_withdrawal(
                user_id=user_id,
                material_id=self.material.id,
                amount=amount,
                notes=notes
            )

            # Refresh withdrawals
            await self.load_related_data()
            
            # Reset form
            self.new_withdrawal_amount_input.clear()
            self.new_withdrawal_notes_input.clear()
            self.new_withdrawal_user_combo.setCurrentIndex(-1)
            self.user_search_input.clear()

            QMessageBox.information(self, "Successo", "Prelievo aggiunto con successo.")
            
            # Refresh parent list if needed (e.g. to update available quantity)
            parent = self.parent()
            if hasattr(parent, "refresh_materials"):
                await parent.refresh_materials()

        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiungere il prelievo: {e}")
        finally:
            self.add_withdrawal_button.setEnabled(True)

    def save_image(self):
        if not self.image_edit.current_image_path:
            return None
            
        # Check if the image is the same as the existing one
        current_full_path = os.path.abspath(self.image_edit.current_image_path)
        existing_full_path = ""
        if self.material.image_path:
            existing_full_path = os.path.abspath(os.path.join(get_base_path(), self.material.image_path))
            
        if current_full_path == existing_full_path:
            return self.material.image_path

        try:
            images_dir = os.path.join(get_base_path(), "images")
            os.makedirs(images_dir, exist_ok=True)
            
            ext = os.path.splitext(self.image_edit.current_image_path)[1] or ".png"
            filename = f"{uuid.uuid4()}{ext}"
            target_path = os.path.join(images_dir, filename)
            
            image = QImage(self.image_edit.current_image_path)
            max_size = 1024
            if image.width() > max_size or image.height() > max_size:
                image = image.scaled(
                    max_size, max_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            image.save(target_path)
            return os.path.join("images", filename)
            
        except Exception as e:
            print(f"Errore salvataggio immagine: {e}")
            return None

    @asyncSlot()
    async def save_changes(self, *args):
        denomination = self.denomination_input.text().strip()
        if not denomination:
            QMessageBox.warning(self, "Validation Error", "Denomination is required.")
            return

        try:
            image_path = self.save_image()
            
            min_stock = self.material.min_stock
            if self.material.material_type == MaterialType.CONSUMABLE:
                 try:
                     min_stock = int(self.min_stock_edit.text().strip())
                 except ValueError:
                     pass

            updated = await update_material(
                self.material.id,
                denomination=denomination,
                ndc=self.ndc_input.text().strip() or None,
                part_number=self.part_number_input.text().strip() or None,
                serial_number=self.serial_number_input.text().strip() or None,
                code=self.code_input.text().strip() or None,
                image_path=image_path,
                location=self.location_input.text().strip() or None if self.material.material_type == MaterialType.ITEM else None,
                min_stock=min_stock
            )
            self.material.denomination = updated.denomination
            self.material.ndc = updated.ndc
            self.material.part_number = updated.part_number
            self.material.serial_number = updated.serial_number
            self.material.code = updated.code
            self.material.image_path = updated.image_path
            self.material.min_stock = updated.min_stock
            
            parent = self.parent()
            if hasattr(parent, "refresh_materials"):
                await parent.refresh_materials()
            QMessageBox.information(self, "Success", "Material updated successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update material: {str(e)}")

class MaterialItemWidget(QWidget):
    def __init__(self, material: Material, available_qty: int | None = None, status_text: str | None = None):
        super().__init__()
        self.material = material
        self.available_qty = available_qty
        self.status_text = status_text
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Image Thumbnail
        image_label = QLabel()
        image_label.setFixedSize(64, 64)
        image_label.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.material.image_path:
            # Resolve path using get_base_path
            full_path = os.path.join(get_base_path(), self.material.image_path)
            if os.path.exists(full_path):
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        64, 64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    image_label.setPixmap(scaled)
                else:
                    image_label.setText("No Img")
            else:
                image_label.setText("No File")
        else:
            image_label.setText("No Img")
            
        layout.addWidget(image_label)
        
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

        # Row 3: Available Quantity (Consumables) or Status (Items)
        current_row += 1
        
        if self.material.material_type == MaterialType.CONSUMABLE and self.available_qty is not None:
             qty_text = f"Quantità Disponibile: {self.available_qty}"
             style = "color: #00796b; font-weight: bold;"
             
             if hasattr(self.material, 'min_stock') and self.material.min_stock > 0 and self.available_qty <= self.material.min_stock:
                 qty_text += f" (SOTTO SCORTA: {self.material.min_stock})"
                 style = "color: #d32f2f; font-weight: bold;"
                 
             qty_label = QLabel(qty_text)
             qty_label.setStyleSheet(style)
             info_layout.addWidget(qty_label, current_row, 0, 1, 2)
        elif self.status_text:
             status_label = QLabel(self.status_text)
             if "PRELEVATO" in self.status_text:
                 status_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
             elif "DISPONIBILE" in self.status_text:
                 status_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
             elif "NON EFFICIENTE" in self.status_text:
                 status_label.setStyleSheet("color: #f57c00; font-weight: bold;")
             else:
                 status_label.setStyleSheet("font-weight: bold;")
             info_layout.addWidget(status_label, current_row, 0, 1, 2)

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

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh_materials)

    def setup_ui(self):
        type_str = "Attrezzature" if self.material_type == MaterialType.ITEM else "Consumabili"
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
        
        add_btn_text = "Aggiungi Nuova Attrezzatura" if self.material_type == MaterialType.ITEM else "Aggiungi Nuovo Consumabile"
        self.add_btn = QPushButton(add_btn_text)
        self.add_btn.clicked.connect(self.open_add_material_dialog)
        btn_layout.addWidget(self.add_btn)
        
        self.layout.addLayout(btn_layout)

    @asyncSlot()
    async def refresh_materials(self, *args):
        try:
            self.materials = await get_materials(self.material_type)
            active_withdrawals = {}
            consumable_stocks = {}
            if self.material_type == MaterialType.ITEM:
                active_withdrawals = await get_active_item_withdrawals()
            else:
                consumable_stocks = await get_consumable_stocks()
            self.update_list(self.materials, active_withdrawals, consumable_stocks)
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile caricare i materiali: {str(e)}")

    def update_list(self, materials, active_withdrawals=None, consumable_stocks=None):
        if self.material_type == MaterialType.ITEM:
            self.list_efficient.clear()
            self.list_inefficient.clear()
            self.list_withdrawn.clear()
            
            # Ensure active_withdrawals is a dict, default to empty
            active_withdrawals = active_withdrawals or {}
            
            for mat in materials:
                display_text = f"{mat.denomination}"
                if mat.part_number:
                    display_text += f" (PN: {mat.part_number})"
                
                # Build comprehensive search text
                search_text = (
                    f"{mat.denomination or ''} "
                    f"{mat.part_number or ''} "
                    f"{mat.ndc or ''} "
                    f"{mat.code or ''} "
                    f"{mat.serial_number or ''} "
                    f"{str(mat.id)}"
                )

                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, mat.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, display_text)
                item.setData(Qt.ItemDataRole.UserRole + 2, search_text)  # Store full search text
                
                # Determine status text
                status_text = None
                if mat.id in active_withdrawals:
                    withdrawal, user = active_withdrawals[mat.id]
                    user_name = f"{user.first_name} {user.last_name}".strip()
                    status_text = f"PRELEVATO da {user_name}"
                elif not getattr(mat, 'is_efficient', True):
                    status_text = "NON EFFICIENTE"
                else:
                    status_text = "DISPONIBILE"
                
                widget = MaterialItemWidget(mat, status_text=status_text)
                item.setSizeHint(widget.sizeHint())
                
                if mat.id in active_withdrawals:
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
                
                # Build comprehensive search text
                search_text = (
                    f"{mat.denomination or ''} "
                    f"{mat.part_number or ''} "
                    f"{mat.ndc or ''} "
                    f"{mat.code or ''} "
                    f"{mat.serial_number or ''} "
                    f"{str(mat.id)}"
                )

                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, mat.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, display_text)
                item.setData(Qt.ItemDataRole.UserRole + 2, search_text) # Store full search text
                
                stock = consumable_stocks.get(mat.id, 0) if consumable_stocks else 0
                widget = MaterialItemWidget(mat, available_qty=stock)
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
                # Retrieve the full search text stored in UserRole + 2
                filter_text = item.data(Qt.ItemDataRole.UserRole + 2) or ""
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
        dialog.finished.connect(self.refresh_materials)
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
