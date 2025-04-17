from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QComboBox, QCheckBox, QProgressBar,
                            QMessageBox, QFileDialog, QListWidget, QListWidgetItem,
                            QGroupBox, QRadioButton, QDialogButtonBox, QTableWidget,
                            QTableWidgetItem, QHeaderView, QSplitter, QAbstractItemView,
                            QTimeEdit, QSpinBox)
from PyQt6.QtCore import Qt, QTime, pyqtSignal
import os
import time
from datetime import datetime, timedelta

class SyncSchedulerDialog(QDialog):
    """Dialog for managing scheduled directory synchronization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sync Scheduler")
        self.resize(700, 500)
        self.setModal(True)
        
        # Get sync manager and scheduler
        from ..utils.sync_manager import DirectorySyncManager, DirectorySyncScheduler
        if not hasattr(parent, 'sync_manager'):
            parent.sync_manager = DirectorySyncManager(parent)
            
        if not hasattr(parent.sync_manager, 'scheduler'):
            parent.sync_manager.scheduler = DirectorySyncScheduler(parent)
            
        self.scheduler = parent.sync_manager.scheduler
        
        self.setup_ui()
        self.load_scheduled_tasks()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Scheduled tasks list
        tasks_group = QGroupBox("Scheduled Sync Tasks")
        tasks_layout = QVBoxLayout(tasks_group)
        
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(5)
        self.tasks_table.setHorizontalHeaderLabels(["Source", "Target", "Options", "Status", "Last Sync"])
        self.tasks_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tasks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tasks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tasks_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tasks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tasks_layout.addWidget(self.tasks_table)
        
        # Task buttons
        task_buttons_layout = QHBoxLayout()
        
        self.add_task_button = QPushButton("Add Task")
        self.add_task_button.clicked.connect(self.add_task)
        task_buttons_layout.addWidget(self.add_task_button)
        
        self.edit_task_button = QPushButton("Edit Task")
        self.edit_task_button.clicked.connect(self.edit_task)
        task_buttons_layout.addWidget(self.edit_task_button)
        
        self.remove_task_button = QPushButton("Remove Task")
        self.remove_task_button.clicked.connect(self.remove_task)
        task_buttons_layout.addWidget(self.remove_task_button)
        
        self.run_now_button = QPushButton("Run Now")
        self.run_now_button.clicked.connect(self.run_task_now)
        task_buttons_layout.addWidget(self.run_now_button)
        
        tasks_layout.addLayout(task_buttons_layout)
        layout.addWidget(tasks_group)
        
        # Sync schedule settings
        schedule_group = QGroupBox("Sync Schedule")
        schedule_layout = QHBoxLayout(schedule_group)
        
        schedule_layout.addWidget(QLabel("Sync Interval:"))
        
        self.interval_hours = QSpinBox()
        self.interval_hours.setRange(0, 24)
        self.interval_hours.setValue(1)
        self.interval_hours.valueChanged.connect(self.update_schedule)
        schedule_layout.addWidget(self.interval_hours)
        schedule_layout.addWidget(QLabel("hours"))
        
        self.interval_minutes = QSpinBox()
        self.interval_minutes.setRange(0, 59)
        self.interval_minutes.setValue(0)
        self.interval_minutes.valueChanged.connect(self.update_schedule)
        schedule_layout.addWidget(self.interval_minutes)
        schedule_layout.addWidget(QLabel("minutes"))
        
        schedule_layout.addStretch()
        layout.addWidget(schedule_group)
        
        # Status and buttons
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        
        # Update UI state
        self.update_ui_state()
        
    def load_scheduled_tasks(self):
        """Load and display scheduled tasks"""
        self.tasks_table.setRowCount(0)
        
        # Load saved tasks if available
        if hasattr(self.scheduler, 'load_tasks'):
            self.scheduler.load_tasks()
        
        # Display current tasks
        for i, task in enumerate(self.scheduler.sync_tasks):
            self.tasks_table.insertRow(i)
            
            # Source directory
            self.tasks_table.setItem(i, 0, QTableWidgetItem(task['source_dir']))
            
            # Target directory
            self.tasks_table.setItem(i, 1, QTableWidgetItem(task['target_dir']))
            
            # Options
            options_text = self._format_options(task['options'])
            self.tasks_table.setItem(i, 2, QTableWidgetItem(options_text))
            
            # Status
            status = "Enabled" if task['enabled'] else "Disabled"
            self.tasks_table.setItem(i, 3, QTableWidgetItem(status))
            
            # Last sync
            last_sync = task.get('last_sync')
            if last_sync:
                sync_time = datetime.fromtimestamp(last_sync).strftime('%Y-%m-%d %H:%M')
                self.tasks_table.setItem(i, 4, QTableWidgetItem(sync_time))
            else:
                self.tasks_table.setItem(i, 4, QTableWidgetItem("Never"))
        
        # Load and set interval
        hours = self.scheduler.sync_interval // 3600
        minutes = (self.scheduler.sync_interval % 3600) // 60
        
        self.interval_hours.setValue(hours)
        self.interval_minutes.setValue(minutes)
        
    def _format_options(self, options):
        """Format sync options for display"""
        if not options:
            return "Default"
            
        parts = []
        
        # Sync mode
        if 'sync_mode' in options:
            mode_map = {
                'bidirectional': 'Bidirectional',
                'one_way': 'One-way',
                'mirror': 'Mirror'
            }
            parts.append(mode_map.get(options['sync_mode'], options['sync_mode']))
            
        # File types
        if 'file_types' in options:
            if not options['file_types']:
                parts.append("All files")
            else:
                parts.append(f"Files: {', '.join(options['file_types'])}")
                
        return ", ".join(parts)
        
    def update_ui_state(self):
        """Update UI based on selection state"""
        selected_rows = self.tasks_table.selectedIndexes()
        has_selection = bool(selected_rows)
        
        self.edit_task_button.setEnabled(has_selection)
        self.remove_task_button.setEnabled(has_selection)
        self.run_now_button.setEnabled(has_selection)
        
    def add_task(self):
        """Add a new sync task"""
        from ..utils.sync_manager import DirectorySyncDialog
        dialog = DirectorySyncDialog(self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get sync options
            source_dir = dialog.source_dir
            target_dir = dialog.target_dir
            options = dialog.get_sync_options()
            
            # Add to scheduler
            self.scheduler.add_sync_task(source_dir, target_dir, options)
            
            # Save tasks
            self.scheduler.save_tasks()
            
            # Refresh display
            self.load_scheduled_tasks()
            
    def edit_task(self):
        """Edit the selected sync task"""
        selected_rows = set(index.row() for index in self.tasks_table.selectedIndexes())
        if not selected_rows:
            return
            
        # Get the task to edit (use first selected row)
        row = list(selected_rows)[0]
        if row >= len(self.scheduler.sync_tasks):
            return
            
        task = self.scheduler.sync_tasks[row]
        
        # Open edit dialog
        from ..utils.sync_manager import DirectorySyncDialog
        dialog = DirectorySyncDialog(self, task['source_dir'], task['target_dir'])
        
        # Set options based on task
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update task
            task['source_dir'] = dialog.source_dir
            task['target_dir'] = dialog.target_dir
            task['options'] = dialog.get_sync_options()
            
            # Save tasks
            self.scheduler.save_tasks()
            
            # Refresh display
            self.load_scheduled_tasks()
            
    def remove_task(self):
        """Remove the selected sync task"""
        selected_rows = set(index.row() for index in self.tasks_table.selectedIndexes())
        if not selected_rows:
            return
            
        # Confirm deletion
        if len(selected_rows) == 1:
            message = "Are you sure you want to remove this scheduled sync task?"
        else:
            message = f"Are you sure you want to remove these {len(selected_rows)} scheduled sync tasks?"
            
        confirm = QMessageBox.question(
            self,
            "Confirm Removal",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Remove tasks (starting from highest row to avoid index issues)
        for row in sorted(selected_rows, reverse=True):
            if row < len(self.scheduler.sync_tasks):
                task_id = self.scheduler.sync_tasks[row]['id']
                self.scheduler.remove_sync_task(task_id)
        
        # Save tasks
        self.scheduler.save_tasks()
        
        # Refresh display
        self.load_scheduled_tasks()
        
    def run_task_now(self):
        """Run the selected task immediately"""
        selected_rows = set(index.row() for index in self.tasks_table.selectedIndexes())
        if not selected_rows:
            return
            
        # Get the task to run (use first selected row)
        row = list(selected_rows)[0]
        if row >= len(self.scheduler.sync_tasks):
            return
            
        task = self.scheduler.sync_tasks[row]
        
        # Confirm run
        confirm = QMessageBox.question(
            self,
            "Confirm Sync",
            f"Run sync now between:\n{task['source_dir']}\nand\n{task['target_dir']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Open regular sync dialog with these directories
        from ..utils.sync_manager import DirectorySyncDialog
        dialog = DirectorySyncDialog(self, task['source_dir'], task['target_dir'])
        
        # Apply task options to dialog
        # Set the source_dir and target_dir in the UI
        dialog.source_edit.setText(task['source_dir'])
        dialog.target_edit.setText(task['target_dir'])
        
        # Set sync mode
        mode = task['options'].get('sync_mode', 'bidirectional')
        if mode == 'bidirectional':
            dialog.sync_mode.setCurrentIndex(0)
        elif mode == 'one_way':
            dialog.sync_mode.setCurrentIndex(1)
        elif mode == 'mirror':
            dialog.sync_mode.setCurrentIndex(2)
        
        # Set conflict resolution
        resolution = task['options'].get('conflict_resolution', 'newer')
        if resolution == 'newer':
            dialog.conflict_resolution.setCurrentIndex(0)
        elif resolution == 'source':
            dialog.conflict_resolution.setCurrentIndex(1)
        elif resolution == 'target':
            dialog.conflict_resolution.setCurrentIndex(2)
        elif resolution == 'keep_both':
            dialog.conflict_resolution.setCurrentIndex(3)
        
        # Set file types
        file_types = task['options'].get('file_types', ['.md'])
        if file_types == ['.md']:
            dialog.file_types.setCurrentIndex(0)
        elif sorted(file_types) == sorted(['.md', '.txt', '.html']):
            dialog.file_types.setCurrentIndex(1)
        else:
            dialog.file_types.setCurrentIndex(2)
        
        # Set additional options
        dialog.delete_orphaned.setChecked(task['options'].get('delete_orphaned', False))
        dialog.preserve_timestamps.setChecked(task['options'].get('preserve_timestamps', True))
        dialog.dry_run.setChecked(False)  # Default to actual sync, not dry run
        
        # Run the dialog
        dialog.exec()
        
        # Update last sync time if dialog was accepted
        if hasattr(task, 'last_sync'):
            task['last_sync'] = time.time()
            self.scheduler.save_tasks()
            self.load_scheduled_tasks()
        
    def update_schedule(self):
        """Update the sync schedule based on UI settings"""
        hours = self.interval_hours.value()
        minutes = self.interval_minutes.value()
        
        # Ensure at least 1 minute interval
        if hours == 0 and minutes == 0:
            minutes = 1
            self.interval_minutes.setValue(1)
            
        # Calculate interval in seconds
        interval_seconds = (hours * 3600) + (minutes * 60)
        
        # Update scheduler
        self.scheduler.set_sync_interval(interval_seconds)
        
        # Save settings
        self.scheduler.save_tasks()
        
    def closeEvent(self, event):
        """Handle dialog close event"""
        # Save any changes
        self.scheduler.save_tasks()
        event.accept() 