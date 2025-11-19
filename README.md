# OmNote

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/litescript/OmNote/blob/main/LICENSE.md)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![GitHub stars](https://img.shields.io/github/stars/litescript/OmNote?style=social)](https://github.com/litescript/OmNote/stargazers)

OmNote is a lightweight, theme-aware plain-text editor built with GTK4 and libadwaita.  
It integrates seamlessly with the Omarchy desktop environment and provides a clean, efficient workspace with minimal dependencies and "NASA(ish)-style" code hygiene.

## Features

- Automatic theme synchronization with Omarchy (supports live updates)
- Multi-tab editing with full session persistence
- Find/Replace interface with smooth animations
- Efficient state management (cursor position, geometry, unsaved tabs)
- Minimal dependency footprint (Python + GTK4/libadwaita)
- Reliable error handling and robust file I/O (async-safe, race-condition tested)

## Installation

### Quick Install
```bash
git clone https://github.com/litescript/OmNote.git
cd OmNote
./install.sh
```

OmNote will appear in the Omarchy application launcher after installation.

### Requirements
- Python 3.11+
- GTK4
- libadwaita
- PyGObject

#### Arch Linux
```bash
sudo pacman -S python python-gobject gtk4 libadwaita
```

#### Ubuntu/Debian
```bash
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

See INSTALL.md for detailed installation instructions and troubleshooting.

## Usage

### Launch
- From Omarchy launcher: search for “OmNote”
- From terminal:
```bash
omnote
omnote file.txt
omnote --help
```

### Keyboard Shortcuts

| Action              | Shortcut                     |
|---------------------|------------------------------|
| New tab             | Ctrl+N / Ctrl+T              |
| Open file           | Ctrl+O                       |
| Save                | Ctrl+S                       |
| Close tab           | Ctrl+W                       |
| Next/Prev tab       | Ctrl+Tab / Ctrl+Shift+Tab    |
| Find                | Ctrl+F                       |
| Find & Replace      | Ctrl+H                       |
| Toggle line numbers | Ctrl+L                       |
| Quit                | Ctrl+Q                       |
| Next/Prev match     | F3 / Shift+F3                |

## Configuration

### Configuration and Cache
- State file: `~/.config/omnote/state.json`
- Debug log: `~/.cache/omnote/debug.log`

### Theme Selection & Overrides

OmNote automatically detects colors in the following order:

1. Omarchy theme (`~/.config/omarchy/current/theme/`)
2. Alacritty configuration
3. Kitty configuration
4. Foot configuration
5. Environment variables (`OMNOTE_BG`, `OMNOTE_FG`, etc.)
6. System GTK4 theme (fallback)

#### Force system theme
```bash
omnote --system-theme
# or
export OMNOTE_THEME_MODE=system
```

#### Disable live theme watching
```bash
omnote --no-watch
# or
export OMNOTE_NO_WATCH=1
```

### Legacy Compatibility
Older `MICROPAD_*` variables are still supported, but `OMNOTE_*` should be used going forward.

## Development

### Run from source
```bash
make run
```

### Quality checks
```bash
make lint
make type
make test
```

### Development dependencies
```bash
python -m venv .venv && source .venv/bin/activate
pip install ruff mypy pytest
```

## Uninstallation
```bash
./uninstall.sh
```

Manual removal:
```bash
python3 -m pip uninstall omnote
rm ~/.local/share/applications/dev.omarchy.OmNote.desktop
rm ~/.local/share/icons/hicolor/scalable/apps/dev.omarchy.OmNote.svg
```

## License

MIT License. See ([LICENSE](https://github.com/litescript/OmNote/blob/main/LICENSE.md)) for details.
