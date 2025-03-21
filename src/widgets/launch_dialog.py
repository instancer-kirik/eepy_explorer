from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                           QTreeWidget, QTreeWidgetItem, QLabel, QLineEdit,
                           QTextEdit, QInputDialog, QMessageBox, QMenu)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from datetime import datetime

class LaunchDialog(QDialog):
    """Dialog for managing project launch configurations"""
    
    def __init__(self, parent=None, path=None):
        super().__init__(parent)
        self.launch_manager = parent.launch_manager if parent else None
        self.path = path
        self.setup_ui()
        
        # Detect and load configurations
        if path:
            self.detect_configurations()
        
    def setup_ui(self):
        """Initialize the UI components"""
        self.setWindowTitle("Launch Configurations")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Path display
        path_layout = QHBoxLayout()
        path_label = QLabel("Path:")
        self.path_display = QLabel(self.path or "No path selected")
        self.path_display.setWordWrap(True)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_display, 1)
        layout.addLayout(path_layout)
        
        # Configuration list
        self.config_tree = QTreeWidget()
        self.config_tree.setHeaderLabels([
            "Name", "Type", "Command", "Description", "Last Used"
        ])
        self.config_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.config_tree.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.config_tree)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        detect_btn = QPushButton("Detect Configurations")
        detect_btn.clicked.connect(self.detect_configurations)
        button_layout.addWidget(detect_btn)
        
        add_btn = QPushButton("Add Configuration")
        add_btn.clicked.connect(self.add_configuration)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self.edit_configuration(self.config_tree.currentItem()))
        button_layout.addWidget(edit_btn)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_configuration)
        button_layout.addWidget(remove_btn)
        
        button_layout.addStretch()
        
        run_btn = QPushButton("Run Selected")
        run_btn.clicked.connect(self.run_selected)
        button_layout.addWidget(run_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Load existing configurations
        self.load_configurations()
        
    def load_configurations(self):
        """Load existing launch configurations"""
        self.config_tree.clear()
        
        if not self.launch_manager or not self.path:
            return
            
        for config in self.launch_manager.get_launches(self.path):
            self.add_config_item(config)
            
    def add_config_item(self, config):
        """Add configuration item to tree"""
        item = QTreeWidgetItem(self.config_tree)
        item.setText(0, config['name'])
        item.setText(1, config.get('type', ''))
        item.setText(2, config['command'])
        item.setText(3, config.get('description', ''))
        
        # Set last used time if available
        if 'last_used' in config:
            last_used = datetime.fromisoformat(config['last_used'])
            item.setText(4, last_used.strftime('%Y-%m-%d %H:%M:%S'))
            
        # Set icon if available
        if 'icon' in config:
            item.setIcon(0, QIcon.fromTheme(config['icon']))
            
        # Store full config in item data
        item.setData(0, Qt.ItemDataRole.UserRole, config)
        
    def detect_configurations(self):
        """Detect project configurations"""
        if not self.launch_manager or not self.path:
            return
            
        # Detect new configurations
        configs = self.launch_manager.detect_project(self.path)
        
        if configs:
            # Add new configurations
            for config in configs:
                self.launch_manager.add_launch(self.path, config)
                
            # Reload configurations
            self.load_configurations()
        else:
            QMessageBox.information(
                self,
                "No Configurations Found",
                "No project configurations were detected in this directory."
            )
            
    def add_configuration(self):
        """Add a new launch configuration"""
        if not self.launch_manager or not self.path:
            return
            
        name, ok = QInputDialog.getText(
            self, "Add Configuration", "Configuration Name:"
        )
        if not ok or not name:
            return
            
        command, ok = QInputDialog.getText(
            self, "Add Configuration", "Command:"
        )
        if not ok or not command:
            return
            
        description, ok = QInputDialog.getText(
            self, "Add Configuration", "Description:"
        )
        if not ok:
            description = ""
            
        config = {
            'name': name,
            'command': command,
            'description': description,
            'working_dir': self.path,
            'type': 'custom'
        }
        
        self.launch_manager.add_launch(self.path, config)
        self.load_configurations()
        
    def edit_configuration(self, item):
        """Edit an existing configuration"""
        if not item or not self.launch_manager:
            return
            
        config = item.data(0, Qt.ItemDataRole.UserRole)
        if not config:
            return
            
        command, ok = QInputDialog.getText(
            self, "Edit Configuration", "Command:",
            text=config['command']
        )
        if not ok:
            return
            
        description, ok = QInputDialog.getText(
            self, "Edit Configuration", "Description:",
            text=config.get('description', '')
        )
        if not ok:
            return
            
        # Update configuration
        config['command'] = command
        config['description'] = description
        
        self.launch_manager.add_launch(self.path, config)
        self.load_configurations()
        
    def remove_configuration(self):
        """Remove selected configuration"""
        item = self.config_tree.currentItem()
        if not item or not self.launch_manager:
            return
            
        config = item.data(0, Qt.ItemDataRole.UserRole)
        if not config:
            return
            
        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Are you sure you want to remove the configuration '{config['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.launch_manager.remove_launch(self.path, config['name'])
            self.load_configurations()
            
    def run_selected(self):
        """Run selected configuration"""
        item = self.config_tree.currentItem()
        if not item or not self.launch_manager:
            return
            
        config = item.data(0, Qt.ItemDataRole.UserRole)
        if not config:
            return
            
        self.launch_manager.launch_project(self.path, config)
        
    def show_context_menu(self, position):
        """Show context menu for configuration items"""
        item = self.config_tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu()
        
        run_action = menu.addAction("Run")
        run_action.triggered.connect(lambda: self.run_selected())
        
        menu.addSeparator()
        
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self.edit_configuration(item))
        
        remove_action = menu.addAction("Remove")
        remove_action.triggered.connect(self.remove_configuration)
        
        menu.exec(self.config_tree.viewport().mapToGlobal(position)) 