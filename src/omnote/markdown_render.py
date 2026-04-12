from __future__ import annotations

import re

from gi import require_version

require_version("Gtk", "4.0")

from gi.repository import Gtk, Pango

_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_BULLET_RE = re.compile(r"^(\s*)[*\-]\s+(.+)$")
_CHECKBOX_RE = re.compile(r"^\[( |x)\]\s*(.+)$", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"^```")
_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`")


def _insert_with_tags(buf: Gtk.TextBuffer, text: str, *tag_names: str) -> None:
    """Insert text at end of buffer with the given tags applied."""
    start_mark = buf.create_mark(None, buf.get_end_iter(), True)
    buf.insert(buf.get_end_iter(), text)
    start_iter = buf.get_iter_at_mark(start_mark)
    end_iter = buf.get_end_iter()
    for name in tag_names:
        tag = buf.get_tag_table().lookup(name)
        if tag:
            buf.apply_tag(tag, start_iter, end_iter)
    buf.delete_mark(start_mark)


def _insert_inline(buf: Gtk.TextBuffer, text: str, base_tags: list[str]) -> None:
    """Insert text with inline **bold** and `code` formatting."""
    parts: list[tuple[str, list[str]]] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            parts.append((text[pos : m.start()], []))
        if m.group(1) is not None:
            parts.append((m.group(1), ["bold"]))
        else:
            parts.append((m.group(2), ["code"]))
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], []))
    if not parts:
        parts = [(text, [])]

    for content, extra_tags in parts:
        _insert_with_tags(buf, content, *(base_tags + extra_tags))


def _ensure_tags(buf: Gtk.TextBuffer) -> None:
    """Create all markdown rendering tags if they don't already exist."""
    table = buf.get_tag_table()
    defs: dict[str, dict] = {
        "h1": {
            "weight": Pango.Weight.BOLD,
            "scale": 1.8,
            "pixels_above_lines": 14,
            "pixels_below_lines": 6,
        },
        "h2": {
            "weight": Pango.Weight.BOLD,
            "scale": 1.4,
            "pixels_above_lines": 10,
            "pixels_below_lines": 4,
        },
        "h3": {
            "weight": Pango.Weight.BOLD,
            "scale": 1.15,
            "pixels_above_lines": 6,
            "pixels_below_lines": 3,
        },
        "bold": {"weight": Pango.Weight.BOLD},
        "code": {"family": "monospace"},
        "code_block": {
            "family": "monospace",
            "left_margin": 32,
            "pixels_above_lines": 1,
            "pixels_below_lines": 1,
        },
        "bullet": {
            "left_margin": 24,
            "pixels_above_lines": 2,
            "pixels_below_lines": 2,
        },
        "bullet2": {
            "left_margin": 48,
            "pixels_above_lines": 2,
            "pixels_below_lines": 2,
        },
    }
    for name, props in defs.items():
        if table.lookup(name) is None:
            buf.create_tag(name, **props)


def render_markdown(text: str, textview: Gtk.TextView) -> None:
    """Parse markdown text and render it into a Gtk.TextView with styled tags."""
    buf = textview.get_buffer()
    buf.set_text("")
    _ensure_tags(buf)

    lines = text.split("\n")
    in_code_block = False
    first = True

    for line in lines:
        if not first:
            buf.insert(buf.get_end_iter(), "\n")
        first = False

        # Code fence toggle
        if _CODE_FENCE_RE.match(line):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            _insert_with_tags(buf, line, "code_block")
            continue

        # Header
        hm = _HEADER_RE.match(line)
        if hm:
            level = len(hm.group(1))
            tag_name = f"h{min(level, 3)}"
            _insert_inline(buf, hm.group(2), [tag_name])
            continue

        # Bullet / checkbox
        bm = _BULLET_RE.match(line)
        if bm:
            indent = len(bm.group(1))
            content = bm.group(2)
            tag = "bullet2" if indent >= 2 else "bullet"

            cm = _CHECKBOX_RE.match(content)
            if cm:
                checked = cm.group(1).lower() == "x"
                prefix = "\u2611 " if checked else "\u2610 "
                _insert_inline(buf, prefix + cm.group(2), [tag])
            else:
                _insert_inline(buf, "\u2022 " + content, [tag])
            continue

        # Regular text
        _insert_inline(buf, line, [])
