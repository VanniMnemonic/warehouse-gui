from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QMessageBox, QDialog, QFormLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QGridLayout, QScrollArea, QGroupBox
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QPixmap, QImage
from qasync import asyncSlot
import asyncio
import os
import uuid
from warehouse.utils import get_base_path

from warehouse.controllers_material import (
    get_materials, update_material, get_material_batches, get_material_withdrawals,
    create_batch, get_material_dependencies, delete_material, get_consumable_stocks
)
from warehouse.controllers import get_all_users, create_withdrawal, get_active_item_withdrawals
from warehouse.models import MaterialType, Material
from warehouse.ui.material_form import MaterialFormDialog, ImageDropWidget
from warehouse.ui.components import BarcodeSearchComboBox


class MaterialDetailDialog(QDialog):
    def __init__(self, material: Material, parent=None):
        super().__init__(parent)
        self.material = material
        self.users_for_withdrawal = []
        if material.material_type == MaterialType.ITEM:
            title = "Dettagli Attrezzatura"
        else:
            title = "Dettagli Consumabile"
        self.setWindowTitle(title)
        self.resize(700, 800)

        main_layout = QVBoxLayout()
        
        # Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Section 1: Details
        self.details_tab = QWidget()
        self.setup_details_section()
        self.tabs.addTab(self.details_tab, "Dettagli")
        
        # Section 2: Edit (Modifica)
        self.edit_tab = QWidget()
        self.setup_edit_section()
        self.tabs.addTab(self.edit_tab, "Modifica")

        # Section 3: Batches
        if self.material.material_type == MaterialType.CONSUMABLE:
            self.batches_tab = QWidget()
            self.setup_batches_section()
            self.tabs.addTab(self.batches_tab, "Aggiungi Lotto")

        # Section 4: Withdrawals
        self.withdrawals_tab = QWidget()
        self.setup_withdrawals_section()
        self.tabs.addTab(self.withdrawals_tab, "Aggiungi Prelievo")

        # Action Buttons Layout (at the bottom)
        bottom_layout = QVBoxLayout()
        
        self.is_withdrawn = False
        if self.material.material_type == MaterialType.ITEM:
            self.actions_layout = QHBoxLayout()
            
            self.toggle_efficiency_btn = QPushButton()
            self.toggle_efficiency_btn.clicked.connect(self.toggle_efficiency)
            self.actions_layout.addWidget(self.toggle_efficiency_btn)
            
            bottom_layout.addLayout(self.actions_layout)
            self.update_action_buttons()

        # Close Button
        close_btn = QPushButton("Chiudi")
        close_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(close_btn)
        
        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

        self.load_related_data()
        self.load_users_for_withdrawal()

    def setup_details_section(self):
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content = QWidget()
        form_layout = QFormLayout(content)
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Helper to add row
        def add_row(label, value):
            lbl_val = QLabel(str(value) if value else "-")
            lbl_val.setWordWrap(True)
            lbl_val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form_layout.addRow(f"{label}:", lbl_val)
            return lbl_val

        add_row("ID", self.material.id)
        add_row("Tipo", self.material.material_type.value)
        add_row("Denominazione", self.material.denomination)
        add_row("NDC", self.material.ndc)
        add_row("Part Number", self.material.part_number)
        add_row("Numero di Serie", self.material.serial_number)
        add_row("Codice", self.material.code)
        
        if self.material.material_type == MaterialType.CONSUMABLE:
             add_row("Scorta Minima", str(self.material.min_stock))
        
        if self.material.material_type == MaterialType.ITEM:
            self.location_label = add_row("Posizione", "-")
            
        # Image Field
        image_view = QLabel()
        image_view.setFixedSize(300, 300)
        image_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_view.setStyleSheet("border: 1px solid #ddd; background-color: #f9f9f9; border-radius: 8px;")
        
        if self.material.image_path:
            full_path = os.path.join(get_base_path(), self.material.image_path)
            if os.path.exists(full_path):
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        300, 300,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    image_view.setPixmap(scaled)
                else:
                    image_view.setText("Immagine non valida")
            else:
                image_view.setText("File non trovato")
        else:
            image_view.setText("Nessuna immagine")

        form_layout.addRow("Immagine:", image_view)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.details_tab.setLayout(layout)

    def setup_edit_section(self):
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content = QWidget()
        form_layout = QFormLayout(content)
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self.denomination_input = QLineEdit(self.material.denomination)
        self.ndc_input = QLineEdit(self.material.ndc or "")
        self.part_number_input = QLineEdit(self.material.part_number or "")
        self.serial_number_input = QLineEdit(self.material.serial_number or "")
        self.code_input = QLineEdit(self.material.code or "")
        
        form_layout.addRow("Denominazione:", self.denomination_input)
        form_layout.addRow("NDC:", self.ndc_input)
        form_layout.addRow("Part Number:", self.part_number_input)
        form_layout.addRow("Numero di Serie:", self.serial_number_input)
        form_layout.addRow("Codice:", self.code_input)
        
        if self.material.material_type == MaterialType.CONSUMABLE:
             self.min_stock_edit = QLineEdit(str(self.material.min_stock))
             form_layout.addRow("Scorta Minima:", self.min_stock_edit)
        
        if self.material.material_type == MaterialType.ITEM:
            self.location_input = QLineEdit("")
            form_layout.addRow("Posizione:", self.location_input)
            
        self.image_edit = ImageDropWidget()
        if self.material.image_path:
             full_path = os.path.join(get_base_path(), self.material.image_path)
             if os.path.exists(full_path):
                 self.image_edit.load_image(full_path)
        
        form_layout.addRow("Immagine:", self.image_edit)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Buttons for Edit Tab
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("Salva Modifiche")
        save_btn.clicked.connect(self.save_changes)
        buttons_layout.addWidget(save_btn)
        
        delete_btn = QPushButton("Elimina Attrezzatura" if self.material.material_type == MaterialType.ITEM else "Elimina Consumabile")
        delete_btn.setStyleSheet("background-color: #d32f2f; color: white;")
        delete_btn.clicked.connect(self.delete_material_action)
        buttons_layout.addWidget(delete_btn)
        
        layout.addLayout(buttons_layout)
        self.edit_tab.setLayout(layout)

    @asyncSlot()
    async def delete_material_action(self):
        try:
            batch_count, withdrawal_count = await get_material_dependencies(self.material.id)
            
            item_type_str = "questa attrezzatura" if self.material.material_type == MaterialType.ITEM else "questo consumabile"
            msg = f"Sei sicuro di voler eliminare {item_type_str}: {self.material.denomination}?"
            
            dependencies_msg = []
            if batch_count > 0:
                dependencies_msg.append(f"{batch_count} lotti")
            if withdrawal_count > 0:
                dependencies_msg.append(f"{withdrawal_count} prelievi")
                
            if dependencies_msg:
                msg += f"\n\nATTENZIONE: Eliminando {item_type_str} verranno eliminati anche:\n- " + "\n- ".join(dependencies_msg)
            else:
                msg += "\n\nNessun dato correlato verrà eliminato."
                
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

    def setup_batches_section(self):
        if self.material.material_type == MaterialType.ITEM:
            return
            
        layout = QVBoxLayout()
        
        # Existing Batches Table
        table_label = QLabel("Lotti Esistenti")
        table_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(table_label)
        
        self.batches_table = QTableWidget()
        self.batches_table.setMinimumHeight(150)
        self.batches_table.setColumnCount(4)
        self.batches_table.setHorizontalHeaderLabels(["ID", "Scadenza", "Quantità", "Posizione"])
        self.batches_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.batches_table)

        # Add New Batch Form
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
        layout.addWidget(form_group)
        
        self.add_batch_button = QPushButton("Aggiungi Lotto")
        self.add_batch_button.clicked.connect(self.add_batch)
        layout.addWidget(self.add_batch_button)
        
        layout.addStretch()
        self.batches_tab.setLayout(layout)

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
        layout = QVBoxLayout()
        
        # Existing Withdrawals Table
        table_label = QLabel("Storico Prelievi")
        table_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(table_label)
        
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

        # Add New Withdrawal Form
        form_group = QGroupBox("Nuovo Prelievo")
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
        self.search_check_label.setStyleSheet("color: green; font-weight: bold; font-size: 16px;")
        self.search_check_label.hide()
        search_layout.addWidget(self.search_check_label)

        form_layout.addRow("Cerca:", search_layout)
        self.new_withdrawal_amount_input = QLineEdit()
        self.new_withdrawal_notes_input = QLineEdit()

        form_layout.addRow("Utente:", self.new_withdrawal_user_combo)
        form_layout.addRow("Quantità:", self.new_withdrawal_amount_input)
        form_layout.addRow("Note:", self.new_withdrawal_notes_input)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        self.add_withdrawal_button = QPushButton("Aggiungi Prelievo")
        self.add_withdrawal_button.clicked.connect(self.add_material_withdrawal)
        layout.addWidget(self.add_withdrawal_button)
        
        layout.addStretch()
        self.withdrawals_tab.setLayout(layout)

    def update_action_buttons(self):
        if self.material.material_type != MaterialType.ITEM:
            return
            
        if self.material.is_efficient:
            self.toggle_efficiency_btn.setText("Segnala come Non Efficiente")
        else:
            self.toggle_efficiency_btn.setText("Segnala come Efficiente")
            
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
                
            QMessageBox.information(self, "Successo", f"Attrezzatura segnata come {'Efficiente' if new_status else 'Non Efficiente'}.")
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
