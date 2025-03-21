from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                           QLabel, QFileDialog, QProgressBar, QFrame)
from PyQt6.QtCore import Qt
from datetime import datetime
import os

class CompareDialog(QDialog):
    """Dialog for comparing two files"""
    
    def __init__(self, parent=None, file1=None, file2=None):
        super().__init__(parent)
        self.duplicate_finder = parent.duplicate_finder if parent else None
        self.file1 = file1
        self.file2 = file2
        self.setup_ui()
        
        # Compare files if both are provided
        if file1 and file2:
            self.compare_files()
        
    def setup_ui(self):
        """Initialize the UI components"""
        self.setWindowTitle("Compare Files")
        self.setMinimumWidth(600)
        
        layout = QVBoxLayout(self)
        
        # File selection
        file1_layout = QHBoxLayout()
        self.file1_label = QLabel("File 1:")
        self.file1_path = QLabel(self.file1 or "No file selected")
        self.file1_path.setWordWrap(True)
        file1_btn = QPushButton("Browse")
        file1_btn.clicked.connect(lambda: self.browse_file(1))
        file1_layout.addWidget(self.file1_label)
        file1_layout.addWidget(self.file1_path, 1)
        file1_layout.addWidget(file1_btn)
        layout.addLayout(file1_layout)
        
        file2_layout = QHBoxLayout()
        self.file2_label = QLabel("File 2:")
        self.file2_path = QLabel(self.file2 or "No file selected")
        self.file2_path.setWordWrap(True)
        file2_btn = QPushButton("Browse")
        file2_btn.clicked.connect(lambda: self.browse_file(2))
        file2_layout.addWidget(self.file2_label)
        file2_layout.addWidget(self.file2_path, 1)
        file2_layout.addWidget(file2_btn)
        layout.addLayout(file2_layout)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Results section
        self.results_layout = QVBoxLayout()
        
        # Basic info
        self.size1_label = QLabel()
        self.size2_label = QLabel()
        self.modified1_label = QLabel()
        self.modified2_label = QLabel()
        
        self.results_layout.addWidget(self.size1_label)
        self.results_layout.addWidget(self.size2_label)
        self.results_layout.addWidget(self.modified1_label)
        self.results_layout.addWidget(self.modified2_label)
        
        # Comparison results
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.results_layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.hide()
        self.results_layout.addWidget(self.progress_bar)
        
        layout.addLayout(self.results_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.compare_btn = QPushButton("Compare")
        self.compare_btn.clicked.connect(self.compare_files)
        self.compare_btn.setEnabled(bool(self.file1 and self.file2))
        button_layout.addWidget(self.compare_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def browse_file(self, file_num):
        """Open file browser to select a file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select File {file_num}",
            os.path.expanduser("~")
        )
        
        if file_path:
            if file_num == 1:
                self.file1 = file_path
                self.file1_path.setText(file_path)
            else:
                self.file2 = file_path
                self.file2_path.setText(file_path)
                
            # Enable compare button if both files selected
            self.compare_btn.setEnabled(bool(self.file1 and self.file2))
            
    def compare_files(self):
        """Compare the selected files"""
        if not self.file1 or not self.file2:
            return
            
        if not self.duplicate_finder:
            self.status_label.setText("Error: Duplicate finder not available")
            return
            
        # Show progress
        self.progress_bar.show()
        self.compare_btn.setEnabled(False)
        self.status_label.setText("Comparing files...")
        
        # Connect to comparison result signal
        self.duplicate_finder.comparison_result.connect(self.show_results)
        
        # Start comparison
        self.duplicate_finder.compare_files(self.file1, self.file2)
        
    def show_results(self, result):
        """Display comparison results"""
        self.progress_bar.hide()
        self.compare_btn.setEnabled(True)
        
        if result.get('error'):
            self.status_label.setText(f"Error: {result['error']}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            return
            
        # Update file info
        self.size1_label.setText(
            f"File 1 Size: {self.format_size(result['size1'])}"
        )
        self.size2_label.setText(
            f"File 2 Size: {self.format_size(result['size2'])}"
        )
        
        self.modified1_label.setText(
            f"File 1 Modified: {datetime.fromtimestamp(result['modified1']).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.modified2_label.setText(
            f"File 2 Modified: {datetime.fromtimestamp(result['modified2']).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Show comparison result
        if result['are_identical']:
            self.status_label.setText("Files are identical")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            if not result['size_match']:
                self.status_label.setText("Files are different (different sizes)")
            elif not result['quick_hash_match']:
                self.status_label.setText("Files are different (content mismatch)")
            elif not result['full_hash_match']:
                self.status_label.setText("Files are different (content mismatch)")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
    def format_size(self, size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB" 