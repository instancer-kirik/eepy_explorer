import os
import shutil
import hashlib
import time
import logging
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QComboBox, QCheckBox, QProgressBar,
                            QMessageBox, QFileDialog, QListWidget, QListWidgetItem,
                            QGroupBox, QRadioButton, QDialogButtonBox, QTableWidget,
                            QTableWidgetItem, QHeaderView, QSplitter, QAbstractItemView,
                            QProgressDialog)

class DirectorySyncWorker(QThread):
    """Worker thread for synchronizing directories"""
    progress = pyqtSignal(int, str)  # Progress value, message
    log_message = pyqtSignal(str, str)  # Message, level (info, warning, error)
    sync_completed = pyqtSignal(dict)  # Stats about the sync operation
    
    def __init__(self, source_dir, target_dir, options=None):
        super().__init__()
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.options = options or {}
        # Default options
        if 'sync_mode' not in self.options:
            self.options['sync_mode'] = 'bidirectional'  # or 'one_way' or 'mirror'
        if 'conflict_resolution' not in self.options:
            self.options['conflict_resolution'] = 'newer'  # or 'source', 'target', 'keep_both'
        if 'file_types' not in self.options:
            self.options['file_types'] = ['.md']  # Default to markdown files
        if 'delete_orphaned' not in self.options:
            self.options['delete_orphaned'] = False
        if 'dry_run' not in self.options:
            self.options['dry_run'] = False
        if 'preserve_timestamps' not in self.options:
            self.options['preserve_timestamps'] = True
        
        # Store stats
        self.stats = {
            'files_analyzed': 0,
            'files_copied_to_target': 0,
            'files_copied_to_source': 0,
            'files_updated': 0,
            'files_skipped': 0,
            'conflicts_resolved': 0,
            'bytes_transferred': 0,
            'errors': 0,
            'files_deleted': 0,
            'operation_time': 0
        }
        
        # Keep track of sync actions for reporting
        self.sync_actions = []
        
        self.canceled = False
    
    def run(self):
        """Run the sync operation"""
        start_time = time.time()
        try:
            # Validate directories
            if not os.path.exists(self.source_dir):
                self.log_message.emit(f"Source directory doesn't exist: {self.source_dir}", "error")
                return
            if not os.path.exists(self.target_dir):
                if self.options.get('create_target', True):
                    try:
                        os.makedirs(self.target_dir, exist_ok=True)
                        self.log_message.emit(f"Created target directory: {self.target_dir}", "info")
                    except Exception as e:
                        self.log_message.emit(f"Failed to create target directory: {e}", "error")
                        return
                else:
                    self.log_message.emit(f"Target directory doesn't exist: {self.target_dir}", "error")
                    return
            
            # Build file index for both directories
            self.progress.emit(5, "Scanning source directory...")
            source_files = self.build_file_index(self.source_dir)
            
            self.progress.emit(30, "Scanning target directory...")
            target_files = self.build_file_index(self.target_dir)
            
            # Analysis phase
            self.progress.emit(50, "Analyzing differences...")
            sync_plan = self.analyze_directories(source_files, target_files)
            
            # Sync phase - if not dry run
            if not self.options['dry_run']:
                self.progress.emit(60, "Synchronizing files...")
                self.execute_sync_plan(sync_plan)
            else:
                self.log_message.emit("Dry run mode - no changes will be made", "info")
                # In dry run mode, just log the planned actions
                for action in sync_plan:
                    msg = f"Would {action['action']} {action['rel_path']}"
                    if action.get('reason'):
                        msg += f" ({action['reason']})"
                    self.log_message.emit(msg, "info")
            
            # Completion
            end_time = time.time()
            self.stats['operation_time'] = end_time - start_time
            
            self.progress.emit(100, "Sync completed")
            self.log_message.emit(
                f"Completed sync between {self.source_dir} and {self.target_dir}",
                "info"
            )
            self.sync_completed.emit(self.stats)
            
        except Exception as e:
            import traceback
            self.log_message.emit(f"Error during sync operation: {str(e)}", "error")
            self.log_message.emit(traceback.format_exc(), "error")
            self.stats['errors'] += 1
            self.sync_completed.emit(self.stats)
    
    def build_file_index(self, directory):
        """Build an index of files in the directory
        
        Returns a dict mapping relative paths to file info
        """
        file_index = {}
        
        # Get list of file extensions to include
        file_types = self.options.get('file_types', [])
        include_all = not file_types  # If no file types specified, include all
        
        for root, dirs, files in os.walk(directory):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in 
                      ['.eepy', '.obsidian', '.git', '.trash', '.archived', '__pycache__']]
            
            for filename in files:
                # Skip hidden files
                if filename.startswith('.'):
                    continue
                    
                # Check file extension if file types are specified
                if not include_all:
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext not in file_types:
                        continue
                
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, directory)
                
                try:
                    stat_info = os.stat(file_path)
                    file_size = stat_info.st_size
                    mod_time = stat_info.st_mtime
                    
                    # For markdown files, optionally extract tags
                    file_ext = os.path.splitext(filename)[1].lower()
                    tags = []
                    content_hash = None
                    
                    if file_ext == '.md' and self.options.get('analyze_content', True):
                        tags = self.extract_tags(file_path)
                        content_hash = self.compute_file_hash(file_path)
                    
                    file_index[rel_path] = {
                        'path': file_path,
                        'size': file_size,
                        'mod_time': mod_time,
                        'tags': tags,
                        'content_hash': content_hash
                    }
                    
                    self.stats['files_analyzed'] += 1
                    
                    # Update progress occasionally
                    if self.stats['files_analyzed'] % 25 == 0:
                        self.progress.emit(
                            min(45, 5 + int(self.stats['files_analyzed'] / 10)),
                            f"Analyzed {self.stats['files_analyzed']} files..."
                        )
                    
                except Exception as e:
                    self.log_message.emit(f"Error analyzing file {file_path}: {str(e)}", "error")
                    self.stats['errors'] += 1
        
        return file_index
    
    def analyze_directories(self, source_files, target_files):
        """Compare source and target file indexes and create a sync plan"""
        sync_plan = []
        
        # Files in source but not in target (need to copy to target)
        for rel_path in source_files:
            if rel_path not in target_files:
                sync_plan.append({
                    'action': 'copy_to_target',
                    'rel_path': rel_path,
                    'source_info': source_files[rel_path],
                    'reason': 'Only in source'
                })
        
        # Files in target but not in source
        for rel_path in target_files:
            if rel_path not in source_files:
                if self.options['sync_mode'] == 'bidirectional':
                    sync_plan.append({
                        'action': 'copy_to_source',
                        'rel_path': rel_path,
                        'target_info': target_files[rel_path],
                        'reason': 'Only in target'
                    })
                elif self.options['sync_mode'] == 'mirror' and self.options['delete_orphaned']:
                    sync_plan.append({
                        'action': 'delete_from_target',
                        'rel_path': rel_path,
                        'target_info': target_files[rel_path],
                        'reason': 'Orphaned in target'
                    })
        
        # Files in both (check for conflicts)
        for rel_path in set(source_files.keys()) & set(target_files.keys()):
            source_info = source_files[rel_path]
            target_info = target_files[rel_path]
            
            # Check if file content is different
            content_different = False
            
            # If both have content hashes, compare them
            if source_info.get('content_hash') and target_info.get('content_hash'):
                content_different = source_info['content_hash'] != target_info['content_hash']
            # Otherwise, use size and mod time as a proxy
            else:
                size_different = source_info['size'] != target_info['size']
                time_different = abs(source_info['mod_time'] - target_info['mod_time']) > 1  # 1 second tolerance
                content_different = size_different or time_different
            
            # If content is identical, skip
            if not content_different:
                sync_plan.append({
                    'action': 'skip',
                    'rel_path': rel_path,
                    'reason': 'Identical content'
                })
                continue
            
            # Handle conflict according to resolution strategy
            if self.options['conflict_resolution'] == 'newer':
                if source_info['mod_time'] > target_info['mod_time']:
                    sync_plan.append({
                        'action': 'copy_to_target',
                        'rel_path': rel_path,
                        'source_info': source_info,
                        'target_info': target_info,
                        'reason': 'Source is newer'
                    })
                else:
                    sync_plan.append({
                        'action': 'copy_to_source',
                        'rel_path': rel_path,
                        'source_info': source_info,
                        'target_info': target_info,
                        'reason': 'Target is newer'
                    })
            elif self.options['conflict_resolution'] == 'source':
                sync_plan.append({
                    'action': 'copy_to_target',
                    'rel_path': rel_path,
                    'source_info': source_info,
                    'target_info': target_info,
                    'reason': 'Source preferred'
                })
            elif self.options['conflict_resolution'] == 'target':
                sync_plan.append({
                    'action': 'copy_to_source',
                    'rel_path': rel_path,
                    'source_info': source_info,
                    'target_info': target_info,
                    'reason': 'Target preferred'
                })
            elif self.options['conflict_resolution'] == 'keep_both':
                # Create unique filenames for both
                base, ext = os.path.splitext(rel_path)
                source_unique = f"{base}.source{ext}"
                target_unique = f"{base}.target{ext}"
                
                # Skip if the renamed files already exist
                if source_unique not in target_files and target_unique not in source_files:
                    sync_plan.append({
                        'action': 'rename_in_target',
                        'rel_path': rel_path,
                        'new_rel_path': source_unique,
                        'source_info': source_files[rel_path],
                        'reason': 'Keeping both versions'
                    })
                    sync_plan.append({
                        'action': 'rename_in_source',
                        'rel_path': rel_path,
                        'new_rel_path': target_unique,
                        'target_info': target_files[rel_path],
                        'reason': 'Keeping both versions'
                    })
        
        return sync_plan
    
    def execute_sync_plan(self, sync_plan):
        """Execute the sync plan"""
        total_actions = len(sync_plan)
        completed = 0
        
        for action in sync_plan:
            if self.canceled:
                self.log_message.emit("Sync operation canceled by user", "warning")
                break
                
            try:
                rel_path = action['rel_path']
                action_type = action['action']
                
                # Update progress
                completed += 1
                progress_pct = min(99, 60 + int(completed * 35 / total_actions))
                self.progress.emit(progress_pct, f"Syncing files ({completed}/{total_actions})...")
                
                if action_type == 'skip':
                    self.stats['files_skipped'] += 1
                    continue
                
                if action_type == 'copy_to_target':
                    source_path = action['source_info']['path']
                    target_path = os.path.join(self.target_dir, rel_path)
                    
                    # Ensure target directory exists
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    # Copy the file
                    self.copy_file(source_path, target_path)
                    self.stats['files_copied_to_target'] += 1
                    self.log_message.emit(f"Copied to target: {rel_path}", "info")
                
                elif action_type == 'copy_to_source':
                    target_path = action['target_info']['path']
                    source_path = os.path.join(self.source_dir, rel_path)
                    
                    # Ensure source directory exists
                    os.makedirs(os.path.dirname(source_path), exist_ok=True)
                    
                    # Copy the file
                    self.copy_file(target_path, source_path)
                    self.stats['files_copied_to_source'] += 1
                    self.log_message.emit(f"Copied to source: {rel_path}", "info")
                
                elif action_type == 'delete_from_target':
                    target_path = action['target_info']['path']
                    os.remove(target_path)
                    self.stats['files_deleted'] += 1
                    self.log_message.emit(f"Deleted from target: {rel_path}", "info")
                
                elif action_type == 'rename_in_target':
                    source_path = action['source_info']['path']
                    new_rel_path = action['new_rel_path']
                    target_path = os.path.join(self.target_dir, new_rel_path)
                    
                    # Ensure target directory exists
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    # Copy with new name
                    self.copy_file(source_path, target_path)
                    self.stats['conflicts_resolved'] += 1
                    self.log_message.emit(f"Copied to target with new name: {new_rel_path}", "info")
                
                elif action_type == 'rename_in_source':
                    target_path = action['target_info']['path']
                    new_rel_path = action['new_rel_path']
                    source_path = os.path.join(self.source_dir, new_rel_path)
                    
                    # Ensure source directory exists
                    os.makedirs(os.path.dirname(source_path), exist_ok=True)
                    
                    # Copy with new name
                    self.copy_file(target_path, source_path)
                    self.stats['conflicts_resolved'] += 1
                    self.log_message.emit(f"Copied to source with new name: {new_rel_path}", "info")
                
                # Record the action
                self.sync_actions.append({
                    'action': action_type,
                    'path': rel_path,
                    'reason': action.get('reason', '')
                })
                
            except Exception as e:
                self.stats['errors'] += 1
                self.log_message.emit(f"Error processing {action['action']} for {rel_path}: {str(e)}", "error")
    
    def copy_file(self, src, dst):
        """Copy a file with optional timestamp preservation"""
        # Calculate file size for stats
        file_size = os.path.getsize(src)
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        
        # Copy the file
        shutil.copy2(src, dst) if self.options.get('preserve_timestamps', True) else shutil.copy(src, dst)
        
        self.stats['bytes_transferred'] += file_size
    
    def extract_tags(self, file_path):
        """Extract tags from markdown frontmatter"""
        tags = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(2000)  # Read first 2KB to find frontmatter
                
                # Check for YAML frontmatter (between --- lines)
                if content.startswith('---'):
                    end_index = content.find('---', 3)
                    if end_index > 0:
                        frontmatter = content[3:end_index].strip()
                        
                        # Look for tags/tag entries
                        for line in frontmatter.split('\n'):
                            line = line.strip()
                            if line.startswith('tags:') or line.startswith('tag:'):
                                # Extract tags from various formats
                                tag_part = line.split(':', 1)[1].strip()
                                
                                # Format: tags: [tag1, tag2]
                                if tag_part.startswith('[') and tag_part.endswith(']'):
                                    tag_list = tag_part[1:-1].split(',')
                                    for tag in tag_list:
                                        tag = tag.strip().strip('"\'')
                                        if tag:
                                            tags.append(tag)
                                            
                                # Format: tags:
                                #   - tag1
                                #   - tag2
                                elif not tag_part:
                                    # Tags might be in list format in following lines
                                    continue
                                
                                # Format: tags: tag1 tag2
                                else:
                                    for tag in tag_part.split():
                                        tag = tag.strip().strip('"\'')
                                        if tag:
                                            tags.append(tag)
                            
                            # Handle list items for tags defined in multiline format
                            elif line.startswith('- ') and ('tags:' in frontmatter or 'tag:' in frontmatter):
                                tag = line[2:].strip().strip('"\'')
                                if tag:
                                    tags.append(tag)
        
        except Exception as e:
            print(f"Error extracting tags from {file_path}: {e}")
            
        return tags

    def compute_file_hash(self, file_path, algorithm='blake2b'):
        """Compute a hash of the file's contents"""
        hasher = getattr(hashlib, algorithm)()
        
        try:
            with open(file_path, 'rb') as f:
                # Read the file in chunks to avoid memory issues
                chunk_size = 8192  # 8KB chunks
                while chunk := f.read(chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error computing hash for {file_path}: {e}")
            return None
    
    def cancel(self):
        """Cancel the sync operation"""
        self.canceled = True 

class DirectorySyncDialog(QDialog):
    """Dialog for synchronizing two directories"""
    
    def __init__(self, parent=None, source_dir=None, target_dir=None):
        super().__init__(parent)
        self.setWindowTitle("Directory Synchronization")
        self.resize(800, 600)
        self.setModal(True)
        
        self.source_dir = source_dir or ""
        self.target_dir = target_dir or ""
        self.sync_worker = None
        self.log_messages = []
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Directory selection
        dir_layout = QHBoxLayout()
        
        # Source directory
        source_group = QGroupBox("Source Directory:")
        source_layout = QHBoxLayout(source_group)
        self.source_edit = QLabel(self.source_dir)
        self.source_edit.setWordWrap(True)
        source_browse = QPushButton("Browse...")
        source_browse.clicked.connect(self.browse_source)
        source_layout.addWidget(self.source_edit, 1)
        source_layout.addWidget(source_browse)
        dir_layout.addWidget(source_group)
        
        # Target directory
        target_group = QGroupBox("Target Directory:")
        target_layout = QHBoxLayout(target_group)
        self.target_edit = QLabel(self.target_dir)
        self.target_edit.setWordWrap(True)
        target_browse = QPushButton("Browse...")
        target_browse.clicked.connect(self.browse_target)
        target_layout.addWidget(self.target_edit, 1)
        target_layout.addWidget(target_browse)
        dir_layout.addWidget(target_group)
        
        layout.addLayout(dir_layout)
        
        # Sync options
        options_group = QGroupBox("Sync Options")
        options_layout = QVBoxLayout(options_group)
        
        # Sync mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Sync Mode:"))
        self.sync_mode = QComboBox()
        self.sync_mode.addItems(["Bidirectional", "One-way (Source → Target)", "Mirror (Target matches Source)"])
        mode_layout.addWidget(self.sync_mode, 1)
        options_layout.addLayout(mode_layout)
        
        # Conflict resolution
        conflict_layout = QHBoxLayout()
        conflict_layout.addWidget(QLabel("Conflict Resolution:"))
        self.conflict_resolution = QComboBox()
        self.conflict_resolution.addItems(["Keep Newer", "Keep Source", "Keep Target", "Keep Both"])
        conflict_layout.addWidget(self.conflict_resolution, 1)
        options_layout.addLayout(conflict_layout)
        
        # File types
        filetype_layout = QHBoxLayout()
        filetype_layout.addWidget(QLabel("File Types:"))
        self.file_types = QComboBox()
        self.file_types.addItems(["Markdown files only (.md)", "All supported notes files (.md, .txt, .html)", "All files"])
        filetype_layout.addWidget(self.file_types, 1)
        options_layout.addLayout(filetype_layout)
        
        # Additional options
        self.delete_orphaned = QCheckBox("Delete orphaned files in target")
        self.delete_orphaned.setChecked(False)
        options_layout.addWidget(self.delete_orphaned)
        
        self.preserve_timestamps = QCheckBox("Preserve file timestamps")
        self.preserve_timestamps.setChecked(True)
        options_layout.addWidget(self.preserve_timestamps)
        
        self.dry_run = QCheckBox("Dry run (simulate, don't modify files)")
        self.dry_run.setChecked(True)
        options_layout.addWidget(self.dry_run)
        
        layout.addWidget(options_group)
        
        # Log area
        log_group = QGroupBox("Operation Log")
        log_layout = QVBoxLayout(log_group)
        self.log_widget = QListWidget()
        log_layout.addWidget(self.log_widget)
        layout.addWidget(log_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready to sync")
        layout.addWidget(self.status_label)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.clicked.connect(self.analyze_directories)
        buttons_layout.addWidget(self.analyze_button)
        
        self.sync_button = QPushButton("Sync")
        self.sync_button.clicked.connect(self.start_sync)
        buttons_layout.addWidget(self.sync_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_button)
        
        layout.addLayout(buttons_layout)
    
    def browse_source(self):
        """Browse for source directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Source Directory", self.source_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            self.source_dir = directory
            self.source_edit.setText(directory)
    
    def browse_target(self):
        """Browse for target directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Target Directory", self.target_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            self.target_dir = directory
            self.target_edit.setText(directory)
    
    def get_sync_options(self):
        """Get the sync options from the UI controls"""
        options = {}
        
        # Sync mode
        mode_text = self.sync_mode.currentText()
        if "Bidirectional" in mode_text:
            options['sync_mode'] = 'bidirectional'
        elif "One-way" in mode_text:
            options['sync_mode'] = 'one_way'
        elif "Mirror" in mode_text:
            options['sync_mode'] = 'mirror'
            
        # Conflict resolution
        resolution_text = self.conflict_resolution.currentText()
        if "Newer" in resolution_text:
            options['conflict_resolution'] = 'newer'
        elif "Source" in resolution_text:
            options['conflict_resolution'] = 'source'
        elif "Target" in resolution_text:
            options['conflict_resolution'] = 'target'
        elif "Both" in resolution_text:
            options['conflict_resolution'] = 'keep_both'
            
        # File types
        file_types_text = self.file_types.currentText()
        if "Markdown files only" in file_types_text:
            options['file_types'] = ['.md']
        elif "All supported notes files" in file_types_text:
            options['file_types'] = ['.md', '.txt', '.html']
        else:  # All files
            options['file_types'] = []
            
        # Additional options
        options['delete_orphaned'] = self.delete_orphaned.isChecked()
        options['preserve_timestamps'] = self.preserve_timestamps.isChecked()
        options['dry_run'] = self.dry_run.isChecked()
        
        return options
    
    def validate_inputs(self):
        """Validate user inputs before starting sync"""
        if not self.source_dir or not os.path.exists(self.source_dir):
            QMessageBox.warning(self, "Invalid Input", "Please select a valid source directory.")
            return False
            
        if not self.target_dir:
            QMessageBox.warning(self, "Invalid Input", "Please select a target directory.")
            return False
            
        if os.path.normpath(self.source_dir) == os.path.normpath(self.target_dir):
            QMessageBox.warning(self, "Invalid Input", "Source and target directories must be different.")
            return False
            
        return True
    
    def analyze_directories(self):
        """Analyze the directories without performing any changes"""
        if not self.validate_inputs():
            return
            
        # Force dry run mode for analysis
        options = self.get_sync_options()
        options['dry_run'] = True
        
        self.dry_run.setChecked(True)
        self.start_sync()
    
    def start_sync(self):
        """Start the synchronization process"""
        if not self.validate_inputs():
            return
            
        # Get sync options
        options = self.get_sync_options()
        
        # Clear log
        self.log_widget.clear()
        self.log_messages = []
        
        # Reset progress
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting sync...")
        
        # Create and start worker thread
        self.sync_worker = DirectorySyncWorker(
            self.source_dir,
            self.target_dir,
            options
        )
        
        # Connect signals
        self.sync_worker.progress.connect(self.update_progress)
        self.sync_worker.log_message.connect(self.log_message)
        self.sync_worker.sync_completed.connect(self.on_sync_completed)
        
        # Disable controls during sync
        self.set_controls_enabled(False)
        
        # Start the worker
        self.sync_worker.start()
    
    def update_progress(self, value, message):
        """Update the progress bar and status"""
        self.progress_bar.setValue(value)
        if message:
            self.status_label.setText(message)
    
    def log_message(self, message, level="info"):
        """Add a message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_messages.append((log_entry, level))
        
        # Create list item with appropriate color
        item = QListWidgetItem(log_entry)
        if level == "error":
            item.setForeground(Qt.GlobalColor.red)
        elif level == "warning":
            item.setForeground(Qt.GlobalColor.darkYellow)
        
        self.log_widget.addItem(item)
        self.log_widget.scrollToBottom()
    
    def on_sync_completed(self, stats):
        """Handle completion of sync operation"""
        # Re-enable controls
        self.set_controls_enabled(True)
        
        # Display stats
        stats_message = (
            f"Sync completed in {stats['operation_time']:.1f} seconds\n"
            f"- {stats['files_analyzed']} files analyzed\n"
            f"- {stats['files_copied_to_target']} files copied to target\n"
            f"- {stats['files_copied_to_source']} files copied to source\n"
            f"- {stats['files_skipped']} files skipped (identical)\n"
            f"- {stats['conflicts_resolved']} conflicts resolved\n"
            f"- {stats['files_deleted']} files deleted\n"
            f"- {self._format_size(stats['bytes_transferred'])} transferred"
        )
        
        # Add to log
        self.log_message("Sync completed successfully", "info")
        
        # Show completion message
        mode = "Dry run" if self.dry_run.isChecked() else "Sync"
        
        if stats['errors'] > 0:
            self.status_label.setText(f"{mode} completed with {stats['errors']} errors. See log for details.")
            QMessageBox.warning(
                self, 
                f"{mode} Completed with Errors",
                f"{stats_message}\n\n{stats['errors']} errors occurred. Check the log for details."
            )
        else:
            self.status_label.setText(f"{mode} completed successfully.")
            QMessageBox.information(self, f"{mode} Completed", stats_message)
    
    def set_controls_enabled(self, enabled):
        """Enable or disable controls during sync"""
        self.analyze_button.setEnabled(enabled)
        self.sync_button.setEnabled(enabled)
        self.sync_mode.setEnabled(enabled)
        self.conflict_resolution.setEnabled(enabled)
        self.file_types.setEnabled(enabled)
        self.delete_orphaned.setEnabled(enabled)
        self.preserve_timestamps.setEnabled(enabled)
        self.dry_run.setEnabled(enabled)
    
    def _format_size(self, size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.sync_worker and self.sync_worker.isRunning():
            # Ask for confirmation before closing
            confirm = QMessageBox.question(
                self,
                "Sync in Progress",
                "A sync operation is in progress. Are you sure you want to cancel it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if confirm == QMessageBox.StandardButton.Yes:
                # Cancel the worker
                self.sync_worker.cancel()
                self.sync_worker.wait(1000)  # Wait up to 1 second
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

class DirectorySyncManager:
    """Manager for directory synchronization operations"""
    
    def __init__(self, parent=None):
        self.parent = parent
    
    def open_sync_dialog(self, source_dir=None, target_dir=None):
        """Open the sync dialog with optional preset directories"""
        dialog = DirectorySyncDialog(self.parent, source_dir, target_dir)
        dialog.exec()
        
    def quick_sync(self, source_dir, target_dir, options=None):
        """Quickly synchronize two directories with default or provided options"""
        if not options:
            options = {
                'sync_mode': 'bidirectional',
                'conflict_resolution': 'newer',
                'file_types': ['.md'],
                'delete_orphaned': False,
                'preserve_timestamps': True
            }
        
        # Validate directories
        if not os.path.exists(source_dir):
            if self.parent:
                QMessageBox.warning(self.parent, "Sync Error", f"Source directory doesn't exist: {source_dir}")
            return
        
        # Create progress dialog
        progress = QProgressDialog("Synchronizing directories...", "Cancel", 0, 100, self.parent)
        progress.setWindowTitle("Quick Sync")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(0)
        progress.show()
        
        # Create worker
        worker = DirectorySyncWorker(source_dir, target_dir, options)
        
        # Connect signals
        worker.progress.connect(lambda val, msg: progress.setValue(val))
        worker.log_message.connect(lambda msg, level: print(f"[{level}] {msg}"))
        worker.sync_completed.connect(lambda stats: self._on_quick_sync_completed(stats, progress))
        
        # Start the worker
        worker.start()
    
    def _on_quick_sync_completed(self, stats, progress):
        """Handle completion of quick sync"""
        # Close progress dialog
        progress.setValue(100)
        
        if stats['errors'] > 0:
            if self.parent:
                QMessageBox.warning(
                    self.parent,
                    "Sync Completed With Errors",
                    f"Sync completed with {stats['errors']} errors.\n"
                    f"- {stats['files_copied_to_target']} files copied to target\n"
                    f"- {stats['files_copied_to_source']} files copied to source"
                )
        else:
            if self.parent:
                QMessageBox.information(
                    self.parent,
                    "Sync Completed",
                    f"Sync completed successfully.\n"
                    f"- {stats['files_copied_to_target']} files copied to target\n"
                    f"- {stats['files_copied_to_source']} files copied to source"
                )

class DirectorySyncScheduler(QObject):
    """Scheduler for automatic directory synchronization"""
    
    sync_started = pyqtSignal(str, str)  # source_dir, target_dir
    sync_completed = pyqtSignal(str, str, dict)  # source_dir, target_dir, stats
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.sync_tasks = []
        self.active_workers = {}
        self.timer = None
        self.sync_interval = 3600  # Default: 1 hour in seconds
    
    def add_sync_task(self, source_dir, target_dir, options=None, enabled=True):
        """Add a sync task to the scheduler"""
        task_id = f"{source_dir}_{target_dir}".replace('/', '_').replace('\\', '_')
        
        # Check if this task already exists
        for task in self.sync_tasks:
            if task['id'] == task_id:
                # Update existing task
                task['source_dir'] = source_dir
                task['target_dir'] = target_dir
                task['options'] = options or {}
                task['enabled'] = enabled
                task['last_sync'] = task.get('last_sync', None)
                return task_id
        
        # Create new task
        task = {
            'id': task_id,
            'source_dir': source_dir,
            'target_dir': target_dir,
            'options': options or {},
            'enabled': enabled,
            'last_sync': None
        }
        self.sync_tasks.append(task)
        
        # Start timer if this is the first task
        if len(self.sync_tasks) == 1:
            self._start_timer()
            
        return task_id
    
    def remove_sync_task(self, task_id):
        """Remove a sync task from the scheduler"""
        self.sync_tasks = [task for task in self.sync_tasks if task['id'] != task_id]
        
        # Stop timer if no more tasks
        if not self.sync_tasks and self.timer:
            self.timer.stop()
    
    def enable_sync_task(self, task_id, enabled=True):
        """Enable or disable a sync task"""
        for task in self.sync_tasks:
            if task['id'] == task_id:
                task['enabled'] = enabled
                return True
        return False
    
    def set_sync_interval(self, interval_seconds):
        """Set the sync interval in seconds"""
        if interval_seconds < 60:  # Minimum interval: 1 minute
            interval_seconds = 60
            
        self.sync_interval = interval_seconds
        
        # Restart timer if running
        if self.timer and self.timer.isActive():
            self.timer.stop()
            self._start_timer()
    
    def _start_timer(self):
        """Start the sync timer"""
        from PyQt6.QtCore import QTimer
        
        if not self.timer:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._check_sync_tasks)
            
        self.timer.start(60000)  # Check every minute
    
    def _check_sync_tasks(self):
        """Check if any sync tasks need to be executed"""
        current_time = time.time()
        
        for task in self.sync_tasks:
            if not task['enabled']:
                continue
                
            # Skip if already running
            if task['id'] in self.active_workers:
                continue
                
            # Check if it's time to sync
            last_sync = task.get('last_sync', 0)
            if last_sync is None or (current_time - last_sync) >= self.sync_interval:
                self._run_sync_task(task)
    
    def _run_sync_task(self, task):
        """Run a scheduled sync task"""
        source_dir = task['source_dir']
        target_dir = task['target_dir']
        options = task['options']
        
        # Skip if directories don't exist
        if not os.path.exists(source_dir) or not os.path.exists(target_dir):
            return
            
        # Emit signal
        self.sync_started.emit(source_dir, target_dir)
        
        # Create worker
        worker = DirectorySyncWorker(source_dir, target_dir, options)
        
        # Connect signals
        worker.sync_completed.connect(lambda stats: self._on_task_completed(task, stats))
        
        # Store worker
        self.active_workers[task['id']] = worker
        
        # Start the worker
        worker.start()
        
        # Update last sync time
        task['last_sync'] = time.time()
    
    def _on_task_completed(self, task, stats):
        """Handle completion of a sync task"""
        # Remove from active workers
        worker = self.active_workers.pop(task['id'], None)
        
        # Emit signal
        self.sync_completed.emit(task['source_dir'], task['target_dir'], stats)
        
        # Log results
        logging.info(f"Scheduled sync completed for {task['source_dir']} to {task['target_dir']}")
        logging.info(f"- Files copied to target: {stats['files_copied_to_target']}")
        logging.info(f"- Files copied to source: {stats['files_copied_to_source']}")
        logging.info(f"- Errors: {stats['errors']}")
    
    def run_all_tasks_now(self):
        """Force run all enabled sync tasks immediately"""
        for task in self.sync_tasks:
            if task['enabled'] and task['id'] not in self.active_workers:
                self._run_sync_task(task)
    
    def save_tasks(self, config_file=None):
        """Save sync tasks to a configuration file"""
        if not config_file:
            from pathlib import Path
            config_dir = Path.home() / '.config' / 'epy_explorer'
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / 'sync_tasks.json'
            
        # Prepare data for serialization
        tasks_data = []
        for task in self.sync_tasks:
            task_data = {
                'id': task['id'],
                'source_dir': task['source_dir'],
                'target_dir': task['target_dir'],
                'options': task['options'],
                'enabled': task['enabled'],
                # Don't save last_sync time, it will be reset
            }
            tasks_data.append(task_data)
            
        # Save to file
        with open(config_file, 'w', encoding='utf-8') as f:
            import json
            json.dump({
                'tasks': tasks_data,
                'interval': self.sync_interval
            }, f, indent=2)
    
    def load_tasks(self, config_file=None):
        """Load sync tasks from a configuration file"""
        if not config_file:
            from pathlib import Path
            config_file = Path.home() / '.config' / 'epy_explorer' / 'sync_tasks.json'
            
        if not os.path.exists(config_file):
            return False
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                import json
                data = json.load(f)
                
            # Load interval
            if 'interval' in data:
                self.sync_interval = data['interval']
                
            # Load tasks
            self.sync_tasks = []
            for task_data in data.get('tasks', []):
                task = {
                    'id': task_data['id'],
                    'source_dir': task_data['source_dir'],
                    'target_dir': task_data['target_dir'],
                    'options': task_data.get('options', {}),
                    'enabled': task_data.get('enabled', True),
                    'last_sync': None  # Reset last sync time
                }
                self.sync_tasks.append(task)
                
            # Start timer if we have tasks
            if self.sync_tasks:
                self._start_timer()
                
            return True
            
        except Exception as e:
            logging.error(f"Error loading sync tasks: {e}")
            return False 