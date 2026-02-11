from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox, 
    QMessageBox, QTextEdit
)
from qasync import asyncSlot
from warehouse.controllers import create_user

class UserFormDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aggiungi Nuovo Utente")
        self.resize(600, 500)
        
        self.layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        self.form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        
        # Fields
        self.title_input = QLineEdit()
        self.first_name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.workplace_input = QLineEdit()
        self.mobile_input = QLineEdit()
        self.email_input = QLineEdit()
        self.code_input = QLineEdit()
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(100)
        
        self.form_layout.addRow("Titolo:", self.title_input)
        self.form_layout.addRow("Nome *:", self.first_name_input)
        self.form_layout.addRow("Cognome *:", self.last_name_input)
        self.form_layout.addRow("Luogo di lavoro:", self.workplace_input)
        self.form_layout.addRow("Cellulare:", self.mobile_input)
        self.form_layout.addRow("Email:", self.email_input)
        self.form_layout.addRow("Codice (barcode):", self.code_input)
        self.form_layout.addRow("Note:", self.notes_input)
        
        self.layout.addLayout(self.form_layout)
        
        # Buttons
        self.buttons = QDialogButtonBox()
        self.btn_save = self.buttons.addButton("Salva", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_cancel = self.buttons.addButton("Annulla", QDialogButtonBox.ButtonRole.RejectRole)
        
        # Disconnect default signal to prevent auto-close on Enter for Save
        # We manually handle accepted via our async slot
        self.btn_save.clicked.connect(self.accept_data)
        self.buttons.rejected.connect(self.reject)
        
        self.layout.addWidget(self.buttons)
        self.setLayout(self.layout)

    @asyncSlot()
    async def accept_data(self, *args):
        # Disable buttons to prevent double submission
        self.buttons.setEnabled(False)
        
        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()
        
        if not first_name or not last_name:
            QMessageBox.warning(self, "Errore Validazione", "Nome e Cognome sono obbligatori.")
            self.buttons.setEnabled(True)
            return

        try:
            user = await create_user(
                first_name=first_name,
                last_name=last_name,
                title=self.title_input.text().strip() or None,
                workplace=self.workplace_input.text().strip() or None,
                mobile=self.mobile_input.text().strip() or None,
                email=self.email_input.text().strip() or None,
                code=self.code_input.text().strip() or None,
                notes=self.notes_input.toPlainText().strip() or None
            )
            QMessageBox.information(self, "Success", f"User created successfully!\nID: {user.custom_id}")
            # Use accept() from QDialog, but since we are in async slot, we need to be careful.
            # However, since we disconnected the button from the dialog's accept slot,
            # calling super().accept() here is the correct way to close it with Accepted result.
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create user: {str(e)}")
            self.buttons.setEnabled(True)
