from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTreeWidgetItem, 
                           QHBoxLayout, QSplitter, QLabel, QPushButton, QTreeWidget, QGroupBox, QTabWidget, QTreeView, 
                           QHeaderView, QMenu, QInputDialog, QLineEdit, QMessageBox, QStackedWidget, QListView)
from PyQt6.QtCore import Qt, QDir, QFileSystemWatcher, QEventLoop, QSize, QModelIndex
from PyQt6.QtGui import QFileSystemModel, QIcon, QStandardItemModel, QStandardItem
from pathlib import Path
from .toolbar import setup_toolbar
from .preview import update_preview
from ..tools.project import set_project_root
from ..tools.build import BuildManager
from .address_bar import AddressBar
from ..tools.vcs import VCSManager
from ..utils.themes import setup_theme
from ..utils.file_ops import FileOperations
from .tools.test_tool import TestTool
from ..views.test_results import TestResultsView
from .notes_duplicate_dialog import NotesDuplicateDialog  # For finding duplicate notes
from ..tools.command_manager import CommandManager
from ..tools.launch_manager import LaunchManager
from ..tools.notes_manager import NotesManager
import subprocess
import os
import json
import asyncio
from qasync import QEventLoop
import magic
import psutil

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
        # Use the NotesDuplicateDialog which works for both files and notes
        dialog = NotesDuplicateDialog(self)
        dialog.scan_directory(directory)
        dialog.exec()
        
    def find_duplicate_notes(self):
        """Find and manage duplicate notes"""
        if not hasattr(self, 'notes_manager'):
            self.show_error("Notes mode not active")
            return
            
        notes_path = self.notes_manager.get_notes_vault_path()
        if not notes_path:
            self.show_error("No notes directory selected")
            return
            
        # Use the notes manager's duplicate finder to ensure consistency
        self.notes_manager.find_duplicate_notes(self)

    def switch_mode(self, mode):
        """Switch between file, project, and notes modes"""
        if mode == self.current_mode:
            return
        
        print(f"Switching mode from {self.current_mode} to {mode}")
        
        # Store the current path if in file/project mode
        old_path = None
        if hasattr(self, 'model') and self.current_mode != 'notes':
            old_path = self.model.filePath(self.current_view.rootIndex())
        
        # Switch to file mode
        if mode == 'file':
            # Update UI
            if hasattr(self, 'file_mode_btn'):
                self.file_mode_btn.setChecked(True)
            if hasattr(self, 'project_mode_btn'):
                self.project_mode_btn.setChecked(False)
            if hasattr(self, 'notes_mode_btn'):
                self.notes_mode_btn.setChecked(False)
            
            # Switch file tree to standard model
            if hasattr(self, 'model') and hasattr(self, 'tree_view'):
                self.tree_view.setModel(self.model)
                self.list_view.setModel(self.model)
            
            # Toggle toolbar buttons visibility
            self.toggle_toolbar_visibility(file_visible=True, project_visible=False, notes_visible=False)
            
            # Update status bar
            if hasattr(self, 'project_state'):
                self.project_state.setText("")
            
            # Show test view if it was previously open
            if hasattr(self, 'test_view'):
                self.test_view.hide()
        
        # Switch to project mode
        elif mode == 'project':
            # Update UI
            if hasattr(self, 'file_mode_btn'):
                self.file_mode_btn.setChecked(False)
            if hasattr(self, 'project_mode_btn'):
                self.project_mode_btn.setChecked(True)
            if hasattr(self, 'notes_mode_btn'):
                self.notes_mode_btn.setChecked(False)
            
            # Configure project mode
            self.setup_project_mode()
            
            # Toggle toolbar buttons visibility
            self.toggle_toolbar_visibility(file_visible=True, project_visible=True, notes_visible=False)
            
            # No need to navigate explicitly as setup_project_mode handles it
        
        # Switch to notes mode
        elif mode == 'notes':
            print("DEBUG: Switching to notes mode")
            # Update UI
            if hasattr(self, 'file_mode_btn'):
                self.file_mode_btn.setChecked(False)
            if hasattr(self, 'project_mode_btn'):
                self.project_mode_btn.setChecked(False)
            if hasattr(self, 'notes_mode_btn'):
                self.notes_mode_btn.setChecked(True)
            
            # Toggle toolbar buttons visibility
            self.toggle_toolbar_visibility(file_visible=False, project_visible=False, notes_visible=True)
            
            # Hide any test views
            if hasattr(self, 'test_view'):
                self.test_view.hide()
            
            # Check for notes manager
            if not hasattr(self, 'notes_manager'):
                print("DEBUG: Creating notes manager")
                from ..tools.notes_manager import NotesManager
                self.notes_manager = NotesManager(self)
                self.notes_manager.notes_loaded.connect(self.on_notes_loaded)
            
            # Try to get notes model
            print("DEBUG: Setting up notes mode")
            model = self.notes_manager.setup_notes_mode(self)
            
            if model:
                print("DEBUG: Notes model already available")
                # Model is already available
                self.on_notes_loaded(model)
            else:
                print("DEBUG: Notes model will be loaded asynchronously")
                # Model will be loaded asynchronously
                # on_notes_loaded will be called via signal
            
            # Update status bar
            if hasattr(self, 'project_state'):
                self.project_state.setText("")
                
            # Debug current state of the tree view and model
            print(f"DEBUG: Tree view model type: {type(self.tree_view.model())}")
            print(f"DEBUG: Tree view root index valid: {self.tree_view.rootIndex().isValid()}")
            
        # Update current mode
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
            
            print("DEBUG: Notes model loaded, updating UI...")
            
            # Store reference to the model
            self.notes_tree_model = notes_tree_model
            
            # Set up the views with the new model
            self.tree_view.setModel(notes_tree_model)
            self.list_view.setModel(notes_tree_model)
            
            # Always use invalid index to show root in notes mode
            self.tree_view.setRootIndex(QModelIndex())
            self.list_view.setRootIndex(QModelIndex())
            
            # Set column widths and visibility
            self.tree_view.setColumnWidth(0, 250)  # Name column
            self.tree_view.setColumnWidth(1, 200)  # Tags column
            # Path column should stretch
            self.tree_view.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            
            # Set up UI components for notes mode
            self.setup_notes_mode_ui()
            
            # Get the notes vault path for displaying in the UI
            notes_path = ""
            if hasattr(self, 'notes_manager'):
                notes_path = self.notes_manager.get_notes_vault_path()
                print(f"DEBUG: Notes vault path: {notes_path}")
                
                # Update the address bar with the notes vault path (if it exists)
                try:
                    if hasattr(self, 'address_bar') and self.address_bar is not None:
                        self.address_bar.setText(notes_path)
                except RuntimeError:
                    # Handle case where address bar has been deleted
                    print("Warning: Address bar was deleted")
                    pass
                    
                # Display the notes path in the status bar
                self.status_bar.showMessage(f"Notes vault: {notes_path}", 5000)
            else:
                print("DEBUG: No notes_manager attribute found")
            
            # Don't automatically expand tree - leave it collapsed
            # self.tree_view.expandToDepth(0)
            self.tree_view.viewport().update()
            self.list_view.viewport().update()
            
            # Debug model and view state
            print(f"DEBUG: Tree view has {notes_tree_model.rowCount(QModelIndex())} rows at root level")
            
            # Update UI to reflect that loading is complete
            print("DEBUG: Notes loaded and UI updated")
        
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
                
                # Connect the tags list to the filter function
                self.notes_tags_list.clicked.connect(self.filter_notes_by_tag)
            
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
                    
    def filter_notes_by_tag(self, index):
        """Filter notes to only show those with the selected tag"""
        if not hasattr(self, 'notes_model') or not hasattr(self, 'notes_tree_model'):
            return
        
        # Get the selected tag
        tag_model = self.notes_tags_list.model()
        tag_item = tag_model.itemFromIndex(index)
        selected_tag = tag_item.data(Qt.ItemDataRole.UserRole)
        
        # Store the current filter for reference
        self.current_tag_filter = selected_tag
        
        # Show status message
        if selected_tag == "all":
            self.status_bar.showMessage("Showing all notes", 3000)
        else:
            count = 0
            if selected_tag in self.notes_model.tags_map:
                count = len(self.notes_model.tags_map[selected_tag])
            self.status_bar.showMessage(f"Filtering notes by tag: {selected_tag} ({count} notes)", 3000)
        
        # Apply filter to the tree model
        if hasattr(self.notes_tree_model, 'setFilterTag'):
            self.notes_tree_model.setFilterTag(selected_tag)
        
        # Apply filter to the list model if in list view
        if hasattr(self.notes_model, 'setFilterTag'):
            self.notes_model.setFilterTag(selected_tag)
        
        # Refresh the view to show the filtered notes
        self.tree_view.expandAll()
        self.tree_view.viewport().update()
        self.list_view.viewport().update()

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
            
            # Update address bar
            if hasattr(self, 'address_bar'):
                self.address_bar.setText(self.model.filePath(index))
            
            # Add path to file watcher if not already watching
            path = self.model.filePath(index)
            if hasattr(self, 'file_watcher') and path not in self.file_watcher.directories():
                self.file_watcher.addPath(path)
        
        # Update view reference
        if self.view_stack.currentWidget() == self.tree_view:
            self.current_view = self.tree_view
        else:
            self.current_view = self.list_view

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
            index = self.model.index(path)
            if index.isValid():
                self.navigate_to(index)
            else:
                self.show_error(f"Invalid path index: {path}")
        else:
            # For files, navigate to parent directory and select file
            parent_dir = os.path.dirname(path)
            if os.path.exists(parent_dir):
                # First navigate to parent directory
                parent_index = self.model.index(parent_dir)
                if parent_index.isValid():
                    self.navigate_to(parent_index)
                    
                    # Then select the file
                    file_index = self.model.index(path)
                    if file_index.isValid():
                        self.current_view.setCurrentIndex(file_index)
                        # Update preview if needed
                        self.handle_selection_changed()
                else:
                    self.show_error(f"Invalid parent directory: {parent_dir}")
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
        
    def navigate_to_path(self, path):
        """Navigate to a specific path"""
        if not path or not os.path.exists(path):
            print(f"Cannot navigate to nonexistent path: {path}")
            return
            
        if self.current_mode == 'notes':
            print("Cannot navigate to arbitrary paths in notes mode")
            return
            
        index = self.model.index(path)
        if index.isValid():
            self.navigate_to(index)

    def setup_navigation(self):
        """Set up navigation bar with buttons and address bar"""
        # Create container for navigation controls
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)
        
        # Navigation buttons
        back_btn = QPushButton()
        back_btn.setIcon(QIcon.fromTheme("go-previous"))
        back_btn.setToolTip("Back")
        back_btn.clicked.connect(self.navigate_back)
        nav_layout.addWidget(back_btn)
        
        forward_btn = QPushButton()
        forward_btn.setIcon(QIcon.fromTheme("go-next"))
        forward_btn.setToolTip("Forward")
        forward_btn.clicked.connect(self.navigate_forward)
        nav_layout.addWidget(forward_btn)
        
        up_btn = QPushButton()
        up_btn.setIcon(QIcon.fromTheme("go-up"))
        up_btn.setToolTip("Up")
        up_btn.clicked.connect(self.navigate_up)
        nav_layout.addWidget(up_btn)
        
        refresh_btn = QPushButton()
        refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self.refresh_view)
        nav_layout.addWidget(refresh_btn)
        
        # Address bar
        self.address_bar = AddressBar()
        self.address_bar.returnPressed.connect(self.handle_address_bar)
        nav_layout.addWidget(self.address_bar)
        
        return nav_widget

    def handle_address_bar(self):
        """Handle address bar input"""
        path = self.address_bar.text()
        self.navigate_to_address(path)
        
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
            
        current_path = self.get_current_path()
        parent_path = os.path.dirname(current_path)
        
        if parent_path and parent_path != current_path:
            self.navigate_to_path(parent_path)

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
        """Toggle visibility of toolbar buttons based on mode"""
        # File mode toolbar buttons
        file_buttons = [
            'back_button', 'forward_button', 'up_button', 'refresh_button',
            'new_folder_button', 'copy_button', 'cut_button', 'paste_button',
            'delete_button', 'rename_button'
        ]
        
        # Project mode toolbar buttons
        project_buttons = [
            'build_button', 'run_button', 'debug_button', 'test_button',
            'vcs_button', 'terminal_button', 'smelt_button', 'cast_button', 
            'forge_button', 'contract_button', 'doc_button'
        ]
        
        # Notes mode toolbar buttons
        notes_buttons = [
            'tag_button', 'find_dupes_button', 'sort_button', 'search_notes_button',
            'create_note_button', 'back_button', 'forward_button', 'refresh_button'
        ]
        
        # Toggle button visibility based on the current mode
        if notes_visible:
            # In notes mode, only show notes buttons
            for btn_name in notes_buttons:
                if hasattr(self, btn_name):
                    button = getattr(self, btn_name)
                    button.setVisible(True)
            
            # Hide all project and file-specific buttons
            for btn_name in file_buttons:
                if hasattr(self, btn_name) and btn_name not in notes_buttons:
                    button = getattr(self, btn_name)
                    button.setVisible(False)
            
            for btn_name in project_buttons:
                if hasattr(self, btn_name):
                    button = getattr(self, btn_name)
                    button.setVisible(False)
        else:
            # In file or project mode
            for btn_name in file_buttons:
                if hasattr(self, btn_name):
                    button = getattr(self, btn_name)
                    button.setVisible(file_visible)
            
            for btn_name in project_buttons:
                if hasattr(self, btn_name):
                    button = getattr(self, btn_name)
                    button.setVisible(project_visible)
            
            # Always hide notes buttons in non-notes modes
            for btn_name in notes_buttons:
                if hasattr(self, btn_name) and btn_name not in file_buttons:
                    button = getattr(self, btn_name)
                    button.setVisible(False)
            
        # Make sure address bar is visible in file and project mode only
        try:
            if hasattr(self, 'address_bar'):
                self.address_bar.setVisible((file_visible or project_visible) and not notes_visible)
        except RuntimeError:
            # The C++ object might have been deleted
            print("Warning: Address bar widget was deleted")
            pass

    def setup_project_mode(self):
        """Set up project mode"""
        try:
            # Get the current working directory as the project root
            project_path = os.getcwd()
            
            # Check if it's a valid directory
            if not os.path.isdir(project_path):
                self.show_error("Invalid project path")
                return
            
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
                    
                # Update project configuration - pass self (the explorer instance)
                set_project_root(self)
                
                # Show test panel if available
                if hasattr(self, 'test_view'):
                    self.test_view.show()
                    
                # Update status bar
                self.status_bar.showMessage(f"Project: {os.path.basename(project_path)}", 3000)
            else:
                self.show_error(f"Could not set project root: {project_path}")
        except Exception as e:
            self.show_error(f"Error setting up project mode: {str(e)}")
            import traceback
            traceback.print_exc()

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