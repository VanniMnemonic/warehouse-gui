from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox, 
    QMessageBox, QLabel, QFileDialog, QDateEdit, QGroupBox
)
from PyQt6.QtCore import Qt, QSize, QDate
from PyQt6.QtGui import QPixmap, QImage
from qasync import asyncSlot
import os
import uuid
import shutil
from warehouse.utils import get_base_path
from warehouse.models import MaterialType
from warehouse.controllers_material import create_material, create_batch

class ImageDropWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("\n\nTrascina qui l'immagine\no Clicca per Selezionare\n\n")
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 5px;
                color: #555;
            }
            QLabel:hover {
                border-color: #555;
                background-color: #f0f0f0;
            }
        """)
        self.setFixedSize(200, 200)
        self.setAcceptDrops(True)
        self.current_image_path = None
        self.preview_pixmap = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                file_path = urls[0].toLocalFile()
                if self.is_image_file(file_path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            file_path = urls[0].toLocalFile()
            self.load_image(file_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Seleziona Immagine", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
            if file_path:
                self.load_image(file_path)

    def is_image_file(self, path):
        return path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))

    def load_image(self, file_path):
        if self.is_image_file(file_path):
            self.current_image_path = file_path
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.preview_pixmap = pixmap
                scaled_pixmap = pixmap.scaled(
                    self.size(), 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.setPixmap(scaled_pixmap)
            else:
                self.setText("Immagine Non Valida")
                self.current_image_path = None

class MaterialFormDialog(QDialog):
    def __init__(self, material_type: MaterialType, parent=None):
        super().__init__(parent)
        self.material_type = material_type
        type_str = "Attrezzatura" if material_type == MaterialType.ITEM else "Consumabile"
        self.setWindowTitle(f"Aggiungi Nuovo {type_str}")
        self.resize(600, 600)
        
        self.layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        self.form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        
        # Fields
        self.denomination_input = QLineEdit()
        self.ndc_input = QLineEdit()
        self.part_number_input = QLineEdit()
        self.serial_number_input = QLineEdit()
        self.code_input = QLineEdit()
        self.location_input = QLineEdit()
        self.min_stock_input = QLineEdit()
        self.min_stock_input.setText("0")
        self.min_stock_input.setPlaceholderText("Scorta Minima")
        
        # Image Drop Widget
        self.image_widget = ImageDropWidget()
        
        self.form_layout.addRow("Denominazione *:", self.denomination_input)
        self.form_layout.addRow("NDC:", self.ndc_input)
        self.form_layout.addRow("Part Number:", self.part_number_input)
        self.form_layout.addRow("Numero di Serie:", self.serial_number_input)
        self.form_layout.addRow("Codice:", self.code_input)
        
        if self.material_type == MaterialType.CONSUMABLE:
            self.form_layout.addRow("Scorta Minima:", self.min_stock_input)
        
        if self.material_type == MaterialType.ITEM:
            self.form_layout.addRow("Posizione:", self.location_input)
            
        self.form_layout.addRow("Immagine:", self.image_widget)
        
        self.layout.addLayout(self.form_layout)
        
        # Initial Batch for both Consumables and Items
        # (Now that Items also support batches/stock)
        self.initial_batch_group = QGroupBox("Lotto Iniziale (Opzionale)")
        batch_layout = QFormLayout()
        
        self.expiration_input = QDateEdit()
        # Default expiration:
        # Consumable: Today
        # Item: Far future (effectively no expiration)
        if self.material_type == MaterialType.ITEM:
            self.expiration_input.setDate(QDate(2999, 12, 31))
        else:
            self.expiration_input.setDate(QDate.currentDate())
            
        self.expiration_input.setCalendarPopup(True)
        self.expiration_input.setDisplayFormat("yyyy-MM-dd")
        
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("Quantità")
        
        self.batch_location_input = QLineEdit()
        self.batch_location_input.setPlaceholderText("Posizione")
        
        batch_layout.addRow("Scadenza:", self.expiration_input)
        batch_layout.addRow("Quantità:", self.amount_input)
        batch_layout.addRow("Posizione:", self.batch_location_input)
        
        self.initial_batch_group.setLayout(batch_layout)
        self.layout.addWidget(self.initial_batch_group)

        # Buttons
        self.buttons = QDialogButtonBox()
        self.btn_save = self.buttons.addButton("Salva", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_cancel = self.buttons.addButton("Annulla", QDialogButtonBox.ButtonRole.RejectRole)
        
        # Manual connection for async handling
        self.btn_save.clicked.connect(self.accept_data)
        self.buttons.rejected.connect(self.reject)
        
        self.layout.addWidget(self.buttons)
        self.setLayout(self.layout)

    def save_image(self):
        if not self.image_widget.current_image_path:
            return None
        
        try:
            # Create images directory if it doesn't exist
            # Saving in a folder named 'images' relative to the executable/script
            images_dir = os.path.join(get_base_path(), "images")
            os.makedirs(images_dir, exist_ok=True)
            
            # Generate unique filename
            ext = os.path.splitext(self.image_widget.current_image_path)[1]
            if not ext:
                ext = ".png" # Default to png if no extension
            filename = f"{uuid.uuid4()}{ext}"
            target_path = os.path.join(images_dir, filename)
            
            # Save resized image
            # We use the original pixmap loaded in the widget, or reload it
            # Using QImage for saving
            image = QImage(self.image_widget.current_image_path)
            
            # Resize logic: limit max dimension to e.g. 1024
            max_size = 1024
            if image.width() > max_size or image.height() > max_size:
                image = image.scaled(
                    max_size, max_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            image.save(target_path)
            
            # Return relative path for portability
            return os.path.join("images", filename)
            
        except Exception as e:
            print(f"Errore salvataggio immagine: {e}")
            return None

    @asyncSlot()
    async def accept_data(self, *args):
        self.buttons.setEnabled(False)
        
        denomination = self.denomination_input.text().strip()
        
        if not denomination:
            QMessageBox.warning(self, "Errore di Validazione", "La denominazione è obbligatoria.")
            self.buttons.setEnabled(True)
            return

        image_path = self.save_image()

        try:
            min_stock = 0
            if self.material_type == MaterialType.CONSUMABLE:
                 try:
                     min_stock = int(self.min_stock_input.text().strip())
                 except ValueError:
                     min_stock = 0

            material = await create_material(
                material_type=self.material_type,
                denomination=denomination,
                ndc=self.ndc_input.text().strip() or None,
                part_number=self.part_number_input.text().strip() or None,
                serial_number=self.serial_number_input.text().strip() or None,
                code=self.code_input.text().strip() or None,
                image_path=image_path,
                location=self.location_input.text().strip() or None if self.material_type == MaterialType.ITEM else None,
                min_stock=min_stock
            )

            if self.material_type == MaterialType.CONSUMABLE:
                amount_text = self.amount_input.text().strip()
                if amount_text and amount_text.isdigit() and int(amount_text) > 0:
                    try:
                        await create_batch(
                            material_id=material.id,
                            expiration=self.expiration_input.date().toPyDate(),
                            amount=int(amount_text),
                            location=self.batch_location_input.text().strip() or None
                        )
                    except Exception as e:
                        QMessageBox.warning(self, "Attenzione", f"Consumabile creato, ma errore creazione lotto: {e}")

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile creare l'elemento: {e}")
            self.buttons.setEnabled(True)
