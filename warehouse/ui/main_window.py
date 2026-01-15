import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, 
    QLabel, QHBoxLayout, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
from qasync import asyncSlot

from warehouse.controllers import get_all_users, filter_users, create_user
from warehouse.models import User

from warehouse.ui.user_form import UserFormDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Warehouse Manager")
        self.resize(900, 700)
        
        self.users = []
        
        container = QWidget()
        self.layout = QVBoxLayout()
        
        self.setup_ui()
        
        container.setLayout(self.layout)
        self.setCentralWidget(container)
        
        # Load users
        self.refresh_users()

    def setup_ui(self):
        # Header
        header = QLabel("User Management")
        header.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")
        self.layout.addWidget(header)
        
        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search users (Name, ID, Workplace)...")
        self.search_bar.textChanged.connect(self.on_search_changed)
        self.layout.addWidget(self.search_bar)
        
        # User List
        self.user_list = QListWidget()
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

    def on_search_changed(self, text):
        filtered = filter_users(text, self.users)
        self.update_list(filtered)

    @asyncSlot()
    async def open_add_user_dialog(self):
        dialog = UserFormDialog(self)
        
        # Bridge Qt signal to asyncio Future to await the dialog result non-blockingly
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        def on_finished(result):
            if not future.done():
                future.set_result(result)
                
        dialog.finished.connect(on_finished)
        dialog.open() # Non-blocking modal
        
        result = await future
        if result == QDialog.DialogCode.Accepted.value: # Check against int value
             await self.refresh_users()
             self.search_bar.clear()
             self.statusBar().showMessage("User list updated.", 3000)
