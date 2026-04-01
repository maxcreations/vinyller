#!/usr/bin/env python3

"""
Vinyller — Main launch file
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

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.core.library_manager import LibraryManager
from src.ui.ui_main import MainWindow
from src.utils import theme


def main():
    app = QApplication(sys.argv)

    app.setOrganizationName("Maxim Moshkin")
    app.setApplicationName("Vinyller")
    app.setOrganizationDomain("maxcreations.ru")
    version = QApplication.instance().applicationVersion()
    app.setApplicationVersion(version)

    library_manager = LibraryManager()
    settings = library_manager.load_settings()

    # fix linux/macos dropdowns/button styles and paddings
    app.setStyle("windows")

    if sys.platform == "darwin":
        app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    # fix base font size
    app_font = app.font()
    if sys.platform == "darwin":
        app_font.setPointSize(12)
    else:
        app_font.setPointSize(9)
    app.setFont(app_font)

    theme_name = settings.get("theme", "Light")
    accent_color = settings.get("accent_color", "Crimson")
    theme.select_theme(theme_name, accent_color)

    try:
        stylesheet = theme.get_compiled_stylesheet()
        if stylesheet:
            app.setStyleSheet(stylesheet)
            print(f"INFO: Stylesheets loaded successfully for theme: {theme_name}.")
    except Exception as e:
        print(f"ERROR: Error loading stylesheets: {e}")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

