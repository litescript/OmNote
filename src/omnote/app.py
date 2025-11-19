from __future__ import annotations

import os
import sys

from gi import require_version

require_version("Gtk", "4.0")
require_version("Adw", "1")
require_version("Gdk", "4.0")

from gi.repository import Adw, Gio

from .state import State
from .theme import apply_best_theme, start_theme_watcher, stop_theme_watcher
from .window import OmNoteWindow

# Application ID for .desktop file integration
APP_ID = "dev.omarchy.OmNote"


class OmNote(Adw.Application):
    def __init__(self) -> None:
        # NOTE: GApplication subclass
        Adw.Application.__init__(self, application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._state: State | None = None
        self._theme_watcher: object | None = None  # ThemeWatcher type from theme module

        # If the last window is removed, quit the app loop (belt-and-suspenders)
        self.connect("window-removed", self._on_window_removed)

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        apply_best_theme()
        # Check OMNOTE_NO_WATCH first, fall back to MICROPAD_NO_WATCH (legacy)
        if not (os.getenv("OMNOTE_NO_WATCH") or os.getenv("MICROPAD_NO_WATCH")):
            self._theme_watcher = start_theme_watcher()

    def do_activate(self) -> None:
        # Create a window if none exists; otherwise present the current one
        if not self.props.active_window:
            self._state = State.load()
            win = OmNoteWindow(self, self._state)
            win.present()
        else:
            self.props.active_window.present()

    def do_shutdown(self) -> None:
        # Cleanly stop theme watcher so no monitors/timeouts hold the loop
        try:
            stop_theme_watcher()
        except Exception:
            pass
        Adw.Application.do_shutdown(self)

    # ---- helpers ----
    def _on_window_removed(self, app: OmNote, _win) -> None:
        # If no more windows remain, end the app loop explicitly
        if not app.get_windows():
            app.quit()


def main() -> int:
    Adw.init()
    app = OmNote()
    return app.run(sys.argv)
