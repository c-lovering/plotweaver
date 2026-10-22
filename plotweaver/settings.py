"""Where Plotweaver keeps its own settings (theme, recent projects, view options).

Portable mode: if a file named ``portable.txt`` sits next to the program, settings go in
``data/settings.ini`` beside it, so the whole folder can live on a USB stick or in Dropbox.
Otherwise they go in the normal per-user place (the registry on Windows, ~/.config on Linux).
Your novels are never stored here; they're wherever you put them."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings

ORG = APP = "Plotweaver"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def is_portable() -> bool:
    return (app_dir() / "portable.txt").exists()


def data_dir() -> Path:
    return app_dir() / "data"


def app_settings() -> QSettings:
    if is_portable():
        d = data_dir()
        try:
            d.mkdir(exist_ok=True)
            return QSettings(str(d / "settings.ini"), QSettings.IniFormat)
        except OSError:
            pass  # read-only location: fall back to per-user settings
    return QSettings(ORG, APP)
