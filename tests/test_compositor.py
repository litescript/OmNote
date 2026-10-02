"""Tests for omnote.compositor (who draws the window's rounded corners)."""
from __future__ import annotations

from pathlib import Path

import pytest

from omnote import compositor


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "config"
    home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    monkeypatch.delenv("OMNOTE_SQUARE_CORNERS", raising=False)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "umbriel")
    return home


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_umbriel_defaults_to_drawing_its_own_border(config_home: Path) -> None:
    """prefer_no_csd defaults to true in umbriel, so no config still means square."""
    assert compositor.compositor_rounds_corners()


def test_umbriel_with_client_decorations_keeps_libadwaita_corners(config_home: Path) -> None:
    write(config_home / "umbriel/config.toml", "[appearance]\nprefer_no_csd = false\n")
    assert not compositor.compositor_rounds_corners()


def test_other_desktops_keep_libadwaita_corners(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert not compositor.compositor_rounds_corners()


def test_desktop_list_is_matched_per_entry(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "wlroots:Umbriel")
    assert compositor.compositor_rounds_corners()


@pytest.mark.parametrize("forced, expected", [("1", True), ("0", False)])
def test_env_override_wins(
    config_home: Path, monkeypatch: pytest.MonkeyPatch, forced: str, expected: bool
) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "Hyprland")
    monkeypatch.setenv("OMNOTE_SQUARE_CORNERS", forced)
    assert compositor.compositor_rounds_corners() is expected


def test_includes_apply_before_the_file_itself(config_home: Path) -> None:
    """Required, then optional includes, then the file: the file wins."""
    write(config_home / "base.toml", "[appearance]\nprefer_no_csd = false\n")
    write(config_home / "umbriel/extra.toml", "[appearance]\nprefer_no_csd = true\n")
    main = write(
        config_home / "umbriel/config.toml",
        f'[include]\nfiles = ["{config_home}/base.toml"]\n'
        '[include.optional]\nfiles = ["extra.toml", "missing.toml"]\n',
    )
    assert compositor.umbriel_prefers_no_csd(main)  # optional include overrides base

    main.write_text(main.read_text() + "[appearance]\nprefer_no_csd = false\n")
    assert not compositor.umbriel_prefers_no_csd(main)  # and the file overrides both


def test_symlinked_config_resolves_includes_next_to_the_link(config_home: Path) -> None:
    """Like umbriel: relative includes resolve beside the symlink, not its target."""
    real = write(
        config_home / "dotfiles/umbriel.toml", '[include]\nfiles = ["base.toml"]\n'
    )
    write(config_home / "umbriel/base.toml", "[appearance]\nprefer_no_csd = false\n")
    (config_home / "umbriel/config.toml").symlink_to(real)
    assert not compositor.compositor_rounds_corners()


def test_include_cycle_and_broken_toml_fall_back_to_default(config_home: Path) -> None:
    write(config_home / "umbriel/config.toml", '[include]\nfiles = ["other.toml"]\n')
    write(config_home / "umbriel/other.toml", '[include]\nfiles = ["config.toml"]\n')
    assert compositor.compositor_rounds_corners()
    write(config_home / "umbriel/config.toml", "this is [not toml\n")
    assert compositor.compositor_rounds_corners()
