from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QComboBox, QCheckBox, QProgressBar,
                           QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import os
import shutil
from datetime import datetime

class SortWorker(QThread):
    """Thread for sorting notes"""
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    
    def __init__(self, directory, sort_by, create_dirs=True):
        super().__init__()
        self.directory = directory
        self.sort_by = sort_by
        self.create_dirs = create_dirs
        
    def run(self):
        # Get all markdown files
        md_files = []
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith('.md'):
                    md_files.append(os.path.join(root, file))
        
        total_files = len(md_files)
        processed = 0
        
        for file_path in md_files:
            try:
                # Get file info
                filename = os.path.basename(file_path)
                mtime = os.path.getmtime(file_path)
                date = datetime.fromtimestamp(mtime)
                
                # Determine target directory based on sort criteria
                if self.sort_by == 'date':
                    # Sort by year/month
                    target_dir = os.path.join(
                        self.directory,
                        str(date.year),
                        date.strftime('%B')
                    )
                elif self.sort_by == 'tags':
                    # Sort by first tag (if any)
                    from ..widgets.explorer import extract_tags_from_file
                    tags = extract_tags_from_file(file_path)
                    if tags:
                        target_dir = os.path.join(self.directory, tags[0])
                    else:
                        target_dir = os.path.join(self.directory, 'Untagged')
                else:  # alphabetical
                    # Sort by first letter
                    first_letter = filename[0].upper()
                    if not first_letter.isalpha():
                        first_letter = '#'
                    target_dir = os.path.join(self.directory, first_letter)
                
                # Create target directory if needed
                if self.create_dirs:
                    os.makedirs(target_dir, exist_ok=True)
                
                # Move file
                target_path = os.path.join(target_dir, filename)
                if target_path != file_path:
                    shutil.move(file_path, target_path)
                    
            except Exception as e:
                print(f"Error sorting {file_path}: {str(e)}")
                
            processed += 1
            self.progress.emit(int(processed * 100 / total_files))
            
        self.finished.emit()

class SortDialog(QDialog):
    def __init__(self, explorer):
        super().__init__(explorer)
        self.explorer = explorer
        self.setWindowTitle("Sort Notes")
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        
        # Sort criteria selection
        criteria_layout = QHBoxLayout()
        criteria_layout.addWidget(QLabel("Sort by:"))
        
        self.criteria_combo = QComboBox()
        self.criteria_combo.addItems([
            "Date (Year/Month)",
            "Tags (First Tag)",
            "Alphabetical (First Letter)"
        ])
        criteria_layout.addWidget(self.criteria_combo)
        
        layout.addLayout(criteria_layout)
        
        # Create directories option
        self.create_dirs_check = QCheckBox("Create directories if needed")
        self.create_dirs_check.setChecked(True)
        layout.addWidget(self.create_dirs_check)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        sort_btn = QPushButton("Sort")
        sort_btn.clicked.connect(self.start_sorting)
        button_layout.addWidget(sort_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
    def start_sorting(self):
        """Start sorting notes"""
        # Map combo box selection to sort criteria
        criteria_map = {
            0: 'date',
            1: 'tags',
            2: 'alphabetical'
        }
        
        sort_by = criteria_map[self.criteria_combo.currentIndex()]
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Create and start worker thread
        self.worker = SortWorker(
            self.explorer.get_notes_vault_path(),
            sort_by,
            self.create_dirs_check.isChecked()
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.sorting_finished)
        self.worker.start()
        
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
        
    def sorting_finished(self):
        """Handle completion of sorting"""
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Sort Complete", 
                              "Notes have been sorted successfully.")
        # Refresh notes view
        self.explorer.refresh_notes_view() 