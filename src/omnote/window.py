from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gi import require_version

require_version("Gtk", "4.0")
require_version("Adw", "1")
require_version("Gdk", "4.0")
require_version("GtkSource", "5")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, GtkSource

from .state import State, TabState

# Debug logging setup
DEBUG_LOG = Path.home() / ".cache" / "omnote" / "debug.log"
DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)

def _log(msg: str) -> None:
    """Write debug message to log file with size cap (1MB max)."""
    try:
        # Cap log size at 1MB to prevent unbounded growth
        if DEBUG_LOG.exists() and DEBUG_LOG.stat().st_size > 1_000_000:
            DEBUG_LOG.write_text(f"[Log rotated]\n{msg}\n")
        else:
            with open(DEBUG_LOG, "a") as f:
                f.write(f"{msg}\n")
    except Exception:
        pass

# Clear log at session start
try:
    DEBUG_LOG.write_text("")
except Exception:
    pass


class DocumentTab:
    """Represents a single document tab with its own view, buffer, and file state."""
    def __init__(self) -> None:
        self.view = GtkSource.View()
        self.view.set_monospace(True)
        self.view.set_show_line_numbers(False)
        self.view.set_editable(True)
        self.view.set_focusable(True)

        # Disable GtkSourceView's built-in style scheme to use our CSS theme
        buf = self.view.get_buffer()
        buf.set_style_scheme(None)

        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_top_margin(12)
        self.view.set_bottom_margin(12)
        self.view.set_left_margin(14)
        self.view.set_right_margin(14)

        self.buffer = self.view.get_buffer()
        self.file: Gio.File | None = None
        self.changed = False

        # Signal handlers
        self.sid_changed: int | None = None
        self.sid_mark: int | None = None


class OmNoteWindow(Adw.ApplicationWindow):
    """Main window with TextView, inline Find/Replace, file ops, and animated status bar."""

    def __init__(self, app: Adw.Application, state: State) -> None:
        super().__init__(application=app)
        self.set_title("OmNote")
        self.set_default_size(900, 700)

        self.state = state
        self._closing = False

        # Tab management
        self.tab_view: Adw.TabView | None = None
        self.tabs: dict[Adw.TabPage, DocumentTab] = {}  # Map TabPage to DocumentTab

        # timers / signal ids
        self._status_tid: int | None = None
        self._search_tid: int | None = None
        # Track (widget, signal_id) pairs for cleanup - use Any for widget type
        self._signal_ids: list[tuple[Gtk.Widget, int]] = []

        # ---------- layout ----------
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(root)

        # header
        self.header = Adw.HeaderBar()

        new_btn  = Gtk.Button.new_from_icon_name("document-new-symbolic")
        open_btn = Gtk.Button.new_from_icon_name("document-open-symbolic")
        save_btn = Gtk.Button.new_from_icon_name("document-save-symbolic")
        find_btn = Gtk.Button.new_from_icon_name("edit-find-symbolic")
        repl_btn = Gtk.Button.new_from_icon_name("edit-find-replace-symbolic")

        new_btn.set_tooltip_text("New (Ctrl+N)")
        open_btn.set_tooltip_text("Open… (Ctrl+O)")
        save_btn.set_tooltip_text("Save (Ctrl+S)")
        find_btn.set_tooltip_text("Find (Ctrl+F)")
        repl_btn.set_tooltip_text("Replace (Ctrl+H)")

        sid = new_btn.connect("clicked", lambda *_: self._new_file())
        self._signal_ids.append((new_btn, sid))
        sid = open_btn.connect("clicked", lambda *_: self._open_dialog())
        self._signal_ids.append((open_btn, sid))
        sid = save_btn.connect("clicked", lambda *_: self._save_file())
        self._signal_ids.append((save_btn, sid))
        sid = find_btn.connect("clicked", lambda *_: self._show_find())
        self._signal_ids.append((find_btn, sid))
        sid = repl_btn.connect("clicked", lambda *_: self._show_replace())
        self._signal_ids.append((repl_btn, sid))

        self.header.pack_start(new_btn)
        self.header.pack_start(open_btn)
        self.header.pack_start(save_btn)
        self.header.pack_end(find_btn)
        self.header.pack_end(repl_btn)

        root.append(self.header)

        # Create overlay container for floating find/replace bars
        overlay = Gtk.Overlay()
        overlay.set_vexpand(True)
        overlay.set_hexpand(True)

        # top bar stack container (hidden when idle; animates when shown)
        self.top_stack = Gtk.Stack()
        self.top_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_DOWN)
        self.top_stack.set_hexpand(False)  # Don't expand horizontally
        self.top_stack.set_vexpand(False)
        self.top_stack.set_visible(False)  # collapse when no bar is shown
        self.top_stack.set_halign(Gtk.Align.CENTER)  # Center horizontally
        self.top_stack.set_valign(Gtk.Align.START)  # Align to top
        self.top_stack.set_margin_top(8)
        sid = self.top_stack.connect("notify::transition-running", self._on_stack_transition)
        self._signal_ids.append((self.top_stack, sid))

        # find bar
        self.find_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=6, margin_bottom=6, margin_start=8, margin_end=8
        )
        self.find_entry = Gtk.SearchEntry()
        self.find_entry.set_placeholder_text("Find…")
        self.find_entry.set_focusable(True)
        sid = self.find_entry.connect("search-changed", self._on_find_changed)
        self._signal_ids.append((self.find_entry, sid))
        sid = self.find_entry.connect("activate", self._on_find_activate)
        self._signal_ids.append((self.find_entry, sid))

        # Escape key handler for find bar
        find_key_ctrl = Gtk.EventControllerKey()
        find_key_ctrl.connect("key-pressed", self._on_find_key_pressed)
        self.find_entry.add_controller(find_key_ctrl)

        self.find_prev_btn = Gtk.Button.new_with_mnemonic("_Prev")
        sid = self.find_prev_btn.connect("clicked", lambda *_: self.find_next(forward=False))
        self._signal_ids.append((self.find_prev_btn, sid))
        self.find_next_btn = Gtk.Button.new_with_mnemonic("_Next")
        sid = self.find_next_btn.connect("clicked", lambda *_: self.find_next(forward=True))
        self._signal_ids.append((self.find_next_btn, sid))
        self.find_close_btn = Gtk.Button.new_with_mnemonic("_Close")
        sid = self.find_close_btn.connect("clicked", lambda *_: self._hide_find())
        self._signal_ids.append((self.find_close_btn, sid))

        for w in (self.find_entry, self.find_prev_btn, self.find_next_btn, self.find_close_btn):
            self.find_box.append(w)

        # replace bar
        self.replace_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=6, margin_bottom=6, margin_start=8, margin_end=8
        )
        self.replace_find_entry = Gtk.Entry()
        self.replace_find_entry.set_placeholder_text("Find…")
        self.replace_find_entry.set_focusable(True)
        self.replace_with_entry = Gtk.Entry()
        self.replace_with_entry.set_placeholder_text("Replace with…")
        self.replace_with_entry.set_focusable(True)

        # Escape key handlers for replace bar
        replace_find_key_ctrl = Gtk.EventControllerKey()
        replace_find_key_ctrl.connect("key-pressed", self._on_replace_key_pressed)
        self.replace_find_entry.add_controller(replace_find_key_ctrl)

        replace_with_key_ctrl = Gtk.EventControllerKey()
        replace_with_key_ctrl.connect("key-pressed", self._on_replace_key_pressed)
        self.replace_with_entry.add_controller(replace_with_key_ctrl)

        self.replace_one_btn = Gtk.Button(label="Replace")
        self.replace_all_btn = Gtk.Button(label="Replace All")
        self.replace_close_btn = Gtk.Button(label="Close")

        sid = self.replace_find_entry.connect("changed", self._on_replace_find_changed)
        self._signal_ids.append((self.replace_find_entry, sid))
        sid = self.replace_find_entry.connect(
            "activate", lambda *_: self.find_next(forward=True, use_replace_field=True)
        )
        self._signal_ids.append((self.replace_find_entry, sid))
        sid = self.replace_with_entry.connect(
            "activate", lambda *_: self._replace_current_or_next()
        )
        self._signal_ids.append((self.replace_with_entry, sid))
        sid = self.replace_one_btn.connect("clicked", lambda *_: self._replace_current_or_next())
        self._signal_ids.append((self.replace_one_btn, sid))
        sid = self.replace_all_btn.connect("clicked", lambda *_: self._replace_all())
        self._signal_ids.append((self.replace_all_btn, sid))
        sid = self.replace_close_btn.connect("clicked", lambda *_: self._hide_replace())
        self._signal_ids.append((self.replace_close_btn, sid))

        for w in (
            self.replace_find_entry,
            self.replace_with_entry,
            self.replace_one_btn,
            self.replace_all_btn,
            self.replace_close_btn,
        ):
            self.replace_box.append(w)

        # stack pages
        self.top_stack.add_named(self.find_box, "find")
        self.top_stack.add_named(self.replace_box, "replace")

        # empty placeholder (used during hide animation)
        self.empty_bar = Gtk.Box()
        self.top_stack.add_named(self.empty_bar, "empty")
        self.top_stack.set_visible_child_name("empty")

        # Create container for tabs (will be the base layer of overlay)
        tabs_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tabs_container.set_vexpand(True)
        tabs_container.set_hexpand(True)

        # Tab bar
        tab_bar = Adw.TabBar()
        tab_bar.set_expand_tabs(False)  # Fixed-width tabs like Firefox
        tabs_container.append(tab_bar)

        # Tab view for multi-document interface
        self.tab_view = Adw.TabView()
        self.tab_view.set_vexpand(True)
        self.tab_view.set_hexpand(True)
        tab_bar.set_view(self.tab_view)

        # Use CONTROL_TAB shortcuts (Ctrl+Tab, Ctrl+Shift+Tab) for tab switching
        # This disables Ctrl+Home/End/PgUp/PgDn so they work in the text editor
        self.tab_view.set_shortcuts(Adw.TabViewShortcuts.CONTROL_TAB)

        # Connect tab change signal
        sid = self.tab_view.connect("notify::selected-page", self._on_tab_changed)
        self._signal_ids.append((self.tab_view, sid))

        # Tab view wrapper with margins
        tab_view_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tab_view_wrapper.set_margin_top(6)
        tab_view_wrapper.set_margin_bottom(6)
        tab_view_wrapper.set_margin_start(8)
        tab_view_wrapper.set_margin_end(8)
        tab_view_wrapper.append(self.tab_view)

        tabs_container.append(tab_view_wrapper)

        # Set tabs_container as base layer of overlay
        overlay.set_child(tabs_container)

        # Add floating find/replace bar as overlay
        overlay.add_overlay(self.top_stack)

        # Add overlay to root
        root.append(overlay)

        # footer / status
        self.status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=4, margin_bottom=4, margin_start=10, margin_end=10
        )
        self.status_label = Gtk.Label(label="Ln: 1  Col: 1  |  Length: 0")
        self.status_label.set_xalign(0.0)
        self.status_box.append(self.status_label)
        root.append(self.status_box)

        # actions + shortcuts
        self._install_file_accels()
        self._install_shortcuts()

        # Restore tabs from state
        if self.state.tabs:
            for _i, tab_state in enumerate(self.state.tabs):
                if tab_state.file_path:
                    # Tab with saved file
                    f = Gio.File.new_for_path(tab_state.file_path)
                    page = self._create_tab(Path(tab_state.file_path).name, f)
                    doc_tab = self.tabs[page]
                    doc_tab.view.set_show_line_numbers(tab_state.show_line_numbers)
                    self._open_file_gfile(f, tab_state)
                else:
                    # Tab without file - restore unsaved content
                    page = self._create_tab()
                    doc_tab = self.tabs[page]
                    doc_tab.view.set_show_line_numbers(tab_state.show_line_numbers)

                    # Restore buffer content if available
                    if tab_state.unsaved_content:
                        doc_tab.buffer.set_text(tab_state.unsaved_content)
                        # Restore cursor position
                        try:
                            it = doc_tab.buffer.get_iter_at_line_offset(
                                tab_state.cursor_line, tab_state.cursor_col
                            )
                            doc_tab.buffer.place_cursor(it)
                        except Exception:
                            pass
                        # Reset changed flag since we just loaded saved content
                        doc_tab.changed = False

                    # Ensure view is editable and focusable
                    doc_tab.view.set_editable(True)
                    doc_tab.view.set_focusable(True)

            # Select the previously active tab
            if (
                self.tab_view
                and 0 <= self.state.active_tab_index < self.tab_view.get_n_pages()
            ):
                page = self.tab_view.get_nth_page(self.state.active_tab_index)
                self.tab_view.set_selected_page(page)
        else:
            # No saved tabs, create a blank one
            self._create_tab()

        # Focus and update
        def _initial_focus():
            view = self._get_current_view()
            if view:
                view.grab_focus()
            self._update_status()
            return False

        GLib.idle_add(_initial_focus)

        # clean shutdown
        self.connect("close-request", self._on_close_request)

    # ---------- tab management helpers ----------

    def _get_current_tab(self) -> DocumentTab | None:
        """Get the currently active DocumentTab, or None."""
        if not self.tab_view:
            return None
        page = self.tab_view.get_selected_page()
        return self.tabs.get(page) if page else None

    def _get_current_view(self) -> GtkSource.View | None:
        """Get the view for the current tab."""
        tab = self._get_current_tab()
        return tab.view if tab else None

    def _get_current_buffer(self) -> Gtk.TextBuffer | None:
        """Get the buffer for the current tab."""
        tab = self._get_current_tab()
        return tab.buffer if tab else None

    def _create_tab(self, title: str = "Untitled", file: Gio.File | None = None) -> Adw.TabPage:
        """Create a new tab with a DocumentTab."""
        assert self.tab_view is not None
        doc_tab = DocumentTab()
        doc_tab.file = file

        # Connect buffer signals
        doc_tab.sid_changed = doc_tab.buffer.connect("changed", self._on_buffer_changed)
        doc_tab.sid_mark = doc_tab.buffer.connect("mark-set", self._on_mark_set)

        # Wrap view in scrolled window
        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_child(doc_tab.view)

        # Add to tab view
        page = self.tab_view.append(scroller)
        page.set_title(title)
        self.tabs[page] = doc_tab

        return page

    def _close_tab(self, page: Adw.TabPage) -> bool:
        """Close a tab. Returns False if user cancels."""
        assert self.tab_view is not None
        doc_tab = self.tabs.get(page)
        if not doc_tab:
            return True

        # Check if modified
        if doc_tab.changed and not self._confirm_discard():
            return False

        # Disconnect signals
        if doc_tab.sid_changed:
            doc_tab.buffer.disconnect(doc_tab.sid_changed)
        if doc_tab.sid_mark:
            doc_tab.buffer.disconnect(doc_tab.sid_mark)

        # Remove from tracking
        del self.tabs[page]

        # Close the tab
        self.tab_view.close_page(page)

        # If no tabs left, create a new one
        if self.tab_view.get_n_pages() == 0:
            self._create_tab()

        return True

    def _on_tab_changed(self, tab_view: Adw.TabView, param) -> None:
        """Called when the selected tab changes."""
        if self._closing:
            return
        self._update_status()
        self._update_title()
        view = self._get_current_view()
        if view:
            GLib.idle_add(lambda: (view.grab_focus(), False)[1])

    # ---------- helper: bar visibility / focus coordination with animation ----------

    def _set_bar(self, name: str | None) -> None:
        """
        Show given bar ('find' or 'replace') with slide-down, or hide with slide-up.
        We collapse the stack (set_visible(False)) only after the hide animation finishes.
        """
        view = self._get_current_view()
        if not view:
            return

        if name is None:
            # hide with slide-up transition
            self.top_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP)
            self.top_stack.set_visible_child_name("empty")
            view.set_focusable(True)
            # actual set_visible(False) happens in _on_stack_transition when animation ends
            return

        # show specific bar with slide-down
        self.top_stack.set_visible(True)  # make space so animation is visible
        self.top_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_DOWN)
        self.top_stack.set_visible_child_name(name)
        view.set_focusable(False)  # keep TextView from stealing focus

    def _on_stack_transition(self, *_args) -> None:
        """
        After a transition completes, if we're on 'empty', collapse the stack's height.
        """
        try:
            # Gtk.Stack.get_transition_running() exists in GTK4; be defensive
            running = getattr(self.top_stack, "get_transition_running", lambda: False)()
            if running:
                return
        except Exception:
            # if property missing, just proceed
            pass

        if self.top_stack.get_visible_child_name() == "empty":
            self.top_stack.set_visible(False)
            # make sure the editor regains focus after collapse
            def _refocus():
                view = self._get_current_view()
                if view:
                    view.grab_focus()
                return False
            GLib.idle_add(_refocus)

    # ---------- actions, shortcuts ----------

    def _install_file_accels(self) -> None:
        actions: dict[str, tuple[Callable[[], None], list[str]]] = {
            "new": (self._new_file, ["<Primary>n", "<Primary>t"]),  # Ctrl+N or Ctrl+T for new tab
            "open": (self._open_dialog, ["<Primary>o"]),
            "save": (self._save_file, ["<Primary>s"]),
            "quit": (self._maybe_close, ["<Primary>q"]),
            "close-tab": (self._close_current_tab, ["<Primary>w"]),  # Ctrl+W to close tab
            "toggle-line-numbers": (self._toggle_line_numbers, ["<Primary>l"]),
            "next-tab": (self._next_tab, ["<Primary>Tab"]),  # Ctrl+Tab
            "prev-tab": (self._prev_tab, ["<Primary><Shift>Tab"]),  # Ctrl+Shift+Tab
        }
        for name, (cb, accels) in actions.items():
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda _a, _p, cb=cb: cb())
            self.add_action(act)
            self.get_application().set_accels_for_action(f"win.{name}", accels)

    def _install_shortcuts(self) -> None:
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def _idle(fn):
            if self._closing:
                return
            GLib.idle_add(lambda: (not self._closing and fn() is None, False)[1])

        trig_f = Gtk.ShortcutTrigger.parse_string("<Control>F")
        act_f = Gtk.CallbackAction.new(lambda *_: (_idle(self._show_find), True)[1])
        ctrl.add_shortcut(Gtk.Shortcut.new(trig_f, act_f))

        trig_h = Gtk.ShortcutTrigger.parse_string("<Control>H")
        act_h = Gtk.CallbackAction.new(lambda *_: (_idle(self._show_replace), True)[1])
        ctrl.add_shortcut(Gtk.Shortcut.new(trig_h, act_h))

        self.add_controller(ctrl)

    def _toggle_line_numbers(self) -> None:
        """Toggle line numbers on/off in the GtkSourceView."""
        view = self._get_current_view()
        if not view:
            return
        current = view.get_show_line_numbers()
        view.set_show_line_numbers(not current)
        _log(f"Line numbers toggled: {current} -> {not current}")

    def _close_current_tab(self) -> None:
        """Close the currently active tab."""
        assert self.tab_view is not None
        page = self.tab_view.get_selected_page()
        if page:
            self._close_tab(page)

    def _next_tab(self) -> None:
        """Switch to the next tab."""
        if self.tab_view:
            self.tab_view.select_next_page()

    def _prev_tab(self) -> None:
        """Switch to the previous tab."""
        if self.tab_view:
            self.tab_view.select_previous_page()

    # ---------- file ops ----------

    def _new_file(self) -> None:
        # Create a new tab instead of clearing current one
        assert self.tab_view is not None
        page = self._create_tab()
        self.tab_view.set_selected_page(page)
        self._update_title()
        self._queue_status(10)

    def _open_dialog(self) -> None:
        # Open in new tab
        dlg = Gtk.FileDialog()
        dlg.set_title("Open File")
        dlg.open(self, None, self._on_open_done)

    def _on_open_done(self, dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
        if self._closing:
            return
        try:
            f = dlg.open_finish(res)
        except GLib.Error:
            return
        if f:
            assert self.tab_view is not None
            # Create new tab for the file
            filename = f.get_basename() or "Untitled"
            page = self._create_tab(filename, f)
            self.tab_view.set_selected_page(page)
            self._open_file_gfile(f)

    def _open_file_gfile(
        self, f: Gio.File, tab_state: TabState | None = None, target_tab: DocumentTab | None = None
    ) -> None:
        # Use specific tab if provided, otherwise current tab
        tab = target_tab if target_tab else self._get_current_tab()
        if not tab:
            return

        def _finish(obj: Gio.File, res: Gio.AsyncResult) -> None:
            if self._closing:
                return
            # Verify tab still exists in our tracking (wasn't closed during async operation)
            if tab not in [t for t in self.tabs.values()]:
                return
            try:
                stream = obj.read_finish(res)
            except GLib.Error as e:
                self._show_error_dialog("Failed to Open File", f"Could not read file:\n{e.message}")
                return
            try:
                data = (
                    stream.read_bytes(10_000_000, None).get_data().decode("utf-8", errors="replace")
                )
            except Exception as e:
                self._show_error_dialog("Failed to Read File", f"Error decoding file:\n{str(e)}")
                return
            tab.buffer.set_text(data)
            tab.file = f
            tab.changed = False

            # Restore cursor position if provided
            if tab_state:
                try:
                    it = tab.buffer.get_iter_at_line_offset(
                        tab_state.cursor_line, tab_state.cursor_col
                    )
                    tab.buffer.place_cursor(it)
                    if tab.view:
                        tab.view.scroll_to_iter(it, 0.0, False, 0.0, 0.0)
                except Exception:
                    pass

            self._update_title()
            self._queue_status(10)

        f.read_async(GLib.PRIORITY_DEFAULT, None, _finish)

    def _save_file(self) -> None:
        tab = self._get_current_tab()
        if not tab:
            return

        if tab.file is None:
            self._save_as_dialog()
            return

        # Capture file reference and data before async operation
        file_to_save = tab.file
        text = self._get_text()
        data = text.encode("utf-8")

        def _finish(obj: Gio.File, res: Gio.AsyncResult) -> None:
            if self._closing:
                return
            # Verify tab still exists
            if tab not in [t for t in self.tabs.values()]:
                return
            try:
                stream = obj.replace_finish(res)
            except GLib.Error as e:
                self._show_error_dialog("Failed to Save File", f"Could not save file:\n{e.message}")
                return
            try:
                stream.write(data)
                stream.close(None)
            except Exception as e:
                self._show_error_dialog("Failed to Write File", f"Error writing file:\n{str(e)}")
                return
            # Only mark as saved if the file reference hasn't changed
            if tab.file == file_to_save:
                tab.changed = False
            self._update_title()

        file_to_save.replace_async(
            None, False, Gio.FileCreateFlags.REPLACE_DESTINATION,
            GLib.PRIORITY_DEFAULT, None, _finish
        )

    def _save_as_dialog(self) -> None:
        dlg = Gtk.FileDialog()
        dlg.set_title("Save As")
        dlg.save(self, None, self._on_save_done)

    def _on_save_done(self, dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
        tab = self._get_current_tab()
        if self._closing or not tab:
            return
        try:
            f = dlg.save_finish(res)
        except GLib.Error:
            return
        if not f:
            return
        tab.file = f
        self._save_file()

    def _maybe_close(self) -> None:
        tab = self._get_current_tab()
        if tab and tab.changed and not self._confirm_discard():
            return
        self.close()

    def _confirm_discard(self) -> bool:
        """Show confirmation dialog for unsaved changes."""
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading("Unsaved Changes")
        dialog.set_body("This document has unsaved changes. Discard them?")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("discard", "Discard")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        # Run modal and get response
        response = [None]

        def on_response(dlg, result):
            response[0] = dlg.choose_finish(result)

        dialog.choose(None, on_response)

        # Process events until we get a response (simple modal approach)
        while response[0] is None:
            GLib.MainContext.default().iteration(True)

        return response[0] == "discard"

    def _show_error_dialog(self, title: str, message: str) -> None:
        """Show error dialog to user."""
        if self._closing:
            return
        dialog = Adw.MessageDialog.new(self)
        dialog.set_heading(title)
        dialog.set_body(message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present()

    # ---------- buffer / status ----------

    def _get_text(self) -> str:
        buf = self._get_current_buffer()
        if not buf:
            return ""
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return buf.get_text(start, end, True)

    def _set_text(self, text: str) -> None:
        buf = self._get_current_buffer()
        if buf:
            buf.set_text(text)

    def _on_buffer_changed(self, *_args) -> None:
        if self._closing:
            return
        tab = self._get_current_tab()
        if tab:
            tab.changed = True
        self._update_title()
        self._queue_status(30)

    def _on_mark_set(self, *_args) -> None:
        if self._closing:
            return
        self._queue_status(20)

    def _queue_status(self, delay_ms: int) -> None:
        if self._status_tid:
            GLib.source_remove(self._status_tid)
        self._status_tid = GLib.timeout_add(delay_ms, self._update_status)

    def _update_status(self) -> bool:
        self._status_tid = None
        if self._closing:
            return False

        buf = self._get_current_buffer()
        if not buf:
            return False

        try:
            insert_mark = buf.get_insert()
            it = buf.get_iter_at_mark(insert_mark)
            line = it.get_line() + 1
            col = it.get_line_offset() + 1
            start = buf.get_start_iter()
            end = buf.get_end_iter()
            length = len(buf.get_text(start, end, True))
            self.status_label.set_text(f"Ln: {line}  Col: {col}  |  Length: {length}")
        except Exception:
            pass
        return False

    def _update_title(self) -> None:
        tab = self._get_current_tab()
        if not tab:
            self.set_title("OmNote")
            return

        name = tab.file.get_basename() if tab.file else "Untitled"
        dirty = " •" if tab.changed else ""

        # Update window title
        self.set_title(f"OmNote — {name}{dirty}")

        # Update tab title
        if self.tab_view:
            page = self.tab_view.get_selected_page()
            if page:
                page.set_title(f"{name}{dirty}")

    # ---------- find / replace ----------

    def _show_find(self) -> None:
        if self._closing:
            return
        self._set_bar("find")
        GLib.timeout_add(0, self._force_focus_find)
        self._queue_search(lambda: self._highlight_first_match(False), 10)

    def _hide_find(self) -> None:
        self._set_bar(None)

    def _show_replace(self) -> None:
        if self._closing:
            return
        seed = self._current_selection_text() or self.find_entry.get_text()
        if seed:
            self.replace_find_entry.set_text(seed)
            self.replace_find_entry.set_position(-1)
        self._set_bar("replace")
        GLib.timeout_add(0, self._force_focus_replace)
        self._queue_search(lambda: self._highlight_first_match(True), 10)

    def _hide_replace(self) -> None:
        self._set_bar(None)

    def _on_find_key_pressed(self, _controller, keyval, _keycode, _state):
        """Handle Escape key in find bar."""
        if keyval == Gdk.KEY_Escape:
            self._hide_find()
            return True
        return False

    def _on_replace_key_pressed(self, _controller, keyval, _keycode, _state):
        """Handle Escape key in replace bar."""
        if keyval == Gdk.KEY_Escape:
            self._hide_replace()
            return True
        return False

    def _force_focus_find(self) -> bool:
        if (
            self._closing
            or not self.top_stack.get_visible()
            or self.top_stack.get_visible_child_name() != "find"
        ):
            return False
        try:
            self.set_focus(self.find_entry)
            self.find_entry.grab_focus()
            self.find_entry.set_position(-1)
        except Exception:
            pass
        return False

    def _force_focus_replace(self) -> bool:
        if (
            self._closing
            or not self.top_stack.get_visible()
            or self.top_stack.get_visible_child_name() != "replace"
        ):
            return False
        try:
            self.set_focus(self.replace_find_entry)
            self.replace_find_entry.grab_focus()
            self.replace_find_entry.set_position(-1)
        except Exception:
            pass
        return False

    def _on_find_changed(self, *_args) -> None:
        self._queue_search(lambda: self._highlight_first_match(False), 80)

    def _on_find_activate(self, *_args) -> None:
        self._queue_search(lambda: self.find_next(True, False), 0)

    def _on_replace_find_changed(self, *_args) -> None:
        self._queue_search(lambda: self._highlight_first_match(True), 80)

    def _queue_search(self, fn, delay_ms: int) -> None:
        if self._search_tid:
            GLib.source_remove(self._search_tid)
        self._search_tid = GLib.timeout_add(delay_ms, self._run_search, fn)

    def _run_search(self, fn) -> bool:
        self._search_tid = None
        if self._closing:
            return False
        try:
            fn()
        except Exception:
            pass
        return False

    def _current_selection_text(self) -> str:
        buf = self._get_current_buffer()
        if buf and buf.get_has_selection():
            s, e = buf.get_selection_bounds()
            return buf.get_text(s, e, True)
        return ""

    def _buffer_search(
        self, needle: str, start_iter: Gtk.TextIter, forward: bool
    ) -> tuple[Gtk.TextIter, Gtk.TextIter] | None:
        if not needle:
            return None
        flags = Gtk.TextSearchFlags.CASE_INSENSITIVE
        try:
            if forward:
                return start_iter.forward_search(needle, flags, None)
            return start_iter.backward_search(needle, flags, None)
        except Exception:
            return None

    def find_next(self, forward: bool = True, use_replace_field: bool = False) -> None:
        if self._closing:
            return

        buf = self._get_current_buffer()
        view = self._get_current_view()
        if not buf or not view:
            return

        try:
            needle = (
                self.replace_find_entry.get_text()
                if use_replace_field
                else self.find_entry.get_text()
            )
            if not needle:
                return

            insert_mark = buf.get_insert()
            cur = buf.get_iter_at_mark(insert_mark)

            if buf.get_has_selection() and forward:
                _s, cur = buf.get_selection_bounds()

            match = self._buffer_search(needle, cur, forward)
            if not match:
                start = buf.get_start_iter() if forward else buf.get_end_iter()
                match = self._buffer_search(needle, start, forward)
                if not match:
                    return

            mstart, mend = match
            buf.select_range(mstart, mend)
            view.scroll_to_iter(mstart, 0.25, False, 0.0, 0.0)
        except Exception:
            pass

    def _highlight_first_match(self, from_replace: bool) -> None:
        if self._closing:
            return

        buf = self._get_current_buffer()
        if not buf:
            return

        needle = self.replace_find_entry.get_text() if from_replace else self.find_entry.get_text()
        if not needle:
            return
        start = buf.get_start_iter()
        match = self._buffer_search(needle, start, True)
        if match:
            mstart, mend = match
            buf.select_range(mstart, mend)

    def _replace_current_or_next(self) -> None:
        if self._closing:
            return

        buf = self._get_current_buffer()
        if not buf:
            return

        find_text = self.replace_find_entry.get_text()
        repl_text = self.replace_with_entry.get_text()
        if not find_text:
            return

        if buf.get_has_selection():
            s, e = buf.get_selection_bounds()
            if buf.get_text(s, e, True).lower() == find_text.lower():
                buf.delete(s, e)
                ins = buf.get_iter_at_mark(buf.get_insert())
                buf.insert(ins, repl_text)
                ns = buf.get_iter_at_mark(buf.get_insert())
                ne = ns.copy()
                ne.forward_chars(len(repl_text))
                buf.select_range(ns, ne)

        self.find_next(forward=True, use_replace_field=True)

    def _replace_all(self) -> None:
        if self._closing:
            return

        buf = self._get_current_buffer()
        if not buf:
            return

        find_text = self.replace_find_entry.get_text()
        repl_text = self.replace_with_entry.get_text()
        if not find_text:
            return

        start = buf.get_start_iter()
        while True:
            match = self._buffer_search(find_text, start, True)
            if not match:
                break
            mstart, mend = match
            buf.delete(mstart, mend)
            ins = buf.get_iter_at_mark(buf.get_insert())
            buf.insert(ins, repl_text)
            start = buf.get_iter_at_mark(buf.get_insert())

    # ---------- teardown ----------

    def _save_all_tab_states(self) -> None:
        """Save all current tab states to persistent storage."""
        if not self.tab_view:
            return
        _log("=== Starting state save ===")
        tab_states = []
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            tab = self.tabs.get(page)
            if not tab:
                _log(f"Tab {i}: No DocumentTab found")
                continue

            # Get cursor position
            cursor_line = 0
            cursor_col = 0
            try:
                insert_mark = tab.buffer.get_insert()
                it = tab.buffer.get_iter_at_mark(insert_mark)
                cursor_line = it.get_line()
                cursor_col = it.get_line_offset()
            except Exception as e:
                _log(f"Tab {i}: Error getting cursor position: {e}")

            file_path = tab.file.get_path() if tab.file else None
            show_lines = tab.view.get_show_line_numbers() if tab.view else False

            # Save buffer content if there's no file (unsaved tab)
            unsaved_content = None
            if not file_path:
                try:
                    start = tab.buffer.get_start_iter()
                    end = tab.buffer.get_end_iter()
                    unsaved_content = tab.buffer.get_text(start, end, True)
                except Exception as e:
                    _log(f"Tab {i}: Error getting buffer content: {e}")

            tab_state = TabState(
                file_path=file_path,
                cursor_line=cursor_line,
                cursor_col=cursor_col,
                show_line_numbers=show_lines,
                unsaved_content=unsaved_content,
            )
            tab_states.append(tab_state)
            content_preview = f", content={len(unsaved_content)} chars" if unsaved_content else ""
            _log(
                f"Tab {i}: file={file_path}, cursor={cursor_line}:{cursor_col}, "
                f"lines={show_lines}{content_preview}"
            )

        # Update state
        self.state.tabs = tab_states
        selected_page = self.tab_view.get_selected_page()
        if selected_page:
            active_idx = self.tab_view.get_page_position(selected_page)
        else:
            active_idx = 0

        # Invariant: active index must be within tab bounds
        assert 0 <= active_idx < len(tab_states) if tab_states else active_idx == 0
        self.state.active_tab_index = active_idx

        _log(f"Saving {len(tab_states)} tabs, active={active_idx}")
        self.state.save()
        _log("State saved successfully")

    def _on_close_request(self, *_args):
        self._closing = True

        # Save all tab states before closing
        try:
            self._save_all_tab_states()
        except Exception as e:
            _log(f"ERROR: Failed to save tab states: {e}")
            import traceback
            _log(traceback.format_exc())

        for tid in (self._status_tid, self._search_tid):
            if tid:
                try:
                    GLib.source_remove(tid)
                except Exception:
                    pass
        self._status_tid = None
        self._search_tid = None

        # Disconnect all tab signals
        for _page, tab in self.tabs.items():
            if tab.sid_changed:
                try:
                    tab.buffer.disconnect(tab.sid_changed)
                except Exception:
                    pass
            if tab.sid_mark:
                try:
                    tab.buffer.disconnect(tab.sid_mark)
                except Exception:
                    pass

        # Disconnect all tracked window signals
        for widget, sid in self._signal_ids:
            try:
                widget.disconnect(sid)
            except Exception:
                pass
        self._signal_ids.clear()

        self.top_stack.set_visible_child_name("empty")
        # collapse after any residual transition callback
        GLib.idle_add(lambda: (self.top_stack.set_visible(False), False)[1])

        app = self.get_application()
        if app is not None:
            GLib.idle_add(lambda: (app.quit(), False)[1])

        return False
