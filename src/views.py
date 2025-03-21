from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QColor
import time

class TestResultsView(QWidget):
    """View for displaying test results"""
    
    test_selected = pyqtSignal(dict)  # Signal emitted when a test is selected
    run_tests = pyqtSignal()  # Signal to request test run
    toggle_watch = pyqtSignal(bool)  # Signal to toggle test watching
    filter_changed = pyqtSignal(str)  # Signal when filter text changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_signals()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top toolbar
        toolbar = QHBoxLayout()
        
        self.run_button = QPushButton("Run Tests")
        self.run_button.setIcon(QIcon.fromTheme("media-playback-start"))
        toolbar.addWidget(self.run_button)

        self.watch_button = QPushButton("Watch")
        self.watch_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.watch_button.setCheckable(True)
        toolbar.addWidget(self.watch_button)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter tests...")
        toolbar.addWidget(self.filter_input)

        layout.addLayout(toolbar)

        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Test", "Status", "Duration", "Message"])
        self.results_tree.setColumnWidth(0, 300)  # Test name column
        self.results_tree.setColumnWidth(1, 100)  # Status column
        self.results_tree.setColumnWidth(2, 100)  # Duration column
        self.results_tree.itemClicked.connect(self.handle_test_selected)
        layout.addWidget(self.results_tree)

        # Status bar
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.hide()
        status_layout.addWidget(self.progress_bar)

        self.stats_label = QLabel()
        status_layout.addWidget(self.stats_label)
        
        layout.addLayout(status_layout)

    def setup_signals(self):
        """Connect internal signals"""
        self.run_button.clicked.connect(self.run_tests.emit)
        self.watch_button.toggled.connect(self.toggle_watch.emit)
        self.filter_input.textChanged.connect(self.filter_changed.emit)
        self.filter_changed.connect(self.filter_results)

    def update_results(self, results):
        """Update the view with new test results"""
        self.results_tree.clear()
        
        total = passed = failed = skipped = 0
        
        for test_name, result in results.items():
            item = QTreeWidgetItem(self.results_tree)
            item.setText(0, test_name)
            
            # Set status and color
            status = result.get("status", "unknown")
            item.setText(1, status)
            
            if status == "passed":
                item.setForeground(1, QColor("green"))
                passed += 1
            elif status == "failed":
                item.setForeground(1, QColor("red"))
                failed += 1
            elif status == "skipped":
                item.setForeground(1, QColor("gray"))
                skipped += 1
                
            # Duration
            duration = result.get("duration", 0)
            item.setText(2, f"{duration:.2f}s")
            
            # Error message for failed tests
            if "error" in result:
                error_item = QTreeWidgetItem(item)
                error_item.setText(0, "Error")
                error_item.setText(3, result["error"])
                error_item.setForeground(3, QColor("red"))
                
            # Memory leaks for Zig tests
            if "leaks" in result:
                leak_item = QTreeWidgetItem(item)
                leak_item.setText(0, "Memory Leaks")
                leak_item.setText(3, result["leaks"])
                leak_item.setForeground(3, QColor("orange"))
                
            # Compiler errors
            if "compile_error" in result:
                compile_item = QTreeWidgetItem(item)
                compile_item.setText(0, "Compile Error")
                compile_item.setText(3, result["compile_error"])
                compile_item.setForeground(3, QColor("red"))
                
            total += 1

        # Update stats
        self.stats_label.setText(
            f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}"
        )
        
        if failed > 0:
            self.status_label.setText("Tests Failed")
            self.status_label.setStyleSheet("color: red")
        elif passed == total:
            self.status_label.setText("All Tests Passed")
            self.status_label.setStyleSheet("color: green")
        else:
            self.status_label.setText("Tests Completed")
            self.status_label.setStyleSheet("")

    def handle_test_selected(self, item):
        """Handle when a test is selected in the tree"""
        if not item.parent():  # Only handle top-level items (test cases)
            test_data = {
                "name": item.text(0),
                "status": item.text(1),
                "duration": float(item.text(2).rstrip("s")),
            }
            
            # Get error message if present
            for i in range(item.childCount()):
                child = item.child(i)
                if child.text(0) == "Error":
                    test_data["error"] = child.text(3)
                elif child.text(0) == "Memory Leaks":
                    test_data["leaks"] = child.text(3)
                elif child.text(0) == "Compile Error":
                    test_data["compile_error"] = child.text(3)
                    
            self.test_selected.emit(test_data)

    def show_running(self):
        """Show that tests are running"""
        self.status_label.setText("Running Tests...")
        self.status_label.setStyleSheet("")
        self.progress_bar.setRange(0, 0)  # Show busy indicator
        self.progress_bar.show()
        self.run_button.setEnabled(False)
        
    def show_ready(self):
        """Show that view is ready for test run"""
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("")
        self.progress_bar.hide()
        self.run_button.setEnabled(True)

    def filter_results(self, pattern):
        """Filter test results by pattern"""
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            item.setHidden(pattern.lower() not in item.text(0).lower())

    def parse_zig_test_output(self, output):
        """Parse Zig test output into result format"""
        results = {}
        current_test = None
        
        for line in output.split('\n'):
            if line.startswith('test "'):
                # New test case
                current_test = line[6:].split('"')[0]
                results[current_test] = {
                    "status": "running",
                    "start_time": time.time()
                }
            elif line.startswith('All ') and line.endswith(' tests passed.'):
                # All tests passed
                for test in results:
                    if results[test]["status"] == "running":
                        results[test]["status"] = "passed"
            elif "error:" in line.lower():
                # Error in test
                if current_test:
                    results[current_test]["status"] = "failed"
                    results[current_test]["error"] = line
            elif "memory leak detected" in line.lower():
                # Memory leak
                if current_test:
                    results[current_test]["leaks"] = line
            elif "compilation failed" in line.lower():
                # Compilation error
                if current_test:
                    results[current_test]["status"] = "failed"
                    results[current_test]["compile_error"] = line
                    
        # Calculate durations and set final status
        current_time = time.time()
        for test in results:
            if "start_time" in results[test]:
                results[test]["duration"] = current_time - results[test]["start_time"]
                del results[test]["start_time"]
            if results[test]["status"] == "running":
                results[test]["status"] = "unknown"
                
        return results 