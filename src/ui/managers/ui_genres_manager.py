"""
Vinyller — Genres UI manager
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

from PyQt6.QtCore import QObject, QSize, Qt, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QWidget
)

from src.ui.custom_base_widgets import StyledScrollArea, set_custom_tooltip
from src.ui.custom_classes import (
    FlowLayout, SortMode,
    ViewMode, EntityCoverButton
)
from src.utils import theme
from src.utils.constants import (
    BATCH_SIZE, BATCH_SIZE_ALLTRACKS
)
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


class GenresUIManager(QObject):
    """
    Class managing the Genres tab UI logic.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the GenresUIManager.
        """
        super().__init__()
        self.main_window = main_window
        self.ui_manager = ui_manager

        self.genre_separator_widgets = {}
        self.genre_album_separator_widgets = {}

    def populate_genres_tab(self, initial_load_count=None):
        """
        Populates the main genres tab with the library's genres.

        Args:
            initial_load_count (int, optional): The initial number of items to load
                (currently unused in the implementation).
        """
        mw = self.main_window
        mw.last_genre_letter, mw.current_genre_flow_layout = None, None
        self.genre_separator_widgets.clear()

        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        mw.genres_scroll.setWidget(container)

        source_list = mw.data_manager.sorted_genres

        if mw.show_random_suggestions and len(source_list) >= 20:
            suggestion_block = self.ui_manager.components.create_suggestion_block(
                "genre", self.populate_genres_tab
            )
            if suggestion_block:
                layout.addWidget(suggestion_block)

        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            mw.genre_sort_button.hide()
            mw.genre_view_button.hide()
            self.ui_manager.set_header_visibility(mw.genres_header, False)
            self.ui_manager.components._show_loading_library_message(layout)
            return

        if mw.data_manager.is_empty():
            mw.genre_sort_button.hide()
            mw.genre_view_button.hide()
            self.ui_manager.set_header_visibility(mw.genres_header, False)
            self.ui_manager.components._show_no_library_message(layout)
            return
        elif not mw.data_manager.genres_data:
            mw.genre_sort_button.hide()
            mw.genre_view_button.hide()
            self.ui_manager.set_header_visibility(mw.genres_header, False)
            self.ui_manager.components._show_no_metadata_results_message(
                layout, "genres"
            )
            return
        else:
            mw.genre_sort_button.show()
            mw.genre_view_button.show()
            self.ui_manager.set_header_visibility(mw.genres_header, True)

        count = len(source_list)
        mw.genres_header["details"].setText(translate("{count} genre(s)", count=count))
        mw.genres_header["details"].show()

        mw.current_genres_display_list = source_list

        mw.genre_letters = set()
        if mw.show_separators:
            for genre, _ in mw.current_genres_display_list:
                sort_name = mw.data_manager.get_sort_key(genre)
                first_char = sort_name[0] if sort_name else "#"
                current_letter = first_char.upper() if first_char.isalpha() else "*"
                mw.genre_letters.add(current_letter)

        sort_key_func = lambda x: mw.data_manager.get_sort_key(x[0])
        mw.current_genres_display_list.sort(
            key=sort_key_func, reverse=(mw.genre_sort_mode == SortMode.ALPHA_DESC)
        )

        mw.genres_loaded_count = 0

        if mw.genres_loaded_count < len(mw.current_genres_display_list):
            self.load_more_genres()
        layout.addStretch(1)

    def load_more_genres(self):
        """
        Loads the next batch of genres in the grid/list.
        """
        mw = self.main_window
        if not mw.genres_scroll.widget():
            return
        if mw.is_loading_genres:
            return
        genres_list = mw.current_genres_display_list
        if mw.genres_loaded_count >= len(genres_list):
            return
        mw.is_loading_genres = True
        start, end = mw.genres_loaded_count, min(
            mw.genres_loaded_count + BATCH_SIZE, len(genres_list)
        )
        main_layout = mw.genres_scroll.widget().layout()

        stretch_item = None
        if main_layout.count() > 0:
            last_item = main_layout.itemAt(main_layout.count() - 1)
            if last_item and last_item.spacerItem():
                stretch_item = main_layout.takeAt(main_layout.count() - 1)

        for i in range(start, end):
            genre, data = genres_list[i]

            if mw.show_separators:
                sort_name = mw.data_manager.get_sort_key(genre)
                first_char = sort_name[0] if sort_name else "#"
                current_letter = first_char.upper() if first_char.isalpha() else "*"
                if current_letter != mw.last_genre_letter:
                    separator_widget = self.ui_manager.components._create_separator_widget(
                        current_letter, "genres", mw.genre_letters
                    )
                    main_layout.addWidget(separator_widget)
                    self.genre_separator_widgets[current_letter] = separator_widget
                    mw.last_genre_letter = current_letter
                    mw.current_genre_flow_layout = None

            target_layout = main_layout
            if mw.genre_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_genre_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_genre_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_genre_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_genre_flow_layout

            widget = self.ui_manager.components.create_genre_widget(
                genre, data, mw.genre_view_mode
            )
            widget.activated.connect(self.show_genre_albums)

            widget.contextMenuRequested.connect(
                lambda data, pos: mw.action_handler.show_context_menu(
                    data, pos, context={"forced_type": "genre"}
                )
            )

            widget.playClicked.connect(
                lambda d: mw.player_controller.smart_play({"type": "genre", "data": d})
            )
            target_layout.addWidget(widget)

        if stretch_item:
            main_layout.addItem(stretch_item)

        mw.genres_loaded_count = end
        mw.is_loading_genres = False

        QTimer.singleShot(100, self._check_for_more_genres)

    def _check_for_more_genres(self):
        """
        Checks if more genres should be loaded to fill the view.
        """
        mw = self.main_window
        if not mw.genres_scroll.widget():
            return
        scroll_bar = mw.genres_scroll.verticalScrollBar()
        has_more_data = mw.genres_loaded_count < len(mw.current_genres_display_list)
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_genres()

    def show_genre_albums(self, genre_name):
        """
        Displays the detailed view of albums belonging to a specific genre.

        Args:
            genre_name (str): The name of the genre to display albums for.
        """
        mw = self.main_window
        mw.current_genre_view = genre_name

        self.ui_manager.clear_layout(mw.genre_albums_header_layout)
        self.ui_manager.clear_layout(mw.genre_albums_layout)

        album_keys = mw.data_manager.genres_data.get(genre_name, {}).get(
            "albums", set()
        )
        albums_of_genre = [
            (key, mw.data_manager.albums_data[key])
            for key in album_keys
            if key in mw.data_manager.albums_data
        ]

        sort_year_desc = create_svg_icon(
            "assets/control/sort_date_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_year_asc = create_svg_icon(
            "assets/control/sort_date_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )

        sort_options = [
            (translate("By year (newest first)"), sort_year_desc, SortMode.YEAR_DESC),
            (translate("By year (oldest first)"), sort_year_asc, SortMode.YEAR_ASC),
            (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
            (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
        ]
        sort_button = self.ui_manager.components.create_tool_button_with_menu(
            sort_options, mw.artist_album_sort_mode
        )
        sort_button.setFixedHeight(36)
        sort_button.menu().triggered.connect(
            lambda action: self.sort_and_reshow_genre_albums(action.data())
        )
        set_custom_tooltip(
            sort_button,
            title = translate("Sort Options"),
        )
        view_grid = create_svg_icon(
            "assets/control/view_grid.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        view_tile = create_svg_icon(
            "assets/control/view_tile.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        view_tile_small = create_svg_icon(
            "assets/control/view_tile_small.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        view_album_tracks = create_svg_icon(
            "assets/control/view_album_tracks.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )

        view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
            (translate("All tracks"), view_album_tracks, ViewMode.ALL_TRACKS),
        ]
        view_button = self.ui_manager.components.create_tool_button_with_menu(
            view_options, mw.artist_album_view_mode
        )
        view_button.setFixedHeight(36)
        view_button.menu().triggered.connect(mw.set_genre_album_view_mode)
        set_custom_tooltip(
            view_button,
            title = translate("View Options"),
        )
        fav_button = self.ui_manager.components._create_favorite_button(genre_name, "genre")

        album_count = len(albums_of_genre)
        track_count = mw.data_manager.genres_data.get(genre_name, {}).get(
            "track_count", 0
        )
        albums_text = translate("{count} album(s)", count=album_count)
        tracks_text = translate("{count} track(s)", count=track_count)
        details_text = f"{albums_text}, {tracks_text}"

        header_parts = self.ui_manager.components.create_page_header(
            title=genre_name,
            details_text=details_text,
            back_slot=self.ui_manager.navigate_back,
            control_widgets=[fav_button, sort_button, view_button],
            play_slot_data={"type": "genre", "data": genre_name},
            context_menu_data=(genre_name, "genre"),
        )
        if play_button := header_parts.get("play_button"):
            play_button.clicked.connect(
                lambda: mw.player_controller.play_data(
                    {"type": "genre", "data": genre_name}
                )
            )
            mw.main_view_header_play_buttons[genre_name] = play_button

        genre_cover_button = EntityCoverButton(
            genre_name,
            mw.data_manager.genres_data.get(genre_name, {}),
            albums_of_genre,
            "genre",
            self.ui_manager.components.get_pixmap,
            main_window=mw,
        )
        genre_cover_button.artworkChanged.connect(
            mw.action_handler.handle_genre_artwork_changed
        )
        header_parts["header"].layout().insertWidget(
            1, genre_cover_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        mw.genre_albums_header_layout.addWidget(header_parts["header"])

        sort_mode = mw.artist_album_sort_mode
        if sort_mode == SortMode.ALPHA_ASC:
            albums_of_genre.sort(key=lambda x: mw.data_manager.get_sort_key(x[0][1]))
        elif sort_mode == SortMode.ALPHA_DESC:
            albums_of_genre.sort(
                key=lambda x: mw.data_manager.get_sort_key(x[0][1]), reverse=True
            )
        elif sort_mode == SortMode.YEAR_ASC:
            albums_of_genre.sort(
                key=lambda x: (
                    x[1].get("year", 9999),
                    mw.data_manager.get_sort_key(x[0][1]),
                )
            )
        elif sort_mode == SortMode.YEAR_DESC:
            albums_of_genre.sort(
                key=lambda x: (
                    x[1].get("year", 0),
                    mw.data_manager.get_sort_key(x[0][1]),
                ),
                reverse=True,
            )

        mw.genre_albums_scroll = StyledScrollArea()
        mw.genre_albums_scroll.setWidgetResizable(True)
        mw.genre_albums_scroll.setProperty("class", "backgroundPrimary")

        scroll_bar = mw.genre_albums_scroll.verticalScrollBar()

        if mw.artist_album_view_mode == ViewMode.ALL_TRACKS:
            self._populate_genre_all_tracks_view(
                mw.genre_albums_scroll, albums_of_genre
            )
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_genre_all_tracks
                )
            )
        else:
            self._populate_genre_albums_standard_view(
                mw.genre_albums_scroll, albums_of_genre
            )
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_genre_albums
                )
            )

        mw.genre_albums_layout.addWidget(mw.genre_albums_scroll)
        mw.genres_stack.setCurrentIndex(1)

        context = {"genre_name": genre_name}
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("genre"), context_data=context
        )
        self.ui_manager.update_all_track_widgets()

    def _populate_genre_albums_standard_view(self, scroll_area, albums_of_genre):
        """
        Populates the standard album list view for a genre.

        Args:
            scroll_area (StyledScrollArea): The scroll area widget containing the view.
            albums_of_genre (list): A list of tuples containing album keys and their data.
        """
        mw = self.main_window
        mw.current_genre_albums_list = albums_of_genre
        mw.genre_albums_loaded_count = 0
        mw.is_loading_genre_albums = False

        mw.last_genre_album_group = None
        mw.current_genre_album_flow_layout = None
        self.genre_album_separator_widgets.clear()

        root_container = QWidget()
        root_container.setContentsMargins(24, 24, 24, 24)
        root_container.setProperty("class", "backgroundPrimary")
        root_layout = QVBoxLayout(root_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(24)

        self.ui_manager.inject_encyclopedia_section(
            root_layout,
            mw.current_genre_view,
            "genre",
            lambda: self.show_genre_albums(mw.current_genre_view),
        )

        albums_container = QWidget()
        albums_container.setContentsMargins(0, 0, 0, 0)

        albums_layout = QVBoxLayout(albums_container)
        albums_layout.setContentsMargins(0, 0, 0, 0)
        albums_layout.setSpacing(16)

        root_layout.addWidget(albums_container)
        root_layout.addStretch(1)

        mw.active_genre_albums_layout_target = albums_layout

        mw.genre_album_groups = set()
        if mw.show_separators and len(mw.current_genre_albums_list) > 20:
            for album_key, data in mw.current_genre_albums_list:
                current_group = None
                if mw.artist_album_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    album_title = mw.data_manager.get_sort_key(album_key[1])
                    first_char = album_title[0] if album_title else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.artist_album_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                    album_year = data.get("year")
                    if album_year is None or album_year == 0:
                        current_group = "#"
                    else:
                        current_group = str(album_year)

                if current_group:
                    mw.genre_album_groups.add(current_group)

        scroll_area.setWidget(root_container)
        self.load_more_genre_albums()

    def load_more_genre_albums(self):
        """
        Loads the next batch of albums for the currently displayed genre.
        """
        mw = self.main_window
        if (
                not hasattr(mw, "active_genre_albums_layout_target")
                or mw.active_genre_albums_layout_target is None
        ):
            return
        if (
                not hasattr(mw, "genre_albums_scroll")
                or not mw.genre_albums_scroll
                or not mw.genre_albums_scroll.widget()
        ):
            return
        if getattr(mw, "is_loading_genre_albums", False):
            return
        if not hasattr(
                mw, "current_genre_albums_list"
        ) or mw.genre_albums_loaded_count >= len(mw.current_genre_albums_list):
            return

        mw.is_loading_genre_albums = True

        start = mw.genre_albums_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_genre_albums_list))

        main_layout = mw.active_genre_albums_layout_target

        for i in range(start, end):
            album_key, data = mw.current_genre_albums_list[i]
            current_group = None

            if mw.show_separators and len(mw.current_genre_albums_list) > 20:
                if mw.artist_album_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    album_title = mw.data_manager.get_sort_key(album_key[1])
                    first_char = album_title[0] if album_title else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.artist_album_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                    album_year = data.get("year")
                    if album_year is None or album_year == 0:
                        current_group = "#"
                    else:
                        current_group = str(album_year)

                if current_group and current_group != mw.last_genre_album_group:
                    separator_widget = self.ui_manager.components._create_separator_widget(
                        current_group, "genre_albums", mw.genre_album_groups
                    )
                    main_layout.addWidget(separator_widget)
                    self.genre_album_separator_widgets[current_group] = separator_widget
                    mw.last_genre_album_group = current_group
                    mw.current_genre_album_flow_layout = None

            target_layout = main_layout
            if mw.artist_album_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if getattr(mw, "current_genre_album_flow_layout", None) is None:
                    flow_container = QWidget()
                    mw.current_genre_album_flow_layout = FlowLayout(
                        flow_container, stretch_items = True
                    )
                    mw.current_genre_album_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_genre_album_flow_layout

            widget = self.ui_manager.components.create_album_widget(
                album_key, data, mw.artist_album_view_mode, show_artist = True
            )
            widget.activated.connect(
                partial(self.ui_manager.show_album_tracks, source_stack = mw.genres_stack)
            )
            widget.contextMenuRequested.connect(
                lambda data, pos: mw.action_handler.show_context_menu(
                    data, pos, context = {"forced_type": "album"}
                )
            )
            widget.playClicked.connect(mw.player_controller.smart_play)

            try:
                target_layout.addWidget(widget)
            except RuntimeError:
                mw.is_loading_genre_albums = False
                return

        mw.genre_albums_loaded_count = end
        mw.is_loading_genre_albums = False
        QTimer.singleShot(100, self._check_for_more_genre_albums)

    def _check_for_more_genre_albums(self):
        """
        Checks if more albums should be loaded for the currently displayed genre.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "genre_albums_scroll")
            or not mw.genre_albums_scroll.widget()
        ):
            return
        scroll_bar = mw.genre_albums_scroll.verticalScrollBar()
        has_more_data = mw.genre_albums_loaded_count < len(mw.current_genre_albums_list)
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_genre_albums()

    def _populate_genre_all_tracks_view(self, scroll_area, albums_of_genre):
        """
        Populates a flat list view of all tracks by a specific genre.

        Args:
            scroll_area (StyledScrollArea): The scroll area widget containing the view.
            albums_of_genre (list): A list of tuples containing album keys and their data.
        """
        mw = self.main_window
        mw.current_genre_all_tracks_list = albums_of_genre
        mw.genre_all_tracks_loaded_count = 0
        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(24)

        self.ui_manager.inject_encyclopedia_section(
            main_layout,
            mw.current_genre_view,
            "genre",
            lambda: self.show_genre_albums(mw.current_genre_view),
        )

        scroll_area.setWidget(container)
        self.load_more_genre_all_tracks()

    def load_more_genre_all_tracks(self):
        """
        Loads the next batch of tracks in the all-tracks genre view.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "genre_albums_scroll")
            or not mw.genre_albums_scroll
            or not mw.genre_albums_scroll.widget()
        ):
            return
        if getattr(mw, "is_loading_genre_all_tracks", False):
            return
        if not hasattr(
            mw, "current_genre_all_tracks_list"
        ) or mw.genre_all_tracks_loaded_count >= len(mw.current_genre_all_tracks_list):
            return

        mw.is_loading_genre_all_tracks = True
        start = mw.genre_all_tracks_loaded_count
        end = min(start + BATCH_SIZE_ALLTRACKS, len(mw.current_genre_all_tracks_list))
        main_layout = mw.genre_albums_scroll.widget().layout()

        if (
            main_layout.count() > 0
            and (
                stretch_item := main_layout.itemAt(main_layout.count() - 1)
            ).spacerItem()
        ):
            main_layout.takeAt(main_layout.count() - 1)

        for i in range(start, end):
            album_key, data = mw.current_genre_all_tracks_list[i]
            album_widget = self.ui_manager.components._create_detailed_album_widget(
                album_key, data, tracks_to_show=None
            )
            main_layout.addWidget(album_widget)
            if i < len(mw.current_genre_all_tracks_list) - 1:
                separator = QWidget()
                separator.setFixedHeight(1)
                separator.setProperty("class", "separator")
                main_layout.addWidget(separator)

        main_layout.addStretch(1)
        mw.genre_all_tracks_loaded_count = end
        mw.is_loading_genre_all_tracks = False
        self.ui_manager.update_all_track_widgets()

        QTimer.singleShot(100, self._check_for_more_genre_all_tracks)

    def _check_for_more_genre_all_tracks(self):
        """
        Checks if more tracks should be loaded in the all-tracks genre view.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "genre_albums_scroll")
            or not mw.genre_albums_scroll.widget()
        ):
            return
        scroll_bar = mw.genre_albums_scroll.verticalScrollBar()
        has_more_data = mw.genre_all_tracks_loaded_count < len(
            mw.current_genre_all_tracks_list
        )
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_genre_all_tracks()

    def sort_and_reshow_genre_albums(self, mode_id):
        """
        Re-sorts and refreshes the currently displayed genre's albums.

        Args:
            mode_id (SortMode): The sort mode identifier to apply.
        """
        mw = self.main_window
        mw.artist_album_sort_mode = mode_id
        if mw.current_genre_view:
            self.show_genre_albums(mw.current_genre_view)

    def navigate_to_genre(self, genre_name):
        """
        Jumps directly to the specified genre's detailed view.

        Args:
            genre_name (str): The name of the genre to navigate to.
        """
        mw = self.main_window

        canonical_genre_name = None
        if mw.ignore_genre_case:
            for key in mw.data_manager.genres_data.keys():
                if key.lower() == genre_name.lower():
                    canonical_genre_name = key
                    break
        else:
            if genre_name in mw.data_manager.genres_data:
                canonical_genre_name = genre_name

        if canonical_genre_name:
            genre_tab_index = mw.nav_button_icon_names.index("genre")
            mw.main_stack.setCurrentIndex(genre_tab_index)
            mw.nav_buttons[genre_tab_index].setChecked(True)
            self.ui_manager.update_nav_button_icons()
            self.show_genre_albums(canonical_genre_name)