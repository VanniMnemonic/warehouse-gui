from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QMessageBox, QDialog, QFormLayout,
    QDialogButtonBox, QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from qasync import asyncSlot
import asyncio

from warehouse.controllers import get_all_users, filter_users, update_user, get_user_withdrawals
from warehouse.models import User
from warehouse.ui.user_form import UserFormDialog


class UserDetailDialog(QDialog):
    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("User Details")
        self.resize(600, 500)

        main_layout = QVBoxLayout()
        self.tabs = QTabWidget()

        # Tab 1: Details
        self.details_tab = QWidget()
        self.setup_details_tab()
        self.tabs.addTab(self.details_tab, "Details")

        # Tab 2: Withdrawals
        self.withdrawals_tab = QWidget()
        self.setup_withdrawals_tab()
        self.tabs.addTab(self.withdrawals_tab, "Withdrawals")

        main_layout.addWidget(self.tabs)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save_changes)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)

        self.setLayout(main_layout)
        
        # Load withdrawals
        self.load_withdrawals()

    def setup_details_tab(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.title_input = QLineEdit(self.user.title or "")
        self.first_name_input = QLineEdit(self.user.first_name)
        self.last_name_input = QLineEdit(self.user.last_name)
        self.custom_id_label = QLabel(self.user.custom_id)
        self.code_input = QLineEdit(self.user.code or "")
        self.workplace_input = QLineEdit(self.user.workplace or "")
        self.mobile_input = QLineEdit(self.user.mobile or "")
        self.email_input = QLineEdit(self.user.email or "")

        self.notes_input = QTextEdit()
        self.notes_input.setPlainText(self.user.notes or "")

        form_layout.addRow("Title:", self.title_input)
        form_layout.addRow("First Name:", self.first_name_input)
        form_layout.addRow("Last Name:", self.last_name_input)
        form_layout.addRow("ID:", self.custom_id_label)
        form_layout.addRow("Code (barcode):", self.code_input)
        form_layout.addRow("Workplace:", self.workplace_input)
        form_layout.addRow("Mobile:", self.mobile_input)
        form_layout.addRow("Email:", self.email_input)
        form_layout.addRow("Notes:", self.notes_input)

        layout.addLayout(form_layout)
        self.details_tab.setLayout(layout)

    def setup_withdrawals_tab(self):
        layout = QVBoxLayout()
        self.withdrawals_table = QTableWidget()
        self.withdrawals_table.setColumnCount(4)
        self.withdrawals_table.setHorizontalHeaderLabels(["Date", "Material", "Amount", "Notes"])
        self.withdrawals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.withdrawals_table)
        self.withdrawals_tab.setLayout(layout)

    @asyncSlot()
    async def load_withdrawals(self):
        try:
            # returns list of (Withdrawal, Material)
            withdrawals_data = await get_user_withdrawals(self.user.id)
            self.withdrawals_table.setRowCount(len(withdrawals_data))
            for i, (withdrawal, material) in enumerate(withdrawals_data):
                date_str = withdrawal.withdrawal_date.strftime("%Y-%m-%d %H:%M")
                material_str = material.denomination
                self.withdrawals_table.setItem(i, 0, QTableWidgetItem(date_str))
                self.withdrawals_table.setItem(i, 1, QTableWidgetItem(material_str))
                self.withdrawals_table.setItem(i, 2, QTableWidgetItem(str(withdrawal.amount)))
                self.withdrawals_table.setItem(i, 3, QTableWidgetItem(withdrawal.notes or ""))
        except Exception as e:
            QMessageBox.warning(self, "Data Load Error", f"Could not load withdrawals: {e}")

    @asyncSlot()
    async def save_changes(self):
        self.buttons.setEnabled(False)

        first_name = self.first_name_input.text().strip()
        last_name = self.last_name_input.text().strip()

        if not first_name or not last_name:
            QMessageBox.warning(self, "Validation Error", "First Name and Last Name are required.")
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
                parent.refresh_users()
            QMessageBox.information(self, "Success", "User updated successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update user: {str(e)}")
            self.buttons.setEnabled(True)


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
        header = QLabel("User Management")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        self.layout.addWidget(header)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search users (Name, ID, Workplace)...")
        self.search_bar.textChanged.connect(self.on_search_changed)
        self.layout.addWidget(self.search_bar)
        
        self.user_list = QListWidget()
        self.user_list.itemDoubleClicked.connect(self.open_user_detail)
        self.layout.addWidget(self.user_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.refresh_users)
        btn_layout.addWidget(self.refresh_btn)
        
        self.add_btn = QPushButton("Add New User")
        self.add_btn.clicked.connect(self.open_add_user_dialog)
        btn_layout.addWidget(self.add_btn)
        
        self.layout.addLayout(btn_layout)

    @asyncSlot()
    async def refresh_users(self):
        try:
            self.users = await get_all_users()
            self.update_list(self.users)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load users: {str(e)}")

    def update_list(self, users):
        self.user_list.clear()
        for user in users:
            display_text = f"[{user.custom_id}] {user.first_name} {user.last_name}"
            if user.workplace:
                display_text += f" - {user.workplace}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, user.id) # Store ID
            self.user_list.addItem(item)

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
