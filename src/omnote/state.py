from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gi.repository import GLib

APP_DIR_OLD = "micropad"
APP_DIR_NEW = "omnote"

CONF_BASE = Path(GLib.get_user_config_dir())
CONF_OLD = CONF_BASE / APP_DIR_OLD
CONF_NEW = CONF_BASE / APP_DIR_NEW

STATE_OLD = CONF_OLD / "state.json"
STATE_NEW = CONF_NEW / "state.json"


def _migrate_once() -> None:
    """
    One-time, best-effort migration:
    - If old state exists and new state does not, copy old -> new.
    - No deletion; old files are left in place for safety.
    """
    try:
        if STATE_OLD.exists() and not STATE_NEW.exists():
            CONF_NEW.mkdir(parents=True, exist_ok=True)
            STATE_NEW.write_text(STATE_OLD.read_text())
    except Exception:
        # Silent best-effort; we’ll still be able to read from old on load()
        pass


@dataclass
class Geometry:
    width: int = 800
    height: int = 600
    maximized: bool = False
    x: int | None = None
    y: int | None = None


@dataclass
class TabState:
    """State for a single document tab."""
    file_path: str | None = None
    cursor_line: int = 0
    cursor_col: int = 0
    show_line_numbers: bool = False
    unsaved_content: str | None = None  # Buffer content if no file_path


@dataclass
class State:
    tabs: list[TabState] = field(default_factory=list)
    active_tab_index: int = 0
    geometry: Geometry = field(default_factory=Geometry)

    @classmethod
    def load(cls) -> State:
        _migrate_once()

        # Prefer new location; fall back to old if needed
        for f in (STATE_NEW, STATE_OLD):
            try:
                if f.exists():
                    data = json.loads(f.read_text())
                    geom = Geometry(**data.get("geometry", {}))

                    # Load tabs if present, otherwise migrate from old "path" field
                    tabs = []
                    if "tabs" in data:
                        tabs = [TabState(**t) for t in data["tabs"]]
                    elif "path" in data and data["path"]:
                        # Migrate old single-file format
                        tabs = [TabState(file_path=data["path"])]

                    active_tab_index = data.get("active_tab_index", 0)
                    # Ensure active index is within bounds (defensive against corrupted state)
                    if active_tab_index < 0 or (tabs and active_tab_index >= len(tabs)):
                        active_tab_index = 0

                    return cls(tabs=tabs, active_tab_index=active_tab_index, geometry=geom)
            except Exception:
                # If corrupted, try the next option or return default
                continue
        return cls()

    def save(self) -> None:
        # Always save to the new location going forward
        CONF_NEW.mkdir(parents=True, exist_ok=True)
        data = {
            "tabs": [
                {
                    "file_path": t.file_path,
                    "cursor_line": t.cursor_line,
                    "cursor_col": t.cursor_col,
                    "show_line_numbers": t.show_line_numbers,
                    "unsaved_content": t.unsaved_content,
                }
                for t in self.tabs
            ],
            "active_tab_index": self.active_tab_index,
            "geometry": {
                "width": self.geometry.width,
                "height": self.geometry.height,
                "maximized": self.geometry.maximized,
                "x": self.geometry.x,
                "y": self.geometry.y,
            },
        }
        STATE_NEW.write_text(json.dumps(data, indent=2))
