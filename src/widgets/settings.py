from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QTabWidget,
                           QLineEdit, QSpinBox, QComboBox, QCheckBox,
                           QPushButton, QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
import os
import json

class SettingsDialog(QWidget):
    """Widget for managing application settings"""
    
    # Signals
    settings_changed = pyqtSignal(dict)  # Emitted when settings are changed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_file = os.path.expanduser("~/.config/epy_explorer/settings.json")
        self.current_settings = {}
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        
        # Settings tabs
        self.tabs = QTabWidget()
        
        # General settings
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        
        # View settings
        view_group = QGroupBox("View Settings")
        view_layout = QFormLayout(view_group)
        
        self.default_view = QComboBox()
        self.default_view.addItems(["List", "Grid"])
        view_layout.addRow("Default View:", self.default_view)
        
        self.icon_size = QSpinBox()
        self.icon_size.setRange(16, 128)
        self.icon_size.setSingleStep(8)
        view_layout.addRow("Icon Size:", self.icon_size)
        
        self.show_hidden = QCheckBox("Show Hidden Files")
        view_layout.addRow(self.show_hidden)
        
        general_layout.addRow(view_group)
        
        # Preview settings
        preview_group = QGroupBox("Preview Settings")
        preview_layout = QFormLayout(preview_group)
        
        self.preview_enabled = QCheckBox("Enable File Preview")
        preview_layout.addRow(self.preview_enabled)
        
        self.max_preview_size = QSpinBox()
        self.max_preview_size.setRange(1, 100)
        self.max_preview_size.setSuffix(" MB")
        preview_layout.addRow("Max Preview Size:", self.max_preview_size)
        
        general_layout.addRow(preview_group)
        
        # Add tabs
        self.tabs.addTab(general_tab, "General")
        
        # Add tabs widget to layout
        layout.addWidget(self.tabs)
        
        # Save/Cancel buttons
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        buttons_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.load_settings)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
    def load_settings(self):
        """Load settings from config file"""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            if os.path.exists(self.settings_file):
                with open(self.settings_file) as f:
                    self.current_settings = json.load(f)
            else:
                self.current_settings = self.get_default_settings()
                
            # Update UI with loaded settings
            self.default_view.setCurrentText(
                self.current_settings.get('default_view', 'List')
            )
            self.icon_size.setValue(
                self.current_settings.get('icon_size', 32)
            )
            self.show_hidden.setChecked(
                self.current_settings.get('show_hidden', False)
            )
            self.preview_enabled.setChecked(
                self.current_settings.get('preview_enabled', True)
            )
            self.max_preview_size.setValue(
                self.current_settings.get('max_preview_size', 10)
            )
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load settings: {str(e)}")
            
    def save_settings(self):
        """Save settings to config file"""
        try:
            settings = {
                'default_view': self.default_view.currentText(),
                'icon_size': self.icon_size.value(),
                'show_hidden': self.show_hidden.isChecked(),
                'preview_enabled': self.preview_enabled.isChecked(),
                'max_preview_size': self.max_preview_size.value()
            }
            
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
                
            self.current_settings = settings
            self.settings_changed.emit(settings)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings: {str(e)}")
            
    def get_default_settings(self):
        """Get default settings"""
        return {
            'default_view': 'List',
            'icon_size': 32,
            'show_hidden': False,
            'preview_enabled': True,
            'max_preview_size': 10
        } 