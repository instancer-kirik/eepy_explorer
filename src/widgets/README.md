# Eepy Explorer Widgets

## Duplicate Finder Dialog

The duplicate finder dialog provides a UI for finding and managing duplicate files and notes.

### Implementation

- `NotesDuplicateDialog` (in `notes_duplicate_dialog.py`): Advanced UI with content preview, comparison features, and custom selection options. Works for both files and notes.

### Usage

#### Finding Duplicate Files

```python
from .notes_duplicate_dialog import NotesDuplicateDialog

# Create dialog
dialog = NotesDuplicateDialog(parent)
# Start scanning a directory
dialog.scan_directory(directory_path)
# Show dialog
dialog.exec()
```

#### Finding Duplicate Notes

```python
# Direct usage
from .notes_duplicate_dialog import NotesDuplicateDialog
dialog = NotesDuplicateDialog(parent)
dialog.scan_directory(notes_directory)
dialog.exec()
```

Alternatively, if you're using the notes manager:

```python
# The notes manager handles creating the appropriate dialog
parent.notes_manager.find_duplicate_notes(parent)
```

### Features

The duplicate finder dialog includes:
- Content-based duplicate detection
- Suffix pattern detection (-copy, -surfacepro6, etc.)
- Preview of file contents
- Side-by-side comparison
- Advanced selection options, including custom regex patterns
- Option to delete or merge duplicates 