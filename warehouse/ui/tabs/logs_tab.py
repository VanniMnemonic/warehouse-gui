from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QHeaderView, QLabel, QComboBox
)
from PyQt6.QtCore import Qt
from qasync import asyncSlot
from warehouse.controllers_log import get_logs
from warehouse.models import EventLog

class LogsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setup_ui()
        self.setLayout(self.layout)
        
        # Pagination state
        self.current_offset = 0
        self.page_size = 100
        
        # Initial load
        self.refresh_logs()

    def setup_ui(self):
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Log Eventi")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.refresh_btn = QPushButton("Aggiorna")
        self.refresh_btn.clicked.connect(self.on_refresh_click)
        header_layout.addWidget(self.refresh_btn)
        
        self.layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Data/Ora", "Tipo Evento", "Descrizione"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.layout.addWidget(self.table)
        
        # Footer / Pagination controls
        footer_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("<< Precedenti")
        self.prev_btn.clicked.connect(self.load_prev_page)
        self.prev_btn.setEnabled(False)
        footer_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Pagina 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Successivi >>")
        self.next_btn.clicked.connect(self.load_next_page)
        footer_layout.addWidget(self.next_btn)
        
        self.layout.addLayout(footer_layout)

    def on_refresh_click(self):
        self.current_offset = 0
        self.refresh_logs()

    def load_prev_page(self):
        if self.current_offset >= self.page_size:
            self.current_offset -= self.page_size
            self.refresh_logs()

    def load_next_page(self):
        self.current_offset += self.page_size
        self.refresh_logs()

    @asyncSlot()
    async def refresh_logs(self):
        logs = await get_logs(limit=self.page_size, offset=self.current_offset)
        
        self.table.setRowCount(0)
        
        for log in logs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Timestamp
            ts_str = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            self.table.setItem(row, 0, QTableWidgetItem(ts_str))
            
            # Type
            type_str = log.event_type.value if hasattr(log.event_type, 'value') else str(log.event_type)
            self.table.setItem(row, 1, QTableWidgetItem(type_str))
            
            # Description
            desc_item = QTableWidgetItem(log.description)
            desc_item.setToolTip(log.description)
            self.table.setItem(row, 2, desc_item)
            
        # Update pagination state
        page_num = (self.current_offset // self.page_size) + 1
        self.page_label.setText(f"Pagina {page_num}")
        
        self.prev_btn.setEnabled(self.current_offset > 0)
        # We don't know total count easily without another query, 
        # but if we got less than page_size, we are at the end.
        self.next_btn.setEnabled(len(logs) == self.page_size)
