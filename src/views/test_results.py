from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QTreeWidget, QTreeWidgetItem, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon

class TestResultsView(QWidget):
    """View for displaying test results with filtering and watch capabilities"""
    
    # Signals
    run_tests = pyqtSignal()  # Emitted when run button clicked
    toggle_watch = pyqtSignal(bool)  # Emitted when watch mode toggled
    test_selected = pyqtSignal(dict)  # Emitted when a test is selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        
        # Run button
        self.run_button = QPushButton()
        self.run_button.setIcon(QIcon.fromTheme("system-run"))
        self.run_button.setToolTip("Run Tests")
        self.run_button.clicked.connect(self.run_tests.emit)
        toolbar.addWidget(self.run_button)
        
        # Watch button
        self.watch_button = QPushButton()
        self.watch_button.setIcon(QIcon.fromTheme("media-playback-start"))
        self.watch_button.setToolTip("Watch for Changes")
        self.watch_button.setCheckable(True)
        self.watch_button.clicked.connect(self.toggle_watch.emit)
        toolbar.addWidget(self.watch_button)
        
        # Filter input
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter tests...")
        self.filter_input.textChanged.connect(self.filter_results)
        toolbar.addWidget(self.filter_input)
        
        layout.addLayout(toolbar)
        
        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Test", "Status", "Duration", "Details"])
        self.results_tree.setAlternatingRowColors(True)
        self.results_tree.itemClicked.connect(self.handle_test_selected)
        layout.addWidget(self.results_tree)
        
        # Status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
    def update_results(self, results):
        """Update the view with new test results"""
        self.results_tree.clear()
        
        # Track statistics
        total = passed = failed = skipped = 0
        
        for test in results:
            total += 1
            
            item = QTreeWidgetItem(self.results_tree)
            item.setText(0, test["name"])
            item.setText(1, test["status"])
            item.setText(2, f"{test.get('duration', 0):.2f}s")
            
            # Store full test data for selection handling
            item.setData(0, Qt.ItemDataRole.UserRole, test)
            
            if test["status"] == "PASS":
                passed += 1
                item.setIcon(0, QIcon.fromTheme("dialog-ok"))
            elif test["status"] == "FAIL":
                failed += 1
                item.setIcon(0, QIcon.fromTheme("dialog-error"))
                if "error" in test:
                    item.setText(3, test["error"])
            elif test["status"] == "SKIP":
                skipped += 1
                item.setIcon(0, QIcon.fromTheme("dialog-question"))
                
        # Update status
        self.status_label.setText(
            f"Total: {total} | "
            f"Passed: {passed} | "
            f"Failed: {failed} | "
            f"Skipped: {skipped}"
        )
        
    def handle_test_selected(self, item):
        """Handle test selection"""
        test_data = item.data(0, Qt.ItemDataRole.UserRole)
        if test_data:
            self.test_selected.emit(test_data)
            
    def filter_results(self):
        """Filter test results based on search text"""
        filter_text = self.filter_input.text().lower()
        
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            matches = filter_text in item.text(0).lower()
            item.setHidden(not matches)
            
    def show_running(self):
        """Show running state"""
        self.run_button.setEnabled(False)
        self.status_label.setText("Running tests...")
        
    def show_ready(self):
        """Show ready state"""
        self.run_button.setEnabled(True)
        
    def parse_zig_test_output(self, output):
        """Parse Zig test output into structured results"""
        results = []
        current_test = None
        
        for line in output.splitlines():
            if line.startswith("Test"):
                if current_test:
                    results.append(current_test)
                    
                # Start new test
                current_test = {
                    "name": line.split('"')[1],
                    "status": "RUNNING"
                }
            elif current_test:
                if "All tests passed" in line:
                    current_test["status"] = "PASS"
                elif "error:" in line:
                    current_test["status"] = "FAIL"
                    current_test["error"] = line
                    
        # Add last test
        if current_test:
            results.append(current_test)
            
        return results 