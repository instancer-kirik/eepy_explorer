from PyQt6.QtCore import QObject, pyqtSignal
import os
import hashlib
import re
from collections import defaultdict
from pathlib import Path

class DuplicateFinder(QObject):
    """Tool for finding and managing duplicate files"""
    
    # Signals
    duplicates_found = pyqtSignal(dict)  # Emitted when duplicates are found
    progress_updated = pyqtSignal(int, int)  # Current, Total
    comparison_result = pyqtSignal(dict)  # Emitted when file comparison is complete
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chunk_size = 8192  # 8KB chunks for reading
        self.min_size = 1024  # Minimum file size to check (1KB)
        
    def compute_file_hash(self, filepath, quick=False):
        """Compute file hash, optionally using quick mode (first chunk only)"""
        hasher = hashlib.blake2b()  # Using blake2b instead of blake3
        
        try:
            with open(filepath, 'rb') as f:
                if quick:
                    # Quick mode: hash first chunk only
                    chunk = f.read(self.chunk_size)
                    hasher.update(chunk)
                else:
                    # Full mode: hash entire file
                    while chunk := f.read(self.chunk_size):
                        hasher.update(chunk)
                        
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error hashing {filepath}: {str(e)}")
            return None
            
    def find_duplicates(self, directory, recursive=True, file_extensions=None):
        """Find duplicate files in directory
        
        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories
            file_extensions: List of file extensions to check (e.g. ['.md', '.txt'])
        """
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
    
    def analyze_duplicates(self, filepaths):
        """Analyze duplicate files for patterns and relationships"""
        results = []
        
        # Extract common patterns in filenames
        filenames = [os.path.basename(path) for path in filepaths]
        base_names = [os.path.splitext(name)[0] for name in filenames]
        
        # Common suffix patterns
        patterns = [
            r'\(\d+\)$',  # (1), (2), etc.
            r'_\d+$',     # _1, _2, etc.
            r'-\d+$',     # -1, -2, etc.
            r' copy$',    # " copy"
            r' copy \(\d+\)$',  # "copy (1)", etc.
            r'_copy$',    # "_copy"
            r'_copy_\d+$' # "_copy_1", etc.
        ]
        
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
            for pattern in patterns:
                if re.search(pattern, base_name):
                    info['is_original'] = False
                    info['suffix_pattern'] = pattern
                    break
            
            results.append(info)
        
        # Sort results by modified time
        results.sort(key=lambda x: x['modified'])
        
        # Mark oldest file as original if no clear original
        if all(not r['is_original'] for r in results):
            results[0]['is_original'] = True
            
        return results
    
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