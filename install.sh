#!/bin/bash
# OmNote Installation Script

set -e

echo "🚀 Installing OmNote (via pipx)..."

# Check for required system dependencies
check_deps() {
    local missing=()

    # Check Python 3.11+
    if ! command -v python3 &>/dev/null; then
        missing+=("python3")
    else
        version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)'; then
            echo "⚠️  Python 3.11+ required (found $version)"
            missing+=("python3.11+")
        fi
    fi

    # Check for pipx
    if ! command -v pipx &>/dev/null; then
        missing+=("pipx")
    fi

    # Check for GTK4/libadwaita (via pkg-config or common packages)
    if ! pkg-config --exists gtk4 2>/dev/null && ! pacman -Q gtk4 &>/dev/null && ! dpkg -l libgtk-4-1 &>/dev/null; then
        missing+=("gtk4")
    fi

    if ! pkg-config --exists libadwaita-1 2>/dev/null && ! pacman -Q libadwaita &>/dev/null && ! dpkg -l libadwaita-1-0 &>/dev/null; then
        missing+=("libadwaita")
    fi

    if ! pkg-config --exists gtksourceview-5 2>/dev/null && ! pacman -Q gtksourceview5 &>/dev/null && ! dpkg -l gir1.2-gtksource-5 &>/dev/null; then
        missing+=("gtksourceview5")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo "❌ Missing dependencies: ${missing[*]}"
        echo ""
        echo "On Arch Linux:"
        echo "  sudo pacman -S python python-pipx python-gobject gtk4 libadwaita gtksourceview5"
        echo ""
        echo "On Ubuntu/Debian:"
        echo "  sudo apt install python3 python3-pip python3-gi pipx gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gtksource-5"
        echo ""
        echo "If pipx is not available via your distro, you can install it with:"
        echo "  python3 -m pip install --user pipx"
        echo "  pipx ensurepath"
        echo ""
        exit 1
    fi
}

# Install Python package via pipx
install_package() {
    echo "📦 Installing OmNote package with pipx..."

    # We assume we're in the OmNote repo root.
    # --system-site-packages is required so the pipx venv can see the
    # system-installed PyGObject / gi bindings (GTK4, libadwaita, GtkSourceView).
    if pipx list 2>/dev/null | grep -qE '^[[:space:]]*package omnote '; then
        echo "ℹ️  Existing OmNote pipx install detected — removing before fresh install..."
        pipx uninstall omnote
    fi

    pipx install --system-site-packages .

    echo "✅ OmNote installed via pipx"
}

# Install desktop integration
install_desktop() {
    echo "🖥️  Installing desktop integration..."

    # Install .desktop file
    install -Dm644 dist/dev.omarchy.OmNote.desktop \
        ~/.local/share/applications/dev.omarchy.OmNote.desktop

    # Install icon
    install -Dm644 assets/dev.omarchy.OmNote.svg \
        ~/.local/share/icons/hicolor/scalable/apps/dev.omarchy.OmNote.svg

    # Update desktop database
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database ~/.local/share/applications 2>/dev/null || true
    fi

    echo "✅ Desktop integration installed"
}

# Verify installation
verify() {
    echo "🔍 Verifying installation..."

    if command -v omnote &>/dev/null; then
        echo "✅ omnote command available"
    else
        echo "⚠️  omnote command not currently in PATH"
        echo "   Make sure ~/.local/bin is in your PATH, for example:"
        echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi

    if [ -f ~/.local/share/applications/dev.omarchy.OmNote.desktop ]; then
        echo "✅ Desktop file installed"
    fi
}

# Main installation flow
main() {
    echo "════════════════════════════════════════"
    echo "  OmNote Installer (pipx-based)"
    echo "════════════════════════════════════════"
    echo ""

    check_deps
    install_package
    install_desktop
    verify

    echo ""
    echo "════════════════════════════════════════"
    echo "✨ Installation complete!"
    echo ""
    echo "Usage:"
    echo "  • Run: omnote"
    echo "  • Or launch from your desktop environment's app menu as “OmNote”"
    echo ""
    echo "To update (later):"
    echo "  pipx upgrade omnote"
    echo ""
    echo "To uninstall:"
    echo "  pipx uninstall omnote"
    echo "════════════════════════════════════════"
}

main
