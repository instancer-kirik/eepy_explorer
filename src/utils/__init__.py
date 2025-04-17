"""
Utility functions for the EEPY Explorer application.
"""

from .themes import setup_theme

# Import common utility functions to make them available at the package level
from .utils import format_size, format_timestamp, compute_file_hash, file_exists, dir_exists
from .icons import EFileIconProvider

# Create a file icon provider function
def get_file_icon(path):
    """Get icon for a file path"""
    from PyQt6.QtCore import QFileInfo
    provider = EFileIconProvider()
    return provider.icon(QFileInfo(path))
