# EEPY Explorer

A file explorer, and project explorer, and notes vault explorer - built with Python and PyQt6.

With specialized features for interacting with these different aspects.

WHAT THIS IS NOT:
an IDE - E projects require some special features, like meltable build states - see Eiffel Studio
also, does not yet actually "work" with E projects; I was making enzige, an E lang(1995) build tool, that this uses, written in zig, WIP
this is also not designed to replace your main notes app. It is however, designed to fix some issues that I have encountered while using obsidian

## Features


### File Management
- Dual-view interface (list and grid views)
- File operations (copy, cut, paste, delete, rename)
- Preview pane for various file types
- Favorites and quick access locations
- Storage device list (most other file managers didn't see my partitions on my SD card; this does)
- Bulk compression/extraction things probably uses varchiver installed, https://github.com/instancer-kirik/varchiver.git (or  doesn't even work yet because I just moved bulk_extract from .. and it probably isn't referenced properly)

### Project Features
- Project tree view
- Quick command execution
- Test management
- Build process integration

### Notes System
- Markdown notes with frontmatter support
- Tag-based organization
- Inline tag editing
- Note title management
- Find duplicate notes functionality, and soon, pruning

### Interface
- Modern UI with dark theme support
- Contextual toolbars that adapt to current mode
- Split-view interface with preview capabilities
- Drive and favorites management


## Installation

### Prerequisites
- Python 3.8+
- uv (Python package manager)

### Setup
```bash
# Clone the repository
git clone https://github.com/instancer-kirik/eepy-explorer.git
cd eepy-explorer
#and then I think you can just 
uv run run.py
```

## Usage

### File Navigation
- Double-click to open files or directories
- Use the address bar to navigate directly to specific paths
- Back/forward/up buttons for quick navigation
- Toggle between list and grid views with toolbar buttons

### Notes Management
- Click on the "Notes" mode button to switch to notes view
- Navigate your notes through the tree view
- Click directly on tag cells to edit tags inline
- Ctrl+Click on note titles to rename notes
- Double-click notes to open in the internal editor

### Project Management
- Click on the "Project" mode button to switch to project view
- Set any directory as project root through context menu
- Run commands and launch configurations for development tasks

## Development Roadmap

Check out our [detailed roadmap](eepy_explorer/roadmap.md) for upcoming features and improvements.

### Current Focus
- Duplicate notes management

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- PyQt6 for the UI framework
