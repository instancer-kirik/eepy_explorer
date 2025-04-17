"""
Utility functions for the EEPY Explorer application.
This module contains helper functions used across the application.
"""

import os
import re
import hashlib
from datetime import datetime
from .themes import setup_theme
from .icons import EFileIconProvider

def file_exists(path):
    """Check if a file exists and is a file
    
    Args:
        path (str): Path to check
        
    Returns:
        bool: True if the path exists and is a file
    """
    return os.path.exists(path) and os.path.isfile(path)

def dir_exists(path):
    """Check if a directory exists and is a directory
    
    Args:
        path (str): Path to check
        
    Returns:
        bool: True if the path exists and is a directory
    """
    return os.path.exists(path) and os.path.isdir(path)

def format_size(size):
    """Format file size in human readable format
    
    Args:
        size (int): Size in bytes
        
    Returns:
        str: Formatted size with appropriate unit
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"

def format_timestamp(timestamp, format_str='%Y-%m-%d %H:%M:%S'):
    """Format a timestamp into a human-readable date string
    
    Args:
        timestamp (float): Unix timestamp
        format_str (str): Format string for datetime
        
    Returns:
        str: Formatted date string
    """
    return datetime.fromtimestamp(timestamp).strftime(format_str)

def compute_file_hash(filepath, quick=False, algorithm="blake2b", chunk_size=8192):
    """Compute hash for a file
    
    Args:
        filepath (str): Path to the file
        quick (bool): If True, only hash the first chunk
        algorithm (str): Hash algorithm to use ("blake2b" or "blake3")
        chunk_size (int): Size of chunks to read
        
    Returns:
        str: Hex digest hash of the file
    """
    # Select hasher based on algorithm
    if algorithm == "blake3":
        try:
            import blake3
            hasher = blake3.blake3()
        except ImportError:
            print("blake3 not available, falling back to blake2b")
            hasher = hashlib.blake2b()
    else:
        hasher = hashlib.blake2b()
    
    try:
        with open(filepath, 'rb') as f:
            if quick:
                # Quick mode: hash first chunk only
                chunk = f.read(chunk_size)
                hasher.update(chunk)
            else:
                # Full mode: hash entire file
                while chunk := f.read(chunk_size):
                    hasher.update(chunk)
                    
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error hashing {filepath}: {str(e)}")
        return None

def extract_tags_from_markdown(filepath):
    """Extract tags from markdown frontmatter
    
    Args:
        filepath (str): Path to the markdown file
        
    Returns:
        list: List of tags found in the frontmatter
    """
    tags = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
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
                                tags.extend([tag.strip().strip('"\'') for tag in tag_list if tag.strip()])
                                
                            # Format: tags:
                            #   - tag1
                            #   - tag2
                            elif not tag_part:
                                # Tags might be in list format in following lines
                                continue
                            
                            # Format: tags: tag1 tag2
                            else:
                                tags.extend([tag.strip().strip('"\'') for tag in tag_part.split() if tag.strip()])
                        
                        # Handle list items for tags defined in multiline format
                        elif line.startswith('- ') and ('tags:' in frontmatter or 'tag:' in frontmatter):
                            tag = line[2:].strip().strip('"\'')
                            if tag:
                                tags.append(tag)
                                
    except Exception as e:
        print(f"Error extracting tags from {filepath}: {e}")
        
    return tags

def get_common_suffix_patterns():
    """Get common suffix patterns used to identify duplicate files
    
    Returns:
        list: List of suffix patterns
    """
    return [
        # Machine-specific suffixes (prioritized)
        '-surfacepro6',
        '-DESKTOP-AKQD6B9',
        '-laptop',
        # Common copy indicators
        ' copy',
        ' (copy)',
        ' (1)',
        ' (2)',
        ' 1',
        ' 2',
        '_1',
        '_2',
        '-1',
        '-2',
        ' - Copy',
        '_copy',
        ' - copy',
        '- copy'
    ]

def has_suffix_pattern(filename, patterns=None):
    """Check if a filename has a known suffix pattern
    
    Args:
        filename (str): Filename to check
        patterns (list): List of suffix patterns to check for
        
    Returns:
        tuple: (has_pattern, pattern_found)
    """
    if patterns is None:
        patterns = get_common_suffix_patterns()
    
    # First check for exact suffix matches
    for pattern in patterns:
        if filename.endswith(pattern):
            return True, pattern
    
    # Check for patterns that might be followed by an extension (like -surfacepro6.md)
    base_name, ext = os.path.splitext(filename)
    for pattern in patterns:
        if base_name.endswith(pattern):
            return True, pattern
    
    # Special case for device-specific suffixes like -surfacepro6
    for pattern in patterns:
        if '-' in pattern and pattern in filename:
            return True, pattern
            
    return False, None

# Create a file icon provider function
def get_file_icon(path):
    """Get icon for a file path"""
    from PyQt6.QtCore import QFileInfo
    provider = EFileIconProvider()
    return provider.icon(QFileInfo(path)) 