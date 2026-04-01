"""
Vinyller — Catalog UI manager
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
from collections import defaultdict

from PyQt6.QtCore import QObject, QSize, Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QGraphicsOpacityEffect
)

from src.ui.custom_base_widgets import StyledScrollArea, set_custom_tooltip
from src.ui.custom_classes import FlowLayout, SortMode, ViewMode
from src.utils import theme
from src.utils.constants import BATCH_SIZE
from src.utils.utils import create_svg_icon
from src.utils.utils_translator import translate


class CatalogUIManager(QObject):
    """
    Manages the UI logic specifically for the Catalog (Folders) tab.
    Handles directory navigation, lazy loading of folder contents, and view modes.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the CatalogUIManager.
        """
        super().__init__()
        self.main_window = main_window
        self.ui_manager = ui_manager

    def populate_catalog_tab(self, initial_load_count=None):
        """
        Populates the main catalog/folder view with base library directories.
        """
        mw = self.main_window

        # Reset catalog stacks to the root view
        if mw.catalog_stack.count() > 0:
            mw.catalog_stack.setCurrentIndex(0)
            while mw.catalog_stack.count() > 1:
                widget = mw.catalog_stack.widget(1)
                mw.catalog_stack.removeWidget(widget)
                widget.deleteLater()
            if mw.catalog_header_stack.count() > 0:
                mw.catalog_header_stack.setCurrentIndex(0)
                while mw.catalog_header_stack.count() > 1:
                    h_widget = mw.catalog_header_stack.widget(1)
                    mw.catalog_header_stack.removeWidget(h_widget)
                    h_widget.deleteLater()

        def set_placeholder_message(message_func):
            container = QWidget()
            container.setContentsMargins(24, 24, 24, 24)
            container.setProperty("class", "backgroundPrimary")
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(16)
            message_func(layout)
            mw.catalog_scroll.setWidget(container)
            mw.catalog_sort_button.hide()
            mw.catalog_view_button.hide()
            self.ui_manager.set_header_visibility(mw.catalog_header, False)

        # Handle loading and empty library states
        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            set_placeholder_message(self.ui_manager.components._show_loading_library_message)
            return
        if mw.data_manager.is_empty():
            set_placeholder_message(self.ui_manager.components._show_no_library_message)
            return

        mw.catalog_sort_button.show()
        mw.catalog_view_button.show()
        self.ui_manager.set_header_visibility(mw.catalog_header, True)
        count = len(mw.music_library_paths)
        mw.catalog_header["details"].setText(
            translate("{count} folder(s)", count=count)
        )
        mw.catalog_header["details"].show()

        # Setup main scroll container
        scroll_container = QWidget()
        scroll_container.setContentsMargins(24, 24, 24, 24)
        scroll_container.setProperty("class", "backgroundPrimary")
        main_v_layout = QVBoxLayout(scroll_container)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(16)
        mw.catalog_scroll.setWidget(scroll_container)

        if not getattr(mw, "dismissed_add_folder_hint", False):
            hint_widget = self.ui_manager.components.create_library_hint_widget()
            main_v_layout.addWidget(hint_widget)

        # Apply sorting to root directories
        sorted_paths = sorted(
            mw.music_library_paths,
            key=mw.data_manager.get_sort_key,
            reverse=(mw.catalog_sort_mode == SortMode.ALPHA_DESC),
        )
        if not sorted_paths:
            self.ui_manager.components._show_no_search_results_message(main_v_layout)
            return

        mw.cards_container_catalog = QWidget()

        # Configure layout based on view mode
        if mw.catalog_view_mode in [
            ViewMode.GRID,
            ViewMode.TILE_BIG,
            ViewMode.TILE_SMALL,
        ]:
            cards_layout = FlowLayout(mw.cards_container_catalog, stretch_items=True)
            cards_layout.setContentsMargins(0, 0, 0, 0)
            cards_layout.setSpacing(16)
        else:
            cards_layout = QVBoxLayout(mw.cards_container_catalog)
            cards_layout.setContentsMargins(0, 0, 0, 0)
            cards_layout.setSpacing(16)

        main_v_layout.addWidget(mw.cards_container_catalog, 1)

        if not (
            mw.catalog_view_mode
            in [ViewMode.GRID, ViewMode.TILE_BIG, ViewMode.TILE_SMALL]
        ):
            main_v_layout.addStretch(1)

        mw.current_catalog_display_list = sorted_paths
        mw.catalog_loaded_count = 0
        mw.current_catalog_path = ""

        if mw.catalog_loaded_count < len(mw.current_catalog_display_list):
            self.load_more_catalog()

    def load_more_catalog(self):
        """
        Loads the next batch of directories in the catalog root view.
        """
        mw = self.main_window

        if not mw.catalog_scroll.widget():
            return
        if getattr(mw, "is_loading_catalog", False):
            return
        if not hasattr(mw, "current_catalog_display_list"):
            return

        path_list = mw.current_catalog_display_list
        if mw.catalog_loaded_count >= len(path_list):
            return

        mw.is_loading_catalog = True

        start = mw.catalog_loaded_count
        end = min(mw.catalog_loaded_count + BATCH_SIZE, len(path_list))

        if not hasattr(mw, "cards_container_catalog") or not mw.cards_container_catalog:
            mw.is_loading_catalog = False
            return

        layout = mw.cards_container_catalog.layout()

        # Render the current batch of root directories
        for i in range(start, end):
            path = path_list[i]
            if os.path.isdir(path):
                folder_name = os.path.basename(path) or path
                artwork_dicts = self.get_artworks_for_directory(path)

                widget = self.ui_manager.components.create_directory_widget(
                    folder_name, path, mw.catalog_view_mode, artwork_dicts
                )
                widget.activated.connect(self.on_catalog_item_activated)
                widget.playClicked.connect(mw.player_controller.smart_play)
                widget.contextMenuRequested.connect(mw.action_handler.show_context_menu)
                widget.pauseClicked.connect(mw.player.pause)
                layout.addWidget(widget)

        mw.catalog_loaded_count = end
        mw.is_loading_catalog = False

        # Reset states for nested directory loading
        self.current_directory_items = []
        self.directory_items_loaded_count = 0
        self.is_loading_directory_items = False
        self.current_directory_layout_container = None

        QTimer.singleShot(100, self._check_for_more_catalog)

    def _check_for_more_catalog(self):
        """
        Checks if more items should be loaded in the catalog root view.
        """
        mw = self.main_window
        if not mw.catalog_scroll.widget():
            return
        if not hasattr(mw, "current_catalog_display_list"):
            return

        scroll_bar = mw.catalog_scroll.verticalScrollBar()
        has_more_data = mw.catalog_loaded_count < len(mw.current_catalog_display_list)

        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_catalog()

    def get_artworks_for_directory(self, path):
        """
        Retrieves aggregated artworks from files inside a specific directory.
        """
        mw = self.main_window
        norm_path = os.path.normpath(path)
        path_with_sep = norm_path + os.path.sep
        album_keys_in_dir = set()

        # Identify all unique albums inside the directory
        for track in mw.data_manager.all_tracks:
            if os.path.normpath(track["path"]).startswith(path_with_sep):
                track_year = track.get("year", 0)

                if mw.treat_folders_as_unique:
                    album_key = (
                        track.get("album_artist"),
                        track.get("album"),
                        track_year,
                        os.path.dirname(track["path"]),
                    )
                else:
                    album_key = (
                        track.get("album_artist"),
                        track.get("album"),
                        track_year,
                    )
                album_keys_in_dir.add(album_key)

        artworks = []
        seen_artworks = set()

        # Sort albums to fetch the most relevant covers (e.g., newest first)
        sorted_albums = sorted(
            list(album_keys_in_dir),
            key=lambda k: (mw.data_manager.albums_data.get(k, {}).get("year", 0), k[1]),
            reverse=True,
        )

        # Collect up to 4 distinct artworks to create a collage effect
        for album_key in sorted_albums:
            if len(artworks) >= 4:
                break
            if album_data := mw.data_manager.albums_data.get(album_key):
                if artwork_dict := album_data.get("artwork"):
                    artwork_key = next(iter(sorted(artwork_dict.values())), None)
                    if artwork_key and artwork_key not in seen_artworks:
                        artworks.append(artwork_dict)
                        seen_artworks.add(artwork_key)
        return artworks

    def on_catalog_item_activated(self, data):
        """
        Handles user interaction with an item (folder or track) in the catalog.
        """
        mw = self.main_window
        if isinstance(data, dict):
            # If the item is a track, enqueue the whole folder and play the track
            directory = os.path.dirname(data["path"])
            mw.current_queue_name = os.path.basename(directory)
            mw.current_queue_context_path, mw.current_queue_context_data = (
                None,
                directory,
            )
            queue = sorted(
                [
                    t
                    for t in mw.data_manager.all_tracks
                    if os.path.dirname(t["path"]) == directory
                ],
                key=lambda x: (x.get("discnumber", 0), x.get("tracknumber", 0)),
            )
            mw.player.set_queue(queue)
            mw.player.play(data)
        elif isinstance(data, str):
            # If the item is a folder path, navigate into it
            self.navigate_to_directory(data)

    def navigate_to_directory(self, path, scroll_pos=0):
        """
        Navigates the catalog view to the specified directory path.
        """
        mw = self.main_window
        mw.current_catalog_path = path

        # Reset state for the new directory
        mw.current_directory_items = []
        mw.directory_items_loaded_count = 0
        mw.is_loading_directory_items = False
        mw.current_directory_layout_container = None
        mw.active_dir_cards_container = None

        header_page = QWidget()
        header_layout = QVBoxLayout(header_page)
        header_layout.setContentsMargins(0, 0, 0, 0)

        content_page = QWidget()
        content_layout = QVBoxLayout(content_page)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        fav_button = self.ui_manager.components._create_favorite_button(path, "folder")

        # Setup sort options UI
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        catalog_sort_options = [
            (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
            (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
        ]
        catalog_sort_button = self.ui_manager.components.create_tool_button_with_menu(
            catalog_sort_options, mw.catalog_sort_mode
        )
        catalog_sort_button.setFixedHeight(36)
        catalog_sort_button.menu().triggered.connect(mw.set_catalog_sort_mode)
        set_custom_tooltip(
            catalog_sort_button,
            title = translate("Sort Options"),
        )

        # Setup view mode options UI
        view_grid = create_svg_icon(
            "assets/control/view_grid.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        view_tile = create_svg_icon(
            "assets/control/view_tile.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        view_tile_small = create_svg_icon(
            "assets/control/view_tile_small.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]
        catalog_view_button = self.ui_manager.components.create_tool_button_with_menu(
            view_options, mw.catalog_view_mode
        )
        catalog_view_button.setFixedHeight(36)
        catalog_view_button.menu().triggered.connect(mw.set_catalog_view_mode)
        set_custom_tooltip(
            catalog_view_button,
            title = translate("View Options"),
        )

        control_widgets = [fav_button, catalog_sort_button, catalog_view_button]

        # Construct header
        header_parts = self.ui_manager.components.create_page_header(
            title = os.path.basename(path) or path,
            back_slot = self.ui_manager.navigate_back,
            control_widgets = control_widgets,
            play_slot_data = path,
            context_menu_data = (path, "folder"),
        )
        if play_button := header_parts.get("play_button"):
            play_button.clicked.connect(lambda: mw.player_controller.play_data(path))
            mw.main_view_header_play_buttons[path] = play_button

        header_layout.addWidget(header_parts["header"])

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setProperty("class", "backgroundPrimary")
        content_layout.addWidget(scroll_area)

        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(16)
        scroll_area.setWidget(container)

        mw.current_directory_layout_container = container

        # Step 1: Gather valid subdirectories
        try:
            reverse_sort = mw.catalog_sort_mode == SortMode.ALPHA_DESC
            entries = sorted(
                os.listdir(path), key = mw.data_manager.get_sort_key, reverse = reverse_sort
            )
            for entry in entries:
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path) and mw.action_handler.has_music_files(
                        full_path
                ):
                    mw.current_directory_items.append(
                        {"type": "folder", "path": full_path, "name": entry}
                    )
        except OSError:
            pass

        # Step 2: Gather tracks directly inside this directory and group by album
        norm_path = os.path.normpath(path)
        tracks_in_dir = [
            t
            for t in mw.data_manager.all_tracks
            if os.path.normpath(os.path.dirname(t["path"])) == norm_path
        ]

        if tracks_in_dir:
            grouped_by_album = defaultdict(list)
            for track in tracks_in_dir:
                track_year = track.get("year", 0)

                if mw.treat_folders_as_unique:
                    album_key = (
                        track.get("album_artist", translate("Unknown")),
                        track.get("album", translate("Unknown Album")),
                        track_year,
                        norm_path,
                    )
                else:
                    album_key = (
                        track.get("album_artist", translate("Unknown")),
                        track.get("album", translate("Unknown Album")),
                        track_year,
                    )

                grouped_by_album[album_key].append(track)

            sorted_albums = sorted(
                grouped_by_album.items(),
                key = lambda item: (
                    mw.data_manager.get_sort_key(item[0][0]),
                    mw.data_manager.get_sort_key(item[0][1]),
                ),
            )

            for album_key, album_tracks in sorted_albums:
                mw.current_directory_items.append(
                    {"type": "album_details", "key": album_key, "tracks": album_tracks}
                )

        # Handle Empty State
        if not mw.current_directory_items:
            if getattr(mw, "is_processing_library", False):
                empty_text = translate("Adding music to the library...")
            else:
                empty_text = translate("There is no music in this folder")

            container_layout.addStretch(1)

            icon_label = QLabel()
            icon_pixmap = create_svg_icon(
                "assets/control/search_folder.svg", theme.COLORS["TERTIARY"], QSize(64, 64)
            ).pixmap(QSize(64, 64))
            icon_label.setPixmap(icon_pixmap)
            op_eff = QGraphicsOpacityEffect(icon_label)
            op_eff.setOpacity(0.5)
            icon_label.setGraphicsEffect(op_eff)
            container_layout.addWidget(icon_label, alignment = Qt.AlignmentFlag.AlignCenter)
            container_layout.addSpacing(24)

            text_label = QLabel(empty_text)
            text_label.setProperty("class", "textHeaderPrimary textColorPrimary")
            container_layout.addWidget(
                text_label, alignment = Qt.AlignmentFlag.AlignCenter
            )

            container_layout.addStretch(1)
        else:
            scroll_bar = scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_directory_items
                )
            )
            self.load_more_directory_items()

        # Clean up old stack pages
        while mw.catalog_stack.count() > 1:
            w = mw.catalog_stack.widget(1)
            mw.catalog_stack.removeWidget(w)
            w.deleteLater()

        while mw.catalog_header_stack.count() > 1:
            h = mw.catalog_header_stack.widget(1)
            mw.catalog_header_stack.removeWidget(h)
            h.deleteLater()

        mw.catalog_header_stack.addWidget(header_page)
        mw.catalog_stack.addWidget(content_page)

        mw.catalog_stack.setCurrentWidget(content_page)

        if scroll_pos > 0:
            QTimer.singleShot(
                0, lambda: scroll_area.verticalScrollBar().setValue(scroll_pos)
            )

        mw.update_current_view_state(
            main_tab_index = mw.nav_button_icon_names.index("folder"),
            context_data = {"path": path},
        )

    def load_more_directory_items(self):
        """
        Loads the next batch of files/folders in the current catalog directory.
        """
        mw = self.main_window

        if not mw.current_directory_layout_container:
            return

        try:
            if not mw.current_directory_layout_container.isVisible():
                pass
        except RuntimeError:
            return

        if getattr(mw, "is_loading_directory_items", False):
            return
        if not hasattr(mw, "current_directory_items"):
            return

        items = mw.current_directory_items
        if mw.directory_items_loaded_count >= len(items):
            return

        mw.is_loading_directory_items = True

        start = mw.directory_items_loaded_count
        end = min(start + BATCH_SIZE, len(items))

        container = mw.current_directory_layout_container
        layout = container.layout()

        # Handle persistent FlowLayout container for grid/tile views
        cards_container = getattr(mw, "active_dir_cards_container", None)
        if cards_container:
            try:
                _ = cards_container.layout()
            except RuntimeError:
                cards_container = None
                mw.active_dir_cards_container = None

        for i in range(start, end):
            item = items[i]

            # Render Subdirectories
            if item["type"] == "folder":
                if mw.catalog_view_mode in [
                    ViewMode.GRID,
                    ViewMode.TILE_BIG,
                    ViewMode.TILE_SMALL,
                ]:
                    if not cards_container:
                        cards_container = QWidget()
                        cards_layout = FlowLayout(cards_container, stretch_items=True)
                        cards_layout.setSpacing(16)
                        cards_layout.setContentsMargins(0, 0, 0, 0)
                        layout.addWidget(cards_container)
                        mw.active_dir_cards_container = cards_container

                    cards_layout = cards_container.layout()

                    artwork_dicts = self.get_artworks_for_directory(item["path"])
                    widget = self.ui_manager.components.create_directory_widget(
                        item["name"], item["path"], mw.catalog_view_mode, artwork_dicts
                    )
                    widget.activated.connect(self.on_catalog_item_activated)
                    widget.playClicked.connect(mw.player_controller.smart_play)
                    widget.contextMenuRequested.connect(
                        mw.action_handler.show_context_menu
                    )
                    widget.pauseClicked.connect(mw.player.pause)
                    cards_layout.addWidget(widget)
                else:
                    artwork_dicts = self.get_artworks_for_directory(item["path"])
                    widget = self.ui_manager.components.create_directory_widget(
                        item["name"], item["path"], mw.catalog_view_mode, artwork_dicts
                    )
                    widget.activated.connect(self.on_catalog_item_activated)
                    widget.playClicked.connect(mw.player_controller.smart_play)
                    widget.contextMenuRequested.connect(
                        mw.action_handler.show_context_menu
                    )
                    widget.pauseClicked.connect(mw.player.pause)
                    layout.addWidget(widget)

            # Render Albums/Tracks found in the root of the directory
            elif item["type"] == "album_details":
                mw.active_dir_cards_container = None
                cards_container = None

                # Visual separator between folders and files
                if i > 0 and items[i - 1]["type"] == "folder":
                    sep = QWidget()
                    sep.setFixedHeight(1)
                    sep.setProperty("class", "separator")
                    layout.addWidget(sep)

                album_key = item["key"]
                album_tracks = item["tracks"]

                full_album_data = mw.data_manager.albums_data.get(album_key)

                # Mock album data if exact match is missing
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

                widget = self.ui_manager.components._create_detailed_album_widget(
                    album_key, full_album_data, tracks_to_show=album_tracks
                )
                layout.addWidget(widget)

                # Add separator between consecutive album details
                if i < len(items) - 1 and items[i + 1]["type"] == "album_details":
                    sep = QWidget()
                    sep.setFixedHeight(1)
                    sep.setProperty("class", "separator")
                    layout.addWidget(sep)

        if end >= len(items):
            layout.addStretch(1)
            mw.active_dir_cards_container = None

        mw.directory_items_loaded_count = end
        mw.is_loading_directory_items = False

        QTimer.singleShot(100, self._check_for_more_directory_items)

    def _check_for_more_directory_items(self):
        """
        Checks if more items should be loaded in the current catalog directory.
        """
        mw = self.main_window
        if mw.catalog_stack.count() > 1:
            current_page = mw.catalog_stack.widget(1)
            scroll_area = current_page.findChild(QScrollArea)
            if scroll_area:
                scroll_bar = scroll_area.verticalScrollBar()
                has_more = mw.directory_items_loaded_count < len(
                    mw.current_directory_items
                )
                if scroll_bar.maximum() == 0 and has_more:
                    self.load_more_directory_items()