"""
Vinyller — Charts UI manager
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
    ChartsPeriod, FlowLayout, SortMode,
    ViewMode, EntityCoverButton
)
from src.ui.custom_lists import (
    CustomRoles, TrackListWidget
)
from src.utils import theme
from src.utils.constants import (
    BATCH_SIZE, BATCH_SIZE_ALLTRACKS, TOP_TRACKS_LIMIT
)
from src.utils.utils import (
    create_svg_icon, format_month_year
)
from src.utils.utils_translator import translate


class ChartsUIManager:
    """
    Manages the UI logic for the charts tab.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the ChartsUIManager.
        """
        self.main_window = main_window
        self.ui_manager = ui_manager
        self.components = ui_manager.components

    def create_period_selector(self):
        """
        Creates and returns a tool button with a dropdown menu
        for selecting the charts time period (e.g., Current Month, All Time).

        Returns:
            QPushButton: The customized period selector button.
        """
        mw = self.main_window

        # Load icons for different time periods
        icon_month = create_svg_icon(
            "assets/control/sort_date_month.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        icon_all = create_svg_icon(
            "assets/control/sort_date_all_time.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )

        options = [
            (translate("Current Month"), icon_month, ChartsPeriod.MONTHLY),
            (translate("All Time"), icon_all, ChartsPeriod.ALL_TIME),
        ]

        current_period = getattr(mw, "charts_period", ChartsPeriod.MONTHLY)

        button = self.components.create_tool_button_with_menu(options, current_period)
        set_custom_tooltip(
            button,
            title = translate("Time Period"),
        )

        # Ensure we don't have duplicate connections if reused
        try:
            button.menu().triggered.disconnect()
        except Exception:
            pass

        button.menu().triggered.connect(
            lambda action: self.set_charts_period(action.data(), button)
        )

        return button

    def set_charts_period(self, period, button):
        """
        Updates the active charts period, recalculates the ratings,
        and refreshes the current charts view to reflect the new period.

        Args:
            period (ChartsPeriod): The new period to set.
            button (QPushButton): The period selector button to update.
        """
        mw = self.main_window
        if getattr(mw, "charts_period", None) == period:
            return

        print(f"Switching charts period to: {period}")
        mw.charts_period = period

        self.components.update_tool_button_icon(button, period)

        if hasattr(self, "period_button") and self.period_button != button:
            self.components.update_tool_button_icon(self.period_button, period)

        mw.save_current_settings()

        stats = mw.library_manager.load_play_stats()

        mw.data_manager.recalculate_ratings(period, stats)

        self.populate_charts_tab()

        current_idx = mw.charts_stack.currentIndex()
        if current_idx == 1:
            context = mw.current_charts_context
            if context == "all_tracks":
                self.show_all_top_tracks_view()
            elif context == "all_artists":
                self.show_all_top_artists_view()
            elif context == "all_albums":
                self.show_all_top_albums_view()
            elif context == "all_genres":
                self.show_all_top_genres_view()
            elif context == "all_composers":
                self.show_all_top_composers_view()

    def _get_period_display_text(self):
        """
        Retrieves the localized display text for the currently active charts period.

        Returns:
            str: The display text representing the current period.
        """
        period = getattr(self.main_window, "charts_period", ChartsPeriod.MONTHLY)
        if period == ChartsPeriod.MONTHLY:
            return translate("Current Month")
        else:
            return translate("All Time")

    def populate_charts_tab(self):
        """
        Populates the root index of the charts tab. Displays overviews of top
        tracks, albums, artists, genres, composers, and charts archives.
        """
        mw = self.main_window
        container = QWidget()
        container.setContentsMargins(24, 24, 24, 24)
        container.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        mw.charts_scroll.setWidget(container)

        # Handle loading or empty library states
        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            mw.chart_view_button.hide()
            self.ui_manager.set_header_visibility(mw.charts_header, False)
            self.components._show_loading_library_message(layout)
            return

        if mw.data_manager.is_empty():
            self.components._show_no_library_message(layout)
            mw.chart_view_button.hide()
            self.ui_manager.set_header_visibility(mw.charts_header, False)
            return

        # Check if there are any play statistics to show
        play_stats = mw.library_manager.load_play_stats()
        has_stats = (
            play_stats.get("artists")
            or play_stats.get("albums")
            or play_stats.get("genres")
            or play_stats.get("playlists")
            or play_stats.get("folders")
        )
        if not has_stats:
            # Show "No rating yet" placeholder if playback history is empty
            self.ui_manager.set_header_visibility(mw.charts_header, False)
            title = QLabel(translate("No rating yet"))
            title.setProperty("class", "textHeaderSecondary textColorPrimary")
            title.setWordWrap(True)
            title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)

            text = QLabel(translate("Listen to music to generate charts."))
            text.setWordWrap(True)
            text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            text.setProperty("class", "textSecondary textColorPrimary")
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)

            layout.addStretch()
            layout.addWidget(title)
            layout.addWidget(text)
            layout.addStretch()
            return
        else:
            mw.chart_view_button.show()
            self.ui_manager.set_header_visibility(mw.charts_header, True)

            # Dynamically inject the period selector into the main header if not present
            if not getattr(mw, "charts_period_button_added", False):
                self.period_button = self.create_period_selector()
                header_widget = mw.charts_header["header"]
                h_layout = header_widget.layout()

                if h_layout.count() > 0:
                    actions_item = h_layout.itemAt(h_layout.count() - 1)
                    if actions_item.layout():
                        actions_layout = actions_item.layout()
                        found_container = False
                        # Find a suitable container within the actions layout
                        for i in range(actions_layout.count()):
                            item = actions_layout.itemAt(i)
                            w = item.widget()
                            if w and not isinstance(w, QPushButton) and w.layout():
                                w.layout().insertWidget(0, self.period_button)
                                mw.charts_period_button_added = True
                                found_container = True
                                break

                        if not found_container:
                            actions_layout.insertWidget(0, self.period_button)
                            mw.charts_period_button_added = True

        suffix = self._get_period_display_text()
        mw.charts_header["title"].setText(translate("Charts"))
        mw.charts_header["details"].setText(suffix)
        mw.charts_header["details"].show()

        # Prepare sorted lists for overview sections
        top_tracks_all = mw.data_manager.sorted_tracks_by_play_count
        top_tracks = [t for t in top_tracks_all if t.get("play_count", 0) > 0]

        top_artists_all = sorted(
            [
                item
                for item in mw.data_manager.artists_data.items()
                if item[1].get("entity_rating", 0) > 0
            ],
            key=lambda i: (
                -i[1].get("entity_rating", 0),
                mw.data_manager.get_sort_key(i[0]),
            ),
        )

        top_albums_all = sorted(
            [
                item
                for item in mw.data_manager.albums_data.items()
                if item[1].get("entity_rating", 0) > 0
            ],
            key=lambda i: (
                -i[1].get("entity_rating", 0),
                mw.data_manager.get_sort_key(i[0][1]),
            ),
        )

        top_genres_all = sorted(
            [
                item
                for item in mw.data_manager.genres_data.items()
                if item[1].get("entity_rating", 0) > 0
            ],
            key=lambda i: (
                -i[1].get("entity_rating", 0),
                mw.data_manager.get_sort_key(i[0]),
            ),
        )

        top_composers_all = sorted(
            [
                item
                for item in mw.data_manager.composers_data.items()
                if item[1].get("entity_rating", 0) > 0
            ],
            key=lambda i: (
                -i[1].get("entity_rating", 0),
                mw.data_manager.get_sort_key(i[0]),
            ),
        )

        top_artists = top_artists_all
        top_albums = top_albums_all
        top_genres = top_genres_all
        top_composers = top_composers_all

        if top_tracks:
            self._add_vertical_track_list_section(
                layout,
                translate("Top Tracks") + f" ({suffix})",
                tracks_to_display=top_tracks[:10],
                full_tracks_list=top_tracks_all,
                on_see_all=self.show_all_top_tracks_view,
                context_key="all_top_tracks",
                icon_name="track.svg",
                button_text=translate("See all"),
            )
            layout.addSpacing(16)

        sections = [
            (
                "album",
                top_albums,
                top_albums_all,
                translate("Top Albums") + f" ({suffix})",
                "all_top_albums",
                self.show_all_top_albums_view,
                self.components.top_album_cover_pixmap,
            ),
            (
                "artist",
                top_artists,
                top_artists_all,
                translate("Top Artists") + f" ({suffix})",
                "all_top_artists",
                self.show_all_top_artists_view,
                self.components.top_artist_cover_pixmap,
            ),
            (
                "genre",
                top_genres,
                top_genres_all,
                translate("Top Genres") + f" ({suffix})",
                "all_top_genres",
                self.show_all_top_genres_view,
                self.components.top_genre_cover_pixmap,
            ),
            (
                "composer",
                top_composers,
                top_composers_all,
                translate("Top Composers") + f" ({suffix})",
                "all_top_composers",
                self.show_all_top_composers_view,
                self.components.top_composer_cover_pixmap,
            ),
        ]

        for (
            item_type,
            items,
            full_list,
            title_text,
            all_data_key,
            all_view_func,
            all_pixmap,
        ) in sections:
            if items:
                separator_widget = QWidget()
                separator_widget.setFixedHeight(16)
                separator_layout = QHBoxLayout(separator_widget)
                separator_layout.setContentsMargins(0, 0, 0, 0)
                separator_layout.setSpacing(16)

                separator_alpha = QLabel(title_text)
                separator_alpha.setProperty("class", "separatorAlpha")
                separator_alpha.setFixedHeight(16)
                separator_layout.addWidget(separator_alpha)

                separator_line = QWidget()
                separator_line.setProperty("class", "separator")
                separator_line.setFixedHeight(2)
                separator_layout.addWidget(separator_line, stretch=1)
                layout.addWidget(separator_widget)

                flow_container = QWidget()
                flow_layout = FlowLayout(flow_container, stretch_items=True)
                flow_layout.setSpacing(16)

                items_to_display = items
                if len(full_list) > 12:
                    pixmap = all_pixmap
                    title, subtitle = "", ""

                    if item_type == "album":
                        title = translate("All Top Albums")
                        subtitle = translate("{count} album(s)", count=len(full_list))
                    elif item_type == "artist":
                        title = translate("All Top Artists")
                        subtitle = translate("{count} artist(s)", count=len(full_list))
                    elif item_type == "genre":
                        title = translate("All Top Genres")
                        subtitle = translate("{count} genre(s)", count=len(full_list))
                    elif item_type == "composer":
                        title = translate("All Top Composers")
                        subtitle = translate(
                            "{count} composer(s)", count=len(full_list)
                        )

                    if pixmap:
                        all_card = CardWidget(
                            data=all_data_key,
                            view_mode=mw.favorite_view_mode,
                            pixmaps=[pixmap],
                            title=title,
                            subtitle1=subtitle,
                        )
                        all_card.activated.connect(all_view_func)
                        all_card.playClicked.connect(mw.player_controller.play_data)
                        all_card.pauseClicked.connect(mw.player.pause)
                        all_card.contextMenuRequested.connect(
                            mw.action_handler.show_favorite_tracks_card_context_menu
                        )
                        mw.main_view_card_widgets[all_data_key].append(all_card)
                        flow_layout.addWidget(all_card)

                    items_to_display = items[:11]

                for key, data in items_to_display:
                    if not data:
                        continue
                    play_count = data.get("entity_rating", 0)
                    subtitle_extra = translate("Rating: {count}", count=play_count)

                    if item_type == "album":
                        widget = self.components.create_album_widget(
                            key,
                            data,
                            mw.favorite_view_mode,
                            subtitle_extra=subtitle_extra,
                        )
                        widget.activated.connect(
                            partial(
                                self.ui_manager.show_album_tracks,
                                source_stack=mw.charts_stack,
                            )
                        )

                        widget.contextMenuRequested.connect(
                            lambda d, p: mw.action_handler.show_context_menu(
                                d, p, context={"forced_type": "album"}
                            )
                        )
                        widget.playClicked.connect(mw.player_controller.play_data)

                    elif item_type == "artist":
                        widget = self.components.create_artist_widget(
                            key,
                            data,
                            mw.favorite_view_mode,
                            subtitle_extra=subtitle_extra,
                        )
                        widget.activated.connect(
                            partial(self.show_top_artist_albums_view, key)
                        )

                        widget.contextMenuRequested.connect(
                            lambda d, p: mw.action_handler.show_context_menu(
                                d, p, context={"forced_type": "artist"}
                            )
                        )
                        widget.playClicked.connect(
                            lambda d: mw.player_controller.play_data(
                                {"type": "artist", "data": d}
                            )
                        )

                    elif item_type == "genre":
                        widget = self.components.create_genre_widget(
                            key,
                            data,
                            mw.favorite_view_mode,
                            subtitle_extra=subtitle_extra,
                        )
                        widget.activated.connect(
                            partial(self.show_top_genre_albums_view, key)
                        )

                        widget.contextMenuRequested.connect(
                            lambda d, p: mw.action_handler.show_context_menu(
                                d, p, context={"forced_type": "genre"}
                            )
                        )
                        widget.playClicked.connect(
                            lambda d: mw.player_controller.play_data(
                                {"type": "genre", "data": d}
                            )
                        )

                    elif item_type == "composer":
                        widget = self.components.create_composer_widget(
                            key,
                            data,
                            mw.favorite_view_mode,
                            subtitle_extra=subtitle_extra,
                        )
                        widget.activated.connect(
                            partial(self.show_top_composer_albums_view, key)
                        )

                        widget.contextMenuRequested.connect(
                            lambda d, p: mw.action_handler.show_context_menu(
                                d, p, context={"forced_type": "composer"}
                            )
                        )
                        widget.playClicked.connect(
                            lambda d: mw.player_controller.play_data(
                                {"type": "composer", "data": d}
                            )
                        )

                    flow_layout.addWidget(widget)

                layout.addWidget(flow_container)
                layout.addSpacing(16)

        try:
            charts_archive = mw.library_manager.load_charts_archive()
        except Exception as e:
            print(f"Unable to load charts archives: {e}")
            charts_archive = {}

        sorted_archive_keys = sorted(charts_archive.keys(), reverse=True)

        if sorted_archive_keys:
            separator_widget = QWidget()
            separator_widget.setFixedHeight(16)
            separator_layout = QHBoxLayout(separator_widget)
            separator_layout.setContentsMargins(0, 0, 0, 0)
            separator_layout.setSpacing(16)

            separator_alpha = QLabel(translate("Charts Archive"))
            separator_alpha.setProperty("class", "separatorAlpha")
            separator_alpha.setFixedHeight(16)
            separator_layout.addWidget(separator_alpha)

            separator_line = QWidget()
            separator_line.setProperty("class", "separator")
            separator_line.setFixedHeight(2)
            separator_layout.addWidget(separator_line, stretch=1)
            layout.addWidget(separator_widget)

            flow_container = QWidget()
            flow_layout = FlowLayout(flow_container, stretch_items=True)
            flow_layout.setSpacing(16)

            pixmap = self.components.top_archive_cover_pixmap

            for month_key in sorted_archive_keys:
                month_data = charts_archive.get(month_key, {})
                if not month_data:
                    continue

                title = format_month_year(month_key)
                subtitle = translate("Archive")

                widget = CardWidget(
                    data=(month_key, "month_overview"),
                    view_mode=mw.favorite_view_mode,
                    pixmaps=[pixmap],
                    title=title,
                    subtitle1=subtitle,
                    is_artist_card=False,
                    show_play_button=False,
                )

                widget.activated.connect(
                    partial(self.show_archived_month_view, month_key)
                )
                flow_layout.addWidget(widget)

            layout.addWidget(flow_container)
            layout.addSpacing(16)

        layout.addStretch(1)
        self.ui_manager.update_all_track_widgets()

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
        Adds a vertically aligned track list section to the given layout, typically
        used for displaying the 'Top Tracks' preview block.

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

        track_list_widget = TrackListWidget(
            mw,
            parent_context=context_key,
            use_row_for_track_num=True,
            show_score=True,
            parent=container,
        )

        has_any_composer = any(
            t.get("composer") and t.get("composer").strip() for t in tracks_to_display
        )
        track_list_widget.delegate.setShowComposerColumn(has_any_composer)

        for track in tracks_to_display:
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
        Handles track playback specifically initiated from a vertical track list.
        Sets the global queue context and plays the specific track index.

        Args:
            full_tracks_list (list): The list containing all tracks in the context.
            queue_name (str): The display name of the current queue.
            context_key (str): The internal context identifier.
            track_to_play (dict): Data dictionary of the track to be played.
        """
        mw = self.main_window
        mw.current_queue_name = queue_name
        mw.current_queue_context_data = context_key
        mw.conscious_choice_data = (track_to_play["path"], "track")
        mw.player.set_queue(full_tracks_list)
        target_index = next(
            (
                i
                for i, t in enumerate(full_tracks_list)
                if t["path"] == track_to_play["path"]
            ),
            0,
        )
        mw.player.play(target_index)

    def show_all_top_tracks_view(self, data=None):
        """
        Displays a detailed sub-view showing the full list of top tracks
        for the currently active charts period.

        Args:
            data: Optional data passed when triggered (typically None).
        """
        mw = self.main_window

        is_refresh = (
            mw.current_charts_context == "all_tracks"
            and mw.charts_stack.currentIndex() == 1
            and mw.chart_detail_layout.count() > 0
        )

        if not is_refresh:
            mw.current_charts_context = "all_tracks"
            self.ui_manager.clear_layout(mw.chart_detail_header_layout)
            self.ui_manager.clear_layout(mw.chart_detail_layout)

        all_track_objects = [
            t
            for t in mw.data_manager.sorted_tracks_by_play_count
            if t.get("play_count", 0) > 0
        ]
        track_objects = all_track_objects[:TOP_TRACKS_LIMIT]
        details_text = translate("{count} track(s)", count=len(track_objects))

        title_text = translate("Top Tracks")
        period_text = self._get_period_display_text()
        combined_details = f"{period_text}  •  {details_text}"

        if not is_refresh:
            period_btn = self.create_period_selector()

            header_parts = self.components.create_page_header(
                title=title_text,
                details_text=combined_details,
                back_slot=self.ui_manager.navigate_back,
                control_widgets=[period_btn],
                play_slot_data="all_top_tracks",
                context_menu_data=("all_top_tracks", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_top_tracks")
                )
                mw.main_view_header_play_buttons["all_top_tracks"] = play_button

            self.charts_tracks_details_label = header_parts["details"]
            self.charts_tracks_title_label = header_parts["title"]

            mw.chart_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.chart_detail_scroll_area = scroll_area
            mw.chart_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "charts_tracks_details_label"):
                period_text = self._get_period_display_text()
                combined_details = f"{period_text}  •  {details_text}"
                self.charts_tracks_details_label.setText(combined_details)
            if hasattr(self, "charts_tracks_title_label"):
                self.charts_tracks_title_label.setText(title_text)

        if mw.chart_detail_scroll_area.widget():
            mw.chart_detail_scroll_area.widget().deleteLater()

        if not track_objects:
            container = QWidget()
            container.setProperty("class", "backgroundPrimary")
            layout = QVBoxLayout(container)
            text_label = QLabel(translate("No tracks found."))
            text_label.setProperty("class", "textColorPrimary")
            layout.addWidget(text_label)
            layout.addStretch(1)
            mw.chart_detail_scroll_area.setWidget(container)
        else:
            playlist_widget = self.components._create_detailed_playlist_widget(
                playlist_path="all_top_tracks",
                playlist_name=translate("Top Tracks"),
                tracks=track_objects,
                pixmap=self.components.top_track_cover_pixmap,
                show_score=True,
            )

            try:
                playlist_widget.playlistContextMenu.disconnect()
            except Exception:
                pass

            playlist_widget.playlistContextMenu.connect(
                mw.action_handler.show_favorite_tracks_card_context_menu
            )

            playlist_widget.setContentsMargins(24, 24, 24, 24)
            mw.chart_detail_scroll_area.setWidget(playlist_widget)

        if not is_refresh:
            mw.charts_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("charts"),
                context_data={"context": "all_tracks"},
            )
        self.ui_manager.update_all_track_widgets()

    def show_all_top_albums_view(self):
        """
        Displays a detailed sub-view of all top albums for the active period,
        including user controls for sorting and switching view modes.
        """
        mw = self.main_window

        is_refresh = (
            mw.current_charts_context == "all_albums"
            and mw.charts_stack.currentIndex() == 1
            and mw.chart_detail_layout.count() > 0
        )

        if not is_refresh:
            mw.current_charts_context = "all_albums"
            mw.chart_detail_separator_widgets.clear()
            self.ui_manager.clear_layout(mw.chart_detail_header_layout)
            self.ui_manager.clear_layout(mw.chart_detail_layout)

        sort_rating_desc = create_svg_icon(
            "assets/control/sort_rating_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_rating_asc = create_svg_icon(
            "assets/control/sort_rating_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
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

        control_widgets = []
        if not is_refresh:
            sort_options = [
                (
                    translate("By rating (most first)"),
                    sort_rating_desc,
                    SortMode.DATE_ADDED_DESC,
                ),
                (
                    translate("By rating (least first)"),
                    sort_rating_asc,
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
                sort_options, mw.charts_album_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "charts_album_sort_mode", action.data()),
                    self.show_all_top_albums_view(),
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
                mw.favorite_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_view_mode", action.data()),
                    self.show_all_top_albums_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            period_btn = self.create_period_selector()
            control_widgets = [period_btn, sort_button, view_button]

        items_all = mw.data_manager.albums_data.items()
        items = [item for item in items_all if item[1].get("entity_rating", 0) > 0]

        if mw.charts_album_sort_mode == SortMode.DATE_ADDED_DESC:
            items.sort(key=lambda i: i[1].get("entity_rating", 0), reverse=True)
        elif mw.charts_album_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda i: i[1].get("entity_rating", 0))
        elif mw.charts_album_sort_mode == SortMode.YEAR_DESC:
            items.sort(
                key=lambda i: (i[1].get("year", 0), i[1].get("entity_rating", 0)),
                reverse=True,
            )
        elif mw.charts_album_sort_mode == SortMode.YEAR_ASC:
            items.sort(
                key=lambda i: (i[1].get("year", 9999), i[1].get("entity_rating", 0))
            )
        elif mw.charts_album_sort_mode == SortMode.ALPHA_ASC:
            items.sort(
                key=lambda i: (
                    mw.data_manager.get_sort_key(i[0][1]),
                    i[1].get("entity_rating", 0),
                )
            )
        elif mw.charts_album_sort_mode == SortMode.ALPHA_DESC:
            items.sort(
                key=lambda i: (
                    mw.data_manager.get_sort_key(i[0][1]),
                    i[1].get("entity_rating", 0),
                ),
                reverse=True,
            )
        else:
            items.sort(
                key=lambda i: (
                    -i[1].get("entity_rating", 0),
                    mw.data_manager.get_sort_key(i[0][1]),
                )
            )

        mw.album_groups = set()
        if mw.show_favorites_separators:
            for album_key, album_data in items:
                current_group = None
                if mw.charts_album_sort_mode in [
                    SortMode.ALPHA_ASC,
                    SortMode.ALPHA_DESC,
                ]:
                    album_title = mw.data_manager.get_sort_key(album_key[1])
                    first_char = album_title[0] if album_title else "#"
                    current_group = first_char.upper() if first_char.isalpha() else "*"
                elif mw.charts_album_sort_mode in [
                    SortMode.YEAR_ASC,
                    SortMode.YEAR_DESC,
                ]:
                    album_year = album_data.get("year")
                    current_group = (
                        str(album_year)
                        if (album_year is not None and album_year > 0)
                        else "#"
                    )
                elif mw.charts_album_sort_mode in [
                    SortMode.DATE_ADDED_DESC,
                    SortMode.DATE_ADDED_ASC,
                ]:
                    current_group = translate("By rating")

                if current_group:
                    mw.album_groups.add(current_group)

        mw.current_charts_all_albums_list = items
        mw.charts_all_albums_loaded_count = 0
        mw.is_loading_charts_all_albums = False
        mw.last_charts_all_albums_group = None
        mw.current_charts_all_albums_flow_layout = None

        title_text = translate("All Top Albums")
        details_text = translate("{count} album(s)", count=len(items))

        period_text = self._get_period_display_text()
        combined_details = f"{period_text}  •  {details_text}"

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=title_text,
                details_text=combined_details,
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_top_albums",
                context_menu_data=("all_top_albums", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_top_albums")
                )
                mw.main_view_header_play_buttons["all_top_albums"] = play_button

            self.charts_albums_details_label = header_parts["details"]
            self.charts_albums_title_label = header_parts["title"]

            mw.chart_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.chart_detail_scroll_area = scroll_area
            mw.chart_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "charts_albums_details_label"):
                period_text = self._get_period_display_text()
                combined_details = f"{period_text}  •  {details_text}"
                self.charts_albums_details_label.setText(combined_details)
            if hasattr(self, "charts_albums_title_label"):
                self.charts_albums_title_label.setText(title_text)

        if mw.chart_detail_scroll_area.widget():
            mw.chart_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        mw.chart_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No top albums found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.chart_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_charts_all_albums
                )
            )
            self.load_more_charts_all_albums()

        if not is_refresh:
            mw.charts_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("charts"),
                context_data={"context": "all_albums"},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_charts_all_albums(self):
        """
        Lazily loads and renders the next batch of top albums as the user scrolls,
        creating UI widgets and managing layout sections.
        """
        mw = self.main_window
        if mw.is_loading_charts_all_albums:
            return
        if mw.charts_all_albums_loaded_count >= len(mw.current_charts_all_albums_list):
            return

        mw.is_loading_charts_all_albums = True
        start = mw.charts_all_albums_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_charts_all_albums_list))

        container = mw.chart_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            album_key, album_data = mw.current_charts_all_albums_list[i]
            if not album_data:
                continue

            current_group = None
            if mw.charts_album_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                album_title = mw.data_manager.get_sort_key(album_key[1])
                first_char = album_title[0] if album_title else "#"
                current_group = first_char.upper() if first_char.isalpha() else "*"
            elif mw.charts_album_sort_mode in [SortMode.YEAR_ASC, SortMode.YEAR_DESC]:
                album_year = album_data.get("year")
                current_group = (
                    str(album_year)
                    if (album_year is not None and album_year > 0)
                    else "#"
                )
            elif mw.charts_album_sort_mode in [
                SortMode.DATE_ADDED_DESC,
                SortMode.DATE_ADDED_ASC,
            ]:
                current_group = translate("By rating")

            if (
                mw.show_favorites_separators
                and current_group
                and current_group != mw.last_charts_all_albums_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "charts_albums", mw.album_groups
                )
                main_layout.addWidget(separator_widget)
                mw.chart_detail_separator_widgets[current_group] = separator_widget
                mw.last_charts_all_albums_group = current_group
                mw.current_charts_all_albums_flow_layout = None

            target_layout = main_layout
            if mw.favorite_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_charts_all_albums_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_charts_all_albums_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_charts_all_albums_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_charts_all_albums_flow_layout

            play_count = album_data.get("entity_rating", 0)
            subtitle_extra = translate("Rating: {count}", count=play_count)

            widget = self.components.create_album_widget(
                album_key,
                album_data,
                mw.favorite_view_mode,
                subtitle_extra=subtitle_extra,
            )
            widget.activated.connect(
                partial(self.ui_manager.show_album_tracks, source_stack=mw.charts_stack)
            )

            widget.contextMenuRequested.connect(
                lambda d, p: mw.action_handler.show_context_menu(
                    d, p, context={"forced_type": "album"}
                )
            )
            widget.playClicked.connect(mw.player_controller.play_data)
            target_layout.addWidget(widget)

        mw.charts_all_albums_loaded_count = end
        mw.is_loading_charts_all_albums = False

        if end >= len(mw.current_charts_all_albums_list):
            if mw.favorite_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_charts_all_albums)

    def _check_for_more_charts_all_albums(self):
        """
        Periodically checks the scroll position to determine if the next batch
        of top albums should be loaded.
        """
        mw = self.main_window
        if not mw.chart_detail_scroll_area.widget():
            return
        scroll_bar = mw.chart_detail_scroll_area.verticalScrollBar()
        has_more = mw.charts_all_albums_loaded_count < len(
            mw.current_charts_all_albums_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_charts_all_albums()

    def show_all_top_artists_view(self):
        """
        Displays a detailed sub-view showing all top artists for the selected
        charts period with necessary UI controls for sorting and layouts.
        """
        mw = self.main_window

        is_refresh = (
            mw.current_charts_context == "all_artists"
            and mw.charts_stack.currentIndex() == 1
            and mw.chart_detail_layout.count() > 0
        )

        if not is_refresh:
            mw.current_charts_context = "all_artists"
            mw.chart_detail_separator_widgets.clear()
            self.ui_manager.clear_layout(mw.chart_detail_header_layout)
            self.ui_manager.clear_layout(mw.chart_detail_layout)

        sort_rating_desc = create_svg_icon(
            "assets/control/sort_rating_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_rating_asc = create_svg_icon(
            "assets/control/sort_rating_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )

        control_widgets = []
        if not is_refresh:
            sort_options = [
                (
                    translate("By rating (most first)"),
                    sort_rating_desc,
                    SortMode.DATE_ADDED_DESC,
                ),
                (
                    translate("By rating (least first)"),
                    sort_rating_asc,
                    SortMode.DATE_ADDED_ASC,
                ),
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]

            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.charts_artist_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "charts_artist_sort_mode", action.data()),
                    self.show_all_top_artists_view(),
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
                mw.favorite_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_view_mode", action.data()),
                    self.show_all_top_artists_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            period_btn = self.create_period_selector()
            control_widgets = [period_btn, sort_button, view_button]

        items_all = mw.data_manager.artists_data.items()
        items = [item for item in items_all if item[1].get("entity_rating", 0) > 0]

        if mw.charts_artist_sort_mode == SortMode.ALPHA_ASC:
            items.sort(
                key=lambda i: (
                    mw.data_manager.get_sort_key(i[0]),
                    i[1].get("entity_rating", 0),
                )
            )
        elif mw.charts_artist_sort_mode == SortMode.ALPHA_DESC:
            items.sort(
                key=lambda i: (
                    mw.data_manager.get_sort_key(i[0]),
                    i[1].get("entity_rating", 0),
                ),
                reverse=True,
            )
        elif mw.charts_artist_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda i: i[1].get("entity_rating", 0))
        else:
            items.sort(
                key=lambda i: (
                    -i[1].get("entity_rating", 0),
                    mw.data_manager.get_sort_key(i[0]),
                )
            )

        mw.artist_letters = set()
        if mw.show_favorites_separators:
            for artist_name, _ in items:
                first_char = (
                    mw.data_manager.get_sort_key(artist_name)[0].upper()
                    if mw.data_manager.get_sort_key(artist_name)
                    else "*"
                )
                mw.artist_letters.add(first_char)

        mw.current_charts_all_artists_list = items
        mw.charts_all_artists_loaded_count = 0
        mw.is_loading_charts_all_artists = False
        mw.last_charts_all_artists_group = None
        mw.current_charts_all_artists_flow_layout = None

        title_text = translate("All Top Artists")
        details_text = translate("{count} artist(s)", count=len(items))
        period_text = self._get_period_display_text()
        combined_details = f"{period_text}  •  {details_text}"

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=title_text,
                details_text=combined_details,
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_top_artists",
                context_menu_data=("all_top_artists", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_top_artists")
                )
                mw.main_view_header_play_buttons["all_top_artists"] = play_button

            self.charts_artists_details_label = header_parts["details"]
            self.charts_artists_title_label = header_parts["title"]

            mw.chart_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.chart_detail_scroll_area = scroll_area
            mw.chart_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "charts_artists_details_label"):
                period_text = self._get_period_display_text()
                combined_details = f"{period_text}  •  {details_text}"
                self.charts_artists_details_label.setText(combined_details)
            if hasattr(self, "charts_artists_title_label"):
                self.charts_artists_title_label.setText(title_text)

        if mw.chart_detail_scroll_area.widget():
            mw.chart_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        mw.chart_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No top artists found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.chart_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_charts_all_artists
                )
            )
            self.load_more_charts_all_artists()

        if not is_refresh:
            mw.charts_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("charts"),
                context_data={"context": "all_artists"},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_charts_all_artists(self):
        """
        Lazily loads and renders the next batch of top artists into the UI structure.
        """
        mw = self.main_window
        if mw.is_loading_charts_all_artists:
            return
        if mw.charts_all_artists_loaded_count >= len(
            mw.current_charts_all_artists_list
        ):
            return

        mw.is_loading_charts_all_artists = True
        start = mw.charts_all_artists_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_charts_all_artists_list))

        container = mw.chart_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            artist_name, artist_data = mw.current_charts_all_artists_list[i]

            sort_name = mw.data_manager.get_sort_key(artist_name)
            first_char = sort_name[0] if sort_name else "*"

            current_group = None
            if mw.charts_artist_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                current_group = first_char.upper() if first_char.isalpha() else "*"
            else:
                current_group = translate("By rating")

            if (
                mw.show_favorites_separators
                and current_group
                and current_group != mw.last_charts_all_artists_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "charts_artists", mw.artist_letters
                )
                main_layout.addWidget(separator_widget)
                mw.chart_detail_separator_widgets[current_group] = separator_widget
                mw.last_charts_all_artists_group = current_group
                mw.current_charts_all_artists_flow_layout = None

            target_layout = main_layout
            if mw.favorite_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_charts_all_artists_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_charts_all_artists_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_charts_all_artists_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_charts_all_artists_flow_layout

            if artist_data:
                play_count = artist_data.get("entity_rating", 0)
                subtitle_extra = translate("Rating: {count}", count=play_count)

                widget = self.components.create_artist_widget(
                    artist_name,
                    artist_data,
                    mw.favorite_view_mode,
                    subtitle_extra=subtitle_extra,
                )
                widget.activated.connect(
                    partial(self.show_top_artist_albums_view, artist_name)
                )

                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "artist"}
                    )
                )
                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "artist", "data": d}
                    )
                )
                target_layout.addWidget(widget)

        mw.charts_all_artists_loaded_count = end
        mw.is_loading_charts_all_artists = False

        if end >= len(mw.current_charts_all_artists_list):
            if mw.favorite_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_charts_all_artists)

    def _check_for_more_charts_all_artists(self):
        """
        Periodically checks if more top artists need to be loaded based on the current scroll state.
        """
        mw = self.main_window
        if not mw.chart_detail_scroll_area.widget():
            return
        scroll_bar = mw.chart_detail_scroll_area.verticalScrollBar()
        has_more = mw.charts_all_artists_loaded_count < len(
            mw.current_charts_all_artists_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_charts_all_artists()

    def show_all_top_genres_view(self):
        """
        Displays a detailed sub-view showing all top genres for the selected
        charts period, enabling the user to browse genres by rating or alphabet.
        """
        mw = self.main_window

        is_refresh = (
            mw.current_charts_context == "all_genres"
            and mw.charts_stack.currentIndex() == 1
            and mw.chart_detail_layout.count() > 0
        )

        if not is_refresh:
            mw.current_charts_context = "all_genres"
            mw.chart_detail_separator_widgets.clear()
            self.ui_manager.clear_layout(mw.chart_detail_header_layout)
            self.ui_manager.clear_layout(mw.chart_detail_layout)

        sort_rating_desc = create_svg_icon(
            "assets/control/sort_rating_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_rating_asc = create_svg_icon(
            "assets/control/sort_rating_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )

        control_widgets = []
        if not is_refresh:
            sort_options = [
                (
                    translate("By rating (most first)"),
                    sort_rating_desc,
                    SortMode.DATE_ADDED_DESC,
                ),
                (
                    translate("By rating (least first)"),
                    sort_rating_asc,
                    SortMode.DATE_ADDED_ASC,
                ),
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]

            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.charts_genre_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "charts_genre_sort_mode", action.data()),
                    self.show_all_top_genres_view(),
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
                mw.favorite_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_view_mode", action.data()),
                    self.show_all_top_genres_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            period_btn = self.create_period_selector()
            control_widgets = [period_btn, sort_button, view_button]

        items_all = mw.data_manager.genres_data.items()
        items = [item for item in items_all if item[1].get("entity_rating", 0) > 0]

        if mw.charts_genre_sort_mode == SortMode.ALPHA_ASC:
            items.sort(
                key=lambda i: (
                    mw.data_manager.get_sort_key(i[0]),
                    i[1].get("entity_rating", 0),
                )
            )
        elif mw.charts_genre_sort_mode == SortMode.ALPHA_DESC:
            items.sort(
                key=lambda i: (
                    mw.data_manager.get_sort_key(i[0]),
                    i[1].get("entity_rating", 0),
                ),
                reverse=True,
            )
        elif mw.charts_genre_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda i: i[1].get("entity_rating", 0))
        else:
            items.sort(
                key=lambda i: (
                    -i[1].get("entity_rating", 0),
                    mw.data_manager.get_sort_key(i[0]),
                )
            )

        mw.genre_letters = set()
        if mw.show_favorites_separators:
            for genre_name, _ in items:
                first_char = (
                    mw.data_manager.get_sort_key(genre_name)[0].upper()
                    if mw.data_manager.get_sort_key(genre_name)
                    else "*"
                )
                mw.genre_letters.add(first_char)

        mw.current_charts_all_genres_list = items
        mw.charts_all_genres_loaded_count = 0
        mw.is_loading_charts_all_genres = False
        mw.last_charts_all_genres_group = None
        mw.current_charts_all_genres_flow_layout = None

        title_text = translate("All Top Genres")
        details_text = translate("{count} genre(s)", count=len(items))
        period_text = self._get_period_display_text()
        combined_details = f"{period_text}  •  {details_text}"

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=title_text,
                details_text=combined_details,
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_top_genres",
                context_menu_data=("all_top_genres", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_top_genres")
                )
                mw.main_view_header_play_buttons["all_top_genres"] = play_button

            self.charts_genres_details_label = header_parts["details"]
            self.charts_genres_title_label = header_parts["title"]
            mw.chart_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.chart_detail_scroll_area = scroll_area
            mw.chart_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "charts_genres_details_label"):
                period_text = self._get_period_display_text()
                combined_details = f"{period_text}  •  {details_text}"
                self.charts_genres_details_label.setText(combined_details)
            if hasattr(self, "charts_genres_title_label"):
                self.charts_genres_title_label.setText(title_text)

        if mw.chart_detail_scroll_area.widget():
            mw.chart_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        mw.chart_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No top genres found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.chart_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_charts_all_genres
                )
            )
            self.load_more_charts_all_genres()

        if not is_refresh:
            mw.charts_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("charts"),
                context_data={"context": "all_genres"},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_charts_all_genres(self):
        """
        Lazily loads and renders the next batch of top genres during scrolling.
        """
        mw = self.main_window
        if mw.is_loading_charts_all_genres:
            return
        if mw.charts_all_genres_loaded_count >= len(mw.current_charts_all_genres_list):
            return

        mw.is_loading_charts_all_genres = True
        start = mw.charts_all_genres_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_charts_all_genres_list))

        container = mw.chart_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            genre_name, genre_data = mw.current_charts_all_genres_list[i]

            sort_name = mw.data_manager.get_sort_key(genre_name)
            first_char = sort_name[0] if sort_name else "*"

            current_group = None
            if mw.charts_genre_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                current_group = first_char.upper() if first_char.isalpha() else "*"
            else:
                current_group = translate("By rating")

            if (
                mw.show_favorites_separators
                and current_group
                and current_group != mw.last_charts_all_genres_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "charts_genres", mw.genre_letters
                )
                main_layout.addWidget(separator_widget)
                mw.chart_detail_separator_widgets[current_group] = separator_widget
                mw.last_charts_all_genres_group = current_group
                mw.current_charts_all_genres_flow_layout = None

            target_layout = main_layout
            if mw.favorite_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_charts_all_genres_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_charts_all_genres_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_charts_all_genres_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_charts_all_genres_flow_layout

            if genre_data:
                play_count = genre_data.get("entity_rating", 0)
                subtitle_extra = translate("Rating: {count}", count=play_count)

                widget = self.components.create_genre_widget(
                    genre_name,
                    genre_data,
                    mw.favorite_view_mode,
                    subtitle_extra=subtitle_extra,
                )
                widget.activated.connect(
                    partial(self.show_top_genre_albums_view, genre_name)
                )

                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "genre"}
                    )
                )
                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "genre", "data": d}
                    )
                )
                target_layout.addWidget(widget)

        mw.charts_all_genres_loaded_count = end
        mw.is_loading_charts_all_genres = False

        if end >= len(mw.current_charts_all_genres_list):
            if mw.favorite_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_charts_all_genres)

    def _check_for_more_charts_all_genres(self):
        """
        Periodically checks if more top genres need to be loaded based on scroll capacity.
        """
        mw = self.main_window
        if not mw.chart_detail_scroll_area.widget():
            return
        scroll_bar = mw.chart_detail_scroll_area.verticalScrollBar()
        has_more = mw.charts_all_genres_loaded_count < len(
            mw.current_charts_all_genres_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_charts_all_genres()

    def show_all_top_composers_view(self):
        """
        Displays a detailed sub-view showing all top composers for the active
        charts period, allowing users to interact with composer cards.
        """
        mw = self.main_window

        is_refresh = (
            mw.current_charts_context == "all_composers"
            and mw.charts_stack.currentIndex() == 1
            and mw.chart_detail_layout.count() > 0
        )

        if not is_refresh:
            mw.current_charts_context = "all_composers"
            mw.chart_detail_separator_widgets.clear()
            self.ui_manager.clear_layout(mw.chart_detail_header_layout)
            self.ui_manager.clear_layout(mw.chart_detail_layout)

        sort_rating_desc = create_svg_icon(
            "assets/control/sort_rating_desc.svg",
            theme.COLORS["PRIMARY"],
            QSize(24, 24),
        )
        sort_rating_asc = create_svg_icon(
            "assets/control/sort_rating_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_desc = create_svg_icon(
            "assets/control/sort_alpha_desc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        sort_alpha_asc = create_svg_icon(
            "assets/control/sort_alpha_asc.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )

        control_widgets = []
        if not is_refresh:
            sort_options = [
                (
                    translate("By rating (most first)"),
                    sort_rating_desc,
                    SortMode.DATE_ADDED_DESC,
                ),
                (
                    translate("By rating (least first)"),
                    sort_rating_asc,
                    SortMode.DATE_ADDED_ASC,
                ),
                (translate("Alphabetical (A-Z)"), sort_alpha_asc, SortMode.ALPHA_ASC),
                (translate("Alphabetical (Z-A)"), sort_alpha_desc, SortMode.ALPHA_DESC),
            ]

            sort_button = self.components.create_tool_button_with_menu(
                sort_options, mw.charts_artist_sort_mode
            )
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "charts_artist_sort_mode", action.data()),
                    self.show_all_top_composers_view(),
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
                mw.favorite_view_mode,
            )
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "favorite_view_mode", action.data()),
                    self.show_all_top_composers_view(),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            period_btn = self.create_period_selector()
            control_widgets = [period_btn, sort_button, view_button]

        items_all = mw.data_manager.composers_data.items()
        items = [item for item in items_all if item[1].get("entity_rating", 0) > 0]

        if mw.charts_artist_sort_mode == SortMode.ALPHA_ASC:
            items.sort(
                key=lambda i: (
                    mw.data_manager.get_sort_key(i[0]),
                    i[1].get("entity_rating", 0),
                )
            )
        elif mw.charts_artist_sort_mode == SortMode.ALPHA_DESC:
            items.sort(
                key=lambda i: (
                    mw.data_manager.get_sort_key(i[0]),
                    i[1].get("entity_rating", 0),
                ),
                reverse=True,
            )
        elif mw.charts_artist_sort_mode == SortMode.DATE_ADDED_ASC:
            items.sort(key=lambda i: i[1].get("entity_rating", 0))
        else:
            items.sort(
                key=lambda i: (
                    -i[1].get("entity_rating", 0),
                    mw.data_manager.get_sort_key(i[0]),
                )
            )

        mw.artist_letters = set()
        if mw.show_favorites_separators:
            for artist_name, _ in items:
                first_char = (
                    mw.data_manager.get_sort_key(artist_name)[0].upper()
                    if mw.data_manager.get_sort_key(artist_name)
                    else "*"
                )
                mw.artist_letters.add(first_char)

        mw.current_charts_all_composers_list = items
        mw.charts_all_composers_loaded_count = 0
        mw.is_loading_charts_all_composers = False
        mw.last_charts_all_composers_group = None
        mw.current_charts_all_composers_flow_layout = None

        title_text = translate("All Top Composers")
        details_text = translate("{count} artist(s)", count=len(items))
        period_text = self._get_period_display_text()
        combined_details = f"{period_text}  •  {details_text}"

        if not is_refresh:
            header_parts = self.components.create_page_header(
                title=title_text,
                details_text=combined_details,
                back_slot=self.ui_manager.navigate_back,
                control_widgets=control_widgets,
                play_slot_data="all_top_composers",
                context_menu_data=("all_top_composers", "system_list"),
            )
            if play_button := header_parts.get("play_button"):
                play_button.clicked.connect(
                    lambda: mw.player_controller.play_data("all_top_composers")
                )
                mw.main_view_header_play_buttons["all_top_composers"] = play_button

            self.charts_composers_details_label = header_parts["details"]
            self.charts_composers_title_label = header_parts["title"]

            mw.chart_detail_header_layout.addWidget(header_parts["header"])

            scroll_area = StyledScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setProperty("class", "backgroundPrimary")
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            mw.chart_detail_scroll_area = scroll_area
            mw.chart_detail_layout.addWidget(scroll_area, 1)
        else:
            if hasattr(self, "charts_composers_details_label"):
                period_text = self._get_period_display_text()
                combined_details = f"{period_text}  •  {details_text}"
                self.charts_composers_details_label.setText(combined_details)
            if hasattr(self, "charts_composers_title_label"):
                self.charts_composers_title_label.setText(title_text)

        if mw.chart_detail_scroll_area.widget():
            mw.chart_detail_scroll_area.widget().deleteLater()

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        mw.chart_detail_scroll_area.setWidget(container)

        if not items:
            text_label = QLabel(translate("No top composers found."))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label)
            main_layout.addStretch(1)
        else:
            scroll_bar = mw.chart_detail_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_charts_all_composers
                )
            )
            self.load_more_charts_all_composers()

        if not is_refresh:
            mw.charts_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("charts"),
                context_data={"context": "all_composers"},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_charts_all_composers(self):
        """
        Lazily loads and displays the next batch of top composers in the view.
        """
        mw = self.main_window
        if mw.is_loading_charts_all_composers:
            return
        if mw.charts_all_composers_loaded_count >= len(
            mw.current_charts_all_composers_list
        ):
            return

        mw.is_loading_charts_all_composers = True
        start = mw.charts_all_composers_loaded_count
        end = min(start + BATCH_SIZE, len(mw.current_charts_all_composers_list))

        container = mw.chart_detail_scroll_area.widget()
        if not container:
            return
        main_layout = container.layout()

        for i in range(start, end):
            artist_name, artist_data = mw.current_charts_all_composers_list[i]

            sort_name = mw.data_manager.get_sort_key(artist_name)
            first_char = sort_name[0] if sort_name else "*"

            current_group = None
            if mw.charts_artist_sort_mode in [SortMode.ALPHA_ASC, SortMode.ALPHA_DESC]:
                current_group = first_char.upper() if first_char.isalpha() else "*"
            else:
                current_group = translate("By rating")

            if (
                mw.show_favorites_separators
                and current_group
                and current_group != mw.last_charts_all_composers_group
            ):
                separator_widget = self.components._create_separator_widget(
                    current_group, "charts_composers", mw.artist_letters
                )
                main_layout.addWidget(separator_widget)
                mw.chart_detail_separator_widgets[current_group] = separator_widget
                mw.last_charts_all_composers_group = current_group
                mw.current_charts_all_composers_flow_layout = None

            target_layout = main_layout
            if mw.favorite_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_charts_all_composers_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_charts_all_composers_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_charts_all_composers_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_charts_all_composers_flow_layout

            if artist_data:
                play_count = artist_data.get("entity_rating", 0)
                subtitle_extra = translate("Rating: {count}", count=play_count)

                widget = self.components.create_artist_widget(
                    artist_name,
                    artist_data,
                    mw.favorite_view_mode,
                    subtitle_extra=subtitle_extra,
                )
                widget.activated.connect(
                    partial(self.show_top_artist_albums_view, artist_name)
                )

                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "composer"}
                    )
                )
                widget.playClicked.connect(
                    lambda d: mw.player_controller.play_data(
                        {"type": "composer", "data": d}
                    )
                )
                target_layout.addWidget(widget)

        mw.charts_all_composers_loaded_count = end
        mw.is_loading_charts_all_composers = False

        if end >= len(mw.current_charts_all_composers_list):
            if mw.favorite_view_mode not in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                main_layout.addStretch(1)

        QTimer.singleShot(100, self._check_for_more_charts_all_composers)

    def _check_for_more_charts_all_composers(self):
        """
        Periodically checks if more top composers should be loaded during scrolling.
        """
        mw = self.main_window
        if not mw.chart_detail_scroll_area.widget():
            return
        scroll_bar = mw.chart_detail_scroll_area.verticalScrollBar()
        has_more = mw.charts_all_composers_loaded_count < len(
            mw.current_charts_all_composers_list
        )
        if scroll_bar.maximum() == 0 and has_more:
            self.load_more_charts_all_composers()

    def _populate_charts_sub_view_lazy(
        self,
        scroll_area,
        view_mode_setting_attr,
        enc_key=None,
        enc_type=None,
        enc_refresh_callback=None,
    ):
        """
        Prepares the layout and structure for a lazy-loaded secondary sub-view
        (like an artist's discography) inside the charts tab.

        Args:
            scroll_area (StyledScrollArea): The scroll area to hold the layout.
            view_mode_setting_attr (str): Attribute name representing the current view mode state.
            enc_key (str, optional): The key for the encyclopedia context.
            enc_type (str, optional): The type of entity for the encyclopedia.
            enc_refresh_callback (callable, optional): Callback triggered when refreshing the encyclopedia view.
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

        mw.active_charts_layout_target = target_layout

        scroll_area.setWidget(root_container)

    def show_top_artist_albums_view(self, artist_name):
        """
        Displays a specific artist's top albums in a dedicated sub-view.

        Args:
            artist_name (str): The name of the artist to display.
        """
        mw = self.main_window

        is_refresh = (
            mw.current_artist_view == artist_name
            and mw.current_charts_context == "artist"
            and mw.charts_stack.currentIndex() == 1
            and mw.chart_detail_layout.count() > 0
        )

        if not is_refresh:
            mw.current_artist_view = artist_name
            mw.current_charts_context = "artist"
            self.ui_manager.clear_layout(mw.chart_detail_header_layout)
            self.ui_manager.clear_layout(mw.chart_detail_layout)

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
                mw.artist_album_sort_mode,
            )
            sort_button.setFixedHeight(36)
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "artist_album_sort_mode", action.data()),
                    self.show_top_artist_albums_view(artist_name),
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
                mw.artist_album_view_mode,
            )
            view_button.setFixedHeight(36)
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "artist_album_view_mode", action.data()),
                    self.show_top_artist_albums_view(artist_name),
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

            mw.chart_detail_header_layout.addWidget(header_parts["header"])

        artist_data = mw.data_manager.artists_data.get(artist_name, {})
        album_keys_for_artist = artist_data.get("albums", [])
        albums_of_artist = [
            (tuple(key), mw.data_manager.albums_data[tuple(key)])
            for key in album_keys_for_artist
            if tuple(key) in mw.data_manager.albums_data
        ]

        sort_mode = mw.artist_album_sort_mode
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

        mw.current_charts_artist_album_list = albums_of_artist
        mw.charts_artist_albums_loaded_count = 0

        if not is_refresh:
            mw.charts_sub_view_scroll_area = StyledScrollArea()
            mw.charts_sub_view_scroll_area.setProperty("class", "backgroundPrimary")
            mw.charts_sub_view_scroll_area.setWidgetResizable(True)

        self._populate_charts_sub_view_lazy(
            mw.charts_sub_view_scroll_area,
            "artist_album_view_mode",
            enc_key=artist_name,
            enc_type="artist",
            enc_refresh_callback=lambda: self.show_top_artist_albums_view(artist_name),
        )

        if not is_refresh:
            scroll_bar = mw.charts_sub_view_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_charts_artist_albums
                )
            )

        self.load_more_charts_artist_albums()

        if not is_refresh:
            mw.chart_detail_layout.addWidget(mw.charts_sub_view_scroll_area)
            mw.charts_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("charts"),
                context_data={"context": "artist", "data": artist_name},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_charts_artist_albums(self):
        """
        Lazily loads and displays the next batch of albums for the specific artist view.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "active_charts_layout_target")
            or mw.active_charts_layout_target is None
        ):
            return
        if mw.is_loading_charts_artist_albums:
            return
        if mw.charts_artist_albums_loaded_count >= len(
            mw.current_charts_artist_album_list
        ):
            return

        mw.is_loading_charts_artist_albums = True

        start = mw.charts_artist_albums_loaded_count
        batch_size = (
            BATCH_SIZE_ALLTRACKS
            if mw.artist_album_view_mode == ViewMode.ALL_TRACKS
            else BATCH_SIZE
        )
        end = min(start + batch_size, len(mw.current_charts_artist_album_list))

        target_layout = mw.active_charts_layout_target

        for i in range(start, end):
            album_key, data = mw.current_charts_artist_album_list[i]
            if mw.artist_album_view_mode == ViewMode.ALL_TRACKS:
                widget = self.components._create_detailed_album_widget(
                    album_key, data, tracks_to_show=None
                )
                target_layout.addWidget(widget)
                if i < len(mw.current_charts_artist_album_list) - 1:
                    separator = QWidget()
                    separator.setFixedHeight(1)
                    separator.setProperty("class", "separator")
                    target_layout.addWidget(separator)
            else:
                widget = self.components.create_album_widget(
                    album_key, data, mw.artist_album_view_mode, show_artist=False
                )
                widget.activated.connect(
                    partial(
                        self.ui_manager.show_album_tracks, source_stack=mw.charts_stack
                    )
                )

                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "album"}
                    )
                )
                widget.playClicked.connect(mw.player_controller.play_data)
                target_layout.addWidget(widget)

        mw.charts_artist_albums_loaded_count = end
        mw.is_loading_charts_artist_albums = False
        self.ui_manager.update_all_track_widgets()

        QTimer.singleShot(100, self._check_for_more_charts_artist_albums)

    def _check_for_more_charts_artist_albums(self):
        """
        Periodically checks the scrollbar position to verify if more artist albums need to be loaded.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "charts_sub_view_scroll_area")
            or not mw.charts_sub_view_scroll_area.widget()
        ):
            return
        scroll_bar = mw.charts_sub_view_scroll_area.verticalScrollBar()
        has_more_data = mw.charts_artist_albums_loaded_count < len(
            mw.current_charts_artist_album_list
        )
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_charts_artist_albums()

    def show_top_genre_albums_view(self, genre_name):
        """
        Displays a specific genre's top albums in a dedicated sub-view.

        Args:
            genre_name (str): The name of the genre to display.
        """
        mw = self.main_window

        is_refresh = (
            mw.current_genre_view == genre_name
            and mw.current_charts_context == "genre"
            and mw.charts_stack.currentIndex() == 1
            and mw.chart_detail_layout.count() > 0
        )

        if not is_refresh:
            mw.current_genre_view = genre_name
            mw.current_charts_context = "genre"
            self.ui_manager.clear_layout(mw.chart_detail_header_layout)
            self.ui_manager.clear_layout(mw.chart_detail_layout)

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
                mw.artist_album_sort_mode,
            )

            sort_button.setFixedHeight(36)
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "artist_album_sort_mode", action.data()),
                    self.show_top_genre_albums_view(genre_name),
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
                mw.artist_album_view_mode,
            )
            view_button.setFixedHeight(36)
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "artist_album_view_mode", action.data()),
                    self.show_top_genre_albums_view(genre_name),
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
            albums_text = translate("{count} album(s)", count=album_count)
            tracks_text = translate("{count} track(s)", count=track_count)
            details_text = f"{albums_text}, {tracks_text}"

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

            mw.chart_detail_header_layout.addWidget(header_parts["header"])

        album_keys = mw.data_manager.genres_data.get(genre_name, {}).get(
            "albums", set()
        )
        albums_of_genre = [
            (key, mw.data_manager.albums_data[key])
            for key in album_keys
            if key in mw.data_manager.albums_data
        ]

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

        mw.current_charts_genre_album_list = albums_of_genre
        mw.charts_genre_albums_loaded_count = 0
        mw.is_loading_charts_genre_albums = False

        if not is_refresh:
            mw.charts_sub_view_scroll_area = StyledScrollArea()
            mw.charts_sub_view_scroll_area.setProperty("class", "backgroundPrimary")
            mw.charts_sub_view_scroll_area.setWidgetResizable(True)

        self._populate_charts_sub_view_lazy(
            mw.charts_sub_view_scroll_area,
            "artist_album_view_mode",
            enc_key=genre_name,
            enc_type="genre",
            enc_refresh_callback=lambda: self.show_top_genre_albums_view(genre_name),
        )

        if not is_refresh:
            scroll_bar = mw.charts_sub_view_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_charts_genre_albums
                )
            )

        self.load_more_charts_genre_albums()

        if not is_refresh:
            mw.chart_detail_layout.addWidget(mw.charts_sub_view_scroll_area)
            mw.charts_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("charts"),
                context_data={"context": "genre", "data": genre_name},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_charts_genre_albums(self):
        """
        Lazily loads and renders the next batch of albums for the specific genre view.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "active_charts_layout_target")
            or mw.active_charts_layout_target is None
        ):
            return
        if mw.is_loading_charts_genre_albums:
            return
        if mw.charts_genre_albums_loaded_count >= len(
            mw.current_charts_genre_album_list
        ):
            return

        mw.is_loading_charts_genre_albums = True

        batch = (
            BATCH_SIZE_ALLTRACKS
            if mw.artist_album_view_mode == ViewMode.ALL_TRACKS
            else BATCH_SIZE
        )
        start = mw.charts_genre_albums_loaded_count
        end = min(start + batch, len(mw.current_charts_genre_album_list))

        target_layout = mw.active_charts_layout_target

        for i in range(start, end):
            album_key, data = mw.current_charts_genre_album_list[i]

            if mw.artist_album_view_mode == ViewMode.ALL_TRACKS:
                widget = self.components._create_detailed_album_widget(
                    album_key, data, tracks_to_show=None
                )
                target_layout.addWidget(widget)
                if i < len(mw.current_charts_genre_album_list) - 1:
                    separator = QWidget()
                    separator.setFixedHeight(1)
                    separator.setProperty("class", "separator")
                    target_layout.addWidget(separator)
            else:
                widget = self.components.create_album_widget(
                    album_key, data, mw.artist_album_view_mode, show_artist=True
                )
                widget.activated.connect(
                    partial(
                        self.ui_manager.show_album_tracks, source_stack=mw.charts_stack
                    )
                )

                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "album"}
                    )
                )
                widget.playClicked.connect(mw.player_controller.play_data)
                target_layout.addWidget(widget)

        mw.charts_genre_albums_loaded_count = end
        mw.is_loading_charts_genre_albums = False

        QTimer.singleShot(100, self._check_for_more_charts_genre_albums)

    def _check_for_more_charts_genre_albums(self):
        """
        Periodically checks the scrollbar position to verify if more genre albums need to be loaded.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "charts_sub_view_scroll_area")
            or not mw.charts_sub_view_scroll_area.widget()
        ):
            return
        scroll_bar = mw.charts_sub_view_scroll_area.verticalScrollBar()
        has_more_data = mw.charts_genre_albums_loaded_count < len(
            mw.current_charts_genre_album_list
        )
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_charts_genre_albums()

    def show_top_composer_albums_view(self, composer_name):
        """
        Displays a specific composer's top albums in a dedicated sub-view.

        Args:
            composer_name (str): The name of the composer to display.
        """
        mw = self.main_window

        is_refresh = (
            mw.current_composer_view == composer_name
            and mw.current_charts_context == "composer"
            and mw.charts_stack.currentIndex() == 1
            and mw.chart_detail_layout.count() > 0
        )

        if not is_refresh:
            mw.current_composer_view = composer_name
            mw.current_charts_context = "composer"
            self.ui_manager.clear_layout(mw.chart_detail_header_layout)
            self.ui_manager.clear_layout(mw.chart_detail_layout)

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
                mw.composer_album_sort_mode,
            )
            sort_button.setFixedHeight(36)
            sort_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "composer_album_sort_mode", action.data()),
                    self.show_top_composer_albums_view(composer_name),
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
                mw.composer_album_view_mode,
            )
            view_button.setFixedHeight(36)
            view_button.menu().triggered.connect(
                lambda action: (
                    setattr(mw, "composer_album_view_mode", action.data()),
                    self.show_top_composer_albums_view(composer_name),
                )
            )
            set_custom_tooltip(
                view_button,
                title = translate("View Options"),
            )
            fav_button = self.components._create_favorite_button(composer_name, "composer")

            composer_data = mw.data_manager.composers_data.get(composer_name, {})
            album_keys_for_composer = composer_data.get("albums", [])
            albums_of_composer = [
                (tuple(key), mw.data_manager.albums_data[tuple(key)])
                for key in album_keys_for_composer
                if tuple(key) in mw.data_manager.albums_data
            ]

            album_count = len(albums_of_composer)
            track_count = mw.data_manager.composers_data.get(composer_name, {}).get(
                "track_count", 0
            )
            albums_text = translate("{count} album(s)", count=album_count)
            tracks_text = translate("{count} track(s)", count=track_count)
            details_text = f"{albums_text}, {tracks_text}"

            header_parts = self.components.create_page_header(
                translate("{composer_name}: Albums", composer_name=composer_name),
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
                mw.data_manager.composers_data[composer_name],
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

            mw.chart_detail_header_layout.addWidget(header_parts["header"])

        composer_data = mw.data_manager.composers_data.get(composer_name, {})
        album_keys_for_composer = composer_data.get("albums", [])
        albums_of_composer = [
            (tuple(key), mw.data_manager.albums_data[tuple(key)])
            for key in album_keys_for_composer
            if tuple(key) in mw.data_manager.albums_data
        ]

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

        mw.current_charts_composer_album_list = albums_of_composer
        mw.charts_composer_albums_loaded_count = 0
        mw.is_loading_charts_composer_albums = False

        if not is_refresh:
            mw.charts_sub_view_scroll_area = StyledScrollArea()
            mw.charts_sub_view_scroll_area.setProperty("class", "backgroundPrimary")
            mw.charts_sub_view_scroll_area.setWidgetResizable(True)

        self._populate_charts_sub_view_lazy(
            mw.charts_sub_view_scroll_area,
            "composer_album_view_mode",
            enc_key=composer_name,
            enc_type="composer",
            enc_refresh_callback=lambda: self.show_top_composer_albums_view(
                composer_name
            ),
        )

        if not is_refresh:
            scroll_bar = mw.charts_sub_view_scroll_area.verticalScrollBar()
            scroll_bar.valueChanged.connect(
                lambda value: self.ui_manager.check_scroll_and_load(
                    value, scroll_bar, self.load_more_charts_composer_albums
                )
            )

        self.load_more_charts_composer_albums()

        if not is_refresh:
            mw.chart_detail_layout.addWidget(mw.charts_sub_view_scroll_area)
            mw.charts_stack.setCurrentIndex(1)
            mw.update_current_view_state(
                main_tab_index=mw.nav_button_icon_names.index("charts"),
                context_data={"context": "composer", "data": composer_name},
            )
        self.ui_manager.update_all_track_widgets()

    def load_more_charts_composer_albums(self):
        """
        Lazily loads and renders the next batch of albums for the specific composer view.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "active_charts_layout_target")
            or mw.active_charts_layout_target is None
        ):
            return
        if mw.is_loading_charts_composer_albums:
            return
        if mw.charts_composer_albums_loaded_count >= len(
            mw.current_charts_composer_album_list
        ):
            return

        mw.is_loading_charts_composer_albums = True

        start = mw.charts_composer_albums_loaded_count
        batch_size = (
            BATCH_SIZE_ALLTRACKS
            if mw.composer_album_view_mode == ViewMode.ALL_TRACKS
            else BATCH_SIZE
        )
        end = min(start + batch_size, len(mw.current_charts_composer_album_list))

        target_layout = mw.active_charts_layout_target

        for i in range(start, end):
            album_key, data = mw.current_charts_composer_album_list[i]
            if mw.composer_album_view_mode == ViewMode.ALL_TRACKS:
                widget = self.components._create_detailed_album_widget(
                    album_key, data, tracks_to_show=None
                )
                target_layout.addWidget(widget)
                if i < len(mw.current_charts_composer_album_list) - 1:
                    separator = QWidget()
                    separator.setFixedHeight(1)
                    separator.setProperty("class", "separator")
                    target_layout.addWidget(separator)
            else:
                widget = self.components.create_album_widget(
                    album_key, data, mw.composer_album_view_mode, show_artist=False
                )
                widget.activated.connect(
                    partial(
                        self.ui_manager.show_album_tracks, source_stack=mw.charts_stack
                    )
                )

                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_context_menu(
                        d, p, context={"forced_type": "album"}
                    )
                )
                widget.playClicked.connect(mw.player_controller.play_data)
                target_layout.addWidget(widget)

        mw.charts_composer_albums_loaded_count = end
        mw.is_loading_charts_composer_albums = False
        self.ui_manager.update_all_track_widgets()

        QTimer.singleShot(100, self._check_for_more_charts_composer_albums)

    def _check_for_more_charts_composer_albums(self):
        """
        Periodically checks the scrollbar position to verify if more composer albums need to be loaded.
        """
        mw = self.main_window
        if (
            not hasattr(mw, "charts_sub_view_scroll_area")
            or not mw.charts_sub_view_scroll_area.widget()
        ):
            return
        scroll_bar = mw.charts_sub_view_scroll_area.verticalScrollBar()
        has_more_data = mw.charts_composer_albums_loaded_count < len(
            mw.current_charts_composer_album_list
        )
        if scroll_bar.maximum() == 0 and has_more_data:
            self.load_more_charts_composer_albums()

    def show_archived_month_view(self, month_key: str):
        """
        Displays a summary view for a specific archived month, outlining the
        top entities (tracks, artists, etc.) available for that past month.

        Args:
            month_key (str): The identifier key for the archived month (e.g., '2026-03').
        """
        mw = self.main_window
        mw.current_charts_context = "archive_month"
        self.ui_manager.clear_layout(mw.chart_detail_header_layout)
        self.ui_manager.clear_layout(mw.chart_detail_layout)

        try:
            month_data = mw.library_manager.load_charts_archive().get(month_key)
            if not month_data:
                raise ValueError(f"No data for key {month_key}")
        except Exception as e:
            print(f"Unable to load archive data for {month_key}: {e}")
            header_parts = self.components.create_page_header(
                title=translate("Error"),
                details_text=translate("Could not load archive data."),
                back_slot=self.ui_manager.navigate_back,
            )
            mw.chart_detail_header_layout.addWidget(header_parts["header"])
            mw.charts_stack.setCurrentIndex(1)
            return

        title = format_month_year(month_key)
        play_data = (month_key, "month_overview")

        header_parts = self.components.create_page_header(
            title=title,
            details_text=translate("Charts Archive"),
            back_slot=self.ui_manager.navigate_back,
        )

        mw.chart_detail_header_layout.addWidget(header_parts["header"])

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setProperty("class", "backgroundPrimary")
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        scroll_area.setWidget(container)

        flow_container = QWidget()
        flow_layout = FlowLayout(flow_container, stretch_items=True)
        flow_layout.setSpacing(16)

        categories_to_show = [
            ("tracks", translate("Top Tracks"), self.components.top_track_cover_pixmap),
            (
                "artists",
                translate("Top Artists"),
                self.components.top_artist_cover_pixmap,
            ),
            ("albums", translate("Top Albums"), self.components.top_album_cover_pixmap),
            ("genres", translate("Top Genres"), self.components.top_genre_cover_pixmap),
            (
                "composers",
                translate("Top Composers"),
                self.components.top_artist_cover_pixmap,
            ),
        ]

        found_categories = False

        for cat_key, cat_title, cat_pixmap_base in categories_to_show:
            if chart_list := month_data.get(cat_key):
                found_categories = True
                pixmap = cat_pixmap_base
                count = len(chart_list)
                subtitle = translate("{count} item(s)", count=count)
                hashable_data_key = (cat_key, month_key)

                widget = CardWidget(
                    data=hashable_data_key,
                    view_mode=mw.favorite_view_mode,
                    pixmaps=[pixmap],
                    title=cat_title,
                    subtitle1=subtitle,
                    is_artist_card=False,
                )
                widget.contextMenuRequested.connect(
                    lambda d, p: mw.action_handler.show_favorite_tracks_card_context_menu(
                        d, p
                    )
                )
                widget.activated.connect(
                    partial(self.show_archived_detail_view, month_key, cat_key)
                )
                widget.playClicked.connect(mw.player_controller.play_data)
                widget.pauseClicked.connect(mw.player.pause)
                mw.main_view_card_widgets[hashable_data_key].append(widget)
                flow_layout.addWidget(widget)

        if not found_categories:
            text_label = QLabel(translate("This archive entry is empty"))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(flow_container)
        main_layout.addStretch(1)
        mw.chart_detail_layout.addWidget(scroll_area, 1)

        mw.charts_stack.setCurrentIndex(1)
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("charts"),
            context_data={"context": "archive_month", "data": month_key},
        )

    def show_archived_detail_view(self, month_key: str, chart_type: str):
        """
        Displays a detailed list of archived items (tracks, artists, albums, etc.)
        for a specific month and chart category.

        Args:
            month_key (str): The archived month key.
            chart_type (str): The type of entity to list (e.g., 'tracks', 'albums').
        """
        mw = self.main_window
        mw.current_charts_context = f"archive_detail_{chart_type}"
        self.ui_manager.clear_layout(mw.chart_album_detail_header_layout)
        self.ui_manager.clear_layout(mw.chart_album_detail_layout)

        try:
            chart_list = (
                mw.library_manager.load_charts_archive()
                .get(month_key, {})
                .get(chart_type)
            )
            if chart_list is None:
                raise ValueError(f"No data for {month_key} -> {chart_type}")
        except Exception as e:
            print(
                f"Unable to load archive data for {month_key} -> {chart_type}: {e}"
            )
            return

        title_map = {
            "tracks": translate("Top Tracks"),
            "artists": translate("Top Artists"),
            "albums": translate("Top Albums"),
            "genres": translate("Top Genres"),
            "composers": translate("Top Composers"),
        }
        title = f"{title_map.get(chart_type, chart_type.capitalize())} - {format_month_year(month_key)}"

        play_data = (chart_type, month_key)

        header_parts = self.components.create_page_header(
            title=title,
            details_text=translate("{count} item(s)", count=len(chart_list)),
            back_slot=self.ui_manager.navigate_back,
            play_slot_data=play_data,
            context_menu_data=(play_data, "system_list"),
        )

        if play_button := header_parts.get("play_button"):
            play_button.clicked.connect(
                lambda: mw.player_controller.play_data(play_data)
            )
            mw.main_view_header_play_buttons[play_data] = play_button

        mw.chart_album_detail_header_layout.addWidget(header_parts["header"])

        scroll_area = StyledScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setProperty("class", "backgroundPrimary")
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setProperty("class", "backgroundPrimary")
        container.setContentsMargins(24, 24, 24, 24)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        scroll_area.setWidget(container)

        if not chart_list:
            text_label = QLabel(translate("This Chart is empty"))
            text_label.setProperty("class", "textColorPrimary")
            main_layout.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignCenter)
            main_layout.addStretch(1)
            mw.chart_album_detail_layout.addWidget(scroll_area, 1)
            mw.charts_stack.setCurrentIndex(2)
            return

        if chart_type == "tracks":
            tracks_with_scores = []
            for path, score in chart_list:
                track_obj = mw.data_manager.get_track_by_path(path)
                if track_obj:
                    track_copy = track_obj.copy()
                    track_copy["play_count"] = score
                    tracks_with_scores.append(track_copy)
                else:
                    tracks_with_scores.append(
                        {
                            "path": path,
                            "title": translate(
                                "[File not found] {filename}",
                                filename=os.path.basename(path),
                            ),
                            "artists": ["---"],
                            "play_count": score,
                        }
                    )

            playlist_widget = self.components._create_detailed_playlist_widget(
                playlist_path=f"archive_{month_key}_tracks",
                playlist_name=title,
                tracks=tracks_with_scores,
                pixmap=self.components.top_track_cover_pixmap.scaled(128, 128),
                show_score=True,
            )
            if hasattr(playlist_widget, "playlistContextMenu"):
                try:
                    playlist_widget.playlistContextMenu.disconnect()
                except TypeError:
                    pass

            main_layout.addWidget(playlist_widget)

        else:
            flow_container = QWidget()
            flow_layout = FlowLayout(flow_container, stretch_items=True)
            flow_layout.setSpacing(16)

            item_data_map = None
            create_widget_func = None
            activate_func = None

            if chart_type == "artists":
                item_data_map = mw.data_manager.artists_data
                create_widget_func = self.components.create_artist_widget
                activate_func = self.show_top_artist_albums_view
            elif chart_type == "albums":
                item_data_map = mw.data_manager.albums_data
                create_widget_func = self.components.create_album_widget
                activate_func = partial(
                    self.ui_manager.show_album_tracks, source_stack=mw.charts_stack
                )
            elif chart_type == "genres":
                item_data_map = mw.data_manager.genres_data
                create_widget_func = self.components.create_genre_widget
                activate_func = self.show_top_genre_albums_view
            elif chart_type == "composers":
                item_data_map = mw.data_manager.composers_data
                create_widget_func = self.components.create_composer_widget
                activate_func = self.show_top_composer_albums_view

            if not item_data_map or not create_widget_func:
                pass
            else:
                for item_key_str, score in chart_list:
                    item_key = item_key_str
                    if chart_type == "albums":
                        try:
                            item_key = tuple(json.loads(item_key_str))
                        except Exception:
                            continue

                    item_data = item_data_map.get(item_key)
                    if not item_data and chart_type == "albums" and len(item_key) >= 2:
                        target_artist = item_key[0]
                        target_album = item_key[1]
                        for real_key, real_data in item_data_map.items():
                            if (
                                isinstance(real_key, tuple)
                                and len(real_key) >= 2
                                and real_key[0] == target_artist
                                and real_key[1] == target_album
                            ):
                                item_data = real_data
                                item_key = real_key
                                break

                    subtitle_extra = translate("Rating: {count}", count=score)

                    if item_data:
                        widget = create_widget_func(
                            item_key,
                            item_data,
                            mw.favorite_view_mode,
                            subtitle_extra=subtitle_extra,
                        )
                        if activate_func:
                            widget.activated.connect(partial(activate_func, item_key))

                        widget.contextMenuRequested.connect(
                            mw.action_handler.show_context_menu
                        )
                        widget.playClicked.connect(mw.player_controller.play_data)
                        mw.main_view_card_widgets[item_key].append(widget)

                    else:
                        title_text = (
                            item_key
                            if isinstance(item_key, str)
                            else (item_key[1] if len(item_key) > 1 else "Unknown")
                        )
                        widget = CardWidget(
                            data=item_key,
                            view_mode=mw.favorite_view_mode,
                            pixmaps=[self.components.get_pixmap(None, 128)],
                            title=f"[{translate('Not found')}] {title_text}",
                            subtitle_extra=subtitle_extra,
                            is_artist_card=(chart_type == "artists"),
                        )
                        widget.setEnabled(False)

                    flow_layout.addWidget(widget)

                main_layout.addWidget(flow_container)

        main_layout.addStretch(1)
        mw.chart_album_detail_layout.addWidget(scroll_area, 1)

        mw.charts_stack.setCurrentIndex(2)
        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("charts"),
            context_data={"context": f"archive_detail_{chart_type}", "data": month_key},
        )
        self.ui_manager.update_all_track_widgets()

