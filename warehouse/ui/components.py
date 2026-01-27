from PyQt6.QtWidgets import QComboBox, QCompleter
from PyQt6.QtCore import Qt, pyqtSignal

class BarcodeSearchComboBox(QComboBox):
    """
    A QComboBox that allows searching by text and selecting by barcode scanning.
    """
    
    # Custom signal if needed, though currentIndexChanged is usually enough
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        # Setup custom model-based completer
        self._completer = QCompleter(self.model())
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        # We need a proxy model or custom filtering to search in UserRole+2 (search_text)
        # But for QComboBox simple usage, standard completer searches DisplayRole or EditRole.
        # To search across multiple fields, we usually concatenate them in the display text OR
        # use a QSortFilterProxyModel.
        # 
        # A simpler approach for "search-box like" behavior is to use a QSortFilterProxyModel
        # that filters rows based on a custom role where we store "all searchable text".
        
        from PyQt6.QtCore import QSortFilterProxyModel
        
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model())
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        # We will store the full searchable text in UserRole + 2
        self.proxy_model.setFilterRole(Qt.ItemDataRole.UserRole + 2)
        self.proxy_model.setFilterKeyColumn(0)
        
        # Replace the completer's model with our proxy model
        self._completer.setModel(self.proxy_model)
        
        # We need to ensure the combobox uses the completer
        self.setCompleter(self._completer)

        # Connect text change to handle barcode scanning AND filtering
        self.editTextChanged.connect(self.on_edit_text_changed)
        
        # Store barcodes mapping: barcode -> index (in source model)
        self.barcode_map = {}

    def addItem(self, text, userData=None, barcode=None, search_text=None):
        super().addItem(text, userData)
        index = self.count() - 1
        
        # If search_text is not provided, use the display text
        full_search_text = search_text if search_text else text
        self.setItemData(index, full_search_text, Qt.ItemDataRole.UserRole + 2)
        
        if barcode:
            # Normalize barcode if needed (strip whitespace)
            clean_barcode = str(barcode).strip()
            if clean_barcode:
                # Store barcode in UserRole + 1 (custom role)
                self.setItemData(index, clean_barcode, Qt.ItemDataRole.UserRole + 1)
                self.barcode_map[clean_barcode] = index

    def on_edit_text_changed(self, text):
        if not text:
            self.proxy_model.setFilterFixedString("")
            return
            
        clean_text = text.strip()
        
        # 1. Barcode check (Priority)
        if clean_text in self.barcode_map:
            index = self.barcode_map[clean_text]
            if index != self.currentIndex():
                self.setCurrentIndex(index)
                return

        # 2. Filter the completer suggestions
        # The proxy model filters based on UserRole+2 (full search text)
        self.proxy_model.setFilterFixedString(text)
        
        # We need to manually trigger the completer popup update
        # because we are changing the underlying model filtering
        if self._completer.popup():
             # Logic to force update?
             # QCompleter usually updates automatically when prefix changes.
             # But here we are filtering the model itself.
             pass

    # Overriding to make sure we set the data correctly
    def setItemData(self, index, value, role=Qt.ItemDataRole.UserRole):
        super().setItemData(index, value, role)

