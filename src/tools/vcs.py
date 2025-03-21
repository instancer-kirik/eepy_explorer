import os
import subprocess
from PyQt6.QtWidgets import QMessageBox

class VCSManager:
    def __init__(self, explorer):
        self.explorer = explorer
        self.vcs_tools = self.detect_vcs_tools()
    
    def detect_vcs_tools(self):
        """Detect available VCS tools"""
        vcs_tools = {}
        
        # Check for RabbitVCS components
        rabbitvcs_paths = [
            "/usr/bin/rabbitvcs",
            "/usr/local/bin/rabbitvcs",
            "/usr/lib/rabbitvcs/bin/rabbitvcs",
            # Add more potential paths
        ]
        
        for path in rabbitvcs_paths:
            if os.path.exists(path):
                vcs_tools['rabbitvcs'] = path
                break
        
        # Check for git (as fallback)
        try:
            git_path = subprocess.check_output(["which", "git"]).decode().strip()
            vcs_tools['git'] = git_path
        except subprocess.CalledProcessError:
            pass
            
        return vcs_tools
    
    def open_vcs(self):
        """Open VCS browser"""
        if not self.vcs_tools:
            self.explorer.show_error(
                "No VCS tools found. Please install RabbitVCS:\n"
                "sudo pacman -S rabbitvcs-core rabbitvcs-nautilus\n"
                "or\n"
                "yay -S rabbitvcs"
            )
            return
            
        try:
            if 'rabbitvcs' in self.vcs_tools:
                # Try RabbitVCS browser
                subprocess.run([self.vcs_tools['rabbitvcs'], "browser"], check=True)
            elif 'git' in self.vcs_tools:
                # Fallback to git GUI if available
                subprocess.run(["git", "gui"], check=True)
            else:
                self.explorer.show_error("No supported VCS GUI found")
        except FileNotFoundError as e:
            self.explorer.show_error(f"VCS tool not found: {e}")
        except subprocess.CalledProcessError as e:
            self.explorer.show_error(f"Failed to open VCS browser: {e}")
    
    def init_git(self):
        """Initialize git repository"""
        try:
            subprocess.run(["git", "init"], check=True)
            self.explorer.model.update_vcs_status()
            self.explorer.refresh_view()
            QMessageBox.information(self.explorer, "Success", "Git repository initialized")
        except subprocess.CalledProcessError as e:
            self.explorer.show_error(f"Failed to initialize git: {e}")
    
    def git_add(self, path):
        """Add file to git"""
        try:
            subprocess.run(["git", "add", path], check=True)
            self.explorer.refresh_view()
        except subprocess.CalledProcessError as e:
            self.explorer.show_error(f"Failed to add file: {e}")
    
    def git_commit(self, path):
        """Commit file to git"""
        try:
            message, ok = QInputDialog.getText(
                self.explorer, 'Commit', 'Enter commit message:'
            )
            if ok and message:
                subprocess.run(
                    ["git", "commit", path, "-m", message],
                    check=True
                )
                self.explorer.refresh_view()
        except subprocess.CalledProcessError as e:
            self.explorer.show_error(f"Failed to commit: {e}")
    
    def show_diff(self, path):
        """Show file changes"""
        try:
            diff = subprocess.check_output(
                ['git', 'diff', path],
                text=True
            )
            self.explorer.preview_tabs.setPlainText(diff)
        except subprocess.CalledProcessError:
            self.explorer.show_error("Failed to get diff")
    
    def show_history(self, path):
        """Show file history"""
        try:
            history = subprocess.check_output(
                ['git', 'log', '--follow', '--pretty=format:%h %ad %s', path],
                text=True
            )
            self.explorer.preview_tabs.setPlainText(history)
        except subprocess.CalledProcessError:
            self.explorer.show_error("Failed to get history") 