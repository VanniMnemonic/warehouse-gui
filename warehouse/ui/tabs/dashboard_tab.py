from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QLabel, QGroupBox, QMessageBox, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor, QPalette, QPixmap
from qasync import asyncSlot
from datetime import date, timedelta
import os
from warehouse.utils import get_base_path
from warehouse.controllers_material import get_expiring_batches, get_inefficient_materials, get_consumable_stocks
from warehouse.controllers import get_active_item_withdrawals
from warehouse.models import Batch, Material

class ExpiringBatchItemWidget(QWidget):
    def __init__(self, batch: Batch, material: Material, available_qty: int | None = None):
        super().__init__()
        self.batch = batch
        self.material = material
        self.available_qty = available_qty
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Image Thumbnail
        image_label = QLabel()
        image_label.setFixedSize(48, 48)
        image_label.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.material.image_path:
            full_path = os.path.join(get_base_path(), self.material.image_path)
            if os.path.exists(full_path):
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        48, 48,
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
        
        # Details Layout
        details_layout = QGridLayout()
        details_layout.setVerticalSpacing(2)
        
        # Material Name
        lbl_name = QLabel(self.material.denomination)
        lbl_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        details_layout.addWidget(lbl_name, 0, 0, 1, 2)
        
        # Expiration
        days_left = (self.batch.expiration - date.today()).days
        exp_str = f"Scadenza: {self.batch.expiration} ({days_left} giorni)"
        lbl_exp = QLabel(exp_str)
        if days_left < 0:
            lbl_exp.setStyleSheet("color: red; font-weight: bold;")
        elif days_left < 30:
            lbl_exp.setStyleSheet("color: orange; font-weight: bold;")
        details_layout.addWidget(lbl_exp, 1, 0)
        
        # Amount
        details_layout.addWidget(QLabel(f"Quantità Lotto: {self.batch.amount}"), 1, 1)

        # Available Quantity
        if self.available_qty is not None:
             qty_label = QLabel(f"Totale Disponibile: {self.available_qty}")
             qty_label.setStyleSheet("color: #00796b; font-weight: bold;")
             details_layout.addWidget(qty_label, 2, 1)

        # Location
        loc = self.batch.location or "N/A"
        details_layout.addWidget(QLabel(f"Posizione: {loc}"), 2, 0)
        
        layout.addLayout(details_layout)
        self.setLayout(layout)

class InefficientMaterialItemWidget(QWidget):
    def __init__(self, material: Material, withdrawal_info: str | None = None):
        super().__init__()
        self.material = material
        self.withdrawal_info = withdrawal_info
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Image Thumbnail
        image_label = QLabel()
        image_label.setFixedSize(48, 48)
        image_label.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.material.image_path:
            full_path = os.path.join(get_base_path(), self.material.image_path)
            if os.path.exists(full_path):
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        48, 48,
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
        
        # Details Layout
        details_layout = QGridLayout()
        details_layout.setVerticalSpacing(2)
        
        # Name
        lbl_name = QLabel(f"{self.material.denomination} (ID: {self.material.id})")
        lbl_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #d32f2f;") # Red title for inefficient
        details_layout.addWidget(lbl_name, 0, 0, 1, 2)
        
        # Codes
        details = []
        if self.material.part_number:
            details.append(f"P/N: {self.material.part_number}")
        if self.material.serial_number:
            details.append(f"S/N: {self.material.serial_number}")
        
        details_layout.addWidget(QLabel(" | ".join(details)), 1, 0, 1, 2)
        
        if self.withdrawal_info:
            w_label = QLabel(self.withdrawal_info)
            w_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
            details_layout.addWidget(w_label, 2, 0, 1, 2)

        layout.addLayout(details_layout)
        self.setLayout(layout)

class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        QTimer.singleShot(0, self.refresh_data)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh_data)

    def setup_ui(self):
        main_layout = QHBoxLayout()
        
        # Section 1: Expiring Batches
        expiring_group = QGroupBox("Lotti in Scadenza Prossima (Consumabili)")
        expiring_layout = QVBoxLayout()
        self.expiring_list = QListWidget()
        self.expiring_list.setSpacing(2)
        expiring_layout.addWidget(self.expiring_list)
        expiring_group.setLayout(expiring_layout)
        
        # Section 2: Inefficient Items
        inefficient_group = QGroupBox("Oggetti Non Efficienti (Danneggiati)")
        inefficient_layout = QVBoxLayout()
        self.inefficient_list = QListWidget()
        self.inefficient_list.setSpacing(2)
        inefficient_layout.addWidget(self.inefficient_list)
        inefficient_group.setLayout(inefficient_layout)
        
        main_layout.addWidget(expiring_group)
        main_layout.addWidget(inefficient_group)
        
        self.setLayout(main_layout)

    @asyncSlot()
    async def refresh_data(self, *args):
        try:
            # Load Data
            consumable_stocks = await get_consumable_stocks()
            active_withdrawals = await get_active_item_withdrawals()
            
            # Load Expiring Batches
            self.expiring_list.clear()
            batches_data = await get_expiring_batches(limit=50)
            for batch, material in batches_data:
                item = QListWidgetItem(self.expiring_list)
                available = consumable_stocks.get(material.id, 0)
                widget = ExpiringBatchItemWidget(batch, material, available_qty=available)
                item.setSizeHint(widget.sizeHint())
                self.expiring_list.setItemWidget(item, widget)

            # Load Inefficient Items
            self.inefficient_list.clear()
            inefficient_items = await get_inefficient_materials()
            for material in inefficient_items:
                item = QListWidgetItem(self.inefficient_list)
                
                withdrawal_info = None
                if material.id in active_withdrawals:
                    withdrawal, user = active_withdrawals[material.id]
                    withdrawal_info = f"PRELEVATO da {user.first_name} {user.last_name}"
                
                widget = InefficientMaterialItemWidget(material, withdrawal_info=withdrawal_info)
                item.setSizeHint(widget.sizeHint())
                self.inefficient_list.setItemWidget(item, widget)
                
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile aggiornare la dashboard: {e}")
