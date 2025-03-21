from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                           QTreeWidget, QTreeWidgetItem, QLabel, QProgressBar,
                           QCheckBox, QMessageBox, QHeaderView, QComboBox, QGroupBox)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QIcon
import os
import re
import json
from datetime import datetime
from pathlib import Path

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
        """Find notes with specific suffixes like '-surfacepro6'"""
        suffix_pattern = "-surfacepro6"
        suffix_groups = {}
        total_files = 0
        processed_files = 0
        
        # First pass: count files
        for root, _, files in os.walk(self.directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    total_files += 1
        
        self.progress.emit(0, total_files)
        
        # Second pass: find files with suffix patterns
        for root, _, files in os.walk(self.directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    filepath = os.path.join(root, filename)
                    
                    # Check if file has the suffix pattern
                    base_name = os.path.splitext(filename)[0]
                    if suffix_pattern in base_name:
                        # Get the original name by removing the suffix
                        original_name = base_name.replace(suffix_pattern, "")
                        original_file = original_name + ".md"
                        original_path = os.path.join(root, original_file)
                        
                        # Check if the original file exists
                        if os.path.exists(original_path):
                            # Add to suffix groups
                            group_key = f"{root}:{original_name}"
                            if group_key not in suffix_groups:
                                suffix_groups[group_key] = []
                            
                            suffix_groups[group_key].append(filepath)
                            suffix_groups[group_key].append(original_path)
                    
                    processed_files += 1
                    if processed_files % 10 == 0:
                        self.progress.emit(processed_files, total_files)
        
        # Format results
        duplicates = {}
        for group_key, filepaths in suffix_groups.items():
            # Remove duplicates in the group
            filepaths = list(set(filepaths))
            if len(filepaths) > 1:
                # Create a unique hash for this group
                group_hash = f"suffix_{group_key}"
                duplicates[group_hash] = self.analyze_suffix_duplicates(filepaths, suffix_pattern)
        
        self.progress.emit(total_files, total_files)
        self.finished.emit(duplicates)
    
    def analyze_suffix_duplicates(self, filepaths, suffix_pattern):
        """Analyze suffix-based duplicates"""
        results = []
        
        for path in filepaths:
            filename = os.path.basename(path)
            base_name = os.path.splitext(filename)[0]
            
            # Analyze file
            info = {
                'path': path,
                'filename': filename,
                'size': os.path.getsize(path),
                'modified': os.path.getmtime(path),
                'is_original': not suffix_pattern in base_name,  # Mark non-suffix files as original
                'suffix_pattern': suffix_pattern if suffix_pattern in base_name else None,
                'tags': self.extract_tags(path)
            }
            
            results.append(info)
        
        # Sort results by modified time (newest first)
        results.sort(key=lambda x: x['modified'], reverse=True)
        
        return results

class NotesDuplicateDialog(QDialog):
    """Dialog for managing duplicate notes"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.explorer = parent
        self.duplicate_finder = parent.duplicate_finder if hasattr(parent, 'duplicate_finder') else None
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        self.setWindowTitle("Duplicate Notes")
        self.setMinimumSize(900, 600)
        
        layout = QVBoxLayout(self)
        
        # Scan options
        options_layout = QHBoxLayout()
        
        self.scan_mode_label = QLabel("Scan Mode:")
        options_layout.addWidget(self.scan_mode_label)
        
        self.scan_mode_combo = QComboBox()
        self.scan_mode_combo.addItems(["Content", "Title", "Tags", "Suffix"])
        options_layout.addWidget(self.scan_mode_combo)
        
        self.scan_btn = QPushButton("Scan for Duplicates")
        self.scan_btn.clicked.connect(self.start_scan)
        options_layout.addWidget(self.scan_btn)
        
        options_layout.addStretch()
        
        layout.addLayout(options_layout)
        
        # Selection strategy group
        self.strategy_group = QGroupBox("Selection Strategy")
        self.strategy_group.setEnabled(False)
        strategy_layout = QHBoxLayout(self.strategy_group)
        
        # Radio buttons for selection strategy
        self.select_duplicates_radio = QCheckBox("Select Duplicates (non-originals)")
        self.select_duplicates_radio.setChecked(True)
        strategy_layout.addWidget(self.select_duplicates_radio)
        
        self.select_older_radio = QCheckBox("Select Older Files")
        strategy_layout.addWidget(self.select_older_radio)
        
        self.select_newer_radio = QCheckBox("Select Newer Files")
        strategy_layout.addWidget(self.select_newer_radio)
        
        self.select_suffix_radio = QCheckBox("Select Files with Suffix")
        strategy_layout.addWidget(self.select_suffix_radio)
        
        # Connect radio buttons to ensure only one is selected
        self.select_duplicates_radio.toggled.connect(self.update_selection_strategy)
        self.select_older_radio.toggled.connect(self.update_selection_strategy)
        self.select_newer_radio.toggled.connect(self.update_selection_strategy)
        self.select_suffix_radio.toggled.connect(self.update_selection_strategy)
        
        layout.addWidget(self.strategy_group)
        
        # Progress section
        progress_layout = QHBoxLayout()
        self.progress_label = QLabel("Ready to scan")
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)
        
        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels([
            "Filename", "Path", "Size", "Modified", "Tags", "Status"
        ])
        self.results_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_tree)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.auto_select_btn = QPushButton("Auto-select Based on Strategy")
        self.auto_select_btn.clicked.connect(self.auto_select_duplicates)
        self.auto_select_btn.setEnabled(False)
        button_layout.addWidget(self.auto_select_btn)
        
        self.clear_btn = QPushButton("Clear Selection")
        self.clear_btn.clicked.connect(self.clear_selection)
        self.clear_btn.setEnabled(False)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        
        self.merge_btn = QPushButton("Merge Selected")
        self.merge_btn.clicked.connect(self.merge_selected)
        self.merge_btn.setEnabled(False)
        button_layout.addWidget(self.merge_btn)
        
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)
        
        layout.addLayout(button_layout)
        
    def scan_directory(self, directory):
        """Scan directory for duplicates"""
        self.show()  # Make sure dialog is visible
        # Start the scan with default mode (content)
        self.scan_mode_combo.setCurrentIndex(0)  # Set to Content
        self.start_scan()
        
    def start_scan(self):
        """Start scanning for duplicates"""
        # Get scan mode
        scan_mode = self.scan_mode_combo.currentText().lower()
        
        # Get notes vault path
        vault_path = self.explorer.get_notes_vault_path()
        if not vault_path or not os.path.exists(vault_path):
            QMessageBox.warning(
                self,
                "Invalid Path",
                f"Notes vault path is invalid: {vault_path}"
            )
            return
        
        # Update UI
        self.progress_bar.setRange(0, 0)  # Show busy indicator
        self.progress_label.setText(f"Scanning notes using {scan_mode} mode...")
        self.results_tree.clear()
        self.scan_btn.setEnabled(False)
        
        # Start scanner thread
        self.scanner = NotesDuplicateScanner(vault_path, scan_mode, self)
        self.scanner.progress.connect(self.update_progress)
        self.scanner.finished.connect(self.show_results)
        self.scanner.start()
        
    def update_progress(self, current, total):
        """Update progress bar"""
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processed {current} of {total} files...")
        
    def show_results(self, duplicates):
        """Display duplicate files in tree"""
        self.results_tree.clear()
        total_duplicates = 0
        
        for hash_value, files in duplicates.items():
            group_item = QTreeWidgetItem(self.results_tree)
            
            # Set group title based on hash type
            if hash_value.startswith("title_"):
                title = hash_value.replace("title_", "")
                group_item.setText(0, f"Title: {title} ({len(files)} files)")
            elif hash_value.startswith("tags_"):
                tags = hash_value.replace("tags_", "").replace("_", ", ")
                group_item.setText(0, f"Similar Tags: {tags} ({len(files)} files)")
            elif hash_value.startswith("suffix_"):
                group_key = hash_value.replace("suffix_", "")
                group_item.setText(0, f"Suffix: {group_key} ({len(files)} files)")
            else:
                group_item.setText(0, f"Content Group ({len(files)} files)")
                
            group_item.setExpanded(True)
            
            for file_info in files:
                file_item = QTreeWidgetItem(group_item)
                file_item.setText(0, file_info['filename'])
                file_item.setText(1, file_info['path'])
                file_item.setText(2, self.format_size(file_info['size']))
                file_item.setText(3, datetime.fromtimestamp(
                    file_info['modified']).strftime('%Y-%m-%d %H:%M:%S'))
                
                # Add tags if available
                if 'tags' in file_info and file_info['tags']:
                    file_item.setText(4, ", ".join(file_info['tags']))
                
                # Set status
                if file_info['is_original']:
                    status = "Original"
                    file_item.setIcon(0, QIcon.fromTheme("document-save"))
                else:
                    status = "Duplicate"
                    if 'suffix_pattern' in file_info and file_info['suffix_pattern']:
                        status += f" (suffix: {file_info['suffix_pattern']})"
                    file_item.setIcon(0, QIcon.fromTheme("edit-copy"))
                    total_duplicates += 1
                
                file_item.setText(5, status)
                
                # Add checkbox for all items in duplicate groups
                file_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        # Update progress label with summary
        self.progress_label.setText(
            f"Found {total_duplicates} potential duplicate notes in {len(duplicates)} groups"
        )
        
        # Enable buttons and strategy group
        self.scan_btn.setEnabled(True)
        self.auto_select_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.merge_btn.setEnabled(True)
        self.strategy_group.setEnabled(True)
        
        # Auto-select the right strategy based on the scan mode
        scan_mode = self.scan_mode_combo.currentText().lower()
        if scan_mode == "suffix":
            self.select_suffix_radio.setChecked(True)
        else:
            self.select_duplicates_radio.setChecked(True)
        
    def update_selection_strategy(self, checked):
        """Update selection strategies to ensure only one is checked"""
        if not checked:
            # Don't allow unchecking without another option checked
            sender = self.sender()
            if not any([
                self.select_duplicates_radio.isChecked(),
                self.select_older_radio.isChecked(),
                self.select_newer_radio.isChecked(),
                self.select_suffix_radio.isChecked()
            ]):
                sender.setChecked(True)
                return
        
        # If this radio was checked, uncheck the others
        sender = self.sender()
        if sender == self.select_duplicates_radio and sender.isChecked():
            self.select_older_radio.setChecked(False)
            self.select_newer_radio.setChecked(False)
            self.select_suffix_radio.setChecked(False)
        elif sender == self.select_older_radio and sender.isChecked():
            self.select_duplicates_radio.setChecked(False)
            self.select_newer_radio.setChecked(False)
            self.select_suffix_radio.setChecked(False)
        elif sender == self.select_newer_radio and sender.isChecked():
            self.select_duplicates_radio.setChecked(False)
            self.select_older_radio.setChecked(False)
            self.select_suffix_radio.setChecked(False)
        elif sender == self.select_suffix_radio and sender.isChecked():
            self.select_duplicates_radio.setChecked(False)
            self.select_older_radio.setChecked(False)
            self.select_newer_radio.setChecked(False)
            
        # Apply the selected strategy immediately if checked
        if checked and self.results_tree.topLevelItemCount() > 0:
            self.auto_select_duplicates()
            
    def auto_select_duplicates(self):
        """Automatically select duplicate files based on the chosen strategy"""
        root = self.results_tree.invisibleRootItem()
        
        # Clear current selection first
        self.clear_selection()
        
        for i in range(root.childCount()):
            group = root.child(i)
            items = []
            
            # Collect all items in this group
            for j in range(group.childCount()):
                items.append(group.child(j))
            
            # Sort items by modification time (newest first)
            items.sort(key=lambda item: item.text(3), reverse=True)
            
            # Select based on strategy
            if self.select_duplicates_radio.isChecked():
                # Select all non-original files (traditional approach)
                for item in items:
                    if "Duplicate" in item.text(5):
                        item.setCheckState(0, Qt.CheckState.Checked)
                        
            elif self.select_older_radio.isChecked():
                # Skip the newest file, select all older ones
                for item in items[1:]:  # Skip first (newest) item
                    item.setCheckState(0, Qt.CheckState.Checked)
                    
            elif self.select_newer_radio.isChecked():
                # Skip the oldest file, select all newer ones
                items.reverse()  # Now sorted with oldest first
                for item in items[1:]:  # Skip first (oldest) item
                    item.setCheckState(0, Qt.CheckState.Checked)
                    
            elif self.select_suffix_radio.isChecked():
                # Select files with suffix pattern (e.g., -surfacepro6)
                for item in items:
                    if item.text(5) and "suffix" in item.text(5).lower():
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
                    selected_files.append(item.text(1))  # Get file path
        
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
            failed = []
            succeeded = []
            
            for filepath in selected_files:
                try:
                    os.remove(filepath)
                    succeeded.append(filepath)
                except Exception as e:
                    failed.append((filepath, str(e)))
            
            # Show results
            if failed:
                errors = "\n".join(
                    f"- {path}: {error}"
                    for path, error in failed
                )
                QMessageBox.warning(
                    self,
                    "Deletion Errors",
                    f"Some files could not be deleted:\n{errors}"
                )
            
            # Refresh tree
            self.remove_deleted_items(succeeded)
            
            # Refresh explorer view
            if hasattr(self.explorer, 'refresh_view'):
                self.explorer.refresh_view()
            
            QMessageBox.information(
                self,
                "Deletion Complete",
                f"Successfully deleted {len(succeeded)} files."
            )
    
    def merge_selected(self):
        """Merge selected notes with their original"""
        root = self.results_tree.invisibleRootItem()
        
        # Process each group
        for i in range(root.childCount()):
            group = root.child(i)
            
            # Find original file in this group
            original_item = None
            selected_items = []
            
            for j in range(group.childCount()):
                item = group.child(j)
                if "Original" in item.text(5):
                    original_item = item
                elif item.checkState(0) == Qt.CheckState.Checked:
                    selected_items.append(item)
            
            # Skip if no original or no selected items
            if not original_item or not selected_items:
                continue
                
            # Merge selected items into original
            original_path = original_item.text(1)
            
            try:
                # Read original content
                with open(original_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Process each selected item
                for item in selected_items:
                    duplicate_path = item.text(1)
                    
                    try:
                        # Read duplicate content
                        with open(duplicate_path, 'r', encoding='utf-8') as f:
                            duplicate_content = f.read()
                        
                        # Merge content
                        merged_content = self.merge_note_contents(
                            original_content, 
                            duplicate_content,
                            os.path.basename(duplicate_path)
                        )
                        
                        # Update original content for next merge
                        original_content = merged_content
                        
                        # Delete the duplicate file
                        os.remove(duplicate_path)
                        
                    except Exception as e:
                        QMessageBox.warning(
                            self,
                            "Merge Error",
                            f"Error merging {duplicate_path}: {str(e)}"
                        )
                
                # Write merged content back to original file
                with open(original_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                
                # Remove merged items from tree
                for item in selected_items:
                    group.removeChild(item)
                
                # Refresh explorer view
                if hasattr(self.explorer, 'refresh_view'):
                    self.explorer.refresh_view()
                
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Merge Error",
                    f"Error processing merge: {str(e)}"
                )
    
    def merge_note_contents(self, original, duplicate, duplicate_name):
        """Merge two note contents, handling YAML front matter and content"""
        # Extract YAML front matter from both notes
        original_yaml = ""
        original_content = original
        duplicate_yaml = ""
        duplicate_content = duplicate
        
        original_yaml_match = re.search(r'^---\s*\n(.*?)\n---', original, re.DOTALL)
        if original_yaml_match:
            original_yaml = original_yaml_match.group(0)
            original_content = original[len(original_yaml):].strip()
        
        duplicate_yaml_match = re.search(r'^---\s*\n(.*?)\n---', duplicate, re.DOTALL)
        if duplicate_yaml_match:
            duplicate_yaml = duplicate_yaml_match.group(1)
            duplicate_content = duplicate[len(duplicate_yaml_match.group(0)):].strip()
        
        # Merge YAML front matter (if both have it)
        merged_yaml = original_yaml
        if original_yaml and duplicate_yaml:
            # Extract tags from duplicate
            tag_match = re.search(r'tags:\s*\[(.*?)\]', duplicate_yaml)
            if tag_match:
                duplicate_tags = [t.strip().strip('"\'') for t in tag_match.group(1).split(',')]
                
                # Add to original tags
                if 'tags:' in original_yaml:
                    # Find and update tags in original
                    original_tag_match = re.search(r'tags:\s*\[(.*?)\]', original_yaml)
                    if original_tag_match:
                        original_tags = [t.strip().strip('"\'') for t in original_tag_match.group(1).split(',')]
                        # Combine tags
                        all_tags = list(set(original_tags + duplicate_tags))
                        # Replace tags in original
                        tag_str = ', '.join([f'"{t}"' for t in all_tags])
                        merged_yaml = re.sub(
                            r'tags:\s*\[(.*?)\]',
                            f'tags: [{tag_str}]',
                            original_yaml
                        )
        
        # Combine content
        merged_content = merged_yaml + "\n\n" + original_content + "\n\n## Content from " + duplicate_name + "\n\n" + duplicate_content
        
        return merged_content
    
    def remove_deleted_items(self, deleted_paths):
        """Remove deleted items from tree"""
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

    def refresh_view(self):
        """Refresh the results view after operations"""
        self.scan_btn.setEnabled(True)
        self.auto_select_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.merge_btn.setEnabled(False)
        self.strategy_group.setEnabled(False)
        self.results_tree.clear()
        self.progress_label.setText("Ready to scan")
        self.progress_bar.setValue(0) 