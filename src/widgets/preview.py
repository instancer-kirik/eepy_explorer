from PyQt6.QtWidgets import (QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QTreeWidget, QTreeWidgetItem, QStackedWidget,
                           QScrollArea, QGridLayout, QLabel, QTabWidget, QMenu,
                           QLineEdit, QToolButton, QSpinBox, QHeaderView)
from PyQt6.QtGui import (QFont, QSyntaxHighlighter, QTextCharFormat, QColor,
                      QPixmap, QPainter, QTextCursor, QTextOption, QImage, QIcon)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
import re
import os
import json
import zipfile
import tarfile
import chardet
from datetime import datetime
import mimetypes
import magic  # python-magic for better file type detection

class EHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for E language files"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.highlighting_rules = []
        
        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "fn", "if", "else", "while", "for", "in", "return",
            "break", "continue", "struct", "enum", "type",
            "import", "export", "pub", "mut", "const"
        ]
        for word in keywords:
            pattern = f"\\b{word}\\b"
            self.highlighting_rules.append((pattern, keyword_format))
        
        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self.highlighting_rules.append((r"\b[0-9]+\b", number_format))
        
        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', string_format))
        
        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((r"//[^\n]*", comment_format))
        
        # Function calls
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#DCDCAA"))
        self.highlighting_rules.append((r"\b[A-Za-z0-9_]+(?=\()", function_format))

    def highlightBlock(self, text):
        """Apply highlighting to the given block of text"""
        for pattern, format in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                # Calculate match length as end - start (Python's re doesn't have length() method)
                match_length = match.end() - match.start()
                self.setFormat(match.start(), match_length, format)

class MarkdownHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Markdown files"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.highlighting_rules = []
        
        # Headers
        header_format = QTextCharFormat()
        header_format.setForeground(QColor("#569CD6"))
        header_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((r"^#.*$", header_format))
        
        # Bold
        bold_format = QTextCharFormat()
        bold_format.setFontWeight(QFont.Weight.Bold)
        self.highlighting_rules.append((r"\*\*.*\*\*", bold_format))
        
        # Italic
        italic_format = QTextCharFormat()
        italic_format.setFontItalic(True)
        self.highlighting_rules.append((r"\*.*\*", italic_format))
        
        # Code blocks
        code_format = QTextCharFormat()
        code_format.setForeground(QColor("#CE9178"))
        code_format.setBackground(QColor("#1E1E1E"))
        self.highlighting_rules.append((r"`.*`", code_format))
        
        # Links
        link_format = QTextCharFormat()
        link_format.setForeground(QColor("#569CD6"))
        link_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        self.highlighting_rules.append((r"\[.*\]\(.*\)", link_format))

    def highlightBlock(self, text):
        """Apply highlighting to the given block of text"""
        for pattern, format in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                # Calculate match length as end - start (Python's re doesn't have length() method)
                match_length = match.end() - match.start()
                self.setFormat(match.start(), match_length, format)

class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python files"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.highlighting_rules = []
        
        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "def", "class", "if", "else", "elif", "while", "for",
            "in", "try", "except", "finally", "with", "as", "import",
            "from", "return", "yield", "break", "continue", "pass",
            "raise", "True", "False", "None", "and", "or", "not",
            "is", "lambda", "nonlocal", "global", "assert", "del"
        ]
        for word in keywords:
            pattern = f"\\b{word}\\b"
            self.highlighting_rules.append((pattern, keyword_format))
        
        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.extend([
            (r'"[^"\\]*(\\.[^"\\]*)*"', string_format),
            (r"'[^'\\]*(\\.[^'\\]*)*'", string_format),
        ])
        
        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((r"#[^\n]*", comment_format))
        
        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self.highlighting_rules.append((r"\b[0-9]+\b", number_format))
        
        # Function definitions
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#DCDCAA"))
        self.highlighting_rules.append((r"\bdef\s+([^\d\W]\w*)", function_format))
        
        # Class definitions
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#4EC9B0"))
        self.highlighting_rules.append((r"\bclass\s+([^\d\W]\w*)", class_format))

    def highlightBlock(self, text):
        """Apply highlighting to the given block of text"""
        for pattern, format in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                # Calculate match length as end - start (Python's re doesn't have length() method)
                match_length = match.end() - match.start()
                self.setFormat(match.start(), match_length, format)

class ZigHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Zig code"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # TODO: Implement Zig syntax highlighting rules

class PreviewTab(QWidget):
    """Base class for preview tabs with common functionality"""
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        self.setup_toolbar()
        
    def setup_toolbar(self):
        """Setup preview toolbar with common actions"""
        toolbar = QHBoxLayout()
        
        # Open with button
        open_with = QToolButton()
        open_with.setText("Open with...")
        open_with.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu()
        menu.aboutToShow.connect(lambda: self.populate_open_with_menu(menu))
        open_with.setMenu(menu)
        toolbar.addWidget(open_with)
        
        toolbar.addStretch()
        self.layout.addLayout(toolbar)
    
    def populate_open_with_menu(self, menu):
        """Populate the 'Open with' menu with system applications"""
        menu.clear()
        if hasattr(self.parent(), 'explorer'):
            apps = self.parent().explorer.get_system_applications(self.file_path)
            for app in apps:
                action = menu.addAction(app['name'])
                action.triggered.connect(
                    lambda checked, a=app: self.parent().explorer.open_with(self.file_path, a)
                )

    def cleanup(self):
        """Clean up resources when tab is closed"""
        pass
        
    def closeEvent(self, event):
        """Handle cleanup when tab is closed"""
        self.cleanup()
        super().closeEvent(event)

class TextPreviewTab(PreviewTab):
    """Enhanced text preview tab with line numbers and search"""
    def __init__(self, file_path, parent=None):
        super().__init__(file_path, parent)
        self.setup_ui()
        self.load_content()
    
    def setup_ui(self):
        """Setup text preview UI with additional controls"""
        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.returnPressed.connect(self.search_text)
        search_layout.addWidget(self.search_input)
        
        # Word wrap toggle
        self.wrap_button = QPushButton("Word Wrap")
        self.wrap_button.setCheckable(True)
        self.wrap_button.clicked.connect(self.toggle_word_wrap)
        search_layout.addWidget(self.wrap_button)
        
        self.layout.addLayout(search_layout)
        
        # Text editor with line numbers
        editor_layout = QHBoxLayout()
        
        self.line_numbers = QTextEdit()
        self.line_numbers.setFixedWidth(50)
        self.line_numbers.setReadOnly(True)
        editor_layout.addWidget(self.line_numbers)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.verticalScrollBar().valueChanged.connect(self.update_line_numbers)
        editor_layout.addWidget(self.text_edit)
        
        self.layout.addLayout(editor_layout)
        
        # Apply styling
        self.apply_style()
    
    def apply_style(self):
        """Apply dark theme styling"""
        style = """
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
                selection-color: #ffffff;
                padding: 8px;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: 1px solid #202020;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: 1px solid #202020;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:checked {
                background-color: #264f78;
            }
        """
        self.setStyleSheet(style)
        
        # Set monospace font
        font = QFont("Monospace", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(font)
        self.line_numbers.setFont(font)
    
    def load_content(self):
        """Load file content with encoding detection"""
        try:
            # Read first chunk to detect encoding
            with open(self.file_path, 'rb') as f:
                raw = f.read(4096)
                result = chardet.detect(raw)
                encoding = result['encoding'] or 'utf-8'
            
            # Read file in chunks
            content = []
            with open(self.file_path, 'r', encoding=encoding) as f:
                while chunk := f.read(1024*1024):  # 1MB chunks
                    content.append(chunk)
            
            self.text_edit.setPlainText(''.join(content))
            self.update_line_numbers()
            
            # Apply syntax highlighting
            ext = os.path.splitext(self.file_path)[1].lower()
            if hasattr(self.parent(), 'explorer'):
                # Clear previous highlighter if exists
                if hasattr(self.parent().explorer, 'syntax_highlighter'):
                    self.parent().explorer.syntax_highlighter.setDocument(None)
                
                if ext in ['.e', '.ie', '.oe', '.ey', '.ec']:
                    self.parent().explorer.syntax_highlighter = EHighlighter(self.text_edit.document())
                elif ext == '.md':
                    self.parent().explorer.syntax_highlighter = MarkdownHighlighter(self.text_edit.document())
                elif ext == '.py':
                    self.parent().explorer.syntax_highlighter = PythonHighlighter(self.text_edit.document())
            
        except Exception as e:
            if hasattr(self.parent(), 'explorer'):
                self.parent().explorer.show_error(f"Failed to load text file: {str(e)}")
            self.text_edit.setPlainText(f"Error loading file: {str(e)}")
    
    def update_line_numbers(self):
        """Update line numbers based on scroll position"""
        content = []
        
        # Use scrollbar position to determine visible lines
        scrollbar = self.text_edit.verticalScrollBar()
        scroll_pos = scrollbar.value()
        viewport_height = self.text_edit.viewport().height()
        
        # Calculate first visible line from scroll position
        line_height = self.text_edit.fontMetrics().height()
        first_visible_line = max(1, int(scroll_pos / line_height) + 1)
        
        # Calculate number of visible lines
        visible_lines = int(viewport_height / line_height) + 2  # Add a bit extra for safety
        
        # Generate line numbers
        for line_number in range(first_visible_line, first_visible_line + visible_lines):
            content.append(f"{line_number:4d}")
        
        self.line_numbers.setPlainText('\n'.join(content))
    
    def search_text(self):
        """Search for text in preview"""
        query = self.search_input.text()
        if not query:
            return
            
        cursor = self.text_edit.textCursor()
        current_pos = cursor.position()
        
        # Search from current position
        content = self.text_edit.toPlainText()
        next_pos = content.find(query, current_pos)
        
        if next_pos >= 0:
            # Found match
            cursor.setPosition(next_pos)
            cursor.setPosition(next_pos + len(query), QTextCursor.MoveMode.KeepAnchor)
            self.text_edit.setTextCursor(cursor)
        else:
            # Try from start if not found
            next_pos = content.find(query)
            if next_pos >= 0:
                cursor.setPosition(next_pos)
                cursor.setPosition(next_pos + len(query), QTextCursor.MoveMode.KeepAnchor)
                self.text_edit.setTextCursor(cursor)
    
    def toggle_word_wrap(self, checked):
        """Toggle word wrap mode"""
        self.text_edit.setWordWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere if checked
            else QTextOption.WrapMode.NoWrap
        )

class ImagePreviewTab(PreviewTab):
    """Enhanced image preview tab with zoom controls"""
    def __init__(self, file_path, parent=None):
        super().__init__(file_path, parent)
        self.setup_ui()
        self.load_image()
    
    def setup_ui(self):
        """Setup image preview UI with zoom controls"""
        # Zoom controls
        zoom_layout = QHBoxLayout()
        
        zoom_out = QPushButton("-")
        zoom_out.clicked.connect(lambda: self.zoom_image(-10))
        zoom_layout.addWidget(zoom_out)
        
        self.zoom_level = QSpinBox()
        self.zoom_level.setRange(10, 500)
        self.zoom_level.setValue(100)
        self.zoom_level.setSuffix("%")
        self.zoom_level.valueChanged.connect(self.update_zoom)
        zoom_layout.addWidget(self.zoom_level)
        
        zoom_in = QPushButton("+")
        zoom_in.clicked.connect(lambda: self.zoom_image(10))
        zoom_layout.addWidget(zoom_in)
        
        zoom_layout.addStretch()
        
        # Image info
        self.info_label = QLabel()
        zoom_layout.addWidget(self.info_label)
        
        self.layout.addLayout(zoom_layout)
        
        # Image display
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_area.setWidget(self.image_label)
        self.layout.addWidget(scroll_area)
    
    def load_image(self):
        """Load and display image"""
        try:
            self.original_pixmap = QPixmap(self.file_path)
            if self.original_pixmap.isNull():
                raise ValueError("Failed to load image")
            
            # Update info
            size = os.path.getsize(self.file_path)
            dimensions = self.original_pixmap.size()
            self.info_label.setText(
                f"{dimensions.width()}x{dimensions.height()} pixels, "
                f"{format_size(size)}"
            )
            
            self.update_zoom(100)
            
        except Exception as e:
            if hasattr(self.parent(), 'explorer'):
                self.parent().explorer.show_error(f"Failed to load image: {str(e)}")
            self.image_label.setText(f"Error loading image: {str(e)}")
    
    def zoom_image(self, delta):
        """Adjust zoom level by delta percent"""
        new_zoom = self.zoom_level.value() + delta
        self.zoom_level.setValue(new_zoom)
    
    def update_zoom(self, zoom):
        """Update image display with zoom level"""
        if not hasattr(self, 'original_pixmap'):
            return
            
        scaled_size = self.original_pixmap.size() * (zoom / 100.0)
        scaled_pixmap = self.original_pixmap.scaled(
            scaled_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

class ArchivePreviewTab(PreviewTab):
    """Preview tab for archive contents"""
    def __init__(self, file_path, parent=None):
        super().__init__(file_path, parent)
        self.setup_ui()
        self.load_archive()
    
    def setup_ui(self):
        """Setup archive preview UI"""
        # View mode toggle
        view_layout = QHBoxLayout()
        self.list_btn = QPushButton("List")
        self.list_btn.setCheckable(True)
        self.list_btn.setChecked(True)
        self.grid_btn = QPushButton("Grid")
        self.grid_btn.setCheckable(True)
        view_layout.addWidget(self.list_btn)
        view_layout.addWidget(self.grid_btn)
        view_layout.addStretch()
        self.layout.addLayout(view_layout)
        
        # Stacked widget for views
        self.stack = QStackedWidget()
        
        # List view
        self.list_view = QTreeWidget()
        self.list_view.setHeaderLabels(["Name", "Size", "Modified", "Type"])
        self.list_view.header().setStretchLastSection(False)
        self.list_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.stack.addWidget(self.list_view)
        
        # Grid view
        self.grid_scroll = QScrollArea()
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_scroll.setWidget(self.grid_widget)
        self.grid_scroll.setWidgetResizable(True)
        self.stack.addWidget(self.grid_scroll)
        
        self.layout.addWidget(self.stack)
        
        # Connect view toggle buttons
        self.list_btn.clicked.connect(lambda: self.switch_view(0))
        self.grid_btn.clicked.connect(lambda: self.switch_view(1))
        
        # Apply styling
        self.apply_style()
    
    def apply_style(self):
        """Apply dark theme styling"""
        style = """
            QTreeWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
            }
            QTreeWidget::item:selected {
                background-color: #264f78;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border: 1px solid #202020;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:checked {
                background-color: #264f78;
            }
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
        """
        self.setStyleSheet(style)
    
    def switch_view(self, index):
        """Switch between list and grid views"""
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.list_btn.setChecked(True)
            self.grid_btn.setChecked(False)
        else:
            self.list_btn.setChecked(False)
            self.grid_btn.setChecked(True)
    
    def load_archive(self):
        """Load and display archive contents"""
        try:
            if zipfile.is_zipfile(self.file_path):
                self.load_zip_archive()
            elif tarfile.is_tarfile(self.file_path):
                self.load_tar_archive()
            else:
                raise ValueError("Unsupported archive format")
        except Exception as e:
            if hasattr(self.parent(), 'explorer'):
                self.parent().explorer.show_error(f"Failed to load archive: {str(e)}")
    
    def load_zip_archive(self):
        """Load contents of ZIP archive"""
        with zipfile.ZipFile(self.file_path) as zf:
            # Load list view
            for info in zf.infolist():
                item = QTreeWidgetItem(self.list_view)
                item.setText(0, info.filename)
                item.setText(1, format_size(info.file_size))
                date = datetime(*info.date_time)
                item.setText(2, date.strftime('%Y-%m-%d %H:%M'))
                item.setText(3, self.get_file_type(info.filename))
                
                # Set icon based on file type
                icon = self.get_file_icon(info.filename)
                item.setIcon(0, icon)
            
            # Load grid view
            row = col = 0
            max_cols = 3  # Reduced from 4 to 3 to accommodate wider items
            for info in zf.infolist():
                preview = self.create_archive_item_preview(info)
                self.grid_layout.addWidget(preview, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            
            # Add spacing between grid items
            self.grid_layout.setSpacing(10)
    
    def load_tar_archive(self):
        """Load contents of TAR archive"""
        with tarfile.open(self.file_path) as tf:
            # Load list view
            for member in tf.getmembers():
                item = QTreeWidgetItem(self.list_view)
                item.setText(0, member.name)
                item.setText(1, format_size(member.size))
                date = datetime.fromtimestamp(member.mtime)
                item.setText(2, date.strftime('%Y-%m-%d %H:%M'))
                item.setText(3, self.get_file_type(member.name))
                
                # Set icon based on file type
                icon = self.get_file_icon(member.name)
                item.setIcon(0, icon)
            
            # Load grid view
            row = col = 0
            max_cols = 3  # Reduced from 4 to 3 to accommodate wider items
            for member in tf.getmembers():
                preview = self.create_archive_item_preview(member)
                self.grid_layout.addWidget(preview, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            
            # Add spacing between grid items
            self.grid_layout.setSpacing(10)
    
    def get_file_type(self, filename):
        """Get file type description based on extension"""
        ext = os.path.splitext(filename)[1].lower()
        types = {
            '.txt': 'Text File',
            '.py': 'Python Source',
            '.jpg': 'JPEG Image',
            '.png': 'PNG Image',
            '.pdf': 'PDF Document',
            '.zip': 'ZIP Archive',
            '.tar': 'TAR Archive',
            '.gz': 'GZip Archive'
        }
        return types.get(ext, 'File')
    
    def get_file_icon(self, filename):
        """Get appropriate icon for file type"""
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.py', '.pyw']:
            return QIcon.fromTheme('text-x-python')
        elif ext in ['.jpg', '.jpeg', '.png', '.gif']:
            return QIcon.fromTheme('image-x-generic')
        elif ext in ['.pdf']:
            return QIcon.fromTheme('application-pdf')
        elif ext in ['.zip', '.tar', '.gz']:
            return QIcon.fromTheme('package-x-generic')
        else:
            return QIcon.fromTheme('text-x-generic')
    
    def create_archive_item_preview(self, info):
        """Create preview widget for archive item"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(64, 64)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Get appropriate icon
        if isinstance(info, zipfile.ZipInfo):
            icon = self.get_file_icon(info.filename)
            name = os.path.basename(info.filename)
            size = format_size(info.file_size)
        else:  # tarfile.TarInfo
            icon = self.get_file_icon(info.name)
            name = os.path.basename(info.name)
            size = format_size(info.size)
        
        icon_label.setPixmap(icon.pixmap(64, 64))
        layout.addWidget(icon_label)
        
        # Name with better wrapping
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setMinimumHeight(40)  # Give more vertical space for wrapped text
        # Use rich text for better control
        name_label.setTextFormat(Qt.TextFormat.RichText)
        name_label.setText(f"<div style='text-align: center;'>{name}</div>")
        layout.addWidget(name_label)
        
        # Size
        size_label = QLabel(size)
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(size_label)
        
        widget.setFixedWidth(180)  # Increased from 120 to 180 for longer names
        return widget

    def cleanup(self):
        """Clean up archive preview resources"""
        # Clear grid layout
        if hasattr(self, 'grid_layout'):
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        
        # Clear list view
        if hasattr(self, 'list_view'):
            self.list_view.clear()
            
    def closeEvent(self, event):
        """Handle cleanup when archive preview is closed"""
        self.cleanup()
        super().closeEvent(event)

class FilePreview(QWidget):
    """Widget for previewing file contents"""
    
    # Signals
    preview_ready = pyqtSignal(str)  # Emitted when preview is ready
    preview_failed = pyqtSignal(str)  # Emitted when preview fails
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.setup_ui()
        
    def setup_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Preview tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_preview)
        layout.addWidget(self.tabs)
        
    def preview_file(self, path):
        """Create preview for file"""
        if not os.path.exists(path):
            return
            
        self.current_file = path
        
        try:
            # Get MIME type
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(path)
            
            # Create appropriate preview
            if mime_type.startswith('text/'):
                self._preview_text(path)
            elif mime_type.startswith('image/'):
                self._preview_image(path)
            elif mime_type in ['application/zip', 'application/x-zip-compressed']:
                self._preview_archive(path)
            else:
                self._preview_info(path, mime_type)
                
            self.preview_ready.emit(path)
            
        except Exception as e:
            self.preview_failed.emit(str(e))
            
    def _preview_text(self, path):
        """Preview text file with syntax highlighting"""
        editor = QTextEdit()
        editor.setReadOnly(True)
        
        try:
            with open(path, 'r') as f:
                content = f.read()
                
            # Apply syntax highlighting based on extension
            ext = os.path.splitext(path)[1].lower()
            if ext in ['.py', '.pyw']:
                highlighter = PythonHighlighter(editor.document())
            elif ext in ['.zig']:
                highlighter = ZigHighlighter(editor.document())
            elif ext in ['.md', '.markdown']:
                highlighter = MarkdownHighlighter(editor.document())
                
            editor.setPlainText(content)
            self.tabs.addTab(editor, os.path.basename(path))
            
        except Exception as e:
            self.preview_failed.emit(f"Failed to read text file: {str(e)}")
            
    def _preview_image(self, path):
        """Preview image file"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        image = QImage(path)
        if not image.isNull():
            pixmap = QPixmap.fromImage(image)
            # Scale if too large
            if pixmap.width() > 800 or pixmap.height() > 600:
                pixmap = pixmap.scaled(800, 600, Qt.AspectRatioMode.KeepAspectRatio)
            label.setPixmap(pixmap)
            
        scroll.setWidget(label)
        self.tabs.addTab(scroll, os.path.basename(path))
        
    def _preview_archive(self, path):
        """Preview archive contents"""
        editor = QTextEdit()
        editor.setReadOnly(True)
        
        try:
            with zipfile.ZipFile(path) as zf:
                content = []
                for info in zf.infolist():
                    content.append(f"{info.filename:<50} {info.file_size:>10} bytes")
                editor.setPlainText('\n'.join(content))
                
            self.tabs.addTab(editor, os.path.basename(path))
            
        except Exception as e:
            self.preview_failed.emit(f"Failed to read archive: {str(e)}")
            
    def _preview_info(self, path, mime_type):
        """Show basic file info when no preview available"""
        editor = QTextEdit()
        editor.setReadOnly(True)
        
        stat = os.stat(path)
        info = [
            f"File: {os.path.basename(path)}",
            f"Type: {mime_type}",
            f"Size: {stat.st_size} bytes",
            f"Created: {stat.st_ctime}",
            f"Modified: {stat.st_mtime}",
            f"Accessed: {stat.st_atime}",
        ]
        
        editor.setPlainText('\n'.join(info))
        self.tabs.addTab(editor, os.path.basename(path))
        
    def close_preview(self, index):
        """Close preview tab"""
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.current_file = None

def setup_preview(explorer, parent_widget):
    """Setup preview panel with tabs"""
    explorer.preview_tabs = QTabWidget()
    explorer.preview_tabs.setTabsClosable(True)
    explorer.preview_tabs.tabCloseRequested.connect(explorer.close_preview_tab)
    parent_widget.addWidget(explorer.preview_tabs)

def update_preview(explorer, file_path):
    """Update preview content based on file type"""
    if not file_path or not os.path.exists(file_path):
        return
        
    try:
        # Clear existing tabs
        while explorer.preview_tabs.count() > 0:
            explorer.preview_tabs.removeTab(0)
        
        # Create appropriate preview based on file type
        if is_archive(file_path):
            tab = ArchivePreviewTab(file_path, explorer.preview_tabs)
            name = os.path.basename(file_path)
            explorer.preview_tabs.addTab(tab, f"📦 {name}")
            explorer.preview_tabs.show()
        elif is_text_file(file_path):
            tab = TextPreviewTab(file_path, explorer.preview_tabs)
            name = os.path.basename(file_path)
            explorer.preview_tabs.addTab(tab, name)
            explorer.preview_tabs.show()
        elif is_image_file(file_path):
            tab = ImagePreviewTab(file_path, explorer.preview_tabs)
            name = os.path.basename(file_path)
            explorer.preview_tabs.addTab(tab, f"🖼️ {name}")
            explorer.preview_tabs.show()
        else:
            preview_default(explorer, file_path)
            explorer.preview_tabs.show()
            
        explorer.preview_tabs.setCurrentIndex(0)
            
    except Exception as e:
        explorer.show_error(f"Error previewing file: {str(e)}")
        explorer.preview_tabs.hide()

def preview_text_file(explorer, file_path):
    """Preview text file with syntax highlighting"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Create text preview widget
        text_preview = QTextEdit()
        text_preview.setReadOnly(True)
        
        # Set monospace font
        font = QFont("Monospace", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        text_preview.setFont(font)
        
        # Apply dark theme
        text_preview.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
                selection-color: #ffffff;
                padding: 8px;
            }
            QScrollBar:vertical {
                background: #1e1e1e;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #424242;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #525252;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
                background: none;
            }
        """)
        
        text_preview.setPlainText(content)
        
        # Apply syntax highlighting based on file type
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.e', '.ie', '.oe', '.ey', '.ec']:
            explorer.syntax_highlighter = EHighlighter(text_preview.document())
        elif ext == '.md':
            explorer.syntax_highlighter = MarkdownHighlighter(text_preview.document())
        elif ext == '.py':
            explorer.syntax_highlighter = PythonHighlighter(text_preview.document())
            
        # Add to preview tabs
        tab_name = os.path.basename(file_path)
        explorer.preview_tabs.addTab(text_preview, tab_name)
        explorer.preview_tabs.setCurrentIndex(explorer.preview_tabs.count() - 1)
            
    except Exception as e:
        explorer.show_error(f"Failed to preview text file: {e}")

def preview_archive(explorer, file_path):
    """Preview archive contents with list/grid views"""
    try:
        # Create preview widget with grid and list views
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        
        # Add view mode toggle
        view_mode = QHBoxLayout()
        list_btn = QPushButton("List View")
        grid_btn = QPushButton("Grid View")
        list_btn.setCheckable(True)
        grid_btn.setCheckable(True)
        list_btn.setChecked(True)
        view_mode.addWidget(list_btn)
        view_mode.addWidget(grid_btn)
        preview_layout.addLayout(view_mode)
        
        # Create stacked widget for views
        stack = QStackedWidget()
        
        # List view
        list_view = QTreeWidget()
        list_view.setHeaderLabels(["Name", "Size", "Modified", "Index"])
        stack.addWidget(list_view)
        
        # Grid view
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_scroll = QScrollArea()
        grid_scroll.setWidget(grid_widget)
        grid_scroll.setWidgetResizable(True)
        stack.addWidget(grid_scroll)
        
        preview_layout.addWidget(stack)
        
        # Connect view toggle buttons
        list_btn.clicked.connect(lambda: switch_archive_view(stack, 0, list_btn, grid_btn))
        grid_btn.clicked.connect(lambda: switch_archive_view(stack, 1, grid_btn, list_btn))
        
        # Load archive contents
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path) as zf:
                # Get archive index if available
                try:
                    with zf.open("index.json") as f:
                        index_data = json.load(f)
                except Exception as e:
                    print(f"Error reading archive index: {str(e)}")
                    index_data = None
                
                # Populate views
                row = 0
                col = 0
                max_cols = 4  # Number of items per row in grid view
                
                for info in zf.infolist():
                    # Convert ZIP date_time tuple to timestamp
                    date_time = datetime(*info.date_time)
                    
                    # List view item
                    item = QTreeWidgetItem([
                        info.filename,
                        format_size(info.file_size),
                        date_time.strftime('%Y-%m-%d %H:%M'),
                        str(index_data.get(info.filename, {}).get("index", "")) if index_data else ""
                    ])
                    list_view.addTopLevelItem(item)
                    
                    # Grid view item
                    preview = create_archive_item_preview(explorer, info, index_data)
                    grid_layout.addWidget(preview, row, col)
                    col += 1
                    if col >= max_cols:
                        col = 0
                        row += 1
        
        tab_name = os.path.basename(file_path)
        explorer.preview_tabs.addTab(preview_widget, f"📦 {tab_name}")
        explorer.preview_tabs.setCurrentIndex(explorer.preview_tabs.count() - 1)
        
    except Exception as e:
        explorer.show_error(f"Failed to preview archive: {e}")

def preview_image(explorer, file_path):
    """Preview image file"""
    try:
        # Create image preview widget
        preview_widget = QWidget()
        layout = QVBoxLayout(preview_widget)
        
        # Image label
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Load and scale image
        pixmap = QPixmap(file_path)
        scaled_pixmap = pixmap.scaled(
            explorer.preview_tabs.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        image_label.setPixmap(scaled_pixmap)
        
        # Add to layout
        layout.addWidget(image_label)
        
        # Add to preview tabs
        tab_name = os.path.basename(file_path)
        explorer.preview_tabs.addTab(preview_widget, f"🖼️ {tab_name}")
        explorer.preview_tabs.setCurrentIndex(explorer.preview_tabs.count() - 1)
        
    except Exception as e:
        explorer.show_error(f"Failed to preview image: {e}")

def preview_default(explorer, file_path):
    """Default preview for unsupported file types"""
    try:
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        
        text_preview = QTextEdit()
        text_preview.setReadOnly(True)
        text_preview.setPlainText(
            f"No preview available for {os.path.basename(file_path)}\n\n"
            f"File type: {mime_type}\n"
            f"Size: {format_size(os.path.getsize(file_path))}\n"
            f"Modified: {datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        tab_name = os.path.basename(file_path)
        explorer.preview_tabs.addTab(text_preview, tab_name)
    except Exception as e:
        explorer.show_error(f"Error creating default preview: {str(e)}")
        explorer.preview_tabs.hide()

def create_archive_item_preview(explorer, info, index_data=None):
    """Create a preview widget for an archive item"""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    
    # Icon/Preview
    icon_label = QLabel()
    icon_label.setFixedSize(64, 64)
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # Try to get preview from index
    if index_data and info.filename in index_data:
        item_data = index_data[info.filename]
        if "preview" in item_data:
            try:
                pixmap = QPixmap()
                pixmap.loadFromData(item_data["preview"])
                icon_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))
            except Exception as e:
                print(f"Error loading preview image: {str(e)}")
                pass
    
    # Fallback to default icon
    if icon_label.pixmap() is None:
        icon = explorer.model.fileIcon(explorer.model.index(info.filename))
        icon_label.setPixmap(icon.pixmap(64, 64))
    
    layout.addWidget(icon_label)
    
    # Filename (shortened if needed)
    name = os.path.basename(info.filename)
    if len(name) > 20:
        name = name[:17] + "..."
    name_label = QLabel(name)
    name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    name_label.setWordWrap(True)
    layout.addWidget(name_label)
    
    # Size
    size_label = QLabel(format_size(info.file_size))
    size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(size_label)
    
    # Index info if available
    if index_data and info.filename in index_data:
        index_label = QLabel(f"Index: {index_data[info.filename].get('index', '')}")
        index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(index_label)
    
    widget.setFixedWidth(120)
    return widget

def switch_archive_view(stack, index, active_btn, inactive_btn):
    """Switch between list and grid views in archive preview"""
    stack.setCurrentIndex(index)
    active_btn.setChecked(True)
    inactive_btn.setChecked(False)

def format_size(size):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"

def is_archive(path):
    """Check if file is an archive"""
    ext = os.path.splitext(path)[1].lower()
    return ext in ['.zip', '.tar', '.gz', '.bz2', '.rar']

def is_text_file(path):
    """Check if file is text"""
    ext = os.path.splitext(path)[1].lower()
    return ext in ['.txt', '.md', '.py', '.e', '.ie', '.oe', '.ey', '.ec',
                  '.json', '.xml', '.html', '.css', '.js']

def is_image_file(path):
    """Check if file is an image"""
    ext = os.path.splitext(path)[1].lower()
    return ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp'] 