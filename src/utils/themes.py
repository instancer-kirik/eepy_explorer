def setup_theme(explorer):
    """Setup dark theme for all components"""
    explorer.setStyleSheet("""
        QMainWindow, QWidget {
            background: #1e1e1e;
            color: #d4d4d4;
        }
        
        QTreeView, QListView {
            background: #1e1e1e;
            color: #d4d4d4;
            border: none;
            selection-background-color: #264f78;
            selection-color: #ffffff;
        }
        
        QTreeView::item, QListView::item {
            padding: 4px;
            border-radius: 4px;
            color: #d4d4d4;
        }
        
        QTreeView::item:hover, QListView::item:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        QTreeView::item:selected, QListView::item:selected {
            background: #264f78;
        }
        
        QHeaderView::section {
            background: #252526;
            color: #d4d4d4;
            padding: 6px;
            border: none;
        }
        
        QStatusBar {
            background: #252526;
            color: #d4d4d4;
            border-top: 1px solid #333333;
        }
        
        QLabel {
            color: #d4d4d4;
        }
        
        QToolTip {
            background: #252526;
            color: #d4d4d4;
            border: 1px solid #333333;
            padding: 4px;
        }
        
        QPushButton {
            background: #2d2d2d;
            color: #d4d4d4;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 6px;
            min-width: 80px;
        }
        
        QPushButton:hover {
            background: #3d3d3d;
        }
        
        QPushButton:pressed {
            background: #4d4d4d;
        }
        
        QPushButton:disabled {
            background: #2d2d2d;
            color: #6d6d6d;
            border: 1px solid #3d3d3d;
        }
        
        QLineEdit {
            background: #1e1e1e;
            color: #d4d4d4;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 4px;
        }
        
        QLineEdit:focus {
            border: 1px solid #264f78;
        }
        
        QProgressBar {
            background: #1e1e1e;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            text-align: center;
        }
        
        QProgressBar::chunk {
            background: #264f78;
            border-radius: 3px;
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
        
        QScrollBar:horizontal {
            background: #1e1e1e;
            height: 12px;
            margin: 0;
        }
        
        QScrollBar::handle:horizontal {
            background: #424242;
            border-radius: 6px;
            min-width: 20px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background: #525252;
        }
        
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0;
            background: none;
        }
        
        QTabWidget::pane {
            border: 1px solid #3d3d3d;
            background: #1e1e1e;
        }
        
        QTabBar::tab {
            background: #2d2d2d;
            color: #d4d4d4;
            border: 1px solid #3d3d3d;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 6px 10px;
            margin-right: 2px;
        }
        
        QTabBar::tab:selected {
            background: #1e1e1e;
            border-bottom: none;
        }
        
        QTabBar::tab:hover {
            background: #3d3d3d;
        }
        
        QTabBar::close-button {
            image: url(close.png);
            subcontrol-position: right;
            subcontrol-origin: padding;
            margin-left: 4px;
        }
        
        QTabBar::close-button:hover {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 2px;
        }
        
        QSplitter::handle {
            background: #3d3d3d;
        }
        
        QSplitter::handle:horizontal {
            width: 1px;
        }
        
        QSplitter::handle:vertical {
            height: 1px;
        }
        
        QMenu {
            background: #1e1e1e;
            color: #d4d4d4;
            border: 1px solid #3d3d3d;
        }
        
        QMenu::item {
            padding: 6px 20px;
        }
        
        QMenu::item:selected {
            background: #264f78;
        }
        
        QMenu::separator {
            height: 1px;
            background: #3d3d3d;
            margin: 4px 0;
        }
        
        QComboBox {
            background: #2d2d2d;
            color: #d4d4d4;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 4px;
            min-width: 80px;
        }
        
        QComboBox:hover {
            background: #3d3d3d;
        }
        
        QComboBox:on {
            background: #4d4d4d;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        
        QComboBox::down-arrow {
            image: url(down-arrow.png);
        }
        
        QComboBox QAbstractItemView {
            background: #1e1e1e;
            color: #d4d4d4;
            border: 1px solid #3d3d3d;
            selection-background-color: #264f78;
            selection-color: #ffffff;
        }
    """) 