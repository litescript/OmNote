# src/omnote/__main__.py
from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omnote")
    parser.add_argument("files", nargs="*", metavar="FILE", help="File(s) to open, one tab each")
    parser.add_argument(
        "--system-theme", action="store_true", help="Use system theme (ignore custom CSS)"
    )
    parser.add_argument("--no-watch", action="store_true", help="Disable file/theme watching")
    args = parser.parse_args(argv)

    if args.system_theme:
        os.environ["OMNOTE_THEME_MODE"] = "system"
        os.environ["MICROPAD_THEME_MODE"] = "system"  # legacy compat
    if args.no_watch:
        os.environ["OMNOTE_NO_WATCH"] = "1"
        os.environ["MICROPAD_NO_WATCH"] = "1"  # legacy compat

    # argparse owns the command line; GApplication only gets the files. It rejects
    # options it doesn't know (--system-theme), and keeps a literal "--" in its file
    # list, so a name starting with "-" is made relative instead.
    files = [f"./{f}" if f.startswith("-") else f for f in args.files]

    # Deferred so `omnote --help` and the tests don't need GTK
    from .app import main as app_main

    return app_main([sys.argv[0], *files])

if __name__ == "__main__":
    sys.exit(main())
