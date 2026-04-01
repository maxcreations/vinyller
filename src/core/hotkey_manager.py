"""
Vinyller — Hotkey manager
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

from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence

from src.utils.utils_translator import translate


class HotkeyManager:
    """
    Manages all keyboard shortcuts for the application.
    """

    BINDINGS = {
        "play_pause": ["Space", Qt.Key.Key_MediaTogglePlayPause, Qt.Key.Key_MediaPlay],
        "next_track": ["F", "Ctrl+Right", Qt.Key.Key_MediaNext],
        "prev_track": ["B", "Ctrl+Left", Qt.Key.Key_MediaPrevious],
        "vol_up": ["Ctrl+Up", "=", "+"],
        "vol_down": ["Ctrl+Down", "-"],
        "mute": ["M"],
        "shuffle": ["S"],
        "repeat": ["R"],
        "cycle_win": ["C"],
        "settings": ["P"],
        "search": ["Ctrl+F"],
        "favorite": ["L"]
    }

    @classmethod
    def get_hotkey_str(cls, action_id: str) -> str:
        """
        Returns the string representation of the primary hotkey for the UI.
        For example: HotkeyManager.get_hotkey_str("play_pause") returns "Space".
        """
        keys = cls.BINDINGS.get(action_id)
        if keys and isinstance(keys[0], str):
            return keys[0]
        return ""

    @staticmethod
    def get_hotkey_list():
        """Returns a list of (hotkey_string, description) tuples, sorted by description."""
        grouped = {
            translate("Play / Pause"): ["Space", "Media Play"],
            translate("Next Track"): ["Ctrl+Right", "F", "Media Next"],
            translate("Previous Track"): ["Ctrl+Left", "B", "Media Previous"],
            translate("Increase Volume"): ["Ctrl+Up", "=", "+"],
            translate("Decrease Volume"): ["Ctrl+Down", "-"],
            translate("Mute / Unmute"): ["M"],
            translate("Toggle Shuffle"): ["S"],
            translate("Cycle Repeat Mode"): ["R"],
            translate("Cycle window modes"): ["C"],
            translate("Focus Search Field"): ["Ctrl+F"],
            translate("Toggle Favorite"): ["L"],
            translate("Open Settings"): ["P"],
        }

        hotkeys = [(", ".join(keys), desc) for desc, keys in grouped.items()]

        for i in range(10):
            hotkeys.append(
                (f"Ctrl+{i}", translate("Seek to {percent}% of track", percent=i * 10))
            )

        return hotkeys

    def __init__(self, main_window, player_controller, action_handler):
        """
        Initialize the HotkeyManager.

        :param main_window: The main window instance.
        :param player_controller: The player controller instance.
        :param action_handler: The action handler instance.
        """
        self.main_window = main_window
        self.player_controller = player_controller
        self.action_handler = action_handler
        self.player = main_window.player

        self.shortcuts = []
        self.setup_hotkeys()

    def setup_hotkeys(self):
        """
        Creates and connects all the shortcuts.
        """
        action_map = {
            "play_pause": self.player_controller.toggle_play_pause,
            "next_track": self.player.next,
            "prev_track": self.player.previous,
            "vol_up": self.increase_volume,
            "vol_down": self.decrease_volume,
            "mute": self.main_window.toggle_mute,
            "shuffle": self.player_controller.toggle_shuffle,
            "repeat": self.player_controller.cycle_repeat_mode,
            "cycle_win": self.main_window.cycle_window_mode,
            "settings": self.main_window.open_settings,
            "search": self.focus_search,
            "favorite": self.action_handler.toggle_current_track_favorite,
        }

        for action_id, function in action_map.items():
            for key in self.BINDINGS.get(action_id, []):
                shortcut = QShortcut(QKeySequence(key), self.main_window)
                shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
                shortcut.activated.connect(function)
                self.shortcuts.append(shortcut)

        for i in range(0, 10):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self.main_window)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(partial(self.seek_to_percentage, i * 10))
            self.shortcuts.append(shortcut)

    def increase_volume(self):
        """
        Increases the player volume by 5%.
        """
        current_volume = self.main_window.control_panel.volume_slider.value()
        new_volume = min(current_volume + 5, 100)
        self.main_window.control_panel.volume_slider.setValue(new_volume)

    def decrease_volume(self):
        """
        Decreases the player volume by 5%.
        """
        current_volume = self.main_window.control_panel.volume_slider.value()
        new_volume = max(current_volume - 5, 0)
        self.main_window.control_panel.volume_slider.setValue(new_volume)

    def seek_to_percentage(self, percentage):
        """
        Seeks the current track to a given percentage.
        :param percentage: An integer from 0 to 100.
        """
        duration = self.player.player.duration()
        if duration > 0:
            position = int(duration * (percentage / 100.0))
            self.player.set_position(position)

    def focus_search(self):
        """Sets focus to the global search input field."""
        mw = self.main_window

        if mw.vinyl_toggle_button.isChecked():
            mw.return_from_vinyl_widget()

        if hasattr(mw, "global_search_bar") and mw.global_search_bar.isVisible():
            mw.global_search_bar.setFocus()
            mw.global_search_bar.selectAll()