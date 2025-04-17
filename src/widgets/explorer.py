import os
import sys
import time
import platform
import subprocess
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
                           QSplitter, QLabel, QPushButton, QTreeView, QFileDialog,
                           QLineEdit, QComboBox, QMenu, QMessageBox, QToolBar,
                           QStatusBar, QTabWidget, QApplication, QListView,
                           QListWidget, QListWidgetItem, QProgressDialog, QDialog,
                           QDialogButtonBox, QFormLayout, QGroupBox, QHeaderView,
                           QInputDialog, QStackedWidget, QTreeWidget, QTreeWidgetItem)
from PyQt6.QtGui import (QAction, QKeySequence, QColor, QIcon, 
                       QStandardItemModel, QStandardItem, QFileSystemModel)
from PyQt6.QtCore import (Qt, QDir, QModelIndex, QSize, 
                        QEventLoop, QFileSystemWatcher, QProcess, pyqtSignal,
                        QItemSelectionModel, QSortFilterProxyModel)
from .toolbar import setup_toolbar
from .preview import update_preview
from ..tools.project import set_project_root
from ..tools.build import BuildManager
from .address_bar import AddressBar
from ..tools.vcs import VCSManager
from ..utils.utils import setup_theme
from ..utils.file_ops import FileOperations
from .tools.test_tool import TestTool
from ..views.test_results import TestResultsView
from .notes_duplicate_dialog import NotesDuplicateDialog  # For finding duplicate notes
from ..tools.command_manager import CommandManager
from ..tools.launch_manager import LaunchManager
from ..tools.notes_manager import NotesManager
from ..tools.sync_manager import DirectorySyncManager
import json
import magic
import psutil
from qasync import QEventLoop

# Import local modules
from ..utils.utils import setup_theme, get_file_icon, file_exists, dir_exists
from ..utils.dialogs import FileConflictDialog
from ..tools.build import BuildManager
from .tools.test_tool import TestTool
from ..tools.vcs import VCSManager
from ..tools.command_manager import CommandManager
from ..tools.launch_manager import LaunchManager
from ..tools.notes_manager import NotesManager
from ..tools.sync_manager import DirectorySyncManager

# Configure logging
logging.basicConfig(level=logging.INFO)

class EExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize managers and tools
        self.build_manager = BuildManager(self)
        self.vcs_manager = VCSManager(self)
        self.file_ops = FileOperations(self)
        self.test_tool = TestTool(self)
        self.command_manager = CommandManager(self)
        self.launch_manager = LaunchManager(self)
        self.sync_manager = DirectorySyncManager(self)
        
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
        
        # Check for scheduled syncs on startup
        self.sync_manager.check_schedule_on_startup()
        
        # Check UI integrity after initialization
        self.check_ui_integrity()
    
    def check_ui_integrity(self):
        """Check if the UI is properly set up and fix any issues"""
        # Check if address bar exists
        if not hasattr(self, 'address_bar') or self.address_bar is None:
            print("Address bar is missing, recreating it")
            self.recreate_address_bar()
            
        # Check if mode buttons exist
        if not hasattr(self, 'file_mode_btn') or not hasattr(self, 'project_mode_btn') or not hasattr(self, 'notes_mode_btn'):
            print("Mode buttons are missing, recreating toolbar")
            # Try to recreate toolbar
            if hasattr(self, 'toolbar'):
                # Clear existing toolbar
                while self.toolbar.actions():
                    self.toolbar.removeAction(self.toolbar.actions()[0])
                    
                # Create new toolbar widget
                toolbar_widget = QWidget()
                toolbar_layout = QHBoxLayout(toolbar_widget)
                toolbar_layout.setContentsMargins(0, 0, 0, 0)
                
                # Setup toolbar 
                try:
                    setup_toolbar(self, toolbar_layout)
                    self.toolbar.addWidget(toolbar_widget)
                    print("Toolbar recreated successfully")
                except Exception as e:
                    print(f"Error recreating toolbar: {str(e)}")
                    
        # Check if current_view is set
        if not hasattr(self, 'current_view') or self.current_view is None:
            print("Current view is not set, fixing")
            if hasattr(self, 'tree_view'):
                self.current_view = self.tree_view
                print("Set current view to tree view")
            elif hasattr(self, 'list_view'):
                self.current_view = self.list_view
                print("Set current view to list view")
                
        # Navigate to home directory if we don't have a current location
        try:
            if self.current_mode == 'file':
                current_path = self.get_current_path()
                if not current_path or not os.path.exists(current_path):
                    home_path = os.path.expanduser("~")
                    print(f"No valid current path, navigating to home: {home_path}")
                    self.navigate_to_path(home_path)
        except Exception as e:
            print(f"Error checking current path: {str(e)}")
    
    def setup_ui(self):
        """Initialize the main UI components"""
        # Create main layout and toolbar
        main_layout = QVBoxLayout()
        
        # Create toolbar container
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.addToolBar(self.toolbar)
        
        # Create empty lists for toolbar actions by category
        self.file_actions = []
        self.project_actions = []
        self.notes_actions = []
        
        # Create toolbar widget
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Setup toolbar controls with our toolbar helper function
        from .toolbar import setup_toolbar
        try:
            setup_toolbar(self, toolbar_layout)
        except Exception as e:
            print(f"Error setting up toolbar: {str(e)}")
            import traceback
            traceback.print_exc()
        
        self.toolbar.addWidget(toolbar_widget)
        
        # Main widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Create navigation bar using our NavigationBar class
        try:
            from .navigation import NavigationBar
            self.nav_bar = NavigationBar(self)
            self.nav_bar.path_changed.connect(self.navigate_to_path)
            self.nav_bar.back_requested.connect(self.navigate_back)
            self.nav_bar.forward_requested.connect(self.navigate_forward)
            self.nav_bar.up_requested.connect(self.navigate_up)
            self.nav_bar.refresh_requested.connect(self.refresh_view)
            # Connect mode change signal
            if hasattr(self.nav_bar, 'mode_changed'):
                self.nav_bar.mode_changed.connect(self.switch_mode)
            # Initialize with default mode
            if hasattr(self.nav_bar, 'set_mode'):
                self.nav_bar.set_mode(self.current_mode)
            # Add navigation bar to layout
            main_layout.addWidget(self.nav_bar)
        except Exception as e:
            print(f"Error setting up navigation bar: {str(e)}")
            import traceback
            traceback.print_exc()
            
        # Initialize file system model
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        
        # Main splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)
        
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
            except Exception as e2:
                # If show_error fails, use a simple print
                print(f"Failed to show error dialog: {str(e)}, second error: {str(e2)}")

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
        indexes = self.tree_view.selectedIndexes()
        if not indexes:
            return
            
        # Keep only indexes for column 0 (name column)
        indexes = [index for index in indexes if index.column() == 0]
        
        if not indexes:
            return
            
        # Create menu
        menu = QMenu(self)
        
        # Check if we're in file mode or notes mode
        if self.current_mode == 'file':
            # Get file path from the model
            first_item_path = self.model.filePath(indexes[0])
            
            # Add actions based on selection
            if len(indexes) == 1:
                # Single selection actions
                if os.path.isdir(first_item_path):
                    # Directory actions
                    menu.addAction(self.create_action("Open", lambda: self.navigate_to(indexes[0])))
                    menu.addAction(self.create_action("Open in New Tab", lambda: self.open_in_new_tab(first_item_path)))
                    menu.addAction(self.create_action("Open in Terminal", lambda: self.open_in_terminal(first_item_path)))
                    
                    # Add sync directory action
                    menu.addAction(self.create_action("Synchronize Directory...", lambda: self.sync_directory(first_item_path)))
                    
                    menu.addSeparator()
                    menu.addAction(self.create_action("New File", lambda: self.create_new_file(first_item_path)))
                    menu.addAction(self.create_action("New Folder", lambda: self.create_new_folder(first_item_path)))
                    
                    if self.is_project_directory(first_item_path):
                        menu.addSeparator()
                        menu.addAction(self.create_action("Open as Project", lambda: self.switch_to_project_mode(first_item_path)))
                        if hasattr(self, 'launch_manager'):
                            menu.addAction(self.create_action("Run Project", lambda: self.show_launch_manager(first_item_path)))
                else:
                    # File actions
                    menu.addAction(self.create_action("Open", lambda: self.handle_item_double_click(indexes[0])))
                    
                    # Add "Open With" submenu for files
                    open_with_menu = QMenu("Open With", menu)
                    applications = self.get_system_applications(first_item_path)
                    for app_info in applications:
                        open_with_menu.addAction(self.create_action(
                            app_info['name'], 
                            lambda app=app_info: self.open_with(first_item_path, app)
                        ))
                    
                    if applications:
                        menu.addMenu(open_with_menu)
                        
                    menu.addSeparator()
                    
                    # Add compare if multiple files are selected
                    if hasattr(self, 'compare_files_action'):
                        compare_with_menu = QMenu("Compare With...", menu)
                        compare_with_menu.addAction(self.create_action(
                            "Select File...", lambda: self.compare_with_file(first_item_path)
                        ))
                        menu.addMenu(compare_with_menu)

    def sync_directory(self, directory_path):
        """Synchronize a directory with another location"""
        if not directory_path or not os.path.isdir(directory_path):
            self.show_error("Please select a valid directory to synchronize.")
            return
            
        # Check if sync_manager is available
        if not hasattr(self, 'sync_manager'):
            from ..tools.sync_manager import DirectorySyncManager
            self.sync_manager = DirectorySyncManager(self)
            
        # Get notes vault path as the initial target suggestion
        target_dir = ""
        if hasattr(self, 'notes_manager'):
            notes_path = self.notes_manager.get_notes_vault_path()
            if notes_path and os.path.exists(notes_path) and os.path.normpath(notes_path) != os.path.normpath(directory_path):
                target_dir = notes_path
        
        # Open the sync dialog
        self.sync_manager.show_sync_dialog(directory_path, target_dir)

    def setup_drives(self):
        """Set up the drives section"""
        drives_group = QGroupBox("Drives")
        drives_layout = QVBoxLayout(drives_group)
        drives_layout.setContentsMargins(4, 4, 4, 4)
        drives_layout.setSpacing(2)
        
        self.drives_list = QTreeWidget()
        self.drives_list.setHeaderLabels(["Name", "Mount Point", "Type", "Size"])
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

    def mount_drive(self, item):
        """Navigate to selected drive location"""
        try:
            path = item.text(1)  # Path is stored in column 1
            if os.path.exists(path):
                index = self.model.index(path)
                if index.isValid():
                    self.navigate_to(index)
                else:
                    self.show_error(f"Invalid path: {path}")
        except Exception as e:
            self.show_error(f"Error mounting drive: {str(e)}")

    def refresh_drives(self):
        """Refresh the list of available drives"""
        try:
            # Clear existing drives
            self.drives_list.clear()
            
            # Get all disk partitions
            partitions = psutil.disk_partitions(all=True)
            
            for partition in partitions:
                # Create new tree widget item
                drive_item = QTreeWidgetItem(self.drives_list)
                
                # Extract device name for display
                device_name = os.path.basename(partition.device) if partition.device else "Unknown"
                
                # Set the name (device name)
                drive_item.setText(0, device_name)
                
                # Set the mount point
                drive_item.setText(1, partition.mountpoint)
                
                # Set the filesystem type
                drive_item.setText(2, partition.fstype if partition.fstype else "Unknown")
                
                # Try to get disk usage information
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    # Format size as human-readable
                    total_gb = usage.total / (1024 * 1024 * 1024)
                    free_gb = usage.free / (1024 * 1024 * 1024)
                    size_str = f"{total_gb:.1f} GB ({free_gb:.1f} GB free)"
                    drive_item.setText(3, size_str)
                except (PermissionError, FileNotFoundError):
                    drive_item.setText(3, "Unknown")
                
                # Set appropriate icon based on device/mountpoint
                if partition.mountpoint == "/":
                    drive_item.setIcon(0, QIcon.fromTheme("drive-harddisk"))
                elif "/media/" in partition.mountpoint or "/mnt/" in partition.mountpoint:
                    drive_item.setIcon(0, QIcon.fromTheme("drive-removable-media"))
                elif "/boot" in partition.mountpoint:
                    drive_item.setIcon(0, QIcon.fromTheme("system"))
                elif "/home" in partition.mountpoint:
                    drive_item.setIcon(0, QIcon.fromTheme("user-home"))
                else:
                    drive_item.setIcon(0, QIcon.fromTheme("drive-harddisk"))
            
            # Add home directory if it's not already in the list
            home_path = os.path.expanduser("~")
            home_found = False
            for i in range(self.drives_list.topLevelItemCount()):
                item = self.drives_list.topLevelItem(i)
                if item.text(1) == home_path:
                    home_found = True
                    break
            
            if not home_found:
                home_item = QTreeWidgetItem(self.drives_list)
                home_item.setText(0, "Home")
                home_item.setText(1, home_path)
                home_item.setText(2, "home")
                home_item.setIcon(0, QIcon.fromTheme("user-home"))
                
                # Try to get disk usage for home
                try:
                    usage = psutil.disk_usage(home_path)
                    total_gb = usage.total / (1024 * 1024 * 1024)
                    free_gb = usage.free / (1024 * 1024 * 1024)
                    size_str = f"{total_gb:.1f} GB ({free_gb:.1f} GB free)"
                    home_item.setText(3, size_str)
                except Exception:
                    home_item.setText(3, "Unknown")
            
            # Expand all items
            self.drives_list.expandAll()
            
            # Adjust column widths
            for i in range(4):
                self.drives_list.resizeColumnToContents(i)
            
        except Exception as e:
            self.show_error(f"Error refreshing drives: {str(e)}")

    def navigate_to(self, index):
        """Navigate to the given index in the current view"""
        if not index.isValid():
            return
        
        # Store in navigation history
        current_path = self.model.filePath(self.current_view.rootIndex())
        
        # Add to history if changing location
        if current_path != self.model.filePath(index):
            # Trim history if we're not at the end
            if self.nav_current < len(self.nav_history) - 1:
                self.nav_history = self.nav_history[:self.nav_current + 1]
            
            # Add current path to history if it's valid
            self.nav_history.append(current_path)
            self.nav_current = len(self.nav_history) - 1
        
        # If it's a directory, set both views to use it as root
        if os.path.isdir(self.model.filePath(index)):
            self.tree_view.setRootIndex(index)
            self.list_view.setRootIndex(index)
            
            # Update address bar (safely)
            path = self.model.filePath(index)
            self.update_address_bar(path)
            
            # Add path to file watcher if not already watching
            if hasattr(self, 'file_watcher') and path not in self.file_watcher.directories():
                self.file_watcher.addPath(path)
        
        # Update view reference
        if self.view_stack.currentWidget() == self.tree_view:
            self.current_view = self.tree_view
        else:
            self.current_view = self.list_view
            
    def update_address_bar(self, path):
        """Update the address bar with the given path, recreating it if necessary"""
        try:
            if hasattr(self, 'address_bar') and self.address_bar is not None:
                self.address_bar.setText(path)
            else:
                # Address bar missing, recreate it
                self.recreate_address_bar()
                if hasattr(self, 'address_bar') and self.address_bar is not None:
                    self.address_bar.setText(path)
                else:
                    print("Failed to recreate address bar")
        except RuntimeError:
            # Address bar has been deleted, recreate it
            print("Address bar C++ object no longer exists, recreating")
            self.recreate_address_bar()
            # Try again with the new address bar
            if hasattr(self, 'address_bar') and self.address_bar is not None:
                try:
                    self.address_bar.setText(path)
                except Exception as e:
                    print(f"Error setting path in recreated address bar: {e}")
        except Exception as e:
            print(f"Error updating address bar: {e}")

    def recreate_address_bar(self):
        """Recreate the address bar if it has been deleted"""
        try:
            # Check if address bar needs recreation
            if not hasattr(self, 'address_bar') or self.address_bar is None:
                print("Recreating address bar")
                
                # Find the nav_bar
                if hasattr(self, 'nav_bar') and self.nav_bar is not None:
                    # Clear any existing layout contents
                    if self.nav_bar.layout():
                        while self.nav_bar.layout().count():
                            item = self.nav_bar.layout().takeAt(0)
                            if item.widget():
                                item.widget().deleteLater()
                    
                    # Create a new layout if needed
                    if not self.nav_bar.layout():
                        new_layout = QHBoxLayout(self.nav_bar)
                        new_layout.setContentsMargins(2, 2, 2, 2)
                        new_layout.setSpacing(4)
                    
                    # Recreate navigation buttons
                    back_btn = QPushButton()
                    back_btn.setIcon(QIcon.fromTheme("go-previous"))
                    back_btn.setToolTip("Back")
                    back_btn.clicked.connect(self.navigate_back)
                    back_btn.setFixedSize(32, 32)
                    back_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
                    self.nav_bar.layout().addWidget(back_btn)
                    
                    forward_btn = QPushButton()
                    forward_btn.setIcon(QIcon.fromTheme("go-next"))
                    forward_btn.setToolTip("Forward")
                    forward_btn.clicked.connect(self.navigate_forward)
                    forward_btn.setFixedSize(32, 32)
                    forward_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
                    self.nav_bar.layout().addWidget(forward_btn)
                    
                    up_btn = QPushButton()
                    up_btn.setIcon(QIcon.fromTheme("go-up"))
                    up_btn.setToolTip("Up")
                    up_btn.clicked.connect(self.navigate_up)
                    up_btn.setFixedSize(32, 32)
                    up_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
                    self.nav_bar.layout().addWidget(up_btn)
                    
                    refresh_btn = QPushButton()
                    refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
                    refresh_btn.setToolTip("Refresh")
                    refresh_btn.clicked.connect(self.refresh_view)
                    refresh_btn.setFixedSize(32, 32)
                    refresh_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
                    self.nav_bar.layout().addWidget(refresh_btn)
                    
                    # Create a new address bar
                    try:
                        from .address_bar import AddressBar
                        self.address_bar = AddressBar()
                    except (ImportError, ModuleNotFoundError):
                        # Fallback to plain QLineEdit
                        self.address_bar = QLineEdit()
                        
                    # Configure the address bar
                    self.address_bar.returnPressed.connect(self.handle_address_bar)
                    self.address_bar.setMinimumWidth(300)
                    self.nav_bar.layout().addWidget(self.address_bar, 1)
                    
                    # Set initial path
                    current_path = self.get_current_path() or os.path.expanduser("~")
                    self.address_bar.setText(current_path)
                    
                    print("Address bar recreated in nav_bar")
                    return True
                else:
                    # No nav_bar, create one
                    print("No nav_bar found, creating a new one")
                    self.nav_bar = self.setup_navigation()
                    
                    # If we have a main layout, add it at the top
                    central_widget = self.centralWidget()
                    if central_widget and central_widget.layout():
                        central_widget.layout().insertWidget(0, self.nav_bar)
                        print("Added new nav_bar to main layout")
                        return True
                    
                    print("Could not add nav_bar to layout")
                    return False
            return True  # Address bar already exists
        except Exception as e:
            print(f"Error recreating address bar: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def navigate_to_path(self, path):
        """Navigate to a specific path"""
        if not path or not os.path.exists(path):
            print(f"Cannot navigate to nonexistent path: {path}")
            return
            
        # Special case for notes mode
        if self.current_mode == 'notes':
            # In notes mode, allow navigating to the notes vault path
            notes_vault_path = ""
            if hasattr(self, 'notes_manager'):
                notes_vault_path = self.notes_manager.get_notes_vault_path()
                
            if path == notes_vault_path:
                # This is valid - update address bar to show notes vault path
                self.update_address_bar(path)
                
                # If notes tree model exists, ensure it's set on the tree view
                if hasattr(self, 'notes_tree_model') and self.notes_tree_model:
                    self.tree_view.setModel(self.notes_tree_model)
                    self.tree_view.expandToDepth(0)  # Show top-level items
                    
                print(f"Set address bar to notes vault path: {path}")
                return
            else:
                print(f"Cannot navigate to {path} in notes mode")
                return
        
        # Update address bar with the target path
        self.update_address_bar(path)
            
        # Get the model index for the path
        index = self.model.index(path)
        if index.isValid():
            try:
                self.navigate_to(index)
            except RuntimeError as e:
                print(f"RuntimeError in navigate_to_path: {e}")
                # Try again after recreating address bar
                if "has been deleted" in str(e):
                    self.recreate_address_bar()
                    try:
                        self.navigate_to(index)
                    except Exception as e2:
                        print(f"Failed to navigate after recreating address bar: {e2}")
            except Exception as e:
                print(f"Error in navigate_to_path: {e}")
        else:
            print(f"Invalid index for path: {path}")

    def setup_navigation(self):
        """Set up navigation bar with buttons and address bar"""
        # If we already have a navigation bar from the setup_ui method, use that
        if hasattr(self, 'nav_bar') and self.nav_bar is not None:
            return self.nav_bar
            
        # Otherwise create a new NavigationBar
        try:
            from .navigation import NavigationBar
            nav_bar = NavigationBar(self)
            
            # Connect signals
            nav_bar.path_changed.connect(self.navigate_to_path)
            nav_bar.back_requested.connect(self.navigate_back)
            nav_bar.forward_requested.connect(self.navigate_forward)
            nav_bar.up_requested.connect(self.navigate_up)
            nav_bar.refresh_requested.connect(self.refresh_view)
            
            # Connect mode change signal if available
            if hasattr(nav_bar, 'mode_changed'):
                nav_bar.mode_changed.connect(self.switch_mode)
                
            # Set initial path
            try:
                current_path = os.path.expanduser("~")  # Default to home
                if hasattr(self, 'model') and hasattr(self, 'current_view'):
                    model_path = self.model.filePath(self.current_view.rootIndex())
                    if model_path and os.path.exists(model_path):
                        current_path = model_path
                
                nav_bar.set_path(current_path)
            except Exception as e:
                print(f"Error setting initial path in navigation bar: {e}")
                
            # Set initial mode
            if hasattr(nav_bar, 'set_mode'):
                nav_bar.set_mode(self.current_mode)
                
            return nav_bar
            
        except ImportError as e:
            print(f"Error importing NavigationBar: {e}")
            # Continue with fallback
        except Exception as e:
            print(f"Error creating navigation bar: {e}")
            import traceback
            traceback.print_exc()
            
        # Create container for navigation controls (fallback)
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(2, 2, 2, 2)
        nav_layout.setSpacing(4)
        
        # Navigation buttons
        back_btn = QPushButton()
        back_btn.setIcon(QIcon.fromTheme("go-previous"))
        back_btn.setToolTip("Back")
        back_btn.clicked.connect(self.navigate_back)
        back_btn.setFixedSize(32, 32)
        back_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
        nav_layout.addWidget(back_btn)
        
        forward_btn = QPushButton()
        forward_btn.setIcon(QIcon.fromTheme("go-next"))
        forward_btn.setToolTip("Forward")
        forward_btn.clicked.connect(self.navigate_forward)
        forward_btn.setFixedSize(32, 32)
        forward_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
        nav_layout.addWidget(forward_btn)
        
        up_btn = QPushButton()
        up_btn.setIcon(QIcon.fromTheme("go-up"))
        up_btn.setToolTip("Up")
        up_btn.clicked.connect(self.navigate_up)
        up_btn.setFixedSize(32, 32)
        up_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
        nav_layout.addWidget(up_btn)
        
        refresh_btn = QPushButton()
        refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self.refresh_view)
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }")
        nav_layout.addWidget(refresh_btn)
        
        # Address bar
        try:
            from .address_bar import AddressBar
            self.address_bar = AddressBar()
            self.address_bar.returnPressed.connect(self.handle_address_bar)
            self.address_bar.setMinimumWidth(300)  # Ensure it has adequate width
            nav_layout.addWidget(self.address_bar, 1)  # Give address bar stretch factor to fill available space
        except ImportError as e:
            print(f"Error importing AddressBar: {e}")
            # Create a fallback QLineEdit
            self.address_bar = QLineEdit()
            self.address_bar.returnPressed.connect(self.handle_address_bar)
            self.address_bar.setMinimumWidth(300)
            nav_layout.addWidget(self.address_bar, 1)
        except Exception as e:
            print(f"Error creating address bar: {e}")
            
        # Try to initialize with current path
        try:
            current_path = os.path.expanduser("~")  # Default to home
            if hasattr(self, 'model') and hasattr(self, 'current_view'):
                model_path = self.model.filePath(self.current_view.rootIndex())
                if model_path and os.path.exists(model_path):
                    current_path = model_path
            
            if hasattr(self, 'address_bar') and self.address_bar is not None:
                self.address_bar.setText(current_path)
        except Exception as e:
            print(f"Error setting initial path in address bar: {e}")
        
        return nav_widget

    def handle_address_bar(self):
        """Handle address bar input"""
        try:
            path = self.address_bar.text()
            self.navigate_to_address(path)
        except Exception as e:
            print(f"Error handling address bar input: {e}")
            self.show_error(f"Error navigating to path: {str(e)}")
            
    def navigate_to_address(self, path):
        """Navigate to a specific path address"""
        if not path or not os.path.exists(path):
            self.show_error(f"Invalid path: {path}")
            return
        
        # Check if we're in notes mode
        if self.current_mode == 'notes':
            # In notes mode, we can't navigate to arbitrary paths
            self.show_error("Cannot navigate to external paths in Notes mode")
            return
        
        # Handle directory vs file
        if os.path.isdir(path):
            # Navigate to directory
            self.navigate_to_path(path)
        else:
            # For files, navigate to parent directory and select file
            parent_dir = os.path.dirname(path)
            if os.path.exists(parent_dir):
                # First navigate to parent directory
                self.navigate_to_path(parent_dir)
                
                # Then select the file
                file_index = self.model.index(path)
                if file_index.isValid():
                    self.current_view.setCurrentIndex(file_index)
                    # Update preview if needed
                    self.handle_selection_changed()
            else:
                self.show_error(f"Parent directory not found: {parent_dir}")
                
    def get_current_path(self):
        """Get the current path in the file tree"""
        if self.current_mode == 'notes':
            if hasattr(self, 'notes_manager'):
                return self.notes_manager.get_notes_vault_path()
            return ""
        elif hasattr(self, 'model') and hasattr(self, 'current_view'):
            return self.model.filePath(self.current_view.rootIndex())
        return ""

    def navigate_back(self):
        """Navigate back in history"""
        if self.nav_current > 0:
            self.nav_current -= 1
            path = self.nav_history[self.nav_current]
            if os.path.exists(path):
                index = self.model.index(path)
                if index.isValid():
                    # Disable history recording temporarily
                    old_recording = getattr(self, '_recording_history', True)
                    self._recording_history = False
                    self.navigate_to(index)
                    self._recording_history = old_recording
            
    def navigate_forward(self):
        """Navigate forward in history"""
        if self.nav_current < len(self.nav_history) - 1:
            self.nav_current += 1
            path = self.nav_history[self.nav_current]
            if os.path.exists(path):
                index = self.model.index(path)
                if index.isValid():
                    # Disable history recording temporarily
                    old_recording = getattr(self, '_recording_history', True)
                    self._recording_history = False
                    self.navigate_to(index)
                    self._recording_history = old_recording
                
    def navigate_up(self):
        """Navigate to parent directory"""
        # In notes mode, don't allow navigating above the vault root
        if self.current_mode == 'notes':
            print("DEBUG: In notes mode, can't navigate up from vault root")
            return
        
        # Make sure the address bar is available
        self.check_address_bar()
            
        current_path = self.get_current_path()
        parent_path = os.path.dirname(current_path)
        
        if parent_path and parent_path != current_path:
            try:
                self.navigate_to_path(parent_path)
            except RuntimeError as e:
                if "AddressBar has been deleted" in str(e):
                    # Address bar was deleted, try to recreate it
                    self.recreate_address_bar()
                    
                    # Try again
                    try:
                        self.navigate_to_path(parent_path)
                    except Exception as e2:
                        print(f"Failed to navigate up after recreating address bar: {e2}")
                else:
                    print(f"RuntimeError in navigate_up: {e}")
            except Exception as e:
                print(f"Error in navigate_up: {e}")

    def check_address_bar(self):
        """Check if address bar exists and try to recreate it if not"""
        if not hasattr(self, 'address_bar') or self.address_bar is None:
            print("Address bar missing, attempting to recreate")
            self.recreate_address_bar()
            return hasattr(self, 'address_bar') and self.address_bar is not None
        
        # Try to verify the address bar is still valid
        try:
            # A simple property access should raise an exception if the object is deleted
            test = self.address_bar.isVisible()
            return True
        except RuntimeError:
            print("Address bar C++ object deleted, attempting to recreate")
            self.recreate_address_bar()
            return hasattr(self, 'address_bar') and self.address_bar is not None
        except Exception as e:
            print(f"Error checking address bar: {e}")
            return False

    def refresh_view(self, directory=None):
        """Refresh the current view"""
        # If a specific directory was changed, check if it's the current one
        if directory and self.current_mode != 'notes':
            current_dir = self.model.filePath(self.current_view.rootIndex())
            if directory != current_dir:
                # The changed directory is not the one we're viewing, no need to refresh
                return
        
        # If we're in notes mode, handle differently
        if self.current_mode == 'notes':
            if hasattr(self, 'notes_manager'):
                # Check if we need to fully refresh or just update UI
                self.notes_manager.refresh_notes(self, False)
            return
        
        # Standard file view refresh
        current_path = None
        
        try:
            # Store the current selection if any
            indexes = self.current_view.selectedIndexes()
            selected_path = None
            if indexes:
                # Only use the first selected item from the first column
                for idx in indexes:
                    if idx.column() == 0:
                        selected_path = self.model.filePath(idx)
                        break
            
            # Store current directory path
            current_path = self.model.filePath(self.current_view.rootIndex())
            
            # Check if the path still exists before refreshing
            if not os.path.exists(current_path):
                # Path doesn't exist anymore, navigate to parent
                parent_path = os.path.dirname(current_path)
                if os.path.exists(parent_path):
                    self.navigate_to_address(parent_path)
                else:
                    # If parent doesn't exist either, go to home
                    self.navigate_to_address(os.path.expanduser("~"))
                return
            
            # Force model refresh by resetting the root path
            self.model.setRootPath(self.model.rootPath())
            
            # Refresh both views and update address bar
            self.tree_view.setRootIndex(self.model.index(current_path))
            self.list_view.setRootIndex(self.model.index(current_path))
            
            # Restore selection if possible
            if selected_path and os.path.exists(selected_path):
                index = self.model.index(selected_path)
                if index.isValid():
                    self.current_view.setCurrentIndex(index)
        
        except Exception as e:
            import traceback
            print(f"Error refreshing view: {str(e)}")
            traceback.print_exc()
            
            # Attempt to gracefully recover
            if current_path and os.path.exists(current_path):
                try:
                    # Try to refresh the view with a known good path
                    self.tree_view.setRootIndex(self.model.index(current_path))
                    self.list_view.setRootIndex(self.model.index(current_path))
                except Exception as e2:
                    print(f"Failed to recover from refresh error: {str(e2)}")
                    pass

    def toggle_toolbar_visibility(self, file_visible=True, project_visible=False, notes_visible=False):
        """Toggle toolbar visibility based on the current mode"""
        # Enable/disable actions and sections based on mode
        if hasattr(self, 'file_actions'):
            for action in self.file_actions:
                action.setVisible(file_visible)
                
        if hasattr(self, 'project_actions'):
            for action in self.project_actions:
                action.setVisible(project_visible)
                
        if hasattr(self, 'notes_actions'):
            for action in self.notes_actions:
                action.setVisible(notes_visible)
                
        # Update toolbar to hide empty sections
        if hasattr(self, 'toolbar'):
            for action in self.toolbar.actions():
                action_text = action.text()
                
                # Toggle section visibility based on mode
                if action_text in ["File Operations", "Navigation"]:
                    action.setVisible(file_visible)
                elif action_text in ["Project"]:
                    action.setVisible(project_visible)
                elif action_text in ["Notes"]:
                    action.setVisible(notes_visible)

    def setup_project_mode(self):
        """Initialize project mode (e.g., set up version control, build system)"""
        try:
            # Get project root (use current directory by default)
            project_path = self.get_current_path()
            if not project_path or not os.path.isdir(project_path):
                project_path = os.getcwd()
            
            # Configure file model to use project root
            self.tree_view.setModel(self.model)
            self.list_view.setModel(self.model)
            
            # Set project root index
            project_index = self.model.index(project_path)
            if project_index.isValid():
                self.tree_view.setRootIndex(project_index)
                self.list_view.setRootIndex(project_index)
                self.current_view = self.tree_view
                
                # Update address bar - with try/except to handle deleted address bar
                try:
                    if hasattr(self, 'address_bar') and self.address_bar is not None:
                        self.address_bar.setText(project_path)
                except RuntimeError:
                    # Handle case where address bar has been deleted
                    print("Warning: Address bar was deleted, creating new one")
                    # Don't try to recreate it here to avoid potential new issues
                    pass
            
                # Try to detect project type
                project_type = self.detect_project_type(project_path)
                
                if project_type:
                    # Update project indicator
                    if hasattr(self, 'project_type'):
                        self.project_type.setText(f"{project_type}")
                    
                    # Set project in build manager
                    if hasattr(self, 'build_manager'):
                        if hasattr(self.build_manager, 'set_project'):
                            self.build_manager.set_project(project_path, project_type)
                        else:
                            print("build_manager doesn't have set_project method")
                    
                    # Update status bar
                    self.statusBar().showMessage(f"Project: {os.path.basename(project_path)} ({project_type})", 3000)
                    
                    # Update title
                    self.setWindowTitle(f"EEPY Explorer - {os.path.basename(project_path)} ({project_type})")
                else:
                    # No specific project type detected
                    if hasattr(self, 'project_type'):
                        self.project_type.setText("Generic Project")
                        
                    # Update status bar
                    self.statusBar().showMessage(f"Project: {os.path.basename(project_path)}", 3000)
                    
                    # Update title
                    self.setWindowTitle(f"EEPY Explorer - {os.path.basename(project_path)}")
                
                # Update project configuration - pass self (the explorer instance)
                try:
                    # Try different import paths since we don't know the exact structure
                    try:
                        from ..tools.project import set_project_root
                    except ImportError:
                        try:
                            from src.tools.project import set_project_root
                        except ImportError:
                            try:
                                from tools.project import set_project_root
                            except ImportError:
                                print("Could not import set_project_root from any module path")
                                raise
                    
                    # Call function if import succeeded
                    set_project_root(self)
                except (ImportError, AttributeError) as e:
                    print(f"Couldn't use set_project_root: {e}")
                except Exception as e:
                    print(f"Error in set_project_root: {e}")
                
                # Show test panel if available
                if hasattr(self, 'test_view'):
                    self.test_view.show()
                
                return project_type
            else:
                self.statusBar().showMessage(f"Could not set project root: {project_path}", 3000)
                return None
        except Exception as e:
            print(f"Error setting up project mode: {str(e)}")
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Error setting up project mode: {str(e)}", 3000)
            return None

    def open_in_internal_editor(self, path):
        """Open a file in the internal editor"""
        if not path or not os.path.exists(path):
            self.show_error(f"Cannot open file: {path}")
            return
        
        # Check if it's a text file
        try:
            # Use magic to detect file type
            file_type = magic.from_file(path, mime=True)
            if not file_type.startswith('text/'):
                # Try to open with system default
                subprocess.Popen(['xdg-open', path])
                return
        except Exception as e:
            print(f"Error detecting file type: {e}")
            # Fallback: check extension
            if not path.lower().endswith(('.md', '.txt', '.py', '.js', '.html', '.css', '.json')):
                # Try to open with system default
                subprocess.Popen(['xdg-open', path])
                return
        
        try:
            # Create editor dialog
            from .editor_dialog import EditorDialog
            editor = EditorDialog(self, path)
            editor.show()
            
            # Connect file saved signal if editor supports it
            if hasattr(editor, 'file_saved'):
                editor.file_saved.connect(self.handle_file_saved)
            
        except ImportError:
            # If we don't have the editor module, try to use a system editor
            try:
                subprocess.Popen(['xdg-open', path])
            except Exception as e:
                self.show_error(f"Could not open editor: {str(e)}")
            
        except Exception as e:
            self.show_error(f"Error opening editor: {str(e)}")
            import traceback
            traceback.print_exc()
        
    def handle_file_saved(self, path):
        """Handle a file being saved in the editor"""
        # Refresh relevant views
        if self.current_mode == 'notes' and hasattr(self, 'notes_manager'):
            # Update notes model if we're in notes mode
            self.notes_manager.update_note(self, path)
        else:
            # Otherwise just refresh the view
            self.refresh_view()

    def open_with(self, path, app_info):
        """Open a file with a specific application"""
        try:
            if 'command' in app_info:
                # Use the app's command
                cmd = app_info['command'].replace('%f', path)
                subprocess.Popen(cmd, shell=True)
            else:
                # Fallback to default opener
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            self.show_error(f"Error opening file: {str(e)}")

    def get_system_applications(self, path):
        """Get a list of system applications that can open this file type"""
        apps = []
        
        # Default apps for common file types
        if path.lower().endswith(('.md', '.txt')):
            apps.append({'name': 'Text Editor', 'icon': 'accessories-text-editor', 'command': 'gedit %f'})
        elif path.lower().endswith(('.py')):
            apps.append({'name': 'Python IDE', 'icon': 'text-x-python', 'command': 'code %f'})
        elif path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            apps.append({'name': 'Image Viewer', 'icon': 'image-viewer', 'command': 'eog %f'})
        elif path.lower().endswith(('.pdf')):
            apps.append({'name': 'PDF Viewer', 'icon': 'application-pdf', 'command': 'evince %f'})
        
        # Add system default
        apps.append({'name': 'System Default', 'icon': 'system-run', 'command': 'xdg-open %f'})
        
        return apps

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
            
            # Set up editor
            editor.setText(current_tags)
            editor.setGeometry(rect)
            editor.setFocus()
            editor.show()
            
            # Connect editing finished signal
            editor.editingFinished.connect(self.save_note_tags)
            
        except Exception as e:
            print(f"Error setting up tags editor: {str(e)}")
            import traceback
            traceback.print_exc()

    def save_note_tags(self):
        """Save tags after editing"""
        try:
            # Get the editor that sent the signal
            editor = self.sender()
            if not editor:
                return
            
            # Get the path and new tags
            path = editor.property("note_path")
            new_tags = editor.text()
            
            # Remove the editor
            editor.deleteLater()
            
            # Update the file with new tags
            if hasattr(self, 'notes_manager'):
                self.notes_manager.update_tags(self, path, new_tags.split(','))
        except Exception as e:
            print(f"Error saving note tags: {str(e)}")
            import traceback
            traceback.print_exc()

    def open_in_terminal(self, path):
        """Open a terminal at the specified path"""
        try:
            # Try to detect the user's terminal
            terminals = [
                ['x-terminal-emulator', '-e', f'cd "{path}" && bash'],
                ['gnome-terminal', '--working-directory', path],
                ['konsole', '--workdir', path],
                ['xfce4-terminal', '--working-directory', path],
                ['lxterminal', '--working-directory', path],
                ['mate-terminal', '--working-directory', path],
                ['alacritty', '-e', f'cd "{path}" && bash'],
                ['kitty', '--directory', path],
                ['terminator', '--working-directory', path]
            ]
            
            # Try each terminal until one works
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    return  # Terminal opened successfully
                except (FileNotFoundError, subprocess.SubprocessError):
                    continue
                
            # If we reach here, none of the terminals worked
            self.show_error("Could not find a suitable terminal emulator")
            
        except Exception as e:
            self.show_error(f"Error opening terminal: {str(e)}")
            import traceback
            traceback.print_exc()

    def show_launch_manager(self, project_path):
        """Show the launch configuration manager for a project"""
        try:
            # Check if the launch manager exists
            if not hasattr(self, 'launch_manager'):
                self.show_error("Launch manager not available")
                return
            
            # Open the launch config dialog
            self.launch_manager.show_config_dialog(project_path)
        except Exception as e:
            self.show_error(f"Error showing launch manager: {str(e)}")
            import traceback
            traceback.print_exc()

    def setup_views(self):
        """Set up the file views"""
        # Create container for navigation and views
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)
        
        # Create view container (without adding navigation bar again)
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
        self.current_view_mode = 'list'
        
        return container

    def sort_notes(self):
        """Delegate to the notes manager for sorting notes"""
        if hasattr(self, 'notes_manager'):
            self.notes_manager.show_sort_dialog(self)
        else:
            self.show_error("Notes mode not active")
    
    def search_notes_content(self):
        """Delegate to the notes manager for searching notes content"""
        if hasattr(self, 'notes_manager'):
            self.notes_manager.search_notes_content(self)
        else:
            self.show_error("Notes mode not active")
    
    def manage_tags(self):
        """Delegate to the notes manager for tag management"""
        if hasattr(self, 'notes_manager'):
            self.notes_manager.manage_tags(self)
        else:
            self.show_error("Notes mode not active")
            
    def create_new_note(self):
        """Delegate to the notes manager for creating a new note"""
        if hasattr(self, 'notes_manager'):
            self.notes_manager.create_new_note(self)
        else:
            self.show_error("Notes mode not active")
    
    def get_notes_dir(self):
        """Get the current notes directory path"""
        if hasattr(self, 'notes_manager'):
            return self.notes_manager.get_notes_vault_path()
        return None

    def keyPressEvent(self, event):
        """Handle key press events across the application"""
        # If in notes mode, handle notes-specific keys
        if self.current_mode == 'notes':
            # Up navigation - ignore in notes mode at root level
            if event.key() == Qt.Key.Key_Backspace:
                print("Backspace key ignored in notes mode")
                event.accept()
                return
                
        # Handle other common key events
        super().keyPressEvent(event)

    def create_menu(self):
        """Create main menu"""
        # Create the menu bar
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction("&New File", self.new_file, "Ctrl+N")
        file_menu.addAction("&Open File", self.open_file, "Ctrl+O")
        file_menu.addAction("&Save", lambda: self.editor_tabs.save_current_file() if hasattr(self, 'editor_tabs') else None, "Ctrl+S")
        file_menu.addAction("Save &As", lambda: self.editor_tabs.save_current_file_as() if hasattr(self, 'editor_tabs') else None, "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("&Refresh", lambda: self.refresh_view(), "F5")
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, "Alt+F4")
        
        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction("&Cut", lambda: self.file_ops.cut_selected_files(), "Ctrl+X")
        edit_menu.addAction("&Copy", lambda: self.file_ops.copy_selected_files(), "Ctrl+C")
        edit_menu.addAction("&Paste", lambda: self.file_ops.paste_files(), "Ctrl+V")
        edit_menu.addSeparator()
        edit_menu.addAction("&Find Files", self.show_find_dialog, "Ctrl+F")
        
        # View menu
        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction("File &Browser Mode", self.set_file_mode, "Ctrl+1")
        view_menu.addAction("&Project Mode", self.set_project_mode, "Ctrl+2")
        view_menu.addAction("&Notes Mode", self.set_notes_mode, "Ctrl+3")
        view_menu.addSeparator()
        view_menu.addAction("List View", lambda: self.set_view_mode('list'), "Ctrl+L")
        view_menu.addAction("Icon View", lambda: self.set_view_mode('icon'), "Ctrl+I")
        view_menu.addSeparator()
        view_menu.addAction("Toggle &Preview", self.toggle_preview, "F12")
        
        # Tools menu
        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction("&Terminal", lambda: self.open_in_terminal(self.get_current_path()), "F9")
        tools_menu.addAction("&Open Shell", self.open_shell)
        
        # Project menu
        project_menu = menu_bar.addMenu("&Project")
        project_menu.addAction("&Run Project", lambda: self.show_launch_manager(self.get_current_path()), "F5")
        project_menu.addAction("&Build Project", lambda: self.build_manager.build_project(self.get_current_path()), "F7")
        project_menu.addAction("&Test Project", lambda: self.test_tool.run_tests(self.get_current_path()), "F8")
        
        # Notes menu
        notes_menu = menu_bar.addMenu("&Notes")
        notes_menu.addAction("&Sort Notes", self.sort_notes)
        notes_menu.addAction("&Search Content", self.search_notes_content)
        notes_menu.addAction("&Manage Tags", self.manage_tags)
        notes_menu.addAction("&New Note", self.create_new_note)
        notes_menu.addAction("Find &Duplicates", self.find_duplicate_notes)
        
        # Add Sync submenu to Notes menu
        sync_menu = notes_menu.addMenu("&Synchronize")
        sync_menu.addAction("&Sync Directories", self.synchronize_directories)
        sync_menu.addAction("&Open Sync Manager", self.open_sync_manager)
        sync_menu.addAction("&Schedule Sync", self.open_sync_scheduler)
        
        return menu_bar

    def synchronize_directories(self):
        """Open the synchronize directories dialog"""
        try:
            # Ensure sync_manager is initialized
            if not hasattr(self, 'sync_manager'):
                from ..tools.sync_manager import DirectorySyncManager
                self.sync_manager = DirectorySyncManager(self)
                
            self.sync_manager.show_sync_dialog()
        except ImportError as e:
            print(f"Error importing sync dialog: {e}")
            QMessageBox.critical(self, "Error", "Sync dialog module not available")
    
    def open_sync_manager(self):
        """Open the sync manager dialog"""
        try:
            # Same as synchronize_directories for now, but could be extended with more features
            self.synchronize_directories()
        except Exception as e:
            print(f"Error opening sync manager: {e}")
            QMessageBox.critical(self, "Error", f"Error opening sync manager: {str(e)}")
    
    def open_sync_scheduler(self):
        """Open the sync scheduler dialog"""
        try:
            # Ensure sync_manager is initialized
            if not hasattr(self, 'sync_manager'):
                from ..tools.sync_manager import DirectorySyncManager
                self.sync_manager = DirectorySyncManager(self)
                
            self.sync_manager.show_schedule_dialog()
        except ImportError as e:
            print(f"Error importing sync scheduler: {e}")
            QMessageBox.critical(self, "Error", "Sync scheduler module not available")
    
    def find_duplicate_notes(self):
        """Find and manage duplicate notes"""
        try:
            # Use the more feature-rich notes duplicate dialog
            from ..widgets.notes_duplicate_dialog import NotesDuplicateDialog
            
            dialog = NotesDuplicateDialog(self)
            notes_path = self.get_notes_dir()
            if notes_path:
                dialog.scan_directory(notes_path)
                dialog.exec()
            else:
                QMessageBox.critical(self, "Error", "No notes directory configured.")
                
        except Exception as e:
            print(f"Error finding duplicate notes: {e}")
            QMessageBox.critical(self, "Error", f"Error finding duplicate notes: {str(e)}")

    def delete_files(self):
        """Delete selected files and directories with confirmation."""
        # Get selected paths based on current view
        selected_paths = []
        
        # Get selected indexes from the current view
        if self.current_mode == 'file' or self.current_mode == 'project':
            indexes = self.current_view.selectedIndexes()
            # Filter to just get unique file paths (one per row)
            for index in indexes:
                if index.column() == 0:  # Only consider the first column
                    path = self.model.filePath(index)
                    if path and path not in selected_paths:
                        selected_paths.append(path)
        elif self.current_mode == 'notes':
            # Handle notes selection
            if hasattr(self, 'notes_tree_model') and self.tree_view.selectionModel():
                indexes = self.tree_view.selectionModel().selectedIndexes()
                for index in indexes:
                    if index.column() == 0:  # Only consider the first column
                        data = self.notes_tree_model.data(index, Qt.ItemDataRole.UserRole)
                        if isinstance(data, dict):
                            path = data.get('path', '')
                        elif isinstance(data, str):
                            path = data
                        else:
                            continue
                            
                        if path:
                            # Convert to absolute path if needed
                            if not os.path.isabs(path) and hasattr(self, 'notes_manager'):
                                notes_path = self.notes_manager.get_notes_vault_path()
                                path = os.path.join(notes_path, path)
                                
                            if path not in selected_paths:
                                selected_paths.append(path)
        
        if not selected_paths:
            return
            
        # Ask for confirmation
        count = len(selected_paths)
        if count == 1:
            msg = f"Are you sure you want to delete '{os.path.basename(selected_paths[0])}'?"
        else:
            msg = f"Are you sure you want to delete {count} items?"
            
        reply = QMessageBox.question(
            self, 'Confirm Deletion', 
            msg, 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for path in selected_paths:
                try:
                    if os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to delete {path}: {str(e)}")
            
            # Refresh the view after deletion
            self.refresh_view()

    def toggle_view_mode(self):
        """Toggle between list view and icon view modes"""
        if self.view_stack.currentWidget() == self.tree_view:
            # Currently in list/tree view, switch to icon view
            self.view_stack.setCurrentWidget(self.list_view)
            self.current_view = self.list_view
            self.current_view_mode = 'icon'
        else:
            # Currently in icon view, switch to list/tree view
            self.view_stack.setCurrentWidget(self.tree_view)
            self.current_view = self.tree_view
            self.current_view_mode = 'list'
        
        # Update user interface to reflect the change
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage(f"Switched to {self.current_view_mode} view", 2000)

    def switch_mode(self, mode):
        """Switch between different application modes (file, project, notes)
        
        Args:
            mode: String indicating the mode ('file', 'project', or 'notes')
        """
        try:
            # Update mode buttons if they exist
            if hasattr(self, 'file_mode_btn'):
                self.file_mode_btn.setChecked(mode == 'file')
            if hasattr(self, 'project_mode_btn'):
                self.project_mode_btn.setChecked(mode == 'project')
            if hasattr(self, 'notes_mode_btn'):
                self.notes_mode_btn.setChecked(mode == 'notes')
            
            # Skip if already in the requested mode
            if self.current_mode == mode:
                return
                
            # Store current mode
            previous_mode = self.current_mode
            self.current_mode = mode
            
            # Update navigation bar mode if it exists
            if hasattr(self, 'nav_bar') and hasattr(self.nav_bar, 'set_mode'):
                try:
                    self.nav_bar.set_mode(mode)
                except Exception as e:
                    print(f"Error updating navigation bar mode: {e}")
            
            # Update address bar based on mode
            self.update_address_bar_for_mode(mode)
            
            # Show/hide UI elements based on mode - fixed to prevent project tools hiding
            if mode == 'file':
                # VISIBILITY: Show file operations, hide project and notes operations
                self._set_toolbar_visibility(show_file=True, show_project=False, show_notes=False)
                
                # Switch from notes back to standard file model if needed
                if previous_mode == 'notes' and hasattr(self, 'notes_tree_model'):
                    self.tree_view.setModel(self.model)
                    self.list_view.setModel(self.model)
                    
                    # Navigate to home directory or last file path
                    home_path = os.path.expanduser("~")
                    try:
                        self.navigate_to_path(home_path)
                    except Exception as e:
                        print(f"Error navigating to home: {str(e)}")
                
                # Update status bar
                self.statusBar().showMessage("File Explorer Mode", 2000)
                
            elif mode == 'project':
                # VISIBILITY: Show file and project operations, hide notes operations
                self._set_toolbar_visibility(show_file=True, show_project=True, show_notes=False)
                    
                # Switch to project mode
                self.setup_project_mode()
                
            elif mode == 'notes':
                # VISIBILITY: Show file and notes operations, hide project operations
                self._set_toolbar_visibility(show_file=True, show_project=False, show_notes=True)
                    
                # Switch to notes mode
                if not hasattr(self, 'notes_manager'):
                    # Initialize notes manager if needed
                    try:
                        from ..tools.notes_manager import NotesManager
                    except ImportError:
                        try:
                            from src.tools.notes_manager import NotesManager
                        except ImportError:
                            try:
                                from tools.notes_manager import NotesManager
                            except ImportError:
                                print("Error importing NotesManager module")
                                self.statusBar().showMessage("Notes mode not available - missing NotesManager", 3000)
                                # Reset mode
                                self.current_mode = previous_mode
                                return
                
                    # Create notes manager
                    self.notes_manager = NotesManager(self)
                    print("Created new NotesManager")
                
                # Set up notes mode
                self.notes_tree_model = self.notes_manager.setup_notes_mode(self)
                
                # Connect notes loaded signal if needed
                if not hasattr(self.notes_manager, 'notes_loaded') or \
                   not hasattr(self.notes_manager.notes_loaded, 'isConnected') or \
                   not self.notes_manager.notes_loaded.isConnected(self.on_notes_loaded):
                    self.notes_manager.notes_loaded.connect(self.on_notes_loaded)
                
                # If the model is already available, make sure it's properly displayed
                if hasattr(self, 'notes_tree_model') and self.notes_tree_model:
                    # Set the model on the tree view
                    self.tree_view.setModel(self.notes_tree_model)
                    # Explicitly expand top-level items
                    self.tree_view.expandToDepth(0)
                    # Force switch to tree view
                    self.view_stack.setCurrentWidget(self.tree_view)
                    self.current_view = self.tree_view
                    
                    # Get notes vault path
                    notes_vault_path = self.notes_manager.get_notes_vault_path()
                    
                    # Update address bar with notes vault path
                    if hasattr(self, 'address_bar') and notes_vault_path and os.path.exists(notes_vault_path):
                        self.address_bar.setText(notes_vault_path)
                        print(f"Set address bar to notes vault path: {notes_vault_path}")
                
                # Update status bar
                self.statusBar().showMessage("Notes Vault Mode", 2000)
            else:
                self.statusBar().showMessage("Unknown mode", 2000)
                # Reset mode
                self.current_mode = previous_mode
        except Exception as e:
            print(f"Error switching mode: {e}")
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Error switching to {mode} mode: {str(e)}", 3000)
            
    def _set_toolbar_visibility(self, show_file=True, show_project=False, show_notes=False):
        """Helper method to set toolbar visibility consistently"""
        try:
            # File operation buttons
            if hasattr(self, 'copy_button'):
                self.copy_button.setVisible(show_file)
            if hasattr(self, 'cut_button'):
                self.cut_button.setVisible(show_file)
            if hasattr(self, 'paste_button'):
                self.paste_button.setVisible(show_file)
            
            # Project operation buttons
            if hasattr(self, 'vcs_button'):
                self.vcs_button.setVisible(show_project)
            if hasattr(self, 'build_button'):
                self.build_button.setVisible(show_project)
            if hasattr(self, 'smelt_button'):
                self.smelt_button.setVisible(show_project)
            if hasattr(self, 'cast_button'):
                self.cast_button.setVisible(show_project)
            if hasattr(self, 'forge_button'):
                self.forge_button.setVisible(show_project)
            
            # Notes operation buttons
            if hasattr(self, 'tag_button'):
                self.tag_button.setVisible(show_notes)
            if hasattr(self, 'find_dupes_button'):
                self.find_dupes_button.setVisible(show_notes)
            if hasattr(self, 'sort_button'):
                self.sort_button.setVisible(show_notes)
            if hasattr(self, 'search_notes_button'):
                self.search_notes_button.setVisible(show_notes)
            if hasattr(self, 'create_note_button'):
                self.create_note_button.setVisible(show_notes)
        except Exception as e:
            print(f"Error setting toolbar visibility: {e}")

    def switch_view_mode(self, mode):
        """Switch to a specific view mode (list or grid)
        
        Args:
            mode: String indicating the mode ('list' or 'grid')
        """
        if mode == 'list':
            self.view_stack.setCurrentWidget(self.tree_view)
            self.current_view = self.tree_view
            self.current_view_mode = 'list'
            
            # Update toggle button states if they exist
            if hasattr(self, 'list_view_btn'):
                self.list_view_btn.setChecked(True)
            if hasattr(self, 'grid_view_btn'):
                self.grid_view_btn.setChecked(False)
                
        elif mode == 'grid' or mode == 'icon':
            self.view_stack.setCurrentWidget(self.list_view)
            self.current_view = self.list_view
            self.current_view_mode = 'icon'
            
            # Update toggle button states if they exist
            if hasattr(self, 'list_view_btn'):
                self.list_view_btn.setChecked(False)
            if hasattr(self, 'grid_view_btn'):
                self.grid_view_btn.setChecked(True)
                
        # Update status bar
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(f"Switched to {self.current_view_mode} view", 2000)

    def on_notes_loaded(self, notes_tree_model):
        """Handle notes being loaded by the notes manager"""
        try:
            # Check if the model is valid
            if not notes_tree_model:
                print("Error: Notes tree model is None")
                return
                
            print("Setting up notes view with loaded model")
            
            # Update tree view with notes model
            self.tree_view.setModel(notes_tree_model)
            
            # Add sorting capability
            self.tree_view.setSortingEnabled(True)
            self.tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
            
            # Expand the root item to show contents
            self.tree_view.expandToDepth(0)  # Show top-level items
            
            # Store reference to the model
            self.notes_tree_model = notes_tree_model
            
            # Hide the grid view button and show list view only
            if hasattr(self, 'grid_view_btn'):
                self.grid_view_btn.setEnabled(False)
            if hasattr(self, 'list_view_btn'):
                self.list_view_btn.setChecked(True)
                self.list_view_btn.setEnabled(False)
            
            # Set view mode to list
            self.view_stack.setCurrentWidget(self.tree_view)
            self.current_view = self.tree_view
            self.current_view_mode = 'list'
            
            # Connect double-click handler for opening notes
            if hasattr(self.tree_view, 'doubleClicked'):
                try:
                    # Disconnect existing handlers if any
                    self.tree_view.doubleClicked.disconnect()
                except:
                    pass  # No handlers connected
                    
                # Connect to notes handler if available
                if hasattr(self.notes_manager, 'open_note'):
                    self.tree_view.doubleClicked.connect(self.notes_manager.open_note)
            
            # Custom mouse handling for tag editing
            if hasattr(self.tree_view, 'mousePressEvent'):
                # Store original handler if not already stored
                if not hasattr(self, '_original_mouse_press'):
                    self._original_mouse_press = self.tree_view.mousePressEvent
                
                # Set custom handler
                self.tree_view.mousePressEvent = self.handle_notes_mouse_press
            
            # Close any progress dialog
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
                
            # Update status bar
            self.statusBar().showMessage("Notes vault loaded", 2000)
            
        except Exception as e:
            print(f"Error setting up notes view: {e}")
            import traceback
            traceback.print_exc()
            
            # Show error in status bar
            self.statusBar().showMessage(f"Error loading notes: {str(e)}", 5000)

    def set_project_mode(self):
        """Set the explorer to project mode"""
        # Get current path as project root
        project_path = self.get_current_path()
        
        # If no path is selected, use current working directory
        if not project_path or not os.path.isdir(project_path):
            project_path = os.getcwd()
            
        # Switch to project mode
        self.switch_mode('project')
        
        # Set the project root
        project_index = self.model.index(project_path)
        if project_index.isValid():
            self.navigate_to(project_index)
            
        # Update project configuration
        set_project_root(self)
        
    def set_file_mode(self):
        """Set the explorer to file mode"""
        self.switch_mode('file')
        
    def set_notes_mode(self):
        """Set the explorer to notes mode"""
        # Initialize notes manager if needed
        if not hasattr(self, 'notes_manager'):
            try:
                from ..tools.notes_manager import NotesManager
            except ImportError:
                try:
                    from src.tools.notes_manager import NotesManager
                except ImportError:
                    try:
                        from tools.notes_manager import NotesManager
                    except ImportError:
                        print("Could not import NotesManager")
                        return
            
            self.notes_manager = NotesManager(self)
            print("Created notes manager")
        
        # Switch to notes mode
        self.switch_mode('notes')
        
        # Make sure address bar is updated
        self.update_address_bar_for_mode('notes')

    def detect_project_type(self, project_path):
        """Detect the type of project based on files in the project directory
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            String indicating project type (e.g., "Python", "Node.js", etc.) or None if not detected
        """
        if not os.path.isdir(project_path):
            return None
            
        # Check for various project types based on their characteristic files
        if os.path.exists(os.path.join(project_path, "pyproject.toml")):
            return "Python (pyproject.toml)"
        elif os.path.exists(os.path.join(project_path, "setup.py")):
            return "Python (setup.py)"
        elif os.path.exists(os.path.join(project_path, "requirements.txt")):
            return "Python"
        elif os.path.exists(os.path.join(project_path, "Cargo.toml")):
            return "Rust"
        elif os.path.exists(os.path.join(project_path, "build.zig")):
            return "Zig"
        elif os.path.exists(os.path.join(project_path, "package.json")):
            return "Node.js"
        elif os.path.exists(os.path.join(project_path, "CMakeLists.txt")):
            return "CMake"
        elif os.path.exists(os.path.join(project_path, "Makefile")) or any(f.endswith(".mk") for f in os.listdir(project_path)):
            return "Make"
        elif os.path.exists(os.path.join(project_path, "pom.xml")):
            return "Java (Maven)"
        elif os.path.exists(os.path.join(project_path, "build.gradle")):
            return "Java (Gradle)"
        elif os.path.exists(os.path.join(project_path, ".git")):
            return "Git Repository"
            
        # Default case - generic directory
        return None

    def update_address_bar_for_mode(self, mode):
        """Update the address bar based on current mode"""
        try:
            if mode == 'notes':
                # For notes mode, set to notes vault path
                if hasattr(self, 'notes_manager') and hasattr(self.notes_manager, 'get_notes_vault_path'):
                    notes_path = self.notes_manager.get_notes_vault_path()
                    if notes_path:
                        print(f"Notes path from manager: {notes_path}")
                        # Force navigate to notes path
                        if os.path.exists(notes_path):
                            # Directly update address bar
                            if hasattr(self, 'address_bar'):
                                self.address_bar.setText(notes_path)
                                print(f"Updated address bar to notes path: {notes_path}")
                            
                            # If notes tree model exists, make sure it's set
                            if hasattr(self, 'notes_tree_model') and self.notes_tree_model:
                                self.tree_view.setModel(self.notes_tree_model)
                                self.tree_view.expandToDepth(0)
                                print("Set tree view model to notes model")
                            else:
                                print("Notes tree model not available yet")
                        else:
                            print(f"Notes path doesn't exist: {notes_path}")
                    else:
                        print("No notes path available from notes manager")
                else:
                    print("Notes manager not properly initialized")
                        
            elif mode == 'project':
                # For project mode, set to current project root
                project_path = self.get_current_path()
                if project_path and os.path.exists(project_path) and os.path.isdir(project_path):
                    # Update address bar
                    if hasattr(self, 'address_bar'):
                        self.address_bar.setText(project_path)
                        print(f"Updated address bar to project path: {project_path}")
                    
                    # Navigate to the project path
                    self.tree_view.setModel(self.model)
                    index = self.model.index(project_path)
                    if index.isValid():
                        try:
                            self.tree_view.setRootIndex(index)
                            self.list_view.setRootIndex(index)
                        except Exception as e:
                            print(f"Error setting root index: {e}")
                else:
                    print(f"Invalid project path: {project_path}")
                    
            elif mode == 'file':
                # For file mode, get the current path
                current_path = self.get_current_path()
                if current_path and os.path.exists(current_path) and os.path.isdir(current_path):
                    # Update address bar
                    if hasattr(self, 'address_bar'):
                        self.address_bar.setText(current_path)
                        print(f"Updated address bar to file path: {current_path}")
                else:
                    home_path = os.path.expanduser("~")
                    if hasattr(self, 'address_bar'):
                        self.address_bar.setText(home_path)
                        print(f"Updated address bar to home path: {home_path}")
                
                    # Navigate to the home directory
                    index = self.model.index(home_path)
                    if index.isValid():
                        try:
                            self.tree_view.setRootIndex(index)
                            self.list_view.setRootIndex(index)
                        except Exception as e:
                            print(f"Error setting root index: {e}")
                
        except Exception as e:
            print(f"Error updating address bar for mode {mode}: {e}")
            import traceback
            traceback.print_exc()

def get_synchronized_directory_pair(parent=None):
    """Get a pair of directories to synchronize"""
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QComboBox, QDialogButtonBox, QFileDialog)
    from PyQt6.QtCore import Qt
    
    # Create a dialog to select directories and sync mode
    dialog = QDialog(parent)
    dialog.setWindowTitle("Directory Pair")
    dialog.setMinimumWidth(500)
    
    layout = QVBoxLayout(dialog)
    
    # Source directory
    source_layout = QHBoxLayout()
    source_layout.addWidget(QLabel("Source:"))
    source_edit = QLabel()
    source_edit.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
    source_layout.addWidget(source_edit, 1)
    source_btn = QPushButton("Browse...")
    
    def browse_source():
        directory = QFileDialog.getExistingDirectory(
            dialog, "Select Source Directory", source_edit.text(),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            source_edit.setText(directory)
            
    source_btn.clicked.connect(browse_source)
    source_layout.addWidget(source_btn)
    layout.addLayout(source_layout)
    
    # Target directory
    target_layout = QHBoxLayout()
    target_layout.addWidget(QLabel("Target:"))
    target_edit = QLabel()
    target_edit.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
    target_layout.addWidget(target_edit, 1)
    target_btn = QPushButton("Browse...")
    
    def browse_target():
        directory = QFileDialog.getExistingDirectory(
            dialog, "Select Target Directory", target_edit.text(),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            target_edit.setText(directory)
            
    target_btn.clicked.connect(browse_target)
    target_layout.addWidget(target_btn)
    layout.addLayout(target_layout)
    
    # Sync mode
    mode_layout = QHBoxLayout()
    mode_layout.addWidget(QLabel("Sync Mode:"))
    mode_combo = QComboBox()
    mode_combo.addItem("Two-way sync", "two_way")
    mode_combo.addItem("Mirror source to target", "mirror")
    mode_combo.addItem("One-way (source to target)", "one_way_source_to_target")
    mode_combo.addItem("One-way (target to source)", "one_way_target_to_source")
    mode_layout.addWidget(mode_combo, 1)
    layout.addLayout(mode_layout)
    
    # Buttons
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | 
        QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    
    # Execute dialog
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return source_edit.text(), target_edit.text(), mode_combo.currentData()
    else:
        return None, None, None