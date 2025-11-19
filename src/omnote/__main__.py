# src/omnote/__main__.py
from __future__ import annotations

import argparse
import os
import sys

from .app import main as app_main


def main() -> int:
    parser = argparse.ArgumentParser(prog="omnote")
    parser.add_argument(
        "--system-theme", action="store_true", help="Use system theme (ignore custom CSS)"
    )
    parser.add_argument("--no-watch", action="store_true", help="Disable file/theme watching")
    args = parser.parse_args()

    if args.system_theme:
        os.environ["OMNOTE_THEME_MODE"] = "system"
        os.environ["MICROPAD_THEME_MODE"] = "system"  # legacy compat
    if args.no_watch:
        os.environ["OMNOTE_NO_WATCH"] = "1"
        os.environ["MICROPAD_NO_WATCH"] = "1"  # legacy compat

    return app_main()

if __name__ == "__main__":
    sys.exit(main())
