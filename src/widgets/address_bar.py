import os
from PyQt6.QtWidgets import QLineEdit, QCompleter
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QFileSystemModel

class PathCompleter(QCompleter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModel(QFileSystemModel(self))
        self.setCompletionMode(QCompleter.CompletionMode.InlineCompletion)
        
        # Configure the file system model
        model = self.model()
        model.setRootPath("")
        model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)

class AddressBar(QLineEdit):
    """Custom line edit for file path navigation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface"""
        self.setPlaceholderText("Enter path...")
        self.setClearButtonEnabled(True)
        self.setStyleSheet("""
            QLineEdit {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 4px 8px;
                background: rgba(255, 255, 255, 0.05);
                selection-background-color: rgba(255, 255, 255, 0.1);
            }
            QLineEdit:focus {
                border: 1px solid rgba(255, 255, 255, 0.2);
                background: rgba(255, 255, 255, 0.07);
            }
        """)
        self.completer = PathCompleter(self)
        self.setCompleter(self.completer)
        self.completion_index = -1
        self.completions = []
        
    def keyPressEvent(self, event):
        # Handle right arrow to accept completion
        if event.key() == Qt.Key.Key_Right and self.completer.currentCompletion():
            self.setText(self.completer.currentCompletion())
            return
            
        # Handle up/down to cycle through completions
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            current_text = self.text()
            current_path = os.path.dirname(current_text)
            basename = os.path.basename(current_text)
            
            # Get completions if we haven't already
            if not self.completions:
                try:
                    self.completions = [f for f in os.listdir(current_path or '/')
                                      if f.startswith(basename)]
                except OSError:
                    self.completions = []
            
            if self.completions:
                # Update completion index based on direction
                if event.key() == Qt.Key.Key_Up:
                    self.completion_index = (self.completion_index - 1) % len(self.completions)
                else:
                    self.completion_index = (self.completion_index + 1) % len(self.completions)
                
                # Set text to current completion
                completion = self.completions[self.completion_index]
                self.setText(os.path.join(current_path, completion))
            return
            
        # Handle tab for next completion
        if event.key() == Qt.Key.Key_Tab:
            current_text = self.text()
            current_path = os.path.dirname(current_text)
            basename = os.path.basename(current_text)
            
            try:
                # Get all possible completions
                matches = [f for f in os.listdir(current_path or '/')
                          if f.startswith(basename)]
                
                if matches:
                    # Find common prefix among matches
                    common = os.path.commonprefix(matches)
                    if common:
                        self.setText(os.path.join(current_path, common))
            except OSError:
                pass
            return
            
        # Reset completions on any other key
        if event.key() not in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt):
            self.completions = []
            self.completion_index = -1
        
        super().keyPressEvent(event) 