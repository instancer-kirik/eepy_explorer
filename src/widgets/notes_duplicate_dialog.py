from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                           QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar,
                           QCheckBox, QMessageBox, QHeaderView, QComboBox, QGroupBox,
                           QSplitter, QWidget, QPlainTextEdit, QMenu, QLineEdit, QAbstractItemView, QSpacerItem, QSizePolicy, QFileDialog, QTabWidget, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QTimer
from PyQt6.QtGui import QIcon, QColor, QBrush, QFont
import os
import re
import json
from datetime import datetime
from pathlib import Path
import hashlib
from ..utils.utils import get_common_suffix_patterns, has_suffix_pattern
from PyQt6.QtWidgets import QApplication
from collections import defaultdict
import platform
import subprocess
import logging

from ..tools.duplicate_finder import DuplicateFinderWorker, SuffixDuplicateFinderWorker

class NotesDuplicateScanner(QThread):
    """Thread for scanning duplicate notes"""
    progress = pyqtSignal(int, int)  # Current, Total
    finished = pyqtSignal(dict)  # Emitted when duplicates are found
    
    def __init__(self, directory, scan_mode="content", parent=None):
        super().__init__(parent)
        self.directory = directory
        self.scan_mode = scan_mode  # "content", "title", "tags", "suffix"
        self.duplicate_finder = parent.duplicate_finder if parent else None
        
    def run(self):
        """Run the duplicate scan"""
        if self.scan_mode == "content":
            # Use the standard duplicate finder for content-based duplicates
            duplicates = self.duplicate_finder.find_duplicates(
                self.directory, 
                recursive=True,
                file_extensions=['.md']
            )
            self.finished.emit(duplicates)
        elif self.scan_mode == "title":
            self.find_title_duplicates()
        elif self.scan_mode == "tags":
            self.find_tag_duplicates()
        elif self.scan_mode == "suffix":
            self.find_suffix_duplicates()
        else:
            self.finished.emit({})
            
    def find_title_duplicates(self):
        """Find notes with duplicate titles"""
        title_groups = {}
        total_files = 0
        processed_files = 0
        
        # First pass: count files
        for root, _, files in os.walk(self.directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    total_files += 1
        
        self.progress.emit(0, total_files)
        
        # Second pass: group by title
        for root, _, files in os.walk(self.directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    filepath = os.path.join(root, filename)
                    
                    # Extract title from filename (remove extension)
                    title = os.path.splitext(filename)[0]
                    
                    # Add to title group
                    if title not in title_groups:
                        title_groups[title] = []
                    
                    title_groups[title].append(filepath)
                    
                    processed_files += 1
                    if processed_files % 10 == 0:
                        self.progress.emit(processed_files, total_files)
        
        # Filter for duplicates and format results
        duplicates = {}
        for title, filepaths in title_groups.items():
            if len(filepaths) > 1:
                # Create a unique hash for this group
                group_hash = f"title_{title}"
                duplicates[group_hash] = self.analyze_title_duplicates(filepaths, title)
        
        self.progress.emit(total_files, total_files)
        self.finished.emit(duplicates)
    
    def analyze_title_duplicates(self, filepaths, title):
        """Analyze duplicate titles"""
        results = []
        
        for path in filepaths:
            filename = os.path.basename(path)
            
            # Analyze file
            info = {
                'path': path,
                'filename': filename,
                'size': os.path.getsize(path),
                'modified': os.path.getmtime(path),
                'is_original': False,  # Will determine below
                'suffix_pattern': None,
                'title': title,
                'tags': self.extract_tags(path)
            }
            
            results.append(info)
        
        # Sort results by modified time
        results.sort(key=lambda x: x['modified'])
        
        # Mark oldest file as original
        results[0]['is_original'] = True
            
        return results
    
    def find_tag_duplicates(self):
        """Find notes with similar tags"""
        tag_groups = {}
        note_tags = {}
        total_files = 0
        processed_files = 0
        
        # First pass: count files
        for root, _, files in os.walk(self.directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    total_files += 1
        
        self.progress.emit(0, total_files)
        
        # Second pass: extract tags from files
        for root, _, files in os.walk(self.directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    filepath = os.path.join(root, filename)
                    
                    # Extract tags
                    tags = self.extract_tags(filepath)
                    if tags:
                        note_tags[filepath] = tags
                        
                        # Add to tag groups
                        for tag in tags:
                            if tag not in tag_groups:
                                tag_groups[tag] = []
                            tag_groups[tag].append(filepath)
                    
                    processed_files += 1
                    if processed_files % 10 == 0:
                        self.progress.emit(processed_files, total_files)
        
        # Find notes with similar tag sets
        duplicates = {}
        processed = set()
        
        for filepath, tags in note_tags.items():
            if filepath in processed:
                continue
                
            # Find notes with similar tags (at least 80% match)
            similar_notes = []
            for other_path, other_tags in note_tags.items():
                if filepath != other_path and other_path not in processed:
                    # Calculate tag similarity
                    common_tags = set(tags) & set(other_tags)
                    if common_tags and len(common_tags) >= 0.8 * min(len(tags), len(other_tags)):
                        similar_notes.append(other_path)
            
            # If we found similar notes, add them as a duplicate group
            if similar_notes:
                similar_notes.append(filepath)
                processed.update(similar_notes)
                
                # Create a unique hash for this group
                group_hash = f"tags_{'_'.join(sorted(tags))}"
                duplicates[group_hash] = self.analyze_tag_duplicates(similar_notes, tags)
        
        self.progress.emit(total_files, total_files)
        self.finished.emit(duplicates)
    
    def analyze_tag_duplicates(self, filepaths, common_tags):
        """Analyze duplicate tags"""
        results = []
        
        for path in filepaths:
            filename = os.path.basename(path)
            
            # Analyze file
            info = {
                'path': path,
                'filename': filename,
                'size': os.path.getsize(path),
                'modified': os.path.getmtime(path),
                'is_original': False,  # Will determine below
                'suffix_pattern': None,
                'tags': self.extract_tags(path)
            }
            
            results.append(info)
        
        # Sort results by modified time
        results.sort(key=lambda x: x['modified'])
        
        # Mark oldest file as original
        results[0]['is_original'] = True
            
        return results
    
    def extract_tags(self, filepath):
        """Extract tags from markdown file"""
        tags = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Extract tags from YAML front matter
                yaml_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
                if yaml_match:
                    yaml_content = yaml_match.group(1)
                    # Look for tags: [...] or tags:
                    tag_match = re.search(r'tags:\s*\[(.*?)\]', yaml_content)
                    if tag_match:
                        # Extract tags from array format
                        tag_str = tag_match.group(1)
                        tags.extend([t.strip().strip('"\'') for t in tag_str.split(',')])
                    else:
                        # Look for YAML list format
                        tag_lines = re.findall(r'tags:\s*\n((?:[ \t]*-.*\n)+)', yaml_content)
                        if tag_lines:
                            for line in tag_lines[0].split('\n'):
                                tag_item = re.search(r'[ \t]*-[ \t]*(.*?)[ \t]*$', line)
                                if tag_item:
                                    tags.append(tag_item.group(1).strip('"\''))
                
                # Extract inline tags (#tag)
                inline_tags = re.findall(r'#([a-zA-Z0-9_-]+)', content)
                tags.extend(inline_tags)
                
                # Remove duplicates and return
                return list(set(tags))
        except Exception as e:
            print(f"Error extracting tags from {filepath}: {str(e)}")
            return []
    
    def find_suffix_duplicates(self):
        """Find notes with specific suffixes that indicate duplicates"""
        # Common suffix patterns that indicate duplicates
        suffix_patterns = [
            "-surfacepro6", 
            "-copy",
            " copy",
            " (copy)",
            " (1)",
            " (2)",
            "_copy",
            "_1",
            "_2"
        ]
        
        suffix_groups = {}
        total_files = 0
        processed_files = 0
        
        # First pass: count files
        for root, _, files in os.walk(self.directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    total_files += 1
        
        self.progress.emit(0, total_files)
        
        # Second pass: find files with suffix patterns and group them
        file_base_map = {}  # Map to track base names to file paths
        
        # First collect all files and their base names
        for root, _, files in os.walk(self.directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    filepath = os.path.join(root, filename)
                    base_name = os.path.splitext(filename)[0]
                    
                    # Store in a mapping for later processing
                    key = os.path.join(root, base_name)
                    if key not in file_base_map:
                        file_base_map[key] = []
                    file_base_map[key].append((filepath, base_name, False))
                    
                    processed_files += 1
                    if processed_files % 10 == 0:
                        self.progress.emit(processed_files, total_files)
        
        # Now identify duplicates based on suffix patterns
        for key, file_list in file_base_map.items():
            # Skip single files
            if len(file_list) <= 1:
                continue
            
            # Check each file for suffix patterns
            has_suffix = False
            group_files = []
            
            for file_path, base_name, _ in file_list:
                # Check if this file has any of the suffix patterns
                is_duplicate = False
                detected_suffix = None
                
                for suffix in suffix_patterns:
                    if suffix in base_name:
                        is_duplicate = True
                        detected_suffix = suffix
                        has_suffix = True
                        break
                
                group_files.append((file_path, base_name, is_duplicate, detected_suffix))
            
            # If we found at least one file with a suffix, create a duplicate group
            if has_suffix:
                group_key = f"{key}"
                suffix_groups[group_key] = [file[0] for file in group_files]  # Store just the paths
        
        # Format results
        duplicates = {}
        for group_key, filepaths in suffix_groups.items():
            # Remove duplicates in the group
            filepaths = list(set(filepaths))
            if len(filepaths) > 1:
                # Create a unique hash for this group
                group_hash = f"suffix_{os.path.basename(group_key)}"
                duplicates[group_hash] = self.analyze_suffix_duplicates(filepaths, suffix_patterns)
        
        self.progress.emit(total_files, total_files)
        return duplicates
    
    def analyze_suffix_duplicates(self, filepaths, suffix_patterns):
        """Analyze suffix-based duplicates"""
        results = []
        
        # First pass - identify which files have suffixes
        for path in filepaths:
            filename = os.path.basename(path)
            base_name = os.path.splitext(filename)[0]
            
            # Detect if this file has a suffix pattern
            detected_suffix = None
            for suffix in suffix_patterns:
                if suffix in base_name:
                    detected_suffix = suffix
                    break
            
            # Analyze file
            info = {
                'path': path,
                'filename': filename,
                'size': os.path.getsize(path),
                'modified': os.path.getmtime(path),
                'is_original': detected_suffix is None,  # Mark files without suffix as original
                'suffix_pattern': detected_suffix,
                'tags': self.extract_tags(path)
            }
            
            results.append(info)
        
        # Check if we need to handle the special case where all files have suffixes
        all_have_suffixes = all(result['suffix_pattern'] is not None for result in results)
        
        if all_have_suffixes and len(results) > 0:
            # For the case where all files have suffixes, mark the base filename as original
            # Find the shortest filename (likely the base name)
            results.sort(key=lambda x: len(x['filename']))
            # Mark the first (shortest) as original
            results[0]['is_original'] = True
        
        # Ensure we've identified at least one original file
        has_original = any(result['is_original'] for result in results)
        
        if not has_original and len(results) > 0:
            # If no file was marked as original, mark the oldest file as original
            results.sort(key=lambda x: x['modified'])
            results[0]['is_original'] = True
            results[0]['suffix_pattern'] = None  # Clear the suffix pattern for the designated original
        
        # Sort by status (original first) then by modified time (newest first)
        results.sort(key=lambda x: (not x['is_original'], -x['modified']))
        
        return results

class NotesDuplicateDialog(QDialog):
    """Dialog for managing duplicate notes"""
    
    def __init__(self, parent=None):
        """Initialize the dialog"""
        super().__init__(parent)
        
        # Store reference to parent explorer if available
        self.explorer = parent
        
        # Get notes directory path from parent if available
        self.notes_vault_path = None
        if parent and hasattr(parent, 'get_notes_vault_path'):
            self.notes_vault_path = parent.get_notes_vault_path()
        elif parent and hasattr(parent, 'get_notes_dir'):
            self.notes_vault_path = parent.get_notes_dir()
        
        # Add directory comparison mode flag
        self.directory_comparison_mode = False
        self.comparison_directories = []
        
        # Initialize worker related variables
        self.worker = None
        self.worker_thread = None
        self.worker_running = False
        
        # Setup UI
        self.setup_ui()
        
        # Initialize the results tree
        self.duplicates = {}
        
        # Show the dialog
        self.setWindowTitle("Find and Manage Duplicate Notes")
        self.resize(900, 600)
        
    def setup_ui(self):
        """Initialize the UI components"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Search options group
        search_group = QGroupBox("Search Options")
        search_layout = QVBoxLayout(search_group)
        
        # Path input
        path_layout = QHBoxLayout()
        path_label = QLabel("Directory to scan:")
        self.path_edit = QLineEdit()
        if self.notes_vault_path:
            self.path_edit.setText(self.notes_vault_path)
        else:
            self.path_edit.setText(os.path.expanduser("~/Notes"))
        path_browse = QPushButton("Browse")
        path_browse.clicked.connect(self.browse_directory)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(path_browse)
        search_layout.addLayout(path_layout)
        
        # Add second directory option for comparison mode
        self.multi_dir_checkbox = QCheckBox("Compare two directories")
        self.multi_dir_checkbox.toggled.connect(self.toggle_directory_comparison_mode)
        search_layout.addWidget(self.multi_dir_checkbox)
        
        # Second directory selection (hidden by default)
        self.second_dir_layout = QHBoxLayout()
        second_dir_label = QLabel("Second directory:")
        self.second_dir_edit = QLineEdit()
        second_dir_browse = QPushButton("Browse")
        second_dir_browse.clicked.connect(self.browse_second_directory)
        self.second_dir_layout.addWidget(second_dir_label)
        self.second_dir_layout.addWidget(self.second_dir_edit, 1)
        self.second_dir_layout.addWidget(second_dir_browse)
        search_layout.addLayout(self.second_dir_layout)
        self.second_dir_layout.setVisible(False)  # Initially hidden
        
        # Add note about cross-directory comparison
        self.compare_dirs_note = QLabel(
            "Cross-directory mode will compare all files between the two directories to find duplicates, "
            "even if they have different names or are in different sub-folders."
        )
        self.compare_dirs_note.setWordWrap(True)
        self.compare_dirs_note.setStyleSheet("font-style: italic; color: #555;")
        search_layout.addWidget(self.compare_dirs_note)
        self.compare_dirs_note.setVisible(False)  # Initially hidden
        
        # Search criteria (similar layout as before with added explanations)
        criteria_layout = QHBoxLayout()
        criteria_label = QLabel("Search for duplicates by:")
        self.criteria_combo = QComboBox()
        self.criteria_combo.addItem("Content Hash (exact duplicates)")
        self.criteria_combo.addItem("Filename Suffix (copy indicators)")
        self.criteria_combo.addItem("Note Title")
        self.criteria_combo.addItem("Similar Tags")
        criteria_layout.addWidget(criteria_label)
        criteria_layout.addWidget(self.criteria_combo, 1)
        search_layout.addLayout(criteria_layout)
        
        # Criteria explanation labels
        self.content_explanation = QLabel(
            "Content hash mode identifies byte-identical files, regardless of name."
        )
        self.suffix_explanation = QLabel(
            "Suffix mode finds files that appear to be copies (e.g., file-copy.md, file-surfacepro6.md)."
        )
        self.title_explanation = QLabel(
            "Title mode groups notes with the same filename but in different locations."
        )
        self.tag_explanation = QLabel(
            "Tag mode finds notes that share similar tags (80% similarity)."
        )
        
        # Style the explanations
        for label in [self.content_explanation, self.suffix_explanation, 
                     self.title_explanation, self.tag_explanation]:
            label.setWordWrap(True)
            label.setStyleSheet("font-style: italic; color: #555; margin-left: 10px;")
            search_layout.addWidget(label)
        
        # Initially show only the content explanation
        self.suffix_explanation.hide()
        self.title_explanation.hide()
        self.tag_explanation.hide()
        
        # Connect the combo box change event to update explanations
        self.criteria_combo.currentIndexChanged.connect(self.update_search_explanation)
        
        # Advanced options checkbox
        self.advanced_checkbox = QCheckBox("Show advanced options")
        self.advanced_checkbox.toggled.connect(self.toggle_advanced_options)
        search_layout.addWidget(self.advanced_checkbox)
        
        # Advanced options group (hidden by default)
        self.advanced_options = QGroupBox("Advanced Options")
        advanced_layout = QVBoxLayout(self.advanced_options)
        
        # Include subdirectories option
        self.recursive_checkbox = QCheckBox("Include subdirectories")
        self.recursive_checkbox.setChecked(True)
        advanced_layout.addWidget(self.recursive_checkbox)
        
        # Auto-select identical option
        self.auto_select_checkbox = QCheckBox("Auto-select duplicates for deletion")
        self.auto_select_checkbox.setChecked(True)
        self.auto_select_checkbox.setToolTip("Automatically select files that appear to be duplicates")
        advanced_layout.addWidget(self.auto_select_checkbox)
        
        # Hide identical groups
        self.hide_identical_checkbox = QCheckBox("Hide 100% identical groups")
        self.hide_identical_checkbox.setChecked(False)
        self.hide_identical_checkbox.setToolTip("Hide groups where all files are identical")
        advanced_layout.addWidget(self.hide_identical_checkbox)
        
        # Add advanced options to layout (hidden by default)
        search_layout.addWidget(self.advanced_options)
        self.advanced_options.hide()
        
        # Search button
        search_button_layout = QHBoxLayout()
        self.search_button = QPushButton("Find Duplicates")
        self.search_button.clicked.connect(self.start_search)
        search_button_layout.addStretch()
        search_button_layout.addWidget(self.search_button)
        search_layout.addLayout(search_button_layout)
        
        # Add search options to main layout
        main_layout.addWidget(search_group)
        
        # Results group (initially hidden)
        self.results_group = QGroupBox("Results")
        self.results_group.setVisible(False)
        results_layout = QVBoxLayout(self.results_group)
        
        # Results toolbar
        toolbar_layout = QHBoxLayout()
        
        # Action dropdown
        action_label = QLabel("Action:")
        self.action_combo = QComboBox()
        self.action_combo.addItem("Compare Selected")
        self.action_combo.addItem("Delete Selected")
        self.action_combo.addItem("Merge Selected")
        toolbar_layout.addWidget(action_label)
        toolbar_layout.addWidget(self.action_combo)
        
        # Apply button
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_selection)
        toolbar_layout.addWidget(self.apply_button)
        
        # Selection buttons
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(lambda: self.auto_select_duplicates(select_all=True))
        toolbar_layout.addWidget(self.select_all_button)
        
        self.select_duplicates_button = QPushButton("Select Duplicates")
        self.select_duplicates_button.clicked.connect(self.auto_select_duplicates)
        toolbar_layout.addWidget(self.select_duplicates_button)
        
        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.clicked.connect(self.clear_selection)
        toolbar_layout.addWidget(self.clear_selection_button)
        
        self.unselect_group_button = QPushButton("Unselect Group")
        self.unselect_group_button.clicked.connect(self.unselect_current_group)
        toolbar_layout.addWidget(self.unselect_group_button)
        
        results_layout.addLayout(toolbar_layout)
        
        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setColumnCount(7)
        self.results_tree.setHeaderLabels(["Filename", "Size", "Tags", "Modified", "Path", "Status", "Content Match"])
        self.results_tree.setAlternatingRowColors(True)
        self.results_tree.setSortingEnabled(True)
        self.results_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        
        # Set column widths
        self.results_tree.setColumnWidth(0, 200)  # Filename
        self.results_tree.setColumnWidth(1, 80)   # Size
        self.results_tree.setColumnWidth(2, 150)  # Tags
        self.results_tree.setColumnWidth(3, 150)  # Modified
        # Let Path column take remaining space
        self.results_tree.setColumnWidth(5, 100)  # Status
        self.results_tree.setColumnWidth(6, 120)  # Content Match
        
        # Enable context menu
        self.results_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_tree.customContextMenuRequested.connect(self.show_context_menu)
        
        # Enable multi selection
        self.results_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        results_layout.addWidget(self.results_tree)
        
        # Selection count
        self.selection_layout = QHBoxLayout()
        self.selection_label = QLabel("0 items selected")
        self.selection_layout.addWidget(self.selection_label)
        
        # Copy paths button
        self.copy_paths_button = QPushButton("Copy Selected Paths")
        self.copy_paths_button.clicked.connect(self.copy_selected_paths)
        self.selection_layout.addWidget(self.copy_paths_button)
        
        results_layout.addLayout(self.selection_layout)
        
        # Add results to main layout
        main_layout.addWidget(self.results_group)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label, 1)
        
        self.progress_label = QLabel("")
        status_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)
        
        main_layout.addLayout(status_layout)
        
        # Button bar
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.on_close)
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
        
        # Connect the item change signal to update selection count
        self.results_tree.itemChanged.connect(self.update_selection_count)
        
    def toggle_directory_comparison_mode(self, checked):
        """Toggle visibility of the second directory input"""
        self.directory_comparison_mode = checked
        self.second_dir_layout.setVisible(checked)
        self.compare_dirs_note.setVisible(checked)
        
        # Update the UI based on comparison mode
        if checked:
            # Force content hash mode in comparison mode
            self.criteria_combo.setCurrentIndex(0)
            self.criteria_combo.setEnabled(False)
            
            # If second directory is empty, suggest a path
            if not self.second_dir_edit.text():
                # Try to guess a secondary notes directory
                primary_path = self.path_edit.text()
                if primary_path:
                    dir_name = os.path.basename(primary_path)
                    parent_dir = os.path.dirname(primary_path)
                    
                    # Check for common patterns
                    suggestions = [
                        os.path.join(parent_dir, f"{dir_name}-old"),
                        os.path.join(parent_dir, f"{dir_name}_backup"),
                        os.path.join(parent_dir, f"{dir_name}.bak"),
                        os.path.join(parent_dir, "old_" + dir_name)
                    ]
                    
                    # Use the first suggestion that exists
                    for suggestion in suggestions:
                        if os.path.exists(suggestion):
                            self.second_dir_edit.setText(suggestion)
                            break
        else:
            # Re-enable criteria selection
            self.criteria_combo.setEnabled(True)
            
    def browse_directory(self):
        """Browse for a directory to scan"""
        # Get the current directory
        current_dir = self.path_edit.text()
        if not current_dir or not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~")
            
        # Open directory dialog
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", current_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        if directory:
            self.path_edit.setText(directory)
            
    def browse_second_directory(self):
        """Browse for a second directory to compare"""
        # Get the current directory
        current_dir = self.second_dir_edit.text()
        if not current_dir or not os.path.exists(current_dir):
            # Use the first directory as starting point
            current_dir = self.path_edit.text()
            if not current_dir or not os.path.exists(current_dir):
                current_dir = os.path.expanduser("~")
            
        # Open directory dialog
        directory = QFileDialog.getExistingDirectory(
            self, "Select Second Directory", current_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        if directory:
            self.second_dir_edit.setText(directory)
            
    def update_search_explanation(self, index):
        """Update the search explanation based on selected criteria"""
        # Hide all explanations
        self.content_explanation.hide()
        self.suffix_explanation.hide()
        self.title_explanation.hide()
        self.tag_explanation.hide()
        
        # Show the relevant explanation
        if index == 0:
            self.content_explanation.show()
        elif index == 1:
            self.suffix_explanation.show()
        elif index == 2:
            self.title_explanation.show()
        elif index == 3:
            self.tag_explanation.show()
            
    def toggle_advanced_options(self, checked):
        """Toggle visibility of advanced options"""
        self.advanced_options.setVisible(checked)

    def scan_directory(self, directory):
        """Scan directory for duplicates"""
        self.show()  # Make sure dialog is visible
        self.notes_vault_path = directory
        self.path_edit.setText(directory)
        # Start the scan
        self.start_search()
        
    def find_duplicates(self):
        """Initialize and start the duplicate finder worker"""
        # Get selected directories
        directory = self.path_edit.text()
        second_directory = self.second_dir_edit.text() if self.directory_comparison_mode else None
        
        # Verify paths
        if not directory or not os.path.exists(directory):
            QMessageBox.warning(self, "Invalid Directory", "The specified directory does not exist.")
            return
            
        if self.directory_comparison_mode and (not second_directory or not os.path.exists(second_directory)):
            QMessageBox.warning(self, "Invalid Second Directory", "The specified second directory does not exist.")
            return
            
        # Store paths for comparison mode
        self.comparison_directories = [directory]
        if second_directory:
            self.comparison_directories.append(second_directory)
        
        # Disable buttons
        self.enable_all_buttons(False)
        
        # Get search mode
        scan_mode = ""
        criteria_index = self.criteria_combo.currentIndex()
        
        if criteria_index == 0:
            scan_mode = "content"
        elif criteria_index == 1:
            scan_mode = "suffix"
        elif criteria_index == 2:
            scan_mode = "title"
        elif criteria_index == 3:
            scan_mode = "tags"
            
        # Special handling for directory comparison mode
        if self.directory_comparison_mode:
            # Create a worker for comparing two directories
            self.worker = DirectoryComparisonWorker(directory, second_directory)
        elif scan_mode in ["content", "suffix"]:
            # Use the more efficient workers for content and suffix-based scans
            if scan_mode == "content":
                self.worker = DuplicateFinderWorker(
                    self.comparison_directories, 
                    recursive=self.recursive_checkbox.isChecked()
                )
            else:  # suffix mode
                self.worker = SuffixDuplicateFinderWorker(directory)
        else:
            # Use the standard scanner for title and tag-based searches
            self.worker = NotesDuplicateScanner(directory, scan_mode, self)
            
        # Connect signals
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.process_duplicates)
        if hasattr(self.worker, 'error'):
            self.worker.error.connect(self.on_error)
        
        # Start the worker
        if self.directory_comparison_mode:
            # Directory comparison has a run method
            self.worker_thread = QThread()
            self.worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.worker.run)
            self.worker_thread.start()
        elif hasattr(self.worker, 'run'):
            # NotesDuplicateScanner has a run method
            self.worker.start()
        elif hasattr(self.worker, 'find_duplicates'):
            # DuplicateFinderWorker style
            self.worker_thread = QThread()
            self.worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.worker.find_duplicates)
            self.worker_thread.start()
            
        self.worker_running = True
        
    def verify_files_are_duplicates(self, file1_path, file2_path):
        """Verify if two files are actual duplicates by comparing content"""
        try:
            # Check if files exist
            if not os.path.exists(file1_path) or not os.path.exists(file2_path):
                return False
            
            # Check file sizes (quick check)
            size1 = os.path.getsize(file1_path)
            size2 = os.path.getsize(file2_path)
            
            # Different sizes = definitely different content
            if size1 != size2:
                return False
            
            # For empty files, consider them unique
            if size1 == 0 and size2 == 0:
                return False
            
            # Calculate and compare hashes
            with open(file1_path, 'rb') as f1, open(file2_path, 'rb') as f2:
                # Read the files in chunks to handle large files
                chunk_size = 4096
                identical = True
                
                while True:
                    chunk1 = f1.read(chunk_size)
                    chunk2 = f2.read(chunk_size)
                    
                    if chunk1 != chunk2:
                        identical = False
                        break
                    
                    if not chunk1:  # End of file
                        break
                
                return identical
        
        except Exception as e:
            print(f"Error comparing files {os.path.basename(file1_path)} and {os.path.basename(file2_path)}: {e}")
            return False
            
    def content_similarity(self, file1_path, file2_path):
        """Calculate content similarity between two files"""
        try:
            # Read file contents
            with open(file1_path, 'r', encoding='utf-8', errors='replace') as f1:
                content1 = f1.read()
                
            with open(file2_path, 'r', encoding='utf-8', errors='replace') as f2:
                content2 = f2.read()
                
            # Extract content (excluding YAML frontmatter if present)
            _, body1 = self.extract_yaml_and_body(content1)
            _, body2 = self.extract_yaml_and_body(content2)
            
            # Calculate line-by-line similarity
            lines1 = body1.strip().split('\n')
            lines2 = body2.strip().split('\n')
            
            # Quick check for identical content
            if body1.strip() == body2.strip():
                return 1.0
                
            # Calculate similarity
            matching_lines = sum(1 for l1, l2 in zip(lines1, lines2) if l1 == l2)
            total_lines = max(len(lines1), len(lines2))
            similarity = matching_lines / total_lines if total_lines > 0 else 0
            
            return similarity
            
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0.0

    def closeEvent(self, event):
        """Handle close event to properly clean up threads"""
        self.stop_worker()
        self.wait_for_threads()
        super().closeEvent(event)
    
    def on_close(self):
        """Handle close button click"""
        self.stop_worker()
        self.wait_for_threads()
        self.accept()
    
    def stop_worker(self):
        """Signal worker to stop processing and clean up"""
        if self.worker:
            try:
                # Set stop flag if the worker has the attribute
                if hasattr(self.worker, 'should_stop'):
                    self.worker.should_stop = True
                    print("Signaled worker to stop")
            except Exception as e:
                print(f"Error signaling worker to stop: {e}")
    
    def wait_for_threads(self):
        """
        Wait for any running worker threads to finish before
        starting a new operation.
        """
        try:
            # If a worker thread is running, wait for it to finish
            if self.worker_thread and self.worker_thread.isRunning():
                print("Waiting for worker thread to finish...")
                
                # Attempt to disconnect any signals safely
                try:
                    if self.worker:
                        if hasattr(self.worker, 'progress') and self.worker.progress:
                            try:
                                self.worker.progress.disconnect()
                            except (TypeError, RuntimeError):
                                pass
                        
                        if hasattr(self.worker, 'finished') and self.worker.finished:
                            try:
                                self.worker.finished.disconnect()
                            except (TypeError, RuntimeError):
                                pass
                                
                        if hasattr(self.worker, 'error') and self.worker.error:
                            try:
                                self.worker.error.disconnect()
                            except (TypeError, RuntimeError):
                                pass
                                
                        if hasattr(self.worker, 'started') and self.worker.started:
                            try:
                                self.worker.started.disconnect()
                            except (TypeError, RuntimeError):
                                pass
                except (TypeError, RuntimeError, AttributeError) as e:
                    # Handle case where signals were not connected or worker was deleted
                    print(f"Warning: Could not disconnect signals from worker: {e}")
                
                # Try to quit the thread gracefully with increasing force
                try:
                    # First try requesting quit
                    self.worker_thread.quit()
                    
                    # Give the thread a chance to quit gracefully
                    if not self.worker_thread.wait(1000):  # 1 second timeout
                        print("Thread did not quit in time, requesting termination...")
                        
                        # If still running, try terminating
                        self.worker_thread.terminate()
                        
                        # Give it another chance to terminate
                        if not self.worker_thread.wait(1000):  # 1 second timeout
                            print("Thread still not terminated, forcing exit...")
                            
                            # Last resort
                            try:
                                self.worker_thread.exit(0)
                                self.worker_thread.wait(500)  # Wait a bit more
                            except Exception as e:
                                print(f"Error forcing thread exit: {e}")
                        else:
                            print("Thread terminated successfully.")
                    else:
                        print("Thread quit gracefully.")
                except (RuntimeError, AttributeError) as e:
                    print(f"Error stopping thread: {e}")
                
                # Reset references to worker and thread
                self.worker = None
                self.worker_thread = None
                self.worker_running = False
                
                # Force garbage collection to ensure thread resources are released
                import gc
                gc.collect()
                
        except Exception as e:
            print(f"Error waiting for threads: {e}")
            import traceback
            traceback.print_exc()
            # Reset references to be safe
            self.worker_thread = None
            self.worker = None
            self.worker_running = False

    def enable_all_buttons(self, enabled=True):
        """Enable or disable all buttons in the dialog"""
        self.browse_button.setEnabled(enabled)
        
        # If using old-style UI
        if hasattr(self, 'search_button'):
            self.search_button.setEnabled(enabled)
            self.select_button.setEnabled(enabled)
            self.clear_button.setEnabled(enabled)
            self.delete_button.setEnabled(enabled)
            self.merge_button.setEnabled(enabled)
            self.compare_button.setEnabled(enabled)
            self.unselect_group_button.setEnabled(enabled)
            self.copy_paths_button.setEnabled(enabled)
        
        # Apply buttons from new UI
        if hasattr(self, 'action_combo'):
            self.close_button.setEnabled(enabled)
    
    def populate_results(self, duplicates):
        """Populate the results tree with duplicates"""
        self.results_tree.clear()
        self.duplicates = duplicates
        
        # Set up counts
        total_groups = 0
        total_duplicates = 0
        
        # Populate tree
        for group_id, files in duplicates.items():
            # Skip groups with only one file unless they're special groups
            is_empty_unique = "empty_files_unique" == group_id
            is_frontmatter_unique = "frontmatter_unique" in str(group_id)
            if len(files) <= 1 and not (is_empty_unique or is_frontmatter_unique):
                continue
            
            # Create group item
            group_name = os.path.basename(files[0]['path']).replace('.md', '')
            if '-' in group_name:
                # Try to get a cleaner group name by removing suffixes
                base_name = group_name.split('-')[0].strip()
                if base_name:
                    group_name = base_name
                    
            # Calculate total size for the group
            total_group_size = sum(f.get('size', 0) for f in files)
            
            # Customize group item based on group type
            is_suffix_group = "suffix_" in str(group_id) if isinstance(group_id, str) else False
            is_content_group = "content_" in str(group_id) if isinstance(group_id, str) else False
            is_empty_group = "empty_" in str(group_id) and not is_empty_unique if isinstance(group_id, str) else False
            is_frontmatter_group = "frontmatter_" in str(group_id) and not is_frontmatter_unique if isinstance(group_id, str) else False
            
            # Add warning for suspiciously large groups
            large_group_warning = ""
            if len(files) > 20:
                large_group_warning = " ⚠️ LARGE GROUP"
            
            # Group title
            group_item = QTreeWidgetItem(self.results_tree)
            group_size_text = self.format_size(total_group_size)
            
            if is_suffix_group:
                group_item.setText(0, f"Suffix Group: {group_name} ({len(files)} files){large_group_warning}")
                group_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                group_item.setText(1, group_size_text)  # Show total size for the group
            elif is_empty_unique:
                group_item.setText(0, f"Empty Files ({len(files)} files)")
                group_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                group_item.setText(1, group_size_text)  # Show total size for the group
                group_item.setBackground(0, QBrush(QColor(220, 220, 255)))  # Light blue background for unique
            elif is_empty_group:
                group_item.setText(0, f"Duplicate Empty Files ({len(files)} files){large_group_warning}")
                group_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                group_item.setText(1, group_size_text)  # Show total size for the group
                group_item.setBackground(0, QBrush(QColor(255, 220, 220)))  # Light red background
            elif is_frontmatter_unique:
                group_item.setText(0, f"Unique Frontmatter File ({len(files)} files)")
                group_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                group_item.setText(1, group_size_text)  # Show total size for the group
                group_item.setBackground(0, QBrush(QColor(230, 255, 230)))  # Light green background
            elif is_frontmatter_group:
                # Get tags to show in group name
                tags = []
                for file in files:
                    if 'tags' in file and file['tags']:
                        tags.extend(file['tags'])
                tags = list(set(tags))  # Remove duplicates
                tag_str = ", ".join(tags[:3])
                if len(tags) > 3:
                    tag_str += "..."
                
                group_item.setText(0, f"Frontmatter Group: [{tag_str}] ({len(files)} files){large_group_warning}")
                group_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                group_item.setText(1, group_size_text)  # Show total size for the group
                group_item.setBackground(0, QBrush(QColor(255, 240, 200)))  # Light yellow background
            elif is_content_group:
                group_item.setText(0, f"Content Group: {group_name} ({len(files)} files) - 100% IDENTICAL{large_group_warning}")
                group_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                group_item.setText(1, group_size_text)  # Show total size for the group
                # Highlight content groups more prominently
                group_item.setBackground(0, QBrush(QColor(200, 230, 255)))  # Light blue background
                
                # For large content groups, add a warning tooltip
                if len(files) > 20:
                    group_item.setToolTip(0, "Large group detected - verify these files are truly identical before deleting")
                    group_item.setForeground(0, QBrush(QColor(180, 0, 0)))  # Dark red text for warning
            else:
                group_item.setText(0, f"Duplicate Group: {group_name} ({len(files)} files){large_group_warning}")
                group_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                group_item.setText(1, group_size_text)  # Show total size for the group
            
            # Check if any file is marked as original
            has_original = any(f.get('is_original', False) for f in files)
            
            # Add child items for each file
            for file_info in files:
                item = QTreeWidgetItem(group_item)
                
                # First column: Filename with checkbox
                filename = file_info['filename']
                item.setText(0, filename)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                
                # Second column: Size
                if 'size' in file_info:
                    item.setText(1, self.format_size(file_info['size']))
                
                # Third column: Tags 
                if 'tags' in file_info and file_info['tags']:
                    item.setText(2, ", ".join(file_info['tags']))
                
                # Fourth column: Modified date
                if 'modified' in file_info:
                    modified_time = datetime.fromtimestamp(file_info['modified'])
                    item.setText(3, modified_time.strftime('%Y-%m-%d %H:%M:%S'))
                
                # Fifth column: Path
                if 'path' in file_info:
                    item.setText(4, file_info['path'])
                
                # Sixth column: status
                status_text = ""
                if is_empty_unique:
                    # For unique empty files, don't mark them as duplicates
                    status_text = "Empty File"
                    item.setBackground(0, QBrush(QColor(220, 220, 255)))  # Light blue for unique empty
                elif is_frontmatter_unique:
                    status_text = "Frontmatter-Only File"
                    item.setBackground(0, QBrush(QColor(230, 255, 230)))  # Light green
                elif is_suffix_group:
                    if file_info.get('is_original', False):
                        status_text = "Original"
                        item.setBackground(0, QBrush(QColor(200, 255, 200)))  # Light green for original
                    else:
                        suffix = file_info.get('suffix_pattern', 'unknown suffix')
                        status_text = f"Duplicate (suffix: {suffix})"
                        total_duplicates += 1
                        item.setBackground(0, QBrush(QColor(255, 230, 200)))  # Light orange for duplicates
                elif is_empty_group:
                    if file_info.get('is_original', False):
                        status_text = "Original (Empty File)"
                        item.setBackground(0, QBrush(QColor(200, 255, 200)))  # Light green for original
                    else:
                        status_text = "Duplicate (Empty File)"
                        total_duplicates += 1
                        item.setBackground(0, QBrush(QColor(255, 230, 200)))  # Light orange for duplicates
                elif is_frontmatter_group:
                    if file_info.get('is_original', False):
                        status_text = "Original (Frontmatter Only)"
                        item.setBackground(0, QBrush(QColor(200, 255, 200)))  # Light green for original
                    else:
                        status_text = "Duplicate (Frontmatter Only)"
                        total_duplicates += 1
                        item.setBackground(0, QBrush(QColor(255, 230, 200)))  # Light orange for duplicates
                else:
                    if has_original and file_info.get('is_original', False):
                        status_text = "Original"
                        item.setBackground(0, QBrush(QColor(200, 255, 200)))  # Light green for original
                    else:
                        status_text = "Duplicate"
                        total_duplicates += 1
                        item.setBackground(0, QBrush(QColor(255, 230, 200)))  # Light orange for duplicates
                    
                item.setText(5, status_text)
                
                # Seventh column: Content Match
                # For content groups, all files have matching content
                if is_empty_unique or is_empty_group:
                    item.setText(6, "EMPTY FILE")
                    item.setForeground(6, QBrush(QColor(100, 100, 255)))  # Blue text
                    item.setToolTip(6, "This file is empty (0 bytes)")
                elif is_frontmatter_unique or is_frontmatter_group:
                    item.setText(6, "FRONTMATTER ONLY")
                    item.setForeground(6, QBrush(QColor(255, 140, 0)))  # Orange text
                    item.setToolTip(6, "This file only contains YAML frontmatter, no content")
                elif is_content_group:
                    item.setText(6, "YES - 100% IDENTICAL")
                    item.setForeground(6, QBrush(QColor(0, 128, 0)))  # Green text
                    # Add tooltip to explain match confidence
                    item.setToolTip(6, "Files contain identical content (100% match)")
                    
                    # For large groups, add a "Verify" option in the tooltip
                    if len(files) > 20:
                        item.setToolTip(6, "Files appear to contain identical content, but large groups should be verified manually")
                else:
                    item.setText(6, "Unknown")
                    item.setToolTip(6, "Content similarity has not been verified")
                
                # Store the file info as data
                item.setData(0, Qt.ItemDataRole.UserRole, file_info)
            
            group_item.setExpanded(True)
            total_groups += 1
        
        # Update status
        self.progress_label.setText(f"Found {total_groups} groups with {total_duplicates} duplicate files")
        
        # Resize columns
        for i in range(7):
            self.results_tree.resizeColumnToContents(i)
        
        # Enable the buttons
        self.enable_all_buttons(True)
    
    def auto_select_duplicates(self, select_all=False):
        """Automatically select duplicate items based on selected strategy"""
        strategy = self.select_strategy_combo.currentText()
        custom_pattern = self.custom_pattern_edit.text() if strategy == "Match pattern" else None
        
        # Track how many items were selected
        selected_count = 0
        
        # Loop through all groups in the results tree
        for group_idx in range(self.results_tree.topLevelItemCount()):
            group_item = self.results_tree.topLevelItem(group_idx)
            
            # Collect child items
            items = []
            for child_idx in range(group_item.childCount()):
                child_item = group_item.child(child_idx)
                # Skip already deleted items
                if child_item.text(5) == "Deleted":
                    continue
                items.append(child_item)
            
            if len(items) <= 1:
                continue
            
            # Apply different selection strategies
            selected_items = []
            
            if strategy == "Keep newest":
                # Sort by modification time (newest first)
                try:
                    sorted_items = sorted(items, key=lambda x: os.path.getmtime(x.text(4)), reverse=True)
                    # Keep the newest file (first item), mark others for deletion
                    if sorted_items:
                        selected_items = sorted_items[1:]  # Select all except the first (newest)
                except (ValueError, OSError) as e:
                    logging.error(f"Error sorting by modification time: {e}")
                    # Fallback: don't select any if we can't sort
                    selected_items = []
                    
            elif strategy == "Keep oldest":
                # Sort by modification time (oldest first)
                try:
                    sorted_items = sorted(items, key=lambda x: os.path.getmtime(x.text(4)))
                    # Keep the oldest file (first item), mark others for deletion
                    if sorted_items:
                        selected_items = sorted_items[1:]  # Select all except the first (oldest)
                except (ValueError, OSError) as e:
                    logging.error(f"Error sorting by modification time: {e}")
                    # Fallback: don't select any if we can't sort
                    selected_items = []
                    
            elif strategy == "Keep shortest path":
                # Sort by path length (shortest first)
                sorted_items = sorted(items, key=lambda x: len(x.text(4)))
                # Keep the shortest path (first item), mark others for deletion
                if sorted_items:
                    selected_items = sorted_items[1:]  # Select all except the first (shortest)
                    
            elif strategy == "Keep longest path":
                # Sort by path length (longest first)
                sorted_items = sorted(items, key=lambda x: len(x.text(4)), reverse=True)
                # Keep the longest path (first item), mark others for deletion
                if sorted_items:
                    selected_items = sorted_items[1:]  # Select all except the first (longest)
            
            elif strategy == "Keep non-suffixed":
                # Special strategy to identify and select files with common duplicate suffixes
                common_suffixes = ["-surfacepro6", "-DESKTOP-AKQD6B9", "-laptop", " copy", " (copy)", " (1)"]
                
                # First identify items without these suffixes
                non_suffixed_items = []
                suffixed_items = []
                
                for item in items:
                    filename = os.path.basename(item.text(4))
                    base_name = os.path.splitext(filename)[0]
                    
                    has_suffix = False
                    for suffix in common_suffixes:
                        if suffix in base_name:
                            suffixed_items.append(item)
                            has_suffix = True
                            break
                    
                    if not has_suffix:
                        non_suffixed_items.append(item)
                
                # If we have both types, keep non-suffixed and select suffixed
                if non_suffixed_items and suffixed_items:
                    selected_items = suffixed_items
                # If all have suffixes, keep the oldest and select the rest
                elif not non_suffixed_items and suffixed_items:
                    try:
                        sorted_items = sorted(items, key=lambda x: os.path.getmtime(x.text(4)))
                        selected_items = sorted_items[1:]  # Select all except the oldest
                    except:
                        # Fallback: select all but first
                        selected_items = items[1:]
                # Otherwise, just keep the default (no selection)
                else:
                    selected_items = []
            
            elif strategy == "Match pattern":
                if custom_pattern:
                    try:
                        pattern = re.compile(custom_pattern)
                        # Special case: if pattern is simply "Duplicate", match status column
                        if custom_pattern.lower() == "duplicate":
                            # Select all items marked as duplicates
                            for item in items:
                                if "Duplicate" in item.text(5):  # Status is in column 5
                                    selected_items.append(item)
                        else:
                            # Otherwise use pattern on all columns
                            for item in items:
                                # Check all visible columns
                                for col in range(6):  # Check first 6 columns
                                    if pattern.search(item.text(col)):
                                        selected_items.append(item)
                                        break
                    except re.error:
                        QMessageBox.warning(self, "Invalid Pattern", 
                                          f"The pattern '{custom_pattern}' is not a valid regular expression.")
                else:
                    # If no pattern specified, select all duplicates by default
                    for item in items:
                        if "Original" not in item.text(5):  # Select non-originals
                            selected_items.append(item)
            
            # Check/uncheck items based on selection
            for item in items:
                if item in selected_items:
                    item.setCheckState(0, Qt.CheckState.Checked)
                    selected_count += 1
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
        
        # Update the count of selected items
        self.update_selection_count()
        
        # Show a status message
        if selected_count > 0:
            self.status_label.setText(f"Auto-selected {selected_count} duplicate files")
    
    def clear_selection(self):
        """Clear all selections in the results tree"""
        root = self.results_tree.invisibleRootItem()
        
        for i in range(root.childCount()):
            group = root.child(i)
            
            for j in range(group.childCount()):
                item = group.child(j)
                if hasattr(item, 'checkState'):
                    item.setCheckState(0, Qt.CheckState.Unchecked)
        
        self.progress_label.setText("Selection cleared")
        
    def delete_selected(self):
        """Delete selected duplicate notes"""
        root = self.results_tree.invisibleRootItem()
        
        # Collect items to delete
        items_to_delete = []
        content_match_items = []
        unknown_match_items = []
        
        for i in range(root.childCount()):
            group = root.child(i)
            is_content_group = "content_" in group.text(0)
            
            for j in range(group.childCount()):
                item = group.child(j)
                if item.checkState(0) == Qt.CheckState.Checked:
                    items_to_delete.append(item)
                    if is_content_group or item.text(6) == "YES - 100% IDENTICAL":
                        content_match_items.append(item)
                    else:
                        unknown_match_items.append(item)
        
        # Confirm deletion
        if not items_to_delete:
            QMessageBox.information(self, "No Selection", "No items selected for deletion.")
            return
        
        # Prepare warning message
        total_items = len(items_to_delete)
        content_match_count = len(content_match_items)
        unknown_match_count = len(unknown_match_items)
        
        warning_message = f"Are you sure you want to delete {total_items} selected notes?\n\n"
        
        if content_match_count > 0:
            warning_message += f"• {content_match_count} files are confirmed content matches (identical content)\n"
        
        if unknown_match_count > 0:
            warning_message += f"• {unknown_match_count} files have unverified content similarity\n"
        
        if unknown_match_count > 0:
            warning_message += "\nWarning: Some selected files might have unique content! Review your selection carefully."
        
        confirm = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            warning_message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        # Delete files
        deleted_count = 0
        errors = []
        
        for item in items_to_delete:
            try:
                file_path = item.text(4)  # Path is in column 4
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    
                    # Remove the item from the tree
                    parent = item.parent()
                    parent.removeChild(item)
                    
                    # If group is now empty, remove it
                    if parent.childCount() == 0:
                        idx = self.results_tree.indexOfTopLevelItem(parent)
                        if idx >= 0:
                            self.results_tree.takeTopLevelItem(idx)
            except Exception as e:
                errors.append(f"Error deleting {os.path.basename(file_path)}: {str(e)}")
        
        # Show results
        if errors:
            QMessageBox.warning(
                self, 
                "Deletion Errors", 
                f"Deleted {deleted_count} files with {len(errors)} errors:\n\n" + "\n".join(errors)
            )
        else:
            QMessageBox.information(
                self, 
                "Deletion Complete", 
                f"Successfully deleted {deleted_count} duplicate notes."
            )
        
        # Update the status label
        self.status_label.setText(f"Deleted {deleted_count} duplicate notes")
    
    def merge_selected(self):
        """Merge selected notes with their original versions"""
        root = self.results_tree.invisibleRootItem()
        
        # Collect items to merge, grouped by parent
        merge_groups = {}
        content_match_count = 0
        unknown_match_count = 0
        
        for i in range(root.childCount()):
            group = root.child(i)
            group_key = i
            is_content_group = "content_" in group.text(0) if isinstance(group.text(0), str) else False
            
            merge_groups[group_key] = {
                'original': None,
                'duplicates': [],
                'is_content_group': is_content_group
            }
            
            # First find the original in this group
            for j in range(group.childCount()):
                item = group.child(j)
                if "Original" in item.text(5):
                    merge_groups[group_key]['original'] = item
                    break
            
            # If no original was found, use the first item
            if not merge_groups[group_key]['original'] and group.childCount() > 0:
                merge_groups[group_key]['original'] = group.child(0)
            
            # Now collect selected duplicates
            for j in range(group.childCount()):
                item = group.child(j)
                if item.checkState(0) == Qt.CheckState.Checked:
                    # Don't merge the original into itself
                    if item != merge_groups[group_key]['original']:
                        merge_groups[group_key]['duplicates'].append(item)
                        # Track content match status
                        if is_content_group or item.text(6) == "YES - 100% IDENTICAL":
                            content_match_count += 1
                        else:
                            unknown_match_count += 1
            
            # Remove groups with no selected duplicates
            if not merge_groups[group_key]['duplicates']:
                del merge_groups[group_key]
        
        # Check if anything is selected
        if not merge_groups:
            QMessageBox.information(self, "No Selection", "No duplicate notes selected for merging.")
            return
        
        # Count total items to merge
        total_duplicates = content_match_count + unknown_match_count
        
        # Construct a more informative confirmation message
        merge_message = f"You've selected {total_duplicates} duplicate files to merge:\n\n"
        
        if content_match_count > 0:
            merge_message += f"• {content_match_count} files with identical content (100% match)\n"
            if content_match_count > 0 and unknown_match_count == 0:
                merge_message += "\nNOTE: Since all selected files have identical content, merging will only\n"
                merge_message += "combine tags and metadata. You may prefer to simply delete duplicates instead.\n"
        
        if unknown_match_count > 0:
            merge_message += f"• {unknown_match_count} files with unverified content similarity\n"
            merge_message += "\nWarning: Files with unverified content similarity may contain unique content\n"
            merge_message += "that will be appended to the original file.\n"
        
        merge_message += "\nMerging will transfer tags and content from duplicates to original files,\n"
        merge_message += "then delete the duplicates. Continue?"
        
        # Confirm merge
        confirm = QMessageBox.question(
            self, 
            "Confirm Merge", 
            merge_message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        # Merge files
        merged_count = 0
        errors = []
        
        for group_key, group_data in merge_groups.items():
            original_item = group_data['original']
            if not original_item:
                errors.append(f"No original file found for group {group_key}")
                continue
            
            original_path = original_item.text(4)
            
            # Read original content
            try:
                with open(original_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            except Exception as e:
                errors.append(f"Error reading original file {os.path.basename(original_path)}: {str(e)}")
                continue
            
            # Process duplicates
            for dup_item in group_data['duplicates']:
                dup_path = dup_item.text(4)
                
                try:
                    # Read duplicate content
                    with open(dup_path, 'r', encoding='utf-8') as f:
                        dup_content = f.read()
                    
                    # For content-identical files, only merge tags
                    is_content_match = group_data['is_content_group'] or dup_item.text(6) == "YES - 100% IDENTICAL"
                    
                    # Merge the contents
                    if is_content_match:
                        # Only merge tags, don't append content
                        merged_content = self.merge_note_contents(original_content, dup_content, merge_content=False)
                    else:
                        # Merge tags and append content
                        merged_content = self.merge_note_contents(original_content, dup_content, merge_content=True)
                    
                    # Write back to original
                    with open(original_path, 'w', encoding='utf-8') as f:
                        f.write(merged_content)
                    
                    # Delete the duplicate
                    os.remove(dup_path)
                    
                    # Remove from tree
                    parent = dup_item.parent()
                    parent.removeChild(dup_item)
                    
                    # Update count
                    merged_count += 1
                    
                    # Update original content for next merge in this group
                    original_content = merged_content
                    
                except Exception as e:
                    errors.append(f"Error merging {os.path.basename(dup_path)}: {str(e)}")
        
        # Remove empty groups
        root = self.results_tree.invisibleRootItem()
        for i in range(root.childCount() - 1, -1, -1):
            group = root.child(i)
            if group.childCount() <= 1:  # Only original remaining
                root.removeChild(group)
        
        # Show results
        if errors:
            QMessageBox.warning(
                self, 
                "Merge Errors", 
                f"Merged {merged_count} files with {len(errors)} errors:\n\n" + "\n".join(errors[:10])
            )
        else:
            QMessageBox.information(
                self, 
                "Merge Complete", 
                f"Successfully merged {merged_count} duplicate notes into their originals."
            )
        
        # Update status
        self.status_label.setText(f"Merged {merged_count} duplicate notes")
    
    def merge_note_contents(self, original_content, duplicate_content, merge_content=True):
        """Merge the contents of two notes, combining their YAML front matter and content"""
        # Extract front matter and content from both files
        original_yaml, original_body = self.extract_yaml_and_body(original_content)
        duplicate_yaml, duplicate_body = self.extract_yaml_and_body(duplicate_content)
        
        # If either doesn't have YAML, use the other's YAML
        if not original_yaml:
            original_yaml = duplicate_yaml
        elif not duplicate_yaml:
            duplicate_yaml = original_yaml
        
        # Merge YAML front matter
        merged_yaml = self.merge_yaml_front_matter(original_yaml, duplicate_yaml)
        
        # Merge bodies only if requested and if they're different
        merged_body = original_body
        if merge_content and original_body.strip() != duplicate_body.strip():
            merged_body = original_body.strip() + "\n\n" + "## Content from duplicate\n\n" + duplicate_body.strip()
        
        # Reconstruct the file
        if merged_yaml:
            return f"---\n{merged_yaml}\n---\n\n{merged_body}"
        else:
            return merged_body
    
    def extract_yaml_and_body(self, content):
        """Extract YAML front matter and body from a note"""
        yaml_block = ""
        body = content
        
        # Check for YAML front matter
        if content.startswith('---'):
            end_idx = content.find('---', 3)
            if end_idx != -1:
                yaml_block = content[3:end_idx].strip()
                body = content[end_idx+3:].strip()
        
        return yaml_block, body
    
    def merge_yaml_front_matter(self, yaml1, yaml2):
        """Merge two YAML front matter blocks"""
        # Parse YAML blocks into dictionaries
        data1 = {}
        data2 = {}
        
        try:
            for line in yaml1.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    data1[key] = value
        except Exception:
            pass
        
        try:
            for line in yaml2.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    data2[key] = value
        except Exception:
            pass
        
        # Merge special fields
        merged_data = {**data1}
        
        # Merge tags
        if 'tags' in data1 or 'tags' in data2:
            tags1 = self.parse_tags(data1.get('tags', ''))
            tags2 = self.parse_tags(data2.get('tags', ''))
            
            # Combine tags and remove duplicates
            merged_tags = list(set(tags1 + tags2))
            if merged_tags:
                merged_data['tags'] = '[' + ', '.join(merged_tags) + ']'
        
        # Add any fields from data2 that aren't in data1
        for key, value in data2.items():
            if key not in merged_data:
                merged_data[key] = value
        
        # Convert back to YAML string
        yaml_lines = []
        for key, value in merged_data.items():
            yaml_lines.append(f"{key}: {value}")
        
        return '\n'.join(yaml_lines)
    
    def parse_tags(self, tags_str):
        """Parse tags from a tags string"""
        tags = []
        
        # Check if the tags are in array format: [tag1, tag2]
        if tags_str.startswith('[') and tags_str.endswith(']'):
            tags_str = tags_str[1:-1]
            for tag in tags_str.split(','):
                tag = tag.strip().strip("'\"")
                if tag:
                    tags.append(tag)
        # Or in list format with possible newlines
        elif tags_str:
            for line in tags_str.split('\n'):
                if line.strip().startswith('-'):
                    tag = line.strip()[1:].strip().strip("'\"")
                    if tag:
                        tags.append(tag)
        
        return tags
    
    def format_size(self, size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def update_selection_count(self):
        """Update the selection count label"""
        selected_items = self.results_tree.selectedItems()
        self.selection_count_label.setText(f"{len(selected_items)} items selected")

    def apply_selection(self):
        """Apply the selected action to selected items in the results tree"""
        # Get all checked items
        checked_items = []
        for group_idx in range(self.results_tree.topLevelItemCount()):
            group_item = self.results_tree.topLevelItem(group_idx)
            for child_idx in range(group_item.childCount()):
                child_item = group_item.child(child_idx)
                if child_item.checkState(0) == Qt.CheckState.Checked:
                    checked_items.append((group_item, child_item))
        
        if not checked_items:
            QMessageBox.warning(self, "No Selection", "Please select items to apply action")
            return
        
        # Count selected items
        selected_count = len(checked_items)
        
        # Confirm action
        action = self.action_combo.currentText()
        msg = f"Apply '{action}' to {selected_count} selected items?"
        if action == "Delete":
            msg += "\n\nWARNING: This will permanently delete the selected files!"
        
        confirm = QMessageBox.question(self, "Confirm Action", msg,
                                      QMessageBox.StandardButton.Yes | 
                                      QMessageBox.StandardButton.No)
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        # Apply action to each selected item
        processed = 0
        errors = 0
        
        self.status_label.setText("Applying action...")
        QApplication.processEvents()
        
        for group_item, child_item in checked_items:
            try:
                file_path = child_item.text(4)  # Path is in column 4
                
                if action == "Delete":
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        child_item.setText(5, "Deleted")  # Update status in column 5
                        processed += 1
                    else:
                        child_item.setText(5, "Error: File not found")
                        errors += 1
                
                elif action == "Open":
                    # Use the system's default application to open the file
                    if os.path.exists(file_path):
                        # Use platformdetection to open file with default application
                        if platform.system() == 'Windows':
                            os.startfile(file_path)
                        elif platform.system() == 'Darwin':  # macOS
                            subprocess.run(['open', file_path])
                        else:  # Linux
                            subprocess.run(['xdg-open', file_path])
                        child_item.setText(5, "Opened")
                        processed += 1
                    else:
                        child_item.setText(5, "Error: File not found")
                        errors += 1
                
                elif action == "Copy Path":
                    clipboard = QApplication.clipboard()
                    clipboard.setText(file_path)
                    child_item.setText(5, "Path copied")
                    processed += 1
                
                # More actions can be added here
                
            except Exception as e:
                child_item.setText(5, f"Error: {str(e)}")
                errors += 1
        
        # Update status
        if errors > 0:
            self.status_label.setText(f"Applied action to {processed} items with {errors} errors")
        else:
            self.status_label.setText(f"Successfully applied action to {processed} items")
        
        # Refresh the tree after actions
        self.results_tree.viewport().update()

    def browse_directory(self):
        """Browse for a directory to scan"""
        # Get the current directory
        current_dir = self.path_edit.text()
        if not current_dir or not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~")
            
        # Open directory dialog
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", current_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        if directory:
            self.path_edit.setText(directory)

    def unselect_current_group(self):
        """Unselect all items in the current group"""
        current_items = self.results_tree.selectedItems()
        if not current_items:
            QMessageBox.information(self, "No Selection", "Please select a group or item first")
            return
        
        # Find the group containing the selected item(s)
        group_items = []
        for item in current_items:
            # If item is a top-level item (group), add it directly
            if item.parent() is None:
                if item not in group_items:
                    group_items.append(item)
            # Otherwise, add its parent (the group)
            else:
                parent = item.parent()
                if parent not in group_items:
                    group_items.append(parent)
        
        # Unselect all items in the identified groups
        for group in group_items:
            for i in range(group.childCount()):
                child = group.child(i)
                if hasattr(child, 'checkState'):
                    child.setCheckState(0, Qt.CheckState.Unchecked)
        
        # Update the selection count
        self.update_selection_count()
        
        if len(group_items) == 1:
            group_name = group_items[0].text(0)
            self.progress_label.setText(f"Unselected all items in group: {group_name}")
        else:
            self.progress_label.setText(f"Unselected items in {len(group_items)} groups")

    def compare_selected(self):
        """Compare selected notes with their original versions"""
        root = self.results_tree.invisibleRootItem()
        
        # First step: Verify duplicates with content hashes
        self.verify_duplicates_content(root)
        
        # Now collect all selected items with their originals
        originals = {}  # Maps original paths to original items
        duplicates = {}  # Maps original paths to list of duplicate items
        identical_duplicates = {}  # Maps original paths to list of identical duplicates
        different_duplicates = {}  # Maps original paths to list of different duplicates
        empty_files = []  # List of empty files
        
        # Collect all items and organize them
        for i in range(root.childCount()):
            group = root.child(i)
            
            # Skip groups without a group heading (shouldn't happen, but just in case)
            if not group or not hasattr(group, 'text'):
                continue
            
            group_text = group.text(0)
            is_content_group = "content_" in group_text.lower() if isinstance(group_text, str) else False
            is_suffix_group = "suffix" in group_text.lower() if isinstance(group_text, str) else False
            
            # Always verify content for accurate comparison
            strict_verification = True
            suffix_verification = is_suffix_group
            
            original_item = None
            selected_duplicates = []
            
            # First find the original in this group
            for j in range(group.childCount()):
                item = group.child(j)
                if item.text(5) and "Original" in item.text(5):
                    original_item = item
                    break
            
            # If no original was found, use the first item
            if not original_item and group.childCount() > 0:
                original_item = group.child(0)
            
            if not original_item:
                continue
                
            original_path = original_item.text(4)
            
            # Check if original is an empty file - get the size from the tree
            original_size = 0
            try:
                size_text = original_item.text(1)  # Size is in column 1
                if size_text:
                    # Remove any "B", "KB", etc. and convert to integer
                    size_text = size_text.split()[0].strip()
                    original_size = float(size_text)
                    if "KB" in original_item.text(1):
                        original_size *= 1024
                    elif "MB" in original_item.text(1):
                        original_size *= 1024 * 1024
            except:
                # If we can't parse size, get it from the file
                try:
                    original_size = os.path.getsize(original_path)
                except:
                    original_size = 0
            
            # Skip empty file groups entirely
            if original_size == 0 and "empty" in group.text(0).lower():
                # Instead, collect them in a separate list
                for j in range(group.childCount()):
                    item = group.child(j)
                    if item.checkState(0) == Qt.CheckState.Checked:
                        empty_files.append(item)
                continue
                
            originals[original_path] = original_item
            
            # Now collect selected duplicates
            for j in range(group.childCount()):
                item = group.child(j)
                if item.checkState(0) == Qt.CheckState.Checked:
                    # Don't include the original itself if it was checked
                    if item != original_item:
                        # Get file paths
                        file_path = item.text(4)
                        
                        # Skip empty files for duplication analysis
                        file_size = 0
                        try:
                            size_text = item.text(1)  # Size is in column 1
                            if size_text:
                                size_text = size_text.split()[0].strip()
                                file_size = float(size_text)
                                if "KB" in item.text(1):
                                    file_size *= 1024
                                elif "MB" in item.text(1):
                                    file_size *= 1024 * 1024
                        except:
                            try:
                                file_size = os.path.getsize(file_path)
                            except:
                                file_size = 0
                        
                        if file_size == 0:
                            empty_files.append(item)
                            continue
                        
                        # Verify file exists
                        if not os.path.exists(file_path):
                            continue
                        
                        # Always verify if files are actual duplicates by content
                        is_identical = self.verify_files_are_duplicates(original_path, file_path)
                        
                        # Update status in the UI
                        if is_identical:
                            item.setText(6, "YES - 100% IDENTICAL")
                            # Add to identical duplicates
                            if original_path not in identical_duplicates:
                                identical_duplicates[original_path] = []
                            identical_duplicates[original_path].append(item)
                            # Also add to selected duplicates
                            selected_duplicates.append(item)
                        else:
                            item.setText(6, "NO - DIFFERENT CONTENT")
                            # Add to different duplicates for review
                            if original_path not in different_duplicates:
                                different_duplicates[original_path] = []
                            different_duplicates[original_path].append(item)
            
            if selected_duplicates:
                duplicates[original_path] = selected_duplicates
        
        # Handle empty files specially
        if empty_files:
            self.handle_empty_files(empty_files)
        
        # Check if anything is selected
        if not duplicates and not different_duplicates:
            if not empty_files:  # Only show this if we didn't handle empty files
                QMessageBox.information(self, "No Selection", "No duplicate notes selected for comparison.")
            return
        
        # If no duplicates were found after verification, show message and return
        identical_count = sum(len(items) for items in identical_duplicates.values())
        different_count = sum(len(items) for items in different_duplicates.values())
        
        if identical_count == 0 and different_count == 0:
            QMessageBox.information(
                self,
                "No Valid Duplicates",
                "No valid duplicates were found among your selection. The files may have different content or may not be actual duplicates."
            )
            return
            
        # If we have identical duplicates, offer to auto-delete them
        auto_deleted = 0
        if identical_count > 0:
            # Create a preview of files to be deleted
            preview_text = self.create_duplicate_preview(identical_duplicates)
            
            message = (f"Found {identical_count} duplicates with identical content to their originals.\n\n"
                      f"Would you like to automatically delete these identical duplicates?\n\n"
                      f"Preview of files to be deleted (first 10 shown):\n{preview_text}")
            
            response = QMessageBox.question(
                self,
                "Identical Duplicates Found",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if response == QMessageBox.StandardButton.Yes:
                # Auto-delete identical duplicates
                deleted, errors = self.delete_identical_duplicates(identical_duplicates)
                auto_deleted = deleted
                
                if errors:
                    QMessageBox.warning(
                        self,
                        "Deletion Errors",
                        f"Deleted {deleted} out of {identical_count} identical duplicates with {len(errors)} errors:\n\n" + 
                        "\n".join(errors[:10])
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Deletion Complete",
                        f"Successfully deleted {deleted} identical duplicates."
                    )
        
        # If we have different duplicates, proceed with manual review
        if different_count > 0:
            # Create a preview of files to be compared
            preview_text = self.create_duplicate_preview(different_duplicates)
            
            message = (f"Found {different_count} duplicates with differences from their originals.\n\n"
                      f"Would you like to review these files individually?\n\n"
                      f"Preview of files to be compared (first 10 shown):\n{preview_text}")
            
            response = QMessageBox.question(
                self,
                "Different Duplicates Found",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if response == QMessageBox.StandardButton.Yes:
                # Compare files with differences individually
                compared_count = 0
                errors = []
                action_taken = None
                
                # Flatten the different duplicates for easier iteration
                to_compare = []
                for orig_path, dup_items in different_duplicates.items():
                    orig_item = originals[orig_path]
                    for dup_item in dup_items:
                        to_compare.append((orig_item, dup_item))
                
                # Compare each pair
                for orig_item, dup_item in to_compare:
                    orig_path = orig_item.text(4)
                    dup_path = dup_item.text(4)
                    
                    try:
                        # Compare files
                        diff = self.compare_files(orig_path, dup_path)
                        
                        # Add items to the diff for actions
                        diff['original_item'] = orig_item
                        diff['duplicate_item'] = dup_item
                        diff['original_path'] = orig_path
                        diff['duplicate_path'] = dup_path
                        diff['is_content_group'] = False  # These are different files
                        
                        # Show differences (this now includes action buttons)
                        action_taken = self.show_differences(diff)
                        
                        # Only count as compared if the dialog was shown
                        if action_taken != "cancel_all":
                            compared_count += 1
                        else:
                            # User wants to stop comparing
                            break
                        
                    except Exception as e:
                        errors.append(f"Error comparing {os.path.basename(dup_path)}: {str(e)}")
                
                # Show results
                if errors:
                    QMessageBox.warning(
                        self, 
                        "Comparison Errors", 
                        f"Compared {compared_count} files with {len(errors)} errors:\n\n" + "\n".join(errors[:10])
                    )
                elif compared_count > 0:
                    QMessageBox.information(
                        self, 
                        "Comparison Complete", 
                        f"Successfully compared {compared_count} duplicate notes to their originals."
                    )
                
                # Update status
                if auto_deleted > 0:
                    self.status_label.setText(f"Auto-deleted {auto_deleted} identical duplicates, compared {compared_count} different duplicates")
                else:
                    self.status_label.setText(f"Compared {compared_count} duplicate notes")
        elif auto_deleted > 0:
            # We deleted identical duplicates and had no different ones
            self.status_label.setText(f"Auto-deleted {auto_deleted} identical duplicates")
            QMessageBox.information(
                self,
                "Processing Complete",
                f"Successfully deleted {auto_deleted} identical duplicates. No files with differences were found."
            )
        else:
            # No action was taken
            QMessageBox.information(
                self,
                "No Action Taken",
                "No files were processed. Please select some duplicates and try again."
            )
    
    def verify_duplicates_content(self, root):
        """Verify content similarity for all files in the tree"""
        try:
            # First collect originals and duplicates by group
            for i in range(root.childCount()):
                group = root.child(i)
                group_text = group.text(0)
                
                # Skip content groups since they're already verified
                if "content_" in group_text.lower():
                    continue
                
                # Focus on suffix groups which need verification
                if "suffix" not in group_text.lower():
                    continue
                
                # Find the original
                original_item = None
                for j in range(group.childCount()):
                    item = group.child(j)
                    if item.text(5) and "Original" in item.text(5):
                        original_item = item
                        break
                
                # If no original, use first item
                if not original_item and group.childCount() > 0:
                    original_item = group.child(0)
                
                if not original_item:
                    continue
                
                # Get original content hash
                original_path = original_item.text(4)
                
                # Now verify each potential duplicate
                for j in range(group.childCount()):
                    item = group.child(j)
                    if item != original_item:
                        dup_path = item.text(4)
                        
                        # Check actual content similarity
                        is_identical = self.verify_files_are_duplicates(original_path, dup_path)
                        
                        # Update the item's status in column 6
                        if is_identical:
                            item.setText(6, "YES - 100% IDENTICAL")
                        else:
                            item.setText(6, "NO - DIFFERENT CONTENT")
        
        except Exception as e:
            print(f"Error verifying duplicates: {e}")
            import traceback
            traceback.print_exc()
    
    def verify_files_are_duplicates(self, file1_path, file2_path):
        """Verify if two files are actual duplicates by comparing content"""
        try:
            # Check if files exist
            if not os.path.exists(file1_path) or not os.path.exists(file2_path):
                return False
            
            # Check file sizes (quick check)
            size1 = os.path.getsize(file1_path)
            size2 = os.path.getsize(file2_path)
            
            # Different sizes = definitely different content
            if size1 != size2:
                return False
            
            # For empty files, consider them unique
            if size1 == 0 and size2 == 0:
                return False
            
            # Calculate and compare hashes
            with open(file1_path, 'rb') as f1, open(file2_path, 'rb') as f2:
                # Read the files in chunks to handle large files
                chunk_size = 4096
                identical = True
                
                while True:
                    chunk1 = f1.read(chunk_size)
                    chunk2 = f2.read(chunk_size)
                    
                    if chunk1 != chunk2:
                        identical = False
                        break
                    
                    if not chunk1:  # End of file
                        break
                
                return identical
        
        except Exception as e:
            print(f"Error comparing files {os.path.basename(file1_path)} and {os.path.basename(file2_path)}: {e}")
            return False
    
    def create_duplicate_preview(self, duplicate_map):
        """Create a preview of files in the duplicate map"""
        preview_lines = []
        count = 0
        
        for original_path, items in duplicate_map.items():
            original_name = os.path.basename(original_path)
            
            for item in items:
                if count >= 10:  # Limit to 10 entries
                    preview_lines.append("... and more ...")
                    break
                    
                duplicate_path = item.text(4)
                duplicate_name = os.path.basename(duplicate_path)
                size_text = item.text(1)
                
                preview_lines.append(f"• {duplicate_name} ({size_text}) → original: {original_name}")
                count += 1
            
            if count >= 10:
                break
        
        return "\n".join(preview_lines)
    
    def handle_empty_files(self, empty_files):
        """Handle empty files with special care"""
        if not empty_files:
            return
            
        count = len(empty_files)
        
        # Create a preview of the empty files
        preview_lines = []
        for i, item in enumerate(empty_files[:10]):  # Show first 10
            file_path = item.text(4)
            file_name = os.path.basename(file_path)
            preview_lines.append(f"• {file_name}")
        
        if len(empty_files) > 10:
            preview_lines.append("... and more ...")
            
        preview_text = "\n".join(preview_lines)
        
        # Ask what to do with empty files
        message = (f"Found {count} empty files (0 bytes).\n\n"
                  f"Empty files should be handled separately as they may have unique filenames but no content.\n\n"
                  f"Files:\n{preview_text}\n\n"
                  f"What would you like to do with these empty files?")
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Empty Files Found")
        layout = QVBoxLayout(dialog)
        
        # Information
        info_label = QLabel(message)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Options
        option_group = QGroupBox("Choose an action for empty files:")
        option_layout = QVBoxLayout(option_group)
        
        delete_button = QPushButton("Delete All Empty Files")
        delete_button.setStyleSheet("background-color: #ffcccc;")
        delete_button.clicked.connect(lambda: self.set_empty_file_action(dialog, "delete"))
        option_layout.addWidget(delete_button)
        
        skip_button = QPushButton("Skip (Keep All Empty Files)")
        skip_button.setStyleSheet("background-color: #ccffcc;")
        skip_button.clicked.connect(lambda: self.set_empty_file_action(dialog, "skip"))
        option_layout.addWidget(skip_button)
        
        view_button = QPushButton("View Each File Individually")
        view_button.clicked.connect(lambda: self.set_empty_file_action(dialog, "view"))
        option_layout.addWidget(view_button)
        
        layout.addWidget(option_group)
        
        # Store result
        dialog.action_result = "skip"  # Default
        
        # Show dialog
        dialog.exec()
        
        # Process the choice
        action = dialog.action_result
        
        if action == "delete":
            # Confirm deletion
            confirm = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete all {count} empty files?\n\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if confirm == QMessageBox.StandardButton.Yes:
                deleted, errors = self.delete_empty_files(empty_files)
                
                if errors:
                    QMessageBox.warning(
                        self,
                        "Deletion Errors",
                        f"Deleted {deleted} out of {count} empty files with {len(errors)} errors:\n\n" + 
                        "\n".join(errors[:10])
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Deletion Complete",
                        f"Successfully deleted {deleted} empty files."
                    )
                
                self.status_label.setText(f"Deleted {deleted} empty files")
        
        elif action == "view":
            # For now, just show a message - we can implement individual review later if needed
            QMessageBox.information(
                self,
                "View Empty Files",
                "Individual review of empty files is not yet implemented. Please use the select/unselect checkboxes in the tree view to mark files for deletion."
            )
    
    def set_empty_file_action(self, dialog, action):
        """Set the action for empty files and close dialog"""
        dialog.action_result = action
        dialog.accept()
    
    def delete_empty_files(self, empty_files):
        """Delete all empty files"""
        deleted_count = 0
        errors = []
        
        for item in empty_files:
            try:
                file_path = item.text(4)  # Path is in column 4
                if os.path.exists(file_path):
                    # Double check that it's actually empty
                    if os.path.getsize(file_path) == 0:
                        os.remove(file_path)
                        deleted_count += 1
                        
                        # Remove the item from the tree
                        parent = item.parent()
                        if parent:
                            parent.removeChild(item)
                            
                            # If group is now empty, remove it
                            if parent.childCount() <= 1:  # Only original left
                                idx = self.results_tree.indexOfTopLevelItem(parent)
                                if idx >= 0:
                                    self.results_tree.takeTopLevelItem(idx)
                    else:
                        errors.append(f"File is not empty: {os.path.basename(file_path)}")
            except Exception as e:
                errors.append(f"Error deleting {os.path.basename(file_path)}: {str(e)}")
        
        return deleted_count, errors
    
    def delete_identical_duplicates(self, identical_duplicates):
        """Delete all identical duplicates automatically"""
        deleted_count = 0
        errors = []
        
        # Process each group of identical duplicates
        for original_path, items in identical_duplicates.items():
            # Verify that original exists and has content
            if not os.path.exists(original_path):
                errors.append(f"Original file not found: {os.path.basename(original_path)}")
                continue
                
            original_size = os.path.getsize(original_path)
            if original_size == 0:
                errors.append(f"Original file is empty: {os.path.basename(original_path)}")
                continue
            
            for item in items:
                try:
                    file_path = item.text(4)  # Path is in column 4
                    if not os.path.exists(file_path):
                        errors.append(f"File not found: {os.path.basename(file_path)}")
                        continue
                        
                    # Double check file sizes match (non-zero)
                    duplicate_size = os.path.getsize(file_path)
                    if duplicate_size == 0:
                        errors.append(f"Skipping empty file: {os.path.basename(file_path)}")
                        continue
                        
                    if duplicate_size != original_size:
                        errors.append(f"File size mismatch: {os.path.basename(file_path)}")
                        continue
                    
                    # Proceed with deletion
                    os.remove(file_path)
                    deleted_count += 1
                    
                    # Remove the item from the tree
                    parent = item.parent()
                    if parent:
                        parent.removeChild(item)
                        
                        # If group is now empty, remove it
                        if parent.childCount() <= 1:  # Only original left
                            idx = self.results_tree.indexOfTopLevelItem(parent)
                            if idx >= 0:
                                self.results_tree.takeTopLevelItem(idx)
                except Exception as e:
                    errors.append(f"Error deleting {os.path.basename(file_path)}: {str(e)}")
        
        return deleted_count, errors

    def show_differences(self, diff):
        """Show the differences between two files and provide action buttons"""
        # Create a dialog to show differences
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Compare: {diff.get('file1', 'File 1')} vs {diff.get('file2', 'File 2')}")
        dialog.resize(1000, 700)  # Larger dialog for better diff viewing
        
        # Main layout
        layout = QVBoxLayout(dialog)
        
        # Error handling
        if 'error' in diff:
            error_label = QLabel(f"Error comparing files: {diff['error']}")
            error_label.setStyleSheet("color: red;")
            layout.addWidget(error_label)
            layout.addWidget(QPushButton("Close", clicked=dialog.accept))
            dialog.exec()
            return "error"
        
        # Create tabs for different comparison views
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab 1: Summary
        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        
        # Files being compared
        files_label = QLabel(f"<b>Comparing:</b> {diff['file1']} (original) ↔ {diff['file2']} (duplicate)")
        summary_layout.addWidget(files_label)
        
        # Content similarity
        similarity = round(diff['body_similarity'] * 100, 1)
        similarity_label = QLabel(f"<b>Content Similarity:</b> {similarity}%")
        similarity_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {'green' if similarity > 90 else 'orange' if similarity > 60 else 'red'};")
        summary_layout.addWidget(similarity_label)
        
        # YAML differences summary
        if diff['yaml_diff']:
            yaml_label = QLabel(f"<b>YAML Front Matter Differences:</b> {len(diff['yaml_diff'])} fields")
            summary_layout.addWidget(yaml_label)
            
            yaml_box = QGroupBox("YAML Differences")
            yaml_layout = QVBoxLayout(yaml_box)
            
            for key, (val1, val2) in diff['yaml_diff'].items():
                if key == 'tags':
                    continue  # We'll show tags separately
                
                diff_label = QLabel(f"<b>{key}:</b> {'(not in original)' if val1 is None else val1} ↔ {'(not in duplicate)' if val2 is None else val2}")
                yaml_layout.addWidget(diff_label)
            
            summary_layout.addWidget(yaml_box)
        
        # Tags differences
        if diff['tags_only_in_1'] or diff['tags_only_in_2']:
            tags_label = QLabel("<b>Tag Differences:</b>")
            summary_layout.addWidget(tags_label)
            
            tags_box = QGroupBox("Tags Comparison")
            tags_layout = QVBoxLayout(tags_box)
            
            if diff['tags_only_in_1']:
                tags1_label = QLabel(f"<b>Only in original:</b> {', '.join(diff['tags_only_in_1'])}")
                tags_layout.addWidget(tags1_label)
            
            if diff['tags_only_in_2']:
                tags2_label = QLabel(f"<b>Only in duplicate:</b> {', '.join(diff['tags_only_in_2'])}")
                tags_layout.addWidget(tags2_label)
            
            summary_layout.addWidget(tags_box)
        
        # Add recommendation
        if similarity > 95:
            recommendation = QLabel("<b>Recommendation:</b> These files are nearly identical. Consider using the 'Delete' action to remove the duplicate.")
            recommendation.setStyleSheet("color: green; font-weight: bold;")
        elif similarity > 80:
            recommendation = QLabel("<b>Recommendation:</b> These files are very similar. Consider using the 'Merge' action to combine their content.")
            recommendation.setStyleSheet("color: blue; font-weight: bold;")
        else:
            recommendation = QLabel("<b>Recommendation:</b> These files have significant differences. Review content carefully before merging or deleting.")
            recommendation.setStyleSheet("color: red; font-weight: bold;")
        
        summary_layout.addWidget(recommendation)
        
        # Add summary to tabs
        tabs.addTab(summary_widget, "Summary")
        
        # Tab 2: Advanced Diff View
        if diff['content_diff']:
            # Create the advanced diff view with side-by-side comparison
            diff_widget = QWidget()
            diff_layout = QVBoxLayout(diff_widget)
            
            # Create a splitter for side-by-side view
            splitter = QSplitter(Qt.Orientation.Horizontal)
            
            # Original content (left side)
            left_widget = QWidget()
            left_layout = QVBoxLayout(left_widget)
            left_layout.setContentsMargins(0, 0, 0, 0)
            
            left_label = QLabel("<b>Original:</b>")
            left_layout.addWidget(left_label)
            
            left_editor = QPlainTextEdit()
            left_editor.setReadOnly(True)
            left_layout.addWidget(left_editor)
            
            # Modified content (right side)
            right_widget = QWidget()
            right_layout = QVBoxLayout(right_widget)
            right_layout.setContentsMargins(0, 0, 0, 0)
            
            right_label = QLabel("<b>Duplicate:</b>")
            right_layout.addWidget(right_label)
            
            right_editor = QPlainTextEdit()
            right_editor.setReadOnly(True)
            right_layout.addWidget(right_editor)
            
            # Add to splitter
            splitter.addWidget(left_widget)
            splitter.addWidget(right_widget)
            splitter.setSizes([500, 500])  # Equal sizes
            
            diff_layout.addWidget(splitter)
            
            # Extract original and duplicate text
            with open(diff['original_path'], 'r', encoding='utf-8') as f:
                orig_text = f.read()
                
            with open(diff['duplicate_path'], 'r', encoding='utf-8') as f:
                dup_text = f.read()
                
            # Set text in editors
            left_editor.setPlainText(orig_text)
            right_editor.setPlainText(dup_text)
            
            # Highlight the differences (simplified version)
            self.highlight_differences(left_editor, right_editor, diff['content_diff'])
            
            # Add to tabs
            tabs.addTab(diff_widget, "Side-by-Side View")
            
            # Tab 3: Traditional Diff View
            trad_diff_widget = QWidget()
            trad_diff_layout = QVBoxLayout(trad_diff_widget)
            
            diff_text = QPlainTextEdit()
            diff_text.setReadOnly(True)
            diff_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)  # Better for diffs
            trad_diff_layout.addWidget(diff_text)
            
            # Format and display traditional diff
            diff_content = f"Comparing {diff['file1']} (left) with {diff['file2']} (right)\n"
            diff_content += "=" * 80 + "\n\n"
            
            for line_num, line1, line2 in diff['content_diff']:
                if line1 is None:
                    diff_content += f"+ Line {line_num+1}: {line2}\n"
                elif line2 is None:
                    diff_content += f"- Line {line_num+1}: {line1}\n"
                else:
                    diff_content += f"! Line {line_num+1}:\n  - {line1}\n  + {line2}\n"
            
            diff_text.setPlainText(diff_content)
            
            # Add to tabs
            tabs.addTab(trad_diff_widget, "Traditional Diff")
        
        # Tab 4: Merge Preview
        merge_widget = QWidget()
        merge_layout = QVBoxLayout(merge_widget)
        
        merge_label = QLabel("<b>Merge Preview:</b> This shows what the file will look like after merging")
        merge_layout.addWidget(merge_label)
        
        # Preview of merged content
        is_content_match = diff['is_content_group'] or diff['body_similarity'] > 0.95
        
        with open(diff['original_path'], 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        with open(diff['duplicate_path'], 'r', encoding='utf-8') as f:
            duplicate_content = f.read()
        
        # Create merged content
        merged_content = self.merge_note_contents(original_content, duplicate_content, not is_content_match)
        
        # Show the merged result
        merge_editor = QPlainTextEdit()
        merge_editor.setReadOnly(True)
        merge_editor.setPlainText(merged_content)
        merge_layout.addWidget(merge_editor)
        
        # Explain what will be merged
        if is_content_match:
            merge_explain = QLabel("Only metadata and tags will be merged because content is nearly identical")
            merge_explain.setStyleSheet("color: green;")
        else:
            merge_explain = QLabel("Both content and metadata will be merged")
            merge_explain.setStyleSheet("color: blue;")
        merge_layout.addWidget(merge_explain)
        
        # Add merge options - for future enhancement
        merge_options = QGroupBox("Merge Options")
        merge_options_layout = QVBoxLayout(merge_options)
        
        tags_only_check = QCheckBox("Only merge tags and metadata (preserve original content)")
        tags_only_check.setChecked(is_content_match)
        merge_options_layout.addWidget(tags_only_check)
        
        append_check = QCheckBox("Append content instead of merging line-by-line")
        append_check.setChecked(True)
        merge_options_layout.addWidget(append_check)
        
        # Store in dialog object for access from action functions
        dialog.merge_tags_only = tags_only_check
        dialog.merge_append = append_check
        
        merge_layout.addWidget(merge_options)
        
        # Add to tabs
        tabs.addTab(merge_widget, "Merge Preview")
        
        # Add action buttons
        buttons_layout = QHBoxLayout()
        
        # Skip button (just close this dialog)
        skip_button = QPushButton("Skip")
        skip_button.clicked.connect(dialog.accept)
        buttons_layout.addWidget(skip_button)
        
        # Delete button
        delete_button = QPushButton("Delete Duplicate")
        delete_button.clicked.connect(lambda: self.delete_from_dialog(dialog, diff))
        buttons_layout.addWidget(delete_button)
        
        # Merge button
        merge_button = QPushButton("Merge to Original")
        merge_button.clicked.connect(lambda: self.merge_from_dialog(dialog, diff))
        buttons_layout.addWidget(merge_button)
        
        # Cancel all button
        cancel_all_button = QPushButton("Cancel All")
        cancel_all_button.clicked.connect(lambda: self.cancel_all_comparisons(dialog))
        buttons_layout.addWidget(cancel_all_button)
        
        layout.addLayout(buttons_layout)
        
        # Store the result
        self.comparison_result = None
        
        # Show the dialog and wait for a response
        dialog.exec()
        
        # Return the result
        return self.comparison_result or "skip"
        
    def highlight_differences(self, left_editor, right_editor, content_diff):
        """Highlight differences between the two text editors"""
        try:
            from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor
            
            # Create formats for highlighting
            removed_format = QTextCharFormat()
            removed_format.setBackground(QColor(255, 200, 200))  # Light red
            
            added_format = QTextCharFormat()
            added_format.setBackground(QColor(200, 255, 200))  # Light green
            
            # Apply highlights to editors
            for line_num, line1, line2 in content_diff:
                if line1 is not None:
                    # Highlight in left editor
                    cursor = left_editor.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.Start)
                    cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line_num)
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
                    cursor.setCharFormat(removed_format)
                
                if line2 is not None:
                    # Highlight in right editor
                    cursor = right_editor.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.Start)
                    cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line_num)
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
                    cursor.setCharFormat(added_format)
        except Exception as e:
            print(f"Error highlighting differences: {e}")
            
    def delete_from_dialog(self, dialog, diff):
        """Delete the duplicate file from the comparison dialog"""
        try:
            duplicate_path = diff['duplicate_path']
            
            # Confirm deletion
            confirm = QMessageBox.question(
                dialog, 
                "Confirm Deletion", 
                f"Delete duplicate file: {os.path.basename(duplicate_path)}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if confirm != QMessageBox.StandardButton.Yes:
                return
            
            # Delete the file
            if os.path.exists(duplicate_path):
                os.remove(duplicate_path)
                
                # Also remove from tree
                dup_item = diff['duplicate_item']
                parent = dup_item.parent()
                if parent:
                    parent.removeChild(dup_item)
                    
                    # Remove group if empty
                    if parent.childCount() <= 1:
                        idx = self.results_tree.indexOfTopLevelItem(parent)
                        if idx >= 0:
                            self.results_tree.takeTopLevelItem(idx)
                
                # Update status
                self.status_label.setText(f"Deleted: {os.path.basename(duplicate_path)}")
                
                # Store result and close dialog
                self.comparison_result = "delete"
                dialog.accept()
            else:
                QMessageBox.warning(dialog, "Error", f"File not found: {duplicate_path}")
        except Exception as e:
            QMessageBox.critical(dialog, "Error", f"Error deleting file: {str(e)}")
    
    def merge_from_dialog(self, dialog, diff):
        """Merge the duplicate file from the comparison dialog"""
        try:
            original_path = diff['original_path']
            duplicate_path = diff['duplicate_path']
            
            # Get merge options if available
            merge_tags_only = getattr(dialog, 'merge_tags_only', None)
            tags_only = merge_tags_only.isChecked() if merge_tags_only else diff['is_content_group']
            
            # Confirm merge
            merge_type = "tags only" if tags_only else "tags and content" 
            confirm = QMessageBox.question(
                dialog, 
                "Confirm Merge", 
                f"Merge {merge_type} from {os.path.basename(duplicate_path)} to {os.path.basename(original_path)}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if confirm != QMessageBox.StandardButton.Yes:
                return
            
            # Read file contents
            with open(original_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            with open(duplicate_path, 'r', encoding='utf-8') as f:
                duplicate_content = f.read()
            
            # Merge contents
            merged_content = self.merge_note_contents(original_content, duplicate_content, not tags_only)
            
            # Write back to original
            with open(original_path, 'w', encoding='utf-8') as f:
                f.write(merged_content)
            
            # Delete the duplicate
            os.remove(duplicate_path)
            
            # Also remove from tree
            dup_item = diff['duplicate_item']
            parent = dup_item.parent()
            if parent:
                parent.removeChild(dup_item)
                
                # Remove group if empty
                if parent.childCount() <= 1:
                    idx = self.results_tree.indexOfTopLevelItem(parent)
                    if idx >= 0:
                        self.results_tree.takeTopLevelItem(idx)
            
            # Update status
            self.status_label.setText(f"Merged: {os.path.basename(duplicate_path)} into {os.path.basename(original_path)}")
            
            # Store result and close dialog
            self.comparison_result = "merge"
            dialog.accept()
        except Exception as e:
            QMessageBox.critical(dialog, "Error", f"Error merging files: {str(e)}")
    
    def cancel_all_comparisons(self, dialog):
        """Cancel all remaining comparisons"""
        confirm = QMessageBox.question(
            dialog, 
            "Cancel All", 
            "Stop comparing all remaining files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.comparison_result = "cancel_all"
            dialog.accept()

    def compare_files(self, file1, file2):
        """Compare two files and return a list of differences"""
        try:
            # Read file contents
            with open(file1, 'r', encoding='utf-8') as f:
                content1 = f.read()
                
            with open(file2, 'r', encoding='utf-8') as f:
                content2 = f.read()
                
            # Extract YAML and body
            yaml1, body1 = self.extract_yaml_and_body(content1)
            yaml2, body2 = self.extract_yaml_and_body(content2)
            
            # Compare YAML front matter
            yaml_diff = {}
            yaml1_dict = {}
            yaml2_dict = {}
            
            # Parse YAML blocks into dictionaries
            for line in yaml1.split('\n'):
                if ':' in line:
                    try:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        yaml1_dict[key] = value
                    except:
                        pass
            
            for line in yaml2.split('\n'):
                if ':' in line:
                    try:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        yaml2_dict[key] = value
                    except:
                        pass
            
            # Find differences
            all_keys = set(yaml1_dict.keys()) | set(yaml2_dict.keys())
            for key in all_keys:
                if key not in yaml1_dict:
                    yaml_diff[key] = (None, yaml2_dict[key])
                elif key not in yaml2_dict:
                    yaml_diff[key] = (yaml1_dict[key], None)
                elif yaml1_dict[key] != yaml2_dict[key]:
                    yaml_diff[key] = (yaml1_dict[key], yaml2_dict[key])
            
            # Compare tags specifically
            tags1 = self.parse_tags(yaml1_dict.get('tags', ''))
            tags2 = self.parse_tags(yaml2_dict.get('tags', ''))
            tags_only_in_1 = [t for t in tags1 if t not in tags2]
            tags_only_in_2 = [t for t in tags2 if t not in tags1]
            
            # Compute similarity of bodies
            # Simple case: identical content
            if body1.strip() == body2.strip():
                body_similarity = 1.0
                content_diff = []
            else:
                # Convert to lines and compare
                lines1 = body1.strip().split('\n')
                lines2 = body2.strip().split('\n')
                
                # Calculate similarity (simple ratio of matching lines)
                matching_lines = sum(1 for l1, l2 in zip(lines1, lines2) if l1 == l2)
                total_lines = max(len(lines1), len(lines2))
                body_similarity = matching_lines / total_lines if total_lines > 0 else 0
                
                # Generate diff output
                content_diff = []
                for i, (l1, l2) in enumerate(zip(lines1, lines2)):
                    if l1 != l2:
                        content_diff.append((i, l1, l2))
                
                # Add missing lines from the longer file
                for i in range(min(len(lines1), len(lines2)), len(lines1)):
                    content_diff.append((i, lines1[i], None))
                for i in range(min(len(lines1), len(lines2)), len(lines2)):
                    content_diff.append((i, None, lines2[i]))
            
            # Return all differences
            return {
                'yaml_diff': yaml_diff,
                'tags_only_in_1': tags_only_in_1,
                'tags_only_in_2': tags_only_in_2,
                'body_similarity': body_similarity,
                'content_diff': content_diff,
                'file1': os.path.basename(file1),
                'file2': os.path.basename(file2)
            }
        
        except Exception as e:
            print(f"Error comparing files: {e}")
            import traceback
            traceback.print_exc()
            return {
                'error': str(e),
                'file1': os.path.basename(file1),
                'file2': os.path.basename(file2)
            }

    def show_context_menu(self, position):
        """Show context menu for the results tree"""
        # Get the item at the position
        item = self.results_tree.itemAt(position)
        if not item:
            return
            
        # Don't show context menu for group items (top-level)
        if item.parent() is None:
            return
            
        # Create context menu
        context_menu = QMenu(self)
        
        # Add actions
        preview_action = context_menu.addAction("Preview File")
        open_action = context_menu.addAction("Open File")
        copy_path_action = context_menu.addAction("Copy Path")
        context_menu.addSeparator()
        delete_action = context_menu.addAction("Delete File")
        
        # Get file path from the item (column 4)
        file_path = item.text(4)
        
        # Execute the menu and get the selected action
        action = context_menu.exec(self.results_tree.viewport().mapToGlobal(position))
        
        # Handle actions
        if action == preview_action:
            self.preview_file(file_path)
        elif action == open_action:
            self.open_file(file_path)
        elif action == copy_path_action:
            QApplication.clipboard().setText(file_path)
            self.status_label.setText(f"Copied path to clipboard: {file_path}")
        elif action == delete_action:
            confirm = QMessageBox.question(
                self, 
                "Confirm Deletion", 
                f"Are you sure you want to delete {os.path.basename(file_path)}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    os.unlink(file_path)
                    item.setText(5, "Deleted")
                    self.status_label.setText(f"Deleted file: {file_path}")
                except Exception as e:
                    QMessageBox.warning(self, "Delete Failed", f"Could not delete file: {str(e)}")
    
    def preview_file(self, file_path):
        """Preview file content in a dialog"""
        try:
            # Make sure file exists
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "File Not Found", f"File not found: {file_path}")
                return
                
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Create preview dialog
            preview_dialog = QDialog(self)
            preview_dialog.setWindowTitle(f"Preview: {os.path.basename(file_path)}")
            preview_dialog.resize(700, 500)
            
            # Layout
            layout = QVBoxLayout(preview_dialog)
            
            # File info section
            info_layout = QHBoxLayout()
            
            # File size
            size = os.path.getsize(file_path)
            size_label = QLabel(f"Size: {self.format_size(size)}")
            info_layout.addWidget(size_label)
            
            # Modified time
            modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            time_label = QLabel(f"Modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
            info_layout.addWidget(time_label)
            
            # Add path label
            path_label = QLabel(f"Path: {file_path}")
            path_label.setWordWrap(True)
            
            layout.addLayout(info_layout)
            layout.addWidget(path_label)
            
            # Text editor for content
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("monospace"))
            text_edit.setText(content)
            
            layout.addWidget(text_edit)
            
            # Close button
            button_layout = QHBoxLayout()
            close_button = QPushButton("Close")
            close_button.clicked.connect(preview_dialog.accept)
            button_layout.addStretch()
            button_layout.addWidget(close_button)
            layout.addLayout(button_layout)
            
            # Show dialog
            preview_dialog.exec()
            
        except Exception as e:
            QMessageBox.warning(self, "Preview Error", f"Error previewing file: {str(e)}")
    
    def open_file(self, file_path):
        """Open file with default application"""
        try:
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "File Not Found", f"File not found: {file_path}")
                return
                
            # Use platform-specific method to open file
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
                
            self.status_label.setText(f"Opened file: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Open Failed", f"Could not open file: {str(e)}")

    def copy_selected_paths(self):
        """Copy paths of selected items to clipboard"""
        selected_paths = []
        
        # Collect all selected or checked items
        for group_idx in range(self.results_tree.topLevelItemCount()):
            group_item = self.results_tree.topLevelItem(group_idx)
            
            for child_idx in range(group_item.childCount()):
                child_item = group_item.child(child_idx)
                # Include items that are either checked or selected
                if child_item.checkState(0) == Qt.CheckState.Checked or child_item.isSelected():
                    file_path = child_item.text(4)  # Path is in column 4
                    selected_paths.append(file_path)
        
        if not selected_paths:
            QMessageBox.information(self, "No Selection", "No items selected for copying paths.")
            return
        
        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(selected_paths))
        
        # Update status
        self.status_label.setText(f"Copied {len(selected_paths)} file paths to clipboard")

    def update_progress(self, value, maximum):
        """Update the progress bar"""
        if maximum > 0:
            percentage = (value / maximum) * 100
            self.progress_bar.setValue(int(percentage))
            self.progress_label.setText(f"Processing files: {value}/{maximum} ({int(percentage)}%)")

    def on_error(self, error_msg):
        """Handle errors from the worker thread"""
        QMessageBox.critical(self, "Error", error_msg)
        self.status_label.setText(f"Error: {error_msg}")
        self.progress_label.setText("Failed")
        print(f"Error in duplicate finder: {error_msg}")
        
        # Ensure buttons are enabled
        self.enable_all_buttons()

    def process_duplicates(self, duplicates):
        """Process duplicate results from worker"""
        # Make results visible regardless of whether duplicates were found
        self.results_group.setVisible(True)
        
        # Log what we received for debugging
        print(f"Received duplicate results: {len(duplicates)} groups")
        for key in duplicates.keys():
            print(f"  Group: {key} with {len(duplicates[key])} files")
        
        # Special handling for empty files and frontmatter-only files
        empty_files_to_add = []  # Completely empty files (0 bytes)
        frontmatter_files = []   # Files with only frontmatter, no content
        keys_to_remove = []
        
        for key, files in list(duplicates.items()):
            # Check if these are empty files (0 bytes)
            if all(f.get('size', 0) == 0 for f in files):
                # Extract these files for special handling
                for file in files:
                    # Mark each empty file as its own "original" if they have different names
                    file['is_original'] = True
                    file['is_empty'] = True
                    empty_files_to_add.append(file)
                keys_to_remove.append(key)
            
            # Check for frontmatter-only files
            elif any(f.get('is_frontmatter_only', False) for f in files):
                # Extract these files for special handling
                for file in files:
                    frontmatter_files.append(file)
                keys_to_remove.append(key)
            
            # Also check for content groups that are actually empty files or frontmatter-only
            # This is a fallback check if the worker didn't properly identify them
            elif "content_" in str(key):
                is_empty_group = True
                is_frontmatter_group = True
                
                for file in files:
                    file_path = file.get('path', '')
                    try:
                        # Check if file is empty
                        if os.path.getsize(file_path) > 0:
                            is_empty_group = False
                            
                            # Check if file has only frontmatter
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            if not content.startswith('---'):
                                is_frontmatter_group = False
                            elif '---' in content[3:]:
                                # Check if there's content after frontmatter
                                parts = content.split('---', 2)
                                if len(parts) >= 3 and parts[2].strip():
                                    is_frontmatter_group = False
                    except Exception:
                        is_empty_group = False
                        is_frontmatter_group = False
                
                if is_empty_group:
                    # These are empty files misidentified as content group
                    for file in files:
                        file['is_original'] = True
                        file['is_empty'] = True
                        empty_files_to_add.append(file)
                    keys_to_remove.append(key)
                elif is_frontmatter_group:
                    # These are frontmatter-only files misidentified as content group
                    for file in files:
                        file['is_frontmatter_only'] = True
                        frontmatter_files.append(file)
                    keys_to_remove.append(key)
                    
        # Remove files that we'll handle separately
        for key in keys_to_remove:
            if key in duplicates:
                del duplicates[key]
                
        # Group empty files by basename to find true duplicates
        if empty_files_to_add:
            empty_files_by_name = {}
            for file in empty_files_to_add:
                basename = os.path.basename(file['path'])
                if basename not in empty_files_by_name:
                    empty_files_by_name[basename] = []
                empty_files_by_name[basename].append(file)
            
            # Add duplicate empty files as groups, and unique ones separately
            unique_empty_files = []
            for basename, files in empty_files_by_name.items():
                if len(files) > 1:
                    # These are actual duplicate empty files (same name)
                    # Sort by modified time and mark newest as original
                    files.sort(key=lambda x: x.get('modified', 0), reverse=True)
                    files[0]['is_original'] = True
                    for i in range(1, len(files)):
                        files[i]['is_original'] = False
                    duplicates[f'empty_{basename}'] = files
                else:
                    # Unique empty file - add to collection for a separate group
                    unique_empty_files.extend(files)
            
            # Add all unique empty files as a single group
            if unique_empty_files:
                duplicates['empty_files_unique'] = unique_empty_files
        
        # Group frontmatter-only files by their tags to find duplicates
        if frontmatter_files:
            # First group by tags
            frontmatter_by_tags = {}
            for file in frontmatter_files:
                tags_key = ','.join(sorted(file.get('tags', [])))
                if tags_key not in frontmatter_by_tags:
                    frontmatter_by_tags[tags_key] = []
                frontmatter_by_tags[tags_key].append(file)
            
            # Process each group
            for tags_key, files in frontmatter_by_tags.items():
                if len(files) > 1:
                    # Sort by modified time (newest first) and mark the newest as original
                    files.sort(key=lambda x: x.get('modified', 0), reverse=True)
                    files[0]['is_original'] = True
                    for i in range(1, len(files)):
                        files[i]['is_original'] = False
                    tag_label = tags_key[:20] + '...' if len(tags_key) > 20 else tags_key
                    duplicates[f'frontmatter_{hash(tags_key)}'] = files
                else:
                    # Just one file with these tags - not a duplicate
                    files[0]['is_original'] = True
                    duplicates[f'frontmatter_unique_{hash(tags_key)}'] = files
            
        self.populate_results(duplicates)
        self.enable_all_buttons()
        
        # Total up stats for the status message
        total_groups = 0
        total_duplicates = 0
        for group in duplicates.values():
            if len(group) > 1:  # Only count actual duplicate groups
                total_groups += 1
                total_files = len(group)
                # Count duplicates (non-originals)
                duplicates_in_group = sum(1 for f in group if not f.get('is_original', False))
                total_duplicates += duplicates_in_group
                
        if total_groups > 0:
            self.status_label.setText(f"Found {total_groups} duplicate groups with {total_duplicates} duplicate files")
            
            # Auto-select all duplicates
            QTimer.singleShot(100, self.auto_select_duplicates)
        else:
            self.status_label.setText("No duplicates found")
            # Make it clear to the user what happened
            self.results_tree.clear()
            no_results_item = QTreeWidgetItem(self.results_tree)
            no_results_item.setText(0, "No duplicate notes found")
            no_results_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        
        self.progress_label.setText("Done")
        self.progress_bar.setValue(100)

