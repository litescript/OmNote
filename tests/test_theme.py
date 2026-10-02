"""Tests for omnote.theme palette detection (pure-Python parts; GTK is mocked)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# What Omarchy 4's alacritty.toml.tpl renders for Tokyo Night
TOKYO_NIGHT = """
[colors.primary]
background = "#1a1b26"
foreground = "#a9b1d6"

[colors.cursor]
text = "#1a1b26"
cursor = "#c0caf5"

[colors.selection]
text = "#a9b1d6"
background = "#292e42"
"""

TOKYO_PALETTE = {
    "bg": "#1a1b26",
    "fg": "#a9b1d6",
    "sel_bg": "#292e42",
    "sel_fg": "#a9b1d6",
    "caret": "#c0caf5",
}


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for var in ("ALACRITTY_CONFIG", "KITTY_CONFIG_DIRECTORY", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(var, raising=False)
    for prefix in ("OMNOTE_", "MICROPAD_"):
        for key in ("THEME_MODE", "BG", "FG", "SEL_BG", "SEL_FG", "CARET"):
            monkeypatch.delenv(prefix + key, raising=False)
    return home


@pytest.fixture
def theme(home: Path, monkeypatch: pytest.MonkeyPatch):
    """Import theme fresh (its paths are resolved at import) with gi mocked."""
    mock_gi = MagicMock()
    monkeypatch.setitem(sys.modules, "gi", mock_gi)
    monkeypatch.setitem(sys.modules, "gi.repository", mock_gi.repository)
    monkeypatch.delitem(sys.modules, "omnote.theme", raising=False)
    module = importlib.import_module("omnote.theme")
    yield module
    sys.modules.pop("omnote.theme", None)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestOmarchy:
    def test_state_dir_theme_is_detected(self, home: Path, theme) -> None:
        """Issue #3: Omarchy 4 keeps the active theme under ~/.local/state."""
        theme_dir = home / ".local/state/omarchy/current/theme"
        write(theme_dir / "alacritty.toml", TOKYO_NIGHT)

        assert theme._omarchy_current_dir() == theme_dir
        assert theme._from_omarchy_theme() == TOKYO_PALETTE

    def test_state_dir_wins_over_legacy_config_dir(self, home: Path, theme) -> None:
        write(home / ".local/state/omarchy/current/theme/alacritty.toml", TOKYO_NIGHT)
        write(
            home / ".config/omarchy/current/theme/alacritty.toml",
            '[colors.primary]\nbackground = "#000000"\nforeground = "#ffffff"\n',
        )
        assert theme._from_omarchy_theme()["bg"] == "#1a1b26"


class TestAlacritty:
    def test_follows_general_import(self, home: Path, theme) -> None:
        """Omarchy's top-level alacritty.toml is only an import pointer."""
        write(home / ".local/state/omarchy/current/theme/alacritty.toml", TOKYO_NIGHT)
        write(
            home / ".config/alacritty/alacritty.toml",
            'general.import = [ "~/.local/state/omarchy/current/theme/alacritty.toml" ]\n',
        )
        assert theme._from_alacritty_config() == TOKYO_PALETTE

    def test_relative_import_resolves_against_importing_file(
        self, home: Path, theme, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write(home / ".config/alacritty/themes/tokyo.toml", TOKYO_NIGHT)
        main = write(
            home / ".config/alacritty/alacritty.toml",
            '[general]\nimport = ["themes/tokyo.toml"]\n',
        )
        monkeypatch.chdir(tmp_path)
        assert theme._parse_alacritty(main) == TOKYO_PALETTE

    def test_symlinked_config_resolves_imports_next_to_the_link(
        self, home: Path, theme
    ) -> None:
        """Dotfile repos symlink alacritty.toml in; its imports live beside the link."""
        real = write(home / "dotfiles/alacritty.toml", '[general]\nimport = ["themes/t.toml"]\n')
        write(home / ".config/alacritty/themes/t.toml", TOKYO_NIGHT)
        (home / ".config/alacritty/alacritty.toml").symlink_to(real)
        assert theme._from_alacritty_config() == TOKYO_PALETTE

    def test_importing_file_overrides_imported_colors(self, home: Path, theme) -> None:
        write(home / ".config/alacritty/tokyo.toml", TOKYO_NIGHT)
        main = write(
            home / ".config/alacritty/alacritty.toml",
            'general.import = ["tokyo.toml"]\n\n[colors.primary]\nbackground = "#000000"\n',
        )
        pal = theme._parse_alacritty(main)
        assert pal["bg"] == "#000000"
        assert pal["fg"] == "#a9b1d6"

    def test_import_cycle_terminates(self, home: Path, theme) -> None:
        a = write(home / "a.toml", 'general.import = ["b.toml"]\n')
        write(home / "b.toml", 'general.import = ["a.toml"]\n')
        assert theme._parse_alacritty(a) is None

    def test_no_colors_reports_not_found(self, home: Path, theme) -> None:
        """No placeholder palette when nothing is configured."""
        main = write(home / ".config/alacritty/alacritty.toml", "[font]\nsize = 11\n")
        assert theme._parse_alacritty(main) is None
        assert not any(theme._from_alacritty_config().values())

    def test_non_hex_values_are_dropped(self, home: Path, theme) -> None:
        main = write(
            home / "alacritty.toml",
            '[colors.primary]\nbackground = "#101010"\nforeground = "#f0f0f0"\n'
            '[colors.selection]\ntext = "CellForeground"\n',
        )
        pal = theme._parse_alacritty(main)
        assert pal["sel_fg"] == "#f0f0f0"
        assert pal["sel_bg"] is not None and pal["sel_bg"].startswith("#")


KITTY_THEME = """
cursor                #f8d9d7
background            #240f0f
foreground            #f8d9d7
selection_foreground  #f8d9d7
selection_background  #59302e
"""

KITTY_PALETTE = {
    "bg": "#240f0f",
    "fg": "#f8d9d7",
    "sel_bg": "#59302e",
    "sel_fg": "#f8d9d7",
    "caret": "#f8d9d7",
}


class TestKitty:
    def test_symlinked_config_with_relative_include(self, home: Path, theme) -> None:
        """kitty.conf symlinked from a dotfile repo, theme included from beside the link."""
        real = write(home / "dotfiles/kitty/kitty.conf", "font_size 11\ninclude themes/t.conf\n")
        write(home / ".config/kitty/themes/t.conf", KITTY_THEME)
        (home / ".config/kitty/kitty.conf").symlink_to(real)
        assert theme._from_kitty_config() == KITTY_PALETTE

    def test_last_assignment_wins(self, home: Path, theme) -> None:
        write(home / ".config/kitty/t.conf", "background #111111\nforeground #eeeeee\n")
        write(
            home / ".config/kitty/kitty.conf",
            "background #000000\ninclude t.conf\nforeground #222222\n",
        )
        pal = theme._from_kitty_config()
        assert pal["bg"] == "#111111"
        assert pal["fg"] == "#222222"

    def test_globinclude_and_options_with_shared_prefixes(self, home: Path, theme) -> None:
        write(home / ".config/kitty/colors/a.conf", "background #101010\n")
        write(home / ".config/kitty/colors/b.conf", "foreground #f0f0f0\n")
        write(
            home / ".config/kitty/kitty.conf",
            "globinclude colors/*.conf\nbackground_opacity 0.9\ncursor_shape beam\n",
        )
        pal = theme._from_kitty_config()
        assert (pal["bg"], pal["fg"], pal["caret"]) == ("#101010", "#f0f0f0", None)

    def test_honors_kitty_config_directory(
        self, home: Path, theme, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write(home / "elsewhere/kitty.conf", KITTY_THEME)
        monkeypatch.setenv("KITTY_CONFIG_DIRECTORY", str(home / "elsewhere"))
        assert theme._from_kitty_config() == KITTY_PALETTE

    def test_include_cycle_terminates(self, home: Path, theme) -> None:
        write(home / ".config/kitty/kitty.conf", "include other.conf\n")
        write(home / ".config/kitty/other.conf", "include kitty.conf\n")
        assert not any(theme._from_kitty_config().values())

    def test_no_colors_reports_not_found(self, home: Path, theme) -> None:
        write(home / ".config/kitty/kitty.conf", "font_size 11\n")
        assert not any(theme._from_kitty_config().values())


class TestApplyBestTheme:
    @pytest.fixture
    def applied(self, theme, monkeypatch: pytest.MonkeyPatch) -> list:
        calls: list = []
        monkeypatch.setattr(
            theme, "_apply_css", lambda css=None, path=None: calls.append((css, path))
        )
        return calls

    def test_palette_becomes_css(self, home: Path, theme, applied: list) -> None:
        write(home / ".local/state/omarchy/current/theme/alacritty.toml", TOKYO_NIGHT)
        theme.apply_best_theme()
        css, path = applied[-1]
        assert "@define-color term_bg #1a1b26;" in css

    def test_kitty_palette_is_used(self, home: Path, theme, applied: list) -> None:
        write(home / ".config/kitty/kitty.conf", KITTY_THEME)
        theme.apply_best_theme()
        assert "@define-color term_bg #240f0f;" in applied[-1][0]

    def test_alacritty_wins_over_kitty(self, home: Path, theme, applied: list) -> None:
        write(home / ".config/kitty/kitty.conf", KITTY_THEME)
        write(home / ".config/alacritty/alacritty.toml", TOKYO_NIGHT)
        theme.apply_best_theme()
        assert "@define-color term_bg #1a1b26;" in applied[-1][0]

    def test_floating_bar_style_does_not_frame_every_stack(self, theme) -> None:
        """Each editor sits in a Gtk.Stack (editor/preview); only the find bar gets the frame."""
        css = theme._css_from_palette(TOKYO_PALETTE, dark=True)
        assert "stack.floating-bar {" in css
        assert "\nstack {" not in css

    def test_popover_shadow_margin_stays_transparent(self, theme) -> None:
        """Popovers have the .background class; only their menu should be painted."""
        css = theme._css_from_palette(TOKYO_PALETTE, dark=True)
        selectors = [line.split("{")[0] for line in css.splitlines() if line.endswith("{")]
        assert not any(".background" in sel for sel in selectors)
        assert "popover > contents, popover > arrow {" in css

    def test_nothing_detected_inherits_system_theme(self, theme, applied: list) -> None:
        """No more flat-gray override when no palette exists anywhere."""
        theme.apply_best_theme()
        assert applied[-1] == (None, None)

    def test_nothing_detected_uses_user_gtk_css(self, home: Path, theme, applied: list) -> None:
        gtk_css = write(home / ".config/gtk-4.0/gtk.css", "/* user css */\n")
        theme.apply_best_theme()
        assert applied[-1] == (None, gtk_css)
