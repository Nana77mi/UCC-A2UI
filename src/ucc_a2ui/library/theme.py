from __future__ import annotations

from typing import Dict

DEFAULT_THEME = {
    "primary": "#1976d2",
    "secondary": "#9c27b0",
    "background": "#ffffff",
    "surface": "#f5f5f5",
    "error": "#d32f2f",
    "onPrimary": "#ffffff",
    "onSecondary": "#ffffff",
    "onBackground": "#1c1c1c",
    "onSurface": "#1c1c1c",
}


def merge_theme_tokens(tokens: Dict[str, str]) -> Dict[str, str]:
    theme = DEFAULT_THEME.copy()
    for key, value in tokens.items():
        if key and value:
            theme[key] = value
    return theme
