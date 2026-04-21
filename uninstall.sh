#!/bin/bash
# OmNote Uninstallation Script

set -e

echo "🗑️  Uninstalling OmNote..."

# Remove Python package (pipx first — that's what install.sh uses;
# fall back to pip for legacy installs).
if command -v pipx &>/dev/null && pipx list 2>/dev/null | grep -qE '^[[:space:]]*package omnote '; then
    echo "📦 Removing pipx package..."
    pipx uninstall omnote
    echo "✅ Package removed"
elif python3 -m pip show omnote &>/dev/null; then
    echo "📦 Removing pip package (legacy install)..."
    python3 -m pip uninstall -y omnote
    echo "✅ Package removed"
fi

# Remove desktop integration
if [ -f ~/.local/share/applications/dev.omarchy.OmNote.desktop ]; then
    echo "🖥️  Removing desktop integration..."
    rm -f ~/.local/share/applications/dev.omarchy.OmNote.desktop
    rm -f ~/.local/share/icons/hicolor/scalable/apps/dev.omarchy.OmNote.svg

    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database ~/.local/share/applications 2>/dev/null || true
    fi
    echo "✅ Desktop integration removed"
fi

# Optionally remove config (prompt user)
if [ -d ~/.config/omnote ]; then
    echo ""
    read -p "Remove config directory ~/.config/omnote? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf ~/.config/omnote
        echo "✅ Config removed"
    else
        echo "⏭️  Keeping config"
    fi
fi

echo ""
echo "✨ Uninstallation complete!"
