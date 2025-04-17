from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QPushButton,
                           QLineEdit, QCompleter, QToolButton, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
import os

from .address_bar import AddressBar

class NavigationBar(QWidget):
    """Widget for file system navigation with mode switching"""
    
    # Signals
    path_changed = pyqtSignal(str)  # Emitted when path changes
    back_requested = pyqtSignal()  # Emitted when back button clicked
    forward_requested = pyqtSignal()  # Emitted when forward button clicked
    up_requested = pyqtSignal()  # Emitted when up button clicked
    refresh_requested = pyqtSignal()  # Emitted when refresh button clicked
    mode_changed = pyqtSignal(str)  # Emitted when mode is changed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = os.path.expanduser("~")
        self._current_mode = "file"  # Default mode
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Mode buttons (file, project, notes)
        self.file_mode_btn = QToolButton()
        self.file_mode_btn.setIcon(QIcon.fromTheme("folder"))
        self.file_mode_btn.setToolTip("File Explorer Mode")
        self.file_mode_btn.setCheckable(True)
        self.file_mode_btn.setChecked(True)  # Default mode
        self.file_mode_btn.clicked.connect(lambda: self._handle_mode_change("file"))
        layout.addWidget(self.file_mode_btn)
        
        self.project_mode_btn = QToolButton()
        self.project_mode_btn.setIcon(QIcon.fromTheme("project"))
        self.project_mode_btn.setToolTip("Project Mode")
        self.project_mode_btn.setCheckable(True)
        self.project_mode_btn.clicked.connect(lambda: self._handle_mode_change("project"))
        layout.addWidget(self.project_mode_btn)
        
        self.notes_mode_btn = QToolButton()
        self.notes_mode_btn.setIcon(QIcon.fromTheme("text-x-markdown"))
        self.notes_mode_btn.setToolTip("Notes Vault Mode")
        self.notes_mode_btn.setCheckable(True)
        self.notes_mode_btn.clicked.connect(lambda: self._handle_mode_change("notes"))
        layout.addWidget(self.notes_mode_btn)
        
        # Add a small separator
        separator = QWidget()
        separator.setFixedWidth(4)
        layout.addWidget(separator)
        
        # Navigation buttons
        self.back_btn = QPushButton("←")
        self.back_btn.setFixedWidth(30)
        self.back_btn.clicked.connect(self.back_requested.emit)
        self.back_btn.setEnabled(False)
        layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("→")
        self.forward_btn.setFixedWidth(30)
        self.forward_btn.clicked.connect(self.forward_requested.emit)
        self.forward_btn.setEnabled(False)
        layout.addWidget(self.forward_btn)
        
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
        
    def _handle_mode_change(self, mode):
        """Handle when user clicks a mode button"""
        if mode != self._current_mode:
            old_mode = self._current_mode
            self._current_mode = mode
            
            # Update button states with safety checks
            try:
                if hasattr(self, 'file_mode_btn') and self.file_mode_btn is not None:
                    self.file_mode_btn.setChecked(mode == "file")
                if hasattr(self, 'project_mode_btn') and self.project_mode_btn is not None:
                    self.project_mode_btn.setChecked(mode == "project")
                if hasattr(self, 'notes_mode_btn') and self.notes_mode_btn is not None:
                    self.notes_mode_btn.setChecked(mode == "notes")
            except RuntimeError as e:
                # Handle case where the C++ object has been deleted
                print(f"Warning: Could not update mode buttons: {e}")
            
            # Emit the mode changed signal
            self.mode_changed.emit(mode)
        
    def set_mode(self, mode):
        """Set the current application mode"""
        if mode in ["file", "project", "notes"] and mode != self._current_mode:
            self._current_mode = mode
            
            # Update button states with safety checks
            try:
                if hasattr(self, 'file_mode_btn') and self.file_mode_btn is not None:
                    self.file_mode_btn.setChecked(mode == "file")
                if hasattr(self, 'project_mode_btn') and self.project_mode_btn is not None:
                    self.project_mode_btn.setChecked(mode == "project") 
                if hasattr(self, 'notes_mode_btn') and self.notes_mode_btn is not None:
                    self.notes_mode_btn.setChecked(mode == "notes")
            except RuntimeError as e:
                # Handle case where the C++ object has been deleted
                print(f"Warning: Could not update mode buttons: {e}")
            
            return True
        return False
        
    def get_current_mode(self):
        """Get the current application mode"""
        return self._current_mode
        
    def set_path(self, path):
        """Update the address bar with new path"""
        self._current_path = path
        self.address_bar.setText(path)
        
    def set_history_state(self, can_go_back, can_go_forward):
        """Update navigation button states"""
        self.back_btn.setEnabled(can_go_back)
        self.forward_btn.setEnabled(can_go_forward)
        
    def _handle_address_change(self):
        """Handle when user enters a new path"""
        path = self.address_bar.text()
        if os.path.exists(path):
            self._current_path = path
            self.path_changed.emit(path)
        else:
            # Restore previous path
            self.address_bar.setText(self._current_path)
            
    def get_current_path(self):
        """Get the current path from address bar"""
        return self.address_bar.text() 