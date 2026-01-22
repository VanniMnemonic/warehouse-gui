from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox, 
    QMessageBox, QLabel, QFileDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QImage
from qasync import asyncSlot
import os
import uuid
from warehouse.models import MaterialType
from warehouse.controllers_material import create_material

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
        type_str = "Oggetto" if material_type == MaterialType.ITEM else "Consumabile"
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
        
        # Image Drop Widget
        self.image_widget = ImageDropWidget()
        
        self.form_layout.addRow("Denominazione *:", self.denomination_input)
        self.form_layout.addRow("NDC:", self.ndc_input)
        self.form_layout.addRow("Part Number:", self.part_number_input)
        self.form_layout.addRow("Numero di Serie:", self.serial_number_input)
        self.form_layout.addRow("Codice:", self.code_input)
        
        if self.material_type == MaterialType.ITEM:
            self.form_layout.addRow("Posizione:", self.location_input)
            
        self.form_layout.addRow("Immagine:", self.image_widget)
        
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

    def save_image(self):
        if not self.image_widget.current_image_path:
            return None
        
        try:
            # Create images directory if it doesn't exist
            # Saving in a folder named 'images' in the current working directory
            images_dir = os.path.join(os.getcwd(), "images")
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
            material = await create_material(
                material_type=self.material_type,
                denomination=denomination,
                ndc=self.ndc_input.text().strip() or None,
                part_number=self.part_number_input.text().strip() or None,
                serial_number=self.serial_number_input.text().strip() or None,
                code=self.code_input.text().strip() or None,
                image_path=image_path,
                location=self.location_input.text().strip() or None if self.material_type == MaterialType.ITEM else None
            )
            type_msg = "Oggetto" if self.material_type == MaterialType.ITEM else "Consumabile"
            QMessageBox.information(self, "Successo", f"{type_msg} creato con successo!")
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile creare il materiale: {str(e)}")
            self.buttons.setEnabled(True)
