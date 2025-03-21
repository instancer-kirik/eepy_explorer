from PyQt6.QtWidgets import (QTreeView, QListView, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLineEdit, QStackedWidget,
                           QTextEdit, QLabel, QTreeWidget, QTreeWidgetItem)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFileSystemModel, QColor, QPalette

from .address_bar import AddressBar

class TestResultsView(QWidget):
    """View for displaying test results"""
    
    test_selected = pyqtSignal(dict)  # Emitted when a test is selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Controls
        controls = QHBoxLayout()
        
        self.run_btn = QPushButton("Run Tests")
        self.run_btn.setToolTip("Run all tests")
        controls.addWidget(self.run_btn)
        
        self.watch_btn = QPushButton("Watch")
        self.watch_btn.setCheckable(True)
        self.watch_btn.setToolTip("Watch for changes and run tests automatically")
        controls.addWidget(self.watch_btn)
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter tests...")
        controls.addWidget(self.filter_input)
        
        layout.addLayout(controls)
        
        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Test", "Status", "Duration"])
        self.results_tree.itemClicked.connect(self.handle_test_selected)
        layout.addWidget(self.results_tree)
        
        # Details view
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        
        # Status bar
        self.status_bar = QWidget()
        status_layout = QHBoxLayout(self.status_bar)
        
        self.passed_label = QLabel("Passed: 0")
        self.failed_label = QLabel("Failed: 0")
        self.skipped_label = QLabel("Skipped: 0")
        
        status_layout.addWidget(self.passed_label)
        status_layout.addWidget(self.failed_label)
        status_layout.addWidget(self.skipped_label)
        
        layout.addWidget(self.status_bar)
        
    def update_results(self, results):
        """Update view with new test results"""
        self.results_tree.clear()
        
        if not results:
            return
            
        for test in results['tests']:
            item = QTreeWidgetItem([
                test['name'],
                test['status'],
                str(test['duration']) if test['duration'] else ''
            ])
            
            # Set color based on status
            if test['status'] == 'passed':
                item.setForeground(1, QColor('#4CAF50'))  # Green
            elif test['status'] == 'failed':
                item.setForeground(1, QColor('#F44336'))  # Red
            elif test['status'] == 'skipped':
                item.setForeground(1, QColor('#FFC107'))  # Yellow
                
            self.results_tree.addTopLevelItem(item)
            
        # Update summary
        summary = results['summary']
        self.passed_label.setText(f"Passed: {summary['passed']}")
        self.failed_label.setText(f"Failed: {summary['failed']}")
        self.skipped_label.setText(f"Skipped: {summary['skipped']}")
        
    def handle_test_selected(self, item):
        """Show details for selected test"""
        test_name = item.text(0)
        for test in self._current_results['tests']:
            if test['name'] == test_name:
                self.test_selected.emit(test)
                self.details.setText('\n'.join(test['output']))
                break

def setup_views(explorer, main_splitter):
    """Setup tree and list views with navigation"""
    # Create view container
    tree_widget = QWidget()
    tree_layout = QVBoxLayout(tree_widget)
    tree_layout.setContentsMargins(0, 0, 0, 0)
    
    # Add navigation widget
    nav_widget = create_navigation_widget(explorer)
    tree_layout.addWidget(nav_widget)
    
    # Initialize views
    explorer.tree_view = create_tree_view(explorer)
    explorer.list_view = create_list_view(explorer)
    explorer.test_view = TestResultsView()
    
    # Create view stack
    explorer.view_stack = QStackedWidget()
    explorer.view_stack.addWidget(explorer.tree_view)
    explorer.view_stack.addWidget(explorer.list_view)
    explorer.view_stack.addWidget(explorer.test_view)
    
    # Use tree view by default
    explorer.current_view = explorer.tree_view
    explorer.current_view_mode = 'list'
    
    tree_layout.addWidget(explorer.view_stack)
    main_splitter.addWidget(tree_widget)
    
    # Initialize navigation history
    explorer.nav_history = []
    explorer.nav_current = -1
    
    # Connect test view signals
    explorer.test_view.run_btn.clicked.connect(explorer.run_tests)
    explorer.test_view.watch_btn.clicked.connect(explorer.toggle_test_watch)
    explorer.test_view.filter_input.textChanged.connect(explorer.filter_tests)

def create_navigation_widget(explorer):
    """Create navigation bar with back/forward/up buttons and address bar"""
    nav_widget = QWidget()
    nav_layout = QHBoxLayout(nav_widget)
    nav_layout.setContentsMargins(0, 0, 0, 0)
    
    # Back/Forward buttons
    explorer.back_btn = QPushButton("←")
    explorer.back_btn.setFixedWidth(30)
    explorer.back_btn.clicked.connect(explorer.navigate_back)
    explorer.back_btn.setEnabled(False)
    nav_layout.addWidget(explorer.back_btn)
    
    explorer.forward_btn = QPushButton("→")
    explorer.forward_btn.setFixedWidth(30)
    explorer.forward_btn.clicked.connect(explorer.navigate_forward)
    explorer.forward_btn.setEnabled(False)
    nav_layout.addWidget(explorer.forward_btn)
    
    # Up button
    explorer.up_btn = QPushButton("↑")
    explorer.up_btn.setFixedWidth(30)
    explorer.up_btn.clicked.connect(explorer.navigate_up)
    nav_layout.addWidget(explorer.up_btn)
    
    # Address bar
    explorer.address_bar = AddressBar()
    explorer.address_bar.returnPressed.connect(explorer.navigate_to_address)
    nav_layout.addWidget(explorer.address_bar)
    
    # Refresh button
    refresh_btn = QPushButton("⟳")
    refresh_btn.setFixedWidth(30)
    refresh_btn.clicked.connect(explorer.refresh_view)
    nav_layout.addWidget(refresh_btn)
    
    return nav_widget

def create_tree_view(explorer):
    """Create and configure tree view"""
    tree_view = QTreeView()
    tree_view.setModel(explorer.model)
    tree_view.setHeaderHidden(False)
    tree_view.setAlternatingRowColors(False)
    tree_view.setAnimated(True)
    tree_view.setIndentation(20)
    tree_view.setSortingEnabled(True)
    
    # Configure selection and interaction
    tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
    tree_view.clicked.connect(explorer.handle_item_click)
    tree_view.doubleClicked.connect(explorer.handle_item_double_click)
    
    # Set column widths
    tree_view.setColumnWidth(0, 300)  # Name
    tree_view.setColumnWidth(1, 80)   # Size
    tree_view.setColumnWidth(2, 100)  # Type
    tree_view.setColumnWidth(3, 150)  # Date Modified
    
    return tree_view

def create_list_view(explorer):
    """Create and configure list view"""
    list_view = QListView()
    list_view.setModel(explorer.model)
    list_view.setViewMode(QListView.ViewMode.IconMode)
    list_view.setIconSize(QSize(48, 48))
    list_view.setGridSize(QSize(100, 80))
    list_view.setSpacing(10)
    list_view.setUniformItemSizes(True)
    list_view.setWrapping(True)
    list_view.setResizeMode(QListView.ResizeMode.Adjust)
    list_view.setWordWrap(True)
    list_view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
    
    # Configure selection and interaction
    list_view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
    list_view.clicked.connect(explorer.handle_item_click)
    list_view.doubleClicked.connect(explorer.handle_item_double_click)
    
    return list_view 