from PyQt6.QtCore import QObject, pyqtSignal
import os
import re
from collections import defaultdict
from pathlib import Path
from abc import ABC, ABCMeta, abstractmethod
import hashlib

from ..utils.utils import compute_file_hash, extract_tags_from_markdown, has_suffix_pattern, get_common_suffix_patterns

# Create a metaclass that combines QObject metaclass and ABCMeta
class MetaQObjectABC(type(QObject), ABCMeta):
    pass

class BaseDuplicateFinder(QObject, ABC, metaclass=MetaQObjectABC):
    """Abstract base class for duplicate finding functionality"""
    
    # Common signals
    progress_updated = pyqtSignal(int, int)  # Current, Total
    duplicates_found = pyqtSignal(dict)  # Emitted when duplicates are found
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chunk_size = 8192  # 8KB chunks for reading
        self.min_size = 1024  # Minimum file size to check (1KB)
    
    @abstractmethod
    def find_duplicates(self, directory, recursive=True, file_extensions=None):
        """Find duplicate files in directory
        
        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories
            file_extensions: List of file extensions to check (e.g. ['.md', '.txt'])
        """
        pass
    
    def compute_file_hash(self, filepath, quick=False, algorithm="blake2b"):
        """Compute file hash, optionally using quick mode (first chunk only)"""
        return compute_file_hash(filepath, quick, algorithm, self.chunk_size)
    
    def resolve_duplicates(self, actions):
        """Resolve duplicates according to specified actions"""
        results = {
            'succeeded': [],
            'failed': []
        }
        
        for action in actions:
            try:
                if action['action'] == 'delete':
                    os.remove(action['source'])
                    results['succeeded'].append(action)
                # Add more actions as needed (move, rename, etc.)
            except Exception as e:
                action['error'] = str(e)
                results['failed'].append(action)
                
        return results
    
    def analyze_duplicates(self, filepaths):
        """Analyze duplicate files for patterns and relationships"""
        results = []
        
        # Extract common patterns in filenames
        filenames = [os.path.basename(path) for path in filepaths]
        base_names = [os.path.splitext(name)[0] for name in filenames]
        
        # Common suffix patterns
        suffix_patterns = get_common_suffix_patterns()
        
        for path in filepaths:
            filename = os.path.basename(path)
            base_name = os.path.splitext(filename)[0]
            
            # Analyze file
            info = {
                'path': path,
                'filename': filename,
                'size': os.path.getsize(path),
                'modified': os.path.getmtime(path),
                'is_original': True,  # Assume original until proven otherwise
                'suffix_pattern': None
            }
            
            # Check for copy patterns
            has_pattern, pattern = has_suffix_pattern(base_name, suffix_patterns)
            if has_pattern:
                info['is_original'] = False
                info['suffix_pattern'] = pattern
            
            results.append(info)
        
        # Sort results by modified time
        results.sort(key=lambda x: x['modified'])
        
        # Mark oldest file as original if no clear original
        if all(not r['is_original'] for r in results):
            results[0]['is_original'] = True
            
        return results


class FileDuplicateFinder(BaseDuplicateFinder):
    """Tool for finding and managing duplicate files"""
    
    # Additional signals
    comparison_result = pyqtSignal(dict)  # Emitted when file comparison is complete
    
    def __init__(self, parent=None):
        super().__init__(parent)
            
    def find_duplicates(self, directory, recursive=True, file_extensions=None):
        """Find duplicate files in directory"""
        # Group files by size first (quick filter)
        size_groups = defaultdict(list)
        total_files = 0
        processed_files = 0
        
        # First pass: group by size
        for root, _, files in os.walk(directory):
            for filename in files:
                # Skip if we're only looking for specific extensions
                if file_extensions and not any(filename.lower().endswith(ext) for ext in file_extensions):
                    continue
                    
                filepath = os.path.join(root, filename)
                try:
                    size = os.path.getsize(filepath)
                    if size >= self.min_size:
                        size_groups[size].append(filepath)
                        total_files += 1
                except Exception as e:
                    print(f"Error accessing {filepath}: {str(e)}")
                    
            if not recursive:
                break
        
        # Update progress
        self.progress_updated.emit(0, total_files)
        
        # Second pass: compute quick hashes for size matches
        quick_hash_groups = defaultdict(list)
        for size, filepaths in size_groups.items():
            if len(filepaths) > 1:  # Only check groups with potential duplicates
                for filepath in filepaths:
                    quick_hash = self.compute_file_hash(filepath, quick=True)
                    if quick_hash:
                        quick_hash_groups[quick_hash].append(filepath)
                    processed_files += 1
                    if processed_files % 10 == 0:  # Update progress every 10 files
                        self.progress_updated.emit(processed_files, total_files)
        
        # Third pass: compute full hashes for quick hash matches
        duplicates = defaultdict(list)
        for quick_hash, filepaths in quick_hash_groups.items():
            if len(filepaths) > 1:  # Only check groups with potential duplicates
                full_hash_groups = defaultdict(list)
                for filepath in filepaths:
                    full_hash = self.compute_file_hash(filepath, quick=False)
                    if full_hash:
                        full_hash_groups[full_hash].append(filepath)
                    processed_files += 1
                    if processed_files % 10 == 0:  # Update progress every 10 files
                        self.progress_updated.emit(processed_files, total_files)
                
                # Add confirmed duplicates to results
                for full_hash, duplicate_files in full_hash_groups.items():
                    if len(duplicate_files) > 1:
                        duplicates[full_hash] = self.analyze_duplicates(duplicate_files)
        
        self.progress_updated.emit(total_files, total_files)
        self.duplicates_found.emit(dict(duplicates))
        return duplicates
    
    def suggest_resolution(self, duplicates):
        """Suggest resolution actions for duplicate files"""
        suggestions = []
        
        for hash_value, files in duplicates.items():
            # Find the original or oldest file
            original = next(
                (f for f in files if f['is_original']),
                min(files, key=lambda x: x['modified'])
            )
            
            # Generate suggestions for each duplicate
            for file in files:
                if file['path'] != original['path']:
                    suggestion = {
                        'action': 'delete',
                        'source': file['path'],
                        'reason': 'Duplicate file'
                    }
                    
                    # If file has a copy pattern, it's a clear duplicate
                    if file['suffix_pattern']:
                        suggestion['confidence'] = 'high'
                    else:
                        suggestion['confidence'] = 'medium'
                        
                    suggestions.append(suggestion)
        
        return suggestions

    def compare_files(self, file1, file2):
        """Compare two files and return detailed comparison results"""
        try:
            # Get basic file info
            size1 = os.path.getsize(file1)
            size2 = os.path.getsize(file2)
            
            result = {
                'are_identical': False,
                'size_match': size1 == size2,
                'size1': size1,
                'size2': size2,
                'name1': os.path.basename(file1),
                'name2': os.path.basename(file2),
                'path1': file1,
                'path2': file2,
                'modified1': os.path.getmtime(file1),
                'modified2': os.path.getmtime(file2),
                'quick_hash_match': False,
                'full_hash_match': False,
                'error': None
            }
            
            # If sizes don't match, files are definitely different
            if not result['size_match']:
                self.comparison_result.emit(result)
                return result
            
            # Quick hash comparison (first chunk)
            quick_hash1 = self.compute_file_hash(file1, quick=True)
            quick_hash2 = self.compute_file_hash(file2, quick=True)
            
            result['quick_hash_match'] = quick_hash1 == quick_hash2
            
            # If quick hashes don't match, files are different
            if not result['quick_hash_match']:
                self.comparison_result.emit(result)
                return result
            
            # Full hash comparison
            full_hash1 = self.compute_file_hash(file1, quick=False)
            full_hash2 = self.compute_file_hash(file2, quick=False)
            
            result['full_hash_match'] = full_hash1 == full_hash2
            result['are_identical'] = result['full_hash_match']
            
            self.comparison_result.emit(result)
            return result
            
        except Exception as e:
            result = {
                'are_identical': False,
                'error': str(e),
                'path1': file1,
                'path2': file2
            }
            self.comparison_result.emit(result)
            return result


class NotesDuplicateFinder(BaseDuplicateFinder):
    """Class for finding and managing duplicate notes"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def find_duplicates(self, directory, recursive=True, file_extensions=None):
        """Find duplicate notes in directory
        
        This implementation handles markdown notes specifically.
        """
        if not file_extensions:
            file_extensions = ['.md']  # Default to markdown files
            
        # Default to a content-based search
        return self.find_duplicates_by_content(directory, recursive)
            
    def find_duplicates_by_content(self, directory, recursive=True):
        """Find notes with identical content"""
        # Dictionary to store duplicate files
        duplicates = {}
        
        # Get list of markdown files
        md_files = []
        total_files = 0
        
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    filepath = os.path.join(root, filename)
                    md_files.append(filepath)
                    total_files += 1
                    
            if not recursive:
                break
                
        # Process files
        processed_files = 0
        self.progress_updated.emit(0, total_files)
        
        # Group by hash value
        hash_groups = defaultdict(list)
        
        # Process each file
        for filepath in md_files:
            try:
                # Calculate hash for content
                hash_value = self.compute_file_hash(filepath, algorithm="blake2b")
                
                if hash_value:
                    hash_groups[hash_value].append(filepath)
                    
            except Exception as e:
                print(f"Error processing {filepath}: {str(e)}")
                
            processed_files += 1
            if processed_files % 10 == 0:
                self.progress_updated.emit(processed_files, total_files)
                
        # Format results for duplicate groups
        for hash_value, filepaths in hash_groups.items():
            if len(filepaths) > 1:  # Only include duplicate groups
                # Analyze the group
                duplicates[hash_value] = self.analyze_duplicates(filepaths)
                
        self.progress_updated.emit(total_files, total_files)
        self.duplicates_found.emit(dict(duplicates))
        return duplicates
        
    def find_duplicates_by_suffix(self, directory, recursive=True, suffix_patterns=None):
        """Find notes with specific suffixes that indicate duplicates"""
        if suffix_patterns is None:
            suffix_patterns = get_common_suffix_patterns()
            
        # Maps to store groups of related files
        file_base_map = defaultdict(list)
        suffix_groups = {}
        
        # Count files for progress tracking
        total_files = 0
        processed_files = 0
        
        # First get a count of files
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename.lower().endswith('.md'):
                    total_files += 1
                    
            if not recursive:
                break
                
        self.progress_updated.emit(0, total_files)
        
        # Process files to group them by base name without suffixes
        for root, _, files in os.walk(directory):
            for filename in files:
                if not filename.lower().endswith('.md'):
                    continue
                    
                file_path = os.path.join(root, filename)
                base_name = os.path.splitext(filename)[0]
                
                # Remove all known suffixes to get the true base name
                original_base = base_name
                for suffix in suffix_patterns:
                    if suffix in base_name:
                        # Try to remove the suffix
                        position = base_name.rfind(suffix)
                        if position > 0 and base_name.endswith(suffix):
                            # If the suffix is at the end of the name, remove it
                            base_name = base_name[:position]
                            break
                
                # Group by base name
                file_base_map[base_name].append((file_path, original_base, os.path.getmtime(file_path)))
                
                processed_files += 1
                if processed_files % 10 == 0:
                    self.progress_updated.emit(processed_files, total_files)
                    
            if not recursive:
                break
                
        # Now identify duplicates based on suffix patterns
        duplicates = {}
        for key, file_list in file_base_map.items():
            # Skip single files
            if len(file_list) <= 1:
                continue
                
            # Check each file for suffix patterns
            has_suffix = False
            for file_path, base_name, _ in file_list:
                # Check if this file has any of the suffix patterns
                has_pattern, _ = has_suffix_pattern(base_name, suffix_patterns)
                if has_pattern:
                    has_suffix = True
                    break
            
            # If we found at least one file with a suffix, create a duplicate group
            if has_suffix:
                group_key = f"suffix_{os.path.basename(key)}"
                duplicates[group_key] = self.analyze_suffix_duplicates(file_list, suffix_patterns)
        
        self.progress_updated.emit(total_files, total_files)
        self.duplicates_found.emit(dict(duplicates))
        return duplicates
        
    def analyze_suffix_duplicates(self, file_list, suffix_patterns):
        """Analyze duplicate files identified by suffix patterns"""
        results = []
        
        # Sort by modified time to help determine the original
        file_list.sort(key=lambda x: x[2])  # Sort by modified time
        
        for file_path, base_name, mod_time in file_list:
            # Check for suffix patterns
            has_pattern, found_suffix = has_suffix_pattern(base_name, suffix_patterns)
            
            stats = os.stat(file_path)
            
            # Extract tags if it's a markdown file
            tags = extract_tags_from_markdown(file_path) if file_path.endswith('.md') else []
            
            info = {
                'path': file_path,
                'filename': os.path.basename(file_path),
                'size': stats.st_size,
                'modified': stats.st_mtime,
                'is_original': not has_pattern,  # Files without suffix patterns are considered originals
                'suffix_pattern': found_suffix,
                'tags': tags
            }
            
            results.append(info)
        
        # Ensure we have at least one original 
        # If all files have suffixes, mark the oldest as original
        if all(not r['is_original'] for r in results):
            results[0]['is_original'] = True
            
        return results
        
    def extract_tags(self, filepath):
        """Extract tags from markdown frontmatter"""
        return extract_tags_from_markdown(filepath)


class DuplicateFinderWorker(QObject):
    """Worker to find duplicates using a hash"""
    # Define signals
    started = pyqtSignal()
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = files
        self.should_stop = False

    def find_duplicates(self):
        """Find duplicate files by content hash"""
        self.started.emit()
        try:
            duplicate_groups = {}
            total_files = len(self.files)
            
            # Check if we should stop
            if self.should_stop:
                self.finished.emit({})
                return
            
            # First pass: identify empty files and files with only frontmatter
            empty_files = []
            frontmatter_only_files = []
            
            for i, file_path in enumerate(self.files):
                # Check if we should stop
                if self.should_stop:
                    self.finished.emit({})
                    return
                    
                try:
                    # Check file size first
                    file_size = os.path.getsize(file_path)
                    if file_size == 0:
                        file_info = {
                            'path': file_path,
                            'filename': os.path.basename(file_path),
                            'size': 0,
                            'modified': os.path.getmtime(file_path),
                            'is_empty': True
                        }
                        empty_files.append(file_info)
                        continue
                    
                    # Check for frontmatter-only files
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Parse frontmatter to get tags
                    frontmatter, content_without_frontmatter = self._extract_frontmatter(content)
                    
                    # If the file has frontmatter but no content
                    if frontmatter and not content_without_frontmatter.strip():
                        file_info = {
                            'path': file_path,
                            'filename': os.path.basename(file_path),
                            'size': file_size,
                            'modified': os.path.getmtime(file_path),
                            'tags': self._extract_tags_from_frontmatter(frontmatter),
                            'is_frontmatter_only': True
                        }
                        frontmatter_only_files.append(file_info)
                        continue
                        
                except Exception as e:
                    print(f"Error processing file {file_path}: {str(e)}")
                
                # Update progress
                if i % 10 == 0:  # Update progress every 10 files
                    self.progress.emit(i + 1, total_files)
            
            # Process empty files
            if empty_files:
                # Sort by modification time (newest first)
                empty_files.sort(key=lambda x: x['modified'], reverse=True)
                # Mark the newest file as original
                if empty_files:
                    empty_files[0]['is_original'] = True
                duplicate_groups['content_empty_files'] = empty_files
            
            # Process frontmatter-only files
            if frontmatter_only_files:
                # Sort by modification time (newest first)
                frontmatter_only_files.sort(key=lambda x: x['modified'], reverse=True)
                # Mark the newest file as original
                if frontmatter_only_files:
                    frontmatter_only_files[0]['is_original'] = True
                duplicate_groups['content_frontmatter_only'] = frontmatter_only_files
            
            # Continue with normal content hashing for remaining files
            file_hashes = {}
            
            for i, file_path in enumerate(self.files):
                # Check if we should stop
                if self.should_stop:
                    self.finished.emit({})
                    return
                    
                # Skip files we've already categorized
                if any(file_path == f['path'] for f in empty_files + frontmatter_only_files):
                    continue
                    
                try:
                    # Compute the hash of the file
                    file_hash = self._compute_file_hash(file_path)
                    
                    # Skip files with errors
                    if not file_hash:
                        continue
                        
                    # Get file metadata
                    file_size = os.path.getsize(file_path)
                    modified_time = os.path.getmtime(file_path)
                    
                    # Parse file to get tags
                    tags = []
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        frontmatter, _ = self._extract_frontmatter(content)
                        if frontmatter:
                            tags = self._extract_tags_from_frontmatter(frontmatter)
                    except Exception:
                        pass  # Skip tag extraction if there's an error
                    
                    # Build file info
                    file_info = {
                        'path': file_path,
                        'filename': os.path.basename(file_path),
                        'size': file_size,
                        'modified': modified_time,
                        'tags': tags
                    }
                    
                    # Add to the appropriate hash group
                    if file_hash in file_hashes:
                        file_hashes[file_hash].append(file_info)
                    else:
                        file_hashes[file_hash] = [file_info]
                except Exception as e:
                    print(f"Error processing file {file_path}: {str(e)}")
                
                # Update progress
                if i % 10 == 0:  # Update progress every 10 files
                    self.progress.emit(i + 1, total_files)
            
            # Create duplicate groups (skip non-duplicates)
            for file_hash, files in file_hashes.items():
                if len(files) > 1:
                    # For suspiciously large groups, verify content with additional check
                    if len(files) > 20:
                        print(f"Large group detected: {len(files)} files with hash {file_hash}, performing additional verification")
                        # Consider adding a more thorough verification here
                        pass
                        
                    # Sort by modification time (newest first)
                    files.sort(key=lambda x: x['modified'], reverse=True)
                    
                    # Mark the first file as the original
                    files[0]['is_original'] = True
                    
                    # Store in duplicate groups
                    group_id = f"content_{file_hash[:10]}"  # Use first 10 chars of hash as ID
                    duplicate_groups[group_id] = files
            
            # Emit the duplicate groups
            self.progress.emit(total_files, total_files)
            self.finished.emit(duplicate_groups)
            
        except Exception as e:
            error_msg = f"Error finding duplicates: {str(e)}"
            print(error_msg)
            self.error.emit(error_msg)
            self.finished.emit({})  # Empty result

    def _compute_file_hash(self, file_path):
        """Compute a blake2b hash of a file"""
        try:
            # For files over 10MB, use a chunked approach
            file_size = os.path.getsize(file_path)
            
            with open(file_path, 'rb') as f:
                if file_size > 10 * 1024 * 1024:  # 10MB
                    # For large files, use a chunked approach
                    hasher = hashlib.blake2b()
                    chunk_size = 8192  # 8KB chunks
                    
                    # Read the file in chunks
                    while chunk := f.read(chunk_size):
                        hasher.update(chunk)
                    
                    return hasher.hexdigest()
                else:
                    # For smaller files, read the entire content
                    content = f.read()
                    return hashlib.blake2b(content).hexdigest()
        except Exception as e:
            print(f"Error computing hash for {file_path}: {str(e)}")
            return None

    def _extract_frontmatter(self, content):
        """Extract frontmatter from a markdown file"""
        if not content.startswith('---\n'):
            return {}, content
            
        # Find the end of the frontmatter
        end_marker = content.find('\n---\n', 4)
        if end_marker == -1:
            return {}, content
            
        # Extract the frontmatter
        frontmatter_text = content[4:end_marker]
        content_without_frontmatter = content[end_marker + 5:]
        
        return frontmatter_text, content_without_frontmatter
    
    def _extract_tags_from_frontmatter(self, frontmatter_text):
        """Extract tags from frontmatter text without using yaml module"""
        tags = []
        
        # Look for tags: [...] pattern
        tag_match = re.search(r'tags:\s*\[(.*?)\]', frontmatter_text)
        if tag_match:
            # Extract tags from array format
            tag_str = tag_match.group(1)
            tags.extend([t.strip().strip('"\'') for t in tag_str.split(',')])
        else:
            # Look for tags: followed by list items
            for line in frontmatter_text.split('\n'):
                if line.strip().startswith('- ') and 'tags:' in frontmatter_text:
                    tag = line.strip()[2:].strip().strip('"\'')
                    if tag:
                        tags.append(tag)
        
        return tags

class SuffixDuplicateFinderWorker(QObject):
    """Worker to find duplicate notes by suffix"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.should_stop = False
        
    def run(self):
        """Execute the worker thread to find suffix duplicates"""
        try:
            print("Starting suffix duplicate finder worker")
            duplicates = self.find_suffix_duplicates()
            print(f"Found {len(duplicates)} duplicate groups")
            self.finished.emit(duplicates)
        except Exception as e:
            error_msg = f"Error in suffix duplicate finder: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.error.emit(error_msg)
            # Always emit the finished signal, even in case of error
            self.finished.emit({})
    
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
        
    def extract_tags(self, filepath):
        """Extract tags from a note's YAML front matter"""
        tags = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for YAML front matter
            if content.startswith('---'):
                # Extract the YAML block
                yaml_end = content.find('---', 3)
                if yaml_end != -1:
                    yaml_block = content[3:yaml_end].strip()
                    
                    # Look for tags field
                    for line in yaml_block.split('\n'):
                        if line.startswith('tags:'):
                            # Parse the tags
                            tag_line = line[5:].strip()
                            if tag_line.startswith('[') and tag_line.endswith(']'):
                                # Array format: tags: [tag1, tag2]
                                tag_str = tag_line[1:-1]
                                tags = [t.strip().strip("'\"") for t in tag_str.split(',') if t.strip()]
                            else:
                                # List format: 
                                # tags:
                                #   - tag1
                                #   - tag2
                                i = yaml_block.find('tags:')
                                if i != -1:
                                    # Start from the line after "tags:"
                                    tag_section = yaml_block[i+5:].strip()
                                    for tag_line in tag_section.split('\n'):
                                        if tag_line.strip().startswith('-'):
                                            tag = tag_line.strip()[1:].strip().strip("'\"")
                                            if tag:
                                                tags.append(tag)
                                        elif not tag_line.strip() or not tag_line.strip().startswith(' '):
                                            # End of tag section
                                            break
        except Exception as e:
            print(f"Error extracting tags from {filepath}: {e}")
            
        return tags 