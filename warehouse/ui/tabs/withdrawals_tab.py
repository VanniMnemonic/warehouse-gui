from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QLabel, QHBoxLayout, QDialog, QDialogButtonBox,
    QRadioButton, QButtonGroup, QFrame, QGridLayout
)
from PyQt6.QtGui import QColor, QPalette, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal
from qasync import asyncSlot
import asyncio
import os
from warehouse.controllers import get_all_withdrawals, return_withdrawal_item
from warehouse.models import MaterialType, Withdrawal, User, Material
from warehouse.utils import get_base_path

class WithdrawalItemWidget(QWidget):
    return_requested = pyqtSignal(int)

    def __init__(self, withdrawal: Withdrawal, user: User, material: Material):
        super().__init__()
        self.withdrawal = withdrawal
        self.user = user
        self.material = material
        self.setup_ui()

    def on_return_click(self, *args):
        print(f"DEBUG: Button clicked for withdrawal {self.withdrawal.id}, args: {args}")
        self.return_requested.emit(self.withdrawal.id)

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        image_label = QLabel()
        image_label.setFixedSize(64, 64)
        image_label.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if self.material.image_path:
            full_path = os.path.join(get_base_path(), self.material.image_path)
            if os.path.exists(full_path):
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        64,
                        64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
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
        
        # Material Name (Bold)
        mat_name = self.material.denomination
        if self.material.code:
            mat_name += f" ({self.material.code})"
        lbl_material = QLabel(mat_name)
        lbl_material.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(lbl_material, 0, 0, 1, 2)
        
        # User and Date
        user_str = f"Utente: {self.user.first_name} {self.user.last_name}"
        date_str = self.withdrawal.withdrawal_date.strftime("%Y-%m-%d %H:%M")
        info_layout.addWidget(QLabel(user_str), 1, 0)
        info_layout.addWidget(QLabel(date_str), 1, 1)
        
        # Amount and Notes
        amount_str = f"Quantità: {self.withdrawal.amount}"
        info_layout.addWidget(QLabel(amount_str), 2, 0)
        
        if self.withdrawal.notes:
            notes_lbl = QLabel(f"Note: {self.withdrawal.notes}")
            notes_lbl.setStyleSheet("color: gray; font-style: italic;")
            info_layout.addWidget(notes_lbl, 2, 1)
            
        layout.addLayout(info_layout, stretch=1)
        
        # Status / Action Section
        status_layout = QVBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        is_returnable = self.material.material_type == MaterialType.ITEM
        
        if is_returnable:
            if self.withdrawal.return_date:
                # Returned
                status_text = f"Restituito il:\n{self.withdrawal.return_date.strftime('%Y-%m-%d')}"
                lbl_status = QLabel(status_text)
                lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight)
                status_layout.addWidget(lbl_status)
                
                eff_text = "Efficiente" if self.withdrawal.efficient_at_return else "Inefficiente"
                lbl_eff = QLabel(eff_text)
                lbl_eff.setStyleSheet(f"color: {'green' if self.withdrawal.efficient_at_return else 'red'}; font-weight: bold;")
                lbl_eff.setAlignment(Qt.AlignmentFlag.AlignRight)
                status_layout.addWidget(lbl_eff)
            else:
                # Pending Return
                btn_return = QPushButton("Restituisci")
                btn_return.setFixedWidth(100)
                btn_return.clicked.connect(self.on_return_click)
                status_layout.addWidget(btn_return)
                
                # Apply background color for pending
                self.setAutoFillBackground(True)
                palette = self.palette()
                palette.setColor(QPalette.ColorRole.Window, QColor(255, 235, 235)) # Light Red
                self.setPalette(palette)
        else:
            # Consumable
            lbl_status = QLabel("Consumabile")
            lbl_status.setStyleSheet("color: gray;")
            status_layout.addWidget(lbl_status)
            
        layout.addLayout(status_layout)
        
        self.setLayout(layout)
        
        # Add a bottom border
        self.setStyleSheet(self.styleSheet() + """
            WithdrawalItemWidget {
                border-bottom: 1px solid #ddd;
            }
        """)

class ReturnDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restituisci Oggetto")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("L'oggetto è efficiente (funzionante) alla restituzione?"))
        
        self.efficient_group = QButtonGroup(self)
        self.yes_radio = QRadioButton("Sì, efficiente")
        self.no_radio = QRadioButton("No, danneggiato/inefficiente")
        self.yes_radio.setChecked(True)
        
        self.efficient_group.addButton(self.yes_radio)
        self.efficient_group.addButton(self.no_radio)
        
        layout.addWidget(self.yes_radio)
        layout.addWidget(self.no_radio)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        
    def is_efficient(self):
        return self.yes_radio.isChecked()

class WithdrawalsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setup_ui()
        self.setLayout(self.layout)
        self.withdrawals_data = [] # List of tuples (Withdrawal, User, Material)

    def setup_ui(self):
        # Header
        header_layout = QHBoxLayout()
        header = QLabel("Cronologia Prelievi")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        header_layout.addWidget(header)
        
        self.refresh_btn = QPushButton("Aggiorna")
        self.refresh_btn.clicked.connect(self.refresh_withdrawals)
        header_layout.addWidget(self.refresh_btn)
        
        self.layout.addLayout(header_layout)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(2)
        self.layout.addWidget(self.list_widget)
        
        # Initial load
        self.refresh_withdrawals()

    @asyncSlot()
    async def refresh_withdrawals(self, *args):
        try:
            data = await get_all_withdrawals()
            
            # Sort: Pending returns first, then by date desc
            def sort_key(row):
                withdrawal, _, material = row
                is_pending = (material.material_type == MaterialType.ITEM and withdrawal.return_date is None)
                return (is_pending, withdrawal.withdrawal_date)
            
            # Convert to list if it's not already (SQLAlchemy result usually is, but good to be safe for sorting)
            data = list(data)
            data.sort(key=sort_key, reverse=True)
            
            self.withdrawals_data = data
            self.update_list(data)
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile caricare i prelievi: {e}")

    def update_list(self, data):
        self.list_widget.clear()
        
        for withdrawal, user, material in data:
            item = QListWidgetItem(self.list_widget)
            # Size hint will be adjusted by the widget, but setting a default height helps
            item.setSizeHint(item.sizeHint()) 
            
            widget = WithdrawalItemWidget(withdrawal, user, material)
            widget.return_requested.connect(self.on_return_signal)
            
            # Adjust item size to widget size
            item.setSizeHint(widget.sizeHint())
            
            self.list_widget.setItemWidget(item, widget)

    def on_return_signal(self, withdrawal_id):
        """Wrapper sincrono per avviare il task asincrono manualmente, aggirando problemi di firma di qasync."""
        asyncio.create_task(self.handle_return(withdrawal_id))

    async def handle_return(self, withdrawal_id):
        print(f"DEBUG: handle_return called with id: {withdrawal_id}")
        dialog = ReturnDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            efficient = dialog.is_efficient()
            try:
                await return_withdrawal_item(withdrawal_id, efficient)
                QMessageBox.information(self, "Successo", "Oggetto restituito con successo.")
                await self.refresh_withdrawals()
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile restituire l'oggetto: {e}")
