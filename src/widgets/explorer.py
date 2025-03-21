from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTreeWidgetItem, 
                           QHBoxLayout, QSplitter, QLabel, QPushButton, QTreeWidget, QGroupBox, QTabWidget, QTreeView, QListView, QStackedWidget, QProgressDialog, QApplication, QMessageBox, QHeaderView, QMenu, QInputDialog, QLineEdit)
from PyQt6.QtCore import Qt, QDir, QSize, QFileSystemWatcher, QTimer, QEventLoop, QThread
from PyQt6.QtGui import QFileSystemModel, QIcon, QStandardItemModel, QStandardItem
from PyQt6 import sip
from pathlib import Path
from .toolbar import setup_toolbar
from .preview import update_preview
from ..tools.project import set_project_root
from ..tools.build import BuildManager
from .address_bar import AddressBar
from ..tools.vcs import VCSManager
from ..utils.themes import setup_theme
from ..utils.file_ops import FileOperations
from ..utils.dialogs import FileConflictDialog
from .tools.test_tool import TestTool
from ..views.test_results import TestResultsView
from ..tools.duplicate_finder import DuplicateFinder
from .duplicate_dialog import DuplicateDialog
from ..tools.command_manager import CommandManager
from ..tools.launch_manager import LaunchManager
from ..tools.notes_manager import NotesManager
import subprocess
import os
import zipfile
import json
from datetime import datetime
import psutil
import asyncio
from qasync import QEventLoop, asyncSlot
import re
import hashlib
import sys
import mimetypes
import magic
import time
import shutil

class EExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize managers and tools
        self.build_manager = BuildManager(self)
        self.vcs_manager = VCSManager(self)
        self.file_ops = FileOperations(self)
        self.test_tool = TestTool(self)
        self.duplicate_finder = DuplicateFinder(self)
        self.command_manager = CommandManager(self)
        self.launch_manager = LaunchManager(self)
        
        # Initialize state variables
        self.file_history = []
        self.history_index = -1
        self.clipboard_files = []
        self.clipboard_operation = None
        self.current_mode = 'file'
        self.current_view_mode = 'list'
        
        # Setup UI
        self.setup_ui()
        setup_theme(self)
        
        # Setup async event loop
        self.loop = QEventLoop()
        asyncio.set_event_loop(self.loop)
        
        # Set up file watcher for auto-refresh
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self.refresh_view)
        
        # Set up test tool
        # Make sure we're connecting to methods that actually exist
        if hasattr(self.test_view, 'handle_test_started'):
            self.test_tool.test_started.connect(self.test_view.handle_test_started)
        if hasattr(self.test_view, 'handle_test_finished'):
            self.test_tool.test_finished.connect(self.test_view.handle_test_finished)
        if hasattr(self.test_view, 'handle_test_error'):
            self.test_tool.test_error.connect(self.test_view.handle_test_error)
            
        # Set up navigation history
        self.nav_history = []
        self.nav_current = -1
        
        # Refresh drives list
        self.refresh_drives()
    
    def setup_ui(self):
        """Initialize the main UI components"""
        # Window setup
        self.setWindowTitle("EEPY Explorer")
        self.setGeometry(100, 100, 1200, 800)
        
        # Status bar and project state
        self.status_bar = self.statusBar()
        self.project_state = QLabel()
        self.status_bar.addPermanentWidget(self.project_state)
        
        # Initialize file system model
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)
        
        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        setup_toolbar(self, toolbar_layout)
        self.main_layout.addWidget(toolbar)
        
        # Main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(main_splitter)
        
        # Left panel (file tree, favorites, drives)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        main_splitter.addWidget(left_panel)
        
        # Set up file tree and favorites
        self.setup_file_tree(left_layout)
        self.setup_favorites(left_layout)
        
        # Add drives section
        drives_group = self.setup_drives()
        left_layout.addWidget(drives_group)
        
        # Right panel with vertical splitter
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(self.right_splitter)
        
        # Set up views with navigation
        views_container = self.setup_views()
        self.right_splitter.addWidget(views_container)
        
        # Preview panel with toggle button
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(2)
        
        # Preview toggle button
        preview_header = QWidget()
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(4, 2, 4, 2)
        
        self.preview_toggle = QPushButton("▼ Preview")  # ▼ for expanded, ▶ for collapsed
        self.preview_toggle.setStyleSheet("""
            QPushButton {
                border: none;
                text-align: left;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.preview_toggle.clicked.connect(self.toggle_preview)
        preview_header_layout.addWidget(self.preview_toggle)
        preview_layout.addWidget(preview_header)
        
        # Preview tabs
        self.preview_tabs = QTabWidget()
        self.preview_tabs.setTabsClosable(True)
        self.preview_tabs.tabCloseRequested.connect(self.close_preview_tab)
        preview_layout.addWidget(self.preview_tabs)
        self.right_splitter.addWidget(preview_container)
        
        # Hide preview initially
        self.preview_tabs.hide()
        self.preview_toggle.setText("▶ Preview")
        
        # Test results view
        self.test_view = TestResultsView()
        self.test_view.run_tests.connect(self.test_tool.run_tests)
        self.test_view.toggle_watch.connect(self.test_tool.toggle_watch)
        self.test_view.test_selected.connect(self.test_tool.handle_test_selected)
        self.right_splitter.addWidget(self.test_view)
        
        # Set initial splitter sizes
        self.right_splitter.setSizes([500, 0, 200])  # Views:Preview:Tests ratio
        main_splitter.setSizes([300, 900])  # Left:Right ratio
        
        # Initialize navigation history
        self.nav_history = []
        self.nav_current = -1
        
        # Refresh drives list
        self.refresh_drives()
        
        # Set up navigation bar
        self.setup_navigation()
    
    def setup_file_tree(self, parent_layout):
        """Set up the file tree view"""
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.model)
        self.file_tree.setDragEnabled(True)
        self.file_tree.setAcceptDrops(True)
        self.file_tree.setDropIndicatorShown(True)
        self.file_tree.doubleClicked.connect(self.handle_item_double_click)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
        # Set to collapsed state by default
        self.file_tree.setExpanded(self.file_tree.rootIndex(), False)
        parent_layout.addWidget(self.file_tree)

    def setup_favorites(self, layout):
        """Set up favorites section with auto-import"""
        favorites_group = QGroupBox("Favorites")
        favorites_layout = QVBoxLayout(favorites_group)
        favorites_layout.setContentsMargins(4, 4, 4, 4)
        favorites_layout.setSpacing(2)
        
        # Favorites tree
        self.favorites_tree = QTreeWidget()
        self.favorites_tree.setHeaderLabels(["Name", "Path"])
        self.favorites_tree.setColumnWidth(0, 150)
        self.favorites_tree.header().setStretchLastSection(True)
        self.favorites_tree.itemClicked.connect(self.navigate_to_favorite)
        favorites_layout.addWidget(self.favorites_tree)
        
        # Auto-import common locations
        self.auto_import_favorites()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_favorite)
        button_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_favorite)
        button_layout.addWidget(remove_btn)
        
        favorites_layout.addLayout(button_layout)
        layout.addWidget(favorites_group)
        
        # Load saved favorites
        self.load_favorites()
    
    def auto_import_favorites(self):
        """Auto-import common user directories as favorites"""
        home = str(Path.home())
        common_dirs = {
            "Home": home,
            "Desktop": os.path.join(home, "Desktop"),
            "Documents": os.path.join(home, "Documents"),
            "Downloads": os.path.join(home, "Downloads"),
            "Pictures": os.path.join(home, "Pictures"),
            "Music": os.path.join(home, "Music"),
            "Videos": os.path.join(home, "Videos"),
            "Projects": os.path.join(home, "Projects"),
            "Code": os.path.join(home, "Code")
        }
        
        # System locations
        system_dirs = {
            "Root": "/",
            "Boot": "/boot",
            "Media": "/media",
            "Mnt": "/mnt",
            "Opt": "/opt",
            "Usr": "/usr",
            "Var": "/var"
        }
        
        # Add common user directories that exist
        for name, path in common_dirs.items():
            if os.path.exists(path) and os.path.isdir(path):
                self.add_favorite_item(name, path, "user")
        
        # Add system directories that exist
        for name, path in system_dirs.items():
            if os.path.exists(path) and os.path.isdir(path):
                self.add_favorite_item(name, path, "system")
    
    def add_favorite_item(self, name, path, category="user"):
        """Add an item to favorites with appropriate icon"""
        item = QTreeWidgetItem(self.favorites_tree)
        item.setText(0, name)
        item.setText(1, path)
        
        # Set appropriate icon
        if category == "user":
            if "home" in path.lower():
                icon = QIcon.fromTheme("user-home")
            elif "desktop" in path.lower():
                icon = QIcon.fromTheme("user-desktop")
            elif "documents" in path.lower():
                icon = QIcon.fromTheme("folder-documents")
            elif "downloads" in path.lower():
                icon = QIcon.fromTheme("folder-downloads")
            elif "pictures" in path.lower():
                icon = QIcon.fromTheme("folder-pictures")
            elif "music" in path.lower():
                icon = QIcon.fromTheme("folder-music")
            elif "videos" in path.lower():
                icon = QIcon.fromTheme("folder-videos")
            else:
                icon = QIcon.fromTheme("folder")
        else:  # system
            if path == "/":
                icon = QIcon.fromTheme("drive-harddisk")
            elif "boot" in path:
                icon = QIcon.fromTheme("system")
            elif "media" in path or "mnt" in path:
                icon = QIcon.fromTheme("drive-removable-media")
            else:
                icon = QIcon.fromTheme("folder-system")
        
        item.setIcon(0, icon)
        return item
    
    def navigate_to_favorite(self, item):
        """Navigate to selected favorite location"""
        try:
            path = item.text(1)
            if os.path.exists(path):
                index = self.model.index(path)
                if index.isValid():
                    self.navigate_to(index)
                else:
                    self.show_error(f"Invalid path: {path}")
        except Exception as e:
            self.show_error(f"Error navigating to favorite: {str(e)}")
    
    def add_favorite(self):
        """Add current location to favorites"""
        current_path = self.model.filePath(self.current_view.rootIndex())
        name = os.path.basename(current_path) or current_path
        
        # Add to tree
        self.add_favorite_item(name, current_path)
        
        # Save favorites
        self.save_favorites()
    
    def remove_favorite(self):
        """Remove selected favorite"""
        item = self.favorites_tree.currentItem()
        if item:
            self.favorites_tree.takeTopLevelItem(
                self.favorites_tree.indexOfTopLevelItem(item)
            )
            # Save favorites
            self.save_favorites()
    
    def save_favorites(self):
        """Save favorites to config file"""
        favorites = []
        root = self.favorites_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            favorites.append({
                'name': item.text(0),
                'path': item.text(1)
            })
        
        config_dir = os.path.expanduser('~/.config/epy_explorer')
        os.makedirs(config_dir, exist_ok=True)
        
        with open(os.path.join(config_dir, 'favorites.json'), 'w') as f:
            json.dump(favorites, f, indent=2)
    
    def load_favorites(self):
        """Load favorites from config file"""
        config_file = os.path.expanduser('~/.config/epy_explorer/favorites.json')
        if os.path.exists(config_file):
            try:
                with open(config_file) as f:
                    favorites = json.load(f)
                for fav in favorites:
                    if os.path.exists(fav['path']):
                        self.add_favorite_item(fav['name'], fav['path'])
            except Exception as e:
                self.show_error(f"Error loading favorites: {str(e)}")

    def show_error(self, message: str):
        """Show error dialog"""
        QMessageBox.critical(self, "Error", message)

    def close_preview_tab(self, index):
        """Close a preview tab"""
        self.preview_tabs.removeTab(index)

    def toggle_preview(self):
        """Toggle preview pane visibility"""
        if self.preview_tabs.isVisible():
            self.preview_tabs.hide()
            self.preview_toggle.setText("▶ Preview")
            # Store current sizes before collapsing
            self._preview_size = self.right_splitter.sizes()[1]
            sizes = self.right_splitter.sizes()
            sizes[1] = 0  # Collapse preview
            self.right_splitter.setSizes(sizes)
        else:
            self.preview_tabs.show()
            self.preview_toggle.setText("▼ Preview")
            # Restore previous size or use default
            sizes = self.right_splitter.sizes()
            sizes[1] = getattr(self, '_preview_size', 300)  # Default to 300 if not stored
            self.right_splitter.setSizes(sizes)

    def handle_item_double_click(self, index):
        """Handle double click on file tree item"""
        if not index or not index.isValid():
            return
            
        try:
            # Get the path based on the current mode
            path = None
            in_notes_mode = hasattr(self, 'notes_mode_btn') and self.notes_mode_btn.isChecked()
            
            if in_notes_mode and hasattr(self, 'notes_tree_model'):
                # Check which column was double-clicked
                column = index.column()
                
                # If tags column, handle tag editing
                if column == 1:
                    self.edit_note_tags(index)
                    return
                
                # Only process double-clicks on the filename column (0) or path column
                # Get the path from the index
                data = self.notes_tree_model.data(index.siblingAtColumn(0), Qt.ItemDataRole.UserRole)
                
                # Check if the data is a dictionary or a string
                if isinstance(data, dict):
                    # If it's a dictionary, extract the path
                    path = data.get('path', '')
                elif isinstance(data, str):
                    # If it's a string, use it directly
                    path = data
                else:
                    print(f"Unexpected data type from model: {type(data)}")
                    return
                
                if not path:
                    return
                
                # Convert relative path to absolute if needed
                if not os.path.isabs(path) and hasattr(self, 'notes_manager'):
                    notes_path = self.notes_manager.get_notes_vault_path()
                    path = os.path.join(notes_path, path)
            else:
                # File or project mode, get path from file model
                if hasattr(self, 'model'):
                    path = self.model.filePath(index)
                
            if not path or not os.path.exists(path):
                print(f"Path doesn't exist or is invalid: {path}")
                return
                
            if os.path.isdir(path):
                if in_notes_mode:
                    # In notes mode, don't navigate to folder, just expand/collapse
                    expanded = self.tree_view.isExpanded(index)
                    if expanded:
                        self.tree_view.collapse(index)
                    else:
                        self.tree_view.expand(index)
                    return
                else:
                    # In file/project mode, navigate to folder
                    self.navigate_to(index)
            else:
                # For notes mode and markdown files, open in internal editor
                if in_notes_mode and path.lower().endswith('.md'):
                    self.open_in_internal_editor(path)
                    return
                
                # For other files, show in preview pane
                # Check if preview tabs exist before trying to access them
                if not hasattr(self, 'preview_tabs') or self.preview_tabs is None:
                    print("Preview tabs not available")
                    # Fallback to opening with system default application
                    import subprocess
                    subprocess.Popen(['xdg-open', path])
                    return
                    
                # Clear existing preview tabs
                while self.preview_tabs.count() > 0:
                    self.preview_tabs.removeTab(0)
                
                # Show preview for the selected file
                update_preview(self, path)
                
                # Show preview pane if hidden
                if not self.preview_tabs.isVisible():
                    self.toggle_preview()
                
                # Select the first tab if available
                if self.preview_tabs.count() > 0:
                    self.preview_tabs.setCurrentIndex(0)
        except Exception as e:
            import traceback
            print(f"Error handling item double click: {str(e)}")
            traceback.print_exc()  # Print exception details for debugging
            try:
                self.show_error(f"Error opening file: {str(e)}")
            except:
                # If show_error fails, use a simple print
                print(f"Failed to show error dialog: {str(e)}")

    def handle_selection_changed(self):
        """Handle selection change in views"""
        try:
            indexes = self.current_view.selectedIndexes()
            if indexes:
                # Get the path based on the current mode
                in_notes_mode = hasattr(self, 'notes_mode_btn') and self.notes_mode_btn.isChecked()
                
                if in_notes_mode and hasattr(self, 'notes_tree_model'):
                    # We're in notes mode, get path from notes model
                    # Only consider index column 0 (first column)
                    file_indexes = [idx for idx in indexes if idx.column() == 0]
                    if not file_indexes:
                        return
                    
                    data = self.notes_tree_model.data(file_indexes[0], Qt.ItemDataRole.UserRole)
                    
                    # Handle different data types from the model
                    if isinstance(data, dict):
                        path = data.get('path', '')
                    elif isinstance(data, str):
                        path = data
                    else:
                        print(f"Unexpected data type from model: {type(data)}")
                        return
                        
                    if not path:
                        return
                    
                    # Convert relative path to absolute
                    if not os.path.isabs(path) and hasattr(self, 'notes_manager'):
                        notes_path = self.notes_manager.get_notes_vault_path()
                        path = os.path.join(notes_path, path)
                else:
                    # File or project mode, get path from file model
                    # Filter out duplicate selections (only use the first column index)
                    if len(indexes) > 0:
                        # Get only indexes from the first column to avoid duplicates
                        first_column_indexes = [idx for idx in indexes if idx.column() == 0]
                        if first_column_indexes:
                            path = self.model.filePath(first_column_indexes[0])
                        else:
                            return
                    else:
                        return
                
                if not path or not os.path.exists(path):
                    return
                    
                # Only update preview if not a directory
                if not os.path.isdir(path):
                    # Clear existing preview tabs
                    while self.preview_tabs.count() > 0:
                        self.preview_tabs.removeTab(0)
                    
                    # Show preview for the selected file
                    update_preview(self, path)
                    
                    # Show preview pane if hidden
                    if not self.preview_tabs.isVisible():
                        self.toggle_preview()
                    
                    # Select the first tab if available
                    if self.preview_tabs.count() > 0:
                        self.preview_tabs.setCurrentIndex(0)
        except Exception as e:
            self.show_error(f"Error updating preview: {str(e)}")
            import traceback
            traceback.print_exc()  # Print exception details for debugging

    def show_context_menu(self, position):
        """Show context menu for file tree"""
        menu = QMenu()
        indexes = self.current_view.selectedIndexes()
        
        if not indexes:
            return
            
        # Get selected paths
        selected_paths = []
        for index in indexes:
            if index.column() == 0:  # Only process first column to avoid duplicates
                path = self.model.filePath(index)
                selected_paths.append(path)
        
        if not selected_paths:
            return
            
        # Single item selected
        if len(selected_paths) == 1:
            path = selected_paths[0]
            
            # Basic file operations
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self.handle_item_double_click(indexes[0]))
            
            # For files, add "Open with..." submenu
            if not os.path.isdir(path):
                open_with_menu = menu.addMenu("Open with...")
                apps = self.get_system_applications(path)
                for app in apps:
                    action = open_with_menu.addAction(app['name'])
                    if 'icon' in app:
                        action.setIcon(QIcon.fromTheme(app['icon']))
                    action.triggered.connect(
                        lambda checked, a=app: self.open_with(path, a)
                    )
            
            if os.path.isdir(path):
                open_terminal_action = menu.addAction("Open in Terminal")
                open_terminal_action.triggered.connect(lambda: self.open_in_terminal(path))
                
                # Add launch submenu for directories
                menu.addSeparator()
                launch_menu = menu.addMenu("Launch")
                
                # Add detected configurations
                configs = self.launch_manager.detect_project(path)
                if configs:
                    for config in configs:
                        action = launch_menu.addAction(config['name'])
                        action.setIcon(QIcon.fromTheme(config.get('icon', 'system-run')))
                        action.setToolTip(config.get('description', ''))
                        action.triggered.connect(
                            lambda checked, c=config: self.launch_manager.launch_project(path, c)
                        )
                    launch_menu.addSeparator()
                
                # Add saved configurations
                saved_configs = self.launch_manager.get_launches(path)
                if saved_configs:
                    for config in saved_configs:
                        action = launch_menu.addAction(config['name'])
                        action.setIcon(QIcon.fromTheme(config.get('icon', 'system-run')))
                        action.setToolTip(config.get('description', ''))
                        action.triggered.connect(
                            lambda checked, c=config: self.launch_manager.launch_project(path, c)
                        )
                    launch_menu.addSeparator()
                
                # Add manage option
                manage_action = launch_menu.addAction("Manage Configurations...")
                manage_action.triggered.connect(lambda: self.show_launch_manager(path))
                
                # Add find duplicates action for directories
                menu.addSeparator()
                find_duplicates_action = menu.addAction("Find Duplicate Files")
                find_duplicates_action.triggered.connect(lambda: self.find_duplicates(path))
            
            menu.addSeparator()
            
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(lambda: self.file_ops.copy_selected_files())
            
            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self.file_ops.cut_selected_files())
            
            if self.clipboard_files:
                paste_action = menu.addAction("Paste")
                paste_action.triggered.connect(lambda: self.file_ops.paste_files())
            
            menu.addSeparator()
            
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self.file_ops.delete_selected_files())
            
            rename_action = menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self.file_ops.rename_file(indexes[0]))
            
            # Add to favorites
            menu.addSeparator()
            add_favorite_action = menu.addAction("Add to Favorites")
            add_favorite_action.triggered.connect(self.add_favorite)
            
        # Exactly two files selected
        elif len(selected_paths) == 2 and all(os.path.isfile(p) for p in selected_paths):
            # Add compare action at the top
            compare_action = menu.addAction("Compare Files")
            compare_action.triggered.connect(lambda: self.compare_files(selected_paths[0], selected_paths[1]))
            
            menu.addSeparator()
            
            # Basic multi-select operations
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(lambda: self.file_ops.copy_selected_files())
            
            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self.file_ops.cut_selected_files())
            
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self.file_ops.delete_selected_files())
            
        # Multiple items selected
        else:
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(lambda: self.file_ops.copy_selected_files())
            
            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self.file_ops.cut_selected_files())
            
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self.file_ops.delete_selected_files())
        
        menu.exec(self.current_view.viewport().mapToGlobal(position))

    def compare_files(self, file1, file2):
        """Open file comparison dialog"""
        from .compare_dialog import CompareDialog
        dialog = CompareDialog(self, file1, file2)
        dialog.exec()

    def find_duplicates(self, directory):
        """Open duplicate finder dialog for directory"""
        dialog = DuplicateDialog(self)
        dialog.scan_directory(directory)
        dialog.exec()
        
    def find_duplicate_notes(self):
        """Find duplicate notes in the notes vault (compatibility method)"""
        if hasattr(self, 'notes_manager'):
            notes_path = self.notes_manager.get_notes_vault_path()
            self.find_duplicates(notes_path)
        else:
            self.show_error("Notes manager not available")

    def switch_mode(self, mode):
        """Switch between file explorer, project, and notes modes"""
        if mode == self.current_mode:
            return
        
        print(f"Switching mode from {self.current_mode} to {mode}")
        
        # Clear selection
        old_path = self.get_current_path()
        
        # Update button state
        self.file_mode_btn.setChecked(mode == 'file')
        self.project_mode_btn.setChecked(mode == 'project')
        self.notes_mode_btn.setChecked(mode == 'notes')
        
        # Show/hide appropriate views
        if mode == 'file':
            # Switch to file explorer mode
            self.tree_view.setModel(self.model)
            self.list_view.setModel(self.model)
            self.file_ops.paste_button = self.paste_button  # Reconnect
            self.file_ops.files_dropped.connect(self.refresh_view)
            
            # Show file toolbar buttons
            self.toggle_toolbar_visibility(file_visible=True, project_visible=False, notes_visible=False)
            
            # Hide test view in file mode
            if hasattr(self, 'test_view'):
                self.test_view.hide()
                
            # Update project state
            self.project_state.setText("")
            self.refresh_view()
            
        elif mode == 'project':
            # Switch to project mode
            self.setup_project_mode()
            
            # Show project toolbar buttons
            self.toggle_toolbar_visibility(file_visible=False, project_visible=True, notes_visible=False)
            
            # Show test view in project mode
            if hasattr(self, 'test_view'):
                self.test_view.show()
                
            # Update project state
            project_path = os.getcwd()
            self.project_state.setText(f"Project: {os.path.basename(project_path)} ({project_path})")
            
        elif mode == 'notes':
            # Create notes manager if it doesn't exist
            if not hasattr(self, 'notes_manager'):
                self.notes_manager = NotesManager(self)
                # Connect to the signal
                self.notes_manager.notes_loaded.connect(self.on_notes_loaded)
            
            # Initialize notes model and view
            self.view_stack.setCurrentWidget(self.tree_view)
            self.toggle_toolbar_visibility(file_visible=False, project_visible=False, notes_visible=True)
            
            # Update project state
            notes_path = self.notes_manager.get_notes_vault_path()
            self.project_state.setText(f"Notes Vault: {os.path.basename(notes_path)} ({notes_path})")
            
            # Hide test view in notes mode
            if hasattr(self, 'test_view'):
                self.test_view.hide()
            
            # Let the notes manager handle loading and progress display
            # This will trigger the on_notes_loaded callback when complete
            # Use fast_mode=True to speed up loading when possible
            self.notes_manager.setup_notes_mode(self, fast_mode=True)
        
        # Update mode
        self.current_mode = mode
        
        # Only try to navigate if we're not in notes mode, since navigating while switching
        # to notes mode can cause crashes (address bar may be temporarily invalid)
        if old_path and mode != 'notes':
            try:
                # Make sure the current path is valid
                if os.path.exists(old_path):
                    self.navigate_to_address(old_path)
                else:
                    print(f"Previous path no longer exists: {old_path}")
            except Exception as e:
                print(f"Could not navigate to {old_path} in {mode} mode: {e}")

    def on_notes_loaded(self, notes_tree_model):
        """Called when notes are loaded asynchronously"""
        try:
            if not notes_tree_model:
                print("Error: Notes model is None")
                return
            
            print("Notes model loaded, updating UI...")
            
            # Store reference to the model
            self.notes_tree_model = notes_tree_model
            
            # Set up the views with the new model
            self.tree_view.setModel(notes_tree_model)
            self.list_view.setModel(notes_tree_model)
            
            # Set column widths and visibility
            self.tree_view.setColumnWidth(0, 250)  # Name column
            self.tree_view.setColumnWidth(1, 200)  # Tags column
            # Path column should stretch
            self.tree_view.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            
            # Set up UI components for notes mode
            self.setup_notes_mode_ui()
            
            # Make sure the notes view is fully refreshed but collapsed by default
            self.tree_view.collapseAll()
            self.tree_view.viewport().update()
            self.list_view.viewport().update()
            
            # Update UI to reflect that loading is complete
            print("Notes loaded and UI updated")
        
        except Exception as e:
            print(f"Error in on_notes_loaded: {str(e)}")
            import traceback
            traceback.print_exc()

    def setup_notes_mode_ui(self):
        """Set up UI elements specific to notes mode"""
        # Setup tree and list view properties for notes mode
        if hasattr(self, 'tree_view') and hasattr(self, 'notes_model'):
            # Update tree view to use custom view
            self.tree_view.expandToDepth(0)
            
            # Set up mouse press event for editing notes
            self.tree_view.mousePressEvent = self.handle_notes_mouse_press
            
            # Setup list view for tags filtering
            if hasattr(self, 'notes_tags_list'):
                # Add tags from model
                self.update_tags_list()
                
        # Enable notes-specific buttons
        for btn in [self.tag_button, self.find_dupes_button, self.sort_button, self.search_notes_button]:
            if hasattr(self, btn.__str__()):
                btn.setEnabled(True)
                
    def update_tags_list(self):
        """Update the tags list based on notes model"""
        if hasattr(self, 'notes_model') and hasattr(self, 'notes_tags_list'):
            # Clear existing tags
            self.tag_model = QStandardItemModel()
            self.notes_tags_list.setModel(self.tag_model)
            
            # Add "All" item 
            all_item = QStandardItem("All Notes")
            all_item.setData("all", Qt.ItemDataRole.UserRole)
            self.tag_model.appendRow(all_item)
            
            # Get tags from model
            if hasattr(self.notes_model, 'tags_map'):
                # Add tags sorted alphabetically
                for tag in sorted(self.notes_model.tags_map.keys()):
                    tag_item = QStandardItem(tag)
                    tag_item.setData(tag, Qt.ItemDataRole.UserRole)
                    tag_item.setData(len(self.notes_model.tags_map[tag]), Qt.ItemDataRole.UserRole + 1)
                    self.tag_model.appendRow(tag_item)
                    
    def refresh_notes_view(self):
        """Refresh the notes view without reloading the model"""
        if hasattr(self, 'notes_model'):
            # Just refresh the view
            self.tree_view.reset()
            self.list_view.reset()
            print("Notes view refreshed")
        else:
            # If no model exists, do a full setup
            if hasattr(self, 'notes_manager'):
                self.notes_manager.setup_notes_mode(self)

    def setup_views(self):
        """Set up the file views"""
        # Create container for navigation and views
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)
        
        # Add navigation bar
        nav_widget = self.setup_navigation()
        container_layout.addWidget(nav_widget)
        
        # Create view container
        self.view_stack = QStackedWidget()
        
        # Configure tree view
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.model)
        self.tree_view.setRootIndex(self.model.index(QDir.rootPath()))
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        
        # Configure header sizing for better display
        header = self.tree_view.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name column stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Size column fits content
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type column fits content
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Date column fits content
        
        self.tree_view.doubleClicked.connect(self.handle_item_double_click)
        self.tree_view.selectionModel().selectionChanged.connect(self.handle_selection_changed)
        
        # Configure list view
        self.list_view = QListView()
        self.list_view.setModel(self.model)
        self.list_view.setRootIndex(self.model.index(QDir.rootPath()))
        self.list_view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.list_view.setViewMode(QListView.ViewMode.IconMode)
        self.list_view.setIconSize(QSize(48, 48))
        self.list_view.setGridSize(QSize(100, 80))
        self.list_view.setSpacing(10)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setWrapping(True)
        self.list_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_view.setWordWrap(True)
        self.list_view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.list_view.doubleClicked.connect(self.handle_item_double_click)
        self.list_view.selectionModel().selectionChanged.connect(self.handle_selection_changed)
        
        # Add views to stack
        self.view_stack.addWidget(self.tree_view)
        self.view_stack.addWidget(self.list_view)
        
        # Add view stack to container
        container_layout.addWidget(self.view_stack)
        
        # Use tree view by default
        self.current_view = self.tree_view
        self.current_mode = 'list'
        
        return container

    def setup_drives(self):
        """Set up the drives section"""
        drives_group = QGroupBox("Drives")
        drives_layout = QVBoxLayout(drives_group)
        drives_layout.setContentsMargins(4, 4, 4, 4)
        drives_layout.setSpacing(2)
        
        self.drives_list = QTreeWidget()
        self.drives_list.setHeaderLabels(["Name", "Type"])
        self.drives_list.itemClicked.connect(self.mount_drive)
        self.drives_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.drives_list.header().setStretchLastSection(False)
        self.drives_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Make name column stretch
        drives_layout.addWidget(self.drives_list)
        
        # Refresh drives button
        refresh_drives = QPushButton("Refresh")
        refresh_drives.clicked.connect(self.refresh_drives)
        drives_layout.addWidget(refresh_drives)
        
        return drives_group
        
    def refresh_drives(self):
        """Refresh the list of available drives"""
        self.drives_list.clear()
        
        # Get list of mounted drives
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
            self.show_error(f"Error refreshing drives: {str(e)}")
            
    def mount_drive(self, item):
        """Mount a drive when clicked"""
        drive_info = item.data(0, Qt.ItemDataRole.UserRole)
        if drive_info and os.path.exists(drive_info['mountpoint']):
            index = self.model.index(drive_info['mountpoint'])
            self.navigate_to(index)
            
    def navigate_to(self, index, add_to_history=True):
        """Navigate to a location in the file system"""
        try:
            if not index.isValid():
                return
                
            path = self.model.filePath(index)
            if not os.path.exists(path):
                return
                
            # Update both views
            self.tree_view.setRootIndex(index)
            self.list_view.setRootIndex(index)
            
                # Update address bar safely
            if hasattr(self, 'address_bar') and self.address_bar is not None and not sip.isdeleted(self.address_bar):
                self.address_bar.setText(path)
            
            # Add to navigation history
            if add_to_history:
                # Remove any forward history
                if self.nav_current < len(self.nav_history) - 1:
                    self.nav_history = self.nav_history[:self.nav_current + 1]
                
                self.nav_history.append(index)
                self.nav_current = len(self.nav_history) - 1
                
                # Update navigation buttons safely
            if hasattr(self, 'back_btn') and self.back_btn is not None and not sip.isdeleted(self.back_btn):
                self.back_btn.setEnabled(self.nav_current > 0)
            if hasattr(self, 'forward_btn') and self.forward_btn is not None and not sip.isdeleted(self.forward_btn):
                self.forward_btn.setEnabled(self.nav_current < len(self.nav_history) - 1)
                    
        except Exception as e:
            self.show_error(f"Error navigating to location: {str(e)}")

    def setup_navigation(self):
        """Set up navigation bar"""
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        
        # Back/Forward buttons
        self.back_btn = QPushButton("←")
        self.back_btn.setFixedWidth(30)
        self.back_btn.clicked.connect(self.navigate_back)
        self.back_btn.setEnabled(False)
        nav_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("→")
        self.forward_btn.setFixedWidth(30)
        self.forward_btn.clicked.connect(self.navigate_forward)
        self.forward_btn.setEnabled(False)
        nav_layout.addWidget(self.forward_btn)
        
        # Up button
        self.up_btn = QPushButton("↑")
        self.up_btn.setFixedWidth(30)
        self.up_btn.clicked.connect(self.navigate_up)
        nav_layout.addWidget(self.up_btn)
        
        # Address bar
        self.address_bar = AddressBar()
        self.address_bar.setParent(nav_widget)  # Ensure proper parent-child relationship
        self.address_bar.returnPressed.connect(self.navigate_to_address)
        nav_layout.addWidget(self.address_bar)
        
        # Refresh button
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedWidth(30)
        refresh_btn.clicked.connect(self.refresh_view)
        nav_layout.addWidget(refresh_btn)
        
        return nav_widget

    def navigate_back(self):
        """Navigate to previous location in history"""
        if self.nav_current > 0:
            self.nav_current -= 1
            self.navigate_to(self.nav_history[self.nav_current], False)

    def navigate_forward(self):
        """Navigate to next location in history"""
        if self.nav_current < len(self.nav_history) - 1:
            self.nav_current += 1
            self.navigate_to(self.nav_history[self.nav_current], False)

    def navigate_up(self):
        """Navigate to parent directory"""
        current_path = self.model.filePath(self.current_view.rootIndex())
        parent_path = os.path.dirname(current_path)
        if parent_path != current_path:  # Not at root
            index = self.model.index(parent_path)
            self.navigate_to(index)

    def navigate_to_address(self, address=None):
        """Navigate to the address in the address bar"""
        try:
            # Don't attempt to navigate in notes mode, as navigation works differently
            if self.current_mode == 'notes':
                print("Navigation in notes mode uses different mechanism")
                return
                
            # Get address from address bar if not provided
            if address is None:
                if not hasattr(self, 'address_bar') or self.address_bar is None or sip.isdeleted(self.address_bar):
                    print("Address bar not available")
                    return
                address = self.address_bar.text()
                
            # Check if path exists
            if not os.path.exists(address):
                print(f"Cannot navigate to non-existent path: {address}")
                return
                
            # Navigate to the address
            self.model.setRootPath(address)
            self.tree_view.setRootIndex(self.model.index(address))
            self.list_view.setRootIndex(self.model.index(address))
            
            # Update address bar safely
            self.update_address_bar()
            
            # Add to history
            if address not in self.file_history:
                self.file_history.append(address)
                self.history_index = len(self.file_history) - 1
        except Exception as e:
            print(f"Error in navigate_to_address: {e}")
            import traceback
            traceback.print_exc()
            
    def update_address_bar(self):
        """Update address bar with current path"""
        try:
            if not hasattr(self, 'address_bar') or self.address_bar is None or sip.isdeleted(self.address_bar):
                print("Address bar not available for updating")
                return
                
            current_path = self.model.filePath(self.current_view.rootIndex())
            self.address_bar.setText(current_path)
        except Exception as e:
            print(f"Error updating address bar: {e}")

    def refresh_view(self):
        """Refresh the current view"""
        self.model.layoutChanged.emit()
        self.current_view.viewport().update()

    def get_current_path(self):
        """Get current working directory"""
        if self.project_mode_btn.isChecked():
            return os.getcwd()
        else:
            return self.model.filePath(self.current_view.rootIndex())

    def setup_project_mode(self):
        """Initialize project mode"""
        self.project_model = QStandardItemModel()
        self.project_model.setHorizontalHeaderLabels(['Name', 'Type', 'Status'])
        
        # Try to find project root (look for common project files)
        current_dir = os.getcwd()
        project_root = current_dir
        
        # Check for common project files/directories
        project_indicators = [
            '.git', '.hg', '.svn',  # VCS
            'pyproject.toml', 'setup.py', 'requirements.txt',  # Python
            'package.json', 'node_modules',  # Node.js
            'Cargo.toml',  # Rust
            'CMakeLists.txt', 'Makefile',  # C/C++
            '.epy_project'  # Our own project file
        ]
        
        # Look for project root
        while current_dir != '/':
            for indicator in project_indicators:
                if os.path.exists(os.path.join(current_dir, indicator)):
                    project_root = current_dir
                    break
            if project_root != current_dir:
                break
            current_dir = os.path.dirname(current_dir)
        
        # Load project tree
        root_item = self.project_model.invisibleRootItem()
        self.load_directory(root_item, project_root)
        
        # Update project state
        self.project_state.setText(f"Project: {os.path.basename(project_root)} ({project_root})")
        
        # Set up context menu
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_project_context_menu)

    def load_directory(self, parent_item, dir_path):
        """Recursively load directory contents into project tree"""
        try:
            # Sort entries: directories first, then files
            entries = os.listdir(dir_path)
            dirs = []
            files = []
            
            for entry in entries:
                full_path = os.path.join(dir_path, entry)
                if os.path.isdir(full_path):
                    # Skip common ignore directories
                    if entry not in ['.git', '.svn', '__pycache__', 'node_modules', 'target', 'build']:
                        dirs.append(entry)
                else:
                    files.append(entry)
            
            # Add directories
            for dir_name in sorted(dirs):
                dir_path_full = os.path.join(dir_path, dir_name)
                dir_item = QStandardItem(QIcon.fromTheme('folder'), dir_name)
                dir_item.setData(dir_path_full, Qt.ItemDataRole.UserRole)
                type_item = QStandardItem('Directory')
                status_item = QStandardItem('')
                
                parent_item.appendRow([dir_item, type_item, status_item])
                self.load_directory(dir_item, dir_path_full)
            
            # Add files
            for file_name in sorted(files):
                file_path_full = os.path.join(dir_path, file_name)
                ext = os.path.splitext(file_name)[1].lower()
                
                # Get file icon based on type
                if ext in ['.py', '.pyw']:
                    icon = QIcon.fromTheme('text-x-python')
                    file_type = 'Python Source'
                elif ext in ['.c', '.cpp', '.h', '.hpp']:
                    icon = QIcon.fromTheme('text-x-c++src')
                    file_type = 'C/C++ Source'
                elif ext in ['.rs']:
                    icon = QIcon.fromTheme('text-x-rust')
                    file_type = 'Rust Source'
                elif ext in ['.js', '.ts']:
                    icon = QIcon.fromTheme('text-x-javascript')
                    file_type = 'JavaScript/TypeScript'
                else:
                    icon = QIcon.fromTheme('text-x-generic')
                    file_type = 'File'
                
                file_item = QStandardItem(icon, file_name)
                file_item.setData(file_path_full, Qt.ItemDataRole.UserRole)
                type_item = QStandardItem(file_type)
                status_item = QStandardItem('')  # TODO: Add VCS status
                
                parent_item.appendRow([file_item, type_item, status_item])
                
        except Exception as e:
            self.show_error(f"Error loading directory {dir_path}: {str(e)}")

    def show_project_context_menu(self, position):
        """Show context menu for project view"""
        menu = QMenu()
        
        # Get selected item
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            # No item selected, show only refresh option
            refresh_action = menu.addAction("Refresh Project Tree")
            refresh_action.triggered.connect(self.refresh_project_view)
            menu.exec(self.tree_view.mapToGlobal(position))
            return

        # Get the path based on current mode
        if self.project_mode_btn.isChecked() and hasattr(self, 'project_model'):
            item = self.project_model.itemFromIndex(index)
            if not item:
                return
            path = item.data(Qt.ItemDataRole.UserRole)
        else:
            path = self.model.filePath(index)

        if not path:
            return

        # Add menu items based on item type
        if os.path.isdir(path):
            # Directory options
            if path != os.getcwd():  # Don't show for current project root
                set_project_action = menu.addAction("Set as Project Directory")
                set_project_action.setToolTip("Make this directory the root of your project")
                set_project_action.triggered.connect(lambda: self.set_project_root(path))
                menu.addSeparator()

            # Common directory actions
            open_action = menu.addAction("Open in File Explorer")
            open_action.triggered.connect(lambda: self.navigate_to(self.model.index(path)))
            
            terminal_action = menu.addAction("Open in Terminal")
            terminal_action.triggered.connect(lambda: self.open_in_terminal(path))
            
            # Add find duplicates action for directories
            menu.addSeparator()
            find_duplicates_action = menu.addAction("Find Duplicate Files")
            find_duplicates_action.triggered.connect(lambda: self.find_duplicates(path))

            # Add commands submenu
            menu.addSeparator()
            commands_menu = menu.addMenu("Run Command")
            
            # Add recent commands
            recent_commands = self.command_manager.get_recent_commands(5)
            if recent_commands:
                for name, cmd in recent_commands.items():
                    action = commands_menu.addAction(f"{name} - {cmd['description']}")
                    action.triggered.connect(
                        lambda checked, n=name: self.command_manager.run_command(n, path)
                    )
                commands_menu.addSeparator()
            
            # Add "Manage Commands" option
            manage_commands = commands_menu.addAction("Manage Commands...")
            manage_commands.triggered.connect(self.show_command_manager)
            
            # Add "New Command" option
            new_command = commands_menu.addAction("New Command...")
            new_command.triggered.connect(lambda: self.show_command_manager(path))

        else:
            # File options
            open_action = menu.addAction("Open File")
            open_action.triggered.connect(lambda: self.handle_item_double_click(index))
            
            # Add "Open with..." submenu for files
            open_with_menu = menu.addMenu("Open with...")
            apps = self.get_system_applications(path)
            for app in apps:
                action = open_with_menu.addAction(app['name'])
                if 'icon' in app:
                    action.setIcon(QIcon.fromTheme(app['icon']))
                action.triggered.connect(
                    lambda checked, a=app: self.open_with(path, a)
                )
            
            show_in_explorer = menu.addAction("Show in File Explorer")
            show_in_explorer.triggered.connect(lambda: self.navigate_to(self.model.index(os.path.dirname(path))))
            
            # Add commands submenu for files too
            menu.addSeparator()
            commands_menu = menu.addMenu("Run Command")
            
            # Add recent commands
            recent_commands = self.command_manager.get_recent_commands(5)
            if recent_commands:
                for name, cmd in recent_commands.items():
                    action = commands_menu.addAction(f"{name} - {cmd['description']}")
                    action.triggered.connect(
                        lambda checked, n=name: self.command_manager.run_command(n, os.path.dirname(path))
                    )
                commands_menu.addSeparator()
            
            # Add "Manage Commands" option
            manage_commands = commands_menu.addAction("Manage Commands...")
            manage_commands.triggered.connect(self.show_command_manager)
            
            # Add "New Command" option
            new_command = commands_menu.addAction("New Command...")
            new_command.triggered.connect(lambda: self.show_command_manager(os.path.dirname(path)))

        # Always add refresh option
        menu.addSeparator()
        refresh_action = menu.addAction("Refresh Project Tree")
        refresh_action.triggered.connect(self.refresh_project_view)
        
        menu.exec(self.tree_view.mapToGlobal(position))

    def show_command_manager(self, initial_path=None):
        """Show command manager dialog"""
        from .command_dialog import CommandDialog
        dialog = CommandDialog(self)
        if initial_path:
            dialog.add_command()  # Start with add command dialog if path provided
        dialog.exec()

    def set_project_root(self, path):
        """Set new project root"""
        if not os.path.isdir(path):
            self.show_error("Selected path is not a directory")
            return
            
        try:
            # Check if path exists and is accessible
            if not os.access(path, os.R_OK):
                self.show_error("Cannot access selected directory")
                return
                
            # Change working directory
            os.chdir(path)
            
            # Switch to project mode if not already
            if not self.project_mode_btn.isChecked():
                self.switch_mode('project')
            else:
                self.setup_project_mode()
                
            # Update project state
            self.project_state.setText(f"Project: {os.path.basename(path)} ({path})")
            
        except Exception as e:
            self.show_error(f"Error setting project directory: {str(e)}")

    def open_project_item(self, path):
        """Open project item (file or directory)"""
        if os.path.isfile(path):
            # TODO: Implement file opening based on type
            pass
        elif os.path.isdir(path):
            self.set_project_root(path)

    def switch_view_mode(self, mode):
        """Switch between list and grid view modes"""
        if mode == self.current_view_mode:
            return
        
        if mode == 'list':
            self.list_view_btn.setChecked(True)
            self.grid_view_btn.setChecked(False)
            self.view_stack.setCurrentWidget(self.tree_view)
            self.current_view = self.tree_view
        else:
            self.list_view_btn.setChecked(False)
            self.grid_view_btn.setChecked(True)
            self.view_stack.setCurrentWidget(self.list_view)
            self.current_view = self.list_view
            
        self.current_view_mode = mode
            
    def toggle_toolbar_visibility(self, file_visible=True, project_visible=False, notes_visible=False):
        """Toggle visibility of toolbar button groups"""
        # File operations toolbar buttons
        self.copy_button.setVisible(file_visible)
        self.cut_button.setVisible(file_visible)
        self.paste_button.setVisible(file_visible)
        
        # Project operations toolbar buttons
        self.vcs_button.setVisible(project_visible)
        self.build_button.setVisible(project_visible)
        self.smelt_button.setVisible(project_visible)
        self.cast_button.setVisible(project_visible)
        self.forge_button.setVisible(project_visible)
        self.contract_button.setVisible(project_visible)
        self.doc_button.setVisible(project_visible)
        self.test_button.setVisible(project_visible)
        
        # Notes operations toolbar buttons
        self.tag_button.setVisible(notes_visible)
        self.find_dupes_button.setVisible(notes_visible)
        self.sort_button.setVisible(notes_visible)
        self.search_notes_button.setVisible(notes_visible)

    def open_with(self, file_path, app_info):
        """Open a file with a specified application"""
        try:
            if not os.path.exists(file_path):
                self.show_error(f"File not found: {file_path}")
                return
                
            command = app_info['command']
            
            if command == 'internal':
                # Open in our internal text editor
                self.open_in_internal_editor(file_path)
                return
                
            if command == 'custom':
                # Show file dialog to choose application
                from PyQt6.QtWidgets import QFileDialog
                app_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Choose Application",
                    "/usr/bin",
                    "Applications (*);;All Files (*)"
                )
                
                if not app_path:
                    return
                    
                command = app_path
            
            # Launch the application with the file
            subprocess.Popen([command, file_path])
            
        except Exception as e:
            self.show_error(f"Error opening file: {str(e)}")
    
    def open_in_internal_editor(self, file_path):
        """Open a file in the internal text editor"""
        try:
            # Check if file is text
            is_text = True
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Try to read a bit of the file to check if it's text
                    f.read(1024)
            except UnicodeDecodeError:
                is_text = False
            
            if not is_text:
                self.show_error(f"Cannot open binary file in text editor: {file_path}")
                return
            
            # Create the text editor dialog
            from .text_editor import TextEditorDialog
            editor = TextEditorDialog(self, file_path)
            
            # If it's a markdown file and we're in notes mode, add tags editor
            if file_path.lower().endswith('.md') and hasattr(self, 'notes_mode_btn') and self.notes_mode_btn.isChecked():
                self.setup_markdown_editor_tags(editor, file_path)
                
            # Show the editor
            editor.exec()
            
            # Refresh notes view if we're in notes mode and a note was edited
            if file_path.lower().endswith('.md') and hasattr(self, 'notes_mode_btn') and self.notes_mode_btn.isChecked():
                if hasattr(self, 'notes_manager'):
                    self.notes_manager.refresh_notes(self)
                    
        except Exception as e:
            self.show_error(f"Error opening in internal editor: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def setup_markdown_editor_tags(self, editor, file_path):
        """Add tags editing capability to the markdown editor"""
        try:
            # Extract existing tags from file
            tags = []
            if hasattr(self, 'notes_manager'):
                # Use the existing tag extraction method
                tags = self.notes_manager._extract_tags_from_file(file_path)
            
            # Add tags editor to the dialog
            from PyQt6.QtWidgets import QLineEdit, QLabel, QHBoxLayout
            tags_layout = QHBoxLayout()
            tags_layout.addWidget(QLabel("Tags:"))
            tags_edit = QLineEdit()
            tags_edit.setText(", ".join(tags))
            tags_edit.setPlaceholderText("Enter tags separated by commas")
            tags_layout.addWidget(tags_edit)
            
            # Get the main layout
            main_layout = editor.layout()
            # Insert the tags layout before the editor
            main_layout.insertLayout(1, tags_layout)
            
            # Store reference to tags edit field
            editor.tags_edit = tags_edit
            
            # Override the save method to also save tags
            original_save = editor.save_file
            
            def save_with_tags():
                # First call the original save method
                result = original_save()
                if result:
                    # Then update the frontmatter tags
                    self.update_markdown_frontmatter_tags(file_path, tags_edit.text())
                return result
            
            # Replace the save method
            editor.save_file = save_with_tags
            
        except Exception as e:
            print(f"Error setting up markdown tags editor: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def update_markdown_frontmatter_tags(self, file_path, tags_text):
        """Update the tags in a markdown file's frontmatter"""
        try:
            # Parse comma-separated tags
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if file has frontmatter
            has_frontmatter = content.startswith('---')
            
            if has_frontmatter:
                # Find the end of frontmatter
                end_index = content.find('---', 3)
                if end_index > 0:
                    frontmatter = content[3:end_index].strip()
                    rest_of_content = content[end_index:]
                    
                    # Check if frontmatter has tags
                    has_tags = re.search(r'^tags:', frontmatter, re.MULTILINE) is not None
                    
                    if has_tags:
                        # Replace existing tags
                        new_frontmatter = re.sub(
                            r'^tags:.*?$([\s\S]*?)(^[^-\s]|\Z)',
                            f'tags: {tags}\n\\2',
                            frontmatter,
                            flags=re.MULTILINE
                        )
                    else:
                        # Add tags to frontmatter
                        new_frontmatter = f"{frontmatter}\ntags: {tags}"
                    
                    # Write updated content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(f"---\n{new_frontmatter}\n{rest_of_content}")
            else:
                # No frontmatter, add one
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"---\ntags: {tags}\n---\n\n{content}")
                    
            print(f"Updated tags for {file_path}: {tags}")
            
        except Exception as e:
            print(f"Error updating markdown tags: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def refresh_project_view(self):
        """Refresh the project view"""
        self.setup_project_mode()

    def handle_notes_mouse_press(self, event):
        """Custom handler for mouse press events in notes mode"""
        if not hasattr(self, 'notes_mode_btn') or not self.notes_mode_btn.isChecked():
            # If not in notes mode, use the default handler
            QTreeView.mousePressEvent(self.tree_view, event)
            return
        
        # Get the index at the cursor position
        index = self.tree_view.indexAt(event.position().toPoint())
        if not index.isValid():
            # If clicking on empty area, use default handler
            QTreeView.mousePressEvent(self.tree_view, event)
            return
        
        # Determine which column was clicked
        column = index.column()
        
        # Handle click based on column
        if column == 0:  # Filename column
            if event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                # Ctrl+Click on title - edit the title
                self.edit_note_title(index)
            else:
                # Normal click - just select the item
                QTreeView.mousePressEvent(self.tree_view, event)
        elif column == 1:  # Tags column
            # Edit tags when clicking on the tags column
            self.edit_note_tags(index)
        else:
            # For other columns, use default behavior
            QTreeView.mousePressEvent(self.tree_view, event)

    def edit_note_title(self, index):
        """Edit the title of a note"""
        try:
            # Get the path of the note
            data = self.notes_tree_model.data(index, Qt.ItemDataRole.UserRole)
            
            # Handle different data types from the model
            if isinstance(data, dict):
                path = data.get('path', '')
            elif isinstance(data, str):
                path = data
            else:
                print(f"Unexpected data type from model: {type(data)}")
                return
            
            if not path:
                print("No path found for note")
                return
            
            # Convert relative path to absolute if needed
            if not os.path.isabs(path) and hasattr(self, 'notes_manager'):
                notes_path = self.notes_manager.get_notes_vault_path()
                abs_path = os.path.join(notes_path, path)
            else:
                abs_path = path
            
            # Check if it's a file and exists
            if not os.path.isfile(abs_path) or not os.path.exists(abs_path):
                print(f"Not a valid file: {abs_path}")
                return
            
            # Get current filename
            dirname, filename = os.path.split(abs_path)
            
            # Create an input dialog for the new title
            title, ok = QInputDialog.getText(
                self, 
                "Edit Note Title",
                "Enter new title for the note:",
                QLineEdit.EchoMode.Normal,
                os.path.splitext(filename)[0]  # Show filename without extension
            )
            
            if ok and title:
                # Create new path with the new title
                new_filename = title + os.path.splitext(filename)[1]  # Keep extension
                new_path = os.path.join(dirname, new_filename)
                
                # Rename the file
                try:
                    os.rename(abs_path, new_path)
                    print(f"Renamed note from {filename} to {new_filename}")
                    
                    # Refresh notes model
                    if hasattr(self, 'notes_manager'):
                        self.notes_manager.refresh_notes(self)
                except Exception as e:
                    self.show_error(f"Error renaming note: {str(e)}")
                    print(f"Error renaming note: {str(e)}")
                
        except Exception as e:
            print(f"Error editing note title: {str(e)}")
            self.show_error(f"Error editing note title: {str(e)}")

    def edit_note_tags(self, index):
        """Edit the tags of a note directly in the tree view"""
        try:
            if not hasattr(self, 'notes_tree_model'):
                return
            
            # Store the index being edited
            self.editing_tags_index = index
            
            # Get the rectangle of the cell
            rect = self.tree_view.visualRect(index)
            
            # Create a line edit for inline editing
            editor = QLineEdit(self.tree_view)
            
            # Get the path of the note
            data = self.notes_tree_model.data(index.siblingAtColumn(0), Qt.ItemDataRole.UserRole)
            
            # Handle different data types from the model
            if isinstance(data, dict):
                path = data.get('path', '')
            elif isinstance(data, str):
                path = data
            else:
                print(f"Unexpected data type from model: {type(data)}")
                return
            
            if not path:
                print("No path found for note")
                return
            
            # Convert relative path to absolute if needed
            if not os.path.isabs(path) and hasattr(self, 'notes_manager'):
                notes_path = self.notes_manager.get_notes_vault_path()
                abs_path = os.path.join(notes_path, path)
            else:
                abs_path = path
            
            # Store the path for later use when saving
            editor.setProperty("note_path", abs_path)
            
            # Set the current tags
            current_tags = ""
            if hasattr(self, 'notes_manager'):
                tags = self.notes_manager._extract_tags_from_file(abs_path)
                current_tags = ", ".join(tags)
            
            editor.setText(current_tags)
            editor.setGeometry(rect)
            editor.setFocus()
            editor.show()
            
            # Connect editing finished signal
            editor.editingFinished.connect(self._save_tags_inline)
            
            # Start editing
            self.tree_view.setCurrentIndex(index)
            
        except Exception as e:
            print(f"Error setting up inline tag editing: {str(e)}")
            self.show_error(f"Error editing tags: {str(e)}")

    def _save_tags_inline(self):
        """Save tags after inline editing is completed"""
        try:
            # Get the editor that sent the signal
            editor = self.sender()
            if not editor:
                return
            
            # Get the file path
            abs_path = editor.property("note_path")
            if not abs_path or not os.path.exists(abs_path):
                print(f"Invalid path for tag update: {abs_path}")
                editor.deleteLater()
                return
            
            # Get the new tags text
            tags_text = editor.text()
            
            # Update the tags in the file
            if hasattr(self, 'update_markdown_frontmatter_tags'):
                self.update_markdown_frontmatter_tags(abs_path, tags_text)
                print(f"Updated tags for {os.path.basename(abs_path)}")
                
                # Refresh the notes model with minimal reloading
                # Just update the specific item instead of full refresh
                if hasattr(self, 'notes_manager'):
                    # Pass the specific file path explicitly
                    self.notes_manager.refresh_notes(self, force=False, specific_file=abs_path)
            else:
                print("update_markdown_frontmatter_tags method not found")
            
            # Clean up the editor
            editor.deleteLater()
            
        except Exception as e:
            print(f"Error saving tags: {str(e)}")
            
            # Clean up the editor
            if 'editor' in locals() and editor:
                editor.deleteLater()
