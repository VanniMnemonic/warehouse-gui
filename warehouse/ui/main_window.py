import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel, QHBoxLayout, 
    QComboBox, QApplication, QStyleFactory
)
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt
from qasync import asyncSlot

from warehouse.models import MaterialType
from warehouse.ui.tabs.users_tab import UsersTab
from warehouse.ui.tabs.materials_tab import MaterialsTab
from warehouse.ui.tabs.withdrawals_tab import WithdrawalsTab
from warehouse.ui.tabs.dashboard_tab import DashboardTab
from warehouse.ui.tabs.settings_tab import SettingsTab

class MainWindow(QMainWindow):
    def __init__(self, stop_event=None):
        super().__init__()
        self.stop_event = stop_event
        self.setWindowTitle("Gestore Magazzino")
        self.resize(1200, 800)
        
        # Set default theme
        QApplication.setStyle("Fusion")
        
        container = QWidget()
        self.layout = QVBoxLayout()
        
        self.setup_ui()
        
        container.setLayout(self.layout)
        self.setCentralWidget(container)

    def setup_ui(self):
        # Tabs
        self.tabs = QTabWidget()
        
        # 0. Dashboard Tab (New)
        self.dashboard_tab = DashboardTab()
        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        
        # 1. Users Tab
        self.users_tab = UsersTab()
        self.tabs.addTab(self.users_tab, "Utenti")
        
        # 2. Items Tab
        self.items_tab = MaterialsTab(MaterialType.ITEM)
        self.tabs.addTab(self.items_tab, "Oggetti")
        
        # 3. Consumables Tab
        self.consumables_tab = MaterialsTab(MaterialType.CONSUMABLE)
        self.tabs.addTab(self.consumables_tab, "Consumabili")
        
        # 4. Withdrawals Tab
        self.withdrawals_tab = WithdrawalsTab()
        self.tabs.addTab(self.withdrawals_tab, "Prelievi")
        
        # 5. Settings Tab
        self.settings_tab = SettingsTab()
        self.settings_tab.db_changed.connect(self.on_db_changed)
        self.tabs.addTab(self.settings_tab, "Impostazioni")
        
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.layout.addWidget(self.tabs)
        
        # Status Bar
        self.statusBar().showMessage("Pronto")

    @asyncSlot()
    async def on_db_changed(self):
        """Called when DB is imported or reset from SettingsTab"""
        # Refresh all tabs
        await self.dashboard_tab.refresh_data()
        await self.users_tab.refresh_users()
        await self.items_tab.refresh_materials()
        await self.consumables_tab.refresh_materials()
        await self.withdrawals_tab.refresh_withdrawals()
        self.statusBar().showMessage("Dati aggiornati dopo operazione su DB", 5000)

    @asyncSlot()
    async def on_tab_changed(self, *args):
        if not args:
            return
        index = args[0]
        widget = self.tabs.widget(index)
        if isinstance(widget, DashboardTab):
            await widget.refresh_data()
        elif isinstance(widget, UsersTab):
            # Assuming UsersTab has a refresh method, check previous code if needed.
            # Usually it loads on init. Let's check if it has a public refresh method.
            if hasattr(widget, "refresh_users"):
                await widget.refresh_users()
        elif isinstance(widget, MaterialsTab):
            await widget.refresh_materials()
        elif isinstance(widget, WithdrawalsTab):
            await widget.refresh_withdrawals()

    def closeEvent(self, event):
        """Assicura che il loop asyncio venga terminato alla chiusura della finestra."""
        if self.stop_event:
            self.stop_event.set()
        super().closeEvent(event)


