from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, 
    QMessageBox, QFileDialog, QGroupBox, QApplication, QStyleFactory,
    QHBoxLayout
)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from qasync import asyncSlot
import shutil
import os
import zipfile
import tempfile
from datetime import datetime
from warehouse.database import engine, init_db, DATABASE_URL
from warehouse.models import SQLModel
from warehouse.utils import get_base_path
from warehouse.ui.theme import apply_theme
from sqlalchemy import text

class SettingsTab(QWidget):
    db_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 1. Theme Selection
        theme_group = QGroupBox("Aspetto")
        theme_layout = QVBoxLayout()
        
        theme_layout.addWidget(QLabel("Tema dell'applicazione:"))
        
        self.theme_combo = QComboBox()
        # Get available styles
        styles = QStyleFactory.keys()
        self.theme_combo.addItems(styles)
        self.theme_combo.addItem("Fusion Dark")
        
        # Load saved theme
        settings = QSettings("WarehouseApp", "WarehouseGUI")
        saved_theme = settings.value("theme", "Fusion Dark")
        
        # Set current selection
        index = self.theme_combo.findText(saved_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
            # Apply the theme immediately
            self.change_theme(saved_theme)
        else:
            # Fallback if saved theme not found
            index = self.theme_combo.findText("Fusion Dark")
            if index >= 0:
                self.theme_combo.setCurrentIndex(index)
                self.change_theme("Fusion Dark")
            
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_combo)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # 2. Database Management
        db_group = QGroupBox("Gestione Database")
        db_layout = QVBoxLayout()
        
        # Export
        btn_export = QPushButton("Esporta Database")
        btn_export.clicked.connect(self.export_db)
        db_layout.addWidget(btn_export)
        
        # Import
        btn_import = QPushButton("Importa Database")
        btn_import.clicked.connect(self.import_db)
        db_layout.addWidget(btn_import)
        
        # Reset
        btn_reset = QPushButton("Reset Database")
        btn_reset.setStyleSheet("background-color: #ffcccc; color: red; font-weight: bold;")
        btn_reset.clicked.connect(self.reset_db)
        db_layout.addWidget(btn_reset)
        
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)
        
        self.setLayout(layout)

    def change_theme(self, theme_name):
        # Save preference
        settings = QSettings("WarehouseApp", "WarehouseGUI")
        settings.setValue("theme", theme_name)
        
        # Apply theme
        apply_theme(theme_name)

    def export_db(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Esporta Backup Completo", "warehouse_backup.zip", "ZIP Archive (*.zip);;SQLite Database (*.db *.sqlite)"
        )
        if not file_path:
            return

        try:
            base_path = get_base_path()
            db_file = os.path.join(base_path, "warehouse.db")
            images_dir = os.path.join(base_path, "images")

            if file_path.endswith('.zip'):
                # Create ZIP directly from source files
                with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add DB
                    if os.path.exists(db_file):
                        zipf.write(db_file, "warehouse.db")
                    
                    # Add Images
                    if os.path.exists(images_dir):
                        for root, dirs, files in os.walk(images_dir):
                            for file in files:
                                abs_path = os.path.join(root, file)
                                rel_path = os.path.relpath(abs_path, base_path)
                                zipf.write(abs_path, rel_path)
                                    
                QMessageBox.information(self, "Successo", "Backup completo (DB + Immagini) esportato con successo.")
            else:
                # Legacy DB only export
                shutil.copy2(db_file, file_path)
                QMessageBox.information(self, "Successo", "Database (solo file) esportato con successo.")
                
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile esportare il backup: {e}")

    @asyncSlot()
    async def import_db(self):
        confirm = QMessageBox.warning(
            self,
            "Conferma Importazione",
            "L'importazione sovrascriverà i dati attuali (Database e Immagini).\nTutto il contenuto corrente andrà perso.\nContinuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Importa Backup", "", "Backup Files (*.zip *.db *.sqlite)"
        )
        
        if not file_path:
            return

        try:
            # We need to close the engine connection properly before overwriting the file
            await engine.dispose()
            
            base_path = get_base_path()
            db_file = os.path.join(base_path, "warehouse.db")
            images_dir = os.path.join(base_path, "images")

            if file_path.endswith('.zip'):
                # Extract ZIP
                with tempfile.TemporaryDirectory() as temp_dir:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    
                    # Check for DB file in extracted root
                    extracted_db = os.path.join(temp_dir, "warehouse.db")
                    if not os.path.exists(extracted_db):
                        raise FileNotFoundError("Il file 'warehouse.db' non è presente nell'archivio.")
                    
                    # Replace DB
                    shutil.copy2(extracted_db, db_file)
                    
                    # Replace Images
                    extracted_images = os.path.join(temp_dir, "images")
                    if os.path.exists(extracted_images):
                        if os.path.exists(images_dir):
                            shutil.rmtree(images_dir)
                        shutil.copytree(extracted_images, images_dir)
                    else:
                        # If zip has no images folder, should we clear local images?
                        # Yes, to match backup state.
                        if os.path.exists(images_dir):
                            shutil.rmtree(images_dir)
            else:
                # Legacy DB file import
                shutil.copy2(file_path, db_file)
                # Note: Legacy import doesn't touch images, preserving them (or leaving them orphaned)
            
            # Re-initialize DB (create engine/metadata if needed, though file exists)
            # Actually engine is global, but disposed. It will reconnect on next use.
            
            QMessageBox.information(self, "Successo", "Backup importato con successo.")
            self.db_changed.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile importare il backup: {e}")

    @asyncSlot()
    async def reset_db(self):
        confirm = QMessageBox.question(
            self,
            "Conferma Reset",
            "Sei sicuro di voler resettare il database? Tutti i dati andranno persi irreversibilmente.\nUna copia di backup verrà creata automaticamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Dispose engine to release locks
            await engine.dispose()

            db_file = os.path.join(get_base_path(), "warehouse.db")
            # Auto-export backup before reset
            if os.path.exists(db_file):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = os.path.join(get_base_path(), f"warehouse_backup_RESET_{timestamp}.db")
                shutil.copy2(db_file, backup_filename)
            else:
                backup_filename = "Nessun backup creato (DB non trovato)"
            
            # Re-create engine or just use existing one to drop/create
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.drop_all)
                await conn.run_sync(SQLModel.metadata.create_all)
            
            QMessageBox.information(self, "Successo", f"Database resettato con successo.\nBackup: {os.path.basename(backup_filename)}")
            self.db_changed.emit()
        
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile resettare il database: {e}")
