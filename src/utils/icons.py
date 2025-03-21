import os
from PyQt6.QtWidgets import QFileIconProvider
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QFileInfo

class EFileIconProvider(QFileIconProvider):
    def __init__(self):
        super().__init__()
        self.vcs_status = {}
    
    def set_vcs_status(self, status):
        """Update VCS status information"""
        self.vcs_status = status
    
    def icon(self, info):
        if isinstance(info, QFileInfo):
            # Project structure icons
            if info.isDir():
                if info.fileName() in ['src', 'test', 'docs']:
                    return QIcon.fromTheme('folder-development')
                return QIcon.fromTheme('folder')
            
            # E language file icons
            ext = info.suffix().lower()
            if ext == 'e':
                return QIcon.fromTheme('text-x-source')
            elif ext in ['ey', 'ec']:
                return QIcon.fromTheme('text-x-script')
            elif ext == 'eow':
                return QIcon.fromTheme('text-x-cmake')
            
            # VCS status icons (if in git repo)
            rel_path = os.path.relpath(info.filePath(), os.getcwd())
            if rel_path in self.vcs_status:
                status = self.vcs_status[rel_path]
                if status.startswith('M'):
                    return QIcon.fromTheme('document-save')
                elif status.startswith('A'):
                    return QIcon.fromTheme('list-add')
                elif status.startswith('?'):
                    return QIcon.fromTheme('dialog-question')
            
            # File type icons
            if ext in ['.jpg', '.jpeg', '.png', '.gif']:
                return QIcon.fromTheme('image-x-generic')
            elif ext in ['.mp3', '.wav', '.ogg']:
                return QIcon.fromTheme('audio-x-generic')
            elif ext in ['.mp4', '.avi', '.mkv']:
                return QIcon.fromTheme('video-x-generic')
            elif ext in ['.pdf']:
                return QIcon.fromTheme('application-pdf')
            elif ext in ['.zip', '.tar', '.gz', '.rar']:
                return QIcon.fromTheme('package-x-generic')
            elif ext in ['.txt', '.md']:
                return QIcon.fromTheme('text-x-generic')
        
        return super().icon(info) 