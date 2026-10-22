"""Light and dark themes: Fusion style plus a hand-tuned palette for each.

Both palettes are explicit, so the app looks the same whatever the desktop's own color
scheme is (plain Qt on a dark desktop gives half-dark, hard-to-read widgets)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QToolTip

THEMES = ("light", "dark")
DEFAULT_THEME = "dark"

_DARK = {
    "Window": "#2b2d31", "WindowText": "#e3e4e6", "Base": "#1f2023", "AlternateBase": "#26282c",
    "ToolTipBase": "#3a3c42", "ToolTipText": "#e3e4e6", "PlaceholderText": "#9a9da3",
    "Text": "#e3e4e6", "Button": "#36383d", "ButtonText": "#e3e4e6", "BrightText": "#ff7b72",
    "Light": "#4a4d53", "Midlight": "#3f4247", "Mid": "#7d8087", "Dark": "#18191b", "Shadow": "#000000",
    "Highlight": "#3d7bd9", "HighlightedText": "#ffffff", "Link": "#6aa8ff", "LinkVisited": "#b48cff",
}
_DARK_DISABLED = {"WindowText": "#6c6f75", "Text": "#6c6f75", "ButtonText": "#6c6f75",
                  "Base": "#26282c", "Button": "#2f3135", "Highlight": "#4a4d53",
                  "HighlightedText": "#9a9da3", "PlaceholderText": "#5c5f65"}

_LIGHT = {
    "Window": "#f2f2f3", "WindowText": "#1d1d1f", "Base": "#ffffff", "AlternateBase": "#f5f6f8",
    "ToolTipBase": "#ffffff", "ToolTipText": "#1d1d1f", "PlaceholderText": "#73767c",
    "Text": "#1d1d1f", "Button": "#ececee", "ButtonText": "#1d1d1f", "BrightText": "#c9302c",
    "Light": "#ffffff", "Midlight": "#e2e2e4", "Mid": "#8e9096", "Dark": "#a4a6ab", "Shadow": "#6e6e70",
    "Highlight": "#3d7bd9", "HighlightedText": "#ffffff", "Link": "#1d63d6", "LinkVisited": "#7a3fc9",
}
_LIGHT_DISABLED = {"WindowText": "#a2a4a8", "Text": "#a2a4a8", "ButtonText": "#a2a4a8",
                   "Base": "#f5f5f6", "Button": "#ececee", "Highlight": "#c7cad0",
                   "HighlightedText": "#ffffff", "PlaceholderText": "#b4b6ba"}

# Small touches the palette alone can't do.
_STYLESHEET = """
QToolTip { border: 1px solid palette(mid); padding: 4px; }
QTabBar::tab:selected { font-weight: 600; }
"""


def make_palette(theme: str) -> QPalette:
    colors, disabled = (_DARK, _DARK_DISABLED) if theme == "dark" else (_LIGHT, _LIGHT_DISABLED)
    pal = QPalette()
    for role, hexcolor in colors.items():
        pal.setColor(QPalette.All, getattr(QPalette, role), QColor(hexcolor))
    for role, hexcolor in disabled.items():
        pal.setColor(QPalette.Disabled, getattr(QPalette, role), QColor(hexcolor))
    return pal


def apply_theme(app: QApplication, theme: str):
    theme = theme if theme in THEMES else DEFAULT_THEME
    app.setStyle("Fusion")
    pal = make_palette(theme)
    app.setPalette(pal)
    QToolTip.setPalette(pal)
    app.setStyleSheet(_STYLESHEET)  # re-setting also re-polishes palette(...) references
    app.setProperty("pw_theme", theme)


def current_theme() -> str:
    app = QApplication.instance()
    t = app.property("pw_theme") if app else None
    return t if t in THEMES else DEFAULT_THEME


def is_dark() -> bool:
    return current_theme() == "dark"


def muted(pal: QPalette) -> QColor:
    """Secondary text color (labels, hints) that stays readable in both themes."""
    return pal.placeholderText().color()


def accent(name: str) -> str:
    """Theme-aware colors for the few things that aren't palette roles."""
    dark = is_dark()
    return {
        "link": "#6aa8ff" if dark else "#1d63d6",
        "missing": "#ff7b72" if dark else "#c9302c",
        "error": "#ff7b72" if dark else "#c0392b",
        "banner_bg": "#4a2422" if dark else "#fdecea",
        "banner_fg": "#ffd7d2" if dark else "#8a1f11",
    }[name]
