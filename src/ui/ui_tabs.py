"""
Vinyller — Main tabs manager
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

from PyQt6.QtCore import (
    QSize, Qt
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget
)

from src.ui.custom_base_widgets import (
    StyledScrollArea, set_custom_tooltip
)
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    SearchMode, SortMode,
    ViewMode
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


class TabFactory:
    """
    A factory class responsible for creating the main content tabs (pages)
    for the application's UI. This helps to de-clutter the main UI class.

    Each tab creation method now returns a container holding TWO QStackedWidgets:
    1. self.ui.*_header_stack (for headers)
    2. self.ui.*_stack (for content)
    These are synced via signals.
    """

    def __init__(self, ui_instance):
        """
        Initializes the TabFactory with a reference to the main UI instance.
        """
        self.ui = ui_instance

    def _create_split_stack_container(self, name_prefix):
        """
        Helper to create a container with a Header Stack and a Content Stack.
        Also sets up synchronization between them.
        Returns: (container, header_stack, content_stack)
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_stack = QStackedWidget()
        content_stack = QStackedWidget()

        content_stack.currentChanged.connect(header_stack.setCurrentIndex)

        layout.addWidget(header_stack)
        layout.addWidget(content_stack)

        return container, header_stack, content_stack

    def create_artists_tab(self):
        """Creates the entire 'Artists' tab widget and its sub-pages."""
        container, self.ui.artists_header_stack, self.ui.artists_stack = (
            self._create_split_stack_container("artists")
        )

        all_artists_header_widget = QWidget()
        _h_layout = QVBoxLayout(all_artists_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_date_added_desc = create_svg_icon(
            "assets/control/sort_date_added_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_date_added_asc = create_svg_icon(
            "assets/control/sort_date_added_asc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )

        artist_sort_options = [
            (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
            (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            (
                translate("By date added (newest first)"),
                sort_date_added_desc,
                SortMode.DATE_ADDED_DESC,
            ),
            (
                translate("By date added (oldest first)"),
                sort_date_added_asc,
                SortMode.DATE_ADDED_ASC,
            ),
        ]
        self.ui.artist_sort_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                artist_sort_options, self.ui.artist_sort_mode
            )
        )
        set_custom_tooltip(
            self.ui.artist_sort_button,
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
        artist_view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]
        self.ui.artist_view_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                artist_view_options, self.ui.artist_view_mode
            )
        )
        set_custom_tooltip(
            self.ui.artist_view_button,
            title = translate("View Options"),
        )

        artists_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("All artists"),
            control_widgets=[self.ui.artist_sort_button, self.ui.artist_view_button],
        )
        self.ui.artists_header = artists_header_parts
        _h_layout.addWidget(self.ui.artists_header["header"])
        self.ui.artists_header_stack.addWidget(all_artists_header_widget)

        self.ui.artists_scroll = StyledScrollArea()
        self.ui.artists_scroll.setProperty("class", "backgroundPrimary")
        self.ui.artists_scroll.setWidgetResizable(True)
        self.ui.artists_stack.addWidget(self.ui.artists_scroll)

        artist_albums_header_page = QWidget()
        self.ui.artist_albums_header_layout = QVBoxLayout(artist_albums_header_page)
        self.ui.artist_albums_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.artist_albums_header_layout.setSpacing(0)
        self.ui.artists_header_stack.addWidget(artist_albums_header_page)

        artist_albums_page = QWidget()
        self.ui.artist_albums_layout = QVBoxLayout(artist_albums_page)
        self.ui.artist_albums_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.artist_albums_layout.setSpacing(0)
        self.ui.artists_stack.addWidget(artist_albums_page)

        artist_album_tracks_header_page = QWidget()
        self.ui.artist_album_tracks_header_layout = QVBoxLayout(
            artist_album_tracks_header_page
        )
        self.ui.artist_album_tracks_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.artist_album_tracks_header_layout.setSpacing(0)
        self.ui.artists_header_stack.addWidget(artist_album_tracks_header_page)

        artist_album_tracks_page = QWidget()
        self.ui.artist_album_tracks_layout = QVBoxLayout(artist_album_tracks_page)
        self.ui.artist_album_tracks_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.artist_album_tracks_layout.setSpacing(0)
        self.ui.artists_stack.addWidget(artist_album_tracks_page)

        return container

    def create_composers_tab(self):
        """Creates the entire 'Composers' tab widget and its sub-pages."""
        container, self.ui.composers_header_stack, self.ui.composers_stack = (
            self._create_split_stack_container("composers")
        )

        all_composers_header_widget = QWidget()
        _h_layout = QVBoxLayout(all_composers_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_date_added_desc = create_svg_icon(
            "assets/control/sort_date_added_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_date_added_asc = create_svg_icon(
            "assets/control/sort_date_added_asc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )

        composer_sort_options = [
            (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
            (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            (
                translate("By date added (newest first)"),
                sort_date_added_desc,
                SortMode.DATE_ADDED_DESC,
            ),
            (
                translate("By date added (oldest first)"),
                sort_date_added_asc,
                SortMode.DATE_ADDED_ASC,
            ),
        ]

        self.ui.composer_sort_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                composer_sort_options, self.ui.composer_sort_mode
            )
        )
        set_custom_tooltip(
            self.ui.composer_sort_button,
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

        composer_view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]

        self.ui.composer_view_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                composer_view_options, self.ui.composer_view_mode
            )
        )
        set_custom_tooltip(
            self.ui.composer_view_button,
            title = translate("View Options"),
        )

        composers_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("Composers"),
            control_widgets=[
                self.ui.composer_sort_button,
                self.ui.composer_view_button,
            ],
        )
        self.ui.composers_header = composers_header_parts
        _h_layout.addWidget(self.ui.composers_header["header"])
        self.ui.composers_header_stack.addWidget(all_composers_header_widget)

        self.ui.composers_scroll = StyledScrollArea()
        self.ui.composers_scroll.setProperty("class", "backgroundPrimary")
        self.ui.composers_scroll.setWidgetResizable(True)
        self.ui.composers_stack.addWidget(self.ui.composers_scroll)

        composer_albums_header_page = QWidget()
        self.ui.composer_albums_header_layout = QVBoxLayout(composer_albums_header_page)
        self.ui.composer_albums_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.composer_albums_header_layout.setSpacing(0)
        self.ui.composers_header_stack.addWidget(composer_albums_header_page)

        composer_albums_page = QWidget()
        self.ui.composer_albums_layout = QVBoxLayout(composer_albums_page)
        self.ui.composer_albums_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.composer_albums_layout.setSpacing(0)
        self.ui.composers_stack.addWidget(composer_albums_page)

        composer_album_tracks_header_page = QWidget()
        self.ui.composer_album_tracks_header_layout = QVBoxLayout(
            composer_album_tracks_header_page
        )
        self.ui.composer_album_tracks_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.composer_album_tracks_header_layout.setSpacing(0)
        self.ui.composers_header_stack.addWidget(composer_album_tracks_header_page)

        composer_album_tracks_page = QWidget()
        self.ui.composer_album_tracks_layout = QVBoxLayout(composer_album_tracks_page)
        self.ui.composer_album_tracks_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.composer_album_tracks_layout.setSpacing(0)
        self.ui.composers_stack.addWidget(composer_album_tracks_page)

        return container

    def create_albums_tab(self):
        """Creates the entire 'Albums' tab widget and its sub-pages."""
        container, self.ui.albums_header_stack, self.ui.albums_stack = (
            self._create_split_stack_container("albums")
        )

        all_albums_header_widget = QWidget()
        _h_layout = QVBoxLayout(all_albums_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_year_desc = create_svg_icon(
            "assets/control/sort_date_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_year_asc = create_svg_icon(
            "assets/control/sort_date_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_date_added_desc = create_svg_icon(
            "assets/control/sort_date_added_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_date_added_asc = create_svg_icon(
            "assets/control/sort_date_added_asc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )

        album_sort_options = [
            (translate("By year (newest first)"), sort_year_desc, SortMode.YEAR_DESC),
            (translate("By year (oldest first)"), sort_year_asc, SortMode.YEAR_ASC),
            (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
            (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            (
                translate("By date added (newest first)"),
                sort_date_added_desc,
                SortMode.DATE_ADDED_DESC,
            ),
            (
                translate("By date added (oldest first)"),
                sort_date_added_asc,
                SortMode.DATE_ADDED_ASC,
            ),
        ]
        self.ui.album_sort_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                album_sort_options, self.ui.album_sort_mode
            )
        )
        set_custom_tooltip(
            self.ui.album_sort_button,
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
        album_view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]
        self.ui.album_view_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                album_view_options, self.ui.album_view_mode
            )
        )
        set_custom_tooltip(
            self.ui.album_view_button,
            title = translate("View Options"),
        )

        albums_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("All albums"),
            control_widgets=[self.ui.album_sort_button, self.ui.album_view_button],
        )
        self.ui.albums_header = albums_header_parts
        _h_layout.addWidget(self.ui.albums_header["header"])
        self.ui.albums_header_stack.addWidget(all_albums_header_widget)

        self.ui.albums_scroll = StyledScrollArea()
        self.ui.albums_scroll.setProperty("class", "backgroundPrimary")
        self.ui.albums_scroll.setWidgetResizable(True)
        self.ui.albums_stack.addWidget(self.ui.albums_scroll)

        album_tracks_header_page = QWidget()
        self.ui.album_tracks_header_layout = QVBoxLayout(album_tracks_header_page)
        self.ui.album_tracks_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.album_tracks_header_layout.setSpacing(0)
        self.ui.albums_header_stack.addWidget(album_tracks_header_page)

        album_tracks_page = QWidget()
        self.ui.album_tracks_layout = QVBoxLayout(album_tracks_page)
        self.ui.album_tracks_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.album_tracks_layout.setSpacing(0)
        self.ui.albums_stack.addWidget(album_tracks_page)

        return container

    def create_songs_tab(self):
        """Creates the 'All tracks' tab widget."""
        container, songs_header_stack, songs_stack = self._create_split_stack_container(
            "songs"
        )

        songs_header_widget = QWidget()
        _h_layout = QVBoxLayout(songs_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        sort_artist_alpha_asc = create_svg_icon(
            "assets/control/sort_artist_alpha_asc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_artist_alpha_desc = create_svg_icon(
            "assets/control/sort_artist_alpha_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_album_alpha_asc = create_svg_icon(
            "assets/control/sort_album_alpha_asc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_album_alpha_desc = create_svg_icon(
            "assets/control/sort_album_alpha_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_year_asc = create_svg_icon(
            "assets/control/sort_date_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_year_desc = create_svg_icon(
            "assets/control/sort_date_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )

        songs_sort_options = [
            (translate("By artist (A-Z)"), sort_artist_alpha_asc, SortMode.ARTIST_ASC),
            (translate("By artist (Z-A)"), sort_artist_alpha_desc, SortMode.ARTIST_DESC),
            (translate("By album (A-Z)"), sort_album_alpha_asc, SortMode.ALPHA_ASC),
            (translate("By album (Z-A)"), sort_album_alpha_desc, SortMode.ALPHA_DESC),
            (translate("By year (oldest first)"), sort_year_asc, SortMode.YEAR_ASC),
            (translate("By year (newest first)"), sort_year_desc, SortMode.YEAR_DESC),
        ]
        self.ui.song_sort_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                songs_sort_options, self.ui.song_sort_mode
            )
        )
        set_custom_tooltip(
            self.ui.song_sort_button,
            title = translate("Sort Options"),
        )

        songs_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("All tracks"),
            control_widgets = [self.ui.song_sort_button],
            play_slot_data = "all_tracks"
        )
        self.ui.songs_header = songs_header_parts

        if play_button := self.ui.songs_header.get("play_button"):
            play_button.clicked.connect(
                lambda: self.ui.player_controller.play_data("all_tracks")
            )
            self.ui.main_view_header_play_buttons["all_tracks"] = play_button

        _h_layout.addWidget(self.ui.songs_header["header"])
        songs_header_stack.addWidget(songs_header_widget)

        songs_page = QWidget()
        songs_page_layout = QVBoxLayout(songs_page)
        songs_page_layout.setContentsMargins(0, 0, 0, 0)
        songs_page_layout.setSpacing(0)

        self.ui.songs_nav_container = QWidget()
        self.ui.songs_nav_container.setContentsMargins(0, 0, 0, 0)
        self.ui.songs_nav_container.setProperty("class", "backgroundPrimary")
        self.ui.songs_nav_layout = QVBoxLayout(self.ui.songs_nav_container)
        self.ui.songs_nav_layout.setContentsMargins(24, 16, 24, 0)
        self.ui.songs_nav_layout.setSpacing(0)
        songs_page_layout.addWidget(self.ui.songs_nav_container)
        self.ui.songs_nav_container.hide()

        self.ui.songs_scroll = StyledScrollArea()
        self.ui.songs_scroll.setProperty("class", "backgroundPrimary")
        self.ui.songs_scroll.setWidgetResizable(True)
        songs_page_layout.addWidget(self.ui.songs_scroll)

        songs_stack.addWidget(songs_page)

        return container

    def create_genres_tab(self):
        """Creates the entire 'Genres' tab widget and its sub-pages."""
        container, self.ui.genres_header_stack, self.ui.genres_stack = (
            self._create_split_stack_container("genres")
        )

        all_genres_header_widget = QWidget()
        _h_layout = QVBoxLayout(all_genres_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        genre_sort_options = [
            (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
            (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
        ]
        self.ui.genre_sort_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                genre_sort_options, self.ui.genre_sort_mode
            )
        )
        set_custom_tooltip(
            self.ui.genre_sort_button,
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
        genre_view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]
        self.ui.genre_view_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                genre_view_options, self.ui.genre_view_mode
            )
        )
        set_custom_tooltip(
            self.ui.genre_view_button,
            title = translate("View Options"),
        )

        genres_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("All Genres"),
            control_widgets=[self.ui.genre_sort_button, self.ui.genre_view_button],
        )
        self.ui.genres_header = genres_header_parts
        _h_layout.addWidget(self.ui.genres_header["header"])
        self.ui.genres_header_stack.addWidget(all_genres_header_widget)

        self.ui.genres_scroll = StyledScrollArea()
        self.ui.genres_scroll.setProperty("class", "backgroundPrimary")
        self.ui.genres_scroll.setWidgetResizable(True)
        self.ui.genres_stack.addWidget(self.ui.genres_scroll)

        genre_albums_header_page = QWidget()
        self.ui.genre_albums_header_layout = QVBoxLayout(genre_albums_header_page)
        self.ui.genre_albums_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.genre_albums_header_layout.setSpacing(0)
        self.ui.genres_header_stack.addWidget(genre_albums_header_page)

        genre_albums_page = QWidget()
        self.ui.genre_albums_layout = QVBoxLayout(genre_albums_page)
        self.ui.genre_albums_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.genre_albums_layout.setSpacing(0)
        self.ui.genres_stack.addWidget(genre_albums_page)

        genre_album_tracks_header_page = QWidget()
        self.ui.genre_album_tracks_header_layout = QVBoxLayout(
            genre_album_tracks_header_page
        )
        self.ui.genre_album_tracks_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.genre_album_tracks_header_layout.setSpacing(0)
        self.ui.genres_header_stack.addWidget(genre_album_tracks_header_page)

        genre_album_tracks_page = QWidget()
        self.ui.genre_album_tracks_layout = QVBoxLayout(genre_album_tracks_page)
        self.ui.genre_album_tracks_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.genre_album_tracks_layout.setSpacing(0)
        self.ui.genres_stack.addWidget(genre_album_tracks_page)

        return container

    def create_folder_tab(self):
        """Creates the 'Folder' tab widget."""
        container, self.ui.catalog_header_stack, self.ui.catalog_stack = (
            self._create_split_stack_container("catalog")
        )

        root_header_page = QWidget()
        _h_layout = QVBoxLayout(root_header_page)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_date_added_desc = create_svg_icon(
            "assets/control/sort_date_added_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_date_added_asc = create_svg_icon(
            "assets/control/sort_date_added_asc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )

        catalog_sort_options = [
            (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
            (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            (
                translate("By date added (newest first)"),
                sort_date_added_desc,
                SortMode.DATE_ADDED_DESC,
            ),
            (
                translate("By date added (oldest first)"),
                sort_date_added_asc,
                SortMode.DATE_ADDED_ASC,
            ),
        ]
        self.ui.catalog_sort_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                catalog_sort_options, self.ui.catalog_sort_mode
            )
        )
        set_custom_tooltip(
            self.ui.catalog_sort_button,
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
        catalog_view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]
        self.ui.catalog_view_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                catalog_view_options, self.ui.catalog_view_mode
            )
        )
        set_custom_tooltip(
            self.ui.catalog_view_button,
            title = translate("View Options"),
        )

        header_parts = self.ui.ui_manager.components.create_page_header(
            title=translate("Library folders"),
            control_widgets=[self.ui.catalog_sort_button, self.ui.catalog_view_button],
        )
        self.ui.catalog_header = header_parts
        _h_layout.addWidget(header_parts["header"])
        self.ui.catalog_header_stack.addWidget(root_header_page)

        root_page = QWidget()
        root_layout = QVBoxLayout(root_page)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.ui.catalog_scroll = StyledScrollArea()
        self.ui.catalog_scroll.setProperty("class", "backgroundPrimary")
        self.ui.catalog_scroll.setWidgetResizable(True)
        root_layout.addWidget(self.ui.catalog_scroll)
        self.ui.catalog_stack.addWidget(root_page)

        return container

    def create_playlists_tab(self):
        """Creates the entire 'Playlists' tab widget and its sub-pages."""
        container, self.ui.playlists_header_stack, self.ui.playlists_stack = (
            self._create_split_stack_container("playlists")
        )

        all_playlists_header_widget = QWidget()
        _h_layout = QVBoxLayout(all_playlists_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        playlist_sort_options = [
            (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
            (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
        ]
        self.ui.playlist_sort_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                playlist_sort_options, self.ui.playlist_sort_mode
            )
        )
        set_custom_tooltip(
            self.ui.playlist_sort_button,
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
        playlist_view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]
        self.ui.playlist_view_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                playlist_view_options, self.ui.playlist_view_mode
            )
        )
        set_custom_tooltip(
            self.ui.playlist_view_button,
            title = translate("View Options"),
        )

        playlists_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("All playlists"),
            control_widgets=[
                self.ui.playlist_sort_button,
                self.ui.playlist_view_button,
            ],
        )
        self.ui.playlists_header = playlists_header_parts
        _h_layout.addWidget(self.ui.playlists_header["header"])
        self.ui.playlists_header_stack.addWidget(all_playlists_header_widget)

        self.ui.playlists_scroll = StyledScrollArea()
        self.ui.playlists_scroll.setProperty("class", "backgroundPrimary")
        self.ui.playlists_scroll.setWidgetResizable(True)
        self.ui.playlists_stack.addWidget(self.ui.playlists_scroll)

        playlist_tracks_header_page = QWidget()
        self.ui.playlist_tracks_header_layout = QVBoxLayout(playlist_tracks_header_page)
        self.ui.playlist_tracks_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.playlist_tracks_header_layout.setSpacing(0)
        self.ui.playlists_header_stack.addWidget(playlist_tracks_header_page)

        playlist_tracks_page = QWidget()
        self.ui.playlist_tracks_layout = QVBoxLayout(playlist_tracks_page)
        self.ui.playlist_tracks_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.playlist_tracks_layout.setSpacing(0)
        self.ui.playlists_stack.addWidget(playlist_tracks_page)

        return container

    def create_favorites_tab(self):
        """Creates the entire 'Favorites' tab widget and its sub-pages."""
        container, self.ui.favorites_header_stack, self.ui.favorites_stack = (
            self._create_split_stack_container("favorites")
        )

        all_favorites_header_widget = QWidget()
        _h_layout = QVBoxLayout(all_favorites_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)


        self.ui.favorite_encyclopedia_button = QPushButton()
        self.ui.favorite_encyclopedia_button.setIcon(
            create_svg_icon(
                "assets/control/encyclopedia.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.ui.favorite_encyclopedia_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.ui.favorite_encyclopedia_button.setIconSize(QSize(24, 24))
        self.ui.favorite_encyclopedia_button.setFixedHeight(36)
        self.ui.favorite_encyclopedia_button.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.ui.favorite_encyclopedia_button,
            title = translate("Open Encyclopedia"),
        )
        apply_button_opacity_effect(self.ui.favorite_encyclopedia_button)

        favorites_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("Music Center"),
            control_widgets=[
                self.ui.favorite_encyclopedia_button,
            ],
        )
        self.ui.favorites_header = favorites_header_parts
        _h_layout.addWidget(self.ui.favorites_header["header"])
        self.ui.favorites_header_stack.addWidget(all_favorites_header_widget)

        self.ui.favorites_scroll = StyledScrollArea()
        self.ui.favorites_scroll.setProperty("class", "backgroundPrimary")
        self.ui.favorites_scroll.setWidgetResizable(True)
        self.ui.favorites_stack.addWidget(self.ui.favorites_scroll)

        favorite_detail_header_page = QWidget()
        self.ui.favorite_detail_header_layout = QVBoxLayout(favorite_detail_header_page)
        self.ui.favorite_detail_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.favorite_detail_header_layout.setSpacing(0)
        self.ui.favorites_header_stack.addWidget(favorite_detail_header_page)

        favorite_detail_page = QWidget()
        self.ui.favorite_detail_layout = QVBoxLayout(favorite_detail_page)
        self.ui.favorite_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.favorite_detail_layout.setSpacing(0)
        self.ui.favorites_stack.addWidget(favorite_detail_page)

        favorite_album_detail_header_page = QWidget()
        self.ui.favorite_album_detail_header_layout = QVBoxLayout(
            favorite_album_detail_header_page
        )
        self.ui.favorite_album_detail_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.favorite_album_detail_header_layout.setSpacing(0)
        self.ui.favorites_header_stack.addWidget(favorite_album_detail_header_page)

        favorite_album_detail_page = QWidget()
        self.ui.favorite_album_detail_layout = QVBoxLayout(favorite_album_detail_page)
        self.ui.favorite_album_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.favorite_album_detail_layout.setSpacing(0)
        self.ui.favorites_stack.addWidget(favorite_album_detail_page)

        return container

    def create_search_results_page(self):
        """
        Creates a page for displaying GLOBAL search results.
        It is not bound to a tab, but is called when text is entered.
        """
        container, self.ui.search_header_stack, self.ui.search_stack = (
            self._create_split_stack_container("search")
        )

        search_results_header_widget = QWidget()
        search_header_layout_outer = QVBoxLayout(search_results_header_widget)
        search_header_layout_outer.setContentsMargins(0, 0, 0, 0)

        buttons_data = [
            ("search_all.svg", translate("Search everywhere"), SearchMode.EVERYWHERE),
            (
                "search_favorite.svg",
                translate("Search in favorites"),
                SearchMode.FAVORITES,
            ),
            ("search_artist.svg", translate("Search in artists"), SearchMode.ARTISTS),
            ("search_album.svg", translate("Search in albums"), SearchMode.ALBUMS),
            ("search_genre.svg", translate("Search in genres"), SearchMode.GENRES),
            (
                "search_composer.svg",
                translate("Search in composers"),
                SearchMode.COMPOSERS,
            ),
            ("search_track.svg", translate("Search in tracks"), SearchMode.TRACKS),
            (
                "search_playlist.svg",
                translate("Search in playlists"),
                SearchMode.PLAYLISTS,
            ),
            ("search_lyrics.svg", translate("Search in lyrics"), SearchMode.LYRICS),
        ]
        search_mode_options = [
            (
                tooltip,
                create_svg_icon(
                    f"assets/control/{icon}", theme.COLORS["PRIMARY"], QSize(24, 24)
                ),
                mode,
            )
            for icon, tooltip, mode in buttons_data
        ]

        self.ui.search_mode_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                search_mode_options, self.ui.search_mode
            )
        )

        self.ui.search_view_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                [], self.ui.search_view_mode
            )
        )
        set_custom_tooltip(
            self.ui.search_view_button,
            title = translate("View Options"),
        )

        self.ui.search_actions_container = QWidget()
        self.ui.search_actions_layout = QHBoxLayout(self.ui.search_actions_container)
        self.ui.search_actions_layout.setContentsMargins(0, 0, 0, 0)

        header_parts = self.ui.ui_manager.components.create_page_header(
            translate("Search Results"),
            details_text=translate("Start typing to search..."),
            control_widgets=[
                self.ui.search_view_button,
                self.ui.search_actions_container,
                self.ui.search_mode_button,
            ],
        )
        self.ui.search_header = header_parts

        search_header_layout_outer.addWidget(header_parts["header"])
        self.ui.search_header_stack.addWidget(search_results_header_widget)

        self.ui.search_scroll = StyledScrollArea()
        self.ui.search_scroll.setProperty("class", "backgroundPrimary")
        self.ui.search_scroll.setWidgetResizable(True)
        self.ui.search_stack.addWidget(self.ui.search_scroll)

        search_detail_header_page_1 = QWidget()
        self.ui.search_detail_header_layout_1 = QVBoxLayout(search_detail_header_page_1)
        self.ui.search_detail_header_layout_1.setContentsMargins(0, 0, 0, 0)
        self.ui.search_header_stack.addWidget(search_detail_header_page_1)

        search_detail_page_1 = QWidget()
        self.ui.search_detail_layout_1 = QVBoxLayout(search_detail_page_1)
        self.ui.search_detail_layout_1.setContentsMargins(0, 0, 0, 0)
        self.ui.search_stack.addWidget(search_detail_page_1)

        search_detail_header_page_2 = QWidget()
        self.ui.search_detail_header_layout_2 = QVBoxLayout(search_detail_header_page_2)
        self.ui.search_detail_header_layout_2.setContentsMargins(0, 0, 0, 0)
        self.ui.search_header_stack.addWidget(search_detail_header_page_2)

        search_detail_page_2 = QWidget()
        self.ui.search_detail_layout_2 = QVBoxLayout(search_detail_page_2)
        self.ui.search_detail_layout_2.setContentsMargins(0, 0, 0, 0)
        self.ui.search_stack.addWidget(search_detail_page_2)

        return container, self.ui.search_header_stack, self.ui.search_stack

    def create_charts_tab(self):
        """Creates the entire 'Charts' tab widget and its sub-pages."""
        container, self.ui.charts_header_stack, self.ui.charts_stack = (
            self._create_split_stack_container("charts")
        )

        all_charts_header_widget = QWidget()
        _h_layout = QVBoxLayout(all_charts_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        view_grid = create_svg_icon(
            "assets/control/view_grid.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        view_tile = create_svg_icon(
            "assets/control/view_tile.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        view_tile_small = create_svg_icon(
            "assets/control/view_tile_small.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        charts_view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]
        self.ui.chart_view_button = (
            self.ui.ui_manager.components.create_tool_button_with_menu(
                charts_view_options, self.ui.favorite_view_mode
            )
        )
        set_custom_tooltip(
            self.ui.chart_view_button,
            title = translate("View Options"),
        )

        charts_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("Charts"),
            control_widgets=[self.ui.chart_view_button],
        )
        self.ui.charts_header = charts_header_parts
        _h_layout.addWidget(self.ui.charts_header["header"])
        self.ui.charts_header_stack.addWidget(all_charts_header_widget)

        self.ui.charts_scroll = StyledScrollArea()
        self.ui.charts_scroll.setProperty("class", "backgroundPrimary")
        self.ui.charts_scroll.setWidgetResizable(True)
        self.ui.charts_stack.addWidget(self.ui.charts_scroll)

        chart_detail_header_page = QWidget()
        self.ui.chart_detail_header_layout = QVBoxLayout(chart_detail_header_page)
        self.ui.chart_detail_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.chart_detail_header_layout.setSpacing(0)
        self.ui.charts_header_stack.addWidget(chart_detail_header_page)

        chart_detail_page = QWidget()
        self.ui.chart_detail_layout = QVBoxLayout(chart_detail_page)
        self.ui.chart_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.chart_detail_layout.setSpacing(0)
        self.ui.charts_stack.addWidget(chart_detail_page)

        chart_album_detail_header_page = QWidget()
        self.ui.chart_album_detail_header_layout = QVBoxLayout(
            chart_album_detail_header_page
        )
        self.ui.chart_album_detail_header_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.chart_album_detail_header_layout.setSpacing(0)
        self.ui.charts_header_stack.addWidget(chart_album_detail_header_page)

        chart_album_detail_page = QWidget()
        self.ui.chart_album_detail_layout = QVBoxLayout(chart_album_detail_page)
        self.ui.chart_album_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.ui.chart_album_detail_layout.setSpacing(0)
        self.ui.charts_stack.addWidget(chart_album_detail_page)

        return container

    def create_history_tab(self):
        """Creates the 'Playback History' tab."""
        container, history_header_stack, history_stack = (
            self._create_split_stack_container("history")
        )

        history_header_widget = QWidget()
        _h_layout = QVBoxLayout(history_header_widget)
        _h_layout.setContentsMargins(0, 0, 0, 0)

        history_header_parts = self.ui.ui_manager.components.create_page_header(
            translate("Playback history"),
            control_widgets=[],
            play_slot_data="playback_history",
            context_menu_data=("playback_history", "favorite_tracks"),
        )
        self.ui.history_header = history_header_parts
        _h_layout.addWidget(self.ui.history_header["header"])
        history_header_stack.addWidget(history_header_widget)

        self.ui.history_scroll = StyledScrollArea()
        self.ui.history_scroll.setProperty("class", "backgroundPrimary")
        self.ui.history_scroll.setWidgetResizable(True)
        history_stack.addWidget(self.ui.history_scroll)

        return container