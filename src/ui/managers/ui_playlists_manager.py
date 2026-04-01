"""
Vinyller — Playlists UI manager
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

from PyQt6.QtCore import QTimer, QModelIndex
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QFrame

from src.ui.custom_base_widgets import StyledScrollArea
from src.ui.custom_cards import CardWidget
from src.ui.custom_classes import FlowLayout, SortMode, ViewMode
from src.utils.constants import BATCH_SIZE
from src.utils.utils import format_time
from src.utils.utils_translator import translate


class PlaylistsUIManager:
    """
    Class managing the UI logic and state for the playlists tab.
    """

    def __init__(self, main_window, ui_manager):
        """
        Initializes the PlaylistsUIManager.
        """
        self.main_window = main_window
        self.ui_manager = ui_manager

    def populate_playlists_tab(self):
        """
        Populates the main playlists tab with available custom playlists.
        """
        mw = self.main_window

        mw.current_playlist_flow_layout = None

        scroll_widget = QWidget()
        scroll_widget.setContentsMargins(24, 24, 24, 24)
        scroll_widget.setProperty("class", "backgroundPrimary")
        main_v_layout = QVBoxLayout(scroll_widget)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(16)
        mw.playlists_scroll.setWidget(scroll_widget)

        if getattr(mw, "is_processing_library", False) and mw.data_manager.is_empty():
            mw.playlist_sort_button.hide()
            mw.playlist_view_button.hide()
            self.ui_manager.set_header_visibility(mw.playlists_header, False)
            self.ui_manager.components._show_loading_library_message(main_v_layout)
            self.reset_playlists_view()
            return

        if mw.data_manager.is_empty():
            mw.playlist_sort_button.hide()
            mw.playlist_view_button.hide()
            self.ui_manager.set_header_visibility(mw.playlists_header, False)
            self.ui_manager.components._show_no_library_message(main_v_layout)
            self.reset_playlists_view()
            return

        all_playlists = mw.library_manager.get_playlists()

        if not all_playlists:
            mw.playlist_sort_button.hide()
            mw.playlist_view_button.hide()
            self.ui_manager.set_header_visibility(mw.playlists_header, False)
            self.ui_manager.components._show_no_playlists_message(main_v_layout)
            self.reset_playlists_view()
            return

        mw.playlist_sort_button.show()
        mw.playlist_view_button.show()
        self.ui_manager.set_header_visibility(mw.playlists_header, True)

        playlists_to_display = all_playlists

        mw.playlists_header["details"].setText(
            translate("{count} playlist(s)", count=len(playlists_to_display))
        )
        mw.playlists_header["details"].show()

        playlists_to_display.sort(
            key=lambda p: mw.data_manager.get_sort_key(
                os.path.splitext(os.path.basename(p))[0]
            ),
            reverse=(mw.playlist_sort_mode == SortMode.ALPHA_DESC),
        )

        mw.current_playlists_display_list = playlists_to_display
        mw.playlists_loaded_count = 0
        mw.is_loading_playlists = False

        if mw.playlists_loaded_count < len(mw.current_playlists_display_list):
            self.load_more_playlists()

        main_v_layout.addStretch(1)
        self.reset_playlists_view()

    def load_more_playlists(self):
        """
        Loads the next batch of playlists into the view.
        """
        mw = self.main_window
        if not hasattr(mw, "playlists_scroll") or not mw.playlists_scroll.widget():
            return
        if getattr(mw, "is_loading_playlists", False):
            return
        if not hasattr(mw, "current_playlists_display_list"):
            return

        playlist_list = mw.current_playlists_display_list
        if mw.playlists_loaded_count >= len(playlist_list):
            return

        mw.is_loading_playlists = True

        start = mw.playlists_loaded_count
        end = min(mw.playlists_loaded_count + BATCH_SIZE, len(playlist_list))

        main_layout = mw.playlists_scroll.widget().layout()

        stretch_item = None
        if main_layout.count() > 0:
            last_item = main_layout.itemAt(main_layout.count() - 1)
            if last_item and last_item.spacerItem():
                stretch_item = main_layout.takeAt(main_layout.count() - 1)

        for i in range(start, end):
            p_path = playlist_list[i]
            meta = mw.library_manager.get_playlist_metadata(
                p_path, mw.data_manager.path_to_track_map
            )

            track_count = meta.get("count", 0)
            total_duration_s = meta.get("duration", 0)
            first_artwork = meta.get("artwork")

            playlist_name = os.path.splitext(os.path.basename(p_path))[0]
            total_duration_str = format_time(total_duration_s * 1000)

            if first_artwork:
                pixmap = self.ui_manager.components.get_pixmap(first_artwork, 128)
            else:
                pixmap = self.ui_manager.components.playlist_pixmap

            subtitle1 = translate("{count} track(s)", count=track_count)
            subtitle2 = None
            if mw.playlist_view_mode != ViewMode.GRID and total_duration_s > 0:
                subtitle2 = total_duration_str

            target_layout = main_layout
            if mw.playlist_view_mode in [
                ViewMode.GRID,
                ViewMode.TILE_BIG,
                ViewMode.TILE_SMALL,
            ]:
                if mw.current_playlist_flow_layout is None:
                    flow_container = QWidget()
                    mw.current_playlist_flow_layout = FlowLayout(
                        flow_container, stretch_items=True
                    )
                    mw.current_playlist_flow_layout.setSpacing(16)
                    main_layout.addWidget(flow_container)
                target_layout = mw.current_playlist_flow_layout

            widget = CardWidget(
                data=p_path,
                view_mode=mw.playlist_view_mode,
                pixmaps=[pixmap],
                title=playlist_name,
                subtitle1=subtitle1,
                subtitle2=subtitle2,
                is_artist_card=False,
                icon_pixmap=self.ui_manager.components.playlist_icon_pixmap,
            )

            widget.activated.connect(self.show_playlist_tracks)
            widget.playClicked.connect(mw.player_controller.smart_play)
            widget.pauseClicked.connect(mw.player.pause)
            widget.contextMenuRequested.connect(
                mw.action_handler.show_playlist_card_context_menu
            )

            if p_path not in mw.main_view_card_widgets:
                mw.main_view_card_widgets[p_path] = []
            mw.main_view_card_widgets[p_path].append(widget)

            target_layout.addWidget(widget)

        if stretch_item:
            main_layout.addItem(stretch_item)

        mw.playlists_loaded_count = end
        mw.is_loading_playlists = False

        QTimer.singleShot(200, self._check_for_more_playlists)

    def _check_for_more_playlists(self):
        """
        Checks if more playlists should be loaded to fill the view.
        """
        mw = self.main_window
        if not hasattr(mw, "playlists_scroll") or not mw.playlists_scroll.widget():
            return

        QApplication.processEvents()

        scroll_bar = mw.playlists_scroll.verticalScrollBar()
        has_more_data = mw.playlists_loaded_count < len(
            mw.current_playlists_display_list
        )

        viewport_height = mw.playlists_scroll.viewport().height()
        content_height = mw.playlists_scroll.widget().size().height()

        if (
                scroll_bar.maximum() == 0 or content_height < viewport_height + 50
        ) and has_more_data:
            self.load_more_playlists()

    def _handle_playlist_context_menu(self, track, global_pos, playlist_path, list_widget):
        """
        Shows the context menu for a specific track inside a playlist.

        Args:
            track: The track data object.
            global_pos (QPoint): The global screen coordinates for the context menu.
            playlist_path (str): The file path of the playlist.
            list_widget (QWidget): The list widget containing the track.
        """
        index = QModelIndex()
        if list_widget:
            local_pos = list_widget.mapFromGlobal(global_pos)
            index = list_widget.indexAt(local_pos)

        context = {
            "playlist_path": playlist_path,
            "widget": list_widget,
            "index": index
        }
        self.main_window.action_handler.show_context_menu(track, global_pos, context=context)

    def show_playlist_tracks(self, playlist_path):
        """
        Displays the detailed tracklist view for a specific playlist.

        Args:
            playlist_path (str): The file path of the playlist to display.
        """
        mw = self.main_window
        mw.current_open_playlist_path = playlist_path

        self.ui_manager.clear_layout(mw.playlist_tracks_header_layout)
        self.ui_manager.clear_layout(mw.playlist_tracks_layout)

        playlist_name = os.path.splitext(os.path.basename(playlist_path))[0]
        fav_button = self.ui_manager.components._create_favorite_button(playlist_path, "playlist")
        tracks = mw.library_manager.load_playlist(
            playlist_path, mw.data_manager.path_to_track_map
        )
        track_count = len(tracks)
        total_duration = sum(t.get("duration", 0) for t in tracks)

        tracks_text = translate("{count} track(s)", count=track_count)
        details_text = f"{tracks_text}"

        header_parts = self.ui_manager.components.create_page_header(
            playlist_name,
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

        mw.playlist_tracks_header_layout.addWidget(header_parts["header"])

        if not tracks:
            text_label = QLabel(translate("Could not load tracks from playlist."))
            text_label.setProperty("class", "textColorPrimary")
            mw.playlist_tracks_layout.addWidget(text_label)
            return

        scroll_area = StyledScrollArea()
        scroll_area.setProperty("class", "backgroundPrimary")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        playlist_widget = self.ui_manager.components._create_detailed_playlist_widget(
            playlist_path, playlist_name, tracks
        )
        playlist_widget.setContentsMargins(24, 24, 24, 24)
        scroll_area.setWidget(playlist_widget)

        mw.playlist_tracks_layout.addWidget(scroll_area, 1)
        mw.playlists_stack.setCurrentIndex(1)

        if hasattr(playlist_widget, "trackContextMenu"):
            try:
                playlist_widget.trackContextMenu.disconnect()
            except TypeError:
                pass

            list_widget = playlist_widget.get_track_list_widget()
            playlist_widget.trackContextMenu.connect(
                lambda track, pos: self._handle_playlist_context_menu(
                    track, pos, playlist_path, list_widget
                )
            )

        mw.update_current_view_state(
            main_tab_index=mw.nav_button_icon_names.index("playlist"),
            context_data={"path": playlist_path},
        )
        self.ui_manager.update_all_track_widgets()

    def reset_playlists_view(self):
        """
        Resets the playlist tab back to its root view.
        """
        mw = self.main_window
        mw.current_open_playlist_path = None
        mw.playlists_stack.setCurrentIndex(0)

