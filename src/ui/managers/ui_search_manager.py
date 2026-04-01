"""
Vinyller — Search UI manager
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

import os

from PyQt6.QtCore import (
    QSize, Qt
)
from PyQt6.QtGui import (
    QAction
)
from PyQt6.QtWidgets import (
    QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
)

from src.ui.custom_base_widgets import StyledScrollArea, set_custom_tooltip
from src.ui.custom_cards import CardWidget
from src.ui.custom_classes import (
    apply_button_opacity_effect, FlowLayout, SearchMode, SortMode, ViewMode, EntityCoverButton
)
from src.utils import theme
from src.utils.constants import BATCH_SIZE, BATCH_SIZE_ALLTRACKS
from src.utils.utils import create_svg_icon
from src.utils.utils_translator import translate


class SearchUIManager:
    """
    A class that manages the display logic for GLOBAL search results.
    """

    def __init__(self, main_window, manager):
        """
        Initializes the SearchUIManager with references to the main window
        and the main UI manager.
        """
        self.main_window = main_window
        self.manager = manager

    def populate_search_results(self):
        """
        Populates the search results page based on mw.current_search_results.
        """
        mw = self.main_window
        mw.is_loading_search = False
        mw.search_loaded_count = 0

        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        mw.search_scroll.setWidget(container)

        self.update_search_controls()
        self.update_search_view_options()

        query = mw.global_search_bar.text().strip()

        count = len(mw.current_search_results)
        details_text = (
            translate("Found: {count}", count=count)
            if count > 0
            else translate("No results found")
        )
        if hasattr(mw, "search_header") and mw.search_header:
            mw.search_header["details"].setText(details_text)

        if not mw.current_search_results:
            self.manager.components._show_no_search_results_message(layout)
            return

        self.load_more_search_results()

    def load_more_search_results(self):
        """Lazy loading of search results."""
        mw = self.main_window

        if mw.is_loading_search:
            return

        if mw.search_loaded_count >= len(mw.current_search_results):
            return

        mw.is_loading_search = True

        try:
            query = mw.global_search_bar.text().strip()
            start = mw.search_loaded_count
            batch_size = (
                BATCH_SIZE_ALLTRACKS
                if mw.search_view_mode == ViewMode.ALL_TRACKS
                else BATCH_SIZE
            )
            end = min(start + batch_size, len(mw.current_search_results))

            container = mw.search_scroll.widget()
            if not container:
                return
            main_layout = container.layout()

            if main_layout.count() > 0:
                item = main_layout.itemAt(main_layout.count() - 1)
                if item.spacerItem():
                    main_layout.takeAt(main_layout.count() - 1)

            search_mode = mw.search_mode
            target_layout = main_layout

            if search_mode not in [
                SearchMode.EVERYWHERE,
                SearchMode.FAVORITES,
                SearchMode.TRACKS,
                SearchMode.LYRICS,
            ] and mw.search_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:

                flow_container_found = False
                for i in range(main_layout.count()):
                    item = main_layout.itemAt(i)
                    if item.widget() and isinstance(item.widget().layout(), FlowLayout):
                        target_layout = item.widget().layout()
                        flow_container_found = True
                        break

                if not flow_container_found:
                    flow_container = QWidget()
                    target_layout = FlowLayout(flow_container, stretch_items=True)
                    target_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)

            for i in range(start, end):
                widget = None

                if search_mode == SearchMode.LYRICS:
                    track_data, snippet = mw.current_search_results[i]
                    artwork_data = track_data.get("artwork")
                    pixmap = self.manager.components.get_pixmap(artwork_data, 64)

                    widget = self.manager.components.create_lyrics_card(
                        track_data, snippet, pixmap, query
                    )

                    widget.playClicked.connect(mw.player_controller.play_specific_track)

                    if hasattr(widget, "contextMenuRequested"):
                        widget.contextMenuRequested.connect(
                            mw.action_handler.show_context_menu
                        )

                    if hasattr(widget, "lyricsClicked"):
                        widget.lyricsClicked.connect(mw.action_handler.show_lyrics)
                    target_layout.setSpacing(16)
                    target_layout.addWidget(widget)

                elif search_mode in [
                    SearchMode.EVERYWHERE,
                    SearchMode.FAVORITES,
                    SearchMode.TRACKS,
                ]:
                    album_key, tracks = mw.current_search_results[i]
                    album_data = mw.data_manager.albums_data.get(album_key)

                    if not album_data and tracks:
                        sample = tracks[0]
                        album_data = {
                            "album_artist": sample.get("album_artist", "Unknown"),
                            "artwork": sample.get("artwork"),
                            "year": sample.get("year"),
                        }

                    widget = self.manager.components._create_detailed_album_widget(
                        album_key, album_data, tracks_to_show=tracks, search_query=query
                    )
                    main_layout.addWidget(widget)

                    if i < len(mw.current_search_results) - 1:
                        separator = QWidget()
                        separator.setFixedHeight(1)
                        separator.setProperty("class", "separator")
                        main_layout.addWidget(separator)

                elif search_mode == SearchMode.PLAYLISTS:
                    playlist_path = mw.current_search_results[i]
                    widget = self._create_playlist_card_widget(playlist_path, query)
                    widget.activated.connect(self.show_search_playlist_tracks)

                    if widget:
                        if hasattr(widget, "playClicked"):
                            widget.playClicked.connect(
                                lambda d=playlist_path: mw.player_controller.play_data(
                                    d
                                )
                            )
                        widget.contextMenuRequested.connect(
                            mw.action_handler.show_context_menu
                        )
                        target_layout.addWidget(widget)

                else:
                    item_data, data_dict = mw.current_search_results[i]

                    if search_mode == SearchMode.ARTISTS:
                        widget = self.manager.components.create_artist_widget(
                            item_data,
                            data_dict,
                            mw.search_view_mode,
                            search_query=query,
                        )
                        widget.activated.connect(self.show_search_artist_albums)

                    elif search_mode == SearchMode.ALBUMS:
                        widget = self.manager.components.create_album_widget(
                            item_data,
                            data_dict,
                            mw.search_view_mode,
                            show_artist=True,
                            search_query=query,
                        )
                        widget.activated.connect(self.show_search_album_tracks)

                    elif search_mode == SearchMode.GENRES:
                        widget = self.manager.components.create_genre_widget(
                            item_data,
                            data_dict,
                            mw.search_view_mode,
                            search_query=query,
                        )
                        widget.activated.connect(self.show_search_genre_albums)

                    elif search_mode == SearchMode.COMPOSERS:
                        widget = self.manager.components.create_composer_widget(
                            item_data,
                            data_dict,
                            mw.search_view_mode,
                            search_query=query,
                        )
                        widget.activated.connect(self.show_search_composer_albums)

                    if widget:
                        if hasattr(widget, "playClicked"):
                            play_payload = item_data
                            if search_mode == SearchMode.COMPOSERS:
                                play_payload = {"type": "composer", "data": item_data}
                            elif search_mode == SearchMode.GENRES:
                                play_payload = {"type": "genre", "data": item_data}
                            elif search_mode == SearchMode.ARTISTS:
                                play_payload = {"type": "artist", "data": item_data}

                            widget.playClicked.connect(
                                lambda d=play_payload: mw.player_controller.play_data(d)
                            )

                        widget.contextMenuRequested.connect(
                            mw.action_handler.show_context_menu
                        )
                        target_layout.addWidget(widget)

            main_layout.addStretch(1)
            mw.search_loaded_count = end

        except Exception as e:
            print(f"Error loading search results: {e}")

        finally:
            mw.is_loading_search = False

    def _create_playlist_card_widget(self, path, query):
        """
        Helper method for creating a playlist card widget.

        Args:
            path (str): The file path of the playlist.
            query (str): The search query used to find the playlist.
        """
        mw = self.main_window
        name = os.path.splitext(os.path.basename(path))[0]
        meta = mw.library_manager.get_playlist_metadata(
            path, mw.data_manager.path_to_track_map
        )

        pixmap_size = 128 if mw.search_view_mode != ViewMode.TILE_SMALL else 48
        if meta.get("artwork"):
            pixmap = self.manager.components.get_pixmap(meta["artwork"], pixmap_size)
        else:
            pixmap = self.manager.components.playlist_pixmap.scaled(
                pixmap_size,
                pixmap_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        subtitle = translate("{count} track(s)", count=meta.get("count", 0))

        return CardWidget(
            data=path,
            view_mode=mw.search_view_mode,
            pixmaps=[pixmap],
            title=name,
            subtitle1=subtitle,
            icon_pixmap=self.manager.components.playlist_icon_pixmap,
            search_query=query,
        )

    def show_no_library_message_on_search_tab(self):
        """Displays the 'Library is empty' message."""
        mw = self.main_window
        container = mw.search_scroll.widget()
        if not container:
            return
        layout = container.layout()

        if getattr(mw, "is_processing_library", False):
            self.manager.components._show_loading_library_message(layout)
        else:
            self.manager.components._show_no_library_message(layout)

    def go_back_search(self):
        """Go back one level in the search stack."""
        mw = self.main_window
        current_index = mw.search_stack.currentIndex()

        if current_index > 0:
            layout_key = f"search_detail_layout_{current_index}"
            header_key = f"search_detail_header_layout_{current_index}"

            if hasattr(mw, layout_key):
                self.manager.clear_layout(getattr(mw, layout_key))
            if hasattr(mw, header_key):
                self.manager.clear_layout(getattr(mw, header_key))

            mw.search_stack.setCurrentIndex(current_index - 1)

    def _show_generic_entity_albums(
            self,
            entity_name,
            entity_type,
            data_dict,
            album_keys,
            sort_mode_attr,
            view_mode_attr,
            show_artist_in_card = False,
    ):
        """
        Universal method for displaying albums of an Artist, Genre, or Composer.

        Args:
            entity_name (str): The name of the entity (e.g., artist or genre name).
            entity_type (str): The type of the entity ('artist', 'genre', 'composer').
            data_dict (dict): The dictionary containing metadata for the entity.
            album_keys (list): A list of album keys associated with the entity.
            sort_mode_attr (str): The attribute name in the main window for the sort mode.
            view_mode_attr (str): The attribute name in the main window for the view mode.
            show_artist_in_card (bool, optional): Whether to display the artist's name on the card. Defaults to False.
        """
        mw = self.main_window

        self.manager.clear_layout(mw.search_detail_header_layout_1)
        self.manager.clear_layout(mw.search_detail_layout_1)

        albums_list = []
        for key in album_keys:
            t_key = tuple(key) if isinstance(key, list) else key
            if t_key in mw.data_manager.albums_data:
                albums_list.append((t_key, mw.data_manager.albums_data[t_key]))

        album_count = len(albums_list)
        track_count = data_dict.get("track_count", 0)
        details_text = f"{translate('{count} album(s)', count = album_count)}, {translate('{count} track(s)', count = track_count)}"

        sort_mode = getattr(mw, sort_mode_attr)
        sort_opts = [
            (
                translate("By year (newest first)"),
                "sort_date_desc.svg",
                SortMode.YEAR_DESC,
            ),
            (
                translate("By year (oldest first)"),
                "sort_date_asc.svg",
                SortMode.YEAR_ASC,
            ),
            (translate("Alphabetical (A-Z)"), "sort_alpha_asc.svg", SortMode.ALPHA_ASC),
            (
                translate("Alphabetical (Z-A)"),
                "sort_alpha_desc.svg",
                SortMode.ALPHA_DESC,
            ),
        ]
        real_sort_opts = []
        for txt, icon, mode in sort_opts:
            real_sort_opts.append(
                (
                    txt,
                    create_svg_icon(
                        f"assets/control/{icon}", theme.COLORS["PRIMARY"], QSize(24, 24)
                    ),
                    mode,
                )
            )

        sort_btn = self.manager.components.create_tool_button_with_menu(
            real_sort_opts, sort_mode
        )
        sort_btn.setFixedHeight(36)
        refresh_callback = getattr(self, f"show_search_{entity_type}_albums")
        sort_btn.menu().triggered.connect(
            lambda action: (
                setattr(mw, sort_mode_attr, action.data()),
                refresh_callback(entity_name),
            )
        )

        view_mode = getattr(mw, view_mode_attr)
        view_opts = [
            (translate("Grid"), "view_grid.svg", ViewMode.GRID),
            (translate("Tile"), "view_tile.svg", ViewMode.TILE_BIG),
            (translate("Small Tile"), "view_tile_small.svg", ViewMode.TILE_SMALL),
            (translate("All tracks"), "view_album_tracks.svg", ViewMode.ALL_TRACKS),
        ]
        real_view_opts = []
        for txt, icon, mode in view_opts:
            real_view_opts.append(
                (
                    txt,
                    create_svg_icon(
                        f"assets/control/{icon}", theme.COLORS["PRIMARY"], QSize(24, 24)
                    ),
                    mode,
                )
            )

        view_btn = self.manager.components.create_tool_button_with_menu(
            real_view_opts, view_mode
        )
        view_btn.setFixedHeight(36)
        view_btn.menu().triggered.connect(
            lambda action: (
                setattr(mw, view_mode_attr, action.data()),
                refresh_callback(entity_name),
            )
        )

        fav_btn = self.manager.components._create_favorite_button(
            entity_name, entity_type
        )

        play_data = {"type": entity_type, "data": entity_name}

        header_parts = self.manager.components.create_page_header(
            title = entity_name,
            details_text = details_text,
            back_slot = self.manager.navigate_back,
            control_widgets = [fav_btn, sort_btn, view_btn],
            play_slot_data = play_data,
            context_menu_data = (entity_name, entity_type),
        )
        if btn := header_parts.get("play_button"):
            btn.clicked.connect(lambda: mw.player_controller.play_data(play_data))
            mw.main_view_header_play_buttons[entity_name] = btn

        cover_btn = EntityCoverButton(
            entity_name = entity_name,
            entity_data = data_dict,
            albums_of_entity = albums_list,
            entity_type = entity_type,
            get_pixmap_func = self.manager.components.get_pixmap,
            main_window = mw
        )

        if entity_type == "artist":
            cover_btn.artworkChanged.connect(
                mw.action_handler.handle_artist_artwork_changed
            )
        elif entity_type == "genre":
            cover_btn.artworkChanged.connect(
                mw.action_handler.handle_genre_artwork_changed
            )
        elif entity_type == "composer":
            cover_btn.artworkChanged.connect(
                mw.action_handler.handle_composer_artwork_changed
            )

        header_parts["header"].layout().insertWidget(
            1, cover_btn, alignment = Qt.AlignmentFlag.AlignCenter
        )
        mw.search_detail_header_layout_1.addWidget(header_parts["header"])

        if sort_mode == SortMode.ALPHA_ASC:
            albums_list.sort(key = lambda x: mw.data_manager.get_sort_key(x[0][1]))
        elif sort_mode == SortMode.ALPHA_DESC:
            albums_list.sort(
                key = lambda x: mw.data_manager.get_sort_key(x[0][1]), reverse = True
            )
        elif sort_mode == SortMode.YEAR_ASC:
            albums_list.sort(
                key = lambda x: (
                    x[1].get("year", 9999),
                    mw.data_manager.get_sort_key(x[0][1]),
                )
            )
        elif sort_mode == SortMode.YEAR_DESC:
            albums_list.sort(
                key = lambda x: (
                    x[1].get("year", 0),
                    mw.data_manager.get_sort_key(x[0][1]),
                ),
                reverse = True,
            )

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setProperty("class", "backgroundPrimary")
        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)

        if view_mode == ViewMode.ALL_TRACKS:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(24)
            for i, (album_key, data) in enumerate(albums_list):
                widget = self.manager.components._create_detailed_album_widget(
                    album_key, data
                )
                layout.addWidget(widget)
                if i < len(albums_list) - 1:
                    sep = QWidget()
                    sep.setFixedHeight(1)
                    sep.setProperty("class", "separator")
                    layout.addWidget(sep)
            layout.addStretch(1)
        else:
            layout = FlowLayout(container, stretch_items = True)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(16)
            for album_key, data in albums_list:
                widget = self.manager.components.create_album_widget(
                    album_key, data, view_mode, show_artist = show_artist_in_card
                )
                widget.activated.connect(self.show_search_album_tracks)
                widget.contextMenuRequested.connect(mw.action_handler.show_context_menu)
                widget.playClicked.connect(mw.player_controller.play_data)
                layout.addWidget(widget)

        scroll_area.setWidget(container)
        mw.search_detail_layout_1.addWidget(scroll_area)
        mw.search_stack.setCurrentIndex(1)

        mw.update_current_view_state(
            main_tab_index = mw.global_search_page_index,
            context_data = {"context": entity_type, "data": entity_name}
        )
        self.manager.update_all_track_widgets()

    def show_search_album_tracks(self, album_key):
        """
        Displays the tracks for a selected album and navigates to its detail view.

        Args:
            album_key (tuple): The unique identifier tuple for the album.
        """
        mw = self.main_window
        if mw.search_stack.currentIndex() == 0:
            target_h_layout = mw.search_detail_header_layout_1
            target_c_layout = mw.search_detail_layout_1
            target_idx = 1
        else:
            target_h_layout = mw.search_detail_header_layout_2
            target_c_layout = mw.search_detail_layout_2
            target_idx = 2

        self.manager.clear_layout(target_h_layout)
        self.manager.clear_layout(target_c_layout)

        album_data = mw.data_manager.albums_data.get(album_key)
        if not album_data:
            return

        fav_btn = self.manager.components._create_favorite_button(album_key, "album")
        header_parts = self.manager.components.create_page_header(
            title = album_key[1],
            back_slot = self.manager.navigate_back,
            control_widgets = [fav_btn],
            play_slot_data = album_key,
            context_menu_data = (album_key, "album"),
        )
        if btn := header_parts.get("play_button"):
            btn.clicked.connect(lambda: mw.player_controller.play_data(album_key))
            mw.main_view_header_play_buttons[album_key] = btn

        target_h_layout.addWidget(header_parts["header"])

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setProperty("class", "backgroundPrimary")

        content_container = QWidget()
        content_container.setProperty("class", "backgroundPrimary")
        c_layout = QVBoxLayout(content_container)
        c_layout.setContentsMargins(0, 0, 0, 0)

        album_widget = self.manager.components._create_detailed_album_widget(
            album_key, album_data
        )
        album_widget.setContentsMargins(24, 24, 24, 24)
        c_layout.addWidget(album_widget)

        scroll_area.setWidget(content_container)
        target_c_layout.addWidget(scroll_area, 1)
        mw.search_stack.setCurrentIndex(target_idx)

        mw.update_current_view_state(
            main_tab_index = mw.global_search_page_index,
            context_data = {"context": "album", "data": album_key}
        )
        self.manager.update_all_track_widgets()

    def show_search_playlist_tracks(self, playlist_path):
        """
        Displays the tracks for a selected playlist and navigates to its detail view.

        Args:
            playlist_path (str): The file path of the playlist.
        """
        mw = self.main_window
        mw.current_search_context = "playlist"
        mw.current_search_context_data = playlist_path

        self.manager.clear_layout(mw.search_detail_header_layout_1)
        self.manager.clear_layout(mw.search_detail_layout_1)

        name = os.path.splitext(os.path.basename(playlist_path))[0]
        tracks = mw.library_manager.load_playlist(
            playlist_path, mw.data_manager.path_to_track_map
        )

        fav_btn = self.manager.components._create_favorite_button(
            playlist_path, "playlist"
        )
        header_parts = self.manager.components.create_page_header(
            name,
            details_text = translate("{count} track(s)", count = len(tracks)),
            back_slot = self.manager.navigate_back,
            control_widgets = [fav_btn],
            play_slot_data = playlist_path,
            context_menu_data = (playlist_path, "playlist"),
        )
        if btn := header_parts.get("play_button"):
            btn.clicked.connect(lambda: mw.player_controller.play_data(playlist_path))
            mw.main_view_header_play_buttons[playlist_path] = btn

        mw.search_detail_header_layout_1.addWidget(header_parts["header"])

        scroll_area = StyledScrollArea()
        scroll_area.setProperty("class", "backgroundPrimary")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        if tracks:
            pl_widget = self.manager.components._create_detailed_playlist_widget(
                playlist_path, name, tracks
            )
            pl_widget.setContentsMargins(24, 24, 24, 24)
            scroll_area.setWidget(pl_widget)
        else:
            lbl = QLabel(translate("Could not load tracks."))
            lbl.setProperty("class", "textColorPrimary")
            scroll_area.setWidget(lbl)

        mw.search_detail_layout_1.addWidget(scroll_area, 1)
        mw.search_stack.setCurrentIndex(1)

        mw.update_current_view_state(
            main_tab_index = mw.global_search_page_index,
            context_data = {"context": "playlist", "data": playlist_path}
        )
        self.manager.update_all_track_widgets()

    def show_search_artist_albums(self, artist_name):
        """
        Displays the albums associated with a specific artist.

        Args:
            artist_name (str): The name of the artist.
        """
        mw = self.main_window
        self._show_generic_entity_albums(
            entity_name=artist_name,
            entity_type="artist",
            data_dict=mw.data_manager.artists_data.get(artist_name, {}),
            album_keys=mw.data_manager.artists_data.get(artist_name, {}).get(
                "albums", []
            ),
            sort_mode_attr="artist_album_sort_mode",
            view_mode_attr="artist_album_view_mode",
            show_artist_in_card=False,
        )

    def show_search_genre_albums(self, genre_name):
        """
        Displays the albums associated with a specific genre.

        Args:
            genre_name (str): The name of the genre.
        """
        mw = self.main_window
        self._show_generic_entity_albums(
            entity_name=genre_name,
            entity_type="genre",
            data_dict=mw.data_manager.genres_data.get(genre_name, {}),
            album_keys=mw.data_manager.genres_data.get(genre_name, {}).get(
                "albums", []
            ),
            sort_mode_attr="artist_album_sort_mode",
            view_mode_attr="artist_album_view_mode",
            show_artist_in_card=True,
        )

    def show_search_composer_albums(self, composer_name):
        """
        Displays the albums associated with a specific composer.

        Args:
            composer_name (str): The name of the composer.
        """
        mw = self.main_window
        self._show_generic_entity_albums(
            entity_name=composer_name,
            entity_type="composer",
            data_dict=mw.data_manager.composers_data.get(composer_name, {}),
            album_keys=mw.data_manager.composers_data.get(composer_name, {}).get(
                "albums", []
            ),
            sort_mode_attr="composer_album_sort_mode",
            view_mode_attr="composer_album_view_mode",
            show_artist_in_card=True,
        )

    def update_search_controls(self):
        """Updates the visibility of buttons in the search header."""
        mw = self.main_window
        show_action = mw.search_mode in [
            SearchMode.EVERYWHERE,
            SearchMode.FAVORITES,
            SearchMode.TRACKS,
        ] and bool(mw.current_search_results)

        show_view = mw.search_mode not in [
            SearchMode.EVERYWHERE,
            SearchMode.FAVORITES,
            SearchMode.TRACKS,
            SearchMode.LYRICS,
        ] and bool(mw.current_search_results)

        if hasattr(mw, "search_actions_container"):
            mw.search_actions_container.setVisible(show_action)
            if show_action and not hasattr(mw, "search_play_button"):
                self._init_search_action_buttons()

        if hasattr(mw, "search_view_button"):
            mw.search_view_button.setVisible(show_view)

    def _init_search_action_buttons(self):
        """Creates Play/Shuffle buttons for search results."""
        mw = self.main_window
        play_data = {"type": "search_results"}

        mw.search_play_button = QPushButton()
        mw.search_play_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            mw.search_play_button,
            title = translate("Play all"),
        )
        mw.search_play_button.setIcon(
            create_svg_icon(
                "assets/control/play_outline.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        mw.search_play_button.setIconSize(QSize(24, 24))
        mw.search_play_button.setProperty("class", "btnTool")
        mw.search_play_button.clicked.connect(
            lambda: mw.player_controller.play_data(play_data)
        )
        apply_button_opacity_effect(mw.search_play_button)
        mw.search_actions_layout.addWidget(mw.search_play_button)

        mw.search_shake_button = QPushButton()
        mw.search_shake_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            mw.search_shake_button,
            title = translate("Shake and Play"),
            text = translate("This action will mix all tracks and add them to the playback queue in a random order"),
        )
        mw.search_shake_button.setIcon(
            create_svg_icon(
                "assets/control/shake_queue.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        mw.search_shake_button.setIconSize(QSize(24, 24))
        mw.search_shake_button.setProperty("class", "btnTool")
        mw.search_shake_button.clicked.connect(
            lambda: mw.player_controller.play_data_shuffled(play_data)
        )
        apply_button_opacity_effect(mw.search_shake_button)
        mw.search_actions_layout.addWidget(mw.search_shake_button)

    def update_search_view_options(self):
        """Updates the view button menu (Grid/Tile/List)."""
        mw = self.main_window
        menu = mw.search_view_button.menu()
        menu.clear()

        if mw.search_mode in [
            SearchMode.EVERYWHERE,
            SearchMode.FAVORITES,
            SearchMode.TRACKS,
        ]:
            opts = [
                (translate("All tracks"), "view_album_tracks.svg", ViewMode.ALL_TRACKS)
            ]
            if mw.search_view_mode != ViewMode.ALL_TRACKS:
                mw.search_view_mode = ViewMode.ALL_TRACKS
        else:
            opts = [
                (translate("Grid"), "view_grid.svg", ViewMode.GRID),
                (translate("Tile"), "view_tile.svg", ViewMode.TILE_BIG),
                (translate("Small Tile"), "view_tile_small.svg", ViewMode.TILE_SMALL),
            ]
            if mw.search_view_mode == ViewMode.ALL_TRACKS:
                mw.search_view_mode = ViewMode.GRID

        for txt, icon, mode in opts:
            action = QAction(
                create_svg_icon(
                    f"assets/control/{icon}", theme.COLORS["PRIMARY"], QSize(24, 24)
                ),
                txt,
                mw.search_view_button,
            )
            action.setData(mode)
            menu.addAction(action)

        self.manager.components.update_tool_button_icon(
            mw.search_view_button, mw.search_view_mode
        )