.PHONY: run install-user uninstall-user lint type test

run:
	PYTHONPATH=src python -m omnote

lint:
	@command -v ruff >/dev/null 2>&1 && ruff check src/ || echo "ruff not installed (optional dev tool)"

type:
	@command -v mypy >/dev/null 2>&1 && mypy src/ || echo "mypy not installed (optional dev tool)"

test:
	@command -v pytest >/dev/null 2>&1 && pytest || echo "pytest not installed (optional dev tool)"

install-user:
	install -Dm644 dist/dev.omarchy.OmNote.desktop ~/.local/share/applications/dev.omarchy.OmNote.desktop
	install -Dm644 assets/dev.omarchy.OmNote.svg ~/.local/share/icons/hicolor/scalable/apps/dev.omarchy.OmNote.svg
	update-desktop-database ~/.local/share/applications || true

uninstall-user:
	rm -f ~/.local/share/applications/dev.omarchy.OmNote.desktop
	rm -f ~/.local/share/icons/hicolor/scalable/apps/dev.omarchy.OmNote.svg
	update-desktop-database ~/.local/share/applications || true
