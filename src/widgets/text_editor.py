from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QTextEdit, QLabel, QFileDialog, QMessageBox,
                           QStatusBar, QSplitter, QComboBox, QLineEdit)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QFont, QTextCharFormat, QColor, QFontMetrics, QTextDocument
import os
import re

# Import syntax highlighters
from .preview import PythonHighlighter, MarkdownHighlighter, ZigHighlighter, EHighlighter


class TextEditorDialog(QDialog):
    """Dialog for editing text files"""
    
    def __init__(self, parent=None, file_path=None):
        super().__init__(parent)
        self.parent = parent
        self.file_path = file_path
        self.is_modified = False
        self.setup_ui()
        
        # Load file if provided
        if file_path and os.path.exists(file_path):
            self.load_file(file_path)
        
    def setup_ui(self):
        """Set up the text editor UI"""
        self.setWindowTitle("Text Editor")
        self.resize(800, 600)
        
        # Create main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Create toolbar
        toolbar = QHBoxLayout()
        
        # File operations
        self.new_btn = QPushButton("New")
        self.new_btn.clicked.connect(self.new_file)
        toolbar.addWidget(self.new_btn)
        
        self.open_btn = QPushButton("Open")
        self.open_btn.clicked.connect(self.open_file)
        toolbar.addWidget(self.open_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_file)
        toolbar.addWidget(self.save_btn)
        
        self.save_as_btn = QPushButton("Save As")
        self.save_as_btn.clicked.connect(self.save_file_as)
        toolbar.addWidget(self.save_as_btn)
        
        toolbar.addStretch()
        
        # Search field
        self.search_label = QLabel("Search:")
        toolbar.addWidget(self.search_label)
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Enter search text...")
        self.search_field.returnPressed.connect(self.search_text)
        toolbar.addWidget(self.search_field)
        
        self.search_btn = QPushButton("Find")
        self.search_btn.clicked.connect(self.search_text)
        toolbar.addWidget(self.search_btn)
        
        # Add toolbar to main layout
        layout.addLayout(toolbar)
        
        # Create editor
        self.editor = QTextEdit()
        self.editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.editor.setTabStopDistance(40)  # Set tab width to roughly 4 spaces
        self.editor.textChanged.connect(self.text_changed)
        
        # Set monospace font
        font = QFont("Monospace")
        font.setFixedPitch(True)
        font.setPointSize(10)
        self.editor.setFont(font)
        
        layout.addWidget(self.editor)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.cursor_position_label = QLabel("Line: 1, Col: 1")
        self.status_bar.addPermanentWidget(self.cursor_position_label)
        self.file_info_label = QLabel("No file loaded")
        self.status_bar.addWidget(self.file_info_label)
        layout.addWidget(self.status_bar)
        
        # Connect cursor position update
        self.editor.cursorPositionChanged.connect(self.update_cursor_position)
        
        # Set up syntax highlighting
        self.highlighter = None
        
    def load_file(self, file_path):
        """Load a file into the editor"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.editor.setPlainText(content)
            self.file_path = file_path
            self.update_title()
            self.update_file_info()
            self.is_modified = False
            
            # Set up syntax highlighting based on file extension
            ext = os.path.splitext(file_path)[1].lower()
            self.setup_syntax_highlighting(ext)
            
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not load file: {str(e)}"
            )
            return False
            
    def setup_syntax_highlighting(self, ext):
        """Set up appropriate syntax highlighting for the file type"""
        if self.highlighter:
            self.highlighter.setDocument(None)
            self.highlighter = None
            
        if ext in ['.py', '.pyw']:
            self.highlighter = PythonHighlighter(self.editor.document())
        elif ext in ['.md', '.markdown']:
            self.highlighter = MarkdownHighlighter(self.editor.document())
        elif ext in ['.zig']:
            self.highlighter = ZigHighlighter(self.editor.document())
        elif ext in ['.e']:
            self.highlighter = EHighlighter(self.editor.document())
            
    def update_title(self):
        """Update the window title with file name"""
        if self.file_path:
            base_name = os.path.basename(self.file_path)
            self.setWindowTitle(f"Text Editor - {base_name}{' *' if self.is_modified else ''}")
        else:
            self.setWindowTitle(f"Text Editor - Untitled{' *' if self.is_modified else ''}")
            
    def update_file_info(self):
        """Update the file info label in the status bar"""
        if self.file_path:
            size = os.path.getsize(self.file_path)
            size_str = self.format_size(size)
            self.file_info_label.setText(f"{self.file_path} ({size_str})")
        else:
            self.file_info_label.setText("No file loaded")
            
    def format_size(self, size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
            
    def update_cursor_position(self):
        """Update cursor position in status bar"""
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.cursor_position_label.setText(f"Line: {line}, Col: {col}")
            
    def text_changed(self):
        """Handle text changes"""
        # Only mark as modified if the content actually changed from the original file
        if self.file_path and os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                current_content = self.editor.toPlainText()
                
                # Compare current content with original
                if current_content != original_content:
                    if not self.is_modified:
                        self.is_modified = True
                        self.update_title()
                else:
                    if self.is_modified:
                        self.is_modified = False
                        self.update_title()
            except Exception:
                # If there's an error reading the file, default to standard behavior
                if not self.is_modified:
                    self.is_modified = True
                    self.update_title()
        else:
            # For new files, use standard behavior
            if not self.is_modified:
                self.is_modified = True
                self.update_title()
            
    def new_file(self):
        """Create a new file"""
        if self.check_save():
            self.editor.clear()
            self.file_path = None
            self.is_modified = False
            self.update_title()
            self.update_file_info()
            
    def open_file(self):
        """Open a file dialog to select a file to edit"""
        if self.check_save():
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open File",
                os.path.dirname(self.file_path) if self.file_path else "",
                "Text Files (*.txt);;Python Files (*.py);;Markdown Files (*.md);;All Files (*)"
            )
            
            if file_path:
                self.load_file(file_path)
                
    def save_file(self):
        """Save the current file"""
        if not self.file_path:
            return self.save_file_as()
            
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
                
            self.is_modified = False
            self.update_title()
            self.update_file_info()
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not save file: {str(e)}"
            )
            return False
            
    def save_file_as(self):
        """Save the current file with a new name"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File As",
            os.path.dirname(self.file_path) if self.file_path else "",
            "Text Files (*.txt);;Python Files (*.py);;Markdown Files (*.md);;All Files (*)"
        )
        
        if not file_path:
            return False
            
        self.file_path = file_path
        return self.save_file()
        
    def check_save(self):
        """Check if the current file needs to be saved"""
        if not self.is_modified:
            return True
            
        reply = QMessageBox.question(
            self,
            "Save Changes",
            "The document has been modified. Save changes?",
            QMessageBox.StandardButton.Save | 
            QMessageBox.StandardButton.Discard | 
            QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Save:
            return self.save_file()
        elif reply == QMessageBox.StandardButton.Cancel:
            return False
            
        return True  # Discard
        
    def search_text(self):
        """Search for text in the editor"""
        search_text = self.search_field.text()
        if not search_text:
            return
            
        # Start from current position or beginning if nothing found
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.movePosition(QTextCursor.MoveOperation.Start)
        else:
            cursor.setPosition(cursor.selectionEnd())
            
        # Find the text
        document = self.editor.document()
        found = False
        
        # Create a find flags flags object to set case sensitivity
        flags = QTextDocument.FindFlag.FindCaseSensitively
        
        # Search for the text
        cursor = document.find(search_text, cursor, flags)
        
        if not cursor.isNull():
            found = True
            self.editor.setTextCursor(cursor)
        else:
            # If not found from current position, try from the beginning
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor = document.find(search_text, cursor, flags)
            
            if not cursor.isNull():
                found = True
                self.editor.setTextCursor(cursor)
                
        if not found:
            QMessageBox.information(
                self, "Search", f"No occurrences of '{search_text}' found."
            )
            
    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.check_save():
            event.accept()
        else:
            event.ignore() 