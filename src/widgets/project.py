from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                           QMenu, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
import os
import json

class ProjectView(QWidget):
    """Widget for managing project files and structure"""
    
    # Signals
    file_selected = pyqtSignal(str)  # Emitted when a file is selected
    project_loaded = pyqtSignal(str)  # Emitted when a project is loaded
    project_closed = pyqtSignal()  # Emitted when project is closed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_file = None
        self.project_root = None
        self.project_config = {}
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Project tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name"])
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemClicked.connect(self._handle_item_click)
        layout.addWidget(self.tree)
        
    def load_project(self, path):
        """Load project from directory"""
        if not os.path.isdir(path):
            return False
            
        self.project_root = path
        self.project_file = os.path.join(path, '.epy-project')
        
        # Load project config if exists
        if os.path.exists(self.project_file):
            try:
                with open(self.project_file) as f:
                    self.project_config = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load project config: {str(e)}")
                self.project_config = {}
                
        # Refresh project tree
        self.refresh_tree()
        self.project_loaded.emit(path)
        return True
        
    def close_project(self):
        """Close current project"""
        self.project_root = None
        self.project_file = None
        self.project_config = {}
        self.tree.clear()
        self.project_closed.emit()
        
    def refresh_tree(self):
        """Refresh project tree view"""
        if not self.project_root:
            return
            
        self.tree.clear()
        root_item = QTreeWidgetItem(self.tree)
        root_item.setText(0, os.path.basename(self.project_root))
        root_item.setIcon(0, QIcon.fromTheme("folder-documents"))
        root_item.setData(0, Qt.ItemDataRole.UserRole, self.project_root)
        
        self._populate_tree(root_item, self.project_root)
        root_item.setExpanded(True)
        
    def _populate_tree(self, parent_item, directory):
        """Recursively populate tree with directory contents"""
        try:
            # Get ignore patterns from project config
            ignore_patterns = self.project_config.get('ignore', [])
            
            for name in sorted(os.listdir(directory)):
                # Skip ignored files/directories
                if any(pattern in name for pattern in ignore_patterns):
                    continue
                    
                path = os.path.join(directory, name)
                item = QTreeWidgetItem(parent_item)
                item.setText(0, name)
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                
                if os.path.isdir(path):
                    item.setIcon(0, QIcon.fromTheme("folder"))
                    self._populate_tree(item, path)
                else:
                    item.setIcon(0, QIcon.fromTheme("text-x-generic"))
                    
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to read directory: {str(e)}")
            
    def _handle_item_click(self, item):
        """Handle item click in tree"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.isfile(path):
            self.file_selected.emit(path)
            
    def _show_context_menu(self, position):
        """Show context menu for tree items"""
        item = self.tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu()
        path = item.data(0, Qt.ItemDataRole.UserRole)
        
        if os.path.isdir(path):
            # Directory actions
            new_file_action = menu.addAction("New File")
            new_folder_action = menu.addAction("New Folder")
            menu.addSeparator()
            
        # Common actions
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec(self.tree.mapToGlobal(position))
        
        if action == rename_action:
            self._rename_item(item)
        elif action == delete_action:
            self._delete_item(item)
        elif os.path.isdir(path):
            if action == new_file_action:
                self._create_file(item)
            elif action == new_folder_action:
                self._create_folder(item)
                
    def _rename_item(self, item):
        """Rename file or directory"""
        old_path = item.data(0, Qt.ItemDataRole.UserRole)
        old_name = os.path.basename(old_path)
        
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=old_name
        )
        
        if ok and new_name and new_name != old_name:
            try:
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                os.rename(old_path, new_path)
                item.setText(0, new_name)
                item.setData(0, Qt.ItemDataRole.UserRole, new_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to rename: {str(e)}")
                
    def _delete_item(self, item):
        """Delete file or directory"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        name = os.path.basename(path)
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(path):
                    os.rmdir(path)  # Only remove if empty
                else:
                    os.remove(path)
                    
                parent = item.parent()
                if parent:
                    parent.removeChild(item)
                else:
                    self.tree.takeTopLevelItem(
                        self.tree.indexOfTopLevelItem(item)
                    )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete: {str(e)}")
                
    def _create_file(self, parent_item):
        """Create new file in directory"""
        parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole)
        
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            try:
                path = os.path.join(parent_path, name)
                with open(path, 'w') as f:
                    pass  # Create empty file
                    
                item = QTreeWidgetItem(parent_item)
                item.setText(0, name)
                item.setIcon(0, QIcon.fromTheme("text-x-generic"))
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create file: {str(e)}")
                
    def _create_folder(self, parent_item):
        """Create new folder in directory"""
        parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole)
        
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            try:
                path = os.path.join(parent_path, name)
                os.makedirs(path)
                
                item = QTreeWidgetItem(parent_item)
                item.setText(0, name)
                item.setIcon(0, QIcon.fromTheme("folder"))
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create folder: {str(e)}") 