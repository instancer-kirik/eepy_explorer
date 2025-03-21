from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QPushButton,
                           QLineEdit, QCompleter)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
import os

from .address_bar import AddressBar

class NavigationBar(QWidget):
    """Widget for file system navigation"""
    
    # Signals
    path_changed = pyqtSignal(str)  # Emitted when path changes
    back_requested = pyqtSignal()  # Emitted when back button clicked
    forward_requested = pyqtSignal()  # Emitted when forward button clicked
    up_requested = pyqtSignal()  # Emitted when up button clicked
    refresh_requested = pyqtSignal()  # Emitted when refresh button clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Back button
        self.back_btn = QPushButton("←")
        self.back_btn.setFixedWidth(30)
        self.back_btn.clicked.connect(self.back_requested.emit)
        self.back_btn.setEnabled(False)
        layout.addWidget(self.back_btn)
        
        # Forward button
        self.forward_btn = QPushButton("→")
        self.forward_btn.setFixedWidth(30)
        self.forward_btn.clicked.connect(self.forward_requested.emit)
        self.forward_btn.setEnabled(False)
        layout.addWidget(self.forward_btn)
        
        # Up button
        self.up_btn = QPushButton("↑")
        self.up_btn.setFixedWidth(30)
        self.up_btn.clicked.connect(self.up_requested.emit)
        layout.addWidget(self.up_btn)
        
        # Address bar
        self.address_bar = AddressBar()
        self.address_bar.returnPressed.connect(self._handle_address_change)
        layout.addWidget(self.address_bar)
        
        # Refresh button
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self.refresh_btn)
        
    def set_path(self, path):
        """Update the address bar with new path"""
        self.address_bar.setText(path)
        
    def set_history_state(self, can_go_back, can_go_forward):
        """Update navigation button states"""
        self.back_btn.setEnabled(can_go_back)
        self.forward_btn.setEnabled(can_go_forward)
        
    def _handle_address_change(self):
        """Handle when user enters a new path"""
        path = self.address_bar.text()
        if os.path.exists(path):
            self.path_changed.emit(path)
        else:
            # Restore previous path
            self.address_bar.setText(self._current_path)
            
    def get_current_path(self):
        """Get the current path from address bar"""
        return self.address_bar.text() 