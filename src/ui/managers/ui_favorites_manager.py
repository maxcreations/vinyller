"""
Vinyller — Music center tab and favorites UI manager
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

import json
import os
import random
from collections import defaultdict
from functools import partial

from PyQt6.QtCore import (
    QSize, Qt,
    QTimer
)
from PyQt6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QListWidgetItem, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget
)

from src.ui.custom_base_widgets import (
    StyledScrollArea, set_custom_tooltip
)
from src.ui.custom_cards import CardWidget
from src.ui.custom_classes import (
    ChartsPeriod, FlowLayout, SortMode, ViewMode, EntityCoverButton
)
from src.ui.custom_lists import (
    CustomRoles, TrackListWidget
)
from src.utils import theme
from src.utils.constants import (
    BATCH_SIZE, BATCH_SIZE_ALLTRACKS
)
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


class FavoritesUIManager:
    """
    Manages the UI logic for the favorites tab.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the FavoritesUIManager.
        """
        self.main_window = main_window
        self.ui_manager = ui_manager
        self.components = ui_manager.components

    def populate_favorites_tab(self):
        """
        Populates the main favorites tab with categorized sections including
        favorite tracks, albums, artists, genres, composers, folders, and playlists.
        It also sets up the 'My Wave' banner and popular charts if applicable.
        """
        mw = self.main_window

        if mw.favorites_scroll.widget():
            mw.favorites_scroll.widget().deleteLater()

        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(32)
        mw.favorites_scroll.setWidget(container)

        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            self.ui_manager.set_header_visibility(mw.favorites_header, False)
            self.components._show_loading_library_message(layout)
            return

        if mw.data_manager.is_empty():
            self.ui_manager.set_header_visibility(mw.favorites_header, False)
            self.components._show_no_library_message(layout)
            return

        self.ui_manager.set_header_visibility(mw.favorites_header, True)

        if hasattr(mw, "favorite_encyclopedia_button"):
            mw.favorite_encyclopedia_button.show()
            mw.favorite_encyclopedia_button.clicked.connect(
                self.main_window.open_encyclopedia_manager
            )

        banner = self.components.create_my_wave_banner(
            on_play_wave=self._play_my_wave,
            on_play_random_album=self._play_random_album,
        )
        layout.addWidget(banner)

        fav_tracks_dict = mw.library_manager.load_favorites().get("tracks", {})
        sorted_fav_paths = sorted(
            fav_tracks_dict.keys(), key=lambda k: fav_tracks_dict[k], reverse=True
        )

        all_fav_tracks = [
            mw.data_manager.get_track_by_path(p)
            for p in sorted_fav_paths
            if mw.data_manager.get_track_by_path(p)
        ]

        display_fav_tracks = all_fav_tracks[:5]

        if display_fav_tracks:
            self._add_vertical_track_list_section(
                layout,
                translate("Favorite Tracks"),
                tracks_to_display=display_fav_tracks,
                full_tracks_list=all_fav_tracks,
                on_see_all=self.show_favorite_tracks_view,
                context_key="favorite_tracks",
                icon_name="track.svg",
                button_text=translate("All tracks"),
            )

        if mw.collect_statistics and hasattr(
            mw.library_manager, "get_top_tracks_of_month"
        ):
            top_month_all = mw.library_manager.get_top_tracks_of_month(
                mw.data_manager.path_to_track_map,
                limit=100,
                sort_func=mw.data_manager.get_sort_key,
            )

            top_month_display = top_month_all[:5]

            def go_to_charts_and_show_top_tracks():
                try:
                    charts_idx = mw.nav_button_icon_names.index("charts")
                    mw.main_stack.setCurrentIndex(charts_idx)
                    if hasattr(mw, "nav_buttons") and len(mw.nav_buttons) > charts_idx:
                        for btn in mw.nav_buttons:
                            btn.setChecked(False)
                        mw.nav_buttons[charts_idx].setChecked(True)
                        mw.ui_manager.update_nav_button_icons()

                    if getattr(mw, "charts_period", None) != ChartsPeriod.MONTHLY:
                        mw.charts_period = ChartsPeriod.MONTHLY
                        mw.save_current_settings()
                        stats = mw.library_manager.load_play_stats()
                        mw.data_manager.recalculate_ratings(ChartsPeriod.MONTHLY, stats)

                    mw.ui_manager.charts_ui_manager.show_all_top_tracks_view()
                except ValueError:
                    print("Charts tab not found")

            if top_month_display:
                self._add_vertical_track_list_section(
                    layout,
                    translate("Popular this Month"),
                    tracks_to_display=top_month_display,
                    full_tracks_list=top_month_all,
                    on_see_all=go_to_charts_and_show_top_tracks,
                    context_key="all_top_tracks",
                    icon_name="charts.svg",
                    button_text=translate("Go to Charts"),
                )

        favorites = mw.library_manager.load_favorites()

        categories = [
            "tracks",
            "albums",
            "artists",
            "genres",
            "composers",
            "folders",
            "playlists",
        ]
        has_any_favorites = any(favorites.get(cat) for cat in categories)

        if not has_any_favorites:
            self.ui_manager.set_header_visibility(mw.favorites_header, True)
            self.components._show_no_favorites_message(layout)
            return

        def get_top_items(category_key, data_map, limit=15):
            items_dict = favorites.get(category_key, {})
            sorted_keys = sorted(
                items_dict.keys(), key=lambda k: items_dict[k], reverse=True
            )[:limit]
            result = []
            for k in sorted_keys:
                real_key = tuple(json.loads(k)) if category_key == "albums" else k
                if category_key in ["folders", "playlists"]:
                    result.append((real_key, None))
                elif real_key in data_map:
                    result.append((real_key, data_map[real_key]))
                elif category_key == "albums":
                    target_artist = real_key[0]
                    target_title = real_key[1]
                    for db_key, db_val in data_map.items():
                        if db_key[0] == target_artist and db_key[1] == target_title:
                            result.append((db_key, db_val))
                            break
            return result

        category_configs = {
            "album": {
                "key": "albums",
                "title": translate("Favorite Albums"),
                "type": "album",
                "data_map": mw.data_manager.albums_data,
                "see_all": self.show_all_favorite_albums_view,
                "icon": "album.svg"
            },
            "artist": {
                "key": "artists",
                "title": translate("Favorite Artists"),
                "type": "artist",
                "data_map": mw.data_manager.artists_data,
                "see_all": self.show_all_favorite_artists_view,
                "icon": "artist.svg"
            },
            "genre": {
                "key": "genres",
                "title": translate("Favorite Genres"),
                "type": "genre",
                "data_map": mw.data_manager.genres_data,
                "see_all": self.show_all_favorite_genres_view,
                "icon": "genre.svg"
            },
            "composer": {
                "key": "composers",
                "title": translate("Favorite Composers"),
                "type": "composer",
                "data_map": mw.data_manager.composers_data,
                "see_all": self.show_all_favorite_composers_view,
                "icon": "composer.svg"
            },
            "folder": {
                "key": "folders",
                "title": translate("Favorite Folders"),
                "type": "folder",
                "data_map": {},
                "see_all": self.show_all_favorite_folders_view,
                "icon": "folder.svg"
            },
            "playlist": {
                "key": "playlists",
                "title": translate("Favorite Playlists"),
                "type": "playlist",
                "data_map": {},
                "see_all": self.show_all_favorite_playlists_view,
                "icon": "playlist.svg"
            }
        }

        for tab_name in mw.nav_tab_order:
            if tab_name in category_configs:
                config = category_configs[tab_name]
                items = get_top_items(config["key"], config["data_map"])
                if items:
                    self._add_horizontal_card_section(
                        layout,
                        config["title"],
                        config["type"],
                        items,
                        config["see_all"],
                        icon_name = config["icon"],
                    )

        layout.addStretch(1)
        self.ui_manager.update_all_track_widgets()

    def _play_my_wave(self):
        """
        Generates and plays a dynamic playlist ('My Wave') based on the user's library and preferences.
        """
        mw = self.main_window
        if hasattr(mw.library_manager, "generate_my_wave_queue"):
            queue = mw.library_manager.generate_my_wave_queue(mw.data_manager)
            if queue:
                mw.player_controller.play_data(
                    {"type": "my_wave", "data": translate("My Wave")}, shuffle=False
                )
                mw.player.set_queue(queue)
                mw.player.play(0)
                mw.current_queue_name = translate("My Wave")
            else:
                print("Not enough data for My Wave")
        else:
            print("generate_my_wave_queue method missing in LibraryManager")

    def _play_random_album(self):
        """
        Selects a random album from the loaded library and starts playback.
        """
        mw = self.main_window
        if mw.data_manager.albums_data:
            random_key = random.choice(list(mw.data_manager.albums_data.keys()))
            mw.player_controller.play_data(random_key)

    def _add_vertical_track_list_section(
        self,
        parent_layout,
        title,
        tracks_to_display,
        full_tracks_list,
        on_see_all,
        context_key,
        icon_name=None,
        button_text=None,
    ):
        """
        Adds a section containing a vertical list of tracks (e.g., top tracks or recent favorites)
        to the given parent layout.

        Args:
            parent_layout (QLayout): The layout to which the section is added.
            title (str): The title displayed above the list.
            tracks_to_display (list): A list of track dictionaries to render.
            full_tracks_list (list): The full list of tracks to be used for the playback queue.
            on_see_all (callable): Callback function for the 'See all' button.
            context_key (str): Context identifier used for the track list.
            icon_name (str, optional): Filename for the icon next to the title.
            button_text (str, optional): Custom text for the 'See all' button.
        """
        mw = self.main_window

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setProperty("class", "backgroundPrimary")
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(12)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        if icon_name:
            if not icon_name.endswith(".svg"):
                icon_name += ".svg"
            icon_path = f"assets/control/{icon_name}"
            icon_label = QLabel()
            icon_pixmap = create_svg_icon(
                icon_path, theme.COLORS["PRIMARY"], QSize(24, 24)
            ).pixmap(24, 24)
            icon_label.setPixmap(icon_pixmap)
            op_eff = QGraphicsOpacityEffect(icon_label)
            op_eff.setOpacity(0.8)
            icon_label.setGraphicsEffect(op_eff)
            header_layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setProperty("class", "textHeaderSecondary textColorPrimary")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        if on_see_all:
            text = button_text if button_text else translate("See all")
            see_all_btn = QPushButton(text)

            see_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            see_all_btn.setProperty("class", "btnText")
            see_all_btn.clicked.connect(on_see_all)
            header_layout.addWidget(see_all_btn)

        container_layout.addWidget(header_widget)

        show_score = context_key == "all_top_tracks"

        track_list_widget = TrackListWidget(
            mw,
            parent_context=context_key,
            use_row_for_track_num=True,
            show_score=show_score,
            parent=container,
        )

        has_any_composer = any(
            t.get("composer") and t.get("composer").strip() for t in tracks_to_display
        )
        track_list_widget.delegate.setShowComposerColumn(has_any_composer)

        for i, track in enumerate(tracks_to_display):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, track)
            item.setData(CustomRoles.IsCurrentRole, False)
            item.setData(CustomRoles.IsPlayingRole, False)
            track_list_widget.addItem(item)

        track_list_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        track_list_widget.pauseTrackClicked.connect(mw.player.pause)

        track_list_widget.playTrackClicked.connect(
            lambda track_data, idx: self._play_track_from_vertical_section(
                full_tracks_list, title, context_key, track_data
            )
        )

        track_list_widget.trackContextMenuRequested.connect(
            lambda data, pos, ctx: mw.action_handler.show_context_menu(
                data, pos, context=ctx
            )
        )

        track_list_widget.artistClicked.connect(mw.ui_manager.navigate_to_artist)
        track_list_widget.composerClicked.connect(mw.ui_manager.navigate_to_composer)
        track_list_widget.lyricsClicked.connect(mw.action_handler.show_lyrics)

        track_list_widget.restartTrackClicked.connect(
            lambda track_data, idx: self._play_track_from_vertical_section(
                full_tracks_list, title, context_key, track_data
            )
        )

        container_layout.addWidget(track_list_widget)
        parent_layout.addWidget(container)

        mw.main_view_track_lists.append(track_list_widget)

    def _play_track_from_vertical_section(
        self, full_tracks_list, queue_name, context_key, track_to_play
    ):
        """
        Starts playback of a specific track from a vertical section and sets up the playback queue.

        Args:
            full_tracks_list (list): The list containing all tracks in the context.
            queue_name (str): The display name of the current queue.
            context_key (str): The internal context identifier.
            track_to_play (dict): Data dictionary of the track to be played.
        """
        mw = self.main_window

        mw.current_queue_name = queue_name
        mw.current_queue_context_data = context_key
        mw.current_queue_context_path = None

        mw.conscious_choice_data = (track_to_play["path"], "track")

        mw.player.set_queue(full_tracks_list)

        target_index = 0
        for i, t in enumerate(full_tracks_list):
            if t["path"] == track_to_play["path"]:
                target_index = i
                break

        mw.player.play(target_index)

    def _add_horizontal_card_section(
        self, parent_layout, title, item_type, items, on_see_all, icon_name=None
    ):
        """
        Adds a horizontally scrollable section of visual cards (e.g., albums, artists, playlists).

        Args:
            parent_layout (QLayout): The layout to which the section is added.
            title (str): The title displayed above the section.
            item_type (str): The type of items being displayed (e.g., 'album', 'artist').
            items (list): A list of tuples containing keys and data for the items.
            on_see_all (callable): Callback function for the 'See all' button.
            icon_name (str, optional): Filename for the header icon.
        """
        content_widget = QWidget()
        h_layout = QHBoxLayout(content_widget)
        h_layout.setContentsMargins(8, 0, 8, 0)
        h_layout.setSpacing(16)

        mw = self.main_window

        for key, data in items:
            widget = None

            if item_type == "album":
                widget = self.components.create_album_widget(
                    key, data, ViewMode.TILE_BIG
                )
                widget.activated.connect(
                    partial(
                        self.ui_manager.show_album_tracks,
                        source_stack=mw.favorites_stack,
                    )
                )
                widget.playClicked.connect(mw.player_controller.play_data)
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "album"}
                    )
                )

            elif item_type == "artist":
                widget = self.components.create_artist_widget(
                    key, data, ViewMode.TILE_BIG
                )
                widget.activated.connect(
                    partial(self.show_favorite_artist_albums_view, key)
                )
                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "artist", "data": d}
                    )
                )
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "artist"}
                    )
                )

            elif item_type == "genre":
                widget = self.components.create_genre_widget(
                    key, data, ViewMode.TILE_BIG
                )
                widget.activated.connect(
                    partial(self.show_favorite_genre_albums_view, key)
                )
                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "genre", "data": d}
                    )
                )
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "genre"}
                    )
                )

            elif item_type == "composer":
                widget = self.components.create_composer_widget(
                    key, data, ViewMode.TILE_BIG
                )
                widget.activated.connect(
                    partial(self.show_favorite_composer_albums_view, key)
                )
                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "composer", "data": d}
                    )
                )
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "composer"}
                    )
                )

            elif item_type == "folder":
                folder_name = os.path.basename(key) or key
                artworks = self.ui_manager.get_artworks_for_directory(key)
                widget = self.components.create_directory_widget(
                    folder_name, key, ViewMode.TILE_BIG, artworks
                )
                widget.activated.connect(partial(self.show_favorite_folder_view, key))
                widget.playClicked.connect(mw.player_controller.play_data)
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "folder"}
                    )
                )

            elif item_type == "playlist":
                meta = mw.library_manager.get_playlist_metadata(
                    key, mw.data_manager.path_to_track_map
                )
                track_count = meta.get("count", 0)
                first_art = meta.get("artwork")
                p_name = os.path.splitext(os.path.basename(key))[0]

                pixmap_size = 128
                if first_art:
                    pixmap = self.components.get_pixmap(first_art, pixmap_size)
                else:
                    pixmap = self.components.playlist_pixmap

                subtitle = translate("{count} track(s)", count=track_count)
                widget = CardWidget(
                    data=key,
                    view_mode=ViewMode.TILE_BIG,
                    pixmaps=[pixmap],
                    title=p_name,
                    subtitle1=subtitle,
                    is_artist_card=False,
                    icon_pixmap=self.components.playlist_icon_pixmap,
                )
                widget.activated.connect(partial(self.show_favorite_playlist_view, key))
                widget.playClicked.connect(mw.player_controller.play_data)
                widget.contextMenuRequested.connect(
                    mw.action_handler.show_playlist_card_context_menu
                )

            if widget:
                h_layout.addWidget(widget)

        h_layout.addStretch()

        if content_widget.layout().count() > 1:
            section = self.components.create_navigable_section(
                title, content_widget, on_see_all, header_icon_name=icon_name
            )
            parent_layout.addWidget(section)

    def _show_album_details_safe(self, album_key):
        """
        Safely navigates to the detailed view of a specific album within the favorites stack.

        Args:
            album_key: The unique identifier/tuple for the album.
        """
        mw = self.main_window
        if mw.favorites_stack.currentIndex() != 1:
            mw.favorites_stack.setCurrentIndex(1)
        self.ui_manager.show_album_tracks(album_key, source_stack=mw.favorites_stack)

    def show_all_favorite_playlists_view(self):
        """
        Renders the detailed view listing all favorite playlists, including controls for sorting and view modes.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_playlists_sort_mode"):
            mw.favorite_playlists_sort_mode = SortMode.DATE_ADDED_DESC
        if not hasattr(mw, "favorite_playlists_view_mode"):
            mw.favorite_playlists_view_mode = ViewMode.GRID

        is_refresh = (
            mw.current_favorites_context == "all_playlists"
            and mw.favorite_detail_layout.count() > 0
            and mw.favorites_stack.currentIndex() == 1
        )

        if not is_refresh:
            mw.current_favorites_context = "all_playlists"
            mw.favorite_detail_separator_widgets.clear()
            self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
            self.ui_manager.clear_layout(mw.favorite_detail_layout)

        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
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

        control_widgets = []
        if not is_refresh:
            sort_options = [
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
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]
            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.favorite_playlists_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_playlists_sort_mode", action.data()),
                    self.show_all_favorite_playlists_view(),
                )
            )
            set_custom_tooltip(
                sort_button,
                title = translate("Sort Options"),
            )
            view_button = self.components.create_tool_button_with_menu(
                [
                    (
                        translate("Grid"),
                        create_svg_icon(
                            "assets/control/view_grid.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.GRID,
                    ),
                    (
                        translate("Tile"),
                        create_svg_icon(
                            "assets/control/view_tile.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_BIG,
                    ),
                    (
                        translate("Small Tile"),
                        create_svg_icon(
                            "assets/control/view_tile_small.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_SMALL,
                    ),
                ],
                mw.favorite_playlists_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_playlists_view_mode", action.data()),
                    self.show_all_favorite_playlists_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            control_widgets = [sort_button, view_button]

        favorites = mw.library_manager.load_favorites()
        fav_playlists_dict = favorites.get("playlists", {})
        items = list(fav_playlists_dict.keys())

        if mw.favorite_playlists_sort_mode == SortMode.ALPHA_ASC:
            items.sort(
                key=lambda p: mw.data_manager.get_sort_key(
                    os.path.splitext(os.path.basename(p))[0]
                )
            )
        elif mw.favorite_playlists_sort_mode == SortMode.ALPHA_DESC:
            items.sort(
                key=lambda p: mw.data_manager.get_sort_key(
                    os.path.splitext(os.path.basename(p))[0]
                ),
                reverse=True,
            )
        elif mw.favorite_playlists_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda k: fav_playlists_dict.get(k, 0))
        else:
            items.sort(key=lambda k: fav_playlists_dict.get(k, 0), reverse=True)

        mw.playlist_groups = set()
        if mw.show_favorites_separators:
            for p_path in items:
                current_group = None
                if mw.favorite_playlists_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    p_name = os.path.splitext(os.path.basename(p_path))[0]
                    sort_name = mw.data_manager.get_sort_key(p_name)
                    first_char = sort_name[0] if sort_name else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.favorite_playlists_sort_mode in [
                    SortMode.DATE_ADDED_DESC,
                    SortMode.DATE_ADDED_ASC,
                ]:
                    ts = fav_playlists_dict.get(p_path, 0)
                    current_group = self.ui_manager._format_date_added_group(ts)

                if current_group:
                    mw.playlist_groups.add(current_group)

        mw.current_fav_all_playlists_list = items
        mw.fav_all_playlists_loaded_count = 0
        mw.is_loading_fav_all_playlists = False
        mw.last_fav_all_playlists_group = None
        mw.current_fav_all_playlists_flow_layout = None

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=translate("All Favorite Playlists"),
                details_text=translate("{count} playlist(s)", count=len(items)),
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_favorite_playlists",
                context_menu_data=("all_favorite_playlists", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_favorite_playlists")
                )
                mw.main_view_header_play_buttons["all_favorite_playlists"] = play_button

            self.fav_playlists_details_label = header_parts["details"]
            mw.favorite_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.favorite_detail_scroll_area = scroll_area
            mw.favorite_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "fav_playlists_details_label"):
                self.fav_playlists_details_label.setText(
                    translate("{count} playlist(s)", count=len(items))
                )

        if mw.favorite_detail_scroll_area.widget():
            mw.favorite_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        mw.favorite_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No favorite playlists found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_favorite_playlists
                )
            )
            self.load_more_favorite_playlists()

        if not is_refresh:
            mw.favorites_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("favorite"),
                context_data={"context": "all_playlists"},
            )

        self.ui_manager.update_all_track_widgets()

    def load_more_favorite_playlists(self):
        """
        Loads the next batch of favorite playlists for infinite scrolling in the detailed view.
        """
        mw = self.main_window
        if mw.is_loading_fav_all_playlists:
            return
        if mw.fav_all_playlists_loaded_count >= len(mw.current_fav_all_playlists_list):
            return

        mw.is_loading_fav_all_playlists = True
        start = mw.fav_all_playlists_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_fav_all_playlists_list))

        container = mw.favorite_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            p_path = mw.current_fav_all_playlists_list[i]

            current_group = None
            if mw.favorite_playlists_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                p_name = os.path.splitext(os.path.basename(p_path))[0]
                sort_name = mw.data_manager.get_sort_key(p_name)
                first_char = sort_name[0] if sort_name else "*"
                current_group = first_char.upper() if first_char.isalpha() else "*"
            elif mw.favorite_playlists_sort_mode in [
                SortMode.DATE_ADDED_DESC,
                SortMode.DATE_ADDED_ASC,
            ]:
                ts = mw.favorites["playlists"].get(p_path, 0)
                current_group = self.ui_manager._format_date_added_group(ts)

            if (
                mw.show_favorites_separators
                and current_group
                and current_group != mw.last_fav_all_playlists_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "all_favorite_playlists", mw.playlist_groups
                )
                main_layout.addWidget(separator_widget)
                mw.favorite_detail_separator_widgets[current_group] = separator_widget
                mw.last_fav_all_playlists_group = current_group
                mw.current_fav_all_playlists_flow_layout = None

            target_layout = main_layout
            if mw.favorite_playlists_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_fav_all_playlists_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_fav_all_playlists_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_fav_all_playlists_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_fav_all_playlists_flow_layout

            meta = mw.library_manager.get_playlist_metadata(
                p_path, mw.data_manager.path_to_track_map
            )
            track_count = meta.get("count", 0)
            first_artwork_dict = meta.get("artwork")

            playlist_name = os.path.splitext(os.path.basename(p_path))[0]

            if first_artwork_dict:
                pixmap = self.components.get_pixmap(first_artwork_dict, 128)
            else:
                pixmap = self.components.playlist_pixmap

            subtitle1 = translate("{count} track(s)", count=track_count)

            widget = CardWidget(
                data=p_path,
                view_mode=mw.favorite_playlists_view_mode,
                pixmaps=[pixmap],
                title=playlist_name,
                subtitle1=subtitle1,
                is_artist_card=False,
            )
            widget.activated.connect(partial(self.show_favorite_playlist_view, p_path))
            widget.playClicked.connect(mw.player_controller.play_data)
            widget.pauseClicked.connect(mw.player.pause)
            widget.contextMenuRequested.connect(
                mw.action_handler.show_playlist_card_context_menu
            )
            mw.main_view_card_widgets[p_path].append(widget)
            target_layout.addWidget(widget)

        mw.fav_all_playlists_loaded_count = end
        mw.is_loading_fav_all_playlists = False

        if end >= len(mw.current_fav_all_playlists_list):
            if mw.favorite_playlists_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_fav_playlists)

    def _check_for_more_fav_playlists(self):
        """
        Triggered periodically to check if more favorite playlists need to be loaded
        if the initial batch did not fill the scroll area.
        """
        mw = self.main_window
        try:
            if (
                not hasattr(mw, "favorite_detail_scroll_area")
                or mw.favorite_detail_scroll_area is None
            ):
                return
            if not mw.favorite_detail_scroll_area.widget():
                return
            scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
            has_more = mw.fav_all_playlists_loaded_count < len(
                mw.current_fav_all_playlists_list
            )
            if scroll_bar.maximum() == 0 and has_more:
                self.load_more_favorite_playlists()
        except RuntimeError:
            return

    def show_all_favorite_albums_view(self):
        """
        Renders the detailed view listing all favorite albums with options for sorting and view modes.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_albums_sort_mode"):
            mw.favorite_albums_sort_mode = SortMode.DATE_ADDED_DESC
        if not hasattr(mw, "favorite_albums_view_mode"):
            mw.favorite_albums_view_mode = ViewMode.GRID

        is_refresh = (
            mw.current_favorites_context == "all_albums"
            and mw.favorite_detail_layout.count() > 0
            and mw.favorites_stack.currentIndex() == 1
        )

        if not is_refresh:
            mw.current_favorites_context = "all_albums"
            mw.favorite_detail_separator_widgets.clear()
            self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
            self.ui_manager.clear_layout(mw.favorite_detail_layout)

        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
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

        control_widgets = []
        if not is_refresh:
            sort_options = [
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
                (
                    translate("By year (newest first)"),
                    sort_year_desc,
                    SortMode.YEAR_DESC,
                ),
                (translate("By year (oldest first)"), sort_year_asc, SortMode.YEAR_ASC),
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]
            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.favorite_albums_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_albums_sort_mode", action.data()),
                    self.show_all_favorite_albums_view(),
                )
            )
            set_custom_tooltip(
                sort_button,
                title = translate("Sort Options"),
            )
            view_button = self.components.create_tool_button_with_menu(
                [
                    (
                        translate("Grid"),
                        create_svg_icon(
                            "assets/control/view_grid.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.GRID,
                    ),
                    (
                        translate("Tile"),
                        create_svg_icon(
                            "assets/control/view_tile.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_BIG,
                    ),
                    (
                        translate("Small Tile"),
                        create_svg_icon(
                            "assets/control/view_tile_small.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_SMALL,
                    ),
                ],
                mw.favorite_albums_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_albums_view_mode", action.data()),
                    self.show_all_favorite_albums_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            control_widgets = [sort_button, view_button]

        favorites = mw.library_manager.load_favorites()
        fav_albums_dict = favorites.get("albums", {})
        try:
            items_raw = [json.loads(k) for k in fav_albums_dict.keys()]
        except json.JSONDecodeError:
            items_raw = []

        items = []
        for k in items_raw:
            album_key_tuple = tuple(k)
            if (
                album_key_tuple not in mw.data_manager.albums_data
                and len(album_key_tuple) >= 2
            ):
                target_artist = album_key_tuple[0]
                target_title = album_key_tuple[1]
                found = False
                for real_key in mw.data_manager.albums_data.keys():
                    if real_key[0] == target_artist and real_key[1] == target_title:
                        items.append(list(real_key))
                        found = True
                        break
                if not found:
                    items.append(k)
            else:
                items.append(k)

        if mw.favorite_albums_sort_mode == SortMode.DATE_ADDED_DESC:
            items.sort(
                key=lambda k: fav_albums_dict.get(json.dumps(k), 0), reverse=True
            )
        elif mw.favorite_albums_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda k: fav_albums_dict.get(json.dumps(k), 0))
        elif mw.favorite_albums_sort_mode == SortMode.YEAR_DESC:
            items.sort(
                key=lambda k: (
                    mw.data_manager.albums_data.get(tuple(k), {}).get("year", 0),
                    mw.data_manager.get_sort_key(k[1]),
                ),
                reverse=True,
            )
        elif mw.favorite_albums_sort_mode == SortMode.YEAR_ASC:
            items.sort(
                key=lambda k: (
                    mw.data_manager.albums_data.get(tuple(k), {}).get("year", 9999),
                    mw.data_manager.get_sort_key(k[1]),
                )
            )
        elif mw.favorite_albums_sort_mode == SortMode.ALPHA_ASC:
            items.sort(key=lambda k: mw.data_manager.get_sort_key(k[1]))
        elif mw.favorite_albums_sort_mode == SortMode.ALPHA_DESC:
            items.sort(key=lambda k: mw.data_manager.get_sort_key(k[1]), reverse=True)

        mw.album_groups = set()
        if mw.show_favorites_separators:
            for album_key_list in items:
                album_key = tuple(album_key_list)
                album_data = mw.data_manager.albums_data.get(album_key)
                if not album_data:
                    continue

                current_group = None
                if mw.favorite_albums_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    album_title = mw.data_manager.get_sort_key(album_key[1])
                    first_char = album_title[0] if album_title else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.favorite_albums_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                    album_year = album_data.get("year")
                    current_group = (
                        str(album_year)
                        if (album_year is not None and album_year > 0)
                        else "#"
                    )
                elif mw.favorite_albums_sort_mode in [
                    SortMode.DATE_ADDED_DESC,
                    SortMode.DATE_ADDED_ASC,
                ]:
                    key_str = json.dumps(album_key_list)
                    ts = fav_albums_dict.get(key_str, 0)
                    current_group = self.ui_manager._format_date_added_group(ts)

                if current_group:
                    mw.album_groups.add(current_group)

        mw.current_fav_all_albums_list = items
        mw.fav_all_albums_loaded_count = 0
        mw.is_loading_fav_all_albums = False
        mw.last_fav_all_albums_group = None
        mw.current_fav_all_albums_flow_layout = None

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=translate("All Favorite Albums"),
                details_text=translate("{count} album(s)", count=len(items)),
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_favorite_albums",
                context_menu_data=("all_favorite_albums", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_favorite_albums")
                )
                mw.main_view_header_play_buttons["all_favorite_albums"] = play_button

            self.fav_albums_details_label = header_parts["details"]
            mw.favorite_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.favorite_detail_scroll_area = scroll_area
            mw.favorite_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "fav_albums_details_label"):
                self.fav_albums_details_label.setText(
                    translate("{count} album(s)", count=len(items))
                )

        if mw.favorite_detail_scroll_area.widget():
            mw.favorite_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        mw.favorite_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No favorite albums found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_favorite_albums
                )
            )
            self.load_more_favorite_albums()

        if not is_refresh:
            mw.favorites_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("favorite"),
                context_data={"context": "all_albums"},
            )

        self.ui_manager.update_all_track_widgets()

    def load_more_favorite_albums(self):
        """
        Loads the next batch of favorite albums for infinite scrolling.
        """
        mw = self.main_window
        if mw.is_loading_fav_all_albums:
            return
        if mw.fav_all_albums_loaded_count >= len(mw.current_fav_all_albums_list):
            return

        mw.is_loading_fav_all_albums = True
        start = mw.fav_all_albums_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_fav_all_albums_list))

        container = mw.favorite_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            album_key_list = mw.current_fav_all_albums_list[i]
            album_key = tuple(album_key_list)
            album_data = mw.data_manager.albums_data.get(album_key)
            if not album_data:
                continue

            current_group = None
            if mw.favorite_albums_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                album_title = mw.data_manager.get_sort_key(album_key[1])
                first_char = album_title[0] if album_title else "#"
                current_group = first_char.upper() if first_char.isalpha() else "*"
            elif mw.favorite_albums_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                album_year = album_data.get("year")
                current_group = (
                    str(album_year)
                    if (album_year is not None and album_year > 0)
                    else "#"
                )
            elif mw.favorite_albums_sort_mode in [
                SortMode.DATE_ADDED_DESC,
                SortMode.DATE_ADDED_ASC,
            ]:
                key_str = json.dumps(album_key_list)
                ts = mw.favorites["albums"].get(key_str, 0)
                current_group = self.ui_manager._format_date_added_group(ts)

            if (
                mw.show_favorites_separators
                and current_group
                and current_group != mw.last_fav_all_albums_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "favorite_albums", mw.album_groups
                )
                main_layout.addWidget(separator_widget)
                mw.favorite_detail_separator_widgets[current_group] = separator_widget
                mw.last_fav_all_albums_group = current_group
                mw.current_fav_all_albums_flow_layout = None

            target_layout = main_layout
            if mw.favorite_albums_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_fav_all_albums_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_fav_all_albums_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_fav_all_albums_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_fav_all_albums_flow_layout

            widget = self.components.create_album_widget(
                album_key, album_data, mw.favorite_albums_view_mode
            )
            widget.activated.connect(
                partial(
                    self.ui_manager.show_album_tracks, source_stack=mw.favorites_stack
                )
            )

            widget.contextMenuRequested.connect(
                lambda data, pos: mw.action_handler.show_context_menu(
                    data, pos, context={"forced_type": "album"}
                )
            )

            widget.playClicked.connect(mw.player_controller.play_data)
            target_layout.addWidget(widget)

        mw.fav_all_albums_loaded_count = end
        mw.is_loading_fav_all_albums = False

        if end >= len(mw.current_fav_all_albums_list):
            if mw.favorite_albums_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_fav_albums)

    def _check_for_more_fav_albums(self):
        """
        Periodically checks if more favorite albums need to be loaded to fill the scroll view.
        """
        mw = self.main_window
        if not mw.favorite_detail_scroll_area.widget():
            return
        scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
        has_more = mw.fav_all_albums_loaded_count < len(mw.current_fav_all_albums_list)
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_favorite_albums()

    def show_all_favorite_artists_view(self):
        """
        Renders the detailed view listing all favorite artists with options for sorting and view modes.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_artists_sort_mode"):
            mw.favorite_artists_sort_mode = SortMode.DATE_ADDED_DESC
        if not hasattr(mw, "favorite_artists_view_mode"):
            mw.favorite_artists_view_mode = ViewMode.GRID

        is_refresh = (
            mw.current_favorites_context == "all_artists"
            and mw.favorite_detail_layout.count() > 0
            and mw.favorites_stack.currentIndex() == 1
        )

        if not is_refresh:
            mw.current_favorites_context = "all_artists"
            self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
            self.ui_manager.clear_layout(mw.favorite_detail_layout)

        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
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

        control_widgets = []
        if not is_refresh:
            sort_options = [
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
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]
            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.favorite_artists_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_artists_sort_mode", action.data()),
                    self.show_all_favorite_artists_view(),
                )
            )
            set_custom_tooltip(
                sort_button,
                title = translate("Sort Options"),
            )

            view_button = self.components.create_tool_button_with_menu(
                [
                    (
                        translate("Grid"),
                        create_svg_icon(
                            "assets/control/view_grid.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.GRID,
                    ),
                    (
                        translate("Tile"),
                        create_svg_icon(
                            "assets/control/view_tile.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_BIG,
                    ),
                    (
                        translate("Small Tile"),
                        create_svg_icon(
                            "assets/control/view_tile_small.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_SMALL,
                    ),
                ],
                mw.favorite_artists_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_artists_view_mode", action.data()),
                    self.show_all_favorite_artists_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            control_widgets = [sort_button, view_button]

        favorites = mw.library_manager.load_favorites()
        fav_artists_dict = favorites.get("artists", {})
        items = list(fav_artists_dict.keys())

        if mw.favorite_artists_sort_mode == SortMode.ALPHA_ASC:
            items.sort(key=mw.data_manager.get_sort_key)
        elif mw.favorite_artists_sort_mode == SortMode.ALPHA_DESC:
            items.sort(key=mw.data_manager.get_sort_key, reverse=True)
        elif mw.favorite_artists_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda k: fav_artists_dict.get(k, 0))
        else:
            items.sort(key=lambda k: fav_artists_dict.get(k, 0), reverse=True)

        mw.artist_letters = set()
        if mw.show_favorites_separators:
            for artist_name in items:
                current_group = None
                if mw.favorite_artists_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    sort_name = mw.data_manager.get_sort_key(artist_name)
                    first_char = sort_name[0] if sort_name else "*"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.favorite_artists_sort_mode in [
                    SortMode.DATE_ADDED_DESC,
                    SortMode.DATE_ADDED_ASC,
                ]:
                    ts = fav_artists_dict.get(artist_name, 0)
                    current_group = self.ui_manager._format_date_added_group(ts)

                if current_group:
                    mw.artist_letters.add(current_group)

        mw.favorite_detail_separator_widgets.clear()

        mw.current_fav_all_artists_list = items
        mw.fav_all_artists_loaded_count = 0
        mw.is_loading_fav_all_artists = False
        mw.last_fav_all_artists_group = None
        mw.current_fav_all_artists_flow_layout = None

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=translate("All Favorite Artists"),
                details_text=translate("{count} artist(s)", count=len(items)),
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_favorite_artists",
                context_menu_data=("all_favorite_artists", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_favorite_artists")
                )
                mw.main_view_header_play_buttons["all_favorite_artists"] = play_button

            self.fav_artists_details_label = header_parts["details"]
            mw.favorite_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.favorite_detail_scroll_area = scroll_area
            mw.favorite_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "fav_artists_details_label"):
                self.fav_artists_details_label.setText(
                    translate("{count} artist(s)", count=len(items))
                )

        if mw.favorite_detail_scroll_area.widget():
            mw.favorite_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        mw.favorite_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No favorite artists found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_favorite_artists
                )
            )
            self.load_more_favorite_artists()

        if not is_refresh:
            mw.favorites_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("favorite"),
                context_data={"context": "all_artists"},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_favorite_artists(self):
        """
        Loads the next batch of favorite artists for infinite scrolling.
        """
        mw = self.main_window
        if mw.is_loading_fav_all_artists:
            return
        if mw.fav_all_artists_loaded_count >= len(mw.current_fav_all_artists_list):
            return

        mw.is_loading_fav_all_artists = True
        start = mw.fav_all_artists_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_fav_all_artists_list))

        container = mw.favorite_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            artist_name = mw.current_fav_all_artists_list[i]

            current_group = None
            if mw.favorite_artists_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                sort_name = mw.data_manager.get_sort_key(artist_name)
                first_char = sort_name[0] if sort_name else "*"
                current_group = first_char.upper() if first_char.isalpha() else "*"
            elif mw.favorite_artists_sort_mode in [
                SortMode.DATE_ADDED_DESC,
                SortMode.DATE_ADDED_ASC,
            ]:
                ts = mw.favorites["artists"].get(artist_name, 0)
                current_group = self.ui_manager._format_date_added_group(ts)

            if (
                mw.show_favorites_separators
                and current_group != mw.last_fav_all_artists_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "favorite_artists", mw.artist_letters
                )
                main_layout.addWidget(separator_widget)
                mw.favorite_detail_separator_widgets[current_group] = separator_widget
                mw.last_fav_all_artists_group = current_group
                mw.current_fav_all_artists_flow_layout = None

            target_layout = main_layout
            if mw.favorite_artists_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_fav_all_artists_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_fav_all_artists_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_fav_all_artists_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_fav_all_artists_flow_layout

            if artist_data := mw.data_manager.artists_data.get(artist_name):
                widget = self.components.create_artist_widget(
                    artist_name, artist_data, mw.favorite_artists_view_mode
                )
                widget.activated.connect(
                    partial(self.show_favorite_artist_albums_view, artist_name)
                )

                widget.contextMenuRequested.connect(
                    lambda data, pos: mw.action_handler.show_context_menu(
                        data, pos, context={"forced_type": "artist"}
                    )
                )

                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "artist", "data": d}
                    )
                )
                target_layout.addWidget(widget)

        mw.fav_all_artists_loaded_count = end
        mw.is_loading_fav_all_artists = False

        if end >= len(mw.current_fav_all_artists_list):
            if mw.favorite_artists_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_fav_artists)

    def _check_for_more_fav_artists(self):
        """
        Periodically checks if more favorite artists need to be loaded to fill the scroll view.
        """
        mw = self.main_window
        if not mw.favorite_detail_scroll_area.widget():
            return
        scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
        has_more = mw.fav_all_artists_loaded_count < len(
            mw.current_fav_all_artists_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_favorite_artists()

    def show_all_favorite_composers_view(self):
        """
        Renders the detailed view listing all favorite composers.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_composers_sort_mode"):
            mw.favorite_composers_sort_mode = SortMode.DATE_ADDED_DESC
        if not hasattr(mw, "favorite_composers_view_mode"):
            mw.favorite_composers_view_mode = ViewMode.GRID

        is_refresh = (
            mw.current_favorites_context == "all_composers"
            and mw.favorite_detail_layout.count() > 0
            and mw.favorites_stack.currentIndex() == 1
        )

        if not is_refresh:
            mw.current_favorites_context = "all_composers"
            self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
            self.ui_manager.clear_layout(mw.favorite_detail_layout)

        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
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

        control_widgets = []
        if not is_refresh:
            sort_options = [
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
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]
            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.favorite_composers_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_composers_sort_mode", action.data()),
                    self.show_all_favorite_composers_view(),
                )
            )
            set_custom_tooltip(
                sort_button,
                title = translate("Sort Options"),
            )

            view_button = self.components.create_tool_button_with_menu(
                [
                    (
                        translate("Grid"),
                        create_svg_icon(
                            "assets/control/view_grid.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.GRID,
                    ),
                    (
                        translate("Tile"),
                        create_svg_icon(
                            "assets/control/view_tile.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_BIG,
                    ),
                    (
                        translate("Small Tile"),
                        create_svg_icon(
                            "assets/control/view_tile_small.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_SMALL,
                    ),
                ],
                mw.favorite_composers_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_composers_view_mode", action.data()),
                    self.show_all_favorite_composers_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            control_widgets = [sort_button, view_button]

        favorites = mw.library_manager.load_favorites()
        fav_composers_dict = favorites.get("composers", {})
        items = list(fav_composers_dict.keys())

        if mw.favorite_composers_sort_mode == SortMode.ALPHA_ASC:
            items.sort(key=mw.data_manager.get_sort_key)
        elif mw.favorite_composers_sort_mode == SortMode.ALPHA_DESC:
            items.sort(key=mw.data_manager.get_sort_key, reverse=True)
        elif mw.favorite_composers_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda k: fav_composers_dict.get(k, 0))
        else:
            items.sort(key=lambda k: fav_composers_dict.get(k, 0), reverse=True)

        mw.composer_letters = set()
        if mw.show_favorites_separators:
            for composer_name in items:
                current_group = None
                if mw.favorite_composers_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    sort_name = mw.data_manager.get_sort_key(composer_name)
                    first_char = sort_name[0] if sort_name else "*"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.favorite_composers_sort_mode in [
                    SortMode.DATE_ADDED_DESC,
                    SortMode.DATE_ADDED_ASC,
                ]:
                    ts = fav_composers_dict.get(composer_name, 0)
                    current_group = self.ui_manager._format_date_added_group(ts)

                if current_group:
                    mw.composer_letters.add(current_group)

        mw.favorite_detail_separator_widgets.clear()

        mw.current_fav_all_composers_list = items
        mw.fav_all_composers_loaded_count = 0
        mw.is_loading_fav_all_composers = False
        mw.last_fav_all_composers_group = None
        mw.current_fav_all_composers_flow_layout = None

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=translate("All Favorite Composers"),
                details_text=translate("{count} composer(s)", count=len(items)),
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_favorite_composers",
                context_menu_data=("all_favorite_composers", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_favorite_composers")
                )
                mw.main_view_header_play_buttons["all_favorite_composers"] = play_button

            self.fav_composers_details_label = header_parts["details"]
            mw.favorite_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.favorite_detail_scroll_area = scroll_area
            mw.favorite_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "fav_composers_details_label"):
                self.fav_composers_details_label.setText(
                    translate("{count} composer(s)", count=len(items))
                )

        if mw.favorite_detail_scroll_area.widget():
            mw.favorite_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        mw.favorite_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No favorite composers found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_favorite_composers
                )
            )
            self.load_more_favorite_composers()

        if not is_refresh:
            mw.favorites_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("favorite"),
                context_data={"context": "all_composers"},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_favorite_composers(self):
        """
        Loads the next batch of favorite composers for infinite scrolling.
        """
        mw = self.main_window
        if mw.is_loading_fav_all_composers:
            return
        if mw.fav_all_composers_loaded_count >= len(mw.current_fav_all_composers_list):
            return

        mw.is_loading_fav_all_composers = True
        start = mw.fav_all_composers_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_fav_all_composers_list))

        container = mw.favorite_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            composer_name = mw.current_fav_all_composers_list[i]

            current_group = None
            if mw.favorite_composers_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                sort_name = mw.data_manager.get_sort_key(composer_name)
                first_char = sort_name[0] if sort_name else "*"
                current_group = first_char.upper() if first_char.isalpha() else "*"
            elif mw.favorite_composers_sort_mode in [
                SortMode.DATE_ADDED_DESC,
                SortMode.DATE_ADDED_ASC,
            ]:
                ts = mw.favorites["composers"].get(composer_name, 0)
                current_group = self.ui_manager._format_date_added_group(ts)

            if (
                mw.show_favorites_separators
                and current_group != mw.last_fav_all_composers_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "favorite_composers", mw.composer_letters
                )
                main_layout.addWidget(separator_widget)
                mw.favorite_detail_separator_widgets[current_group] = separator_widget
                mw.last_fav_all_composers_group = current_group
                mw.current_fav_all_composers_flow_layout = None

            target_layout = main_layout
            if mw.favorite_composers_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_fav_all_composers_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_fav_all_composers_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_fav_all_composers_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_fav_all_composers_flow_layout

            if comp_data := mw.data_manager.composers_data.get(composer_name):
                widget = self.components.create_composer_widget(
                    composer_name, comp_data, mw.favorite_composers_view_mode
                )
                widget.activated.connect(
                    partial(self.show_favorite_composer_albums_view, composer_name)
                )

                widget.contextMenuRequested.connect(
                    lambda data, pos: mw.action_handler.show_context_menu(
                        data, pos, context={"forced_type": "composer"}
                    )
                )

                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "composer", "data": d}
                    )
                )
                target_layout.addWidget(widget)

        mw.fav_all_composers_loaded_count = end
        mw.is_loading_fav_all_composers = False

        if end >= len(mw.current_fav_all_composers_list):
            if mw.favorite_composers_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_fav_composers)

    def _check_for_more_fav_composers(self):
        """
        Periodically checks if more favorite composers need to be loaded to fill the scroll view.
        """
        mw = self.main_window
        if not mw.favorite_detail_scroll_area.widget():
            return
        scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
        has_more = mw.fav_all_composers_loaded_count < len(
            mw.current_fav_all_composers_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_favorite_composers()

    def show_favorite_composer_albums_view(self, composer_name):
        """
        Renders a detailed view showing all albums belonging to a specific favorite composer.

        Args:
            composer_name: The name of the composer to display albums for.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_composer_album_sort_mode"):
            mw.favorite_composer_album_sort_mode = SortMode.YEAR_DESC
        if not hasattr(mw, "favorite_composer_album_view_mode"):
            mw.favorite_composer_album_view_mode = ViewMode.GRID

        mw.current_composer_view = composer_name
        mw.current_favorites_context = "composer"
        self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
        self.ui_manager.clear_layout(mw.favorite_detail_layout)

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

        sort_button = self.components.create_tool_button_with_menu(
            [
                (
                    translate("By year (newest first)"),
                    sort_year_desc,
                    SortMode.YEAR_DESC,
                ),
                (translate("By year (oldest first)"), sort_year_asc, SortMode.YEAR_ASC),
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ],
            mw.favorite_composer_album_sort_mode,
        )
        sort_button.setFixedHeight(36)
        sort_button.menu().triggered.connect(
            lambda action: (
                setattr(mw, "favorite_composer_album_sort_mode", action.data()),
                self.show_favorite_composer_albums_view(composer_name),
            )
        )
        set_custom_tooltip(
            sort_button,
            title = translate("Sort Options"),
        )

        view_button = self.components.create_tool_button_with_menu(
            [
                (
                    translate("Grid"),
                    create_svg_icon(
                        "assets/control/view_grid.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.GRID,
                ),
                (
                    translate("Tile"),
                    create_svg_icon(
                        "assets/control/view_tile.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.TILE_BIG,
                ),
                (
                    translate("Small Tile"),
                    create_svg_icon(
                        "assets/control/view_tile_small.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.TILE_SMALL,
                ),
                (
                    translate("All tracks"),
                    create_svg_icon(
                        "assets/control/view_album_tracks.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.ALL_TRACKS,
                ),
            ],
            mw.favorite_composer_album_view_mode,
        )
        view_button.setFixedHeight(36)
        view_button.menu().triggered.connect(
            lambda action: (
                setattr(mw, "favorite_composer_album_view_mode", action.data()),
                self.show_favorite_composer_albums_view(composer_name),
            )
        )
        set_custom_tooltip(
            view_button,
            title = translate("View Options"),
        )
        fav_button = self.components._create_favorite_button(composer_name, "composer")

        comp_data = mw.data_manager.composers_data.get(composer_name, {})
        album_keys = comp_data.get("albums", [])

        albums_of_composer = []
        for key in album_keys:
            t_key = tuple(key) if isinstance(key, list) else key
            if t_key in mw.data_manager.albums_data:
                albums_of_composer.append((t_key, mw.data_manager.albums_data[t_key]))

        album_count = len(albums_of_composer)
        track_count = comp_data.get("track_count", 0)
        albums_text = translate("{count} album(s)", count=album_count)
        tracks_text = translate("{count} track(s)", count=track_count)
        details_text = f"{albums_text}, {tracks_text}"

        header_parts = self.components.create_page_header(
            translate("{name}: Albums", name=composer_name),
            details_text=details_text,
            back_slot=self.ui_manager.navigate_back,
            control_widgets=[fav_button, sort_button, view_button],
            play_slot_data={"type": "composer", "data": composer_name},
            context_menu_data=(composer_name, "composer"),
        )
        if play_button := header_parts.get("play_button"):
            play_button.clicked.connect(
                lambda: mw.player_controller.play_data(
                    {"type": "composer", "data": composer_name}
                )
            )
            mw.main_view_header_play_buttons[composer_name] = play_button

        composer_cover_button = EntityCoverButton(
            composer_name,
            comp_data,
            albums_of_composer,
            "composer",
            self.components.get_pixmap,
            main_window = mw
        )
        composer_cover_button.artworkChanged.connect(
            mw.action_handler.handle_composer_artwork_changed
        )
        header_parts["header"].layout().insertWidget(
            1, composer_cover_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        mw.favorite_detail_header_layout.addWidget(header_parts["header"])

        sort_mode = mw.favorite_composer_album_sort_mode
        if sort_mode == SortMode.ALPHA_ASC:
            albums_of_composer.sort(key=lambda x: mw.data_manager.get_sort_key(x[0][1]))
        elif sort_mode == SortMode.ALPHA_DESC:
            albums_of_composer.sort(
                key=lambda x: mw.data_manager.get_sort_key(x[0][1]), reverse=True
            )
        elif sort_mode == SortMode.YEAR_ASC:
            albums_of_composer.sort(
                key=lambda x: (
                    x[1].get("year", 9999),
                    mw.data_manager.get_sort_key(x[0][1]),
                )
            )
        elif sort_mode == SortMode.YEAR_DESC:
            albums_of_composer.sort(
                key=lambda x: (
                    x[1].get("year", 0),
                    mw.data_manager.get_sort_key(x[0][1]),
                ),
                reverse=True,
            )

        mw.current_fav_composer_album_list = albums_of_composer
        mw.fav_composer_albums_loaded_count = 0
        mw.is_loading_fav_composer_albums = False

        scroll_area = StyledScrollArea()
        scroll_area.setProperty("class", "backgroundPrimary")
        scroll_area.setWidgetResizable(True)
        mw.fav_sub_view_scroll_area = scroll_area

        self._populate_favorite_sub_view_lazy(
            scroll_area,
            "favorite_composer_album_view_mode",
            enc_key=composer_name,
            enc_type="composer",
            enc_refresh_callback=lambda: self.show_favorite_composer_albums_view(
                composer_name
            ),
        )

        scroll_bar = scroll_area.verticalScrollBar()
        scroll_bar.valueChanged.connect(
            lambda value: self.ui_manager.check_scroll_and_load(
                value, scroll_bar, self.load_more_fav_composer_albums
            )
        )
        self.load_more_fav_composer_albums()

        mw.favorite_detail_layout.addWidget(scroll_area)
        mw.favorites_stack.setCurrentIndex(1)
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("favorite"),
            context_data={"context": "composer", "data": composer_name},
        )
        self.ui_manager.update_all_track_widgets()

    def load_more_fav_composer_albums(self):
        """
        Loads the next batch of composer albums for infinite scrolling.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "active_fav_layout_target")
            or mw.active_fav_layout_target is None
        ):
            return
        if mw.is_loading_fav_composer_albums:
            return
        if mw.fav_composer_albums_loaded_count >= len(
            mw.current_fav_composer_album_list
        ):
            return

        mw.is_loading_fav_composer_albums = True
        batch = (
            BATCH_SIZE_ALLTRACKS
            if mw.favorite_composer_album_view_mode == ViewMode.ALL_TRACKS
            else BATCH_SIZE
        )
        start = mw.fav_composer_albums_loaded_count
        end = min(start + batch, len(mw.current_fav_composer_album_list))

        layout = mw.active_fav_layout_target

        for i in range(start, end):
            album_key, data = mw.current_fav_composer_album_list[i]
            if mw.favorite_composer_album_view_mode == ViewMode.ALL_TRACKS:
                widget = self.components._create_detailed_album_widget(
                    album_key, data, tracks_to_show=None
                )
                layout.addWidget(widget)
                if i < len(mw.current_fav_composer_album_list) - 1:
                    separator = QWidget()
                    separator.setFixedHeight(1)
                    separator.setProperty("class", "separator")
                    layout.addWidget(separator)
            else:
                widget = self.components.create_album_widget(
                    album_key, data, mw.favorite_composer_album_view_mode, show_artist=True
                )
                widget.activated.connect(
                    partial(self._show_album_details_safe, album_key)
                )
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "album"}
                    )
                )
                widget.playClicked.connect(mw.player_controller.play_data)
                layout.addWidget(widget)

        mw.fav_composer_albums_loaded_count = end
        mw.is_loading_fav_composer_albums = False
        QTimer.singleShot(100, self._check_for_more_fav_composer_albums)

    def _check_for_more_fav_composer_albums(self):
        """
        Periodically checks if more composer albums need to be loaded to fill the scroll view.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "fav_sub_view_scroll_area")
            or not mw.fav_sub_view_scroll_area.widget()
        ):
            return
        scroll_bar = mw.fav_sub_view_scroll_area.verticalScrollBar()
        has_more = mw.fav_composer_albums_loaded_count < len(
            mw.current_fav_composer_album_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_fav_composer_albums()

    def show_all_favorite_genres_view(self):
        """
        Renders the detailed view listing all favorite genres.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_genres_sort_mode"):
            mw.favorite_genres_sort_mode = SortMode.DATE_ADDED_DESC
        if not hasattr(mw, "favorite_genres_view_mode"):
            mw.favorite_genres_view_mode = ViewMode.GRID

        is_refresh = (
            mw.current_favorites_context == "all_genres"
            and mw.favorite_detail_layout.count() > 0
            and mw.favorites_stack.currentIndex() == 1
        )

        if not is_refresh:
            mw.current_favorites_context = "all_genres"
            self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
            self.ui_manager.clear_layout(mw.favorite_detail_layout)

        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
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

        control_widgets = []
        if not is_refresh:
            sort_options = [
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
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]
            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.favorite_genres_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_genres_sort_mode", action.data()),
                    self.show_all_favorite_genres_view(),
                )
            )
            set_custom_tooltip(
                sort_button,
                title = translate("Sort Options"),
            )

            view_button = self.components.create_tool_button_with_menu(
                [
                    (
                        translate("Grid"),
                        create_svg_icon(
                            "assets/control/view_grid.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.GRID,
                    ),
                    (
                        translate("Tile"),
                        create_svg_icon(
                            "assets/control/view_tile.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_BIG,
                    ),
                    (
                        translate("Small Tile"),
                        create_svg_icon(
                            "assets/control/view_tile_small.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_SMALL,
                    ),
                ],
                mw.favorite_genres_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_genres_view_mode", action.data()),
                    self.show_all_favorite_genres_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            control_widgets = [sort_button, view_button]

        favorites = mw.library_manager.load_favorites()
        fav_genres_dict = favorites.get("genres", {})
        items = list(fav_genres_dict.keys())

        if mw.favorite_genres_sort_mode == SortMode.ALPHA_ASC:
            items.sort(key=mw.data_manager.get_sort_key)
        elif mw.favorite_genres_sort_mode == SortMode.ALPHA_DESC:
            items.sort(key=mw.data_manager.get_sort_key, reverse=True)
        elif mw.favorite_genres_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda k: fav_genres_dict.get(k, 0))
        else:
            items.sort(key=lambda k: fav_genres_dict.get(k, 0), reverse=True)

        mw.genre_letters = set()
        if mw.show_favorites_separators:
            for genre_name in items:
                current_group = None
                if mw.favorite_genres_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    sort_name = mw.data_manager.get_sort_key(genre_name)
                    first_char = sort_name[0] if sort_name else "*"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.favorite_genres_sort_mode in [
                    SortMode.DATE_ADDED_DESC,
                    SortMode.DATE_ADDED_ASC,
                ]:
                    ts = fav_genres_dict.get(genre_name, 0)
                    current_group = self.ui_manager._format_date_added_group(ts)

                if current_group:
                    mw.genre_letters.add(current_group)

        mw.favorite_detail_separator_widgets.clear()

        mw.current_fav_all_genres_list = items
        mw.fav_all_genres_loaded_count = 0
        mw.is_loading_fav_all_genres = False
        mw.last_fav_all_genres_group = None
        mw.current_fav_all_genres_flow_layout = None

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=translate("All Favorite Genres"),
                details_text=translate("{count} genre(s)", count=len(items)),
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_favorite_genres",
                context_menu_data=("all_favorite_genres", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_favorite_genres")
                )
                mw.main_view_header_play_buttons["all_favorite_genres"] = play_button

            self.fav_genres_details_label = header_parts["details"]
            mw.favorite_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.favorite_detail_scroll_area = scroll_area
            mw.favorite_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "fav_genres_details_label"):
                self.fav_genres_details_label.setText(
                    translate("{count} genre(s)", count=len(items))
                )

        if mw.favorite_detail_scroll_area.widget():
            mw.favorite_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        mw.favorite_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No favorite genres found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_favorite_genres
                )
            )
            self.load_more_favorite_genres()

        if not is_refresh:
            mw.favorites_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("favorite"),
                context_data={"context": "all_genres"},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_favorite_genres(self):
        """
        Loads the next batch of favorite genres for infinite scrolling.
        """
        mw = self.main_window
        if mw.is_loading_fav_all_genres:
            return
        if mw.fav_all_genres_loaded_count >= len(mw.current_fav_all_genres_list):
            return

        mw.is_loading_fav_all_genres = True
        start = mw.fav_all_genres_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_fav_all_genres_list))

        container = mw.favorite_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            genre_name = mw.current_fav_all_genres_list[i]

            current_group = None
            if mw.favorite_genres_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                sort_name = mw.data_manager.get_sort_key(genre_name)
                first_char = sort_name[0] if sort_name else "*"
                current_group = first_char.upper() if first_char.isalpha() else "*"
            elif mw.favorite_genres_sort_mode in [
                SortMode.DATE_ADDED_DESC,
                SortMode.DATE_ADDED_ASC,
            ]:
                ts = mw.favorites["genres"].get(genre_name, 0)
                current_group = self.ui_manager._format_date_added_group(ts)

            if (
                mw.show_favorites_separators
                and current_group != mw.last_fav_all_genres_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "favorite_genres", mw.genre_letters
                )
                main_layout.addWidget(separator_widget)
                mw.favorite_detail_separator_widgets[current_group] = separator_widget
                mw.last_fav_all_genres_group = current_group
                mw.current_fav_all_genres_flow_layout = None

            target_layout = main_layout
            if mw.favorite_genres_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_fav_all_genres_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_fav_all_genres_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_fav_all_genres_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_fav_all_genres_flow_layout

            if genre_data := mw.data_manager.genres_data.get(genre_name):
                widget = self.components.create_genre_widget(
                    genre_name, genre_data, mw.favorite_genres_view_mode
                )
                widget.activated.connect(
                    partial(self.show_favorite_genre_albums_view, genre_name)
                )

                widget.contextMenuRequested.connect(
                    lambda data, pos: mw.action_handler.show_context_menu(
                        data, pos, context={"forced_type": "genre"}
                    )
                )

                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "genre", "data": d}
                    )
                )
                target_layout.addWidget(widget)

        mw.fav_all_genres_loaded_count = end
        mw.is_loading_fav_all_genres = False

        if end >= len(mw.current_fav_all_genres_list):
            if mw.favorite_genres_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_fav_genres)

    def _check_for_more_fav_genres(self):
        """
        Periodically checks if more favorite genres need to be loaded to fill the scroll view.
        """
        mw = self.main_window
        if not mw.favorite_detail_scroll_area.widget():
            return
        scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
        has_more = mw.fav_all_genres_loaded_count < len(mw.current_fav_all_genres_list)
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_favorite_genres()

    def show_all_favorite_folders_view(self):
        """
        Renders the detailed view listing all favorite folders.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_folders_sort_mode"):
            mw.favorite_folders_sort_mode = SortMode.DATE_ADDED_DESC
        if not hasattr(mw, "favorite_folders_view_mode"):
            mw.favorite_folders_view_mode = ViewMode.GRID

        is_refresh = (
            mw.current_favorites_context == "all_folders"
            and mw.favorite_detail_layout.count() > 0
            and mw.favorites_stack.currentIndex() == 1
        )

        if not is_refresh:
            mw.current_favorites_context = "all_folders"
            self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
            self.ui_manager.clear_layout(mw.favorite_detail_layout)

        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
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

        control_widgets = []
        if not is_refresh:
            sort_options = [
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
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]
            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.favorite_folders_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_folders_sort_mode", action.data()),
                    self.show_all_favorite_folders_view(),
                )
            )
            set_custom_tooltip(
                sort_button,
                title = translate("Sort Options"),
            )

            view_button = self.components.create_tool_button_with_menu(
                [
                    (
                        translate("Grid"),
                        create_svg_icon(
                            "assets/control/view_grid.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.GRID,
                    ),
                    (
                        translate("Tile"),
                        create_svg_icon(
                            "assets/control/view_tile.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_BIG,
                    ),
                    (
                        translate("Small Tile"),
                        create_svg_icon(
                            "assets/control/view_tile_small.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        ),
                        ViewMode.TILE_SMALL,
                    ),
                ],
                mw.favorite_folders_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_folders_view_mode", action.data()),
                    self.show_all_favorite_folders_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            control_widgets = [sort_button, view_button]

        favorites = mw.library_manager.load_favorites()
        fav_folders_dict = favorites.get("folders", {})
        items = list(fav_folders_dict.keys())

        if mw.favorite_folders_sort_mode == SortMode.ALPHA_ASC:
            items.sort(key=lambda p: mw.data_manager.get_sort_key(os.path.basename(p)))
        elif mw.favorite_folders_sort_mode == SortMode.ALPHA_DESC:
            items.sort(
                key=lambda p: mw.data_manager.get_sort_key(os.path.basename(p)),
                reverse=True,
            )
        elif mw.favorite_folders_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda k: fav_folders_dict.get(k, 0))
        else:
            items.sort(key=lambda k: fav_folders_dict.get(k, 0), reverse=True)

        mw.folder_groups = set()
        if mw.show_favorites_separators:
            for path in items:
                current_group = None
                if mw.favorite_folders_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    p_name = os.path.basename(path)
                    sort_name = mw.data_manager.get_sort_key(p_name)
                    first_char = sort_name[0] if sort_name else "*"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.favorite_folders_sort_mode in [
                    SortMode.DATE_ADDED_DESC,
                    SortMode.DATE_ADDED_ASC,
                ]:
                    ts = fav_folders_dict.get(path, 0)
                    current_group = self.ui_manager._format_date_added_group(ts)

                if current_group:
                    mw.folder_groups.add(current_group)

        mw.favorite_detail_separator_widgets.clear()

        mw.current_fav_all_folders_list = items
        mw.fav_all_folders_loaded_count = 0
        mw.is_loading_fav_all_folders = False
        mw.last_fav_all_folders_group = None
        mw.current_fav_all_folders_flow_layout = None

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=translate("All Favorite Folders"),
                details_text=translate("{count} folder(s)", count=len(items)),
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_favorite_folders",
                context_menu_data=("all_favorite_folders", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_favorite_folders")
                )
                mw.main_view_header_play_buttons["all_favorite_folders"] = play_button

            self.fav_folders_details_label = header_parts["details"]
            mw.favorite_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.favorite_detail_scroll_area = scroll_area
            mw.favorite_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "fav_folders_details_label"):
                self.fav_folders_details_label.setText(
                    translate("{count} folder(s)", count=len(items))
                )

        if mw.favorite_detail_scroll_area.widget():
            mw.favorite_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        mw.favorite_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No favorite folders found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_favorite_folders
                )
            )
            self.load_more_favorite_folders()

        if not is_refresh:
            mw.favorites_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("favorite"),
                context_data={"context": "all_folders"},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_favorite_folders(self):
        """
        Loads the next batch of favorite folders for infinite scrolling.
        """
        mw = self.main_window
        if mw.is_loading_fav_all_folders:
            return
        if mw.fav_all_folders_loaded_count >= len(mw.current_fav_all_folders_list):
            return

        mw.is_loading_fav_all_folders = True
        start = mw.fav_all_folders_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_fav_all_folders_list))

        container = mw.favorite_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            path = mw.current_fav_all_folders_list[i]

            current_group = None
            if mw.favorite_folders_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                p_name = os.path.basename(path)
                sort_name = mw.data_manager.get_sort_key(p_name)
                first_char = sort_name[0] if sort_name else "*"
                current_group = first_char.upper() if first_char.isalpha() else "*"
            elif mw.favorite_folders_sort_mode in [
                SortMode.DATE_ADDED_DESC,
                SortMode.DATE_ADDED_ASC,
            ]:
                ts = mw.favorites["folders"].get(path, 0)
                current_group = self.ui_manager._format_date_added_group(ts)

            if (
                mw.show_favorites_separators
                and current_group
                and current_group != mw.last_fav_all_folders_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "all_favorite_folders", mw.folder_groups
                )
                main_layout.addWidget(separator_widget)
                mw.favorite_detail_separator_widgets[current_group] = separator_widget
                mw.last_fav_all_folders_group = current_group
                mw.current_fav_all_folders_flow_layout = None

            target_layout = main_layout
            if mw.favorite_folders_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_fav_all_folders_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_fav_all_folders_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_fav_all_folders_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_fav_all_folders_flow_layout

            folder_name = os.path.basename(path) or path
            artwork_dicts = self.ui_manager.get_artworks_for_directory(path)
            widget = self.components.create_directory_widget(
                folder_name, path, mw.favorite_folders_view_mode, artwork_dicts
            )
            widget.activated.connect(partial(self.show_favorite_folder_view, path))
            widget.contextMenuRequested.connect(mw.action_handler.show_context_menu)
            widget.playClicked.connect(mw.player_controller.play_data)
            target_layout.addWidget(widget)

        mw.fav_all_folders_loaded_count = end
        mw.is_loading_fav_all_folders = False

        if end >= len(mw.current_fav_all_folders_list):
            if mw.favorite_folders_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_fav_folders)

    def _check_for_more_fav_folders(self):
        """
        Periodically checks if more favorite folders need to be loaded to fill the scroll view.
        """
        mw = self.main_window
        if not mw.favorite_detail_scroll_area.widget():
            return
        scroll_bar = mw.favorite_detail_scroll_area.verticalScrollBar()
        has_more = mw.fav_all_folders_loaded_count < len(
            mw.current_fav_all_folders_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_favorite_folders()

    def show_favorite_tracks_view(self, data=None):
        """
        Renders the detailed view containing all favorite tracks as a playlist, with sort controls.

        Args:
            data: Optional data payload, usually ignored in this context.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_tracks_sort_mode"):
            mw.favorite_tracks_sort_mode = SortMode.DATE_ADDED_DESC

        is_refresh = (
            mw.current_favorites_context == "tracks"
            and mw.favorite_detail_layout.count() > 0
            and mw.favorites_stack.currentIndex() == 1
        )

        if not is_refresh:
            mw.current_favorites_context = "tracks"
            self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
            self.ui_manager.clear_layout(mw.favorite_detail_layout)

        sort_date_added_desc = create_svg_icon(
            "assets/control/sort_date_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_date_added_asc = create_svg_icon(
            "assets/control/sort_date_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_artist_asc = create_svg_icon(
            "assets/control/sort_artist_alpha_asc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_artist_desc = create_svg_icon(
            "assets/control/sort_artist_alpha_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )

        control_widgets = []
        if not is_refresh:
            sort_options = [
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
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
                (translate("By artist (A-Z)"), sort_artist_asc, SortMode.ARTIST_ASC),
                (translate("By artist (Z-A)"), sort_artist_desc, SortMode.ARTIST_DESC),
            ]
            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.favorite_tracks_sort_mode
            )
            sort_button.setFixedHeight(36)
            sort_button.menu().triggered.connect(mw.set_favorite_tracks_sort_mode)
            set_custom_tooltip(
                sort_button,
                title = translate("Sort Options"),
            )
            control_widgets = [sort_button]

        fav_tracks_dict = mw.library_manager.load_favorites().get("tracks", {})
        track_objects = []
        for path in fav_tracks_dict:
            if path in mw.data_manager.path_to_track_map:
                track = mw.data_manager.get_track_by_path(path)
                track_objects.append(track)

        if mw.favorite_tracks_sort_mode == SortMode.DATE_ADDED_DESC:
            track_objects.sort(
                key=lambda t: fav_tracks_dict.get(t["path"], 0), reverse=True
            )
        elif mw.favorite_tracks_sort_mode == SortMode.DATE_ADDED_ASC:
            track_objects.sort(key=lambda t: fav_tracks_dict.get(t["path"], 0))
        elif mw.favorite_tracks_sort_mode == SortMode.ALPHA_ASC:
            track_objects.sort(
                key=lambda t: mw.data_manager.get_sort_key(t.get("title", ""))
            )
        elif mw.favorite_tracks_sort_mode == SortMode.ALPHA_DESC:
            track_objects.sort(
                key=lambda t: mw.data_manager.get_sort_key(t.get("title", "")),
                reverse=True,
            )
        elif mw.favorite_tracks_sort_mode == SortMode.ARTIST_ASC:
            track_objects.sort(
                key=lambda t: (
                    mw.data_manager.get_sort_key(t.get("artist", "")),
                    mw.data_manager.get_sort_key(t.get("title", "")),
                )
            )
        elif mw.favorite_tracks_sort_mode == SortMode.ARTIST_DESC:
            track_objects.sort(
                key=lambda t: (
                    mw.data_manager.get_sort_key(t.get("artist", "")),
                    mw.data_manager.get_sort_key(t.get("title", "")),
                ),
                reverse=True,
            )

        details_text = translate("{count} track(s)", count=len(track_objects))

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=translate("Favorite Tracks"),
                details_text=details_text,
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="favorite_tracks",
                context_menu_data=("favorite_tracks", "favorite_tracks"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("favorite_tracks")
                )
                mw.main_view_header_play_buttons["favorite_tracks"] = play_button

            self.fav_tracks_details_label = header_parts["details"]
            mw.favorite_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.favorite_detail_scroll_area = scroll_area
            mw.favorite_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "fav_tracks_details_label"):
                self.fav_tracks_details_label.setText(details_text)

        if mw.favorite_detail_scroll_area.widget():
            mw.favorite_detail_scroll_area.widget().deleteLater()

        if not track_objects:
            container = QWidget()
            container.setProperty("class", "backgroundPrimary")
            layout = QVBoxLayout(container)
            text_label = QLabel(translate("No favorite tracks found."))
            text_label.setProperty("class", "textColorPrimary")
            layout.addWidget(text_label)
            layout.addStretch(1)
            mw.favorite_detail_scroll_area.setWidget(container)
        else:
            playlist_widget = self.components._create_detailed_playlist_widget(
                playlist_path="favorite_tracks",
                playlist_name=translate("Favorite Tracks"),
                tracks=track_objects,
                pixmap=self.components.favorite_cover_pixmap,
            )

            try:
                playlist_widget.playlistContextMenu.disconnect()
            except Exception:
                pass

            playlist_widget.playlistContextMenu.connect(
                mw.action_handler.show_favorite_tracks_card_context_menu
            )

            playlist_widget.setContentsMargins(24, 24, 24, 24)
            mw.favorite_detail_scroll_area.setWidget(playlist_widget)

        if not is_refresh:
            mw.favorites_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("favorite"),
                context_data={"context": "tracks"},
            )
        self.ui_manager.update_all_track_widgets()

    def show_favorite_playlist_view(self, playlist_path):
        """
        Renders the detailed view displaying the contents of a specific favorite playlist.

        Args:
            playlist_path: The file path to the playlist.
        """
        mw = self.main_window

        mw.current_favorites_context = "playlist"
        self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
        self.ui_manager.clear_layout(mw.favorite_detail_layout)

        playlist_name = os.path.splitext(os.path.basename(playlist_path))[0]
        tracks = mw.library_manager.load_playlist(
            playlist_path, mw.data_manager.path_to_track_map
        )
        track_count = len(tracks)
        details_text = translate("{count} track(s)", count=track_count)

        fav_button = self.components._create_favorite_button(playlist_path, "playlist")

        header_parts = self.components.create_page_header(
            title=playlist_name,
            details_text=details_text,
            back_slot=self.ui_manager.navigate_back,
            control_widgets=[fav_button],
            play_slot_data=playlist_path,
            context_menu_data=(playlist_path, "playlist"),
        )
        if play_button := header_parts.get("play_button"):
            play_button.clicked.connect(
                lambda: mw.player_controller.play_data(playlist_path)
            )
            mw.main_view_header_play_buttons[playlist_path] = play_button
        mw.favorite_detail_header_layout.addWidget(header_parts["header"])

        if not tracks:
            text_label = QLabel(translate("Could not load tracks from playlist."))
            text_label.setProperty("class", "textColorPrimary")
            mw.favorite_detail_layout.addWidget(text_label)
        else:
            scroll_area = StyledScrollArea()
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)

            playlist_widget = self.components._create_detailed_playlist_widget(
                playlist_path, playlist_name, tracks
            )
            playlist_widget.setContentsMargins(24, 24, 24, 24)
            scroll_area.setWidget(playlist_widget)
            mw.favorite_detail_layout.addWidget(scroll_area, 1)

        mw.favorites_stack.setCurrentIndex(1)
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("favorite"),
            context_data={"context": "playlist", "data": playlist_path},
        )
        self.ui_manager.update_all_track_widgets()

    def show_favorite_folder_view(self, path):
        """
        Initiates navigation into a favorite folder's detail view.

        Args:
            path: Directory path of the favorite folder.
        """
        mw = self.main_window

        mw.current_favorites_context = "folder"
        self._navigate_in_favorite_folder(path)

    def _navigate_in_favorite_folder(self, path):
        """
        Renders the contents of a specific folder within the favorites view, parsing nested items
        and grouping tracks by album if it's the final level.

        Args:
            path: Directory path to inspect and render.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_folders_view_mode"):
            mw.favorite_folders_view_mode = ViewMode.GRID

        mw.current_favorite_folder_path_nav = path
        self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
        self.ui_manager.clear_layout(mw.favorite_detail_layout)

        fav_button = self.components._create_favorite_button(path, "folder")
        header_parts = self.components.create_page_header(
            title=os.path.basename(path) or path,
            back_slot=self.ui_manager.navigate_back,
            control_widgets=[fav_button],
            play_slot_data=path,
            context_menu_data=(path, "folder"),
        )
        if play_button := header_parts.get("play_button"):
            play_button.clicked.connect(lambda: mw.player_controller.play_data(path))
            mw.main_view_header_play_buttons[path] = play_button
        mw.favorite_detail_header_layout.addWidget(header_parts["header"])

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setProperty("class", "backgroundPrimary")
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        mw.favorite_detail_layout.addWidget(scroll_area, 1)
        mw.favorites_stack.setCurrentIndex(1)
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("favorite"),
            context_data={"context": "folder", "data": path},
        )

        try:
            is_final_directory = not any(
                os.path.isdir(os.path.join(path, entry))
                and mw.action_handler.has_music_files(os.path.join(path, entry))
                for entry in os.listdir(path)
            )
        except OSError:
            is_final_directory = False

        if is_final_directory:
            container = QWidget()
            container.setContentsMargins(24, 24, 24, 24)
            container.setProperty("class", "backgroundPrimary")
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(24)
            scroll_area.setWidget(container)

            norm_path = os.path.normpath(path)
            tracks_in_dir = [
                t
                for t in mw.data_manager.all_tracks
                if os.path.normpath(t["path"]).startswith(norm_path + os.sep)
            ]

            if not tracks_in_dir:
                text_label = QLabel(translate("There is no music in this folder"))
                text_label.setProperty("class", "textColorPrimary")
                container_layout.addWidget(
                    text_label, alignment=Qt.AlignmentFlag.AlignCenter
                )
            else:
                grouped_by_album = defaultdict(list)
                for track in tracks_in_dir:
                    if mw.treat_folders_as_unique:
                        album_key = (
                            track.get("album_artist", translate("Unknown")),
                            track.get("album", translate("Unknown Album")),
                            norm_path,
                        )
                    else:
                        album_key = (
                            track.get("album_artist", translate("Unknown")),
                            track.get("album", translate("Unknown Album")),
                        )
                    grouped_by_album[album_key].append(track)

                sorted_albums = sorted(
                    grouped_by_album.items(),
                    key=lambda item: (
                        mw.data_manager.get_sort_key(item[0][0]),
                        mw.data_manager.get_sort_key(item[0][1]),
                    ),
                )

                for i, (album_key, album_tracks) in enumerate(sorted_albums):
                    full_album_data = mw.data_manager.albums_data.get(album_key)
                    if not full_album_data:
                        sample_track = album_tracks[0]
                        full_album_data = {
                            "album_artist": album_key[0],
                            "artwork": sample_track.get("artwork"),
                            "year": sample_track.get("year"),
                            "track_count": len(album_tracks),
                            "total_duration": sum(
                                t.get("duration", 0) for t in album_tracks
                            ),
                        }
                    album_widget = self.components._create_detailed_album_widget(
                        album_key, full_album_data, tracks_to_show=album_tracks
                    )
                    container_layout.addWidget(album_widget)
                    if i < len(sorted_albums) - 1:
                        separator = QWidget()
                        separator.setFixedHeight(1)
                        separator.setProperty("class", "separator")
                        container_layout.addWidget(separator)
                container_layout.addStretch(1)
        else:
            container = QWidget()
            container.setContentsMargins(24, 24, 24, 24)
            container.setProperty("class", "backgroundPrimary")
            container_layout = FlowLayout(container, stretch_items=True)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(16)
            scroll_area.setWidget(container)

            try:
                entries = sorted(
                    [
                        entry
                        for entry in os.listdir(path)
                        if os.path.isdir(os.path.join(path, entry))
                    ],
                    key=mw.data_manager.get_sort_key,
                )
                for entry in entries:
                    full_path = os.path.join(path, entry)
                    if mw.action_handler.has_music_files(full_path):
                        artwork_dicts = self.ui_manager.get_artworks_for_directory(
                            full_path
                        )
                        widget = self.components.create_directory_widget(
                            entry, full_path, mw.favorite_folders_view_mode, artwork_dicts
                        )
                        widget.activated.connect(self._navigate_in_favorite_folder)
                        widget.playClicked.connect(mw.player_controller.play_data)
                        widget.contextMenuRequested.connect(
                            mw.action_handler.show_context_menu
                        )
                        container_layout.addWidget(widget)
            except OSError as e:
                text_label = QLabel(translate("Error reading folder: {e}", e=e))
                text_label.setProperty("class", "textColorPrimary")
                container_layout.addWidget(text_label)

        self.ui_manager.update_all_track_widgets()

    def show_favorite_artist_albums_view(self, artist_name):
        """
        Renders a detailed view showing all albums belonging to a specific favorite artist.

        Args:
            artist_name: The name of the artist to display albums for.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_artist_album_sort_mode"):
            mw.favorite_artist_album_sort_mode = SortMode.YEAR_DESC
        if not hasattr(mw, "favorite_artist_album_view_mode"):
            mw.favorite_artist_album_view_mode = ViewMode.GRID

        artist_data = mw.data_manager.artists_data.get(artist_name)
        if not artist_data:
            print(f"Warning: Artist '{artist_name}' not found in library. Returning to Favorites.")
            self.ui_manager.navigate_back()
            return

        mw.current_artist_view = artist_name
        mw.current_favorites_context = "artist"
        self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
        self.ui_manager.clear_layout(mw.favorite_detail_layout)

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

        sort_button = self.components.create_tool_button_with_menu(
            [
                (
                    translate("By year (newest first)"),
                    sort_year_desc,
                    SortMode.YEAR_DESC,
                ),
                (translate("By year (oldest first)"), sort_year_asc, SortMode.YEAR_ASC),
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ],
            mw.favorite_artist_album_sort_mode,
        )
        sort_button.setFixedHeight(36)
        sort_button.menu().triggered.connect(
            lambda action: (
                setattr(mw, "favorite_artist_album_sort_mode", action.data()),
                self.show_favorite_artist_albums_view(artist_name),
            )
        )
        set_custom_tooltip(
            sort_button,
            title = translate("Sort Options"),
        )

        view_button = self.components.create_tool_button_with_menu(
            [
                (
                    translate("Grid"),
                    create_svg_icon(
                        "assets/control/view_grid.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.GRID,
                ),
                (
                    translate("Tile"),
                    create_svg_icon(
                        "assets/control/view_tile.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.TILE_BIG,
                ),
                (
                    translate("Small Tile"),
                    create_svg_icon(
                        "assets/control/view_tile_small.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.TILE_SMALL,
                ),
                (
                    translate("All tracks"),
                    create_svg_icon(
                        "assets/control/view_album_tracks.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.ALL_TRACKS,
                ),
            ],
            mw.favorite_artist_album_view_mode,
        )
        view_button.setFixedHeight(36)
        view_button.menu().triggered.connect(
            lambda action: (
                setattr(mw, "favorite_artist_album_view_mode", action.data()),
                self.show_favorite_artist_albums_view(artist_name),
            )
        )
        set_custom_tooltip(
            view_button,
            title = translate("View Options"),
        )
        fav_button = self.components._create_favorite_button(artist_name, "artist")

        artist_data = mw.data_manager.artists_data.get(artist_name, {})
        album_keys_for_artist = artist_data.get("albums", [])
        albums_of_artist = [
            (tuple(key), mw.data_manager.albums_data[tuple(key)])
            for key in album_keys_for_artist
            if tuple(key) in mw.data_manager.albums_data
        ]

        album_count = len(albums_of_artist)
        track_count = mw.data_manager.artists_data.get(artist_name, {}).get(
            "track_count", 0
        )
        albums_text = translate("{count} album(s)", count=album_count)
        tracks_text = translate("{count} track(s)", count=track_count)
        details_text = f"{albums_text}, {tracks_text}"

        header_parts = self.components.create_page_header(
            translate("{artist_name}: Albums", artist_name=artist_name),
            details_text=details_text,
            back_slot=self.ui_manager.navigate_back,
            control_widgets=[fav_button, sort_button, view_button],
            play_slot_data={"type": "artist", "data": artist_name},
            context_menu_data=(artist_name, "artist"),
        )
        if play_button := header_parts.get("play_button"):
            play_button.clicked.connect(
                lambda: mw.player_controller.play_data(
                    {"type": "artist", "data": artist_name}
                )
            )
            mw.main_view_header_play_buttons[artist_name] = play_button

        artist_cover_button = EntityCoverButton(
            artist_name,
            mw.data_manager.artists_data[artist_name],
            albums_of_artist,
            "artist",
            self.components.get_pixmap,
            main_window = mw
        )
        artist_cover_button.artworkChanged.connect(
            mw.action_handler.handle_artist_artwork_changed
        )
        header_parts["header"].layout().insertWidget(
            1, artist_cover_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        mw.favorite_detail_header_layout.addWidget(header_parts["header"])

        sort_mode = mw.favorite_artist_album_sort_mode
        if sort_mode == SortMode.ALPHA_ASC:
            albums_of_artist.sort(key=lambda x: mw.data_manager.get_sort_key(x[0][1]))
        elif sort_mode == SortMode.ALPHA_DESC:
            albums_of_artist.sort(
                key=lambda x: mw.data_manager.get_sort_key(x[0][1]), reverse=True
            )
        elif sort_mode == SortMode.YEAR_ASC:
            albums_of_artist.sort(
                key=lambda x: (
                    x[1].get("year", 9999),
                    mw.data_manager.get_sort_key(x[0][1]),
                )
            )
        elif sort_mode == SortMode.YEAR_DESC:
            albums_of_artist.sort(
                key=lambda x: (
                    x[1].get("year", 0),
                    mw.data_manager.get_sort_key(x[0][1]),
                ),
                reverse=True,
            )

        mw.current_fav_artist_album_list = albums_of_artist
        mw.fav_artist_albums_loaded_count = 0
        mw.is_loading_fav_artist_albums = False

        scroll_area = StyledScrollArea()
        scroll_area.setProperty("class", "backgroundPrimary")
        scroll_area.setWidgetResizable(True)
        mw.fav_sub_view_scroll_area = scroll_area

        self._populate_favorite_sub_view_lazy(
            scroll_area,
            "favorite_artist_album_view_mode",
            enc_key=artist_name,
            enc_type="artist",
            enc_refresh_callback=lambda: self.show_favorite_artist_albums_view(
                artist_name
            ),
        )

        scroll_bar = scroll_area.verticalScrollBar()
        scroll_bar.valueChanged.connect(
            lambda value: self.ui_manager.check_scroll_and_load(
                value, scroll_bar, self.load_more_fav_artist_albums
            )
        )

        self.load_more_fav_artist_albums()

        mw.favorite_detail_layout.addWidget(scroll_area)
        mw.favorites_stack.setCurrentIndex(1)
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("favorite"),
            context_data={"context": "artist", "data": artist_name},
        )
        self.ui_manager.update_all_track_widgets()

    def _populate_favorite_sub_view_lazy(
        self,
        scroll_area,
        view_mode_setting_attr,
        enc_key=None,
        enc_type=None,
        enc_refresh_callback=None,
    ):
        """
        Sets up the layout target inside the scroll area for lazy-loading sub-items like albums
        for a specific artist, composer, or genre.

        Args:
            scroll_area: The StyledScrollArea component to populate.
            view_mode_setting_attr: The attribute name in the main window specifying the view mode.
            enc_key: The encyclopedia key (e.g., artist or genre name).
            enc_type: Type of the encyclopedia entry ('artist', 'genre', 'composer').
            enc_refresh_callback: Callback triggered to refresh the encyclopedia section.
        """
        mw = self.main_window

        root_container = QWidget()
        root_container.setProperty("class", "backgroundPrimary")
        root_container.setContentsMargins(24, 24, 24, 24)

        root_layout = QVBoxLayout(root_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(24)

        self.ui_manager.inject_encyclopedia_section(
            root_layout, enc_key, enc_type, enc_refresh_callback
        )

        content_container = QWidget()
        content_container.setContentsMargins(0, 0, 0, 0)

        current_view_mode = getattr(mw, view_mode_setting_attr, ViewMode.GRID)

        target_layout = None
        if current_view_mode == ViewMode.ALL_TRACKS:
            layout = QVBoxLayout(content_container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(24)
            target_layout = layout
        else:
            layout = FlowLayout(content_container, stretch_items=True)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(16)
            target_layout = layout

        root_layout.addWidget(content_container)
        root_layout.addStretch(1)

        mw.active_fav_layout_target = target_layout

        scroll_area.setWidget(root_container)

    def load_more_fav_artist_albums(self):
        """
        Loads the next batch of albums for a specific artist.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "active_fav_layout_target")
            or mw.active_fav_layout_target is None
        ):
            return
        if mw.is_loading_fav_artist_albums:
            return
        if mw.fav_artist_albums_loaded_count >= len(mw.current_fav_artist_album_list):
            return

        mw.is_loading_fav_artist_albums = True
        batch = (
            BATCH_SIZE_ALLTRACKS
            if mw.favorite_artist_album_view_mode == ViewMode.ALL_TRACKS
            else BATCH_SIZE
        )
        start = mw.fav_artist_albums_loaded_count
        end = min(start + batch, len(mw.current_fav_artist_album_list))

        layout = mw.active_fav_layout_target

        for i in range(start, end):
            album_key, data = mw.current_fav_artist_album_list[i]
            if mw.favorite_artist_album_view_mode == ViewMode.ALL_TRACKS:
                widget = self.components._create_detailed_album_widget(
                    album_key, data, tracks_to_show=None
                )
                layout.addWidget(widget)
                if i < len(mw.current_fav_artist_album_list) - 1:
                    separator = QWidget()
                    separator.setFixedHeight(1)
                    separator.setProperty("class", "separator")
                    layout.addWidget(separator)
            else:
                widget = self.components.create_album_widget(
                    album_key, data, mw.favorite_artist_album_view_mode, show_artist=False
                )
                widget.activated.connect(
                    partial(self._show_album_details_safe, album_key)
                )
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "album"}
                    )
                )
                widget.playClicked.connect(mw.player_controller.play_data)
                layout.addWidget(widget)

        mw.fav_artist_albums_loaded_count = end
        mw.is_loading_fav_artist_albums = False
        QTimer.singleShot(100, self._check_for_more_fav_artist_albums)

    def _check_for_more_fav_artist_albums(self):
        """
        Periodically checks if more artist albums need to be loaded to fill the scroll view.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "fav_sub_view_scroll_area")
            or not mw.fav_sub_view_scroll_area.widget()
        ):
            return
        scroll_bar = mw.fav_sub_view_scroll_area.verticalScrollBar()
        has_more = mw.fav_artist_albums_loaded_count < len(
            mw.current_fav_artist_album_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_fav_artist_albums()

    def show_favorite_genre_albums_view(self, genre_name):
        """
        Renders a detailed view showing all albums belonging to a specific favorite genre.

        Args:
            genre_name: The name of the genre to display albums for.
        """
        mw = self.main_window

        if not hasattr(mw, "favorite_genre_album_sort_mode"):
            mw.favorite_genre_album_sort_mode = SortMode.YEAR_DESC
        if not hasattr(mw, "favorite_genre_album_view_mode"):
            mw.favorite_genre_album_view_mode = ViewMode.GRID

        mw.current_genre_view = genre_name
        mw.current_favorites_context = "genre"
        self.ui_manager.clear_layout(mw.favorite_detail_header_layout)
        self.ui_manager.clear_layout(mw.favorite_detail_layout)

        sort_button = self.components.create_tool_button_with_menu(
            [
                (
                    translate("By year (newest first)"),
                    create_svg_icon(
                        "assets/control/sort_date_desc.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    SortMode.YEAR_DESC,
                ),
                (
                    translate("By year (oldest first)"),
                    create_svg_icon(
                        "assets/control/sort_date_asc.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    SortMode.YEAR_ASC,
                ),
                (
                    translate("Alphabetical (A-Z)"),
                    create_svg_icon(
                        "assets/control/sort_alpha_asc.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    SortMode.ALPHA_ASC,
                ),
                (
                    translate("Alphabetical (Z-A)"),
                    create_svg_icon(
                        "assets/control/sort_alpha_desc.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    SortMode.ALPHA_DESC,
                ),
            ],
            mw.favorite_genre_album_sort_mode,
        )
        sort_button.setFixedHeight(36)
        sort_button.menu().triggered.connect(
            lambda action: (
                setattr(mw, "favorite_genre_album_sort_mode", action.data()),
                self.show_favorite_genre_albums_view(genre_name),
            )
        )
        set_custom_tooltip(
            sort_button,
            title = translate("Sort Options"),
        )

        view_button = self.components.create_tool_button_with_menu(
            [
                (
                    translate("Grid"),
                    create_svg_icon(
                        "assets/control/view_grid.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.GRID,
                ),
                (
                    translate("Tile"),
                    create_svg_icon(
                        "assets/control/view_tile.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.TILE_BIG,
                ),
                (
                    translate("Small Tile"),
                    create_svg_icon(
                        "assets/control/view_tile_small.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.TILE_SMALL,
                ),
                (
                    translate("All tracks"),
                    create_svg_icon(
                        "assets/control/view_album_tracks.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    ),
                    ViewMode.ALL_TRACKS,
                ),
            ],
            mw.favorite_genre_album_view_mode,
        )
        view_button.setFixedHeight(36)
        view_button.menu().triggered.connect(
            lambda action: (
                setattr(mw, "favorite_genre_album_view_mode", action.data()),
                self.show_favorite_genre_albums_view(genre_name),
            )
        )
        set_custom_tooltip(
            view_button,
            title = translate("View Options"),
        )
        fav_button = self.components._create_favorite_button(genre_name, "genre")
        album_keys = mw.data_manager.genres_data.get(genre_name, {}).get(
            "albums", set()
        )
        albums_of_genre = [
            (key, mw.data_manager.albums_data[key])
            for key in album_keys
            if key in mw.data_manager.albums_data
        ]
        album_count = len(albums_of_genre)
        track_count = mw.data_manager.genres_data.get(genre_name, {}).get(
            "track_count", 0
        )
        details_text = f"{translate('{count} album(s)', count=album_count)}, {translate('{count} track(s)', count=track_count)}"
        header_parts = self.components.create_page_header(
            translate("{genre_name}: Albums", genre_name=genre_name),
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
            self.components.get_pixmap,
            main_window = mw
        )
        genre_cover_button.artworkChanged.connect(
            mw.action_handler.handle_genre_artwork_changed
        )
        header_parts["header"].layout().insertWidget(
            1, genre_cover_button, alignment=Qt.AlignmentFlag.AlignCenter
        )
        mw.favorite_detail_header_layout.addWidget(header_parts["header"])

        sort_mode = mw.favorite_genre_album_sort_mode
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

        mw.current_fav_genre_album_list = albums_of_genre
        mw.fav_genre_albums_loaded_count = 0
        mw.is_loading_fav_genre_albums = False

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setProperty("class", "backgroundPrimary")
        mw.fav_sub_view_scroll_area = scroll_area

        self._populate_favorite_sub_view_lazy(
            scroll_area,
            "favorite_genre_album_view_mode",
            enc_key=genre_name,
            enc_type="genre",
            enc_refresh_callback=lambda: self.show_favorite_genre_albums_view(
                genre_name
            ),
        )

        scroll_bar = scroll_area.verticalScrollBar()
        scroll_bar.valueChanged.connect(
            lambda value: self.ui_manager.check_scroll_and_load(
                value, scroll_bar, self.load_more_fav_genre_albums
            )
        )
        self.load_more_fav_genre_albums()

        mw.favorite_detail_layout.addWidget(scroll_area)
        mw.favorites_stack.setCurrentIndex(1)
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("favorite"),
            context_data={"context": "genre", "data": genre_name},
        )
        self.ui_manager.update_all_track_widgets()

    def load_more_fav_genre_albums(self):
        """
        Loads the next batch of albums for a specific genre.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "active_fav_layout_target")
            or mw.active_fav_layout_target is None
        ):
            return
        if mw.is_loading_fav_genre_albums:
            return
        if mw.fav_genre_albums_loaded_count >= len(mw.current_fav_genre_album_list):
            return

        mw.is_loading_fav_genre_albums = True
        batch = (
            BATCH_SIZE_ALLTRACKS
            if mw.favorite_genre_album_view_mode == ViewMode.ALL_TRACKS
            else BATCH_SIZE
        )
        start = mw.fav_genre_albums_loaded_count
        end = min(start + batch, len(mw.current_fav_genre_album_list))

        layout = mw.active_fav_layout_target

        for i in range(start, end):
            album_key, data = mw.current_fav_genre_album_list[i]
            if mw.favorite_genre_album_view_mode == ViewMode.ALL_TRACKS:
                widget = self.components._create_detailed_album_widget(
                    album_key, data, tracks_to_show=None
                )
                layout.addWidget(widget)
                if i < len(mw.current_fav_genre_album_list) - 1:
                    separator = QWidget()
                    separator.setFixedHeight(1)
                    separator.setProperty("class", "separator")
                    layout.addWidget(separator)
            else:
                widget = self.components.create_album_widget(
                    album_key, data, mw.favorite_genre_album_view_mode, show_artist=True
                )
                widget.activated.connect(
                    partial(self._show_album_details_safe, album_key)
                )
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "album"}
                    )
                )
                widget.playClicked.connect(mw.player_controller.play_data)
                layout.addWidget(widget)

        mw.fav_genre_albums_loaded_count = end
        mw.is_loading_fav_genre_albums = False
        QTimer.singleShot(100, self._check_for_more_fav_genre_albums)

    def _check_for_more_fav_genre_albums(self):
        """
        Periodically checks if more genre albums need to be loaded to fill the scroll view.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "fav_sub_view_scroll_area")
            or not mw.fav_sub_view_scroll_area.widget()
        ):
            return
        scroll_bar = mw.fav_sub_view_scroll_area.verticalScrollBar()
        has_more = mw.fav_genre_albums_loaded_count < len(
            mw.current_fav_genre_album_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_fav_genre_albums()