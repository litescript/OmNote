# OmNote

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/litescript/OmNote/blob/main/LICENSE.md)  
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)  
[![GitHub stars](https://img.shields.io/github/stars/litescript/OmNote?style=social)](https://github.com/litescript/OmNote/stargazers)

OmNote is a lightweight, theme-aware plain-text editor built with GTK4 and libadwaita.  
It integrates seamlessly with the Omarchy desktop environment and provides a clean, efficient workspace with minimal dependencies and “NASA(ish)-style” code hygiene.

## Features

- Automatic theme synchronization with Omarchy (supports live updates)
- Multi-tab editing with full session persistence
- Find/Replace interface with smooth animations
- Efficient state management (cursor position, geometry, unsaved tabs)
- Minimal dependency footprint (Python + GTK4/libadwaita)
- Reliable error handling and robust file I/O

## Installation

OmNote is installed using pipx, which isolates the app from system Python while still providing a normal `omnote` command.
Because GTK bindings are provided by your OS, OmNote must be installed with access to system site-packages.

### Quick Install (Recommended)

```bash
pipx install --system-site-packages \
  "git+https://github.com/litescript/OmNote.git"
```

After installation:

```bash
omnote
```

Or launch OmNote from your desktop environment’s application menu.

Requirements:
- Python 3.11+
- pipx
- GTK 4
- libadwaita
- PyGObject (GI bindings)

Arch Linux:

```bash
sudo pacman -S --needed \
  python python-pipx python-gobject \
  gobject-introspection gtk4 libadwaita
```

Ubuntu / Debian:

```bash
sudo apt install -y \
  python3 python3-pip pipx \
  python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

If pipx is missing:

```bash
python3 -m pip install --user pipx
pipx ensurepath
```

Desktop Launcher (Optional):

```bash
cat > ~/.local/share/applications/omnote.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=OmNote
Comment=Lightweight GTK note editor
Exec=omnote
Icon=omnote
Terminal=false
Categories=Utility;Office;
StartupNotify=true
EOF

update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

Install from Source (Development):

```bash
git clone https://github.com/litescript/OmNote.git
cd OmNote
./install.sh
```

## Usage

### Launch

- From Omarchy launcher: search for **“OmNote”**
- From terminal:

```bash
omnote
omnote file.txt
omnote --help
```

## Keyboard Shortcuts

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

### Config & Cache

- State: `~/.config/omnote/state.json`
- Debug log: `~/.cache/omnote/debug.log`

### Theme Resolution Order

1. Omarchy theme (`~/.config/omarchy/current/theme/`)
2. Alacritty configuration
3. Kitty configuration
4. Foot configuration
5. `OMNOTE_*` environment variables
6. System GTK4 theme (fallback)

### Examples

Force system theme:

```bash
omnote --system-theme
# or
export OMNOTE_THEME_MODE=system
```

Disable live theme watching:

```bash
omnote --no-watch
# or
export OMNOTE_NO_WATCH=1
```

Legacy `MICROPAD_*` variables remain supported.

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

### Dev dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install ruff mypy pytest
```

## Uninstallation

### pipx uninstall (recommended)

```bash
pipx uninstall omnote
```

### Manual removal (icons + desktop files)

```bash
rm ~/.local/share/applications/dev.omarchy.OmNote.desktop
rm ~/.local/share/icons/hicolor/scalable/apps/dev.omarchy.OmNote.svg
```

## License

MIT License. See https://github.com/litescript/OmNote/blob/main/LICENSE.md for details.
