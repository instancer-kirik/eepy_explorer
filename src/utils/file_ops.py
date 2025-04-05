import os
import shutil
from pathlib import Path
from datetime import datetime
import zipfile
from PyQt6.QtWidgets import (QMessageBox, QProgressDialog, QDialog, QDialogButtonBox,
                           QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox,
                           QFileDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class ExtractionWorker(QThread):
    """Worker thread for archive extraction"""
    progress = pyqtSignal(str, int)  # Signal for progress updates (message, value)
    finished = pyqtSignal(list, list)  # Signal for completion (successful, failed)
    error = pyqtSignal(str)  # Signal for errors

    def __init__(self, archives, output_dir, create_subfolders=False):
        super().__init__()
        self.archives = archives
        self.output_dir = output_dir
        self.create_subfolders = create_subfolders
        self.should_stop = False

    def run(self):
        extracted = []
        failed = []
        total = len(self.archives)

        for i, (path, archive_type) in enumerate(self.archives):
            if self.should_stop:
                break

            base_name = os.path.basename(path)
            self.progress.emit(f"Extracting {base_name}...", int((i / total) * 100))

            try:
                # Determine target directory
                if self.create_subfolders:
                    archive_name = os.path.splitext(base_name)[0]
                    target_dir = os.path.join(self.output_dir, archive_name)
                else:
                    target_dir = self.output_dir

                # Create target directory
                os.makedirs(target_dir, exist_ok=True)

                # Extract based on archive type
                if archive_type == "zip":
                    with zipfile.ZipFile(path) as zf:
                        # Check for dangerous paths
                        for name in zf.namelist():
                            if name.startswith('/') or '..' in name:
                                raise ValueError(f"Potentially unsafe path in archive: {name}")
                        zf.extractall(target_dir)
                elif archive_type == "tar":
                    import tarfile
                    with tarfile.open(path) as tf:
                        # Check for dangerous paths
                        for member in tf.getmembers():
                            if member.name.startswith('/') or '..' in member.name:
                                raise ValueError(f"Potentially unsafe path in archive: {member.name}")
                        tf.extractall(target_dir)
                elif archive_type == "rar":
                    try:
                        import rarfile
                        with rarfile.RarFile(path) as rf:
                            rf.extractall(target_dir)
                    except ImportError:
                        raise ImportError("RAR support requires rarfile package")

                extracted.append(path)
            except Exception as e:
                failed.append((base_name, str(e)))

        self.progress.emit("Extraction complete", 100)
        self.finished.emit(extracted, failed)

    def stop(self):
        """Stop the extraction process"""
        self.should_stop = True

class FileConflictDialog(QDialog):
    def __init__(self, conflicts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Conflicts")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Add explanation
        layout.addWidget(QLabel("The following files already exist. Choose what to do:"))
        
        # Create conflict resolution widgets
        self.resolution_widgets = {}
        for src, dst in conflicts:
            group = QGroupBox(os.path.basename(src))
            group_layout = QVBoxLayout(group)
            
            # Add file info
            src_info = os.stat(src)
            dst_info = os.stat(dst)
            
            info_text = (
                f"Source: {self.format_file_info(src, src_info)}\n"
                f"Target: {self.format_file_info(dst, dst_info)}"
            )
            group_layout.addWidget(QLabel(info_text))
            
            # Add resolution options
            resolution = QComboBox()
            resolution.addItems(['Skip', 'Rename', 'Overwrite'])
            self.resolution_widgets[src] = resolution
            group_layout.addWidget(resolution)
            
            layout.addWidget(group)
        
        # Add buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def format_file_info(self, path, stat):
        """Format file information for display"""
        size = self.format_size(stat.st_size)
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
        return f"{path} ({size}, modified {mtime})"
    
    def format_size(self, size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
    
    def get_resolutions(self):
        """Get conflict resolutions"""
        return {
            src: widget.currentText().lower()
            for src, widget in self.resolution_widgets.items()
        }

class FileOperations:
    def __init__(self, explorer):
        self.explorer = explorer
        self.clipboard_files = []
        self.clipboard_operation = None  # 'copy' or 'cut'
    
    def copy_selected_files(self):
        """Copy selected files to clipboard"""
        indexes = self.explorer.tree_view.selectedIndexes()
        if not indexes:
            return
            
        self.clipboard_files = []
        for index in indexes:
            if index.column() == 0:  # Only process first column
                self.clipboard_files.append(self.explorer.model.filePath(index))
        
        self.clipboard_operation = 'copy'
        self.explorer.paste_button.setEnabled(True)
        self.explorer.status_bar.showMessage(f"Copied {len(self.clipboard_files)} items to clipboard", 3000)
    
    def cut_selected_files(self):
        """Cut selected files to clipboard"""
        indexes = self.explorer.tree_view.selectedIndexes()
        if not indexes:
            return
            
        self.clipboard_files = []
        for index in indexes:
            if index.column() == 0:  # Only process first column
                self.clipboard_files.append(self.explorer.model.filePath(index))
        
        self.clipboard_operation = 'cut'
        self.explorer.paste_button.setEnabled(True)
        self.explorer.status_bar.showMessage(f"Cut {len(self.clipboard_files)} items to clipboard", 3000)
    
    def paste_files(self):
        """Paste files from clipboard"""
        if not self.clipboard_files:
            return
            
        target_dir = self.explorer.model.filePath(self.explorer.tree_view.rootIndex())
        
        # Check for conflicts
        conflicts = []
        for src_path in self.clipboard_files:
            target_path = os.path.join(target_dir, os.path.basename(src_path))
            if os.path.exists(target_path):
                conflicts.append((src_path, target_path))
        
        # Handle conflicts if any
        if conflicts:
            dialog = FileConflictDialog(conflicts, self.explorer)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            conflict_resolution = dialog.get_resolutions()
        else:
            conflict_resolution = {}
        
        # Setup progress dialog
        total_size = sum(self.get_dir_size(f) for f in self.clipboard_files)
        progress = QProgressDialog("Preparing to copy files...", "Cancel", 0, total_size, self.explorer)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        copied_size = 0
        for src_path in self.clipboard_files:
            if progress.wasCanceled():
                break
                
            base_name = os.path.basename(src_path)
            target_path = os.path.join(target_dir, base_name)
            
            # Apply conflict resolution
            if src_path in conflict_resolution:
                if conflict_resolution[src_path] == 'skip':
                    continue
                elif conflict_resolution[src_path] == 'rename':
                    target_path = self.get_unique_path(target_path)
            
            try:
                if os.path.isfile(src_path):
                    self.copy_file_with_progress(src_path, target_path, progress, copied_size)
                    copied_size += os.path.getsize(src_path)
                else:
                    self.copy_dir_with_progress(src_path, target_path, progress, copied_size)
                    copied_size += self.get_dir_size(src_path)
                    
                if self.clipboard_operation == 'cut':
                    if os.path.isfile(src_path):
                        os.remove(src_path)
                    else:
                        shutil.rmtree(src_path)
                        
            except Exception as e:
                self.explorer.show_error(f"Failed to copy {base_name}: {str(e)}")
        
        progress.setValue(total_size)
        
        if self.clipboard_operation == 'cut':
            self.clipboard_files = []
            self.explorer.paste_button.setEnabled(False)
        
        self.explorer.refresh_view()
    
    def copy_file_with_progress(self, src, dst, progress, base_progress):
        """Copy a file with progress updates"""
        # Update progress dialog
        progress.setLabelText(f"Copying {os.path.basename(src)}...")
        
        # Copy with progress
        with open(src, 'rb') as fsrc:
            with open(dst, 'wb') as fdst:
                copied = 0
                while True:
                    buf = fsrc.read(1024*1024)  # 1MB chunks
                    if not buf:
                        break
                    fdst.write(buf)
                    copied += len(buf)
                    progress.setValue(base_progress + copied)
                    if progress.wasCanceled():
                        break
        
        # Copy metadata (timestamps, permissions)
        shutil.copystat(src, dst)
    
    def copy_dir_with_progress(self, src, dst, progress, base_progress):
        """Copy a directory with progress updates"""
        # Create target directory
        os.makedirs(dst, exist_ok=True)
        
        # Copy directory metadata
        shutil.copystat(src, dst)
        
        # Copy contents
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            
            if progress.wasCanceled():
                break
                
            if os.path.isfile(s):
                self.copy_file_with_progress(s, d, progress, base_progress)
                base_progress += os.path.getsize(s)
            else:
                self.copy_dir_with_progress(s, d, progress, base_progress)
                base_progress += self.get_dir_size(s)
    
    def get_dir_size(self, path):
        """Get total size of directory contents"""
        total = 0
        if os.path.isfile(path):
            return os.path.getsize(path)
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total += os.path.getsize(fp)
        return total
    
    def get_unique_path(self, path):
        """Get a unique path by appending numbers"""
        if not os.path.exists(path):
            return path
            
        base, ext = os.path.splitext(path)
        counter = 1
        while os.path.exists(f"{base} ({counter}){ext}"):
            counter += 1
        return f"{base} ({counter}){ext}"
    
    def extract_archives(self, paths, output_dir=None, create_subfolders=False):
        """Extract multiple archives
        
        Args:
            paths: List of archive paths to extract
            output_dir: Target directory (will prompt if None)
            create_subfolders: If True, creates a subfolder for each archive
        """
        if not paths:
            self.explorer.show_error("No archives selected")
            return
            
        if not output_dir:
            output_dir = QFileDialog.getExistingDirectory(
                self.explorer, "Select Output Directory"
            )
            if not output_dir:
                return
        
        # Validate archives before starting
        valid_archives = []
        for path in paths:
            archive_type = self.get_archive_type(path)
            if not archive_type:
                self.explorer.show_error(f"Unsupported archive type: {os.path.basename(path)}")
                continue
            if not os.path.exists(path):
                self.explorer.show_error(f"Archive not found: {os.path.basename(path)}")
                continue
            valid_archives.append((path, archive_type))
        
        if not valid_archives:
            self.explorer.show_error("No valid archives to extract")
            return
            
        # Create progress dialog
        progress = QProgressDialog("Preparing to extract archives...", "Cancel", 0, 100, self.explorer)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        
        # Create and start worker thread
        self.extraction_worker = ExtractionWorker(valid_archives, output_dir, create_subfolders)
        
        # Connect signals
        self.extraction_worker.progress.connect(
            lambda msg, val: (progress.setLabelText(msg), progress.setValue(val))
        )
        self.extraction_worker.finished.connect(
            lambda extracted, failed: self._show_extraction_results(extracted, failed, output_dir)
        )
        self.extraction_worker.error.connect(self.explorer.show_error)
        
        # Connect cancel button
        progress.canceled.connect(self.extraction_worker.stop)
        
        # Start extraction
        self.extraction_worker.start()
    
    def _show_extraction_results(self, extracted, failed, output_dir):
        """Show results of extraction operation"""
        if extracted:
            success_msg = f"Successfully extracted {len(extracted)} archive(s) to {output_dir}"
            if failed:
                success_msg += "\n\nThe following archives failed:"
                for name, error in failed:
                    success_msg += f"\n- {name}: {error}"
            QMessageBox.information(self.explorer, "Extraction Complete", success_msg)
        elif failed:
            error_msg = "Failed to extract archives:\n"
            for name, error in failed:
                error_msg += f"\n- {name}: {error}"
            self.explorer.show_error(error_msg)
    
    def get_archive_type(self, path):
        """Detect archive type"""
        ext = os.path.splitext(path)[1].lower()
        if ext == '.zip':
            return "zip"
        elif ext in ['.tar', '.gz', '.bz2']:
            return "tar"
        elif ext == '.rar':
            return "rar"
        return None 