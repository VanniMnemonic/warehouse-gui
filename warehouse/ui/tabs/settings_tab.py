from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, 
    QMessageBox, QFileDialog, QGroupBox, QApplication, QStyleFactory,
    QHBoxLayout
)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt, pyqtSignal
from qasync import asyncSlot
import shutil
import os
from datetime import datetime
from warehouse.database import engine, init_db, DATABASE_URL
from warehouse.models import SQLModel
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
        
        # Set current selection (default is Fusion)
        index = self.theme_combo.findText("Fusion")
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
            
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
        app = QApplication.instance()
        if theme_name == "Fusion Dark":
            app.setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            app.setPalette(palette)
        else:
            app.setStyle(theme_name)
            # Reset palette to standard
            app.setPalette(app.style().standardPalette())

    def export_db(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Esporta Database", "warehouse_backup.db", "SQLite Database (*.db *.sqlite)"
        )
        if file_path:
            try:
                # DATABASE_URL is "sqlite+aiosqlite:///warehouse.db"
                # We need the local file path.
                db_file = os.path.join(get_base_path(), "warehouse.db")
                shutil.copy2(db_file, file_path)
                QMessageBox.information(self, "Successo", "Database esportato con successo.")
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile esportare il database: {e}")

    @asyncSlot()
    async def import_db(self):
        confirm = QMessageBox.warning(
            self,
            "Conferma Importazione",
            "L'importazione sovrascriverà il database attuale. Tutti i dati correnti andranno persi.\nContinuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Importa Database", "", "SQLite Database (*.db *.sqlite)"
        )
        
        if file_path:
            try:
                # We need to close the engine connection properly before overwriting the file
                await engine.dispose()
                
                db_file = os.path.join(get_base_path(), "warehouse.db")
                # Use shutil to copy
                shutil.copy2(file_path, db_file)
                
                # Re-initialize DB (create engine/metadata if needed, though file exists)
                # Actually engine is global, but disposed. It will reconnect on next use.
                
                QMessageBox.information(self, "Successo", "Database importato con successo.")
                self.db_changed.emit()
                
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile importare il database: {e}")

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
