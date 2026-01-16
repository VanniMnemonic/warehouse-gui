import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel
)
from PyQt6.QtCore import Qt
from qasync import asyncSlot

from warehouse.models import MaterialType
from warehouse.ui.tabs.users_tab import UsersTab
from warehouse.ui.tabs.materials_tab import MaterialsTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Warehouse Manager")
        self.resize(1000, 700)
        
        container = QWidget()
        self.layout = QVBoxLayout()
        
        self.setup_ui()
        
        container.setLayout(self.layout)
        self.setCentralWidget(container)

    def setup_ui(self):
        # Tabs
        self.tabs = QTabWidget()
        
        # 1. Users Tab
        self.users_tab = UsersTab()
        self.tabs.addTab(self.users_tab, "Users")
        
        # 2. Items Tab
        self.items_tab = MaterialsTab(MaterialType.ITEM)
        self.tabs.addTab(self.items_tab, "Items")
        
        # 3. Consumables Tab
        self.consumables_tab = MaterialsTab(MaterialType.CONSUMABLE)
        self.tabs.addTab(self.consumables_tab, "Consumables")
        
        self.layout.addWidget(self.tabs)
        
        # Status Bar
        self.statusBar().showMessage("Ready")
