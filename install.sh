#!/bin/bash
# OmNote Installation Script

set -e

echo "🚀 Installing OmNote..."

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

    # Check for GTK4/libadwaita (via pkg-config or common packages)
    if ! pkg-config --exists gtk4 2>/dev/null && ! pacman -Q gtk4 &>/dev/null && ! dpkg -l libgtk-4-1 &>/dev/null; then
        missing+=("gtk4")
    fi

    if ! pkg-config --exists libadwaita-1 2>/dev/null && ! pacman -Q libadwaita &>/dev/null && ! dpkg -l libadwaita-1-0 &>/dev/null; then
        missing+=("libadwaita")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo "❌ Missing dependencies: ${missing[*]}"
        echo ""
        echo "On Arch Linux:"
        echo "  sudo pacman -S python python-gobject gtk4 libadwaita"
        echo ""
        echo "On Ubuntu/Debian:"
        echo "  sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
        echo ""
        exit 1
    fi
}

# Install Python package
install_package() {
    echo "📦 Installing OmNote package..."

    # Install to user site-packages (no sudo needed)
    python3 -m pip install --user --upgrade pip setuptools wheel 2>/dev/null || true
    python3 -m pip install --user -e .

    echo "✅ Package installed"
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
        echo "⚠️  omnote command not in PATH"
        echo "   Add ~/.local/bin to your PATH:"
        echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi

    if [ -f ~/.local/share/applications/dev.omarchy.OmNote.desktop ]; then
        echo "✅ Desktop file installed"
    fi
}

# Main installation flow
main() {
    echo "════════════════════════════════════════"
    echo "  OmNote Installer"
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
    echo "  • Launch from Omarchy launcher"
    echo "  • Run: omnote"
    echo "  • Run: python3 -m omnote"
    echo ""
    echo "To uninstall:"
    echo "  ./uninstall.sh"
    echo "════════════════════════════════════════"
}

main
