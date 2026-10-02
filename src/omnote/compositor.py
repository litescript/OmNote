"""Compositor integration: deciding who draws the window's rounded corners.

libadwaita rounds its windows (15px) unless the compositor reports them as tiled. A
compositor that draws its own rounded border and clips the window to it, but leaves
floating windows untiled, ends up with libadwaita's corner inside its own tighter one,
and the gap between the two curves shows through. Squaring libadwaita's corners hands
the rounding to the compositor alone, the same as it already does for tiled windows.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib  # Py3.11+
except Exception:
    tomllib = None  # type: ignore

# What libadwaita applies to a tiled window: no radius, no 1px inner outline.
# border-radius also covers Adw.MessageDialog, which sets its own instead of the variable.
SQUARE_CORNERS_CSS = "window.csd { --window-radius: 0px; border-radius: 0; outline: none; }"


def _umbriel_config_path() -> Path:
    config_home = Path(os.getenv("XDG_CONFIG_HOME") or "~/.config").expanduser()
    return config_home / "umbriel" / "config.toml"


def _deep_merge(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict):
            dst[k] = _deep_merge(dst[k] if isinstance(dst.get(k), dict) else {}, v)
        else:
            dst[k] = v
    return dst


def _load_umbriel(path: Path, visited: set[Path] | None = None) -> dict:
    """An umbriel config with its includes folded in the way umbriel applies them:
    required includes, then optional ones, then the file itself, so the file wins.
    Relative include paths resolve from the including file as named, not from a
    symlink's target."""
    visited = set() if visited is None else visited
    try:
        key = path.resolve()
    except Exception:
        key = path
    if tomllib is None or key in visited or len(visited) > 16:
        return {}
    visited.add(key)
    try:
        # Inside the try: before Python 3.14, is_file() raises PermissionError for a
        # file in an unreadable directory instead of returning False
        if not path.is_file():
            return {}
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:  # unreadable or malformed reads as absent, i.e. umbriel's defaults
        return {}

    include = data.get("include")
    include = include if isinstance(include, dict) else {}
    optional = include.get("optional")
    optional = optional if isinstance(optional, dict) else {}

    merged: dict = {}
    for files in (include.get("files"), optional.get("files")):
        for raw in files if isinstance(files, list) else []:
            if not isinstance(raw, str):
                continue
            p = Path(raw).expanduser()
            _deep_merge(merged, _load_umbriel(p if p.is_absolute() else path.parent / p, visited))
    return _deep_merge(merged, data)


def umbriel_prefers_no_csd(path: Path | None = None) -> bool:
    """appearance.prefer_no_csd: umbriel draws a border-only decoration (default on)."""
    appearance = _load_umbriel(path or _umbriel_config_path()).get("appearance")
    value = appearance.get("prefer_no_csd") if isinstance(appearance, dict) else None
    return value if isinstance(value, bool) else True


def compositor_rounds_corners() -> bool:
    """Whether the compositor rounds and clips our windows itself.

    OMNOTE_SQUARE_CORNERS=1/0 forces the answer (for compositors not detected here).
    """
    forced = os.getenv("OMNOTE_SQUARE_CORNERS")
    if forced in ("0", "1"):
        return forced == "1"
    try:
        desktops = (os.getenv("XDG_CURRENT_DESKTOP") or "").lower().split(":")
        if "umbriel" in desktops:
            return umbriel_prefers_no_csd()
    except Exception:
        # This runs in do_startup: a detection bug must never keep OmNote from starting.
        # Keep libadwaita's own corners, as before detection existed.
        pass
    return False
