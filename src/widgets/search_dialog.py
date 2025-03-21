from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QLineEdit, QTreeWidget, QTreeWidgetItem,
                           QMessageBox, QProgressBar, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os
import re

class SearchWorker(QThread):
    """Thread for searching notes"""
    progress = pyqtSignal(int)
    result = pyqtSignal(str, str, str)  # file_path, line_number, line_content
    finished = pyqtSignal()
    
    def __init__(self, directory, query, case_sensitive=False):
        super().__init__()
        self.directory = directory
        self.query = query
        self.case_sensitive = case_sensitive
        
    def run(self):
        # Get all markdown files
        md_files = []
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith('.md'):
                    md_files.append(os.path.join(root, file))
        
        total_files = len(md_files)
        processed = 0
        
        # Compile regex pattern
        flags = 0 if self.case_sensitive else re.IGNORECASE
        pattern = re.compile(self.query, flags)
        
        for file_path in md_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            self.result.emit(
                                file_path,
                                str(line_num),
                                line.rstrip()
                            )
            except Exception as e:
                print(f"Error searching {file_path}: {str(e)}")
                
            processed += 1
            self.progress.emit(int(processed * 100 / total_files))
            
        self.finished.emit()

class SearchDialog(QDialog):
    def __init__(self, explorer):
        super().__init__(explorer)
        self.explorer = explorer
        self.setWindowTitle("Search Notes")
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        
        # Search input
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search query")
        self.search_input.returnPressed.connect(self.start_search)
        search_layout.addWidget(self.search_input)
        
        self.case_sensitive_check = QCheckBox("Case sensitive")
        search_layout.addWidget(self.case_sensitive_check)
        
        layout.addLayout(search_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Results tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['File', 'Line', 'Content'])
        self.tree.setColumnCount(3)
        self.tree.itemDoubleClicked.connect(self.open_selected_file)
        layout.addWidget(self.tree)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.start_search)
        button_layout.addWidget(search_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_results)
        button_layout.addWidget(clear_btn)
        
        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(self.open_selected_file)
        button_layout.addWidget(open_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def start_search(self):
        """Start searching notes"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Empty Query", 
                              "Please enter a search query.")
            return
            
        # Clear previous results
        self.clear_results()
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Create and start worker thread
        self.worker = SearchWorker(
            self.explorer.get_notes_vault_path(),
            query,
            self.case_sensitive_check.isChecked()
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.result.connect(self.add_result)
        self.worker.finished.connect(self.search_finished)
        self.worker.start()
        
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        
    def add_result(self, file_path, line_num, line_content):
        """Add search result to tree"""
        # Create or get file item
        file_item = None
        for i in range(self.tree.topLevelItemCount()):
            if self.tree.topLevelItem(i).text(0) == file_path:
                file_item = self.tree.topLevelItem(i)
                break
                
        if not file_item:
            file_item = QTreeWidgetItem([file_path])
            file_item.setData(0, Qt.ItemDataRole.UserRole, file_path)  # Store file path as data
            self.tree.addTopLevelItem(file_item)
            
        # Add result item
        result_item = QTreeWidgetItem([
            '',  # Empty for file column
            line_num,
            line_content
        ])
        result_item.setData(0, Qt.ItemDataRole.UserRole, file_path)  # Store file path in result items too
        file_item.addChild(result_item)
        
    def clear_results(self):
        """Clear search results"""
        self.tree.clear()
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        
    def search_finished(self):
        """Handle completion of search"""
        self.progress_bar.setVisible(False)
        if self.tree.topLevelItemCount() == 0:
            QMessageBox.information(self, "No Results", 
                                  "No matches found.")
                                  
    def open_selected_file(self):
        """Open the selected file from the results tree"""
        selected_item = self.tree.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Selection", "Please select a result to open.")
            return
            
        # Get file path from the item data
        file_path = selected_item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path:
            # Try getting from parent if this is a result item
            parent = selected_item.parent()
            if parent:
                file_path = parent.data(0, Qt.ItemDataRole.UserRole)
                
        if file_path and os.path.exists(file_path):
            # Use the explorer's file opening method
            try:
                if hasattr(self.explorer, 'open_in_internal_editor'):
                    self.explorer.open_in_internal_editor(file_path)
                else:
                    # Fallback to system default application
                    import subprocess
                    subprocess.Popen(['xdg-open', file_path])
            except Exception as e:
                QMessageBox.warning(self, "Error Opening File", f"Could not open file: {str(e)}") 