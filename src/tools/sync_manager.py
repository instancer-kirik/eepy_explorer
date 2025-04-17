import os
import shutil
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QComboBox, QCheckBox, QProgressBar,
                           QMessageBox, QFileDialog, QRadioButton, QGroupBox,
                           QListWidget, QListWidgetItem, QSplitter, QTableWidget,
                           QTableWidgetItem, QHeaderView, QDialogButtonBox,
                           QApplication, QButtonGroup)
from PyQt6.QtCore import Qt

from ..utils.utils import compute_file_hash

# Configure logger
logger = logging.getLogger(__name__)

class SyncWorker(QThread):
    """Worker thread for synchronizing directories"""
    progress = pyqtSignal(int, int, str)  # Current, Total, Message
    finished = pyqtSignal(dict)  # Results dictionary
    error = pyqtSignal(str)  # Error message
    
    def __init__(self, source_dir, target_dir, sync_options=None):
        super().__init__()
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.sync_options = sync_options or {}
        self.should_stop = False
        
    def run(self):
        """Run the synchronization process"""
        try:
            # Default options if not provided
            options = {
                'sync_mode': self.sync_options.get('sync_mode', 'two_way'),
                'handle_conflicts': self.sync_options.get('handle_conflicts', 'newer'),
                'delete_orphaned': self.sync_options.get('delete_orphaned', False),
                'create_backups': self.sync_options.get('create_backups', True),
                'file_types': self.sync_options.get('file_types', ['.md']),
                'skip_patterns': self.sync_options.get('skip_patterns', ['.obsidian', '.git', '.trash']),
                'sync_tags': self.sync_options.get('sync_tags', True),
                'dry_run': self.sync_options.get('dry_run', False),
            }
            
            # Perform the sync based on mode
            if options['sync_mode'] == 'two_way':
                results = self.sync_two_way(options)
            elif options['sync_mode'] == 'mirror':
                results = self.sync_mirror(options)
            elif options['sync_mode'] == 'one_way_source_to_target':
                results = self.sync_one_way(self.source_dir, self.target_dir, options)
            elif options['sync_mode'] == 'one_way_target_to_source':
                results = self.sync_one_way(self.target_dir, self.source_dir, options)
            else:
                self.error.emit(f"Unknown sync mode: {options['sync_mode']}")
                return
                
            self.finished.emit(results)
            
        except Exception as e:
            import traceback
            error_msg = f"Error during synchronization: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.error.emit(error_msg)
    
    def stop(self):
        """Stop the synchronization process"""
        self.should_stop = True
        
    def sync_two_way(self, options):
        """Perform two-way synchronization between directories"""
        results = {
            'created': [],
            'updated': [],
            'deleted': [],
            'conflicts': [],
            'skipped': [],
            'errors': []
        }
        
        # Scan both directories
        source_files = self.scan_directory(self.source_dir, options)
        target_files = self.scan_directory(self.target_dir, options)
        
        total_files = len(source_files) + len(target_files)
        processed = 0
        
        # Process files in source that need to be synced to target
        for rel_path, source_info in source_files.items():
            if self.should_stop:
                break
                
            processed += 1
            self.progress.emit(processed, total_files, f"Processing {rel_path}")
            
            # If file exists in target, compare them
            if rel_path in target_files:
                target_info = target_files[rel_path]
                
                # Check if files are identical
                if source_info['hash'] == target_info['hash']:
                    continue  # Files are identical, no action needed
                
                # Handle conflict based on strategy
                if options['handle_conflicts'] == 'newer':
                    # Use the newer file
                    if source_info['mtime'] > target_info['mtime']:
                        self.sync_file(source_info['path'], target_info['path'], options, results)
                    else:
                        self.sync_file(target_info['path'], source_info['path'], options, results)
                elif options['handle_conflicts'] == 'source':
                    # Source always wins
                    self.sync_file(source_info['path'], target_info['path'], options, results)
                elif options['handle_conflicts'] == 'target':
                    # Target always wins
                    self.sync_file(target_info['path'], source_info['path'], options, results)
                elif options['handle_conflicts'] == 'larger':
                    # Use the larger file
                    if source_info['size'] > target_info['size']:
                        self.sync_file(source_info['path'], target_info['path'], options, results)
                    else:
                        self.sync_file(target_info['path'], source_info['path'], options, results)
                elif options['handle_conflicts'] == 'skip':
                    # Skip conflicts
                    results['conflicts'].append({
                        'source': source_info['path'],
                        'target': target_info['path'],
                        'reason': 'Content differs'
                    })
                    results['skipped'].append(rel_path)
                    
                # Mark as processed in target files
                target_files.pop(rel_path)
            else:
                # File doesn't exist in target, copy it
                target_path = os.path.join(self.target_dir, rel_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                if not options['dry_run']:
                    try:
                        shutil.copy2(source_info['path'], target_path)
                        results['created'].append(target_path)
                    except Exception as e:
                        results['errors'].append({
                            'path': target_path,
                            'error': str(e),
                            'operation': 'create'
                        })
        
        # Now process remaining files in target (ones not in source)
        for rel_path, target_info in target_files.items():
            if self.should_stop:
                break
                
            processed += 1
            self.progress.emit(processed, total_files, f"Processing {rel_path}")
            
            # File exists in target but not in source
            source_path = os.path.join(self.source_dir, rel_path)
            os.makedirs(os.path.dirname(source_path), exist_ok=True)
            
            # In two-way sync, we need to copy to source
            if not options['dry_run']:
                try:
                    shutil.copy2(target_info['path'], source_path)
                    results['created'].append(source_path)
                except Exception as e:
                    results['errors'].append({
                        'path': source_path,
                        'error': str(e),
                        'operation': 'create'
                    })
        
        return results
        
    def sync_mirror(self, options):
        """Make target directory a mirror of source"""
        results = {
            'created': [],
            'updated': [],
            'deleted': [],
            'conflicts': [],
            'skipped': [],
            'errors': []
        }
        
        # Scan both directories
        source_files = self.scan_directory(self.source_dir, options)
        target_files = self.scan_directory(self.target_dir, options)
        
        total_files = len(source_files) + len(target_files)
        processed = 0
        
        # Process files in source that need to be synced to target
        for rel_path, source_info in source_files.items():
            if self.should_stop:
                break
                
            processed += 1
            self.progress.emit(processed, total_files, f"Processing {rel_path}")
            
            # If file exists in target, compare them
            if rel_path in target_files:
                target_info = target_files[rel_path]
                
                # Check if files are identical
                if source_info['hash'] == target_info['hash']:
                    continue  # Files are identical, no action needed
                
                # In mirror mode, source always wins
                self.sync_file(source_info['path'], target_info['path'], options, results)
                    
                # Mark as processed in target files
                target_files.pop(rel_path)
            else:
                # File doesn't exist in target, copy it
                target_path = os.path.join(self.target_dir, rel_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                if not options['dry_run']:
                    try:
                        shutil.copy2(source_info['path'], target_path)
                        results['created'].append(target_path)
                    except Exception as e:
                        results['errors'].append({
                            'path': target_path,
                            'error': str(e),
                            'operation': 'create'
                        })
        
        # In mirror mode, delete files in target that don't exist in source
        if options['delete_orphaned']:
            for rel_path, target_info in target_files.items():
                if self.should_stop:
                    break
                
                processed += 1
                self.progress.emit(processed, total_files, f"Processing {rel_path}")
                
                # Create backup if needed
                if options['create_backups'] and not options['dry_run']:
                    self.create_backup(target_info['path'])
                
                # Delete from target
                if not options['dry_run']:
                    try:
                        os.remove(target_info['path'])
                        results['deleted'].append(target_info['path'])
                    except Exception as e:
                        results['errors'].append({
                            'path': target_info['path'],
                            'error': str(e),
                            'operation': 'delete'
                        })
        
        return results
        
    def sync_one_way(self, source_dir, target_dir, options):
        """Perform one-way synchronization from source to target"""
        results = {
            'created': [],
            'updated': [],
            'deleted': [],
            'conflicts': [],
            'skipped': [],
            'errors': []
        }
        
        # Scan both directories
        source_files = self.scan_directory(source_dir, options)
        target_files = self.scan_directory(target_dir, options)
        
        total_files = len(source_files)
        processed = 0
        
        # Process files in source that need to be synced to target
        for rel_path, source_info in source_files.items():
            if self.should_stop:
                break
                
            processed += 1
            self.progress.emit(processed, total_files, f"Processing {rel_path}")
            
            # If file exists in target, compare them
            if rel_path in target_files:
                target_info = target_files[rel_path]
                
                # Check if files are identical
                if source_info['hash'] == target_info['hash']:
                    continue  # Files are identical, no action needed
                
                # In one-way mode, source always wins
                self.sync_file(source_info['path'], target_info['path'], options, results)
            else:
                # File doesn't exist in target, copy it
                target_path = os.path.join(target_dir, rel_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                if not options['dry_run']:
                    try:
                        shutil.copy2(source_info['path'], target_path)
                        results['created'].append(target_path)
                    except Exception as e:
                        results['errors'].append({
                            'path': target_path,
                            'error': str(e),
                            'operation': 'create'
                        })
        
        # In one-way mode with delete_orphaned, remove files in target that don't exist in source
        if options['delete_orphaned']:
            for rel_path, target_info in target_files.items():
                if rel_path not in source_files:
                    if self.should_stop:
                        break
                    
                    # Create backup if needed
                    if options['create_backups'] and not options['dry_run']:
                        self.create_backup(target_info['path'])
                    
                    # Delete from target
                    if not options['dry_run']:
                        try:
                            os.remove(target_info['path'])
                            results['deleted'].append(target_info['path'])
                        except Exception as e:
                            results['errors'].append({
                                'path': target_info['path'],
                                'error': str(e),
                                'operation': 'delete'
                            })
        
        return results

    def scan_directory(self, directory, options):
        """Scan a directory and return a dictionary of files with metadata
        
        Returns:
            dict: Dictionary with relative paths as keys and file info as values
        """
        files = {}
        
        for root, dirs, filenames in os.walk(directory):
            # Skip directories in the skip patterns
            dirs[:] = [d for d in dirs if not any(pattern in d for pattern in options['skip_patterns'])]
            
            for filename in filenames:
                # Skip files that don't match file types filter
                if options['file_types'] and not any(filename.lower().endswith(ext) for ext in options['file_types']):
                    continue
                
                # Get absolute and relative paths
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, directory)
                
                # Skip if path contains any patterns to skip
                if any(pattern in rel_path for pattern in options['skip_patterns']):
                    continue
                
                try:
                    # Get file stats
                    stats = os.stat(abs_path)
                    
                    # Create file info
                    file_info = {
                        'path': abs_path,
                        'rel_path': rel_path,
                        'size': stats.st_size,
                        'mtime': stats.st_mtime,
                        'hash': self.get_file_hash(abs_path)
                    }
                    
                    files[rel_path] = file_info
                except Exception as e:
                    logger.error(f"Error processing file {abs_path}: {e}")
        
        return files
    
    def get_file_hash(self, file_path):
        """Get a hash of the file contents"""
        try:
            return compute_file_hash(file_path, quick=False, algorithm="md5")
        except Exception as e:
            logger.error(f"Error computing hash for {file_path}: {e}")
            return None
    
    def sync_file(self, source_path, target_path, options, results):
        """Sync a file from source to target"""
        # Create backup if needed
        if options['create_backups'] and not options['dry_run']:
            self.create_backup(target_path)
        
        if not options['dry_run']:
            try:
                # Copy file
                shutil.copy2(source_path, target_path)
                results['updated'].append(target_path)
                
                # Sync tags if needed and it's a markdown file
                if options['sync_tags'] and target_path.lower().endswith('.md') and source_path.lower().endswith('.md'):
                    self.sync_file_tags(source_path, target_path, results)
            except Exception as e:
                results['errors'].append({
                    'path': target_path,
                    'error': str(e),
                    'operation': 'update'
                })
    
    def create_backup(self, file_path):
        """Create a backup of a file"""
        if not os.path.exists(file_path):
            return
            
        # Create backup directory if it doesn't exist
        backup_dir = os.path.join(os.path.dirname(file_path), '.eepy', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create backup filename with timestamp
        filename = os.path.basename(file_path)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        backup_filename = f"{filename}.{timestamp}.bak"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy file to backup
        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup for {file_path}: {e}")
            return None
    
    def sync_file_tags(self, source_path, target_path, results):
        """Sync tags from source to target file"""
        try:
            # Extract tags from source
            source_tags = self.extract_tags(source_path)
            
            # If no tags, nothing to sync
            if not source_tags:
                return
            
            # Read target file
            with open(target_path, 'r', encoding='utf-8') as f:
                target_content = f.read()
            
            # Extract YAML frontmatter from target
            target_yaml, target_body = self.extract_yaml_and_body(target_content)
            
            # Update tags in target YAML
            if target_yaml:
                # Parse target YAML to find tags
                updated_yaml = self.update_yaml_tags(target_yaml, source_tags)
                
                # Reconstruct file with updated YAML
                updated_content = f"---\n{updated_yaml}\n---\n{target_body}"
                
                # Write updated file
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
            else:
                # If target has no YAML frontmatter, we could add one or leave as is
                # For now, leave as is to avoid altering the file structure too much
                pass
                
        except Exception as e:
            logger.error(f"Error syncing tags for {target_path}: {e}")
    
    def extract_tags(self, file_path):
        """Extract tags from a markdown file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            yaml_text, _ = self.extract_yaml_and_body(content)
            if not yaml_text:
                return []
                
            # Look for tags in YAML
            tags = []
            in_tags_section = False
            
            for line in yaml_text.split('\n'):
                line = line.strip()
                
                # Direct tags definition (tags: [tag1, tag2])
                if line.startswith('tags:'):
                    if '[' in line and ']' in line:
                        # Extract tags from array format
                        tag_str = line[line.find('[')+1:line.find(']')]
                        tags.extend([t.strip().strip('"\'') for t in tag_str.split(',')])
                        continue
                    elif len(line) > 5:  # tags: has more text
                        # Format: tags: tag1 tag2
                        tag_str = line[5:].strip()
                        tags.extend([t.strip().strip('"\'') for t in tag_str.split()])
                        continue
                    else:
                        # Format: tags:
                        #   - tag1
                        #   - tag2
                        in_tags_section = True
                        continue
                
                # Handle list items in tags section
                if in_tags_section and line.startswith('-'):
                    tag = line[1:].strip().strip('"\'')
                    if tag:
                        tags.append(tag)
                elif in_tags_section and line and not line.startswith('-'):
                    # End of tags section
                    in_tags_section = False
            
            return tags
        except Exception as e:
            logger.error(f"Error extracting tags from {file_path}: {e}")
            return []
    
    def extract_yaml_and_body(self, content):
        """Extract YAML frontmatter and body from markdown content"""
        if not content.startswith('---\n'):
            return '', content
            
        # Find the end of the frontmatter
        end_marker = content.find('\n---\n', 4)
        if end_marker == -1:
            return '', content
            
        # Extract the frontmatter and body
        yaml_text = content[4:end_marker]
        body = content[end_marker + 5:]
        
        return yaml_text, body
    
    def update_yaml_tags(self, yaml_text, new_tags):
        """Update tags in YAML frontmatter"""
        lines = yaml_text.split('\n')
        has_tags = False
        in_tags_section = False
        updated_lines = []
        
        for i, line in enumerate(lines):
            # Skip tag lines, we'll add our own
            if line.strip().startswith('tags:'):
                has_tags = True
                
                # Check format: tags: [tag1, tag2]
                if '[' in line and ']' in line:
                    # Replace with new tags array
                    updated_lines.append(f'tags: [{", ".join(new_tags)}]')
                    continue
                elif len(line.strip()) > 5:  # tags: has more text
                    # Replace with new tags array
                    updated_lines.append(f'tags: [{", ".join(new_tags)}]')
                    continue
                else:
                    # Format with list items, don't add the tags line yet
                    updated_lines.append('tags:')
                    in_tags_section = True
                    
                    # Add new tags
                    for tag in new_tags:
                        updated_lines.append(f'  - {tag}')
                    continue
            
            # Skip list items in tags section
            if in_tags_section and line.strip().startswith('-'):
                continue
            elif in_tags_section and not line.strip().startswith('-'):
                # End of tags section
                in_tags_section = False
            
            # Keep other lines
            updated_lines.append(line)
        
        # If no tags were found, add them at the end
        if not has_tags:
            if new_tags:
                updated_lines.append(f'tags: [{", ".join(new_tags)}]')
        
        return '\n'.join(updated_lines)

class VersionManager:
    """Manager for tracking and working with file versions"""
    
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.version_dir = os.path.join(base_dir, '.eepy', 'versions')
        self.ensure_version_dir()
        
    def ensure_version_dir(self):
        """Ensure version directory exists"""
        os.makedirs(self.version_dir, exist_ok=True)
        
    def create_version(self, file_path, reason="sync"):
        """Create a version of a file"""
        if not os.path.exists(file_path):
            return None
            
        try:
            # Get relative path to maintain directory structure
            rel_path = os.path.relpath(file_path, self.base_dir)
            version_subdir = os.path.join(self.version_dir, os.path.dirname(rel_path))
            os.makedirs(version_subdir, exist_ok=True)
            
            # Create version filename with timestamp
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            version_filename = f"{os.path.splitext(filename)[0]}.{timestamp}{os.path.splitext(filename)[1]}"
            version_path = os.path.join(version_subdir, version_filename)
            
            # Copy file
            shutil.copy2(file_path, version_path)
            
            # Create metadata file
            meta_path = f"{version_path}.meta"
            with open(meta_path, 'w', encoding='utf-8') as f:
                file_hash = compute_file_hash(file_path)
                file_size = os.path.getsize(file_path)
                f.write(f"original_path={rel_path}\n")
                f.write(f"timestamp={timestamp}\n")
                f.write(f"reason={reason}\n")
                f.write(f"hash={file_hash}\n")
                f.write(f"size={file_size}\n")
            
            return version_path
        except Exception as e:
            logger.error(f"Failed to create version for {file_path}: {e}")
            return None
            
    def get_versions(self, file_path):
        """Get all versions of a file"""
        try:
            # Get relative path
            rel_path = os.path.relpath(file_path, self.base_dir)
            version_subdir = os.path.join(self.version_dir, os.path.dirname(rel_path))
            
            if not os.path.exists(version_subdir):
                return []
                
            # Get base filename
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            ext = os.path.splitext(os.path.basename(file_path))[1]
            
            # Find versions
            versions = []
            for item in os.listdir(version_subdir):
                # Look for files with the pattern "basename.timestamp.ext"
                item_path = os.path.join(version_subdir, item)
                if os.path.isfile(item_path) and not item.endswith('.meta'):
                    # Parse filename to check if it's a version of our file
                    item_base, item_ext = os.path.splitext(item)
                    if item_ext == ext and item_base.startswith(base_name + '.'):
                        # Extract timestamp
                        timestamp_part = item_base[len(base_name)+1:]
                        if len(timestamp_part) == 14 and timestamp_part.isdigit():  # YYYYMMDDHHMMSS
                            # Get metadata if available
                            meta_path = f"{item_path}.meta"
                            metadata = {}
                            if os.path.exists(meta_path):
                                with open(meta_path, 'r', encoding='utf-8') as f:
                                    for line in f:
                                        if '=' in line:
                                            key, value = line.strip().split('=', 1)
                                            metadata[key] = value
                            
                            version_info = {
                                'path': item_path,
                                'timestamp': datetime.strptime(timestamp_part, '%Y%m%d%H%M%S'),
                                'size': os.path.getsize(item_path),
                                'metadata': metadata
                            }
                            versions.append(version_info)
            
            # Sort by timestamp (newest first)
            versions.sort(key=lambda x: x['timestamp'], reverse=True)
            return versions
        except Exception as e:
            logger.error(f"Error getting versions for {file_path}: {e}")
            return []
            
    def restore_version(self, version_path, target_path=None):
        """Restore a file version
        
        Args:
            version_path: Path to the version file
            target_path: Path to restore to (if None, uses original path)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(version_path):
                return False
                
            # Determine target path
            if target_path is None:
                # Try to get original path from metadata
                meta_path = f"{version_path}.meta"
                if os.path.exists(meta_path):
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith('original_path='):
                                rel_path = line.strip()[len('original_path='):]
                                target_path = os.path.join(self.base_dir, rel_path)
                                break
                
                if target_path is None:
                    # Extract path from version filename
                    version_dir = os.path.dirname(version_path)
                    rel_dir = os.path.relpath(version_dir, self.version_dir)
                    version_filename = os.path.basename(version_path)
                    
                    # Extract timestamp
                    filename_parts = version_filename.split('.')
                    if len(filename_parts) >= 3:
                        # Remove timestamp part
                        original_name = '.'.join(filename_parts[:-2] + [filename_parts[-1]])
                        target_path = os.path.join(self.base_dir, rel_dir, original_name)
            
            if target_path is None:
                logger.error(f"Could not determine target path for {version_path}")
                return False
                
            # Create a version of the current file if it exists
            if os.path.exists(target_path):
                self.create_version(target_path, reason="restore")
                
            # Ensure target directory exists
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
            # Copy version to target
            shutil.copy2(version_path, target_path)
            return True
        except Exception as e:
            logger.error(f"Failed to restore version {version_path}: {e}")
            return False
            
    def delete_version(self, version_path):
        """Delete a file version"""
        try:
            if not os.path.exists(version_path):
                return False
                
            # Delete metadata file if exists
            meta_path = f"{version_path}.meta"
            if os.path.exists(meta_path):
                os.remove(meta_path)
                
            # Delete version file
            os.remove(version_path)
            return True
        except Exception as e:
            logger.error(f"Failed to delete version {version_path}: {e}")
            return False

class SyncScheduleDialog(QDialog):
    """Dialog for scheduling sync operations"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Schedule Synchronization")
        self.resize(500, 300)
        
        self.layout = QVBoxLayout(self)
        
        # Instructions
        self.layout.addWidget(QLabel("You can schedule synchronization to run automatically."))
        
        # Directory pairs
        pairs_group = QGroupBox("Directory Pairs")
        pairs_layout = QVBoxLayout(pairs_group)
        
        # Table for directory pairs
        self.pairs_table = QTableWidget()
        self.pairs_table.setColumnCount(3)
        self.pairs_table.setHorizontalHeaderLabels(["Source", "Target", "Sync Mode"])
        self.pairs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.pairs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        pairs_layout.addWidget(self.pairs_table)
        
        # Buttons for adding/removing pairs
        pairs_buttons = QHBoxLayout()
        self.add_pair_btn = QPushButton("Add Pair")
        self.add_pair_btn.clicked.connect(self.add_pair)
        pairs_buttons.addWidget(self.add_pair_btn)
        
        self.remove_pair_btn = QPushButton("Remove Pair")
        self.remove_pair_btn.clicked.connect(self.remove_pair)
        pairs_buttons.addWidget(self.remove_pair_btn)
        
        pairs_layout.addLayout(pairs_buttons)
        self.layout.addWidget(pairs_group)
        
        # Schedule options
        schedule_group = QGroupBox("Schedule")
        schedule_layout = QVBoxLayout(schedule_group)
        
        # Schedule frequency
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("Run synchronization:"))
        
        self.freq_combo = QComboBox()
        self.freq_combo.addItems(["On demand only", "Daily", "Hourly", "On application start"])
        freq_layout.addWidget(self.freq_combo, 1)
        
        schedule_layout.addLayout(freq_layout)
        
        # Create appropriate system-specific schedule
        self.system_schedule_cb = QCheckBox("Create system-wide schedule (requires privileges)")
        self.system_schedule_cb.setToolTip("Creates a system scheduler task (Windows) or cron job (Linux/Mac)")
        schedule_layout.addWidget(self.system_schedule_cb)
        
        self.layout.addWidget(schedule_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_schedule)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)
        
        # Load existing schedule
        self.load_schedule()
        
    def add_pair(self):
        """Add a new directory pair"""
        from ..widgets import get_synchronized_directory_pair
        source, target, mode = get_synchronized_directory_pair(self)
        
        if source and target:
            row = self.pairs_table.rowCount()
            self.pairs_table.insertRow(row)
            self.pairs_table.setItem(row, 0, QTableWidgetItem(source))
            self.pairs_table.setItem(row, 1, QTableWidgetItem(target))
            self.pairs_table.setItem(row, 2, QTableWidgetItem(mode))
            
    def remove_pair(self):
        """Remove selected directory pair"""
        selected_rows = [index.row() for index in self.pairs_table.selectedIndexes()]
        for row in sorted(set(selected_rows), reverse=True):
            self.pairs_table.removeRow(row)
            
    def load_schedule(self):
        """Load existing schedule configuration"""
        try:
            config_dir = os.path.expanduser('~/.config/epy_explorer')
            config_path = os.path.join(config_dir, 'sync_schedule.json')
            
            if os.path.exists(config_path):
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    schedule = json.load(f)
                    
                # Load directory pairs
                pairs = schedule.get('pairs', [])
                for pair in pairs:
                    row = self.pairs_table.rowCount()
                    self.pairs_table.insertRow(row)
                    self.pairs_table.setItem(row, 0, QTableWidgetItem(pair.get('source', '')))
                    self.pairs_table.setItem(row, 1, QTableWidgetItem(pair.get('target', '')))
                    self.pairs_table.setItem(row, 2, QTableWidgetItem(pair.get('mode', 'two_way')))
                    
                # Load frequency
                frequency = schedule.get('frequency', 'On demand only')
                index = self.freq_combo.findText(frequency)
                if index >= 0:
                    self.freq_combo.setCurrentIndex(index)
                    
                # Load system schedule
                self.system_schedule_cb.setChecked(schedule.get('system_schedule', False))
                
        except Exception as e:
            logger.error(f"Error loading sync schedule: {e}")
            
    def save_schedule(self):
        """Save schedule configuration"""
        try:
            # Collect directory pairs
            pairs = []
            for row in range(self.pairs_table.rowCount()):
                source = self.pairs_table.item(row, 0).text()
                target = self.pairs_table.item(row, 1).text()
                mode = self.pairs_table.item(row, 2).text()
                
                pairs.append({
                    'source': source,
                    'target': target,
                    'mode': mode
                })
                
            # Create schedule config
            schedule = {
                'pairs': pairs,
                'frequency': self.freq_combo.currentText(),
                'system_schedule': self.system_schedule_cb.isChecked(),
                'last_updated': datetime.now().isoformat()
            }
            
            # Save to file
            config_dir = os.path.expanduser('~/.config/epy_explorer')
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, 'sync_schedule.json')
            
            with open(config_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(schedule, f, indent=2)
                
            # Create system schedule if requested
            if self.system_schedule_cb.isChecked():
                self.create_system_schedule(schedule)
                
            self.accept()
            
        except Exception as e:
            logger.error(f"Error saving sync schedule: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save schedule: {str(e)}")
            
    def create_system_schedule(self, schedule):
        """Create a system-level schedule based on platform"""
        try:
            import platform
            system = platform.system()
            
            if system == "Windows":
                self.create_windows_task(schedule)
            elif system == "Linux":
                self.create_linux_cron(schedule)
            elif system == "Darwin":  # macOS
                self.create_macos_launchd(schedule)
            else:
                QMessageBox.warning(self, "Not Supported", f"System scheduling not supported on {system}")
                
        except Exception as e:
            logger.error(f"Error creating system schedule: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create system schedule: {str(e)}")
            
    def create_windows_task(self, schedule):
        """Create a Windows scheduled task"""
        # Implementation would use subprocess to call schtasks.exe
        QMessageBox.information(self, "Not Implemented", "Windows task scheduler integration will be available in a future update.")
        
    def create_linux_cron(self, schedule):
        """Create a Linux cron job"""
        # Implementation would create a crontab entry
        QMessageBox.information(self, "Not Implemented", "Linux cron integration will be available in a future update.")
        
    def create_macos_launchd(self, schedule):
        """Create a macOS launchd plist"""
        # Implementation would create a launchd plist
        QMessageBox.information(self, "Not Implemented", "macOS launchd integration will be available in a future update.")

class DirectorySyncManager(QObject):
    """Manager for directory synchronization operations"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
    def show_sync_dialog(self):
        """Show the directory synchronization dialog"""
        dialog = SyncDialog(self.parent)
        dialog.exec()
        
    def show_schedule_dialog(self):
        """Show the sync schedule dialog"""
        dialog = SyncScheduleDialog(self.parent)
        dialog.exec()
        
    def run_scheduled_sync(self):
        """Run synchronization based on saved schedule"""
        try:
            # Load schedule
            config_dir = os.path.expanduser('~/.config/epy_explorer')
            config_path = os.path.join(config_dir, 'sync_schedule.json')
            
            if not os.path.exists(config_path):
                logger.warning("No sync schedule found")
                return
                
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                schedule = json.load(f)
                
            # Get pairs
            pairs = schedule.get('pairs', [])
            if not pairs:
                logger.warning("No directory pairs in schedule")
                return
                
            # Run sync for each pair
            for pair in pairs:
                source = pair.get('source')
                target = pair.get('target')
                mode = pair.get('mode')
                
                if not source or not target:
                    continue
                    
                if not os.path.exists(source):
                    logger.warning(f"Source directory does not exist: {source}")
                    continue
                    
                # Create sync options
                options = {
                    'sync_mode': mode,
                    'handle_conflicts': 'newer',
                    'delete_orphaned': False,
                    'create_backups': True,
                    'file_types': ['.md'],
                    'skip_patterns': ['.eepy', '.obsidian', '.git', '.trash'],
                    'sync_tags': True,
                    'dry_run': False
                }
                
                # Create and run worker
                worker = SyncWorker(source, target, options)
                worker.run()  # Run synchronously for scheduled tasks
                
            logger.info("Scheduled sync completed")
            
        except Exception as e:
            logger.error(f"Error in scheduled sync: {e}")
            
    def check_schedule_on_startup(self):
        """Check if sync should run on application startup"""
        try:
            # Load schedule
            config_dir = os.path.expanduser('~/.config/epy_explorer')
            config_path = os.path.join(config_dir, 'sync_schedule.json')
            
            if not os.path.exists(config_path):
                return
                
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                schedule = json.load(f)
                
            # Check if scheduled to run on start
            if schedule.get('frequency') == 'On application start':
                # Run in a separate thread to avoid blocking startup
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(5000, self.run_scheduled_sync)  # Run after 5 seconds
                
        except Exception as e:
            logger.error(f"Error checking sync schedule: {e}")

# Function for getting directory pair from dialog
def get_synchronized_directory_pair(parent=None):
    """Get a pair of directories to synchronize"""
    # Create a dialog to select directories and sync mode
    dialog = QDialog(parent)
    dialog.setWindowTitle("Directory Pair")
    dialog.setMinimumWidth(500)
    
    layout = QVBoxLayout(dialog)
    
    # Source directory
    source_layout = QHBoxLayout()
    source_layout.addWidget(QLabel("Source:"))
    source_edit = QLabel()
    source_edit.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
    source_layout.addWidget(source_edit, 1)
    source_btn = QPushButton("Browse...")
    
    def browse_source():
        directory = QFileDialog.getExistingDirectory(
            dialog, "Select Source Directory", source_edit.text(),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            source_edit.setText(directory)
            
    source_btn.clicked.connect(browse_source)
    source_layout.addWidget(source_btn)
    layout.addLayout(source_layout)
    
    # Target directory
    target_layout = QHBoxLayout()
    target_layout.addWidget(QLabel("Target:"))
    target_edit = QLabel()
    target_edit.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
    target_layout.addWidget(target_edit, 1)
    target_btn = QPushButton("Browse...")
    
    def browse_target():
        directory = QFileDialog.getExistingDirectory(
            dialog, "Select Target Directory", target_edit.text(),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            target_edit.setText(directory)
            
    target_btn.clicked.connect(browse_target)
    target_layout.addWidget(target_btn)
    layout.addLayout(target_layout)
    
    # Sync mode
    mode_layout = QHBoxLayout()
    mode_layout.addWidget(QLabel("Sync Mode:"))
    mode_combo = QComboBox()
    mode_combo.addItem("Two-way sync", "two_way")
    mode_combo.addItem("Mirror source to target", "mirror")
    mode_combo.addItem("One-way (source to target)", "one_way_source_to_target")
    mode_combo.addItem("One-way (target to source)", "one_way_target_to_source")
    mode_layout.addWidget(mode_combo, 1)
    layout.addLayout(mode_layout)
    
    # Buttons
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | 
        QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    
    # Execute dialog
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return source_edit.text(), target_edit.text(), mode_combo.currentData()
    else:
        return None, None, None

class SyncDialog(QDialog):
    """Dialog for synchronizing directories"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Synchronize Directories")
        self.resize(700, 500)
        
        # Create main layout
        self.main_layout = QVBoxLayout(self)
        
        # Create directory selection section
        self.setup_directory_section()
        
        # Create options section
        self.setup_options_section()
        
        # Create sync button and progress bar
        self.setup_action_section()
        
        # Initialize sync worker
        self.sync_worker = None
        
    def setup_directory_section(self):
        """Set up directory selection UI"""
        dir_group = QGroupBox("Directories")
        dir_layout = QVBoxLayout(dir_group)
        
        # Source directory selection
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source Directory:"))
        self.source_edit = QLabel()
        self.source_edit.setWordWrap(True)
        self.source_edit.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
        self.source_edit.setMinimumWidth(300)
        source_layout.addWidget(self.source_edit, 1)
        self.source_browse_btn = QPushButton("Browse...")
        self.source_browse_btn.clicked.connect(self.browse_source_directory)
        source_layout.addWidget(self.source_browse_btn)
        dir_layout.addLayout(source_layout)
        
        # Target directory selection
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target Directory:"))
        self.target_edit = QLabel()
        self.target_edit.setWordWrap(True)
        self.target_edit.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
        self.target_edit.setMinimumWidth(300)
        target_layout.addWidget(self.target_edit, 1)
        self.target_browse_btn = QPushButton("Browse...")
        self.target_browse_btn.clicked.connect(self.browse_target_directory)
        target_layout.addWidget(self.target_browse_btn)
        dir_layout.addLayout(target_layout)
        
        self.main_layout.addWidget(dir_group)
        
    def setup_options_section(self):
        """Set up sync options UI"""
        options_group = QGroupBox("Sync Options")
        options_layout = QVBoxLayout(options_group)
        
        # Sync mode options
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Sync Mode:"))
        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItem("Two-way sync (merge both directories)", "two_way")
        self.sync_mode_combo.addItem("Mirror (make target identical to source)", "mirror")
        self.sync_mode_combo.addItem("One-way (source to target)", "one_way_source_to_target")
        self.sync_mode_combo.addItem("One-way (target to source)", "one_way_target_to_source")
        self.sync_mode_combo.currentIndexChanged.connect(self.update_ui_for_mode)
        mode_layout.addWidget(self.sync_mode_combo, 1)
        options_layout.addLayout(mode_layout)
        
        # Conflict handling options
        conflict_layout = QHBoxLayout()
        conflict_layout.addWidget(QLabel("Handle Conflicts:"))
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("Keep newer file", "newer")
        self.conflict_combo.addItem("Keep source file", "source")
        self.conflict_combo.addItem("Keep target file", "target")
        self.conflict_combo.addItem("Keep larger file", "larger")
        self.conflict_combo.addItem("Skip conflicts", "skip")
        conflict_layout.addWidget(self.conflict_combo, 1)
        options_layout.addLayout(conflict_layout)
        
        # Checkboxes for additional options
        self.delete_orphaned_cb = QCheckBox("Delete orphaned files in target")
        self.delete_orphaned_cb.setToolTip("Delete files in target that don't exist in source")
        options_layout.addWidget(self.delete_orphaned_cb)
        
        self.create_backups_cb = QCheckBox("Create backups before overwriting")
        self.create_backups_cb.setChecked(True)
        options_layout.addWidget(self.create_backups_cb)
        
        self.sync_tags_cb = QCheckBox("Synchronize tags in markdown files")
        self.sync_tags_cb.setChecked(True)
        self.sync_tags_cb.setToolTip("Merge tags from source to target in markdown frontmatter")
        options_layout.addWidget(self.sync_tags_cb)
        
        self.dry_run_cb = QCheckBox("Dry run (simulate without making changes)")
        options_layout.addWidget(self.dry_run_cb)
        
        # File filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("File Types:"))
        self.file_types_edit = QComboBox()
        self.file_types_edit.addItem("Markdown files (.md)", [".md"])
        self.file_types_edit.addItem("Text files (.txt, .md)", [".txt", ".md"])
        self.file_types_edit.addItem("All files", [])
        filter_layout.addWidget(self.file_types_edit, 1)
        options_layout.addLayout(filter_layout)
        
        self.main_layout.addWidget(options_group)
        
    def setup_action_section(self):
        """Set up action buttons and progress bar"""
        action_layout = QVBoxLayout()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        action_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel()
        action_layout.addWidget(self.status_label)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.sync_button = QPushButton("Start Synchronization")
        self.sync_button.clicked.connect(self.start_sync)
        buttons_layout.addWidget(self.sync_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)
        
        action_layout.addLayout(buttons_layout)
        self.main_layout.addLayout(action_layout)
        
    def browse_source_directory(self):
        """Browse for source directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Source Directory", self.source_edit.text(),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            self.source_edit.setText(directory)
            
    def browse_target_directory(self):
        """Browse for target directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Target Directory", self.target_edit.text(),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if directory:
            self.target_edit.setText(directory)
            
    def update_ui_for_mode(self):
        """Update UI elements based on selected sync mode"""
        mode = self.sync_mode_combo.currentData()
        
        # Update conflict options visibility
        self.conflict_combo.setEnabled(mode == "two_way")
        
        # Update delete orphaned checkbox
        if mode == "mirror":
            self.delete_orphaned_cb.setChecked(True)
            self.delete_orphaned_cb.setEnabled(False)
        else:
            self.delete_orphaned_cb.setEnabled(True)
            
    def get_sync_options(self):
        """Get the currently selected sync options"""
        return {
            'sync_mode': self.sync_mode_combo.currentData(),
            'handle_conflicts': self.conflict_combo.currentData(),
            'delete_orphaned': self.delete_orphaned_cb.isChecked(),
            'create_backups': self.create_backups_cb.isChecked(),
            'sync_tags': self.sync_tags_cb.isChecked(),
            'dry_run': self.dry_run_cb.isChecked(),
            'file_types': self.file_types_edit.currentData(),
            'skip_patterns': ['.eepy', '.obsidian', '.git', '.trash', '__pycache__']
        }
        
    def start_sync(self):
        """Start the synchronization process"""
        # Validate inputs
        source_dir = self.source_edit.text()
        target_dir = self.target_edit.text()
        
        if not source_dir or not os.path.exists(source_dir):
            QMessageBox.warning(self, "Error", "Please select a valid source directory.")
            return
            
        if not target_dir:
            QMessageBox.warning(self, "Error", "Please select a target directory.")
            return
            
        if source_dir == target_dir:
            QMessageBox.warning(self, "Error", "Source and target directories cannot be the same.")
            return
            
        # Create target directory if it doesn't exist
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create target directory: {str(e)}")
                return
                
        # Get sync options
        options = self.get_sync_options()
        
        # Disable UI elements
        self.sync_button.setEnabled(False)
        self.source_browse_btn.setEnabled(False)
        self.target_browse_btn.setEnabled(False)
        
        # Create and start worker thread
        self.sync_worker = SyncWorker(source_dir, target_dir, options)
        self.sync_worker.progress.connect(self.update_progress)
        self.sync_worker.finished.connect(self.sync_finished)
        self.sync_worker.error.connect(self.sync_error)
        
        # Update status
        dry_run_text = " (DRY RUN)" if options['dry_run'] else ""
        self.status_label.setText(f"Synchronizing{dry_run_text}...")
        
        # Start the worker
        self.sync_worker.start()
        
    def update_progress(self, current, total, message):
        """Update progress bar and status message"""
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
        else:
            self.progress_bar.setValue(0)
            
        self.status_label.setText(message)
        QApplication.processEvents()
        
    def sync_finished(self, results):
        """Handle sync completion"""
        # Re-enable UI elements
        self.sync_button.setEnabled(True)
        self.source_browse_btn.setEnabled(True)
        self.target_browse_btn.setEnabled(True)
        
        # Calculate summary
        created = len(results.get('created', []))
        updated = len(results.get('updated', []))
        deleted = len(results.get('deleted', []))
        conflicts = len(results.get('conflicts', []))
        errors = len(results.get('errors', []))
        
        # Update status
        if self.dry_run_cb.isChecked():
            self.status_label.setText(f"Dry run completed: {created} to create, {updated} to update, {deleted} to delete")
        else:
            self.status_label.setText(f"Completed: {created} created, {updated} updated, {deleted} deleted, {conflicts} conflicts, {errors} errors")
        
        # Show detailed results
        if errors > 0:
            error_details = "\n".join([f"{e['path']}: {e['error']}" for e in results.get('errors', [])])
            QMessageBox.warning(self, "Synchronization Completed with Errors", 
                               f"Synchronization completed with {errors} errors:\n\n{error_details}")
        else:
            QMessageBox.information(self, "Synchronization Completed", 
                                   f"Synchronization completed successfully.\n\n"
                                   f"Created: {created}\n"
                                   f"Updated: {updated}\n"
                                   f"Deleted: {deleted}\n"
                                   f"Conflicts: {conflicts}")
                                   
        # If parent is an explorer window, refresh it
        if hasattr(self.parent, 'refresh_view'):
            self.parent.refresh_view()
            
    def sync_error(self, error_message):
        """Handle sync errors"""
        # Re-enable UI elements
        self.sync_button.setEnabled(True)
        self.source_browse_btn.setEnabled(True)
        self.target_browse_btn.setEnabled(True)
        
        # Show error
        self.status_label.setText("Synchronization failed")
        QMessageBox.critical(self, "Synchronization Failed", f"Error: {error_message}")
        
    def reject(self):
        """Handle dialog close"""
        # Stop worker if running
        if self.sync_worker and self.sync_worker.isRunning():
            self.sync_worker.stop()
            self.sync_worker.wait()
            
        super().reject() 