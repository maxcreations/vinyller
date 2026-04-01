"""
Vinyller — Theme tools
Copyright (C) 2026 Maxim Moshkin
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import math
import re

from PyQt6.QtCore import QFile, QTextStream
from PyQt6.QtGui import QColor

from src.utils.constants_linux import IS_LINUX
from src.utils.utils import resource_path

# This file contains color palettes and variables for various application themes.
# NOTE: rgba colors won't work if drawn via QPainter directly - use get_qcolor() to get a valid QColor.

ACCENT_PALETTE = {
    "Crimson": "#DC143C",
    "Brick Red": "#B13434",
    "Orange": "#FF6400",
    "Yellow": "#E69E16",
    "Tan": "#CC9C72",
    "Gold": "#A67D3A",
    "Green": "#6AB134",
    "Teal": "#25A97F",
    "Blue": "#3466B1",
    "Night Blue": "#2B4471",
    "Indigo": "#69348C",
    "Slate Gray": "#4C5B62",
    "Graphite": "#424242",
}


THEMES = {
    "Light": {
        "IS_DARK": False,
        "ACCENT": "#dc143c",
        "ACCENT_SECONDARY": "#A30F2D",
        "ACCENT_HOVER": "#B21031",
        "ACCENT_SELECTED": "rgba(220, 20, 60, 0.2)",
        "ACCENT_SELECTED_HOVER": "rgba(220, 20, 60, 0.3)",
        "PRIMARY": "#000000",
        "SECONDARY": "#FFFFFF",
        "TERTIARY": "#808080",
        "INPUT_BG": "{SECONDARY}",
        "INPUT_BG_HOVER": "#E0E0E0",
        "INPUT_BG_DISABLED": "#f5f5f5",
        "INPUT_BRD": "#dddddd",
        "INPUT_BRD_DISABLED": "#e5e5e5",
        "INPUT_BRD_HOVER": "#AAAAAA",
        "CARD_BG": "{SECONDARY}",
        "CARD_BG_HOVER": "#EEEEEE",
        "WIDGET_BRD_PRIMARY": "#dddddd",
        "WIDGET_BRD_SECONDARY": "#f0f0f0",
        "WIDGET_BG_PRIMARY": "#dddddd",
        "WIDGET_BG_SECONDARY": "#eeeeee",
        "LIST_ITEM_SELECTED": "#F5F5F5",
        "LIST_ITEM_HOVER": "#EEEEEE",
        "LIST_ITEM_BRD": "#dddddd",
        "TOOLTIP_BG": "#ffffe1",
        "TOOLTIP_BRD": "#eeeee1",
        "CONTROL_PANEL_BG": "{SECONDARY}",
        "CONTROL_PANEL_BRD": "{WIDGET_BRD_PRIMARY}",
        "NAV_PANEL_BG": "{SECONDARY}",
        "NAV_PANEL_BRD": "{SECONDARY}",
        "HEADER_BG": "{SECONDARY}",
        "HEADER_BRD": "{WIDGET_BRD_PRIMARY}",
        "VINYLLER_BUTTON": "{SECONDARY}",
        "VINYLLER_BUTTON_HOVER": "rgba(0, 0, 0, 0.10)",
        "VINYLLER_BUTTON_BRD": "{WIDGET_BRD_PRIMARY}",
        "WHITE": "#ffffff",
        "LIGHT_GRAY": "#eeeeee",
        "GREY": "#808080",
        "TRACK_HOVER_BG": "#EEEEEE",
        "OVERLAY_THEME_BG": "rgba(255, 255, 255, 0.85)",
        "OVERLAY_DARK_BG": "rgba(0, 0, 0, 0.85)",
        "HOVER_OVERLAY": "rgba(0, 0, 0, 0.33)",
        "DZ_CONTAINER_BG": "rgba(0, 0, 0, 0.8)",
        "DZ_CONTAINER_FRAME": "rgba(255, 255, 255, 0.2)",
        "DZ_CONTAINER_ACCENT": "rgba(163, 15, 45, 0.6)",
        "SCROLLBAR_BG": "rgba(0, 0, 0, 0.00)",
        "SCROLLBAR_HANDLE": "rgba(0, 0, 0, 0.1)",
        "SCROLLBAR_HANDLE_HOVER": "rgba(0, 0, 0, 0.2)",
        "MISSING_COVER": "assets/view/missing_cover.png",
    },
    "Retro Light": {
        "IS_DARK": False,
        "ACCENT": "#dc143c",
        "ACCENT_SECONDARY": "#A30F2D",
        "ACCENT_HOVER": "#B21031",
        "ACCENT_SELECTED": "rgba(220, 20, 60, 0.2)",
        "ACCENT_SELECTED_HOVER": "rgba(220, 20, 60, 0.3)",

        "PRIMARY": "#3a3631",
        "SECONDARY": "#fffbf2",
        "TERTIARY": "#8f8a83",

        "INPUT_BG": "{SECONDARY}",
        "INPUT_BG_HOVER": "#f4efe5",
        "INPUT_BG_DISABLED": "#e8e2d7",
        "INPUT_BRD": "#d6cfc2",
        "INPUT_BRD_DISABLED": "#e0d9cc",
        "INPUT_BRD_HOVER": "#b8b2a5",

        "CARD_BG": "{SECONDARY}",
        "CARD_BG_HOVER": "#f4efe5",

        "WIDGET_BRD_PRIMARY": "#d6cfc2",
        "WIDGET_BRD_SECONDARY": "#e0d9cc",
        "WIDGET_BG_PRIMARY": "#D6CFC2",
        "WIDGET_BG_SECONDARY": "#e8e2d7",

        "LIST_ITEM_SELECTED": "#e8e2d7",
        "LIST_ITEM_HOVER": "#f4efe5",
        "LIST_ITEM_BRD": "#d6cfc2",

        "TOOLTIP_BG": "#fefbf4",
        "TOOLTIP_BRD": "#d6cfc2",

        "CONTROL_PANEL_BG": "#f4efe5",
        "CONTROL_PANEL_BRD": "#d6cfc2",

        "NAV_PANEL_BG": "{SECONDARY}",
        "NAV_PANEL_BRD": "{SECONDARY}",
        "HEADER_BG": "{SECONDARY}",
        "HEADER_BRD": "{WIDGET_BRD_PRIMARY}",

        "VINYLLER_BUTTON": "{SECONDARY}",
        "VINYLLER_BUTTON_HOVER": "rgba(58, 54, 49, 0.06)",
        "VINYLLER_BUTTON_BRD": "{WIDGET_BRD_PRIMARY}",

        "WHITE": "#ffffff",
        "LIGHT_GRAY": "#eeeeee",
        "GREY": "#808080",
        "TRACK_HOVER_BG": "#f4efe5",

        "OVERLAY_THEME_BG": "rgba(255, 251, 242, 0.85)",
        "OVERLAY_DARK_BG": "rgba(58, 54, 49, 0.85)",
        "HOVER_OVERLAY": "rgba(58, 54, 49, 0.15)",

        "DZ_CONTAINER_BG": "rgba(244, 239, 229, 0.8)",
        "DZ_CONTAINER_FRAME": "rgba(58, 54, 49, 0.2)",
        "DZ_CONTAINER_ACCENT": "rgba(220, 20, 60, 0.6)",

        "SCROLLBAR_BG": "rgba(0, 0, 0, 0.00)",
        "SCROLLBAR_HANDLE": "rgba(58, 54, 49, 0.12)",
        "SCROLLBAR_HANDLE_HOVER": "rgba(58, 54, 49, 0.22)",

        "MISSING_COVER": "assets/view/missing_cover.png",
    },
    "Retro Dark": {
        "IS_DARK": True,
        "ACCENT": "#dc143c",
        "ACCENT_SECONDARY": "#A30F2D",
        "ACCENT_HOVER": "#B21031",
        "ACCENT_SELECTED": "rgba(220, 20, 60, 0.2)",
        "ACCENT_SELECTED_HOVER": "rgba(220, 20, 60, 0.8)",

        "PRIMARY": "#dedcd9",
        "SECONDARY": "#4a4743",
        "TERTIARY": "#9c968e",

        "INPUT_BG": "{SECONDARY}",
        "INPUT_BG_HOVER": "#45423e",
        "INPUT_BG_DISABLED": "#54514c",
        "INPUT_BRD": "#363430",
        "INPUT_BRD_DISABLED": "#4a4743",
        "INPUT_BRD_HOVER": "#2B2A27",

        "CARD_BG": "{SECONDARY}",
        "CARD_BG_HOVER": "#403d39",

        "WIDGET_BRD_PRIMARY": "#3b3834",
        "WIDGET_BRD_SECONDARY": "#363430",
        "WIDGET_BG_PRIMARY": "#363430",
        "WIDGET_BG_SECONDARY": "#403d39",

        "LIST_ITEM_SELECTED": "#54514c",
        "LIST_ITEM_HOVER": "#403d39",
        "LIST_ITEM_BRD": "#363430",

        "TOOLTIP_BG": "#2e2c29",
        "TOOLTIP_BRD": "#242220",

        "CONTROL_PANEL_BG": "#363430",
        "CONTROL_PANEL_BRD": "#363430",

        "NAV_PANEL_BG": "{SECONDARY}",
        "NAV_PANEL_BRD": "{SECONDARY}",
        "HEADER_BG": "{SECONDARY}",
        "HEADER_BRD": "{WIDGET_BRD_PRIMARY}",

        "VINYLLER_BUTTON": "{SECONDARY}",
        "VINYLLER_BUTTON_HOVER": "rgba(222, 220, 217, 0.06)",
        "VINYLLER_BUTTON_BRD": "{WIDGET_BRD_PRIMARY}",

        "WHITE": "#ffffff",
        "LIGHT_GRAY": "#dcdad5",
        "GREY": "#8c8882",
        "TRACK_HOVER_BG": "#54514c",

        "OVERLAY_THEME_BG": "rgba(54, 52, 48, 0.85)",
        "OVERLAY_DARK_BG": "rgba(36, 34, 32, 0.85)",
        "HOVER_OVERLAY": "rgba(0, 0, 0, 0.40)",

        "DZ_CONTAINER_BG": "rgba(46, 44, 41, 0.8)",
        "DZ_CONTAINER_FRAME": "rgba(222, 220, 217, 0.2)",
        "DZ_CONTAINER_ACCENT": "rgba(220, 20, 60, 0.6)",

        "SCROLLBAR_BG": "rgba(255, 255, 255, 0.00)",
        "SCROLLBAR_HANDLE": "rgba(222, 220, 217, 0.12)",
        "SCROLLBAR_HANDLE_HOVER": "rgba(222, 220, 217, 0.22)",

        "MISSING_COVER": "assets/view/missing_cover_theme_dk.png",
    },
    "Graphite": {
        "IS_DARK": True,
        "ACCENT": "#dc143c",
        "ACCENT_SECONDARY": "#A30F2D",
        "ACCENT_HOVER": "#B21031",
        "ACCENT_SELECTED": "rgba(220, 20, 60, 0.2)",
        "ACCENT_SELECTED_HOVER": "rgba(220, 20, 60, 0.8)",
        "PRIMARY": "#cccccc",
        "SECONDARY": "#303030",
        "TERTIARY": "#808080",
        "INPUT_BG": "{SECONDARY}",
        "INPUT_BG_HOVER": "#444444",
        "INPUT_BG_DISABLED": "#808080",
        "INPUT_BRD": "#444444",
        "INPUT_BRD_DISABLED": "#666666",
        "INPUT_BRD_HOVER": "#4f4f4f",
        "CARD_BG": "{SECONDARY}",
        "CARD_BG_HOVER": "#444444",
        "WIDGET_BRD_PRIMARY": "#444444",
        "WIDGET_BRD_SECONDARY": "#3f3f3f",
        "WIDGET_BG_PRIMARY": "#444444",
        "WIDGET_BG_SECONDARY": "#3f3f3f",
        "LIST_ITEM_SELECTED": "#404040",
        "LIST_ITEM_HOVER": "#3f3f3f",
        "LIST_ITEM_BRD": "#3d3d3d",
        "TOOLTIP_BG": "#242424",
        "TOOLTIP_BRD": "#202020",
        "CONTROL_PANEL_BG": "{SECONDARY}",
        "CONTROL_PANEL_BRD": "{WIDGET_BRD_PRIMARY}",
        "NAV_PANEL_BG": "{SECONDARY}",
        "NAV_PANEL_BRD": "{SECONDARY}",
        "HEADER_BG": "{SECONDARY}",
        "HEADER_BRD": "{WIDGET_BRD_PRIMARY}",
        "VINYLLER_BUTTON": "{SECONDARY}",
        "VINYLLER_BUTTON_HOVER": "rgba(0, 0, 0, 0.10)",
        "VINYLLER_BUTTON_BRD": "{WIDGET_BRD_PRIMARY}",
        "WHITE": "#ffffff",
        "LIGHT_GRAY": "#eeeeee",
        "GREY": "#808080",
        "TRACK_HOVER_BG": "#3f3f3f",
        "OVERLAY_THEME_BG": "rgba(0, 0, 0, 0.85)",
        "OVERLAY_DARK_BG": "rgba(0, 0, 0, 0.85)",
        "HOVER_OVERLAY": "rgba(0, 0, 0, 0.33)",
        "DZ_CONTAINER_BG": "rgba(0, 0, 0, 0.8)",
        "DZ_CONTAINER_FRAME": "rgba(255, 255, 255, 0.2)",
        "DZ_CONTAINER_ACCENT": "rgba(163, 15, 45, 0.6)",
        "SCROLLBAR_BG": "rgba(255, 255, 255, 0.00)",
        "SCROLLBAR_HANDLE": "rgba(255, 255, 255, 0.1)",
        "SCROLLBAR_HANDLE_HOVER": "rgba(255, 255, 255, 0.2)",
        "MISSING_COVER": "assets/view/missing_cover_theme_dk.png",
    },
    "Polar Night": {
        "IS_DARK": True,
        "ACCENT": "#dc143c",
        "ACCENT_SECONDARY": "#A30F2D",
        "ACCENT_HOVER": "#B21031",
        "ACCENT_SELECTED": "rgba(220, 20, 60, 0.2)",
        "ACCENT_SELECTED_HOVER": "rgba(220, 20, 60, 0.8)",
        "PRIMARY": "#D8DEE9",
        "SECONDARY": "#2E3440",
        "TERTIARY": "#81A1C1",
        "INPUT_BG": "{SECONDARY}",
        "INPUT_BG_HOVER": "#3B4252",
        "INPUT_BG_DISABLED": "#434C5E",
        "INPUT_BRD": "#434C5E",
        "INPUT_BRD_DISABLED": "#4C566A",
        "INPUT_BRD_HOVER": "#4C566A",
        "CARD_BG": "{SECONDARY}",
        "CARD_BG_HOVER": "#3B4252",
        "WIDGET_BRD_PRIMARY": "#434C5E",
        "WIDGET_BRD_SECONDARY": "#3B4252",
        "WIDGET_BG_PRIMARY": "#434C5E",
        "WIDGET_BG_SECONDARY": "#3B4252",
        "LIST_ITEM_SELECTED": "#434C5E",
        "LIST_ITEM_HOVER": "#3B4252",
        "LIST_ITEM_BRD": "#434C5E",
        "TOOLTIP_BG": "#242933",
        "TOOLTIP_BRD": "#2E3440",
        "CONTROL_PANEL_BG": "{SECONDARY}",
        "CONTROL_PANEL_BRD": "{WIDGET_BRD_PRIMARY}",
        "NAV_PANEL_BG": "{SECONDARY}",
        "NAV_PANEL_BRD": "{SECONDARY}",
        "HEADER_BG": "{SECONDARY}",
        "HEADER_BRD": "{WIDGET_BRD_PRIMARY}",
        "VINYLLER_BUTTON": "{SECONDARY}",
        "VINYLLER_BUTTON_HOVER": "rgba(216, 222, 233, 0.10)",
        "VINYLLER_BUTTON_BRD": "{WIDGET_BRD_PRIMARY}",
        "WHITE": "#ffffff",
        "LIGHT_GRAY": "#eeeeee",
        "GREY": "#808080",
        "TRACK_HOVER_BG": "#3B4252",
        "OVERLAY_THEME_BG": "rgba(46, 52, 64, 0.85)",
        "OVERLAY_DARK_BG": "rgba(36, 41, 51, 0.85)",
        "HOVER_OVERLAY": "rgba(0, 0, 0, 0.33)",
        "DZ_CONTAINER_BG": "rgba(36, 41, 51, 0.8)",
        "DZ_CONTAINER_FRAME": "rgba(216, 222, 233, 0.2)",
        "DZ_CONTAINER_ACCENT": "rgba(163, 15, 45, 0.6)",
        "SCROLLBAR_BG": "rgba(255, 255, 255, 0.00)",
        "SCROLLBAR_HANDLE": "rgba(216, 222, 233, 0.1)",
        "SCROLLBAR_HANDLE_HOVER": "rgba(216, 222, 233, 0.2)",
        "MISSING_COVER": "assets/view/missing_cover_theme_dk.png",
    },
    "Dark": {
        "IS_DARK": True,
        "ACCENT": "#dc143c",
        "ACCENT_SECONDARY": "#A30F2D",
        "ACCENT_HOVER": "#B21031",
        "ACCENT_SELECTED": "rgba(220, 20, 60, 0.2)",
        "ACCENT_SELECTED_HOVER": "rgba(220, 20, 60, 0.8)",
        "PRIMARY": "#cccccc",
        "SECONDARY": "#242424",
        "TERTIARY": "#808080",

        "INPUT_BG": "{SECONDARY}",
        "INPUT_BG_HOVER": "#363636",
        "INPUT_BG_DISABLED": "#4d4d4d",
        "INPUT_BRD": "#363636",
        "INPUT_BRD_DISABLED": "#404040",
        "INPUT_BRD_HOVER": "#444444",

        "CARD_BG": "{SECONDARY}",
        "CARD_BG_HOVER": "#2f2f2f",

        "WIDGET_BRD_PRIMARY": "#363636",
        "WIDGET_BRD_SECONDARY": "#2f2f2f",
        "WIDGET_BG_PRIMARY": "#363636",
        "WIDGET_BG_SECONDARY": "#2f2f2f",

        "LIST_ITEM_SELECTED": "#363636",
        "LIST_ITEM_HOVER": "#2f2f2f",
        "LIST_ITEM_BRD": "#2c2c2c",

        "TOOLTIP_BG": "#1c1c1c",
        "TOOLTIP_BRD": "#161616",

        "CONTROL_PANEL_BG": "{SECONDARY}",
        "CONTROL_PANEL_BRD": "{WIDGET_BRD_PRIMARY}",
        "NAV_PANEL_BG": "{SECONDARY}",
        "NAV_PANEL_BRD": "{SECONDARY}",
        "HEADER_BG": "{SECONDARY}",
        "HEADER_BRD": "{WIDGET_BRD_PRIMARY}",

        "VINYLLER_BUTTON": "{SECONDARY}",
        "VINYLLER_BUTTON_HOVER": "rgba(255, 255, 255, 0.05)",
        "VINYLLER_BUTTON_BRD": "{WIDGET_BRD_PRIMARY}",

        "WHITE": "#ffffff",
        "LIGHT_GRAY": "#eeeeee",
        "GREY": "#808080",
        "TRACK_HOVER_BG": "#2f2f2f",

        "OVERLAY_THEME_BG": "rgba(0, 0, 0, 0.85)",
        "OVERLAY_DARK_BG": "rgba(0, 0, 0, 0.85)",
        "HOVER_OVERLAY": "rgba(0, 0, 0, 0.40)",

        "DZ_CONTAINER_BG": "rgba(0, 0, 0, 0.8)",
        "DZ_CONTAINER_FRAME": "rgba(255, 255, 255, 0.2)",
        "DZ_CONTAINER_ACCENT": "rgba(163, 15, 45, 0.6)",

        "SCROLLBAR_BG": "rgba(255, 255, 255, 0.00)",
        "SCROLLBAR_HANDLE": "rgba(255, 255, 255, 0.08)",
        "SCROLLBAR_HANDLE_HOVER": "rgba(255, 255, 255, 0.15)",

        "MISSING_COVER": "assets/view/missing_cover_theme_dk.png",
    },
}

# Global variable for storing the active color palette.
# "Light" theme is used by default.
COLORS = THEMES["Light"]


def get_relative_luminance(color: QColor) -> float:
    """
    Returns perceived luminance of a color (0.0 - 1.0).
    Uses the standard relative luminance formula: 0.299R + 0.587G + 0.114B.
    """
    return (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255.0


def adjust_brightness(hex_color: str, factor: float = 0.85) -> str:
    """
    Adjusts the brightness (Value) of a given color in HSV space.

    Args:
        hex_color: Color string in HEX format.
        factor: Multiplier for the brightness value (e.g., < 1.0 to darken, > 1.0 to lighten).

    Returns:
        Hexadecimal color string of the adjusted color.
    """
    color = get_qcolor(hex_color)

    # Precise implementation using HSV space
    h, s, v, a = color.getHsv()
    new_v = max(0, min(255, int(v * factor)))
    color.setHsv(h, s, new_v, a)
    return color.name()


def hex_to_rgba_string(hex_color: str, alpha: float) -> str:
    """
    Converts a hex color string to a CSS-compatible rgba() string with specified alpha.
    """
    c = get_qcolor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def is_color_too_close(c1: QColor, c2: QColor, threshold: int = 25) -> bool:
    """
    Checks if two colors are too similar using Euclidean distance in RGB space.
    Threshold ~30 is usually enough to distinguish UI elements.
    """
    rd = c1.red() - c2.red()
    gd = c1.green() - c2.green()
    bd = c1.blue() - c2.blue()
    dist = math.sqrt(rd*rd + gd*gd + bd*bd)
    return dist < threshold


def get_adaptive_alpha(color: QColor, base_alpha: float, is_dark_theme: bool) -> float:
    """
    Calculates adaptive alpha transparency based on luminance contrast.
    If the color is too close to the typical background brightness, alpha is
    increased to maintain visibility.
    """
    lum = get_relative_luminance(color)  # 0.0 to 1.0

    target_alpha = base_alpha

    if is_dark_theme:
        # Dark theme background is dark (~0.2 luminance)
        # If color is also dark (lum < 0.3), we need higher alpha
        if lum < 0.3:
            # Interpolate: if lum is 0.0 -> alpha 0.8, if lum is 0.3 -> base_alpha
            factor = (0.3 - lum) / 0.3
            target_alpha = base_alpha + (0.8 - base_alpha) * factor
    else:
        # Light theme background is light (~1.0 luminance)
        # If color is light (lum > 0.8), we need higher alpha
        if lum > 0.8:
            # Interpolate: if lum is 1.0 -> alpha 0.9, if lum is 0.6 -> base_alpha
            factor = (lum - 0.6) / 0.4
            target_alpha = base_alpha + (0.9 - base_alpha) * factor

    return round(min(1.0, max(0.0, target_alpha)), 2)


def select_theme(theme_name: str, accent_name: str = "Crimson"):
    """
    Selects a base theme and applies an accent color dynamically.
    Ensures sufficient contrast between the accent and the theme's background.

    Args:
        theme_name: Key from the THEMES dictionary.
        accent_name: Key from ACCENT_PALETTE or a custom HEX string.
    """
    global COLORS
    base_theme = THEMES.get(theme_name, THEMES["Light"]).copy()
    is_dark = base_theme.get("IS_DARK", False)

    # 1. Resolve base accent color
    if accent_name and accent_name.startswith("#"):
        hex_color = accent_name
    else:
        hex_color = ACCENT_PALETTE.get(accent_name, ACCENT_PALETTE["Crimson"])

    q_accent = get_qcolor(hex_color)

    # 2. Protection: Check contrast with Background
    bg_hex = base_theme.get("SECONDARY", "#FFFFFF")
    q_bg = get_qcolor(bg_hex)

    # Check if there is a conflict (colors are too close)
    if is_color_too_close(q_accent, q_bg, threshold=25):
        # Extract HSV (Hue, Saturation, Value) components
        h, s, v, a = q_accent.getHsv()
        bg_h, bg_s, bg_v, bg_a = q_bg.getHsv()

        # Define a safety brightness margin (0-255 scale)
        # 40 RGB units roughly correspond to 40-50 Value units
        safety_margin = 25

        if is_dark:
            # For dark themes, the accent color must be LIGHTER than the background.
            # If current color is darker or too close -> force higher brightness.
            new_v = max(v, bg_v + safety_margin)
            # Clamp to 255 (white)
            new_v = min(255, new_v)

            # Note: If 255 is not enough (bg is too light), we would need to lower Saturation (S),
            # but usually Value adjustment is sufficient.
        else:
            # For light themes, the accent color must be DARKER than the background.
            # New Value = Background Value - Margin.
            new_v = min(v, bg_v - safety_margin)
            # Clamp to 0 (black)
            new_v = max(0, new_v)

        q_accent.setHsv(h, s, new_v, a)
        hex_color = q_accent.name()

    # 3. Set ACCENT
    base_theme["ACCENT"] = hex_color

    # 4. Calculate Derived Colors
    base_theme["ACCENT_HOVER"] = adjust_brightness(hex_color, 0.85)

    lum = get_relative_luminance(q_accent)
    secondary_factor = 0.3
    if lum > 0.8:
        secondary_factor = 0.6
    elif lum > 0.6:
        secondary_factor = 0.45

    base_theme["ACCENT_SECONDARY"] = adjust_brightness(hex_color, secondary_factor)

    if is_dark:
        base_hover_alpha = 0.8
    else:
        base_hover_alpha = 0.3

    sel_alpha = get_adaptive_alpha(q_accent, 0.15, is_dark)
    sel_hover_alpha = get_adaptive_alpha(q_accent, base_hover_alpha, is_dark)

    base_theme["ACCENT_SELECTED"] = hex_to_rgba_string(hex_color, sel_alpha)
    base_theme["ACCENT_SELECTED_HOVER"] = hex_to_rgba_string(hex_color, sel_hover_alpha)
    base_theme["DZ_CONTAINER_ACCENT"] = hex_to_rgba_string(hex_color, 0.6)

    COLORS = base_theme


def apply_theme_vars(qss: str, vars_dict: dict) -> str:
    """
    Replaces occurrences of $VARIABLE_NAME in a QSS string with values from a dictionary.
    """
    for k, v in vars_dict.items():
        qss = re.sub(rf"\${k}\b", v, qss)
    return qss


def resolve_theme_vars(variables: dict) -> dict:
    """
    Recursively expands references like {ACCENT} or {SECONDARY} within the variables dictionary.
    Supports keys containing alphanumeric characters and underscores.
    """
    resolved = {}
    for key, value in variables.items():
        # Matches {word}
        pattern = r"\{(\w+)\}"

        # Loop to handle nested references
        while isinstance(value, str) and re.search(pattern, value):
            value = re.sub(
                pattern, lambda m: variables.get(m.group(1), m.group(0)), value
            )
        resolved[key] = value
    return resolved


def get_qcolor(color_str: str) -> QColor:
    """
    Converts a color string (HEX or RGBA) from the theme to a PyQt6 QColor object.

    Args:
        color_str: Hex string (#RRGGBB) or rgba string (rgba(r, g, b, a)).
    """
    if not color_str:
        return QColor()

    # 1. Handle rgba(r, g, b, a)
    if color_str.startswith("rgba"):
        match = re.search(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d\.]+)\)", color_str)
        if match:
            r, g, b, a = match.groups()
            # QColor alpha range is 0-255, CSS is 0.0-1.0
            alpha_int = int(float(a) * 255)
            return QColor(int(r), int(g), int(b), alpha_int)

    # 2. Handle HEX (#RRGGBB) or standard color names
    return QColor(color_str)


def get_compiled_stylesheet() -> str:
    """
    Loads, combines, and compiles the CSS/QSS files based on the currently active theme.
    Expands all variables and handles relative asset paths.

    Returns:
        The final parsed QSS string ready for application.
    """
    css_files_to_load = ["main.css", "scrollbars.css"]

    if COLORS.get("IS_DARK", False):
        css_files_to_load.append("dark_mod.css")

    if IS_LINUX:
        css_files_to_load.append("linux_mod.css")

    combined_stylesheet = ""
    for css_file in css_files_to_load:
        path = resource_path(f"assets/styles/{css_file}")
        style_file = QFile(path)
        if style_file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            combined_stylesheet += QTextStream(style_file).readAll() + "\n"
            style_file.close()
        else:
            print(f"WARNING: Could not open stylesheet file: {path}")

    if not combined_stylesheet:
        print("WARNING: Stylesheet is empty, could not apply styles.")
        return ""

    # Fix asset paths for QSS (replaces relative url(...) with absolute system paths)
    assets_base_path = resource_path("assets").replace("\\", "/")
    final_stylesheet = combined_stylesheet.replace(
        "url(assets/", f"url({assets_base_path}/"
    )

    # Expand internal references ({VAR})
    resolved_colors = resolve_theme_vars(COLORS)

    # Convert all values to strings to ensure regex compatibility (e.g. for boolean IS_DARK)
    stringified_colors = {k: str(v) for k, v in resolved_colors.items()}

    # Replace $VARS with final color values
    return apply_theme_vars(final_stylesheet, stringified_colors)