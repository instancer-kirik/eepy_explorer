from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QComboBox, QScrollArea, QWidget)
from PyQt6.QtCore import Qt
import os

class FileConflictDialog(QDialog):
    """Dialog for handling file conflicts during copy/move operations"""
    
    def __init__(self, conflicts, parent=None):
        """
        Initialize dialog
        
        Args:
            conflicts: List of tuples (source_path, target_path)
            parent: Parent widget
        """
        super().__init__(parent)
        self.conflicts = conflicts
        self.resolutions = {}
        self.setup_ui()
        
    def setup_ui(self):
        """Setup dialog UI"""
        self.setWindowTitle("File Conflicts")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("The following files already exist. Choose what to do:")
        layout.addWidget(header)
        
        # Scrollable conflict list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Add conflict items
        for src, dst in self.conflicts:
            item = QWidget()
            item_layout = QHBoxLayout(item)
            
            # File info
            info = QLabel(f"{os.path.basename(src)}\nTarget: {dst}")
            item_layout.addWidget(info)
            
            # Resolution combo
            combo = QComboBox()
            combo.addItems(["Skip", "Rename", "Replace"])
            combo.setCurrentText("Skip")
            combo.currentTextChanged.connect(
                lambda text, s=src: self.resolutions.update({s: text.lower()})
            )
            item_layout.addWidget(combo)
            
            scroll_layout.addWidget(item)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Buttons
        buttons = QHBoxLayout()
        
        apply_all = QPushButton("Apply to All")
        apply_all.clicked.connect(self.apply_to_all)
        buttons.addWidget(apply_all)
        
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        
        layout.addLayout(buttons)
    
    def apply_to_all(self):
        """Apply current resolution to all conflicts"""
        if not self.conflicts:
            return
            
        # Get first resolution as template
        template = self.resolutions.get(self.conflicts[0][0], 'skip')
        
        # Apply to all
        for src, _ in self.conflicts:
            self.resolutions[src] = template
            
        self.accept()
    
    def get_resolutions(self):
        """Get dictionary of conflict resolutions"""
        return self.resolutions 