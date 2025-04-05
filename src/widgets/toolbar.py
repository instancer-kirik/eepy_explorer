from PyQt6.QtWidgets import (QPushButton, QWidget, QHBoxLayout, 
                           QSizePolicy, QLabel, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

def setup_toolbar(explorer, toolbar_layout):
    """Setup toolbar buttons with modern styling"""
    # Apply base toolbar styling
    toolbar_layout.setSpacing(4)
    toolbar_layout.setContentsMargins(4, 4, 4, 4)

    # Style sheet for toolbar buttons
    button_style = """
        QPushButton {
            border: none;
            border-radius: 4px;
            padding: 6px;
            background: transparent;
            min-width: 32px;
            min-height: 32px;
        }
        QPushButton:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        QPushButton:pressed {
            background: rgba(255, 255, 255, 0.2);
        }
        QPushButton:checked {
            background: rgba(255, 255, 255, 0.15);
        }
        QPushButton:disabled {
            opacity: 0.5;
        }
    """

    # Navigation group
    nav_group = create_nav_group(explorer, button_style)
    toolbar_layout.addWidget(nav_group)
    add_toolbar_separator(toolbar_layout)

    # File operations group
    file_ops = create_file_ops_group(explorer, button_style)
    toolbar_layout.addWidget(file_ops)
    add_toolbar_separator(toolbar_layout)

    # Project operations group
    project_ops = create_project_ops_group(explorer, button_style)
    toolbar_layout.addWidget(project_ops)
    add_toolbar_separator(toolbar_layout)
    
    # Notes operations group
    notes_ops = create_notes_ops_group(explorer, button_style)
    toolbar_layout.addWidget(notes_ops)
    add_toolbar_separator(toolbar_layout)

    # Development tools group
    dev_tools = create_dev_tools_group(explorer, button_style)
    toolbar_layout.addWidget(dev_tools)
    add_toolbar_separator(toolbar_layout)

    # Testing and documentation group
    test_docs = create_test_docs_group(explorer, button_style)
    toolbar_layout.addWidget(test_docs)

    # Add flexible spacer
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    toolbar_layout.addWidget(spacer)

    # Project type indicator (right-aligned)
    explorer.project_type = QLabel()
    explorer.project_type.setStyleSheet("QLabel { padding: 4px; }")
    toolbar_layout.addWidget(explorer.project_type)

def create_nav_group(explorer, button_style):
    """Create navigation button group"""
    nav_group = QWidget()
    nav_layout = QHBoxLayout(nav_group)
    nav_layout.setContentsMargins(0, 0, 0, 0)
    nav_layout.setSpacing(2)

    # Mode switching
    explorer.file_mode_btn = QPushButton("File")
    explorer.file_mode_btn.setIcon(QIcon.fromTheme("folder"))
    explorer.file_mode_btn.setCheckable(True)
    explorer.file_mode_btn.setChecked(True)
    explorer.file_mode_btn.setToolTip("File Explorer Mode")
    explorer.file_mode_btn.clicked.connect(lambda: explorer.switch_mode('file'))
    explorer.file_mode_btn.setStyleSheet(button_style)
    nav_layout.addWidget(explorer.file_mode_btn)

    explorer.project_mode_btn = QPushButton("Project")
    explorer.project_mode_btn.setIcon(QIcon.fromTheme("project"))
    explorer.project_mode_btn.setCheckable(True)
    explorer.project_mode_btn.setToolTip("Project Mode")
    explorer.project_mode_btn.clicked.connect(lambda: explorer.switch_mode('project'))
    explorer.project_mode_btn.setStyleSheet(button_style)
    nav_layout.addWidget(explorer.project_mode_btn)
    
    explorer.notes_mode_btn = QPushButton("Notes")
    explorer.notes_mode_btn.setIcon(QIcon.fromTheme("text-x-markdown"))
    explorer.notes_mode_btn.setCheckable(True)
    explorer.notes_mode_btn.setToolTip("Notes Vault Mode")
    explorer.notes_mode_btn.clicked.connect(lambda: explorer.switch_mode('notes'))
    explorer.notes_mode_btn.setStyleSheet(button_style)
    nav_layout.addWidget(explorer.notes_mode_btn)

    # Add separator
    add_toolbar_separator(nav_layout)

    # View switching
    explorer.list_view_btn = QPushButton("List")
    explorer.list_view_btn.setIcon(QIcon.fromTheme("view-list-symbolic"))
    explorer.list_view_btn.setCheckable(True)
    explorer.list_view_btn.setChecked(True)
    explorer.list_view_btn.setToolTip("List View")
    explorer.list_view_btn.clicked.connect(lambda: explorer.switch_view_mode('list'))
    explorer.list_view_btn.setStyleSheet(button_style)
    nav_layout.addWidget(explorer.list_view_btn)

    explorer.grid_view_btn = QPushButton("Grid")
    explorer.grid_view_btn.setIcon(QIcon.fromTheme("view-grid-symbolic"))
    explorer.grid_view_btn.setCheckable(True)
    explorer.grid_view_btn.setToolTip("Grid View")
    explorer.grid_view_btn.clicked.connect(lambda: explorer.switch_view_mode('grid'))
    explorer.grid_view_btn.setStyleSheet(button_style)
    nav_layout.addWidget(explorer.grid_view_btn)

    return nav_group

def create_file_ops_group(explorer, button_style):
    """Create file operations button group"""
    file_ops = QWidget()
    file_ops_layout = QHBoxLayout(file_ops)
    file_ops_layout.setContentsMargins(0, 0, 0, 0)
    file_ops_layout.setSpacing(2)

    explorer.copy_button = QPushButton("Copy")
    explorer.copy_button.setIcon(QIcon.fromTheme("edit-copy"))
    explorer.copy_button.setToolTip("Copy (Ctrl+C)")
    explorer.copy_button.clicked.connect(explorer.file_ops.copy_selected_files)
    explorer.copy_button.setShortcut("Ctrl+C")
    explorer.copy_button.setStyleSheet(button_style)
    file_ops_layout.addWidget(explorer.copy_button)

    explorer.cut_button = QPushButton("Cut")
    explorer.cut_button.setIcon(QIcon.fromTheme("edit-cut"))
    explorer.cut_button.setToolTip("Cut (Ctrl+X)")
    explorer.cut_button.clicked.connect(explorer.file_ops.cut_selected_files)
    explorer.cut_button.setShortcut("Ctrl+X")
    explorer.cut_button.setStyleSheet(button_style)
    file_ops_layout.addWidget(explorer.cut_button)

    explorer.paste_button = QPushButton("Paste")
    explorer.paste_button.setIcon(QIcon.fromTheme("edit-paste"))
    explorer.paste_button.setToolTip("Paste (Ctrl+V)")
    explorer.paste_button.clicked.connect(explorer.file_ops.paste_files)
    explorer.paste_button.setShortcut("Ctrl+V")
    explorer.paste_button.setEnabled(False)
    explorer.paste_button.setStyleSheet(button_style)
    file_ops_layout.addWidget(explorer.paste_button)

    return file_ops

def create_project_ops_group(explorer, button_style):
    """Create project operations button group"""
    project_ops = QWidget()
    project_ops_layout = QHBoxLayout(project_ops)
    project_ops_layout.setContentsMargins(0, 0, 0, 0)
    project_ops_layout.setSpacing(2)

    explorer.vcs_button = QPushButton("VCS")
    explorer.vcs_button.setIcon(QIcon.fromTheme("git"))
    explorer.vcs_button.setToolTip("Version Control")
    explorer.vcs_button.clicked.connect(explorer.vcs_manager.open_vcs)
    explorer.vcs_button.setStyleSheet(button_style)
    project_ops_layout.addWidget(explorer.vcs_button)

    explorer.build_button = QPushButton("Build")
    explorer.build_button.setIcon(QIcon.fromTheme("system-run"))
    explorer.build_button.setToolTip("Build Project")
    explorer.build_button.clicked.connect(explorer.build_manager.build_project)
    explorer.build_button.setStyleSheet(button_style)
    project_ops_layout.addWidget(explorer.build_button)

    return project_ops

def create_dev_tools_group(explorer, button_style):
    """Create development tools button group"""
    dev_tools = QWidget()
    dev_tools_layout = QHBoxLayout(dev_tools)
    dev_tools_layout.setContentsMargins(0, 0, 0, 0)
    dev_tools_layout.setSpacing(2)

    explorer.smelt_button = QPushButton("Smelt")
    explorer.smelt_button.setIcon(QIcon.fromTheme("media-playback-start"))
    explorer.smelt_button.setToolTip(
        "Smelt - Development Mode\n\n"
        "Like metallurgy's smelting process that keeps metal hot and workable,\n"
        "this mode keeps your code 'molten' for hot-reloading during development.\n\n"
        "Shortcut: Ctrl+R")
    explorer.smelt_button.clicked.connect(explorer.build_manager.smelt_system)
    explorer.smelt_button.setShortcut("Ctrl+R")
    explorer.smelt_button.setStyleSheet(button_style)
    dev_tools_layout.addWidget(explorer.smelt_button)

    explorer.cast_button = QPushButton("Cast")
    explorer.cast_button.setIcon(QIcon.fromTheme("system-software-install"))
    explorer.cast_button.setToolTip(
        "Cast - Development Build\n\n"
        "Like casting molten metal into a mold,\n"
        "this creates a development build with debug symbols.\n\n"
        "Shortcut: Ctrl+B")
    explorer.cast_button.clicked.connect(explorer.build_manager.cast_system)
    explorer.cast_button.setShortcut("Ctrl+B")
    explorer.cast_button.setStyleSheet(button_style)
    dev_tools_layout.addWidget(explorer.cast_button)

    explorer.forge_button = QPushButton("Forge")
    explorer.forge_button.setIcon(QIcon.fromTheme("emblem-system"))
    explorer.forge_button.setToolTip(
        "Forge - Production Build\n\n"
        "Like forging metal to make it stronger,\n"
        "this creates an optimized production build.\n\n"
        "Shortcut: Ctrl+Shift+B")
    explorer.forge_button.clicked.connect(explorer.build_manager.forge_system)
    explorer.forge_button.setShortcut("Ctrl+Shift+B")
    explorer.forge_button.setStyleSheet(button_style)
    dev_tools_layout.addWidget(explorer.forge_button)

    return dev_tools

def create_test_docs_group(explorer, button_style):
    """Create testing and documentation button group"""
    test_docs = QWidget()
    test_docs_layout = QHBoxLayout(test_docs)
    test_docs_layout.setContentsMargins(0, 0, 0, 0)
    test_docs_layout.setSpacing(2)

    explorer.contract_button = QPushButton("Contract")
    explorer.contract_button.setIcon(QIcon.fromTheme("dialog-question"))
    explorer.contract_button.setToolTip("Verify Contracts")
    explorer.contract_button.clicked.connect(explorer.build_manager.verify_contracts)
    explorer.contract_button.setStyleSheet(button_style)
    test_docs_layout.addWidget(explorer.contract_button)

    explorer.doc_button = QPushButton("Docs")
    explorer.doc_button.setIcon(QIcon.fromTheme("text-x-generic"))
    explorer.doc_button.setToolTip("Generate Documentation")
    explorer.doc_button.clicked.connect(explorer.build_manager.generate_docs)
    explorer.doc_button.setStyleSheet(button_style)
    test_docs_layout.addWidget(explorer.doc_button)

    explorer.test_button = QPushButton("Test")
    explorer.test_button.setIcon(QIcon.fromTheme("system-run"))
    explorer.test_button.setToolTip("Run Tests")
    explorer.test_button.clicked.connect(explorer.test_tool.run_tests)
    explorer.test_button.setStyleSheet(button_style)
    test_docs_layout.addWidget(explorer.test_button)

    return test_docs

def create_notes_ops_group(explorer, button_style):
    """Create notes operations button group"""
    notes_ops = QWidget()
    notes_ops_layout = QHBoxLayout(notes_ops)
    notes_ops_layout.setContentsMargins(0, 0, 0, 0)
    notes_ops_layout.setSpacing(2)

    explorer.tag_button = QPushButton("Tags")
    explorer.tag_button.setIcon(QIcon.fromTheme("tag"))
    explorer.tag_button.setToolTip("Manage Tags")
    explorer.tag_button.clicked.connect(lambda: explorer.manage_tags())
    explorer.tag_button.setStyleSheet(button_style)
    notes_ops_layout.addWidget(explorer.tag_button)

    explorer.find_dupes_button = QPushButton("Duplicates")
    explorer.find_dupes_button.setIcon(QIcon.fromTheme("edit-copy"))
    explorer.find_dupes_button.setToolTip("Find Duplicate Notes")
    explorer.find_dupes_button.clicked.connect(explorer.find_duplicate_notes)
    explorer.find_dupes_button.setStyleSheet(button_style)
    notes_ops_layout.addWidget(explorer.find_dupes_button)

    explorer.sort_button = QPushButton("Sort")
    explorer.sort_button.setIcon(QIcon.fromTheme("view-sort-ascending"))
    explorer.sort_button.setToolTip("Sort Notes")
    explorer.sort_button.clicked.connect(lambda: explorer.sort_notes())
    explorer.sort_button.setStyleSheet(button_style)
    notes_ops_layout.addWidget(explorer.sort_button)

    explorer.search_notes_button = QPushButton("Search")
    explorer.search_notes_button.setIcon(QIcon.fromTheme("edit-find"))
    explorer.search_notes_button.setToolTip("Search Notes Content")
    explorer.search_notes_button.clicked.connect(lambda: explorer.search_notes_content())
    explorer.search_notes_button.setStyleSheet(button_style)
    notes_ops_layout.addWidget(explorer.search_notes_button)
    
    # Add create note button
    explorer.create_note_button = QPushButton("New Note")
    explorer.create_note_button.setIcon(QIcon.fromTheme("document-new"))
    explorer.create_note_button.setToolTip("Create a New Note")
    explorer.create_note_button.clicked.connect(lambda: explorer.create_new_note())
    explorer.create_note_button.setStyleSheet(button_style)
    notes_ops_layout.addWidget(explorer.create_note_button)

    return notes_ops

def add_toolbar_separator(layout):
    """Add a vertical separator line to the toolbar"""
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.VLine)
    separator.setFrameShadow(QFrame.Shadow.Sunken)
    separator.setStyleSheet("QFrame { color: rgba(255, 255, 255, 0.1); margin: 4px 8px; }")
    layout.addWidget(separator) 