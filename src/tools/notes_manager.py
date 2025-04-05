import os
import json
import hashlib
import time
import shutil
from datetime import datetime
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QAbstractItemModel, QModelIndex
from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QApplication
from PyQt6.QtCore import Qt

class NotesModel(QObject):
    """Model for representing notes vault data"""
    
    def __init__(self, root_path):
        super().__init__()
        self.root_path = root_path
        self.notes_data = []
        self.tags_map = {}  # Maps tags to file paths
        self.filter_tag = None  # Store current tag filter
        
    def load_from_cache(self, cached_data):
        """Load model from cached data"""
        self.notes_data = cached_data
        self._build_tags_map()
        
    def _build_tags_map(self):
        """Build mapping of tags to file paths"""
        self.tags_map = {}
        for item in self.notes_data:
            if not item.get('is_dir') and 'tags' in item:
                for tag in item.get('tags', []):
                    if tag not in self.tags_map:
                        self.tags_map[tag] = []
                    self.tags_map[tag].append(item['path'])
    
    def get_serializable_data(self):
        """Get data in a format that can be serialized to JSON"""
        return self.notes_data

    def setFilterTag(self, tag):
        """Set the tag to filter notes by"""
        self.filter_tag = tag
        # Emit signal if needed to update views


class NotesLoader(QThread):
    """Background thread for loading notes data"""
    
    progress_update = pyqtSignal(int, str)  # value, message
    finished = pyqtSignal()
    
    def __init__(self, notes_model, directory):
        super().__init__()
        self.notes_model = notes_model
        self.directory = directory
        
    def load_notes(self):
        """Load notes data from directory"""
        try:
            # Scan directory and build model
            notes_data = []
            
            # Report progress: starting
            self.progress_update.emit(20, "Scanning notes vault...")
            
            # Process files and build model data
            self._scan_directory(self.directory, notes_data)
            
            # Update model with data
            self.notes_model.notes_data = notes_data
            self.notes_model._build_tags_map()
            
            # Report progress: finished
            self.progress_update.emit(100, "Notes loaded successfully")
            
            # Emit finished signal
            self.finished.emit()
            
        except Exception as e:
            print(f"Error loading notes: {e}")
            import traceback
            traceback.print_exc()
            self.finished.emit()
    
    def _scan_directory(self, directory, notes_data, parent_path=None):
        """Recursively scan directory for notes"""
        try:
            items = os.listdir(directory)
            
            # Process directories first, then files (for hierarchical structure)
            for name in sorted(items):
                # Skip hidden files and special directories
                if name.startswith('.'):
                    continue
                    
                path = os.path.join(directory, name)
                rel_path = os.path.relpath(path, self.notes_model.root_path)
                
                if os.path.isdir(path):
                    # Add directory to model
                    dir_item = {
                        'path': rel_path,
                        'is_dir': True,
                        'parent_path': parent_path
                    }
                    notes_data.append(dir_item)
                    
                    # Recursively process subdirectory
                    self._scan_directory(path, notes_data, rel_path)
                elif name.lower().endswith('.md'):
                    # Process markdown file
                    stats = os.stat(path)
                    tags = self._extract_tags(path)
                    
                    file_item = {
                        'path': rel_path,
                        'is_dir': False,
                        'mod_time': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                        'tags': tags,
                        'parent_path': parent_path
                    }
                    notes_data.append(file_item)
        
        except Exception as e:
            print(f"Error scanning directory {directory}: {e}")
    
    def _extract_tags(self, file_path):
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


class NotesManager(QObject):
    """Manager for handling notes functionality"""
    
    # Signal emitted when notes are loaded
    notes_loaded = pyqtSignal(object)  # Passes the tree model
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.notes_model = None
        
    def get_config_dir(self):
        """Get the configuration directory, creating it if it doesn't exist"""
        config_dir = os.path.expanduser('~/.config/epy_explorer')
        os.makedirs(config_dir, exist_ok=True)
        return config_dir
        
    def get_notes_vault_path(self):
        """Get the configured notes vault path"""
        try:
            notes_config_path = os.path.join(self.get_config_dir(), 'notes_config.json')
            
            # Log file access for debugging
            print(f"Checking for notes config at: {notes_config_path}")
            
            if os.path.exists(notes_config_path):
                with open(notes_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    vault_path = config.get('vault_path')
                    if vault_path and os.path.exists(vault_path):
                        print(f"Using configured notes vault path: {vault_path}")
                        return vault_path
                    else:
                        print(f"Configured vault path doesn't exist or is not specified")
            else:
                print(f"No notes config found at {notes_config_path}")
                
            # Check for a .eepy_vault file in the home directory that might point to the vault
            home_pointer = os.path.expanduser('~/.eepy_vault')
            if os.path.exists(home_pointer):
                try:
                    with open(home_pointer, 'r') as f:
                        vault_path = f.read().strip()
                        if os.path.exists(vault_path):
                            print(f"Using vault path from .eepy_vault: {vault_path}")
                            return vault_path
                except Exception as e:
                    print(f"Error reading .eepy_vault: {str(e)}")
            
            # Default path is ~/Notes
            default_path = os.path.expanduser('~/Notes')
            
            # Create the default path if it doesn't exist
            if not os.path.exists(default_path):
                try:
                    os.makedirs(default_path, exist_ok=True)
                    print(f"Created default notes path: {default_path}")
                except Exception as e:
                    print(f"Error creating default notes path: {str(e)}")
                    
            print(f"Using default notes vault path: {default_path}")
            return default_path
            
        except Exception as e:
            print(f"Error getting notes vault path: {str(e)}")
            return None

    def compute_directory_hash(self, directory, quick_check=False):
        """Compute a hash representing the state of a directory and its files
        
        Args:
            directory: The directory to compute hash for
            quick_check: If True, uses a faster method that only checks directory structure,
                         not individual file contents
        
        This creates a unique hash based on:
        1. The directory structure (excluding .eepy directory)
        2. File sizes and paths (ignoring modification times which can change without content changing)
        
        Returns:
            str: A hash string that changes when directory content changes
        """
        hasher = hashlib.md5()
        
        try:
            print(f"Computing hash for directory: {directory}")
            
            # Fast mode - just check directory metadata if quick_check is True
            # This is much faster but less accurate - good for checking if a refresh might be needed
            if quick_check:
                # Only scan directory metadata, not individual files
                print("Using quick mode for directory hash")
                dir_list = []
                md_count = 0
                
                for root, dirs, files in os.walk(directory):
                    # Skip ignored directories
                    if any(ignored in root for ignored in ['.eepy', '.obsidian', '.git', '.trash', '.archived', '__pycache__']):
                        continue
                    
                    rel_dir_path = os.path.relpath(root, directory)
                    dir_list.append(rel_dir_path)
                    
                    # Count markdown files for rough check
                    md_files = [f for f in files if f.endswith('.md')]
                    md_count += len(md_files)
                
                # Hash directory structure and file count
                dir_list.sort()
                for d in dir_list:
                    hasher.update(d.encode('utf-8'))
                
                # Add file count as a basic check
                hasher.update(str(md_count).encode('utf-8'))
                
                result = hasher.hexdigest()
                print(f"Quick hash completed with {len(dir_list)} directories and {md_count} markdown files")
                return result
            
            # Optimization: Build a list of files and info before hashing
            md_files = []  # Store tuples of (relative_path, size)
            dir_paths = set()  # Store directory paths
            
            # Start time for performance tracking
            start_time = time.time()
            
            ignored_dirs = ['.eepy', '.obsidian', '.git', '.trash', '.archived', '__pycache__']
            
            # Collect all .md files and directories
            for root, dirs, files in os.walk(directory):
                # Skip hidden and special directories that don't affect content
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ignored_dirs]
                
                # Add directory to the set
                rel_dir_path = os.path.relpath(root, directory)
                if rel_dir_path != '.':  # Skip the root directory itself
                    dir_paths.add(rel_dir_path)
                
                # Process only markdown files
                md_file_count = 0
                for filename in sorted(files):
                    if filename.startswith('.') or not filename.lower().endswith('.md'):
                        continue
                    
                    filepath = os.path.join(root, filename)
                    try:
                        stats = os.stat(filepath)
                        rel_file_path = os.path.relpath(filepath, directory)
                        # Only store path and size, not mtime which can change without content changing
                        md_files.append((rel_file_path, stats.st_size))
                        md_file_count += 1
                    except Exception as e:
                        print(f"Error accessing file {filepath}: {str(e)}")
                
                # Print progress for large directories
                if md_file_count > 0:
                    print(f"Found {md_file_count} markdown files in {rel_dir_path}")
            
            # Sort file and directory lists for deterministic hashing
            md_files.sort()
            dir_paths = sorted(dir_paths)
            
            # Hash directory structure first (just the paths)
            for dir_path in dir_paths:
                hasher.update(dir_path.encode('utf-8'))
            
            # Then hash file information (path and size only)
            for rel_path, size in md_files:
                file_info = f"{rel_path}:{size}"
                hasher.update(file_info.encode('utf-8'))
                
            # Hash the total file count as a way to detect deletions
            hasher.update(str(len(md_files)).encode('utf-8'))
            
            result = hasher.hexdigest()
            
            # Print performance info
            elapsed = time.time() - start_time
            print(f"Hash computation completed in {elapsed:.2f}s")
            print(f"- {len(dir_paths)} directories")
            print(f"- {len(md_files)} markdown files")
            
            return result
        except Exception as e:
            print(f"Error computing directory hash: {str(e)}")
            # Return a fallback hash based on the directory path and current time
            # This ensures we don't keep using a stale cache
            return hashlib.md5(f"{directory}:{time.time()}".encode('utf-8')).hexdigest()

    def ensure_eepy_directory(self, notes_path):
        """Ensure the .eepy directory structure is set up properly in the vault
        
        Creates or verifies:
        - .eepy/ directory in the vault
        - .eepy/README.md with information about what this directory is
        """
        if not os.path.exists(notes_path):
            print(f"Notes path doesn't exist: {notes_path}")
            return None
            
        eepy_dir = os.path.join(notes_path, '.eepy')
        
        # Create the directory if it doesn't exist
        if not os.path.exists(eepy_dir):
            try:
                os.makedirs(eepy_dir, exist_ok=True)
                print(f"Created .eepy directory at {eepy_dir}")
            except Exception as e:
                print(f"Error creating .eepy directory: {str(e)}")
                return None
        
        # Create a README file to explain what this directory is for
        readme_path = os.path.join(eepy_dir, 'README.md')
        if not os.path.exists(readme_path):
            try:
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write("# .eepy Directory\n\n")
                    f.write("This directory contains application data and cache files for the EEPY Explorer application.\n\n")
                    f.write("## Contents\n\n")
                    f.write("- **notes_index.json**: Cache of the notes vault structure and metadata\n")
                    f.write("- **config.json**: Local configuration for the vault\n\n")
                    f.write("You can safely ignore this directory, but don't delete it as it helps improve performance.")
                print(f"Created README file at {readme_path}")
            except Exception as e:
                print(f"Error creating README file: {str(e)}")
                
        return eepy_dir
        
    def save_notes_index(self, notes_data, notes_hash):
        """Save notes index to a cache file"""
        try:
            # Check if notes_data is valid
            if not notes_data or not notes_hash:
                print("No data to save to index")
                return False
                
            # Get path for index file
            notes_path = self.get_notes_vault_path()
            if not notes_path:
                print("No notes vault path configured")
                return False
                
            # Ensure .eepy directory exists
            eepy_dir = self.ensure_eepy_directory(notes_path)
            if not eepy_dir:
                print("Failed to create .eepy directory")
                return False
                
            # Set index file path
            index_path = os.path.join(eepy_dir, 'notes_index.json')
            
            # Convert model data to a serializable structure
            serialized_data = []
            processed_count = 0
            failed_count = 0
            
            for item_data in notes_data:
                try:
                    # Ensure all data is properly serializable
                    serialized_item = {
                        'path': str(item_data.get('path', '')),
                        'is_dir': bool(item_data.get('is_dir', False)),
                        'mod_time': str(item_data.get('mod_time', '')),
                        'tags': list(item_data.get('tags', [])),
                        'parent_path': str(item_data.get('parent_path', ''))
                    }
                    serialized_data.append(serialized_item)
                    processed_count += 1
                except Exception as e:
                    print(f"Error serializing item: {e}")
                    failed_count += 1
            
            # Add hash and timestamp to the index
            index = {
                'hash': notes_hash,
                'timestamp': datetime.now().isoformat(),
                'version': 1,  # Add version field for future compatibility
                'items': serialized_data
            }
            
            # Write to a temporary file first to prevent corruption
            temp_path = index_path + '.temp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)
                
            # Only replace the original if the temp file was written successfully  
            if os.path.exists(temp_path):
                # On Windows, we need to remove the target file first
                if os.path.exists(index_path) and os.name == 'nt':
                    os.remove(index_path)
                os.rename(temp_path, index_path)
                
            print(f"Notes index saved to {index_path}")
            print(f"- Processed: {processed_count} items")
            print(f"- Failed: {failed_count} items")
            print(f"- Hash: {notes_hash[:8]}...")
            return True
            
        except Exception as e:
            print(f"Error saving notes index: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def load_notes_index(self):
        """Load notes index from cache file if it exists"""
        try:
            # Get the notes vault path
            notes_path = self.get_notes_vault_path()
            if not notes_path:
                print("No notes vault path configured")
                return None, None
                
            # Check if .eepy directory exists
            eepy_dir = os.path.join(notes_path, '.eepy')
            if not os.path.exists(eepy_dir):
                print(f"No .eepy directory found at {notes_path}")
                return None, None
                
            # Get index file path
            index_path = os.path.join(eepy_dir, 'notes_index.json')
            if not os.path.exists(index_path):
                print(f"No index file found at {index_path}")
                return None, None
            
            # Load the index file
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
                
            notes_hash = index.get('hash')
            notes_data = index.get('items', [])
            version = index.get('version', 0)
            timestamp = index.get('timestamp', '')
            
            # Basic validation
            if not notes_hash or not notes_data:
                print("Invalid index data (missing hash or items)")
                return None, None
                
            item_count = len(notes_data)
            print(f"Successfully loaded notes index:")
            print(f"- Version: {version}")
            print(f"- Timestamp: {timestamp}")
            print(f"- Items: {item_count}")
            print(f"- Hash: {notes_hash[:8]}...")
            
            return notes_hash, notes_data
            
        except Exception as e:
            print(f"Error loading notes index: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None
            
    def setup_notes_mode(self, parent=None, fast_mode=True):
        """Set up notes mode for the explorer
        
        Args:
            parent: The parent explorer widget
            fast_mode: If True, tries to reuse the existing model when possible
            
        Returns:
            NotesTreeModel or None: The model if already available, or None if loading in background
        """
        try:
            print("--- Notes Mode Setup ---")
            
            # Get the notes vault path
            notes_path = self.get_notes_vault_path()
            if not notes_path:
                print("No notes vault path configured")
                return None
            
            print(f"Notes vault path: {notes_path}")
            
            # Create a progress dialog in the parent
            if parent:
                parent.progress_dialog = QProgressDialog("Loading notes...", "Cancel", 0, 100, parent)
                parent.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                parent.progress_dialog.setMinimumDuration(500)  # Don't show for quick operations
                parent.progress_dialog.setValue(10)
                parent.progress_dialog.show()  # Explicitly show the dialog
                progress = parent.progress_dialog
            else:
                progress = None
            
            # Check if we already have a valid loaded model
            if fast_mode and hasattr(self, 'notes_tree_model') and self.notes_tree_model:
                if progress:
                    progress.setValue(100)
                    progress.close()
                print("Using existing notes model (fast mode)")
                
                # Re-emit notes_loaded signal to update the UI
                self.notes_loaded.emit(self.notes_tree_model)
                return self.notes_tree_model
            
            # Calculate a hash of the directory (for caching)
            # Use quick check for initial comparison
            curr_hash = self.compute_directory_hash(notes_path, quick_check=True)
            
            # Try to load from cache first
            if fast_mode:
                self.update_load_progress(progress, 20, "Checking notes cache...")
                cached_hash, cached_data = self.load_notes_index()
                
                if cached_hash and cached_data:
                    # If the hash matches, use the cached data
                    if cached_hash == curr_hash:
                        print(f"Using cached notes index (hash: {cached_hash[:8]}...)")
                        
                        # Create the model using cached data
                        self.notes_model = NotesModel(notes_path)
                        self.notes_model.load_from_cache(cached_data)
                        self.notes_tree_model = NotesTreeModel(self.notes_model, parent)
                        
                        # Update progress
                        self.update_load_progress(progress, 100, "Notes loaded from cache")
                        
                        # Emit signal that model is ready
                        self.notes_loaded.emit(self.notes_tree_model)
                        print("Notes loaded from cache")
                        
                        # Close progress dialog
                        if progress and not progress.wasCanceled():
                            progress.close()
                        
                        return self.notes_tree_model
                    else:
                        # Verify with a full hash calculation 
                        full_hash = self.compute_directory_hash(notes_path)
                        if cached_hash == full_hash:
                            print(f"Using cached notes index (full hash: {full_hash[:8]}...)")
                            
                            # Create the model using cached data
                            self.notes_model = NotesModel(notes_path)
                            self.notes_model.load_from_cache(cached_data)
                            self.notes_tree_model = NotesTreeModel(self.notes_model, parent)
                            
                            # Update progress
                            self.update_load_progress(progress, 100, "Notes loaded from cache")
                            
                            # Emit signal that model is ready
                            self.notes_loaded.emit(self.notes_tree_model)
                            print("Notes loaded from cache")
                            
                            # Close progress dialog
                            if progress and not progress.wasCanceled():
                                progress.close()
                            
                            return self.notes_tree_model
            
            # If we got here, we need to load notes from scratch
            self.update_load_progress(progress, 30, "Loading notes from files...")
            
            # Create the model
            self.notes_model = NotesModel(notes_path)
            
            # Create and configure loader thread
            self.load_thread = QThread()
            self.load_worker = NotesLoader(self.notes_model, notes_path)
            self.load_worker.moveToThread(self.load_thread)
            
            # Connect signals
            self.load_thread.started.connect(self.load_worker.load_notes)
            self.load_worker.progress_update.connect(
                lambda val, msg: self.update_load_progress(progress, val, msg)
            )
            self.load_worker.finished.connect(
                lambda: self.on_notes_loaded(curr_hash, parent)
            )
            self.load_worker.finished.connect(self.load_worker.deleteLater)
            self.load_thread.finished.connect(self.load_thread.deleteLater)
            
            # Start loading in background
            self.load_thread.start()
            print("Started notes loading in background thread")
            
            # Return None initially, the model will be built in the background
            return None
            
        except Exception as e:
            print(f"Error setting up notes mode: {str(e)}")
            import traceback
            traceback.print_exc()
            if progress:
                progress.cancel()
            if parent:
                QMessageBox.critical(parent, "Error", f"Failed to load notes vault:\n{str(e)}")
            return None

    def update_load_progress(self, progress, value, message):
        """Update the progress dialog during notes loading"""
        if progress and not progress.wasCanceled():
            progress.setValue(value)
            if message:
                progress.setLabelText(message)
            QApplication.processEvents()
            
    def on_notes_loaded(self, notes_hash, parent=None):
        """Called when notes loading is complete"""
        try:
            print("Notes loading finished")
            
            # Save the notes index
            if hasattr(self, 'notes_model') and self.notes_model:
                # Get serializable data from model
                notes_data = self.notes_model.get_serializable_data()
                
                # Save to cache
                self.save_notes_index(notes_data, notes_hash)
                
                # Create tree model
                self.notes_tree_model = NotesTreeModel(self.notes_model, parent)
                
                # Emit signal that model is ready
                self.notes_loaded.emit(self.notes_tree_model)
                
                print("--- Notes Mode Setup Complete ---")
                
                return self.notes_tree_model
                
        except Exception as e:
            print(f"Error in on_notes_loaded: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def refresh_notes(self, parent=None, force=False, specific_file=None):
        """Refresh notes after a file has been edited
        
        Args:
            parent: The parent widget (typically explorer)
            force: If True, forces a full refresh regardless of hash
            specific_file: If provided, only update this specific file's metadata
        """
        try:
            # Get the notes vault path
            notes_path = self.get_notes_vault_path()
            if not notes_path or not os.path.exists(notes_path):
                print(f"Notes path does not exist: {notes_path}")
                return
            
            # Handle specific file update (more efficient for tag changes)
            if specific_file and os.path.exists(specific_file):
                print(f"Updating specific file: {specific_file}")
                if hasattr(self, 'notes_model') and hasattr(self.notes_model, 'tags_map'):
                    # Extract tags from the file
                    tags = self._extract_tags_from_file(specific_file)
                    
                    # Update tags in the model
                    rel_path = os.path.relpath(specific_file, notes_path) if os.path.isabs(specific_file) else specific_file
                    
                    # Remove the file from its previous tags
                    for tag_list in self.notes_model.tags_map.values():
                        if rel_path in tag_list:
                            tag_list.remove(rel_path)
                    
                    # Add the file to its new tags
                    for tag in tags:
                        if tag not in self.notes_model.tags_map:
                            self.notes_model.tags_map[tag] = []
                        if rel_path not in self.notes_model.tags_map[tag]:
                            self.notes_model.tags_map[tag].append(rel_path)
                    
                    # Update the tree model
                    if hasattr(self, 'notes_tree_model'):
                        # Find the item index in the tree model
                        node_index = self.notes_tree_model.get_item_by_path(rel_path)
                        if node_index and node_index.isValid():
                            # Get the node and update its tags
                            node = node_index.internalPointer()
                            if node and node.data:
                                # Update the node's tags directly
                                node.data['tags'] = tags
                                
                                # Get the tag column index
                                tag_column_index = self.notes_tree_model.index(node_index.row(), 1, node_index.parent())
                                # Emit dataChanged for this specific cell
                                self.notes_tree_model.dataChanged.emit(tag_column_index, tag_column_index)
                        else:
                            # If we can't find the exact item, refresh the whole model
                            self.notes_tree_model.dataChanged.emit(QModelIndex(), QModelIndex())
                    
                    # Update any UI elements if parent is provided
                    if parent and hasattr(parent, 'update_tags_list'):
                        parent.update_tags_list()
                    
                    print(f"Updated tags for {os.path.basename(specific_file)}")
                    return
            
            # Skip hash check if force is True
            if force:
                print("Forcing notes refresh...")
                # Force a reload of notes
                self.setup_notes_mode(parent)
                return
            
            # Do a quick hash check first to see if anything might have changed
            quick_hash = self.compute_directory_hash(notes_path, quick_check=True)
            
            # Get cached hash
            cached_hash, cached_data = self.load_notes_index()
            
            if cached_hash and cached_hash == quick_hash:
                # No changes detected with quick hash, no need to refresh
                print("No changes to notes detected")
                return
            
            print("Changes detected in quick hash check, performing full check...")
            
            # Do a full hash calculation to confirm changes
            current_hash = self.compute_directory_hash(notes_path)
            
            if cached_hash and cached_hash == current_hash:
                # No changes, just return
                print("No changes to notes detected in full hash check")
                return
            
            print(f"Notes have changed, refreshing...")
            
            # Update progress dialog if it exists
            if parent and hasattr(parent, 'progress_dialog'):
                parent.progress_dialog.setLabelText("Refreshing notes index...")
                parent.progress_dialog.setValue(10)
            
            # Force a reload of notes
            self.setup_notes_mode(parent)
            
        except Exception as e:
            print(f"Error refreshing notes: {e}")
            import traceback
            traceback.print_exc()

    def _extract_tags_from_file(self, file_path):
        """Extract tags from a markdown file's frontmatter"""
        try:
            # If we have a notes loader, use its method
            if hasattr(self, 'load_worker') and hasattr(self.load_worker, '_extract_tags'):
                return self.load_worker._extract_tags(file_path)
                
            # Otherwise, implement the same logic here
            tags = []
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
            return tags
                
        except Exception as e:
            print(f"Error extracting tags from {file_path}: {e}")
            return []

    def show_sort_dialog(self, parent=None):
        """Open the sort notes dialog"""
        try:
            from ..widgets.sort_dialog import SortDialog
            dialog = SortDialog(parent)
            dialog.exec()
        except ImportError as e:
            print(f"Error importing sort dialog: {e}")
            if parent:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(parent, "Error", "Sort dialog module not available")
                
    def search_notes_content(self, parent=None):
        """Search across notes content"""
        try:
            from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
            
            if parent is None:
                print("Parent widget required for dialog")
                return
                
            # Get search term from user
            search_term, ok = QInputDialog.getText(
                parent,
                "Search Notes",
                "Enter search term:",
                QLineEdit.EchoMode.Normal
            )
            
            if not ok or not search_term:
                return
                
            # Get the notes vault path
            notes_path = self.get_notes_vault_path()
            if not notes_path:
                QMessageBox.warning(parent, "Error", "Notes vault path not available")
                return
                
            # TODO: Implement proper search UI
            # For now, just use a simple message
            QMessageBox.information(parent, "Search", f"Searching for: {search_term}")
            
            # Open a simple search results dialog in the future
            
        except Exception as e:
            print(f"Error searching notes: {e}")
            if parent:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(parent, "Error", f"Error searching notes: {str(e)}")
    
    def manage_tags(self, parent=None):
        """Manage notes tags"""
        try:
            # TODO: Implement tag management UI
            if parent:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(parent, "Tags", "Tag management will be implemented in a future update")
        except Exception as e:
            print(f"Error in tag management: {e}")
            if parent:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(parent, "Error", f"Error in tag management: {str(e)}")
                
    def create_new_note(self, parent=None):
        """Create a new note in the notes vault"""
        try:
            from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
            import os
            from datetime import datetime
            
            if parent is None:
                print("Parent widget required for dialog")
                return
                
            # Get the notes vault path
            notes_path = self.get_notes_vault_path()
            if not notes_path:
                QMessageBox.warning(parent, "Error", "Notes vault path not available")
                return
                
            # Get note title from user
            title, ok = QInputDialog.getText(
                parent,
                "Create New Note",
                "Enter note title:",
                QLineEdit.EchoMode.Normal
            )
            
            if not ok or not title:
                return
                
            # Sanitize title for filename
            filename = title.replace('/', '-').replace('\\', '-')
            if not filename.endswith('.md'):
                filename += '.md'
                
            filepath = os.path.join(notes_path, filename)
            
            # Check if file already exists
            if os.path.exists(filepath):
                if QMessageBox.question(
                    parent, 
                    "File Exists",
                    f"A note with title '{title}' already exists. Overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) != QMessageBox.StandardButton.Yes:
                    return
            
            # Create note with default template
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"""---
title: {title}
created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
tags: []
---

# {title}

"""
                )
                
            QMessageBox.information(parent, "Note Created", f"Created note: {title}")
            
            # Refresh notes view
            self.refresh_notes(parent, force=True)
            
            # Open the new note for editing if explorer has that capability
            if hasattr(parent, 'open_in_internal_editor'):
                parent.open_in_internal_editor(filepath)
            
        except Exception as e:
            print(f"Error creating note: {e}")
            if parent:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(parent, "Error", f"Error creating note: {str(e)}")
                
    def find_duplicate_notes(self, parent=None):
        """Find and manage duplicate notes"""
        try:
            # Use the more feature-rich notes duplicate dialog
            from ..widgets.notes_duplicate_dialog import NotesDuplicateDialog
            
            dialog = NotesDuplicateDialog(parent)
            notes_path = self.get_notes_vault_path()
            if notes_path:
                dialog.scan_directory(notes_path)
                dialog.exec()
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(parent, "Error", "No notes vault path configured.")
                
        except Exception as e:
            print(f"Error finding duplicate notes: {e}")
            if parent:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(parent, "Error", f"Error finding duplicate notes: {str(e)}")

class NotesTreeModel(QAbstractItemModel):
    """Model for displaying notes in a tree structure"""
    
    def __init__(self, notes_model, parent=None):
        super().__init__(parent)
        self.notes_model = notes_model
        self.filter_tag = None  # Store the current tag filter
        self._build_tree()
        
    def _build_tree(self):
        """Build the tree structure from notes data"""
        # Create root node
        self.root_node = TreeNode(None, None)
        
        # Create lookup for quick parent finding
        self.node_lookup = {}
        
        # Sort items by path depth so parents are processed before children
        items = sorted(self.notes_model.notes_data, key=lambda x: len(x['path'].split('/')))
        
        # Add all directory items first
        for item in [i for i in items if i['is_dir']]:
            parent_path = item.get('parent_path')
            parent_node = self._find_parent_node(parent_path)
            
            # Create node
            node = TreeNode(item, parent_node)
            parent_node.children.append(node)
            
            # Add to lookup
            self.node_lookup[item['path']] = node
            
        # Add all file items next
        for item in [i for i in items if not i['is_dir']]:
            parent_path = item.get('parent_path', '')
            parent_node = self._find_parent_node(parent_path)
            
            # Create node
            node = TreeNode(item, parent_node)
            parent_node.children.append(node)
            
            # Add to lookup
            self.node_lookup[item['path']] = node
            
    def _find_parent_node(self, parent_path):
        """Find the parent node for a given path"""
        if not parent_path:
            return self.root_node
            
        if parent_path in self.node_lookup:
            return self.node_lookup[parent_path]
            
        return self.root_node
        
    def index(self, row, column, parent=QModelIndex()):
        """Return the index of the item in the model"""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
            
        if not parent.isValid():
            parent_node = self.root_node
        else:
            parent_node = parent.internalPointer()
            
        if row < len(parent_node.children):
            child_node = parent_node.children[row]
            return self.createIndex(row, column, child_node)
        
        return QModelIndex()
        
    def parent(self, index):
        """Return the parent of the model item"""
        if not index.isValid():
            return QModelIndex()
            
        child_node = index.internalPointer()
        parent_node = child_node.parent
        
        if parent_node == self.root_node:
            return QModelIndex()
            
        # Find the row of the parent node in its parent's children
        if parent_node.parent:
            row = parent_node.parent.children.index(parent_node)
        else:
            row = 0
            
        return self.createIndex(row, 0, parent_node)
        
    def rowCount(self, parent=QModelIndex()):
        """Return the number of rows under the given parent"""
        if parent.column() > 0:
            return 0
            
        if not parent.isValid():
            parent_node = self.root_node
        else:
            parent_node = parent.internalPointer()
            
        return len(parent_node.children)
        
    def columnCount(self, parent=QModelIndex()):
        """Return the number of columns"""
        return 3  # Filename, Tags, Path
        
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return the data for the given role"""
        if not index.isValid():
            return None
            
        node = index.internalPointer()
        if not node or not node.data:
            return None
            
        item = node.data
        
        # Handle visibility based on tag filter
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.ToolTipRole:
            # If we have a tag filter and this is a file, check if it should be shown
            if self.filter_tag and self.filter_tag != "all" and not item.get('is_dir', False):
                # If the item doesn't have the tag, return None to hide it
                if 'tags' not in item or self.filter_tag not in item['tags']:
                    if role == Qt.ItemDataRole.DisplayRole:
                        # Still return data for column 0 so we can expand/collapse folders
                        if index.column() == 0:
                            pass  # Continue to return data
                        else:
                            # For other columns, hide the data
                            return None
        
        if role == Qt.ItemDataRole.DisplayRole:
            column = index.column()
            
            if column == 0:
                # For directories, return the last part of the path
                if item.get('is_dir', False):
                    path_parts = item['path'].split('/')
                    return path_parts[-1] if path_parts else item['path']
                else:
                    # For files, return filename without extension
                    path_parts = item['path'].split('/')
                    filename = path_parts[-1] if path_parts else item['path']
                    if filename.lower().endswith('.md'):
                        return filename[:-3]
                    return filename
            elif column == 1:
                # Tags column
                if not item.get('is_dir', False) and 'tags' in item:
                    return ", ".join(item['tags'])
                return ""
            elif column == 2:
                # Path column
                return item.get('path', '')
                
        elif role == Qt.ItemDataRole.ToolTipRole:
            # Include tags in tooltip if available
            tooltip = item.get('path', '')
            if not item.get('is_dir', False) and 'tags' in item:
                tags = ", ".join(item['tags'])
                if tags:
                    tooltip += f"\nTags: {tags}"
            return tooltip
            
        elif role == Qt.ItemDataRole.UserRole:
            # For UserRole, return the path string instead of dict to prevent errors
            return item.get('path', '')
            
        return None
        
    def flags(self, index):
        """Return the item flags"""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
            
        node = index.internalPointer()
        if not node or not node.data:
            return Qt.ItemFlag.NoItemFlags
            
        item = node.data
        
        # Check if the item should be enabled based on tag filter
        if self.filter_tag and self.filter_tag != "all" and not item.get('is_dir', False):
            if 'tags' not in item or self.filter_tag not in item['tags']:
                # Keep directories enabled but disable files that don't match the filter
                if not item.get('is_dir', False):
                    return Qt.ItemFlag.ItemIsEnabled
        
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
        
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        """Return the header data"""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 0:
                return "Name"
            elif section == 1:
                return "Tags"
            elif section == 2:
                return "Path"
            
        return None
        
    def get_item_by_path(self, path):
        """Get the index for an item by its path"""
        # Try direct lookup
        if hasattr(self, 'node_lookup') and path in self.node_lookup:
            node = self.node_lookup[path]
            if node.parent:
                try:
                    row = node.parent.children.index(node)
                    return self.createIndex(row, 0, node)
                except ValueError:
                    # Child not in parent's children list
                    print(f"Node for {path} found in lookup but not in parent's children")
                    return QModelIndex()
            else:
                # Root item
                return QModelIndex()
        
        # Try case-insensitive search if exact match fails
        if hasattr(self, 'node_lookup'):
            path_lower = path.lower()
            for known_path, node in self.node_lookup.items():
                if known_path.lower() == path_lower and node.parent:
                    try:
                        row = node.parent.children.index(node)
                        return self.createIndex(row, 0, node)
                    except ValueError:
                        continue
        
        # Debug info
        print(f"Item not found for path: {path}")
        return QModelIndex()

    def get_index_for_path(self, path):
        """Get the model index for a given path, with more robust path handling
        
        This method is designed to find the index for a path, even if the exact path
        isn't in the node lookup (for example, if the path uses different path separators
        or has trailing slashes).
        """
        print(f"DEBUG: Looking for index for path: {path}")
        
        # Always return an invalid index for root path in notes mode
        # This ensures the tree shows the top level of the vault
        return QModelIndex()

    def setFilterTag(self, tag):
        """Set the tag to filter notes by"""
        self.filter_tag = tag
        self.layoutChanged.emit()  # Notify views that the data has changed

class TreeNode:
    """Node in the notes tree model"""
    
    def __init__(self, data, parent=None):
        self.data = data
        self.parent = parent
        self.children = [] 