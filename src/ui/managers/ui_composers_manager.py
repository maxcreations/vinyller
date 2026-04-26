"""
Vinyller — Composers UI manager
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

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from src.ui.custom_base_widgets import StyledScrollArea, set_custom_tooltip
from src.ui.custom_classes import (
    FlowLayout, SortMode, ViewMode, EntityCoverButton
)
from src.utils import theme
from src.utils.constants import BATCH_SIZE
from src.utils.utils import create_svg_icon, format_month_year
from src.utils.utils_translator import translate


class ComposersUIManager:
    """
    Class managing the UI logic and state for the composers tab.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the ComposersUIManager.
        """
        self.main_window = main_window
        self.ui_manager = ui_manager
        self.composer_separator_widgets = {}
        self.composer_album_separator_widgets = {}

    def populate_composers_tab(self, initial_load_count=None):
        """
        Populates the main composers tab with the library's composers.

        Args:
            initial_load_count (int, optional): The initial number of items to load
                (currently unused in the implementation).
        """
        mw = self.main_window
        mw.last_composer_letter, mw.current_composer_flow_layout = None, None
        self.composer_separator_widgets.clear()

        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        mw.composers_scroll.setWidget(container)

        source_list = mw.data_manager.sorted_composers

        if mw.show_random_suggestions and len(source_list) >= 20:
            suggestion_block = self.ui_manager.components.create_suggestion_block(
                "composer", self.populate_composers_tab
            )
            if suggestion_block:
                layout.addWidget(suggestion_block)

        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            mw.composer_sort_button.hide()
            mw.composer_view_button.hide()
            self.ui_manager.set_header_visibility(mw.composers_header, False)
            self.ui_manager.components._show_loading_library_message(layout)
            return

        if mw.data_manager.is_empty():
            mw.composer_sort_button.hide()
            mw.composer_view_button.hide()
            self.ui_manager.set_header_visibility(mw.composers_header, False)
            self.ui_manager.components._show_no_library_message(layout)
            return
        elif not mw.data_manager.composers_data:
            mw.composer_sort_button.hide()
            mw.composer_view_button.hide()
            self.ui_manager.set_header_visibility(mw.composers_header, False)
            self.ui_manager.components._show_no_metadata_results_message(
                layout, "composers"
            )
            return
        else:
            mw.composer_sort_button.show()
            mw.composer_view_button.show()
            self.ui_manager.set_header_visibility(mw.composers_header, True)

        count = len(source_list)
        mw.composers_header["details"].setText(
            translate("{count} composer(s)", count=count)
        )
        mw.composers_header["details"].show()

        mw.current_composers_display_list = source_list

        mw.composer_letters = set()
        if mw.show_separators:
            if mw.composer_sort_mode in [
                SortMode.DATE_ADDED_ASC,
                SortMode.DATE_ADDED_DESC,
            ]:
                for _, data in mw.current_composers_display_list:
                    timestamp = data.get("date_added", 0)
                    mw.composer_letters.add(format_month_year(timestamp))
            else:
                for composer, _ in mw.current_composers_display_list:
                    sort_name = mw.data_manager.get_sort_key(composer)
                    first_char = sort_name[0] if sort_name else "#"
                    current_letter = first_char.upper() if first_char.isalpha() else "*"
                    mw.composer_letters.add(current_letter)

        sort_mode = mw.composer_sort_mode
        if sort_mode == SortMode.ALPHA_ASC:
            mw.current_composers_display_list.sort(
                key=lambda x: mw.data_manager.get_sort_key(x[0])
            )
        elif sort_mode == SortMode.ALPHA_DESC:
            mw.current_composers_display_list.sort(
                key=lambda x: mw.data_manager.get_sort_key(x[0]), reverse=True
            )
        elif sort_mode == SortMode.DATE_ADDED_ASC:
            mw.current_composers_display_list.sort(
                key=lambda x: x[1].get("date_added", float("inf"))
            )
        elif sort_mode == SortMode.DATE_ADDED_DESC:
            mw.current_composers_display_list.sort(
                key=lambda x: x[1].get("date_added", 0), reverse=True
            )

        mw.composers_loaded_count = 0

        if mw.composers_loaded_count < len(mw.current_composers_display_list):
            self.load_more_composers()
        layout.addStretch(1)

    def load_more_composers(self):
        """
        Loads the next batch of composers in the grid/list.
        """
        mw = self.main_window
        if not mw.composers_scroll.widget():
            return
        if mw.is_loading_composers:
            return
        composer_list = mw.current_composers_display_list
        if mw.composers_loaded_count >= len(composer_list):
            return
        mw.is_loading_composers = True
        start, end = mw.composers_loaded_count, min(
            mw.composers_loaded_count + BATCH_SIZE, len(composer_list)
        )
        main_layout = mw.composers_scroll.widget().layout()
        stretch_item = None
        if main_layout.count() > 0:
            last_item = main_layout.itemAt(main_layout.count() - 1)
            if last_item and last_item.spacerItem():
                stretch_item = main_layout.takeAt(main_layout.count() - 1)

        for i in range(start, end):
            composer, data = composer_list[i]
            current_group = None
            if mw.show_separators:
                if mw.composer_sort_mode in [
                    SortMode.DATE_ADDED_ASC,
                    SortMode.DATE_ADDED_DESC,
                ]:
                    timestamp = data.get("date_added", 0)
                    current_group = format_month_year(timestamp)
                else:
                    sort_name = mw.data_manager.get_sort_key(composer)
                    first_char = sort_name[0] if sort_name else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"

                if current_group != mw.last_composer_letter:
                    separator_widget = self.ui_manager.components._create_separator_widget(
                        current_group, "composers", mw.composer_letters
                    )
                    main_layout.addWidget(separator_widget)
                    self.composer_separator_widgets[current_group] = separator_widget
                    mw.last_composer_letter = current_group
                    mw.current_composer_flow_layout = None

            target_layout = main_layout
            if mw.composer_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_composer_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_composer_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_composer_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_composer_flow_layout

            widget = self.ui_manager.components.create_composer_widget(
                composer, data, mw.composer_view_mode
            )
            widget.activated.connect(self.show_composer_albums)

            widget.contextMenuRequested.connect(
                lambda data, pos: mw.action_handler.show_context_menu(
                    data, pos, context={"forced_type": "composer"}
                )
            )

            widget.playClicked.connect(
                lambda d: mw.player_controller.smart_play(
                    {"type": "composer", "data": d}
                )
            )
            target_layout.addWidget(widget)

        if stretch_item:
            main_layout.addItem(stretch_item)

        mw.composers_loaded_count = end
        mw.is_loading_composers = False

        QTimer.singleShot(100, self._check_for_more_composers)

    def _check_for_more_composers(self):
        """
        Checks if more composers should be loaded to fill the view.
        """
        mw = self.main_window
        if not mw.composers_scroll.widget():
            return
        scroll_bar = mw.composers_scroll.verticalScrollBar()
        has_more_data = mw.composers_loaded_count < len(
            mw.current_composers_display_list
        )
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_composers()

    def show_composer_albums(self, composer_name):
        """
        Displays the detailed view of albums containing tracks by a specific composer.

        Args:
            composer_name (str): The name of the composer to display.
        """
        mw = self.main_window
        mw.current_composer_view = composer_name

        self.ui_manager.clear_layout(mw.composer_albums_header_layout)
        self.ui_manager.clear_layout(mw.composer_albums_layout)

        composer_data = mw.data_manager.composers_data.get(composer_name, {})
        album_keys = composer_data.get("albums", [])

        albums_of_composer = []
        for key in album_keys:
            t_key = tuple(key) if isinstance(key, list) else key
            if t_key in mw.data_manager.albums_data:
                albums_of_composer.append((t_key, mw.data_manager.albums_data[t_key]))

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
            sort_options, mw.composer_album_sort_mode
        )
        sort_button.setFixedHeight(36)
        sort_button.menu().triggered.connect(
            lambda action: mw.set_composer_album_sort_mode(action)
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

        view_options = [
            (translate("Grid"), view_grid, ViewMode.GRID),
            (translate("Tile"), view_tile, ViewMode.TILE_BIG),
            (translate("Small Tile"), view_tile_small, ViewMode.TILE_SMALL),
        ]

        view_button = self.ui_manager.components.create_tool_button_with_menu(
            view_options, mw.composer_album_view_mode
        )
        view_button.setFixedHeight(36)

        view_button.menu().triggered.connect(mw.set_composer_album_view_mode)
        set_custom_tooltip(
            view_button,
            title = translate("View Options"),
        )
        fav_button = self.ui_manager.components._create_favorite_button(composer_name, "composer")

        album_count = len(albums_of_composer)
        track_count = composer_data.get("track_count", 0)
        albums_text = translate("{count} album(s)", count=album_count)
        tracks_text = translate("{count} track(s)", count=track_count)
        details_text = f"{albums_text}, {tracks_text}"

        header_parts = self.ui_manager.components.create_page_header(
            title=composer_name,
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
            composer_data,
            albums_of_composer,
            "composer",
            self.ui_manager.components.get_pixmap,
            main_window=mw,
        )
        composer_cover_button.artworkChanged.connect(
            mw.action_handler.handle_composer_artwork_changed
        )

        header_parts["header"].layout().insertWidget(
            1, composer_cover_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        mw.composer_albums_header_layout.addWidget(header_parts["header"])

        sort_mode = mw.composer_album_sort_mode
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

        mw.composer_albums_scroll = StyledScrollArea()
        mw.composer_albums_scroll.setWidgetResizable(True)
        mw.composer_albums_scroll.setProperty("class", "backgroundPrimary")

        self._populate_composer_albums_standard_view(
            mw.composer_albums_scroll, albums_of_composer
        )

        mw.composer_albums_scroll.verticalScrollBar().valueChanged.connect(
            lambda value: self.ui_manager.check_scroll_and_load(
                value,
                mw.composer_albums_scroll.verticalScrollBar(),
                self.load_more_composer_albums,
            )
        )

        mw.composer_albums_layout.addWidget(mw.composer_albums_scroll)
        mw.composers_stack.setCurrentIndex(1)

        context = {"composer_name": composer_name}
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("composer"),
            context_data=context,
        )
        self.ui_manager.update_all_track_widgets()

    def _populate_composer_albums_standard_view(self, scroll_area, albums_of_composer):
        """
        Populates the standard album list view for a composer.

        Args:
            scroll_area (StyledScrollArea): The scroll area to hold the layout.
            albums_of_composer (list): A list of tuples containing album keys and data.
        """
        mw = self.main_window
        mw.current_composer_albums_list = albums_of_composer
        mw.composer_albums_loaded_count = 0
        mw.is_loading_composer_albums = False

        mw.last_composer_album_group = None
        mw.current_composer_album_flow_layout = None
        self.composer_album_separator_widgets.clear()

        root_container = QWidget()
        root_container.setContentsMargins(24, 24, 24, 24)
        root_container.setProperty("class", "backgroundPrimary")
        root_layout = QVBoxLayout(root_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(24)

        self.ui_manager.inject_encyclopedia_section(
            root_layout,
            mw.current_composer_view,
            "composer",
            lambda: self.show_composer_albums(mw.current_composer_view),
        )

        albums_container = QWidget()
        albums_container.setContentsMargins(0, 0, 0, 0)

        albums_layout = QVBoxLayout(albums_container)
        albums_layout.setContentsMargins(0, 0, 0, 0)
        albums_layout.setSpacing(16)

        root_layout.addWidget(albums_container)
        root_layout.addStretch(1)
        mw.active_composer_albums_layout_target = albums_layout

        mw.composer_album_groups = set()
        if mw.show_separators and len(mw.current_composer_albums_list) > 20:
            for album_key, data in mw.current_composer_albums_list:
                current_group = None
                if mw.composer_album_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    album_title = mw.data_manager.get_sort_key(album_key[1])
                    first_char = album_title[0] if album_title else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.composer_album_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                    album_year = data.get("year")
                    if album_year is None or album_year == 0:
                        current_group = "#"
                    else:
                        current_group = str(album_year)

                if current_group:
                    mw.composer_album_groups.add(current_group)

        scroll_area.setWidget(root_container)
        self.load_more_composer_albums()

    def load_more_composer_albums(self):
        """
        Loads the next batch of albums for the currently displayed composer.
        """
        mw = self.main_window
        if (
                not hasattr(mw, "active_composer_albums_layout_target")
                or mw.active_composer_albums_layout_target is None
        ):
            return
        if (
                not hasattr(mw, "composer_albums_scroll")
                or not mw.composer_albums_scroll
                or not mw.composer_albums_scroll.widget()
        ):
            return
        if getattr(mw, "is_loading_composer_albums", False):
            return
        if not hasattr(
                mw, "current_composer_albums_list"
        ) or mw.composer_albums_loaded_count >= len(mw.current_composer_albums_list):
            return

        mw.is_loading_composer_albums = True
        start = mw.composer_albums_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_composer_albums_list))

        main_layout = mw.active_composer_albums_layout_target

        for i in range(start, end):
            album_key, data = mw.current_composer_albums_list[i]
            current_group = None

            if mw.show_separators and len(mw.current_composer_albums_list) > 20:
                if mw.composer_album_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                    album_title = mw.data_manager.get_sort_key(album_key[1])
                    first_char = album_title[0] if album_title else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.composer_album_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                    album_year = data.get("year")
                    if album_year is None or album_year == 0:
                        current_group = "#"
                    else:
                        current_group = str(album_year)

                if current_group and current_group != mw.last_composer_album_group:
                    separator_widget = self.ui_manager.components._create_separator_widget(
                        current_group, "composer_albums", mw.composer_album_groups
                    )
                    main_layout.addWidget(separator_widget)
                    self.composer_album_separator_widgets[current_group] = separator_widget
                    mw.last_composer_album_group = current_group
                    mw.current_composer_album_flow_layout = None

            target_layout = main_layout
            if mw.composer_album_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if getattr(mw, "current_composer_album_flow_layout", None) is None:
                    flow_container = QWidget()
                    mw.current_composer_album_flow_layout = FlowLayout(
                        flow_container, stretch_items = True
                    )
                    mw.current_composer_album_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_composer_album_flow_layout

            widget = self.ui_manager.components.create_album_widget(
                album_key, data, mw.composer_album_view_mode, show_artist = True
            )
            widget.activated.connect(
                partial(self.ui_manager.show_album_tracks, source_stack = mw.composers_stack)
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
                mw.is_loading_composer_albums = False
                return

        mw.composer_albums_loaded_count = end
        mw.is_loading_composer_albums = False
        QTimer.singleShot(100, self._check_for_more_composer_albums)

    def _check_for_more_composer_albums(self):
        """
        Checks if more albums should be loaded for the currently displayed composer.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "composer_albums_scroll")
            or not mw.composer_albums_scroll.widget()
        ):
            return
        scroll_bar = mw.composer_albums_scroll.verticalScrollBar()
        has_more_data = mw.composer_albums_loaded_count < len(
            mw.current_composer_albums_list
        )
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_composer_albums()

    def navigate_to_composer(self, composer_name):
        """
        Jumps directly to the specified composer's detailed view.

        Args:
            composer_name (str): The name of the composer to navigate to.
        """
        mw = self.main_window
        if composer_name in mw.data_manager.composers_data:
            try:
                composer_tab_index = mw.nav_button_icon_names.index("composer")
                mw.main_stack.setCurrentIndex(composer_tab_index)
                mw.nav_buttons[composer_tab_index].setChecked(True)
                self.ui_manager.update_nav_button_icons()
                self.show_composer_albums(composer_name)
            except ValueError:
                print(f"Error: Composer tab not found for '{composer_name}'")

