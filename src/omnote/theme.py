from __future__ import annotations

import glob
import os
import re
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

# -------------------- optional parsers --------------------
try:
    import tomllib  # Py3.11+
except Exception:
    tomllib = None  # type: ignore

try:
    import yaml  # optional fallback
except Exception:
    yaml = None

# -------------------- globals / constants --------------------
_CURRENT_PROVIDER: Gtk.CssProvider | None = None
_WATCHER_SINGLETON: ThemeWatcher | None = None  # singleton handle

HEX_RE = (
    r"(?:#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})|"
    r"0x[0-9a-fA-F]{6}|rgb:[0-9a-fA-F]{2}/[0-9a-fA-F]{2}/[0-9a-fA-F]{2})"
)

OMARCHY_DIR      = Path("~/.config/omarchy").expanduser()
OMARCHY_THEMES   = OMARCHY_DIR / "themes"
OMARCHY_CURTHEME = OMARCHY_DIR / "current" / "theme"
OMARCHY_MARKERS  = [
    OMARCHY_DIR / "current-theme",
    OMARCHY_DIR / "theme",
    OMARCHY_DIR / "selected-theme",
]
HYPR_USER_CONF   = Path("~/.config/hypr/hyprland.conf").expanduser()

# -------------------- utils --------------------
def _getenv(var: str, default: str | None = None) -> str | None:
    """Get environment variable with OMNOTE_* preferred, MICROPAD_* fallback."""
    omnote_var = var.replace("MICROPAD_", "OMNOTE_")
    return os.getenv(omnote_var) or os.getenv(var) or default

def _dbg(msg: str) -> None:
    if _getenv("MICROPAD_DEBUG"):
        print(f"[OmNote:theme] {msg}")

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _norm_hex(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    if s.startswith("#") and len(s) in (7, 9):
        return s[:7]
    if s.startswith("0x") and len(s) == 8:
        return f"#{s[2:]}"
    if s.startswith("rgb:"):
        parts = s[4:].split("/")
        if len(parts) == 3 and all(len(p) == 2 for p in parts):
            return f"#{parts[0]}{parts[1]}{parts[2]}"
    return None

def _mix_color(hex_a: str, hex_b: str, t: float) -> str:
    def _clamp(x: int) -> int: return max(0, min(255, x))
    def _rgb(h: str) -> tuple[int,int,int]:
        h = h.strip().lstrip("#")
        if len(h) == 3:
            h = "".join(ch*2 for ch in h)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    def _hex(r: int,g: int,b: int) -> str: return f"#{r:02x}{g:02x}{b:02x}"
    try:
        a = _rgb(hex_a)
        b = _rgb(hex_b)
    except Exception:
        a = (30, 30, 30)
        b = (224, 224, 224)
    r = _clamp(round(a[0]*(1-t) + b[0]*t))
    g = _clamp(round(a[1]*(1-t) + b[1]*t))
    b_ = _clamp(round(a[2]*(1-t) + b[2]*t))
    return _hex(r,g,b_)

# -------------------- palette helpers --------------------
def _empty_palette() -> dict[str, str | None]:
    return {"bg": None, "fg": None, "sel_bg": None, "sel_fg": None, "caret": None}

def _css_from_palette(pal: dict[str, str | None], *, dark: bool) -> str:
    bg    = pal.get("bg")     or "#1e1e1e"
    fg    = pal.get("fg")     or "#e0e0e0"
    selbg = pal.get("sel_bg") or "alpha(@term_fg,0.15)"
    selfg = pal.get("sel_fg") or "@term_fg"
    caret = pal.get("caret")  or "@term_fg"

    entry_mix = 0.06 if dark else 0.12

    css = [
        "/* generated from palette */",
        f"@define-color term_bg {bg};",
        f"@define-color term_fg {fg};",
        f"@define-color term_sel_bg {selbg};",
        f"@define-color term_sel_fg {selfg};",
        f"@define-color term_caret {caret};",
        "",
        "window, .background {",
        "  background-color: @term_bg;",
        "  color: @term_fg;",
        "}",
        "textview, textview.view {",
        "  background-color: @term_bg;",
        "  color: @term_fg;",
        "}",
        "textview > text, textview.view > text {",
        "  background-color: @term_bg;",
        "  background-image: none;",
        "  color: @term_fg;",
        "  caret-color: @term_caret;",
        "}",
        "textview text selection {",
        "  background-color: @term_sel_bg;",
        "  color: @term_sel_fg;",
        "}",
        "/* GtkSourceView line numbers gutter */",
        "textview border, textview.view border {",
        "  background-color: @term_bg;",
        "  color: alpha(@term_fg, 0.5);",
        "}",
        "textview.view gutter, textview gutter {",
        "  background-color: @term_bg;",
        "}",
        "textview.view gutter.left, textview.view gutter.right {",
        "  background-color: @term_bg;",
        "}",
        "headerbar, .titlebar {",
        "  background-color: @term_bg;",
        "  color: @term_fg;",
        "  border-bottom: 1px solid alpha(@term_fg, 0.08);",
        "}",
        "entry, searchentry {",
        f"  background-color: mix(@term_bg, @term_fg, {entry_mix});",
        "  color: @term_fg;",
        "  border: 1px solid alpha(@term_fg, 0.15);",
        "}",
        "entry:focus, searchentry:focus {",
        "  border-color: alpha(@term_fg, 0.28);",
        "}",
        "entry selection, searchentry selection {",
        "  background-color: @term_sel_bg;",
        "  color: @term_sel_fg;",
        "}",
        "/* Floating find/replace bar styling */",
        "stack {",
        "  background-color: @term_bg;",
        "  border: 1px solid alpha(@term_fg, 0.2);",
        "  border-radius: 8px;",
        "  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);",
        "}",
        "/* Tab bar theming */",
        "tabbar, tabbar > scrolledwindow, tabbar > revealer > box {",
        "  background-color: @term_bg;",
        "}",
        "tabbar separator {",
        "  background: transparent;",
        "  min-width: 0;",
        "  min-height: 0;",
        "}",
        "tabbar tab, .tab {",
        "  background-color: alpha(@term_fg, 0.02);",
        "  color: alpha(@term_fg, 0.5);",
        "  border: none;",
        "  border-bottom: 2px solid transparent;",
        "  min-height: 28px;",
        "  min-width: 160px;",
        "  padding: 4px 14px;",
        "}",
        "tabbar tab > box, .tab > box {",
        "  min-width: 0;",
        "}",
        "tabbar tab:hover, .tab:hover {",
        "  background-color: alpha(@term_fg, 0.05);",
        "  color: alpha(@term_fg, 0.8);",
        "}",
        (
            "tabbar tab:selected, tabbar tab:checked, tabbar tab:active, "
            ".tab:selected, .tab:checked, .tab:active {"
        ),
        "  background-color: alpha(@term_fg, 0.12);",
        "  color: @term_fg;",
        "  border-bottom: 2px solid alpha(@term_fg, 0.5);",
        "  font-weight: 500;",
        "}",
        "tabbar .start-action, tabbar .end-action {",
        "  background-color: @term_bg;",
        "}",
        "tabbar button {",
        "  background: transparent;",
        "  border: none;",
        "  color: alpha(@term_fg, 0.5);",
        "  min-height: 24px;",
        "  min-width: 24px;",
        "}",
        "tabbar button:hover {",
        "  color: @term_fg;",
        "  background-color: alpha(@term_fg, 0.15);",
        "}",
    ]
    return "\n".join(css)

# -------------------- detect active Omarchy theme dir --------------------
def _omarchy_current_dir() -> Path | None:
    if OMARCHY_CURTHEME.exists():
        return OMARCHY_CURTHEME

    cand = OMARCHY_THEMES / "current"
    if cand.exists():
        try:
            p = cand.resolve()
            if p.is_dir():
                return p
        except Exception:
            pass

    for m in OMARCHY_MARKERS:
        if m.exists():
            name = _read(m).strip()
            if name:
                p = (OMARCHY_THEMES / name).expanduser()
                if p.is_dir():
                    return p

    if HYPR_USER_CONF.exists():
        txt = _read(HYPR_USER_CONF)
        m = re.search(
            r"(?mi)^\s*(?:source|include)\s*=\s*(?P<p>.+omarchy/.+?/themes/(?P<name>[^/]+)/hyprland\.conf)\s*$",
            txt,
        )
        if m:
            name = m.group("name")
            p = (OMARCHY_THEMES / name).expanduser()
            if p.is_dir():
                return p
    return None

# -------------------- Alacritty parsing --------------------
ALACRITTY_MAIN_CANDIDATES = [
    lambda: os.getenv("ALACRITTY_CONFIG"),
    lambda: str(Path("~/.config/alacritty/alacritty.yml").expanduser()),
    lambda: str(Path("~/.config/alacritty/alacritty.yaml").expanduser()),
    lambda: str(Path("~/.config/alacritty/alacritty.toml").expanduser()),
    lambda: str(Path("~/.alacritty.yml").expanduser()),
]

IMPORT_LINE_RE = re.compile(r'(?mi)^\s*(imports?|import)\s*:\s*(?P<val>.+)$')
QUOTED_PATH_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')
DASHED_ITEM_RE = re.compile(r'(?mi)^\s*-\s*(?:"([^"]+)"|\'([^\']+)\')\s*$')

def _parse_alacritty(path: Path) -> dict[str, str | None] | None:
    if not path.exists():
        return None
    text = _read(path)
    data = None

    if path.suffix.lower() == ".toml" and tomllib is not None:
        try:
            data = tomllib.loads(text)
        except Exception as e:
            _dbg(f"TOML parse failed for {path}: {e}")

    if data is None and yaml is not None and path.suffix.lower() in {".yml", ".yaml"}:
        try:
            data = yaml.safe_load(text)
        except Exception as e:
            _dbg(f"YAML parse failed for {path}: {e}")

    if not isinstance(data, dict):
        return None

    colors   = data.get("colors") or {}
    primary  = colors.get("primary") or {}
    normal   = colors.get("normal") or {}
    bright   = colors.get("bright") or {}
    select   = colors.get("selection") or {}

    bg = primary.get("background")
    fg = primary.get("foreground")

    sel_bg = select.get("background")
    sel_fg = select.get("text") or select.get("foreground")

    if not sel_bg:
        sel_bg = _mix_color(bg or "#1e1e1e", fg or "#e0e0e0", 0.15)
    if not sel_fg:
        sel_fg = fg or "#e0e0e0"

    caret = bright.get("white") or normal.get("white") or fg or "#e0e0e0"

    return {
        "bg": _norm_hex(bg) or "#1e1e1e",
        "fg": _norm_hex(fg) or "#e0e0e0",
        "sel_bg": _norm_hex(sel_bg) or sel_bg,
        "sel_fg": _norm_hex(sel_fg) or sel_fg,
        "caret": _norm_hex(caret) or caret,
    }

def _collect_imports_text(
    main_path: Path, visited: set[Path], depth: int = 0, max_depth: int = 8
) -> str:
    if depth > max_depth:
        return ""
    try:
        main_path = main_path.resolve()
    except Exception:
        pass
    if main_path in visited or not main_path.exists():
        return ""
    visited.add(main_path)

    base_dir = main_path.parent
    txt = _read(main_path)
    if not txt:
        return ""

    combined: list[str] = []

    for m in IMPORT_LINE_RE.finditer(txt):
        val = m.group("val").strip()
        paths: list[str] = []
        for qm in QUOTED_PATH_RE.finditer(val):
            p = qm.group(1) or qm.group(2)
            if p:
                paths.append(p)
        if not paths and (val == "" or val.endswith(":") or val in ("|", ">")):
            after = txt[m.end():]
            for line in after.splitlines():
                if line.strip().startswith(
                    ("#", "colors:", "primary:", "cursor:", "selection:", "schemes:", "themes:")
                ):
                    break
                dm = DASHED_ITEM_RE.match(line)
                if dm:
                    p = dm.group(1) or dm.group(2)
                    if p:
                        paths.append(p)
                elif line.strip() and not line.strip().startswith("-"):
                    break

        for raw in paths:
            for path_str in glob.glob(raw):
                p = Path(path_str).expanduser()
                if not p.is_absolute():
                    p = (base_dir / p).resolve()
                combined.append(_collect_imports_text(p, visited, depth + 1, max_depth))

    combined.append(txt)
    return "\n".join(filter(None, combined))

def _palette_from_alacritty_text(txt: str) -> dict[str, str | None]:
    out = _empty_palette()
    def block_key(block: str, key: str) -> str | None:
        pat = rf"(?mis)^\s*(?:colors\.\s*)?{block}\s*[:=].*?^\s*{key}\s*[:=]\s*(?P<x>{HEX_RE})"
        m = re.search(pat, txt)
        return _norm_hex(m.group("x")) if m else None
    out["bg"]     = block_key("primary",   "background")
    out["fg"]     = block_key("primary",   "foreground")
    out["sel_bg"] = block_key("selection", "background")
    out["sel_fg"] = block_key("selection", "text") or block_key("selection", "foreground")
    out["caret"]  = block_key("cursor",    "cursor") or block_key("cursor", "text")
    return out

# -------------------- kitty / foot parsers --------------------
def _palette_from_kitty_text(txt: str) -> dict[str, str | None]:
    out = _empty_palette()
    def grab(k: str) -> str | None:
        m = re.search(rf"(?mi)^\s*{k}\s+({HEX_RE})", txt)
        return _norm_hex(m.group(1)) if m else None
    out["bg"]    = grab("background")
    out["fg"]    = grab("foreground")
    out["caret"] = grab("cursor")
    out["sel_bg"]= grab("selection_background")
    out["sel_fg"]= grab("selection_foreground")
    return out

def _palette_from_foot_text(txt: str) -> dict[str, str | None]:
    out = _empty_palette()
    def grab(k: str) -> str | None:
        m = re.search(rf"(?mi)^\s*{k}\s*=\s*({HEX_RE})", txt)
        return _norm_hex(m.group(1)) if m else None
    out["bg"]    = grab("background")
    out["fg"]    = grab("foreground")
    out["caret"] = grab("cursor")
    out["sel_bg"]= grab("selection-background")
    out["sel_fg"]= grab("selection-foreground")
    return out

# -------------------- palette sources --------------------
def _palette_from_theme_dir(theme_dir: Path) -> dict[str, str | None]:
    for fname in ("alacritty.toml", "alacritty.yaml", "alacritty.yml"):
        f = theme_dir / fname
        if f.exists():
            pal = _parse_alacritty(f)
            if pal:
                return pal
            return _palette_from_alacritty_text(_read(f))
    f = theme_dir / "kitty.conf"
    if f.exists():
        return _palette_from_kitty_text(_read(f))
    f = theme_dir / "foot.ini"
    if f.exists():
        return _palette_from_foot_text(_read(f))
    return _empty_palette()

def _from_env() -> dict[str, str | None]:
    out = {
        "bg":     _getenv("MICROPAD_BG"),
        "fg":     _getenv("MICROPAD_FG"),
        "sel_bg": _getenv("MICROPAD_SEL_BG"),
        "sel_fg": _getenv("MICROPAD_SEL_FG"),
        "caret":  _getenv("MICROPAD_CARET"),
    }
    if any(out.values()):
        _dbg("Using OMNOTE_* (or legacy MICROPAD_*) env overrides.")
    return out

def _from_omarchy_theme() -> dict[str, str | None]:
    td = _omarchy_current_dir()
    if not td:
        _dbg("Omarchy current theme not detected.")
        return _empty_palette()
    pal = _palette_from_theme_dir(td)
    if any(pal.values()):
        _dbg(f"Omarchy palette applied from {td}")
        return pal
    _dbg("Omarchy theme had no terminal palette files.")
    return _empty_palette()

def _from_alacritty_config() -> dict[str, str | None]:
    cands: list[Path] = []
    envp = os.getenv("ALACRITTY_CONFIG")
    if envp:
        cands.append(Path(envp).expanduser())

    cands += [
        OMARCHY_CURTHEME / "alacritty.toml",
        OMARCHY_CURTHEME / "alacritty.yml",
        OMARCHY_CURTHEME / "alacritty.yaml",
    ]
    cands += [
        Path("~/.config/alacritty/alacritty.toml").expanduser(),
        Path("~/.config/alacritty/alacritty.yml").expanduser(),
        Path("~/.config/alacritty/alacritty.yaml").expanduser(),
        Path("~/.alacritty.yml").expanduser(),
    ]

    for p in cands:
        if p.exists():
            if p.suffix.lower() in {".toml", ".yaml", ".yml"}:
                pal = _parse_alacritty(p)
                if pal and any(pal.values()):
                    _dbg(f"Alacritty palette from {p}")
                    return pal
            agg = _collect_imports_text(p, visited=set())
            if agg:
                pal = _palette_from_alacritty_text(agg)
                if any(pal.values()):
                    _dbg(f"Alacritty palette (imports) via {p}")
                    return pal

    _dbg("Alacritty palette not found.")
    return _empty_palette()

def _from_gtk_defaults() -> dict[str, str | None]:
    return _empty_palette()

def _merge_pref(*dicts: dict[str, str | None]) -> dict[str, str | None]:
    out = _empty_palette()
    for d in dicts:
        for k, v in d.items():
            if out[k] is None and v:
                out[k] = v
    return out

# -------------------- CSS application (GTK4-safe) --------------------
def _apply_css(css: str | None = None, path: Path | None = None) -> None:
    global _CURRENT_PROVIDER

    disp = Gdk.Display.get_default()
    if not disp:
        return

    if _CURRENT_PROVIDER is not None:
        try:
            Gtk.StyleContext.remove_provider_for_display(disp, _CURRENT_PROVIDER)
        except Exception:
            pass
        _CURRENT_PROVIDER = None

    if css is None and path is None:
        return

    provider = Gtk.CssProvider()
    if css is not None:
        provider.load_from_data(css.encode("utf-8"))
    elif path is not None:
        provider.load_from_path(str(path))

    Gtk.StyleContext.add_provider_for_display(
        disp, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _CURRENT_PROVIDER = provider

# -------------------- Public API --------------------
def apply_best_theme() -> None:
    """
    Priority:
      0) OMNOTE_THEME_MODE=system → inherit system theme
      1) Omarchy active theme (palette)
      2) Alacritty main (palette)
      3) OMNOTE_* env (palette)
      4) GTK defaults (no-op)
      5) Fallback: ~/.config/gtk-4.0/gtk.css
      6) Else: clear provider (inherit system)
    """
    if _getenv("MICROPAD_THEME_MODE", "").lower() == "system":
        _dbg("Theme mode=system → clearing provider (inherit system).")
        _apply_css(None, None)
        return

    merged = _merge_pref(
        _from_omarchy_theme(),
        _from_alacritty_config(),
        _from_env(),
        _from_gtk_defaults(),
    )

    sm = Adw.StyleManager.get_default()
    is_dark = bool(getattr(sm, "get_dark", lambda: False)())

    css_text: str | None = (
        _css_from_palette(merged, dark=is_dark) if isinstance(merged, dict) else None
    )
    if css_text:
        _dbg("Using palette → CSS.")
        _apply_css(css=css_text)
        return

    user_gtk_css = Path.home() / ".config" / "gtk-4.0" / "gtk.css"
    if user_gtk_css.exists():
        _dbg("Using user gtk-4.0/gtk.css as fallback.")
        _apply_css(path=user_gtk_css)
        return

    _dbg("Clearing custom CSS (no explicit palette or gtk.css).")
    _apply_css(None, None)

# -------------------- watcher --------------------
class ThemeWatcher:
    """
    FileMonitor-based watcher with clean lifecycle:
    - disconnects Adw.StyleManager signal
    - cancels Gio.FileMonitor instances
    - removes GLib timeout sources
    """
    def __init__(self) -> None:
        self._monitors: list[Gio.FileMonitor] = []
        self._timeouts: set[int] = set()
        self._sm = Adw.StyleManager.get_default()
        self._sm_handler: int | None = self._sm.connect(
            "notify::color-scheme", self._on_style_change
        )

        for p in self._watch_paths():
            self._add_monitor(p)

        _dbg("ThemeWatcher started.")

    def stop(self) -> None:
        # disconnect style manager signal
        if self._sm and self._sm_handler:
            try:
                self._sm.disconnect(self._sm_handler)
            except Exception:
                pass
            self._sm_handler = None

        # cancel monitors
        for m in self._monitors:
            try:
                m.cancel()
            except Exception:
                pass
        self._monitors.clear()

        # remove pending timeouts
        for sid in list(self._timeouts):
            try:
                GLib.source_remove(sid)
            except Exception:
                pass
        self._timeouts.clear()

        _dbg("ThemeWatcher stopped.")

    # ---- internals ----
    def _watch_paths(self) -> list[Path]:
        cands = [
            OMARCHY_DIR,
            OMARCHY_THEMES,
            # Watch parent dir to detect symlink changes
            Path("~/.config/omarchy/current").expanduser(),
            Path("~/.config/omarchy/current/theme/alacritty.toml").expanduser(),
            Path("~/.config/omarchy/current/theme/kitty.conf").expanduser(),
            Path("~/.config/omarchy/current/theme/foot.ini").expanduser(),
            HYPR_USER_CONF,
            (
                Path(os.getenv("ALACRITTY_CONFIG", "")).expanduser()
                if os.getenv("ALACRITTY_CONFIG")
                else None
            ),
            Path("~/.config/alacritty").expanduser(),
            Path("~/.config/alacritty/alacritty.yml").expanduser(),
            Path("~/.config/alacritty/alacritty.yaml").expanduser(),
            Path("~/.config/alacritty/alacritty.toml").expanduser(),
            Path("~/.alacritty.yml").expanduser(),
            Path("~/.config/gtk-4.0/gtk.css").expanduser(),
        ]
        return [p for p in cands if p and Path(p).exists()]

    def _add_monitor(self, path: Path) -> None:
        try:
            f = Gio.File.new_for_path(str(path))
            mon = f.monitor_directory(Gio.FileMonitorFlags.NONE, None) if path.is_dir() \
                else f.monitor_file(Gio.FileMonitorFlags.NONE, None)
            mon.connect("changed", self._on_changed)
            self._monitors.append(mon)
            _dbg(f"Watching {path}")
        except Exception as e:
            _dbg(f"Monitor failed for {path}: {e}")

    def _on_style_change(self, *_args) -> None:
        _dbg("Adw color-scheme changed.")
        apply_best_theme()

    def _on_changed(self, *_args) -> None:
        # debounce rapid bursts and track the timeout id for clean removal
        def _apply():
            try:
                apply_best_theme()
            except Exception:
                pass
            # Remove timeout ID from tracking set before returning
            self._timeouts.discard(sid)
            return False  # one-shot timeout

        sid = GLib.timeout_add(150, _apply)
        self._timeouts.add(sid)

# -------------------- singleton helpers --------------------
def start_theme_watcher() -> ThemeWatcher:
    global _WATCHER_SINGLETON
    if _WATCHER_SINGLETON is None:
        _WATCHER_SINGLETON = ThemeWatcher()
    return _WATCHER_SINGLETON

def stop_theme_watcher() -> None:
    global _WATCHER_SINGLETON
    if _WATCHER_SINGLETON is not None:
        try:
            _WATCHER_SINGLETON.stop()
        finally:
            _WATCHER_SINGLETON = None
