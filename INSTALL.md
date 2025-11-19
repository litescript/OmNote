# OmNote Installation Guide

## Quick Install (Recommended)

```bash
git clone https://github.com/litescript/OmNote.git
cd OmNote
./install.sh
```

That's it! OmNote will appear in your Omarchy launcher.

---

## Requirements

### System Dependencies

**Arch Linux:**
```bash
sudo pacman -S python python-gobject gtk4 libadwaita
```

**Ubuntu/Debian:**
```bash
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```

**Fedora:**
```bash
sudo dnf install python3 python3-gobject gtk4 libadwaita
```

### Python Version
- **Python 3.11+** required

---

## Manual Installation

If you prefer to install manually:

### 1. Install Python Package
```bash
python3 -m pip install --user -e .
```

### 2. Install Desktop Integration
```bash
# Desktop file
install -Dm644 dist/dev.omarchy.OmNote.desktop \
    ~/.local/share/applications/dev.omarchy.OmNote.desktop

# Icon
install -Dm644 assets/dev.omarchy.OmNote.svg \
    ~/.local/share/icons/hicolor/scalable/apps/dev.omarchy.OmNote.svg

# Update desktop database
update-desktop-database ~/.local/share/applications
```

### 3. Verify Installation
```bash
omnote --help
```

---

## Usage

### Launch Methods

**1. From Omarchy Launcher** (recommended)
- Press Super key → Type "OmNote" → Enter

**2. From Terminal**
```bash
omnote
```

**3. Direct Python Module**
```bash
python3 -m omnote
```

### Command-Line Options
```bash
omnote --help              # Show help
omnote --system-theme      # Use system theme (ignore Omarchy themes)
omnote --no-watch          # Disable theme file watching
omnote [file.txt]          # Open specific file
```

---

## Uninstallation

### Quick Uninstall
```bash
cd OmNote
./uninstall.sh
```

### Manual Uninstall
```bash
# Remove package
python3 -m pip uninstall omnote

# Remove desktop integration
rm ~/.local/share/applications/dev.omarchy.OmNote.desktop
rm ~/.local/share/icons/hicolor/scalable/apps/dev.omarchy.OmNote.svg
update-desktop-database ~/.local/share/applications

# Optionally remove config
rm -rf ~/.config/omnote
```

---

## Configuration

OmNote stores its configuration in:
- **State file:** `~/.config/omnote/state.json`
- **Debug log:** `~/.cache/omnote/debug.log`

### Theme Integration

OmNote automatically syncs with Omarchy themes. Priority order:
1. Omarchy theme (`~/.config/omarchy/current/theme/`)
2. Alacritty config (`~/.config/alacritty/`)
3. Kitty config
4. Foot config
5. Environment variables (`OMNOTE_BG`, `OMNOTE_FG`, etc.)
6. System GTK4 theme

To force system theme:
```bash
omnote --system-theme
# or
export OMNOTE_THEME_MODE=system
```

**Legacy compatibility:** Old `MICROPAD_*` environment variables still work.

---

## Troubleshooting

### "omnote: command not found"

Add `~/.local/bin` to your PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### "No module named 'gi'"

Install PyGObject:
```bash
# Arch
sudo pacman -S python-gobject

# Ubuntu/Debian
sudo apt install python3-gi
```

### Theme not updating

Enable debug mode:
```bash
export OMNOTE_DEBUG=1
omnote
# Check ~/.cache/omnote/debug.log
```

### App won't launch

Check system dependencies:
```bash
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk, Adw"
```

---

## Development

### Running from Source (No Install)
```bash
make run
```

### Code Quality Checks
```bash
make lint    # Run ruff
make type    # Run mypy
make test    # Run pytest
```

---

## Support

- **Issues:** https://github.com/litescript/OmNote/issues
- **Repository:** https://github.com/litescript/OmNote

---

## License

See [LICENSE](LICENSE) file.
