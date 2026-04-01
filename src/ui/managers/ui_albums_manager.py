"""
Vinyller — Albums UI manager
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

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame

from src.ui.custom_base_widgets import StyledScrollArea
from src.ui.custom_classes import FlowLayout, SortMode, ViewMode
from src.utils.constants import BATCH_SIZE
from src.utils.utils import format_month_year
from src.utils.utils_translator import translate


class AlbumsUIManager:
    """
    Class managing the UI logic and state for the albums tab and individual album pages.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the AlbumsUIManager.
        """
        self.main_window = main_window
        self.ui_manager = ui_manager
        self.album_separator_widgets = {}

    def populate_albums_tab(self, initial_load_count=None):
        """
        Populates the main albums tab with the library's albums.
        """
        mw = self.main_window
        mw.last_album_group, mw.current_album_flow_layout = None, None
        self.album_separator_widgets.clear()

        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        mw.albums_scroll.setWidget(container)

        query = ""
        source_list = mw.data_manager.sorted_albums

        # Display random album suggestions if conditions are met
        if mw.show_random_suggestions and len(source_list) >= 20:
            suggestion_block = self.ui_manager.components.create_suggestion_block(
                "album", self.populate_albums_tab
            )
            if suggestion_block:
                layout.addWidget(suggestion_block)

        # Handle empty or loading library states
        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            mw.album_sort_button.hide()
            mw.album_view_button.hide()
            self.ui_manager.set_header_visibility(mw.albums_header, False)
            self.ui_manager.components._show_loading_library_message(layout)
            return

        if mw.data_manager.is_empty():
            mw.album_sort_button.hide()
            mw.album_view_button.hide()
            self.ui_manager.set_header_visibility(mw.albums_header, False)
            self.ui_manager.components._show_no_library_message(layout)
            return
        else:
            mw.album_sort_button.show()
            mw.album_view_button.show()
            self.ui_manager.set_header_visibility(mw.albums_header, True)

        count = len(source_list)
        mw.albums_header["details"].setText(translate("{count} album(s)", count=count))
        mw.albums_header["details"].show()

        mw.current_albums_display_list = source_list

        # Apply the selected sorting mode to the current albums display list
        if mw.album_sort_mode == SortMode.ALPHA_ASC:
            mw.current_albums_display_list.sort(
                key=lambda x: mw.data_manager.get_sort_key(x[0][1])
            )
        elif mw.album_sort_mode == SortMode.ALPHA_DESC:
            mw.current_albums_display_list.sort(
                key=lambda x: mw.data_manager.get_sort_key(x[0][1]), reverse=True
            )
        elif mw.album_sort_mode == SortMode.YEAR_ASC:
            mw.current_albums_display_list.sort(
                key=lambda x: (
                    x[1].get("year", 9999),
                    mw.data_manager.get_sort_key(x[0][1]),
                )
            )
        elif mw.album_sort_mode == SortMode.YEAR_DESC:
            mw.current_albums_display_list.sort(
                key=lambda x: (
                    x[1].get("year", 0),
                    mw.data_manager.get_sort_key(x[0][1]),
                ),
                reverse=True,
            )
        elif mw.album_sort_mode == SortMode.DATE_ADDED_ASC:
            mw.current_albums_display_list.sort(
                key=lambda x: x[1].get("date_added", float("inf"))
            )
        elif mw.album_sort_mode == SortMode.DATE_ADDED_DESC:
            mw.current_albums_display_list.sort(
                key=lambda x: x[1].get("date_added", 0), reverse=True
            )

        # Generate group separators based on the sorting criteria
        mw.album_groups = set()
        if mw.show_separators:
            for album_key, data in mw.current_albums_display_list:
                current_group = None
                if mw.album_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    album_title = mw.data_manager.get_sort_key(album_key[1])
                    first_char = album_title[0] if album_title else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.album_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                    album_year = data.get("year")
                    if album_year is None or album_year == 0:
                        current_group = "#"
                    else:
                        current_group = str(album_year)
                elif mw.album_sort_mode in [
                    SortMode.DATE_ADDED_ASC,
                    SortMode.DATE_ADDED_DESC,
                ]:
                    timestamp = data.get("date_added", 0)
                    current_group = format_month_year(timestamp)

                if current_group:
                    mw.album_groups.add(current_group)

        mw.albums_loaded_count = 0

        if mw.albums_loaded_count < len(mw.current_albums_display_list):
            self.load_more_albums()
        layout.addStretch(1)

    def load_more_albums(self):
        """
        Loads the next batch of albums into the view for lazy loading.
        """
        mw = self.main_window
        if not mw.albums_scroll.widget():
            return
        if mw.is_loading_albums:
            return
        album_list = mw.current_albums_display_list
        if mw.albums_loaded_count >= len(album_list):
            return

        mw.is_loading_albums = True
        start, end = mw.albums_loaded_count, min(
            mw.albums_loaded_count + BATCH_SIZE, len(album_list)
        )
        main_layout = mw.albums_scroll.widget().layout()
        stretch_item = None

        if main_layout.count() > 0:
            last_item = main_layout.itemAt(main_layout.count() - 1)
            if last_item and last_item.spacerItem():
                stretch_item = main_layout.takeAt(main_layout.count() - 1)

        for i in range(start, end):
            album_key, data = album_list[i]
            current_group = None

            # Add separators for the current batch if enabled
            if mw.show_separators:
                if mw.album_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    album_title = mw.data_manager.get_sort_key(album_key[1])
                    first_char = album_title[0] if album_title else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.album_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                    album_year = data.get("year")
                    if album_year is None or album_year == 0:
                        current_group = "#"
                    else:
                        current_group = str(album_year)
                elif mw.album_sort_mode in [
                    SortMode.DATE_ADDED_ASC,
                    SortMode.DATE_ADDED_DESC,
                ]:
                    timestamp = data.get("date_added", 0)
                    current_group = format_month_year(timestamp)

                if current_group and current_group != mw.last_album_group:
                    separator_widget = self.ui_manager.components._create_separator_widget(
                        current_group, "albums", mw.album_groups
                    )
                    main_layout.addWidget(separator_widget)
                    self.album_separator_widgets[current_group] = separator_widget
                    mw.last_album_group = current_group
                    mw.current_album_flow_layout = None

            # Setup layout depending on the view mode
            target_layout = main_layout
            if mw.album_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_album_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_album_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_album_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_album_flow_layout

            widget = self.ui_manager.components.create_album_widget(
                album_key, data, mw.album_view_mode
            )
            widget.activated.connect(
                partial(self.show_album_tracks, source_stack=mw.albums_stack)
            )

            widget.contextMenuRequested.connect(
                lambda data, pos: mw.action_handler.show_context_menu(
                    data, pos, context={"forced_type": "album"}
                )
            )

            widget.playClicked.connect(mw.player_controller.smart_play)
            target_layout.addWidget(widget)

        if stretch_item:
            main_layout.addItem(stretch_item)

        mw.albums_loaded_count = end
        mw.is_loading_albums = False

        QTimer.singleShot(100, self._check_for_more_albums)

    def _check_for_more_albums(self):
        """
        Checks if the scrollbar is near the bottom to trigger loading more albums.
        """
        mw = self.main_window
        if not mw.albums_scroll.widget():
            return
        scroll_bar = mw.albums_scroll.verticalScrollBar()
        has_more_data = mw.albums_loaded_count < len(mw.current_albums_display_list)
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_albums()

    def navigate_to_year(self, year_str):
        """
        Navigates to the albums tab and filters/sorts to show albums from a specific year.
        """
        mw = self.main_window
        needs_reload = False

        try:
            album_tab_index = mw.nav_button_icon_names.index("album")
        except ValueError:
            return

        if mw.main_stack.currentIndex() != album_tab_index:
            mw.main_stack.setCurrentIndex(album_tab_index)
            mw.nav_buttons[album_tab_index].setChecked(True)
            self.ui_manager.update_nav_button_icons()
            mw.update_current_view_state(main_tab_index=album_tab_index)

        if mw.albums_stack.currentIndex() != 0:
            mw.albums_stack.setCurrentIndex(0)

        if mw.album_sort_mode not in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
            mw.album_sort_mode = SortMode.YEAR_DESC
            if hasattr(self.ui_manager.components, "update_tool_button_icon"):
                self.ui_manager.components.update_tool_button_icon(mw.album_sort_button, mw.album_sort_mode)
            needs_reload = True

        if hasattr(mw, "albums_grid_layout") and mw.albums_grid_layout.count() == 0:
            needs_reload = True

        if needs_reload:
            if hasattr(mw, 'toast'):
                mw.toast.show_message(f"{translate('Sorting by year:')} {year_str}...", duration=0)

            def delayed_action():
                self.populate_albums_tab()
                QTimer.singleShot(100, lambda: mw.scroll_to_letter(str(year_str), "albums"))

            QTimer.singleShot(50, delayed_action)
        else:
            mw.scroll_to_letter(str(year_str), source_view="albums")

    def show_album_tracks(self, album_key, source_stack):
        """
        Displays the tracklist and details for a selected album, handling UI layout
        routing depending on which stack triggered the view.
        """
        mw = self.main_window
        album_title = album_key[1]
        target_header_layout = None
        target_content_layout = None
        back_slot = self.ui_manager.navigate_back
        stack_index = 1

        # Determine target layout and stack index based on the origin view
        if source_stack == mw.favorites_stack:
            if mw.current_favorites_context in ["artist", "genre", "composer"]:
                target_header_layout = mw.favorite_album_detail_header_layout
                target_content_layout = mw.favorite_album_detail_layout
                stack_index = 2
            else:
                target_header_layout = mw.favorite_detail_header_layout
                target_content_layout = mw.favorite_detail_layout
                stack_index = 1

        elif source_stack == mw.charts_stack:
            if mw.current_charts_context in ["artist", "genre", "composer"]:
                target_header_layout = mw.chart_album_detail_header_layout
                target_content_layout = mw.chart_album_detail_layout
                stack_index = 2
            else:
                target_header_layout = mw.chart_detail_header_layout
                target_content_layout = mw.chart_detail_layout
                stack_index = 1

        elif source_stack == mw.artists_stack:
            target_header_layout = mw.artist_album_tracks_header_layout
            target_content_layout = mw.artist_album_tracks_layout
            stack_index = 2
        elif source_stack == mw.composers_stack:
            target_header_layout = mw.composer_album_tracks_header_layout
            target_content_layout = mw.composer_album_tracks_layout
            stack_index = 2
        elif source_stack == mw.genres_stack:
            target_header_layout = mw.genre_album_tracks_header_layout
            target_content_layout = mw.genre_album_tracks_layout
            stack_index = 2
        else:
            target_header_layout = mw.album_tracks_header_layout
            target_content_layout = mw.album_tracks_layout
            stack_index = 1

        self.ui_manager.clear_layout(target_header_layout)
        self.ui_manager.clear_layout(target_content_layout)

        fav_button = self.ui_manager.components._create_favorite_button(album_key, "album")

        # Check if the album exists in the data manager
        if not (album_data := mw.data_manager.albums_data.get(album_key)):
            header_parts = self.ui_manager.components.create_page_header(
                album_title,
                back_slot=back_slot,
                control_widgets=[fav_button],
                context_menu_data=(album_key, "album"),
            )
            target_header_layout.addWidget(header_parts["header"])
            text_label = QLabel(translate("Could not find album data."))
            text_label.setProperty("class", "textColorPrimary")
            target_content_layout.addWidget(text_label)
            return

        tracks = album_data.get("tracks", [])
        track_count = len(tracks)
        has_virtual_tracks = any(t.get("is_virtual", False) for t in tracks)

        if has_virtual_tracks:
            tracks_text = translate(
                "{count} virtual tracks (extracted from CUE file)", count=track_count
            )
        else:
            tracks_text = translate("{count} track(s)", count=track_count)
        details_text = f"{tracks_text}"

        header_parts = self.ui_manager.components.create_page_header(
            album_title,
            details_text=details_text,
            back_slot=back_slot,
            control_widgets=[fav_button],
            play_slot_data=album_key,
            context_menu_data=(album_key, "album"),
        )
        if play_button := header_parts.get("play_button"):
            play_button.clicked.connect(
                lambda: mw.player_controller.play_data(album_key)
            )
            mw.main_view_header_play_buttons[album_key] = play_button

        target_header_layout.addWidget(header_parts["header"])
        content_container = QWidget()
        content_container.setProperty("class", "backgroundPrimary")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        enc_wrapper = QWidget()
        enc_layout = QVBoxLayout(enc_wrapper)
        enc_layout.setContentsMargins(24, 24, 24, 0)

        self.ui_manager.inject_encyclopedia_section(
            enc_layout,
            album_key,
            "album",
            lambda: self.show_album_tracks(album_key, source_stack),
        )

        if enc_layout.count() > 0:
            content_layout.addWidget(enc_wrapper)
        else:
            enc_wrapper.deleteLater()

        # Handle album merge warnings
        if not mw.treat_folders_as_unique and not getattr(
                mw, "dismissed_album_merge_warning", False
        ):
            tracks = album_data.get("tracks", [])
            titles = [t.get("title", "").strip().lower() for t in tracks]
            has_duplicate_titles = len(titles) != len(set(titles))
            nums = [
                t.get("tracknumber", 0) for t in tracks if t.get("tracknumber", 0) > 0
            ]
            has_duplicate_nums = len(nums) != len(set(nums))
            if has_duplicate_titles or has_duplicate_nums:
                if has_virtual_tracks:
                    pass
                else:
                    warning_widget = self.ui_manager.components.create_album_merge_warning_widget()
                    warning_widget.layout().setContentsMargins(24, 24, 24, 0)
                    content_layout.addWidget(warning_widget)

        album_widget = self.ui_manager.components._create_detailed_album_widget(
            album_key, album_data
        )
        album_widget.setContentsMargins(24, 24, 24, 24)
        content_layout.addWidget(album_widget)
        content_layout.addStretch()

        scroll_area = StyledScrollArea()
        scroll_area.setProperty("class", "backgroundPrimary")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(content_container)

        target_content_layout.addWidget(scroll_area, 1)
        source_stack.setCurrentIndex(stack_index)

        # Save context to maintain proper UI state
        main_tab_index, context = -1, {}
        if source_stack == mw.favorites_stack:
            main_tab_index = mw.nav_button_icon_names.index("favorite")
            if mw.current_favorites_context == "artist":
                context = {
                    "context": "artist",
                    "data": mw.current_artist_view,
                    "album_key": list(album_key),
                }
            elif mw.current_favorites_context == "genre":
                context = {
                    "context": "genre",
                    "data": mw.current_genre_view,
                    "album_key": list(album_key),
                }
            else:
                context = {"context": "album", "data": list(album_key)}
        elif source_stack == mw.charts_stack:
            main_tab_index = mw.nav_button_icon_names.index("charts")
            if mw.current_charts_context == "artist":
                context = {
                    "context": "artist",
                    "data": mw.current_artist_view,
                    "album_key": list(album_key),
                }
            elif mw.current_charts_context == "genre":
                context = {
                    "context": "genre",
                    "data": mw.current_genre_view,
                    "album_key": list(album_key),
                }
            else:
                context = {"context": "album", "data": list(album_key)}
        elif source_stack == mw.artists_stack:
            main_tab_index = mw.nav_button_icon_names.index("artist")
            context = {
                "artist_name": mw.current_artist_view,
                "album_key": list(album_key),
            }
        elif source_stack == mw.composers_stack:
            main_tab_index = mw.nav_button_icon_names.index("composer")
            context = {
                "composer_name": mw.current_composer_view,
                "album_key": list(album_key),
            }
        elif source_stack == mw.genres_stack:
            main_tab_index = mw.nav_button_icon_names.index("genre")
            context = {
                "genre_name": mw.current_genre_view,
                "album_key": list(album_key),
            }
        else:
            main_tab_index = mw.nav_button_icon_names.index("album")
            context = {"album_key": list(album_key)}

        mw.update_current_view_state(
            main_tab_index=main_tab_index, context_data=context
        )
        self.ui_manager.update_all_track_widgets()

    def navigate_to_album_tab_and_show(self, album_key):
        """
        Navigates to the albums tab and immediately shows the specified album's tracks.
        """
        mw = self.main_window

        try:
            album_tab_index = mw.nav_button_icon_names.index("album")
            mw.main_stack.setCurrentIndex(album_tab_index)
            mw.nav_buttons[album_tab_index].setChecked(True)
            self.ui_manager.update_nav_button_icons()
        except (ValueError, IndexError):
            print("Error: Could not find 'album' tab to navigate.")
            return

        self.show_album_tracks(album_key, source_stack=mw.albums_stack)

    def navigate_to_album(self, album_key):
        """
        Locates a specific album in the data manager and navigates to its view.
        """
        mw = self.main_window
        dm = mw.data_manager

        target_key = album_key

        if album_key not in dm.albums_data and isinstance(album_key, (tuple, list)):
            search_tuple = tuple(album_key[:3])
            for real_key in dm.albums_data.keys():
                if isinstance(real_key, tuple) and real_key[:3] == search_tuple:
                    target_key = real_key
                    break

        if target_key in dm.albums_data:
            album_artist = target_key[0]
            if album_artist:
                artist_tab_index = mw.nav_button_icon_names.index("artist")
                mw.main_stack.setCurrentIndex(artist_tab_index)
                mw.nav_buttons[artist_tab_index].setChecked(True)
                self.ui_manager.update_nav_button_icons()
                self.ui_manager.show_artist_albums(album_artist)
                self.show_album_tracks(target_key, source_stack=mw.artists_stack)