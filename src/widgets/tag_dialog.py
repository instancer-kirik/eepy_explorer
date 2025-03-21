from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QLineEdit, QPushButton, QListWidget, QListWidgetItem,
                           QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt
import os
import json
import re

class TagDialog(QDialog):
    def __init__(self, explorer):
        super().__init__(explorer)
        self.explorer = explorer
        self.setWindowTitle("Manage Tags")
        self.setModal(True)
        self.setup_ui()
        self.load_tags()

    def setup_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout(self)
        
        # Add tag input
        input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Enter new tag")
        self.tag_input.returnPressed.connect(self.add_tag)
        input_layout.addWidget(self.tag_input)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_tag)
        input_layout.addWidget(add_btn)
        layout.addLayout(input_layout)
        
        # Tags list
        self.tags_list = QListWidget()
        self.tags_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.tags_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(self.rename_tag)
        button_layout.addWidget(rename_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_tag)
        button_layout.addWidget(delete_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)

    def load_tags(self):
        """Load all tags from notes"""
        self.tags_list.clear()
        tags = set()
        
        # Get all markdown files
        for root, _, files in os.walk(self.explorer.get_notes_vault_path()):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    file_tags = self.explorer.extract_tags_from_file(file_path)
                    tags.update(file_tags)
        
        # Add tags to list
        for tag in sorted(tags):
            item = QListWidgetItem(tag)
            self.tags_list.addItem(item)

    def add_tag(self):
        """Add a new tag"""
        tag = self.tag_input.text().strip()
        if not tag:
            return
            
        # Validate tag
        if not re.match(r'^[a-zA-Z0-9_-]+$', tag):
            QMessageBox.warning(self, "Invalid Tag", 
                              "Tags can only contain letters, numbers, underscores, and hyphens.")
            return
            
        # Check if tag already exists
        if self.tags_list.findItems(tag, Qt.MatchFlag.MatchExactly):
            QMessageBox.warning(self, "Tag Exists", "This tag already exists.")
            return
            
        # Add tag to list
        item = QListWidgetItem(tag)
        self.tags_list.addItem(item)
        self.tag_input.clear()
        
        # Sort list
        self.tags_list.sortItems()
        
        # If we're in notes mode and files are selected, offer to add the tag to them
        if hasattr(self.explorer, 'notes_mode_btn') and self.explorer.notes_mode_btn.isChecked():
            # Get selected files
            indexes = self.explorer.tree_view.selectedIndexes()
            selected_files = []
            
            for index in indexes:
                if index.column() == 0:  # Only process first column
                    item = self.explorer.notes_model.itemFromIndex(index)
                    if item:
                        path = item.data(Qt.ItemDataRole.UserRole)
                        if path and path.endswith('.md') and os.path.isfile(path):
                            selected_files.append(path)
            
            if selected_files:
                reply = QMessageBox.question(
                    self, 
                    "Add Tag to Files",
                    f"Do you want to add the tag '{tag}' to {len(selected_files)} selected file(s)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Add tag to each file
                    success_count = 0
                    modified_files = []
                    for file_path in selected_files:
                        if self.explorer.add_tag_to_file(file_path, tag):
                            success_count += 1
                            modified_files.append(file_path)
                    
                    # Show result and refresh only the modified files in the notes view
                    QMessageBox.information(
                        self,
                        "Tags Added",
                        f"Added tag '{tag}' to {success_count} out of {len(selected_files)} files."
                    )
                    
                    # Use the more efficient refresh method
                    if modified_files:
                        self.explorer.refresh_notes_tags(modified_files)

    def rename_tag(self):
        """Rename selected tag"""
        selected = self.tags_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a tag to rename.")
            return
            
        old_tag = selected[0].text()
        new_tag, ok = QInputDialog.getText(self, "Rename Tag", 
                                         "Enter new name:", text=old_tag)
        
        if ok and new_tag.strip():
            new_tag = new_tag.strip()
            
            # Validate new tag
            if not re.match(r'^[a-zA-Z0-9_-]+$', new_tag):
                QMessageBox.warning(self, "Invalid Tag", 
                                  "Tags can only contain letters, numbers, underscores, and hyphens.")
                return
                
            # Check if new tag already exists
            if self.tags_list.findItems(new_tag, Qt.MatchFlag.MatchExactly):
                QMessageBox.warning(self, "Tag Exists", "This tag already exists.")
                return
                
            # Rename tag in all files
            modified_files = self.rename_tag_in_files(old_tag, new_tag)
            
            # Update list
            selected[0].setText(new_tag)
            self.tags_list.sortItems()
            
            # Show status message
            if modified_files:
                QMessageBox.information(
                    self,
                    "Tags Renamed",
                    f"Renamed tag '{old_tag}' to '{new_tag}' in {len(modified_files)} files."
                )

    def delete_tag(self):
        """Delete selected tags"""
        selected = self.tags_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select tags to delete.")
            return
            
        reply = QMessageBox.question(self, "Confirm Delete",
                                   f"Are you sure you want to delete {len(selected)} tag(s)?",
                                   QMessageBox.StandardButton.Yes | 
                                   QMessageBox.StandardButton.No)
                                   
        if reply == QMessageBox.StandardButton.Yes:
            total_modified = 0
            for item in selected:
                tag = item.text()
                modified_files = self.delete_tag_from_files(tag)
                total_modified += len(modified_files)
                self.tags_list.takeItem(self.tags_list.row(item))
            
            # Show status message
            if total_modified > 0:
                QMessageBox.information(
                    self,
                    "Tags Deleted",
                    f"Deleted {len(selected)} tag(s) from {total_modified} files."
                )

    def rename_tag_in_files(self, old_tag, new_tag):
        """Rename tag in all markdown files"""
        modified_files = []
        for root, _, files in os.walk(self.explorer.get_notes_vault_path()):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        original_content = content
                            
                        # Replace in YAML front matter
                        if content.startswith('---'):
                            parts = content.split('---')
                            if len(parts) >= 3:
                                front_matter = parts[1]
                                if 'tags:' in front_matter:
                                    front_matter = front_matter.replace(
                                        f' {old_tag},', f' {new_tag},'
                                    ).replace(
                                        f' {old_tag}\n', f' {new_tag}\n'
                                    ).replace(
                                        f'"{old_tag}"', f'"{new_tag}"'
                                    )
                                parts[1] = front_matter
                                content = '---'.join(parts)
                        
                        # Replace inline tags
                        content = content.replace(f'#{old_tag}', f'#{new_tag}')
                        
                        # Only write if content changed
                        if content != original_content:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            modified_files.append(file_path)
                            
                    except Exception as e:
                        QMessageBox.warning(self, "Error", 
                                          f"Error updating {file}: {str(e)}")
        
        # Refresh the modified files in the notes model
        if modified_files and hasattr(self.explorer, 'notes_model'):
            self.explorer.refresh_notes_tags(modified_files)
        
        return modified_files

    def delete_tag_from_files(self, tag):
        """Delete tag from all markdown files"""
        modified_files = []
        for root, _, files in os.walk(self.explorer.get_notes_vault_path()):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        original_content = content
                            
                        # Remove from YAML front matter
                        if content.startswith('---'):
                            parts = content.split('---')
                            if len(parts) >= 3:
                                front_matter = parts[1]
                                if 'tags:' in front_matter:
                                    # Remove tag from comma-separated list
                                    front_matter = re.sub(
                                        f'\\s*{tag}\\s*,?', '', front_matter
                                    ).replace(',,', ',').replace('", ]', '"]')
                                    
                                    # Clean up empty tags line
                                    if 'tags:' in front_matter and not re.search(r'tags:\s*[^\s]', front_matter):
                                        front_matter = re.sub(r'tags:.*\n?', '', front_matter)
                                    
                                    # Fix trailing commas
                                    front_matter = re.sub(r',\s*\]', ']', front_matter)
                                    
                                parts[1] = front_matter
                                content = '---'.join(parts)
                        
                        # Remove inline tags
                        content = re.sub(f'\\s*#{tag}\\b', '', content)
                        
                        # Only write if content changed
                        if content != original_content:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            modified_files.append(file_path)
                            
                    except Exception as e:
                        QMessageBox.warning(self, "Error", 
                                          f"Error updating {file}: {str(e)}")
        
        # Refresh the modified files in the notes model
        if modified_files and hasattr(self.explorer, 'notes_model'):
            self.explorer.refresh_notes_tags(modified_files)
            
        return modified_files 