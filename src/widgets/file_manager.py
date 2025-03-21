from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeView, QListView,
                           QStackedWidget, QMenu, QMessageBox)
from PyQt6.QtCore import Qt, QDir, QSize, pyqtSignal
from PyQt6.QtGui import QFileSystemModel, QIcon

class FileManager(QWidget):
    """Widget for managing file operations and views"""
    
    # Signals
    file_selected = pyqtSignal(str)  # Emitted when a file is selected
    directory_changed = pyqtSignal(str)  # Emitted when directory changes
    file_activated = pyqtSignal(str)  # Emitted when file is activated (double-clicked)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_view_mode = 'list'
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create view container
        self.view_stack = QStackedWidget()
        
        # Configure tree view
        self.tree_view = QTreeView()
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        self.tree_view.setModel(self.model)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.setDropIndicatorShown(True)
        self.tree_view.setColumnWidth(0, 300)  # Name
        self.tree_view.setColumnWidth(1, 80)   # Size
        self.tree_view.setColumnWidth(2, 100)  # Type
        self.tree_view.setColumnWidth(3, 150)  # Date Modified
        self.tree_view.doubleClicked.connect(self._handle_activation)
        self.tree_view.selectionModel().selectionChanged.connect(self._handle_selection)
        
        # Configure list view
        self.list_view = QListView()
        self.list_view.setModel(self.model)
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
        self.list_view.doubleClicked.connect(self._handle_activation)
        self.list_view.selectionModel().selectionChanged.connect(self._handle_selection)
        
        # Add views to stack
        self.view_stack.addWidget(self.tree_view)
        self.view_stack.addWidget(self.list_view)
        
        # Use tree view by default
        self.current_view = self.tree_view
        self.view_stack.setCurrentWidget(self.tree_view)
        
        layout.addWidget(self.view_stack)
        
    def switch_view_mode(self, mode):
        """Switch between list and grid view modes"""
        if mode == self.current_view_mode:
            return
            
        if mode == 'list':
            self.view_stack.setCurrentWidget(self.tree_view)
            self.current_view = self.tree_view
        else:
            self.view_stack.setCurrentWidget(self.list_view)
            self.current_view = self.list_view
            
        self.current_view_mode = mode
        
    def set_root_path(self, path):
        """Set the root path for both views"""
        index = self.model.index(path)
        if index.isValid():
            self.tree_view.setRootIndex(index)
            self.list_view.setRootIndex(index)
            self.directory_changed.emit(path)
            
    def get_current_path(self):
        """Get the current directory path"""
        return self.model.filePath(self.current_view.rootIndex())
        
    def get_selected_files(self):
        """Get list of selected file paths"""
        indexes = self.current_view.selectedIndexes()
        return [self.model.filePath(idx) for idx in indexes if idx.column() == 0]
        
    def _handle_activation(self, index):
        """Handle double-click on item"""
        path = self.model.filePath(index)
        self.file_activated.emit(path)
        
    def _handle_selection(self):
        """Handle selection change"""
        files = self.get_selected_files()
        if files:
            self.file_selected.emit(files[0])  # Emit first selected file
            
    def refresh(self):
        """Refresh the current view"""
        self.model.update()
        self.current_view.viewport().update() 