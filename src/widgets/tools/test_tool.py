import os
import asyncio
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QSplitter, QMessageBox

class TestTool(QObject):
    """Tool for managing test execution and monitoring"""
    
    # Signals
    test_started = pyqtSignal()
    test_finished = pyqtSignal(list)  # list of test results
    test_error = pyqtSignal(str)
    
    def __init__(self, explorer):
        super().__init__()
        self.explorer = explorer
        self.test_watcher = None
        self.test_runner = None
        
    async def run_tests(self):
        """Run project tests"""
        # Show the test panel if it's hidden
        self.explorer.test_view.show()
        splitter = self.explorer.test_view.parent()
        if isinstance(splitter, QSplitter):
            sizes = splitter.sizes()
            if sizes[1] < 100:  # If test panel is too small or collapsed
                total = sum(sizes)
                splitter.setSizes([total * 2 // 3, total // 3])
        
        # Start running tests
        self.explorer.test_view.show_running()
        self.test_started.emit()
        
        try:
            # Get project root
            project_root = os.path.dirname(
                self.explorer.model.filePath(self.explorer.file_tree.rootIndex())
            )
            
            # Run tests in background thread
            process = await asyncio.create_subprocess_exec(
                "zig", "build", "test",
                cwd=project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode() + stderr.decode()
            
            # Parse and update results
            results = self.explorer.test_view.parse_zig_test_output(output)
            self.test_finished.emit(results)
            self.explorer.test_view.update_results(results)
            
        except Exception as e:
            error_msg = f"Error running tests: {str(e)}"
            self.test_error.emit(error_msg)
            self.explorer.show_error(error_msg)
        finally:
            self.explorer.test_view.show_ready()
            
    async def toggle_watch(self, checked):
        """Toggle test file watching"""
        if checked:
            try:
                # Get project root
                project_root = os.path.dirname(
                    self.explorer.model.filePath(self.explorer.file_tree.rootIndex())
                )
                
                # Start watching test files
                if not self.test_watcher:
                    self.test_watcher = self.explorer.test_runner.watch_tests()
                    self.explorer.status_bar.showMessage("Watching for changes...")
                    
                    async for results in self.test_watcher:
                        self.test_finished.emit(results)
                        self.explorer.test_view.update_results(results)
                        
            except Exception as e:
                error_msg = f"Failed to watch tests: {str(e)}"
                self.test_error.emit(error_msg)
                self.explorer.show_error(error_msg)
                self.explorer.test_view.watch_button.setChecked(False)
        else:
            # Stop watching
            if self.test_watcher:
                self.test_watcher.cancel()
                self.test_watcher = None
            self.explorer.status_bar.showMessage("Test watch stopped", 3000)
            
    def handle_test_selected(self, test_data):
        """Handle when a test is selected in the results view"""
        # If there's an error, show it in the preview panel
        if "error" in test_data:
            # Create preview tab for error
            from PyQt6.QtWidgets import QTextEdit
            preview = QTextEdit()
            preview.setReadOnly(True)
            preview.setText(test_data["error"])
            
            # Add to preview panel
            self.explorer.preview_tabs.addTab(preview, f"Test: {test_data['name']}")
            self.explorer.preview_tabs.setCurrentWidget(preview)
            
    def filter_tests(self, filter_text):
        """Filter displayed test results"""
        if not filter_text:
            # Show all items
            for i in range(self.explorer.test_view.results_tree.topLevelItemCount()):
                self.explorer.test_view.results_tree.topLevelItem(i).setHidden(False)
            return
            
        # Hide non-matching items
        filter_text = filter_text.lower()
        for i in range(self.explorer.test_view.results_tree.topLevelItemCount()):
            item = self.explorer.test_view.results_tree.topLevelItem(i)
            item.setHidden(not filter_text in item.text(0).lower())
