from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                           QGroupBox, QPushButton, QMenu, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
import os
import psutil
import json

class Sidebar(QWidget):
    """Widget for favorites and drives"""
    
    # Signals
    location_selected = pyqtSignal(str)  # Emitted when location selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.favorites_file = os.path.expanduser("~/.config/epy_explorer/favorites.json")
        self.setup_ui()
        self.load_favorites()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # System Pins section
        system_group = QGroupBox("System")
        system_layout = QVBoxLayout(system_group)
        system_layout.setContentsMargins(4, 4, 4, 4)
        
        self.system_list = QTreeWidget()
        self.system_list.setHeaderHidden(True)
        self.system_list.itemClicked.connect(self._handle_system_click)
        system_layout.addWidget(self.system_list)
        
        # Add default system locations
        self._add_system_locations()
        
        layout.addWidget(system_group)
        
        # Quick Access section
        quick_group = QGroupBox("Quick Access")
        quick_layout = QVBoxLayout(quick_group)
        quick_layout.setContentsMargins(4, 4, 4, 4)
        
        self.quick_list = QTreeWidget()
        self.quick_list.setHeaderHidden(True)
        self.quick_list.itemClicked.connect(self._handle_quick_click)
        quick_layout.addWidget(self.quick_list)
        
        # Add default quick access locations
        self._add_quick_access_locations()
        
        layout.addWidget(quick_group)
        
        # Favorites section
        favorites_group = QGroupBox("Favorites")
        favorites_layout = QVBoxLayout(favorites_group)
        favorites_layout.setContentsMargins(4, 4, 4, 4)
        
        self.favorites_list = QTreeWidget()
        self.favorites_list.setHeaderLabels(["Name"])
        self.favorites_list.itemClicked.connect(self._handle_favorite_click)
        self.favorites_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.favorites_list.customContextMenuRequested.connect(self._show_favorites_menu)
        favorites_layout.addWidget(self.favorites_list)
        
        # Add/Remove favorite buttons
        buttons_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_favorite)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_favorite)
        buttons_layout.addWidget(add_btn)
        buttons_layout.addWidget(remove_btn)
        favorites_layout.addLayout(buttons_layout)
        
        layout.addWidget(favorites_group)
        
        # Drives section
        drives_group = QGroupBox("Drives")
        drives_layout = QVBoxLayout(drives_group)
        drives_layout.setContentsMargins(4, 4, 4, 4)
        
        self.drives_list = QTreeWidget()
        self.drives_list.setHeaderLabels(["Name", "Type"])
        self.drives_list.itemClicked.connect(self._handle_drive_click)
        drives_layout.addWidget(self.drives_list)
        
        # Refresh drives button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_drives)
        drives_layout.addWidget(refresh_btn)
        
        layout.addWidget(drives_group)
        
        # Initial drives refresh
        self.refresh_drives()
        
    def load_favorites(self):
        """Load favorites from config file"""
        try:
            os.makedirs(os.path.dirname(self.favorites_file), exist_ok=True)
            if os.path.exists(self.favorites_file):
                with open(self.favorites_file) as f:
                    favorites = json.load(f)
                    for fav in favorites:
                        self.add_favorite_item(fav['name'], fav['path'])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load favorites: {str(e)}")
            
    def save_favorites(self):
        """Save favorites to config file"""
        try:
            favorites = []
            for i in range(self.favorites_list.topLevelItemCount()):
                item = self.favorites_list.topLevelItem(i)
                favorites.append({
                    'name': item.text(0),
                    'path': item.data(0, Qt.ItemDataRole.UserRole)
                })
            
            os.makedirs(os.path.dirname(self.favorites_file), exist_ok=True)
            with open(self.favorites_file, 'w') as f:
                json.dump(favorites, f)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save favorites: {str(e)}")
            
    def add_favorite(self, path=None, name=None):
        """Add current or specified path to favorites"""
        if not path:
            path = self.parent().get_current_path()
        if not name:
            name = os.path.basename(path)
            
        self.add_favorite_item(name, path)
        self.save_favorites()
        
    def add_favorite_item(self, name, path):
        """Add favorite item to list"""
        item = QTreeWidgetItem(self.favorites_list)
        item.setText(0, name)
        item.setIcon(0, QIcon.fromTheme("folder-favorites"))
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        
    def remove_favorite(self):
        """Remove selected favorite"""
        item = self.favorites_list.currentItem()
        if item:
            self.favorites_list.takeTopLevelItem(
                self.favorites_list.indexOfTopLevelItem(item)
            )
            self.save_favorites()
            
    def refresh_drives(self):
        """Refresh list of mounted drives"""
        self.drives_list.clear()
        
        try:
            partitions = psutil.disk_partitions()
            for p in partitions:
                item = QTreeWidgetItem(self.drives_list)
                item.setText(0, p.mountpoint)
                item.setText(1, p.fstype)
                item.setIcon(0, QIcon.fromTheme("drive-harddisk"))
                
                # Store full info for mounting
                item.setData(0, Qt.ItemDataRole.UserRole, {
                    'device': p.device,
                    'mountpoint': p.mountpoint,
                    'fstype': p.fstype,
                    'opts': p.opts
                })
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to refresh drives: {str(e)}")
            
    def _handle_favorite_click(self, item):
        """Handle favorite item click"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.exists(path):
            self.location_selected.emit(path)
            
    def _handle_drive_click(self, item):
        """Handle drive item click"""
        drive_info = item.data(0, Qt.ItemDataRole.UserRole)
        if drive_info and os.path.exists(drive_info['mountpoint']):
            self.location_selected.emit(drive_info['mountpoint'])
            
    def _show_favorites_menu(self, position):
        """Show context menu for favorites"""
        menu = QMenu()
        
        rename_action = menu.addAction("Rename")
        remove_action = menu.addAction("Remove")
        
        item = self.favorites_list.itemAt(position)
        action = menu.exec(self.favorites_list.mapToGlobal(position))
        
        if action == rename_action and item:
            self.favorites_list.editItem(item)
        elif action == remove_action and item:
            self.remove_favorite()

    def _add_system_locations(self):
        """Add default system locations"""
        locations = [
            ("Home", os.path.expanduser("~"), "user-home"),
            ("Desktop", os.path.expanduser("~/Desktop"), "user-desktop"),
            ("Documents", os.path.expanduser("~/Documents"), "folder-documents"),
            ("Downloads", os.path.expanduser("~/Downloads"), "folder-downloads"),
            ("Pictures", os.path.expanduser("~/Pictures"), "folder-pictures"),
            ("Music", os.path.expanduser("~/Music"), "folder-music"),
            ("Videos", os.path.expanduser("~/Videos"), "folder-videos")
        ]
        
        for name, path, icon in locations:
            if os.path.exists(path):
                item = QTreeWidgetItem(self.system_list)
                item.setText(0, name)
                item.setIcon(0, QIcon.fromTheme(icon))
                item.setData(0, Qt.ItemDataRole.UserRole, path)

    def _add_quick_access_locations(self):
        """Add quick access filesystem locations"""
        locations = [
            ("Root", "/", "drive-harddisk"),
            ("Boot", "/boot", "system-run"),
            ("Media", "/media", "drive-removable-media"),
            ("Mnt", "/mnt", "folder-remote"),
            ("Opt", "/opt", "package-x-generic"),
            ("Usr", "/usr", "system-file-manager"),
            ("Var", "/var", "folder-templates")
        ]
        
        for name, path, icon in locations:
            if os.path.exists(path):
                item = QTreeWidgetItem(self.quick_list)
                item.setText(0, name)
                item.setIcon(0, QIcon.fromTheme(icon))
                item.setData(0, Qt.ItemDataRole.UserRole, path)

    def _handle_system_click(self, item):
        """Handle system location click"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.exists(path):
            self.location_selected.emit(path)

    def _handle_quick_click(self, item):
        """Handle quick access location click"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.exists(path):
            self.location_selected.emit(path) 