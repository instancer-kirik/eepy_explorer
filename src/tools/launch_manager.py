from PyQt6.QtCore import QObject, pyqtSignal
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

class LaunchManager(QObject):
    """Manages project detection and launching"""
    
    # Signals
    launch_started = pyqtSignal(str)  # project_path
    launch_finished = pyqtSignal(str, int)  # project_path, return_code
    launch_error = pyqtSignal(str, str)  # project_path, error
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_dir = os.path.expanduser("~/.config/epy_explorer")
        self.config_file = os.path.join(self.config_dir, "launches.json")
        self.launches = {}
        self.load_launches()
        
        # Project type detectors
        self.detectors = {
            'python': self._detect_python_project,
            'node': self._detect_node_project,
            'rust': self._detect_rust_project,
            'go': self._detect_go_project,
            'zig': self._detect_zig_project,
        }
        
    def load_launches(self):
        """Load saved launch configurations"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.launches = json.load(f)
            except json.JSONDecodeError:
                self.launches = {}
                
    def save_launches(self):
        """Save launch configurations"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        with open(self.config_file, 'w') as f:
            json.dump(self.launches, f, indent=4)
            
    def detect_project(self, path):
        """Detect project type and configuration in directory"""
        results = []
        
        for project_type, detector in self.detectors.items():
            configs = detector(path)
            if configs:
                for config in configs:
                    config['type'] = project_type
                    results.append(config)
                    
        return results
        
    def _detect_python_project(self, path):
        """Detect Python project configurations"""
        configs = []
        
        # Check for various Python project indicators
        if os.path.exists(os.path.join(path, "pyproject.toml")):
            configs.append({
                'name': 'Python Project (pyproject.toml)',
                'command': 'uv run',
                'working_dir': path,
                'description': 'Run with uv (pyproject.toml)',
                'icon': 'text-x-python'
            })
            
        if os.path.exists(os.path.join(path, "setup.py")):
            configs.append({
                'name': 'Python Project (setup.py)',
                'command': 'python setup.py develop',
                'working_dir': path,
                'description': 'Run with setup.py',
                'icon': 'text-x-python'
            })
            
        if os.path.exists(os.path.join(path, "requirements.txt")):
            configs.append({
                'name': 'Python Project (requirements.txt)',
                'command': 'python -m pip install -r requirements.txt',
                'working_dir': path,
                'description': 'Install requirements',
                'icon': 'text-x-python'
            })
            
        # Look for main.py or similar entry points
        main_files = ['main.py', 'app.py', 'run.py']
        for main_file in main_files:
            if os.path.exists(os.path.join(path, main_file)):
                configs.append({
                    'name': f'Python Script ({main_file})',
                    'command': f'python {main_file}',
                    'working_dir': path,
                    'description': f'Run {main_file}',
                    'icon': 'text-x-python'
                })
                
        return configs
        
    def _detect_node_project(self, path):
        """Detect Node.js project configurations"""
        configs = []
        
        if os.path.exists(os.path.join(path, "package.json")):
            configs.append({
                'name': 'Node.js Project',
                'command': 'npm install && npm start',
                'working_dir': path,
                'description': 'Install dependencies and start',
                'icon': 'text-x-javascript'
            })
            
        return configs
        
    def _detect_rust_project(self, path):
        """Detect Rust project configurations"""
        configs = []
        
        if os.path.exists(os.path.join(path, "Cargo.toml")):
            configs.append({
                'name': 'Rust Project',
                'command': 'cargo run',
                'working_dir': path,
                'description': 'Build and run with Cargo',
                'icon': 'text-x-rust'
            })
            
        return configs
        
    def _detect_go_project(self, path):
        """Detect Go project configurations"""
        configs = []
        
        if os.path.exists(os.path.join(path, "go.mod")):
            configs.append({
                'name': 'Go Project',
                'command': 'go run .',
                'working_dir': path,
                'description': 'Run Go project',
                'icon': 'text-x-go'
            })
            
        return configs
        
    def _detect_zig_project(self, path):
        """Detect Zig project configurations"""
        configs = []
        
        if os.path.exists(os.path.join(path, "build.zig")):
            configs.append({
                'name': 'Zig Project',
                'command': 'zig build run',
                'working_dir': path,
                'description': 'Build and run with Zig',
                'icon': 'text-x-zig'
            })
            
        return configs
        
    def add_launch(self, path, config):
        """Add or update a launch configuration"""
        if path not in self.launches:
            self.launches[path] = []
            
        # Update existing config if it exists
        updated = False
        for i, existing in enumerate(self.launches[path]):
            if existing['name'] == config['name']:
                self.launches[path][i] = config
                updated = True
                break
                
        # Add new config if not updated
        if not updated:
            self.launches[path].append(config)
            
        self.save_launches()
        
    def remove_launch(self, path, name):
        """Remove a launch configuration"""
        if path in self.launches:
            self.launches[path] = [
                config for config in self.launches[path]
                if config['name'] != name
            ]
            if not self.launches[path]:
                del self.launches[path]
            self.save_launches()
            
    def get_launches(self, path):
        """Get launch configurations for path"""
        return self.launches.get(path, [])
        
    def launch_project(self, path, config):
        """Launch a project with given configuration"""
        try:
            self.launch_started.emit(path)
            
            # Update launch history
            if path in self.launches:
                for cfg in self.launches[path]:
                    if cfg['name'] == config['name']:
                        cfg['last_used'] = datetime.now().isoformat()
                        cfg['use_count'] = cfg.get('use_count', 0) + 1
                        break
            self.save_launches()
            
            # Run the command
            process = subprocess.Popen(
                config['command'],
                shell=True,
                cwd=config['working_dir'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0 and stderr:
                self.launch_error.emit(path, stderr)
            else:
                self.launch_finished.emit(path, process.returncode)
                
        except Exception as e:
            self.launch_error.emit(path, str(e)) 