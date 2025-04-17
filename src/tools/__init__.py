"""
Tools package for EEPY Explorer
"""

# Import tools modules
from .build import BuildManager
# from .test_tool import TestTool
# from .vcs_manager import VCSManager
from .command_manager import CommandManager
from .launch_manager import LaunchManager
from .notes_manager import NotesManager
from .duplicate_finder import BaseDuplicateFinder, FileDuplicateFinder, NotesDuplicateFinder
from .sync_manager import DirectorySyncManager, SyncWorker, VersionManager 