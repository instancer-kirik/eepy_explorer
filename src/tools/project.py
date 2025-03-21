import os
import json
from pathlib import Path
import asyncio
import aionotify

class EProject:
    """E project structure and conventions"""
    
    # Standard project structure
    STANDARD_DIRS = {
        'src': 'Source files',
        'test': 'Test files',
        'docs': 'Documentation',
        'examples': 'Example code',
        'contracts': 'Contract definitions',
        'build': 'Build artifacts',
    }
    
    # Project markers
    PROJECT_MARKERS = [
        'e.project',      # E project file
        'e.tools.json',   # Tools configuration
        'build.zig',      # Build system
        'src/main.e',     # Main source file
        '.ecf',          # Eiffel configuration file
    ]
    
    def __init__(self, root_path):
        self.root = root_path
        self.config = self.load_config()
        self.test_config = self.load_test_config()
    
    @staticmethod
    def find_project_root(start_path=None):
        """Find nearest E project root"""
        if start_path is None:
            start_path = os.getcwd()
            
        current = os.path.abspath(start_path)
        while current != '/':
            for marker in EProject.PROJECT_MARKERS:
                if os.path.exists(os.path.join(current, marker)):
                    return current
            current = os.path.dirname(current)
        return None
    
    def load_config(self):
        """Load project configuration"""
        config_paths = [
            os.path.join(self.root, 'e.project'),
            os.path.join(self.root, 'e.tools.json')
        ]
        
        for path in config_paths:
            if os.path.exists(path):
                with open(path) as f:
                    return json.loads(f.read())
        return {}
    
    def load_test_config(self):
        """Load test configuration for Zig/E projects"""
        test_config = {
            'test_dirs': ['test'],
            'test_files': ['**/*_test.zig', '**/*_test.e'],
            'test_command': 'zig build test',
            'test_args': [],
            'test_env': {},
            'watch_paths': ['src', 'test'],
        }
        
        # Check for project-specific test config
        config_paths = [
            os.path.join(self.root, 'e.test.json'),
            os.path.join(self.root, 'test.json'),
        ]
        
        for path in config_paths:
            if os.path.exists(path):
                with open(path) as f:
                    user_config = json.loads(f.read())
                    test_config.update(user_config)
                break
                
        return test_config
    
    def get_test_runner(self):
        """Get appropriate test runner based on project type"""
        project_type = self.detect_project_type()
        
        if project_type == 'zig':
            return ZigTestRunner(self)
        elif project_type == 'e':
            return ETestRunner(self)
        else:
            return None
            
    def detect_project_type(self):
        """Detect if this is an E, Zig or Eiffel project"""
        if os.path.exists(os.path.join(self.root, 'build.zig')):
            return 'zig'
        elif list(Path(self.root).glob('*.ecf')):
            # Check for Eiffel Studio
            if os.path.exists(os.path.join(self.root, 'studio')):
                return 'eiffelstudio'
            # Check for Eiffel library
            if os.path.exists(os.path.join(self.root, 'package.iron')):
                return 'eiffel-lib'
            return 'eiffel'
        return 'e'

class TestRunner:
    """Base class for test runners"""
    def __init__(self, project):
        self.project = project
        
    async def run_tests(self, test_filter=None):
        raise NotImplementedError()
        
    async def watch_tests(self):
        raise NotImplementedError()
        
    def parse_test_output(self, output):
        raise NotImplementedError()

class ZigTestRunner(TestRunner):
    """Zig-specific test runner"""
    
    def __init__(self, project):
        super().__init__(project)
        self.test_process = None
        
    async def run_tests(self, test_filter=None):
        """Run Zig tests with optional filter"""
        cmd = ['zig', 'build', 'test']
        
        if test_filter:
            cmd.extend(['--test-filter', test_filter])
            
        # Add any project-specific test args
        cmd.extend(self.project.test_config['test_args'])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project.root
            )
            
            stdout, stderr = await process.communicate()
            return self.parse_test_output(stdout.decode())
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tests': [],
                'summary': {'passed': 0, 'failed': 0, 'skipped': 0}
            }
    
    async def watch_tests(self):
        """Watch for file changes and run tests"""
        watcher = aionotify.Watcher()
        
        # Watch source and test directories
        for path in self.project.test_config['watch_paths']:
            full_path = os.path.join(self.project.root, path)
            if os.path.exists(full_path):
                watcher.watch(
                    path=full_path,
                    flags=aionotify.Flags.MODIFY | aionotify.Flags.CREATE
                )
        
        await watcher.setup()
        
        while True:
            event = await watcher.get_event()
            if event.name.endswith(('.zig', '.e')):
                # Small delay to avoid running tests while files are being saved
                await asyncio.sleep(0.5)
                yield await self.run_tests()
    
    def parse_test_output(self, output):
        """Parse Zig test output into structured format"""
        lines = output.splitlines()
        tests = []
        summary = {'passed': 0, 'failed': 0, 'skipped': 0}
        current_test = None
        
        for line in lines:
            if line.startswith('test "'):
                # New test case
                name = line[6:line.index('"', 6)]
                current_test = {
                    'name': name,
                    'status': 'running',
                    'output': [],
                    'duration': None
                }
                tests.append(current_test)
            elif current_test and 'PASS' in line:
                current_test['status'] = 'passed'
                summary['passed'] += 1
            elif current_test and 'FAIL' in line:
                current_test['status'] = 'failed'
                summary['failed'] += 1
            elif current_test and line.strip():
                current_test['output'].append(line)
        
        return {
            'success': summary['failed'] == 0,
            'tests': tests,
            'summary': summary
        }

class ETestRunner(TestRunner):
    """E language test runner"""
    # Similar implementation for E language tests
    pass

def set_project_root(explorer):
    """Set up project-specific view"""
    # Look for E project markers in priority order
    project_markers = [
        'e.project',
        'e.tools.json', 
        'build.zig',
        'enzige.json'
    ]
    
    current_path = Path(os.getcwd())
    workspace_root = Path(__file__).parent.parent.parent
    
    # First try current directory
    for marker in project_markers:
        if (current_path / marker).exists():
            set_root_path(explorer, current_path)
            return
            
    # Then try parent directories up to workspace root
    while current_path != workspace_root and current_path.parent != current_path:
        for marker in project_markers:
            if (current_path / marker).exists():
                set_root_path(explorer, current_path)
                return
        current_path = current_path.parent
        
    # If no project found, default to current directory
    set_root_path(explorer, Path(os.getcwd()))
    explorer.project_state.setText("No E project detected")

def set_root_path(explorer, path: Path):
    """Set root path for views"""
    path_str = str(path)
    explorer.tree_view.setRootIndex(explorer.model.index(path_str))
    explorer.list_view.setRootIndex(explorer.model.index(path_str))
    explorer.project_state.setText(f"Project: {path.name}")
    
    # Update project type indicator
    if (path / "e.project").exists():
        explorer.project_type.setText("E Project")
    elif (path / "build.zig").exists():
        explorer.project_type.setText("Zig Project")
    else:
        explorer.project_type.setText("") 