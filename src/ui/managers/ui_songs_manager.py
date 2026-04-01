"""
Vinyller — Songs UI manager
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

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from src.ui.custom_classes import SortMode, FlowLayout
from src.utils.constants import BATCH_SIZE_ALLTRACKS
from src.utils.utils_translator import translate


class SongsUIManager:
    """
    Class managing the UI logic and state for the all tracks (songs) tab.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the SongsUIManager.
        """
        self.main_window = main_window
        self.ui_manager = ui_manager

    def populate_songs_tab(self, initial_load_count=None):
        """
        Populates the main songs view, grouping tracks appropriately.

        Args:
            initial_load_count (int, optional): The initial number of items to load
                (currently unused in the implementation).
        """
        mw = self.main_window

        while mw.songs_nav_layout.count():
            item = mw.songs_nav_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        mw.songs_scroll.setWidget(container)

        source_list = mw.data_manager.sorted_songs_groups
        track_count = len(mw.data_manager.all_tracks)

        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            mw.song_sort_button.hide()
            self.ui_manager.set_header_visibility(mw.songs_header, False)
            mw.songs_nav_container.hide()
            self.ui_manager.components._show_loading_library_message(layout)
            return

        if mw.data_manager.is_empty():
            mw.song_sort_button.hide()
            self.ui_manager.set_header_visibility(mw.songs_header, False)
            mw.songs_nav_container.hide()
            self.ui_manager.components._show_no_library_message(layout)
            return
        else:
            mw.song_sort_button.show()
            self.ui_manager.set_header_visibility(mw.songs_header, True)

        mw.songs_header["details"].setText(
            translate("{count} track(s)", count=track_count)
        )
        mw.songs_header["details"].show()

        if mw.song_sort_mode in (SortMode.ARTIST_ASC, SortMode.ARTIST_DESC):
            source_list.sort(
                key=lambda x: (
                    mw.data_manager.get_sort_key(x[0][0]),
                    mw.data_manager.get_sort_key(x[0][1]),
                ),
                reverse=(mw.song_sort_mode == SortMode.ARTIST_DESC)
            )
        elif mw.song_sort_mode in (SortMode.ALPHA_ASC, SortMode.ALPHA_DESC):
            source_list.sort(
                key=lambda x: (
                    mw.data_manager.get_sort_key(x[0][1]),
                    mw.data_manager.get_sort_key(x[0][0]),
                ),
                reverse=(mw.song_sort_mode == SortMode.ALPHA_DESC)
            )
        elif mw.song_sort_mode in (SortMode.YEAR_DESC, SortMode.YEAR_ASC):
            source_list.sort(
                key=lambda x: (
                    mw.data_manager.albums_data.get(x[0], {}).get("year", 0),
                    mw.data_manager.get_sort_key(x[0][0]),
                    mw.data_manager.get_sort_key(x[0][1]),
                ),
                reverse=(mw.song_sort_mode == SortMode.YEAR_DESC)
            )

        grouped_items = {}
        ordered_groups = []

        for album_key, tracks in source_list:
            group = "#"
            if mw.song_sort_mode in (SortMode.ARTIST_ASC, SortMode.ARTIST_DESC):
                artist_name = mw.data_manager.get_sort_key(album_key[0])
                first_char = artist_name[0] if artist_name else "#"
                group = first_char.upper() if first_char.isalpha() else "#"
            elif mw.song_sort_mode in (SortMode.ALPHA_ASC, SortMode.ALPHA_DESC):
                album_title = mw.data_manager.get_sort_key(album_key[1])
                first_char = album_title[0] if album_title else "#"
                group = first_char.upper() if first_char.isalpha() else "#"
            elif mw.song_sort_mode in (SortMode.YEAR_DESC, SortMode.YEAR_ASC):
                album_year = mw.data_manager.albums_data.get(album_key, {}).get("year")
                if album_year is None or album_year == 0:
                    group = "#"
                else:
                    period_start = (album_year // 5) * 5
                    group = f"{period_start}-{period_start + 4}"

            if group not in grouped_items:
                grouped_items[group] = []
                ordered_groups.append(group)
            grouped_items[group].append((album_key, tracks))

        if mw.song_sort_mode in (SortMode.ARTIST_ASC, SortMode.ARTIST_DESC, SortMode.ALPHA_ASC, SortMode.ALPHA_DESC):
            ordered_groups.sort()
        elif mw.song_sort_mode in (SortMode.YEAR_DESC, SortMode.YEAR_ASC):
            is_reverse = (mw.song_sort_mode == SortMode.YEAR_DESC)
            ordered_groups.sort(reverse=is_reverse)

        if not getattr(mw, "current_songs_group", None) or mw.current_songs_group not in grouped_items:
            mw.current_songs_group = ordered_groups[0] if ordered_groups else None

        if mw.current_songs_group and mw.current_songs_group in grouped_items:
            mw.current_songs_display_list = grouped_items[mw.current_songs_group]
        else:
            mw.current_songs_display_list = []

        if ordered_groups and len(ordered_groups) > 1:
            nav_inner = QWidget()
            nav_inner_layout = QVBoxLayout(nav_inner)
            nav_inner_layout.setContentsMargins(0, 0, 0, 0)
            nav_inner_layout.setSpacing(16)

            buttons_container = QWidget()
            buttons_container.setContentsMargins(0, 0, 0, 0)
            flow_layout = FlowLayout(buttons_container)
            flow_layout.setSpacing(8)

            for group in ordered_groups:
                btn = QPushButton(group)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setCheckable(True)

                if group == mw.current_songs_group:
                    btn.setChecked(True)

                btn.setProperty("class", "btnAlphaJump")
                btn.clicked.connect(lambda checked, g=group: self._on_group_selected(g))
                flow_layout.addWidget(btn)

            nav_inner_layout.addWidget(buttons_container)

            header_layout = QVBoxLayout()
            header_layout.setSpacing(4)
            header_layout.setContentsMargins(0, 0, 0, 0)

            title_text = ""
            subtitle_context = "group"

            if mw.song_sort_mode in (SortMode.ARTIST_ASC, SortMode.ARTIST_DESC):
                title_text = translate("Sorted by artist")
            elif mw.song_sort_mode in (SortMode.ALPHA_ASC, SortMode.ALPHA_DESC):
                title_text = translate("Sorted by album")
            elif mw.song_sort_mode in (SortMode.YEAR_DESC, SortMode.YEAR_ASC):
                title_text = translate("Sorted by period")
                subtitle_context = "period"

            album_count = len(mw.current_songs_display_list)
            track_count_in_group = sum(len(tracks) for _, tracks in mw.current_songs_display_list)

            if subtitle_context == "period":
                subtitle_text = (f"{translate('{count} album(s)', count=album_count)}"
                                 f", {translate('{count} track(s)', count=track_count_in_group)}"
                                 f" {translate('in selected period')}")
            else:
                subtitle_text = (f"{translate('{count} album(s)', count=album_count)}"
                                 f", {translate('{count} track(s)', count=track_count_in_group)}"
                                 f" {translate('in selected group')}")

            subtitle_label = QLabel(subtitle_text)
            subtitle_label.setProperty("class", "textSecondary textColorTertiary")
            header_layout.addWidget(subtitle_label)

            nav_inner_layout.addLayout(header_layout)

            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setContentsMargins(0, 0, 0, 0)
            sep.setProperty("class", "separator")
            nav_inner_layout.addWidget(sep)

            mw.songs_nav_layout.addWidget(nav_inner)
            mw.songs_nav_container.show()
        else:
            mw.songs_nav_container.hide()

        mw.songs_loaded_count = 0

        if mw.songs_loaded_count < len(mw.current_songs_display_list):
            self.load_more_songs()

    def _on_group_selected(self, group):
        """
        Handles selection of a specific group (e.g., letter, year range) in the navigation bar.

        Args:
            group (str): The identifier of the selected group.
        """
        self.main_window.current_songs_group = group
        self.main_window.songs_scroll.verticalScrollBar().setValue(0)
        self.populate_songs_tab()

    def load_more_songs(self):
        """
        Loads the next batch of songs into the view.
        """
        mw = self.main_window
        if not mw.songs_scroll.widget():
            return
        if mw.is_loading_songs:
            return

        songs_list = mw.current_songs_display_list
        if mw.songs_loaded_count >= len(songs_list):
            return

        mw.is_loading_songs = True
        start, end = mw.songs_loaded_count, min(
            mw.songs_loaded_count + BATCH_SIZE_ALLTRACKS, len(songs_list)
        )
        main_layout = mw.songs_scroll.widget().layout()

        if (
            main_layout.count() > 0
            and (
                stretch_item := main_layout.itemAt(main_layout.count() - 1)
            ).spacerItem()
        ):
            main_layout.takeAt(main_layout.count() - 1)

        for i in range(start, end):
            album_key, tracks = songs_list[i]
            if not (album_data := mw.data_manager.albums_data.get(album_key)):
                continue

            tracks_to_show = tracks

            main_layout.addWidget(
                self.ui_manager.components._create_detailed_album_widget(
                    album_key, album_data, tracks_to_show=tracks_to_show
                )
            )

            if i < len(songs_list) - 1:
                separator = QWidget()
                separator.setFixedHeight(1)
                separator.setProperty("class", "separator")
                main_layout.addWidget(separator)

        main_layout.addStretch(1)
        mw.songs_loaded_count = end
        mw.is_loading_songs = False

        QTimer.singleShot(100, self._check_for_more_songs)

    def _check_for_more_songs(self):
        """
        Checks if more songs should be loaded to fill the view.
        """
        mw = self.main_window
        if not mw.songs_scroll.widget():
            return
        scroll_bar = mw.songs_scroll.verticalScrollBar()
        has_more_data = mw.songs_loaded_count < len(mw.current_songs_display_list)
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_songs()