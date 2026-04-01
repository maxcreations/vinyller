"""
Vinyller — History UI manager
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

from PyQt6.QtCore import QObject, QSize
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from src.ui.custom_base_widgets import TranslucentMenu
from src.utils import theme
from src.utils.utils import create_svg_icon
from src.utils.utils_translator import translate


class HistoryUIManager(QObject):
    """
    Manages the UI logic specifically for the History tab.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the HistoryUIManager.
        """
        super().__init__()
        self.main_window = main_window
        self.ui_manager = ui_manager

    def populate_history_tab(self, initial_load_count=None):
        """
        Populates the main playback history view.

        Args:
            initial_load_count (int, optional): The initial number of items to load
                (currently unused in the implementation).
        """
        mw = self.main_window

        scroll_widget = mw.history_scroll.widget()
        if scroll_widget:
            self.ui_manager.clear_layout(scroll_widget.layout())
            layout = scroll_widget.layout()
        else:
            scroll_widget = QWidget()
            scroll_widget.setProperty("class", "backgroundPrimary")
            layout = QVBoxLayout(scroll_widget)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(24)
            mw.history_scroll.setWidget(scroll_widget)

        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            self.ui_manager.set_header_visibility(mw.history_header, False)
            self.ui_manager.components._show_loading_library_message(layout)
            return

        history_paths = mw.library_manager.load_playback_history()
        source_tracks = [
            mw.data_manager.get_track_by_path(p)
            for p in history_paths
            if mw.data_manager.get_track_by_path(p)
        ]

        if not source_tracks:
            self.ui_manager.set_header_visibility(mw.history_header, False)
            if mw.data_manager.is_empty():
                self.ui_manager.components._show_no_library_message(layout)
            else:
                self.ui_manager.components._show_no_history_results_message(layout)
            return

        self.ui_manager.set_header_visibility(mw.history_header, True)

        if btn := mw.history_header.get("shake_button"):
            btn.hide()

        if btn := mw.history_header.get("play_button"):
            try:
                btn.clicked.disconnect()
            except TypeError:
                pass
            btn.clicked.connect(
                lambda: mw.player_controller.play_data("playback_history")
            )

        tracks_to_show = source_tracks

        count = len(tracks_to_show)
        mw.history_header["details"].setText(translate("{count} track(s)", count=count))
        mw.history_header["details"].show()

        pixmap = self.ui_manager.components.history_pixmap_128
        playlist_name = translate("Playback history")
        playlist_path = "playback_history"

        playlist_widget = self.ui_manager.components._create_detailed_playlist_widget(
            playlist_path=playlist_path,
            playlist_name=playlist_name,
            tracks=tracks_to_show,
            pixmap=pixmap,
        )

        if hasattr(playlist_widget, "playlistContextMenu"):
            try:
                playlist_widget.playlistContextMenu.disconnect()
            except TypeError:
                pass
            playlist_widget.playlistContextMenu.connect(
                self.show_history_card_context_menu
            )

        if hasattr(playlist_widget, "trackContextMenu"):
            try:
                playlist_widget.trackContextMenu.disconnect()
            except TypeError:
                pass
            playlist_widget.trackContextMenu.connect(
                lambda track, pos: mw.action_handler.show_context_menu(
                    track, pos, context={"source": "history"}
                )
            )

        layout.addWidget(playlist_widget)
        layout.addStretch(1)

        self.ui_manager.update_all_track_widgets()

    def load_more_history(self):
        """
        Not implemented for the history tab. Items load fully at once.
        """
        pass

    def _check_for_more_history(self):
        """
        Not implemented for the history tab.
        """
        pass

    def show_history_card_context_menu(self, data, global_pos):
        """
        Displays a context menu for an item in the playback history.

        Args:
            data: The data payload associated with the history item.
            global_pos (QPoint): The global screen coordinates to display the menu at.
        """
        mw = self.main_window
        menu = TranslucentMenu(mw)

        icn_play = QIcon(
            create_svg_icon(
                f"assets/control/play_outline.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )

        icn_play_next = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_play.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )

        icn_add_to_queue = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_add.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )

        play_action = QAction(icn_play, translate("Play"), mw)
        play_action.triggered.connect(lambda: mw.player_controller.play_data(data))
        menu.addAction(play_action)

        play_next_action = QAction(icn_play_next, translate("Play Next"), mw)
        play_next_action.triggered.connect(lambda: mw.action_handler.play_next(data))
        menu.addAction(play_next_action)

        add_to_queue_action = QAction(icn_add_to_queue, translate("Add to Queue"), mw)
        add_to_queue_action.triggered.connect(
            lambda: mw.action_handler.add_to_queue(data)
        )
        menu.addAction(add_to_queue_action)

        menu.exec(global_pos)