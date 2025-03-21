from PyQt6.QtCore import QObject, pyqtSignal
import os
import json
import subprocess
from datetime import datetime
from collections import defaultdict

class CommandManager(QObject):
    """Manages saved commands and their execution"""
    
    # Signals
    command_started = pyqtSignal(str)  # name
    command_finished = pyqtSignal(str, int)  # name, return_code
    command_error = pyqtSignal(str, str)  # name, error
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_dir = os.path.expanduser("~/.config/epy_explorer")
        self.config_file = os.path.join(self.config_dir, "commands.json")
        self.commands = {}
        self.load_commands()
        
    def load_commands(self):
        """Load commands from config file"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.commands = json.load(f)
            except json.JSONDecodeError:
                self.commands = {}
                
    def save_commands(self):
        """Save commands to config file"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        with open(self.config_file, 'w') as f:
            json.dump(self.commands, f, indent=4)
            
    def add_command(self, name, command, description="", tags=None, cwd=None):
        """Add or update a command"""
        if name not in self.commands:
            # New command
            self.commands[name] = {
                'command': command,
                'description': description,
                'tags': tags or [],
                'cwd': cwd,
                'created': datetime.now().isoformat(),
                'last_used': None,
                'use_count': 0
            }
        else:
            # Update existing command
            self.commands[name].update({
                'command': command,
                'description': description,
                'tags': tags or [],
                'cwd': cwd
            })
            
        self.save_commands()
        
    def remove_command(self, name):
        """Remove a command"""
        if name in self.commands:
            del self.commands[name]
            self.save_commands()
            
    def get_command(self, name):
        """Get a command by name"""
        return self.commands.get(name)
        
    def get_all_commands(self):
        """Get all commands"""
        return self.commands
        
    def get_recent_commands(self, limit=10):
        """Get recently used commands"""
        recent = sorted(
            [
                (name, cmd) for name, cmd in self.commands.items()
                if cmd['last_used']
            ],
            key=lambda x: x[1]['last_used'],
            reverse=True
        )
        return dict(recent[:limit])
        
    def get_popular_commands(self, limit=10):
        """Get most used commands"""
        popular = sorted(
            self.commands.items(),
            key=lambda x: x[1]['use_count'],
            reverse=True
        )
        return dict(popular[:limit])
        
    def get_commands_by_tag(self, tag):
        """Get commands with a specific tag"""
        return {
            name: cmd for name, cmd in self.commands.items()
            if tag in cmd['tags']
        }
        
    def get_all_tags(self):
        """Get all unique tags"""
        tags = set()
        for cmd in self.commands.values():
            tags.update(cmd['tags'])
        return sorted(tags)
        
    def search_commands(self, query):
        """Search commands by name, description, or tags"""
        query = query.lower()
        return {
            name: cmd for name, cmd in self.commands.items()
            if (
                query in name.lower() or
                query in cmd['description'].lower() or
                any(query in tag.lower() for tag in cmd['tags'])
            )
        }
        
    def run_command(self, name, cwd=None):
        """Run a command"""
        if name not in self.commands:
            self.command_error.emit(name, "Command not found")
            return
            
        cmd = self.commands[name]
        working_dir = cwd or cmd['cwd'] or os.getcwd()
        
        try:
            self.command_started.emit(name)
            
            # Update command stats
            cmd['last_used'] = datetime.now().isoformat()
            cmd['use_count'] += 1
            self.save_commands()
            
            # Run command
            process = subprocess.Popen(
                cmd['command'],
                shell=True,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0 and stderr:
                self.command_error.emit(name, stderr)
            else:
                self.command_finished.emit(name, process.returncode)
                
        except Exception as e:
            self.command_error.emit(name, str(e)) 