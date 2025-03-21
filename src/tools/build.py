import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QProgressDialog
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import json

class SmeltMonitorThread(QThread):
    """Thread to monitor smelt process output"""
    status_update = pyqtSignal(str)
    
    def __init__(self, process):
        super().__init__()
        self.process = process
        self._stop = False
        
    def run(self):
        while not self._stop and self.process and self.process.poll() is None:
            output = self.process.stdout.readline()
            if output:
                if "Watching for changes" in output:
                    self.status_update.emit("Ready for development - watching for changes")
                elif "Recompiling" in output:
                    self.status_update.emit("Recompiling changes...")
                elif "Error" in output:
                    self.status_update.emit("Error in development mode")
                    
    def stop(self):
        self._stop = True

class BuildManager:
    def __init__(self, explorer):
        self.explorer = explorer
        self.smelt_process = None
        self.smelt_monitor_thread = None
    
    def get_enzige_path(self):
        """Get path to enzige binary"""
        # Check in order of preference:
        # 1. E/enzige/zig-out/bin/enzige (built binary)
        # 2. E/enzige/src/enzige (source)
        # 3. System enzige
        
        workspace_root = Path(__file__).parent.parent.parent
        built_enzige = workspace_root / "enzige" / "zig-out" / "bin" / "enzige"
        src_enzige = workspace_root / "enzige" / "src" / "enzige"
        
        if built_enzige.exists():
            return str(built_enzige)
        elif src_enzige.exists():
            return str(src_enzige)
        else:
            return "enzige"  # Try system path
    
    def build_project(self):
        """Build the current project"""
        try:
            enzige = self.get_enzige_path()
            subprocess.run([enzige, "build"], check=True)
        except FileNotFoundError:
            QMessageBox.warning(self.explorer, "Build Failed", 
                "enzige not found. Please build enzige first:\n\n"
                "1. cd E/enzige\n"
                "2. zig build\n\n"
                "Or install it system-wide.")
        except subprocess.CalledProcessError as e:
            self.explorer.show_error(f"Build failed: {e}")
    
    def smelt_system(self):
        """Start development mode with hot-reloading"""
        try:
            enzige = self.get_enzige_path()
            # Remove the --server flag and add proper development flags
            self.smelt_process = subprocess.Popen([enzige, "smelt", "--watch", "--dev"], 
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE,
                                                text=True)
            
            # Update UI to show active development mode
            self.explorer.smelt_button.setChecked(True)
            self.explorer.cast_button.setEnabled(False)
            self.explorer.forge_button.setEnabled(False)
            
            self.explorer.status_bar.showMessage("Development mode active - Code is molten")
            
            # Start monitoring the process output
            self.start_smelt_monitor()
            
        except FileNotFoundError:
            self.offer_create_default_project()
        except subprocess.CalledProcessError as e:
            self.explorer.show_error(f"Failed to start development mode: {e}")
    
    def cast_system(self):
        """Create a development build with debug symbols"""
        try:
            enzige = self.get_enzige_path()
            cmd = [enzige, "cast"]
            
            # Show progress dialog
            progress = QProgressDialog("Creating development build...", None, 0, 0, self.explorer)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            progress.close()
            
            if result.returncode == 0:
                QMessageBox.information(self.explorer, "Build Success", 
                    "Development build created successfully.\n\n"
                    "The build includes:\n"
                    "- Debug symbols\n"
                    "- Runtime checks\n"
                    "- Source maps")
            else:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
                
        except FileNotFoundError:
            QMessageBox.warning(self.explorer, "Cast Failed", 
                "enzige not found. Please build enzige first:\n\n"
                "1. cd E/enzige\n"
                "2. zig build\n\n"
                "Or install it system-wide.")
        except subprocess.CalledProcessError as e:
            self.explorer.show_error(f"Development build failed:\n{e.stderr}")
    
    def forge_system(self):
        """Create an optimized production build"""
        try:
            enzige = self.get_enzige_path()
            cmd = [enzige, "forge"]
            
            # Show progress dialog
            progress = QProgressDialog("Creating production build...", None, 0, 0, self.explorer)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            progress.close()
            
            if result.returncode == 0:
                QMessageBox.information(self.explorer, "Build Success", 
                    "Production build forged successfully.\n\n"
                    "Optimizations applied:\n"
                    "- Full compiler optimizations\n"
                    "- Dead code elimination\n"
                    "- Asset optimization\n"
                    "- Code minification")
            else:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
                
        except FileNotFoundError:
            QMessageBox.warning(self.explorer, "Forge Failed", 
                "enzige not found. Please build enzige first:\n\n"
                "1. cd E/enzige\n"
                "2. zig build\n\n"
                "Or install it system-wide.")
        except subprocess.CalledProcessError as e:
            self.explorer.show_error(f"Production build failed:\n{e.stderr}")
    
    def verify_contracts(self):
        """Verify Design by Contract™ assertions"""
        try:
            subprocess.run(["enzige", "verify"], check=True)
            QMessageBox.information(self.explorer, "Contracts", "All contracts verified successfully")
        except subprocess.CalledProcessError:
            self.explorer.show_error("Contract verification failed")
    
    def generate_docs(self):
        """Generate documentation in multiple formats"""
        formats = ["HTML", "RTF", "PDF"]
        try:
            for fmt in formats:
                subprocess.run(["enzige", "doc", f"--format={fmt}"], check=True)
            QMessageBox.information(self.explorer, "Documentation", "Documentation generated successfully")
        except subprocess.CalledProcessError:
            self.explorer.show_error("Documentation generation failed")
    
    def run_tests(self):
        """Run automated tests"""
        try:
            subprocess.run(["enzige", "test", "--auto"], check=True)
            QMessageBox.information(self.explorer, "AutoTest", "All tests passed")
        except subprocess.CalledProcessError:
            self.explorer.show_error("Some tests failed")
    
    def start_smelt_monitor(self):
        """Start monitoring smelt process output"""
        if self.smelt_monitor_thread is not None:
            self.smelt_monitor_thread.stop()
            self.smelt_monitor_thread.quit()
            self.smelt_monitor_thread.wait()
        
        self.smelt_monitor_thread = SmeltMonitorThread(self.smelt_process)
        self.smelt_monitor_thread.status_update.connect(self.explorer.status_bar.showMessage)
        self.smelt_monitor_thread.start()
    
    def offer_create_default_project(self):
        """Offer to create a default test project"""
        msg = QMessageBox(self.explorer)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Create Test Project?")
        msg.setText("No E project found. Would you like to create a test project?")
        msg.setInformativeText(
            "This will create a sample project with:\n"
            "- Basic UI components\n"
            "- Renderer test\n"
            "- Hot-reload example\n"
            "- Build configuration"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.create_test_project()
    
    def create_test_project(self):
        """Create a default test project"""
        try:
            # Create project directory
            project_dir = Path.cwd() / "e-test-project"
            project_dir.mkdir(exist_ok=True)
            
            # Create project structure
            (project_dir / "src").mkdir(exist_ok=True)
            (project_dir / "assets").mkdir(exist_ok=True)
            
            # Create e.project file
            with open(project_dir / "e.project", "w") as f:
                json.dump({
                    "name": "e-test-project",
                    "version": "0.1.0",
                    "type": "application",
                    "entry": "src/main.e",
                    "ui": {
                        "enabled": True,
                        "renderer": "clay"
                    }
                }, f, indent=2)
            
            # Create main.e with test UI
            with open(project_dir / "src" / "main.e", "w") as f:
                f.write("""// Test UI Application
import clay.ui
import clay.render

// Main window setup
window = Window.new("E Test Application")
window.size = (800, 600)

// Test components
button = Button.new("Click Me!")
button.on_click = fn() {
    label.text = "Button clicked!"
}

label = Label.new("Welcome to E!")
label.style.color = Color.blue

// Layout
layout = VStack.new([
    label,
    button,
    Canvas.new(fn(ctx) {
        // Test renderer
        ctx.fill_style = Color.red
        ctx.fill_rect(10, 10, 100, 100)
        ctx.stroke_style = Color.green
        ctx.stroke_circle(150, 150, 50)
    })
])

window.content = layout
window.show()
""")
            
            # Set as current project
            self.explorer.set_root_path(project_dir)
            self.explorer.status_bar.showMessage("Test project created successfully")
            
        except Exception as e:
            self.explorer.show_error(f"Failed to create test project: {e}") 