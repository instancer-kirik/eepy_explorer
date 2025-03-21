from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                           QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar,
                           QCheckBox, QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
import os
from datetime import datetime

class DuplicateDialog(QDialog):
    """Dialog for managing duplicate files"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.duplicate_finder = parent.duplicate_finder
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        self.setWindowTitle("Duplicate Files")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Progress section
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("Scanning files...")
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)
        
        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels([
            "Filename", "Path", "Size", "Modified", "Status"
        ])
        self.results_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_tree)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.auto_select_btn = QPushButton("Auto-select Duplicates")
        self.auto_select_btn.clicked.connect(self.auto_select_duplicates)
        button_layout.addWidget(self.auto_select_btn)
        
        self.clear_btn = QPushButton("Clear Selection")
        self.clear_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        button_layout.addWidget(self.delete_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.duplicate_finder.duplicates_found.connect(self.show_results)
        self.duplicate_finder.progress_updated.connect(self.update_progress)
        
    def scan_directory(self, directory):
        """Start scanning directory for duplicates"""
        self.progress_bar.setRange(0, 0)  # Show busy indicator
        self.progress_label.setText("Scanning files...")
        self.results_tree.clear()
        
        # Start duplicate search
        self.duplicate_finder.find_duplicates(directory)
        
    def update_progress(self, current, total):
        """Update progress bar"""
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processed {current} of {total} files...")
        
    def show_results(self, duplicates):
        """Display duplicate files in tree"""
        self.results_tree.clear()
        total_space = 0
        total_duplicates = 0
        
        for hash_value, files in duplicates.items():
            group_item = QTreeWidgetItem(self.results_tree)
            group_item.setText(0, f"Group ({len(files)} files)")
            group_item.setExpanded(True)
            
            # Sort files by modification time
            files.sort(key=lambda x: x['modified'])
            
            for file_info in files:
                file_item = QTreeWidgetItem(group_item)
                file_item.setText(0, file_info['filename'])
                file_item.setText(1, file_info['path'])
                file_item.setText(2, self.format_size(file_info['size']))
                file_item.setText(3, datetime.fromtimestamp(
                    file_info['modified']).strftime('%Y-%m-%d %H:%M:%S'))
                
                # Set status
                if file_info['is_original']:
                    status = "Original"
                    file_item.setIcon(0, QIcon.fromTheme("document-save"))
                else:
                    status = "Duplicate"
                    if file_info['suffix_pattern']:
                        status += f" (Copy pattern: {file_info['suffix_pattern']})"
                    file_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                    total_duplicates += 1
                    total_space += file_info['size']
                
                file_item.setText(4, status)
                
                # Add checkbox
                if not file_info['is_original']:
                    file_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        # Update progress label with summary
        self.progress_label.setText(
            f"Found {total_duplicates} duplicates "
            f"({self.format_size(total_space)} wasted space)"
        )
        
        # Enable buttons
        self.auto_select_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        
    def auto_select_duplicates(self):
        """Automatically select duplicate files based on suggestions"""
        root = self.results_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            # Skip first (original) file
            for j in range(1, group.childCount()):
                item = group.child(j)
                if "Duplicate" in item.text(4):
                    item.setCheckState(0, Qt.CheckState.Checked)
                    
    def clear_selection(self):
        """Clear all checkboxes"""
        root = self.results_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            for j in range(group.childCount()):
                item = group.child(j)
                if item.checkState(0) == Qt.CheckState.Checked:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    
    def delete_selected(self):
        """Delete selected duplicate files"""
        selected_files = []
        root = self.results_tree.invisibleRootItem()
        
        # Collect selected files
        for i in range(root.childCount()):
            group = root.child(i)
            for j in range(group.childCount()):
                item = group.child(j)
                if item.checkState(0) == Qt.CheckState.Checked:
                    selected_files.append({
                        'action': 'delete',
                        'source': item.text(1)
                    })
        
        if not selected_files:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select files to delete."
            )
            return
            
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {len(selected_files)} files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete files
            results = self.duplicate_finder.resolve_duplicates(selected_files)
            
            # Show results
            if results['failed']:
                errors = "\n".join(
                    f"- {action['source']}: {action['error']}"
                    for action in results['failed']
                )
                QMessageBox.warning(
                    self,
                    "Deletion Errors",
                    f"Some files could not be deleted:\n{errors}"
                )
            
            # Refresh tree
            self.remove_deleted_items(results['succeeded'])
            
            QMessageBox.information(
                self,
                "Deletion Complete",
                f"Successfully deleted {len(results['succeeded'])} files."
            )
            
    def remove_deleted_items(self, deleted_actions):
        """Remove deleted items from tree"""
        deleted_paths = [action['source'] for action in deleted_actions]
        root = self.results_tree.invisibleRootItem()
        
        # Remove items and update groups
        for i in range(root.childCount() - 1, -1, -1):
            group = root.child(i)
            for j in range(group.childCount() - 1, -1, -1):
                item = group.child(j)
                if item.text(1) in deleted_paths:
                    group.removeChild(item)
            
            # Remove empty groups
            if group.childCount() <= 1:  # Only original file left
                root.removeChild(group)
                
    def format_size(self, size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB" 