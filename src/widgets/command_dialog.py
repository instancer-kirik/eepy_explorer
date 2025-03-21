from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                           QTreeWidget, QTreeWidgetItem, QLabel, QLineEdit,
                           QTextEdit, QTabWidget, QWidget, QInputDialog, QMessageBox,
                           QMenu, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from datetime import datetime

class CommandDialog(QDialog):
    """Dialog for managing saved commands"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.command_manager = parent.command_manager if parent else None
        self.setup_ui()
        self.load_commands()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Command Manager")
        self.resize(800, 600)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Commands tab
        commands_widget = QWidget()
        commands_layout = QVBoxLayout(commands_widget)
        
        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.filter_commands)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        commands_layout.addLayout(search_layout)
        
        # Command list
        self.command_tree = QTreeWidget()
        self.command_tree.setHeaderLabels(["Name", "Description", "Tags"])
        self.command_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.command_tree.customContextMenuRequested.connect(self.show_command_context_menu)
        self.command_tree.itemDoubleClicked.connect(self.edit_command)
        commands_layout.addWidget(self.command_tree)
        
        # Buttons
        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add Command")
        add_btn.clicked.connect(self.add_command)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self.edit_command(self.command_tree.currentItem()))
        button_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_command)
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        commands_layout.addLayout(button_layout)
        
        self.tab_widget.addTab(commands_widget, "Commands")
        
        # Tags tab
        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)
        
        # Tag list
        self.tag_tree = QTreeWidget()
        self.tag_tree.setHeaderLabels(["Tag", "Command Count"])
        tags_layout.addWidget(self.tag_tree)
        
        # Tag buttons
        tag_button_layout = QHBoxLayout()
        add_tag_btn = QPushButton("Add Tag")
        add_tag_btn.clicked.connect(self.add_tag)
        tag_button_layout.addWidget(add_tag_btn)
        
        delete_tag_btn = QPushButton("Delete Tag")
        delete_tag_btn.clicked.connect(self.delete_tag)
        tag_button_layout.addWidget(delete_tag_btn)
        
        tag_button_layout.addStretch()
        tags_layout.addLayout(tag_button_layout)
        
        self.tab_widget.addTab(tags_widget, "Tags")
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
    def load_commands(self):
        """Load commands into the tree widget"""
        self.command_tree.clear()
        self.tag_tree.clear()
        
        if not self.command_manager:
            return
            
        # Load commands
        for name, cmd in self.command_manager.get_all_commands().items():
            item = QTreeWidgetItem([
                name,
                cmd.get('description', ''),
                ', '.join(cmd.get('tags', []))
            ])
            self.command_tree.addTopLevelItem(item)
            
        # Load tags
        tag_counts = {}
        for cmd in self.command_manager.get_all_commands().values():
            for tag in cmd.get('tags', []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                
        for tag, count in tag_counts.items():
            item = QTreeWidgetItem([tag, str(count)])
            self.tag_tree.addTopLevelItem(item)
            
        # Resize columns
        for i in range(3):
            self.command_tree.resizeColumnToContents(i)
        for i in range(2):
            self.tag_tree.resizeColumnToContents(i)
            
    def filter_commands(self):
        """Filter commands based on search text"""
        search_text = self.search_input.text().lower()
        
        for i in range(self.command_tree.topLevelItemCount()):
            item = self.command_tree.topLevelItem(i)
            name = item.text(0).lower()
            desc = item.text(1).lower()
            tags = item.text(2).lower()
            
            item.setHidden(
                search_text not in name and
                search_text not in desc and
                search_text not in tags
            )
            
    def add_command(self):
        """Add a new command"""
        if not self.command_manager:
            return
            
        name, ok = QInputDialog.getText(
            self, "Add Command", "Command Name:"
        )
        if not ok or not name:
            return
            
        if name in self.command_manager.get_all_commands():
            QMessageBox.warning(
                self,
                "Error",
                f"Command '{name}' already exists!"
            )
            return
            
        cmd, ok = QInputDialog.getText(
            self, "Add Command", "Command:"
        )
        if not ok or not cmd:
            return
            
        desc, ok = QInputDialog.getText(
            self, "Add Command", "Description:"
        )
        if not ok:
            desc = ""
            
        tags, ok = QInputDialog.getText(
            self, "Add Command", "Tags (comma separated):"
        )
        if not ok:
            tags = ""
            
        self.command_manager.add_command(
            name,
            cmd,
            description=desc,
            tags=[t.strip() for t in tags.split(',') if t.strip()]
        )
        
        self.load_commands()
        
    def edit_command(self, item):
        """Edit an existing command"""
        if not item or not self.command_manager:
            return
            
        name = item.text(0)
        cmd = self.command_manager.get_command(name)
        if not cmd:
            return
            
        new_cmd, ok = QInputDialog.getText(
            self, "Edit Command", "Command:",
            text=cmd['command']
        )
        if not ok:
            return
            
        new_desc, ok = QInputDialog.getText(
            self, "Edit Command", "Description:",
            text=cmd.get('description', '')
        )
        if not ok:
            return
            
        new_tags, ok = QInputDialog.getText(
            self, "Edit Command", "Tags (comma separated):",
            text=', '.join(cmd.get('tags', []))
        )
        if not ok:
            return
            
        self.command_manager.add_command(
            name,
            new_cmd,
            description=new_desc,
            tags=[t.strip() for t in new_tags.split(',') if t.strip()]
        )
        
        self.load_commands()
        
    def delete_command(self):
        """Delete selected command"""
        item = self.command_tree.currentItem()
        if not item or not self.command_manager:
            return
            
        name = item.text(0)
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete command '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.command_manager.remove_command(name)
            self.load_commands()
            
    def show_command_context_menu(self, position):
        """Show context menu for command items"""
        item = self.command_tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu()
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self.edit_command(item))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_command)
        
        menu.exec(self.command_tree.mapToGlobal(position))
        
    def add_tag(self):
        """Add a new tag to selected command"""
        item = self.command_tree.currentItem()
        if not item or not self.command_manager:
            return
            
        name = item.text(0)
        cmd = self.command_manager.get_command(name)
        if not cmd:
            return
            
        tag, ok = QInputDialog.getText(
            self, "Add Tag", "New Tag:"
        )
        if not ok or not tag:
            return
            
        tags = cmd.get('tags', [])
        if tag not in tags:
            tags.append(tag)
            self.command_manager.add_command(
                name,
                cmd['command'],
                description=cmd.get('description', ''),
                tags=tags
            )
            self.load_commands()
            
    def delete_tag(self):
        """Delete selected tag from all commands"""
        item = self.tag_tree.currentItem()
        if not item or not self.command_manager:
            return
            
        tag = item.text(0)
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete tag '{tag}' from all commands?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            commands = self.command_manager.get_all_commands()
            for name, cmd in commands.items():
                tags = cmd.get('tags', [])
                if tag in tags:
                    tags.remove(tag)
                    self.command_manager.add_command(
                        name,
                        cmd['command'],
                        description=cmd.get('description', ''),
                        tags=tags
                    )
            self.load_commands() 