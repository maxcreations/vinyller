"""
Vinyller — Main window UI manager
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
    pyqtSignal, QObject, QSize, Qt, QTimer
)
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QWidget
)

from src.core.state_manager import DropZoneManager
from src.encyclopedia.encyclopedia_helper import EncyclopediaHelper
from src.ui.custom_base_widgets import set_custom_tooltip
from src.ui.custom_cards import CardWidget
from src.ui.custom_classes import (
    InteractiveCoverWidget
)
from src.ui.custom_lists import (
    CustomRoles
)
from src.ui.managers.ui_albums_manager import AlbumsUIManager
from src.ui.managers.ui_artists_manager import ArtistsUIManager
from src.ui.managers.ui_catalog_manager import CatalogUIManager
from src.ui.managers.ui_charts_manager import ChartsUIManager
from src.ui.managers.ui_composers_manager import ComposersUIManager
from src.ui.managers.ui_favorites_manager import FavoritesUIManager
from src.ui.managers.ui_genres_manager import GenresUIManager
from src.ui.managers.ui_history_manager import HistoryUIManager
from src.ui.managers.ui_playlists_manager import PlaylistsUIManager
from src.ui.managers.ui_search_manager import SearchUIManager
from src.ui.managers.ui_songs_manager import SongsUIManager
from src.ui.ui_components import UiComponents
from src.utils import theme
from src.utils.utils import (
    create_svg_icon, format_time, format_month_year
)
from src.utils.utils_translator import translate


class UIManager(QObject):
    """
    Class managing user interface logic and state. Acts as a central hub
    that delegates specific UI tasks to specialized sub-managers.
    """

    alphaJumpRequested = pyqtSignal(str, set, QWidget)

    def __init__(self, main_window):
        """
        Initializes the UIManager, setting up all sub-managers for different
        views and defining the default navigation tab order.
        """
        super().__init__()
        self.main_window = main_window
        self.components = UiComponents(main_window, self)
        self.search_ui_manager = SearchUIManager(main_window, self)
        self.favorites_ui_manager = FavoritesUIManager(main_window, self)
        self.charts_ui_manager = ChartsUIManager(main_window, self)
        self.history_ui_manager = HistoryUIManager(main_window, self)
        self.catalog_ui_manager = CatalogUIManager(main_window, self)
        self.genres_ui_manager = GenresUIManager(main_window, self)
        self.composers_ui_manager = ComposersUIManager(main_window, self)
        self.artists_ui_manager = ArtistsUIManager(main_window, self)
        self.albums_ui_manager = AlbumsUIManager(main_window, self)
        self.encyclopedia_helper = EncyclopediaHelper(main_window, self)
        self.songs_ui_manager = SongsUIManager(main_window, self)
        self.playlists_ui_manager = PlaylistsUIManager(main_window, self)


    def setup_ui(self):
        """Initializes UI creation using UiComponents and DropZoneManager."""
        self.drop_zone_manager = DropZoneManager(self.main_window)
        self.components.setup_ui()

    def populate_all_tabs(self, restoring_state = False):
        """
        Populates all main tabs with data from the library.
        Optionally preserves scroll positions if restoring state.
        """
        mw = self.main_window
        if not restoring_state:
            mw.scroll_positions.clear()
        self.populate_artists_tab()
        self.populate_albums_tab()
        self.populate_songs_tab()
        self.populate_genres_tab()
        self.populate_composers_tab()
        self.populate_catalog_tab()
        self.populate_playlists_tab()
        self.populate_history_tab()
        self.favorites_ui_manager.populate_favorites_tab()
        self.charts_ui_manager.populate_charts_tab()

    def inject_encyclopedia_section(self, layout, item_key, item_type, refresh_callback = None):
        """
        Delegates the injection of an encyclopedia section to the EncyclopediaHelper.

        Args:
            layout (QLayout): The target layout where the section will be injected.
            item_key (str/tuple): The unique identifier for the item.
            item_type (str): The type of the item (e.g., 'artist', 'genre').
            refresh_callback (callable, optional): Callback to refresh the section.
        """
        self.encyclopedia_helper.inject_encyclopedia_section(layout, item_key, item_type, refresh_callback)

    def _create_encyclopedia_widget(self, enc_data, item_name, item_type, item_key, refresh_callback):
        """Delegates the creation of an encyclopedia widget to the EncyclopediaHelper."""
        return self.encyclopedia_helper._create_encyclopedia_widget(enc_data, item_name, item_type, item_key,
                                                                    refresh_callback)

    def open_encyclopedia_editor(self, item_key, item_type, on_success = None, initial_meta = None, parent = None):
        """Opens the encyclopedia editor dialog for the specified item."""
        self.encyclopedia_helper.open_encyclopedia_editor(item_key, item_type, on_success, initial_meta, parent)

    def open_encyclopedia_full_view(self, item_key, item_type):
        """Opens the full immersive encyclopedia view for a specific item."""
        self.encyclopedia_helper.open_encyclopedia_full_view(item_key, item_type)

    def handle_relation_click(self, item_key, item_type, extra_data = None):
        """Handles navigation when a related encyclopedia link is clicked."""
        self.encyclopedia_helper.handle_relation_click(item_key, item_type, extra_data)

    def handle_encyclopedia_import(self, parent_widget):
        """Initiates the process of importing an encyclopedia backup."""
        self.encyclopedia_helper.handle_encyclopedia_import(parent_widget)

    def _confirm_and_restore_backup(self, index, parent_widget):
        """Prompts for confirmation before restoring a specific encyclopedia backup."""
        self.encyclopedia_helper._confirm_and_restore_backup(index, parent_widget)

    def _handle_zip_import(self, parent_widget):
        """Handles importing encyclopedia data from an external ZIP archive."""
        self.encyclopedia_helper._handle_zip_import(parent_widget)

    def handle_encyclopedia_export(self, parent_widget):
        """Initiates the process of exporting the current encyclopedia to a ZIP archive."""
        self.encyclopedia_helper.handle_encyclopedia_export(parent_widget)

    def set_header_visibility(self, header_dict, visible):
        """
        Universally hides or shows interactive header elements
        (Play, Actions, Details, Divider), without affecting the Title.
        """
        if not header_dict:
            return

        if lbl := header_dict.get("details"):
            should_show = visible and bool(lbl.text().strip())
            lbl.setVisible(should_show)

        if btn := header_dict.get("play_button"):
            btn.setVisible(visible)

        if btn := header_dict.get("shake_button"):
            btn.setVisible(visible)

        if btn := header_dict.get("actions_button"):
            btn.setVisible(visible)

        if div := header_dict.get("divider"):
            div.setVisible(visible)

    def check_scroll_and_load(self, value, scroll_bar, load_more_func):
        """
        Checks if the scrollbar is near the bottom and triggers loading more items if so.
        Safeguarded against layout jumps and visual repainting artifacts ("flickering").

        Args:
            value (int): The current value of the scrollbar.
            scroll_bar (QScrollBar): The scrollbar instance being checked.
            load_more_func (callable): The function to call to load more items.
        """
        if scroll_bar.maximum() == 0:
            return

        if value >= scroll_bar.maximum() - 200:
            scroll_area = scroll_bar.parentWidget()
            while scroll_area and not hasattr(scroll_area, "widget"):
                scroll_area = scroll_area.parentWidget()

            if scroll_area:
                scroll_area.setUpdatesEnabled(False)

            scroll_bar.blockSignals(True)
            current_value = scroll_bar.value()

            load_more_func()

            if scroll_area and scroll_area.widget() and scroll_area.widget().layout():
                scroll_area.widget().layout().activate()

            scroll_bar.setValue(current_value)

            scroll_bar.blockSignals(False)

            if scroll_area:
                scroll_area.setUpdatesEnabled(True)

    def _format_date_added_group(self, timestamp):
        """Helper to format date groups consistent with other tabs."""
        return format_month_year(timestamp)

    def _extract_default_image_path(self, item_name, item_type, album_key=None):
        """
        Extracts cover art path.
        1. Priority (Manual Selection): Looks in mw.artist_artworks / mw.genre_artworks.
        2. Metadata: Searches for highest quality in track data.

        Args:
            item_name (str): The name of the item.
            item_type (str): The type of the item ('artist', 'genre', 'composer', 'album').
            album_key (tuple, optional): The specific album key if the item is an album.

        Returns:
            str or None: The file path to the extracted image, or None if not found.
        """
        mw = self.main_window
        dm = mw.data_manager

        manual_path = None

        if item_type == "artist":
            if hasattr(mw, "artist_artworks"):
                manual_path = mw.artist_artworks.get(item_name)
        elif item_type == "genre":
            if hasattr(mw, "genre_artworks"):
                manual_path = mw.genre_artworks.get(item_name)
        elif item_type == "composer":
            if hasattr(mw, "composer_artworks"):
                manual_path = mw.composer_artworks.get(item_name)

        if manual_path and os.path.exists(manual_path):
            return manual_path

        artworks_dict_list = []

        if item_type == "artist" and item_name in dm.artists_data:
            artworks_dict_list = dm.artists_data[item_name].get("artworks", [])
        elif item_type == "genre" and item_name in dm.genres_data:
            artworks_dict_list = dm.genres_data[item_name].get("artworks", [])
        elif item_type == "composer" and item_name in dm.composers_data:
            artworks_dict_list = dm.composers_data[item_name].get("artworks", [])

        elif item_type == "album" and album_key:
            if album_key in dm.albums_data:
                art = dm.albums_data[album_key].get("artwork")
                if art:
                    artworks_dict_list = [art]

            elif isinstance(album_key, (list, tuple)):
                search_key = tuple(album_key)
                search_len = len(search_key)

                for real_key, data in dm.albums_data.items():
                    if isinstance(real_key, tuple) and len(real_key) >= search_len:
                        if real_key[:search_len] == search_key:
                            art = data.get("artwork")
                            if art:
                                artworks_dict_list = [art]
                                break

        for art_dict in artworks_dict_list:
            if not art_dict:
                continue
            try:
                numeric_keys = [int(k) for k in art_dict.keys() if k.isdigit()]
                if numeric_keys:
                    largest_size = sorted(numeric_keys)[-1]
                    best_path = art_dict.get(str(largest_size))

                    if best_path and os.path.exists(best_path):
                        return best_path
            except Exception:
                pass

            for path in art_dict.values():
                if path and os.path.exists(path):
                    return path

        return None

    def populate_artists_tab(self, initial_load_count = None):
        """Populates the main artists view."""
        self.artists_ui_manager.populate_artists_tab(initial_load_count)

    def load_more_artists(self):
        """Loads the next batch of artists in the grid/list."""
        self.artists_ui_manager.load_more_artists()

    def _check_for_more_artists(self):
        """Checks if more artists should be loaded to fill the view."""
        self.artists_ui_manager._check_for_more_artists()

    def show_artist_albums(self, artist_name):
        """Displays the detailed view of albums for a specific artist."""
        self.artists_ui_manager.show_artist_albums(artist_name)

    def _populate_artist_albums_standard_view(self, scroll_area, albums_of_artist):
        """Populates the standard album list view for an artist."""
        self.artists_ui_manager._populate_artist_albums_standard_view(scroll_area, albums_of_artist)

    def load_more_artist_albums(self):
        """Loads the next batch of albums for the currently displayed artist."""
        self.artists_ui_manager.load_more_artist_albums()

    def _check_for_more_artist_albums(self):
        """Checks if more albums should be loaded for the currently displayed artist."""
        self.artists_ui_manager._check_for_more_artist_albums()

    def _populate_artist_all_tracks_view(self, scroll_area, albums_of_artist):
        """Populates a flat list view of all tracks by a specific artist."""
        self.artists_ui_manager._populate_artist_all_tracks_view(scroll_area, albums_of_artist)

    def load_more_artist_all_tracks(self):
        """Loads the next batch of tracks in the all-tracks artist view."""
        self.artists_ui_manager.load_more_artist_all_tracks()

    def _check_for_more_artist_all_tracks(self):
        """Checks if more tracks should be loaded in the all-tracks artist view."""
        self.artists_ui_manager._check_for_more_artist_all_tracks()

    def sort_and_reshow_artist_albums(self, mode_id):
        """Re-sorts and refreshes the currently displayed artist's albums."""
        self.artists_ui_manager.sort_and_reshow_artist_albums(mode_id)

    def navigate_to_artist(self, artist_name):
        """Jumps directly to the specified artist's detailed view."""
        self.artists_ui_manager.navigate_to_artist(artist_name)

    def populate_composers_tab(self, initial_load_count = None):
        """Populates the main composers view."""
        self.composers_ui_manager.populate_composers_tab(initial_load_count)

    def load_more_composers(self):
        """Loads the next batch of composers in the grid/list."""
        self.composers_ui_manager.load_more_composers()

    def _check_for_more_composers(self):
        """Checks if more composers should be loaded to fill the view."""
        self.composers_ui_manager._check_for_more_composers()

    def show_composer_albums(self, composer_name):
        """Displays the detailed view of albums containing tracks by a specific composer."""
        self.composers_ui_manager.show_composer_albums(composer_name)

    def _populate_composer_albums_standard_view(self, scroll_area, albums_of_composer):
        """Populates the standard album list view for a composer."""
        self.composers_ui_manager._populate_composer_albums_standard_view(scroll_area, albums_of_composer)

    def load_more_composer_albums(self):
        """Loads the next batch of albums for the currently displayed composer."""
        self.composers_ui_manager.load_more_composer_albums()

    def _check_for_more_composer_albums(self):
        """Checks if more albums should be loaded for the currently displayed composer."""
        self.composers_ui_manager._check_for_more_composer_albums()

    def navigate_to_composer(self, composer_name):
        """Jumps directly to the specified composer's detailed view."""
        self.composers_ui_manager.navigate_to_composer(composer_name)

    def populate_albums_tab(self, initial_load_count = None):
        """Populates the main albums view."""
        self.albums_ui_manager.populate_albums_tab(initial_load_count)

    def load_more_albums(self):
        """Loads the next batch of albums in the grid/list."""
        self.albums_ui_manager.load_more_albums()

    def _check_for_more_albums(self):
        """Checks if more albums should be loaded to fill the view."""
        self.albums_ui_manager._check_for_more_albums()

    def navigate_to_year(self, year_str):
        """Jumps to the search/filter view showing albums released in the specified year."""
        self.albums_ui_manager.navigate_to_year(year_str)

    def show_album_tracks(self, album_key, source_stack):
        """Displays the detailed tracklist view for a specific album within a given stack."""
        self.albums_ui_manager.show_album_tracks(album_key, source_stack)

    def navigate_to_album_tab_and_show(self, album_key):
        """Switches to the Albums tab and shows the detailed view for the specified album."""
        self.albums_ui_manager.navigate_to_album_tab_and_show(album_key)

    def navigate_to_album(self, album_key):
        """Jumps to the specified album's view within the current context."""
        self.albums_ui_manager.navigate_to_album(album_key)

    def populate_songs_tab(self, initial_load_count=None):
        """Populates the main songs (all tracks) view."""
        self.songs_ui_manager.populate_songs_tab(initial_load_count)

    def load_more_songs(self):
        """Loads the next batch of songs into the view."""
        self.songs_ui_manager.load_more_songs()

    def _check_for_more_songs(self):
        """Checks if more songs should be loaded to fill the view."""
        self.songs_ui_manager._check_for_more_songs()

    def populate_genres_tab(self, initial_load_count=None):
        """Populates the main genres view."""
        self.genres_ui_manager.populate_genres_tab(initial_load_count)

    def load_more_genres(self):
        """Loads the next batch of genres in the grid/list."""
        self.genres_ui_manager.load_more_genres()

    def _check_for_more_genres(self):
        """Checks if more genres should be loaded to fill the view."""
        self.genres_ui_manager._check_for_more_genres()

    def show_genre_albums(self, genre_name):
        """Displays the detailed view of albums belonging to a specific genre."""
        self.genres_ui_manager.show_genre_albums(genre_name)

    def load_more_genre_albums(self):
        """Loads the next batch of albums for the currently displayed genre."""
        self.genres_ui_manager.load_more_genre_albums()

    def load_more_genre_all_tracks(self):
        """Loads the next batch of tracks in the all-tracks genre view."""
        self.genres_ui_manager.load_more_genre_all_tracks()

    def sort_and_reshow_genre_albums(self, mode_id):
        """Re-sorts and refreshes the currently displayed genre's albums."""
        self.genres_ui_manager.sort_and_reshow_genre_albums(mode_id)

    def update_all_track_widgets(self):
        """
        Updates visual state of all widgets (tracks, covers, cards),
        synchronizing them with current playback state.
        """
        mw = self.main_window
        queue = mw.player.get_current_queue()
        current_index = mw.player.get_current_index()
        is_playing = (
            mw.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState
        )
        current_track = (
            queue[current_index] if 0 <= current_index < len(queue) else None
        )
        current_context = mw.current_queue_context_data

        def check_is_current(key, context):
            if key == context:
                return True
            if isinstance(context, dict) and "data" in context:
                if key == context["data"]:
                    return True
            return False

        valid_track_lists = []
        for track_list in mw.main_view_track_lists:
            try:
                if current_track:
                    target_path = current_track.get("path")
                    target_title = current_track.get("title")

                    for i in range(track_list.count()):
                        item = track_list.item(i)
                        item_data = item.data(Qt.ItemDataRole.UserRole)

                        if item_data and item_data.get("path") == target_path:
                            if item.text() != target_title:
                                item.setText(target_title)
                                item_data["title"] = target_title
                                item.setData(Qt.ItemDataRole.UserRole, item_data)

                track_list.updatePlaybackState(
                    current_track_path = current_track["path"] if current_track else None,
                    current_track_index = current_index,
                    is_playing = is_playing,
                    current_context = current_context,
                )
                valid_track_lists.append(track_list)
            except RuntimeError:
                pass
        mw.main_view_track_lists = valid_track_lists

        current_album_key = None
        if current_track:
            track_year = current_track.get("year", 0)
            if mw.treat_folders_as_unique:
                current_album_key = (
                    current_track.get("album_artist"),
                    current_track.get("album"),
                    track_year,
                    os.path.dirname(current_track["path"]),
                )
            else:
                current_album_key = (
                    current_track.get("album_artist"),
                    current_track.get("album"),
                    track_year,
                )

        for item_key, widget_list in list(mw.main_view_cover_widgets.items()):
            is_active_source = check_is_current(item_key, current_context)

            valid_widgets = []
            for w in widget_list:
                try:
                    if isinstance(w, InteractiveCoverWidget):
                        w.update_playback_state(is_active_source, is_playing)
                    valid_widgets.append(w)
                except RuntimeError:
                    pass
            if valid_widgets:
                mw.main_view_cover_widgets[item_key] = valid_widgets
            else:
                if item_key in mw.main_view_cover_widgets:
                    del mw.main_view_cover_widgets[item_key]

        for data_key, button in list(mw.main_view_header_play_buttons.items()):
            try:
                button.setIcon(
                    create_svg_icon(
                        "assets/control/play_outline.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    )
                )
                set_custom_tooltip(
                    button,
                    title = translate("Play"),
                )
            except RuntimeError:
                if data_key in mw.main_view_header_play_buttons:
                    del mw.main_view_header_play_buttons[data_key]

        for data_key, widget_list in list(mw.main_view_card_widgets.items()):
            is_active_source = check_is_current(data_key, current_context)

            valid_widgets = []
            for w in widget_list:
                try:
                    if isinstance(w, CardWidget):
                        w.update_playback_state(is_active_source, is_playing)
                    valid_widgets.append(w)
                except RuntimeError:
                    pass
            if valid_widgets:
                mw.main_view_card_widgets[data_key] = valid_widgets
            else:
                if data_key in mw.main_view_card_widgets:
                    del mw.main_view_card_widgets[data_key]

        queue_widget = mw.right_panel.queue_widget
        for i in range(queue_widget.count()):
            item = queue_widget.item(i)
            if item:
                is_current = i == current_index
                item.setData(CustomRoles.IsCurrentRole, is_current)
                item.setData(CustomRoles.IsPlayingRole, is_current and is_playing)

        if 0 <= current_index < queue_widget.count():
            queue_widget.scrollToItem(
                queue_widget.item(current_index),
                QAbstractItemView.ScrollHint.EnsureVisible,
            )
        queue_widget.viewport().update()

        if hasattr(mw.right_panel, "vinyl_queue_widget"):
            vinyl_queue_widget = mw.right_panel.vinyl_queue_widget
            for i in range(vinyl_queue_widget.count()):
                item = vinyl_queue_widget.item(i)
                if item:
                    is_current = i == current_index
                    item.setData(CustomRoles.IsCurrentRole, is_current)
                    item.setData(CustomRoles.IsPlayingRole, is_current and is_playing)
            vinyl_queue_widget.viewport().update()

    def populate_catalog_tab(self, initial_load_count = None):
        """Populates the main catalog (folder tree) view."""
        self.catalog_ui_manager.populate_catalog_tab(initial_load_count)

    def load_more_catalog(self):
        """Loads the next batch of directories in the catalog root view."""
        self.catalog_ui_manager.load_more_catalog()

    def _check_for_more_catalog(self):
        """Checks if more items should be loaded in the catalog root view."""
        self.catalog_ui_manager._check_for_more_catalog()

    def get_artworks_for_directory(self, path):
        """Retrieves aggregated artworks from files inside a specific directory."""
        return self.catalog_ui_manager.get_artworks_for_directory(path)

    def on_catalog_item_activated(self, data):
        """Handles user interaction with an item (folder or track) in the catalog."""
        self.catalog_ui_manager.on_catalog_item_activated(data)

    def navigate_to_directory(self, path, scroll_pos = 0):
        """Navigates the catalog view to the specified directory path."""
        self.catalog_ui_manager.navigate_to_directory(path, scroll_pos)

    def load_more_directory_items(self):
        """Loads the next batch of files/folders in the current catalog directory."""
        self.catalog_ui_manager.load_more_directory_items()

    def _check_for_more_directory_items(self):
        """Checks if more items should be loaded in the current catalog directory."""
        self.catalog_ui_manager._check_for_more_directory_items()

    def populate_playlists_tab(self):
        """Populates the main playlists view with available custom playlists."""
        self.playlists_ui_manager.populate_playlists_tab()

    def load_more_playlists(self):
        """Loads the next batch of playlists into the view."""
        self.playlists_ui_manager.load_more_playlists()

    def _check_for_more_playlists(self):
        """Checks if more playlists should be loaded to fill the view."""
        self.playlists_ui_manager._check_for_more_playlists()

    def _handle_playlist_context_menu(self, track, global_pos, playlist_path, list_widget):
        """Shows the context menu for a specific track inside a playlist."""
        self.playlists_ui_manager._handle_playlist_context_menu(track, global_pos, playlist_path, list_widget)

    def show_playlist_tracks(self, playlist_path):
        """Displays the detailed tracklist view for a specific playlist."""
        self.playlists_ui_manager.show_playlist_tracks(playlist_path)

    def reset_playlists_view(self):
        """Resets the playlist tab back to its root view."""
        self.playlists_ui_manager.reset_playlists_view()

    def populate_history_tab(self, initial_load_count = None):
        """Populates the main playback history view."""
        self.history_ui_manager.populate_history_tab(initial_load_count)

    def load_more_history(self):
        """Loads the next batch of tracks in the playback history view."""
        self.history_ui_manager.load_more_history()

    def _check_for_more_history(self):
        """Checks if more history items should be loaded to fill the view."""
        self.history_ui_manager._check_for_more_history()

    def show_history_card_context_menu(self, data, global_pos):
        """Displays a context menu for an item in the playback history."""
        self.history_ui_manager.show_history_card_context_menu(data, global_pos)

    def clear_layout(self, layout):
        """Recursively clears and deletes all widgets contained within a layout."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def update_nav_button_icons(self):
        """
        Updates the SVG icons and colors for the navigation bar buttons
        based on their current active state and the application theme.
        """
        mw = self.main_window

        accent_color = theme.get_qcolor(theme.COLORS["ACCENT"])
        r, g, b = accent_color.red(), accent_color.green(), accent_color.blue()
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        is_dark_theme = theme.COLORS.get("IS_DARK", False)

        if brightness > 160 and is_dark_theme:
            fav_icon_active = theme.COLORS["SECONDARY"]
            nav_icon_active = theme.COLORS["SECONDARY"]
        elif brightness > 220:
            fav_icon_active = theme.COLORS["PRIMARY"]
            nav_icon_active = theme.COLORS["PRIMARY"]
        elif brightness > 160:
            fav_icon_active = theme.COLORS["PRIMARY"]
            nav_icon_active = theme.COLORS["PRIMARY"]
        elif brightness < 160 and is_dark_theme:
            fav_icon_active = theme.COLORS["WHITE"]
            nav_icon_active = theme.COLORS["WHITE"]
        else:
            fav_icon_active = theme.COLORS["WHITE"]
            nav_icon_active = theme.COLORS["ACCENT"]

        for i, button in enumerate(mw.nav_buttons):
            icon_name = mw.nav_button_icon_names[i]

            if icon_name == "favorite":
                svg_path = f"assets/control/vinyller.svg"
            elif icon_name == "history":
                svg_path = f"assets/control/history.svg"
            elif icon_name == "charts":
                svg_path = f"assets/control/charts.svg"
            elif icon_name == "composer":
                svg_path = f"assets/control/composer.svg"
            else:
                svg_path = f"assets/control/{icon_name}.svg"

            is_checked = button.isChecked()

            color = nav_icon_active if is_checked else theme.COLORS["PRIMARY"]

            if icon_name == "favorite":
                color = fav_icon_active if is_checked else theme.COLORS["PRIMARY"]

            button.setIcon(create_svg_icon(svg_path, color, QSize(24, 24)))

        if hasattr(mw, "nav_more_button") and mw.nav_more_button:
            hidden_buttons = getattr(mw.nav_more_button, "hidden_buttons", [])

            is_more_active = any(btn.isChecked() for btn in hidden_buttons)

            mw.nav_more_button.setChecked(is_more_active)

            more_color = (
                nav_icon_active if is_more_active else theme.COLORS["PRIMARY"]
            )
            mw.nav_more_button.setIcon(
                create_svg_icon(
                    "assets/control/more_horiz.svg", more_color, QSize(24, 24)
                )
            )

    def on_nav_button_clicked(self, button):
        """
        Handles the event when a navigation button is clicked, switching
        the main stack to the corresponding tab or resetting its scroll/state.
        """
        mw = self.main_window
        try:
            new_index = mw.nav_buttons.index(button)
        except ValueError:
            return

        if mw.global_search_bar.text():
            mw.global_search_bar.blockSignals(True)
            mw.global_search_bar.clear()
            mw.global_search_bar.blockSignals(False)

        if new_index == mw.main_stack.currentIndex():
            icon_name = mw.nav_button_icon_names[new_index]

            if hasattr(mw, 'tab_history') and icon_name in mw.tab_history:
                mw.tab_history[icon_name].clear()

            if icon_name == "artist":
                if mw.artists_stack.currentIndex() != 0:
                    mw.artists_stack.setCurrentIndex(0)
                    mw.update_current_view_state(main_tab_index=new_index)
                else:
                    mw.artists_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "album":
                if mw.albums_stack.currentIndex() != 0:
                    mw.albums_stack.setCurrentIndex(0)
                    mw.update_current_view_state(main_tab_index=new_index)
                else:
                    mw.albums_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "genre":
                if mw.genres_stack.currentIndex() != 0:
                    mw.genres_stack.setCurrentIndex(0)
                    mw.update_current_view_state(main_tab_index=new_index)
                else:
                    mw.genres_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "composer":
                if mw.composers_stack.currentIndex() != 0:
                    mw.composers_stack.setCurrentIndex(0)
                    mw.update_current_view_state(main_tab_index=new_index)
                else:
                    mw.composers_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "folder":
                if mw.current_catalog_path != "":
                    self.populate_catalog_tab()
                    mw.update_current_view_state(main_tab_index=new_index)
                else:
                    mw.catalog_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "playlist":
                if mw.playlists_stack.currentIndex() != 0:
                    mw.playlists_stack.setCurrentIndex(0)
                    mw.update_current_view_state(main_tab_index=new_index)
                else:
                    mw.playlists_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "favorite":
                if mw.favorites_stack.currentIndex() != 0:
                    mw.favorites_stack.setCurrentIndex(0)
                    mw.current_favorites_context = None
                    mw.update_current_view_state(main_tab_index=new_index)
                else:
                    mw.favorites_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "charts":
                if mw.charts_stack.currentIndex() != 0:
                    mw.charts_stack.setCurrentIndex(0)
                    mw.current_charts_context = None
                    mw.update_current_view_state(main_tab_index=new_index)
                else:
                    mw.charts_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "history":
                mw.history_scroll.verticalScrollBar().setValue(0)

            elif icon_name == "track":
                mw.songs_scroll.verticalScrollBar().setValue(0)

        else:
            mw.main_stack.setCurrentIndex(new_index)

        self.update_nav_button_icons()

    def on_main_stack_changed(self, index):
        """
        Triggered when the main view stack changes. Checks if the newly visible
        tab is empty, and lazily populates it if needed.

        Args:
            index (int): The index of the newly selected tab in the stack.
        """
        mw = self.main_window
        has_library_paths = (
            hasattr(mw, "music_library_paths") and mw.music_library_paths
        )

        if index >= len(mw.nav_button_icon_names):
            return

        icon_name = self.main_window.nav_button_icon_names[index]

        is_artists_populated = (
            has_library_paths
            and mw.artists_scroll.widget()
            and mw.artists_scroll.widget().layout().count() > 0
            and mw.data_manager.artists_data
        )
        is_albums_populated = (
            has_library_paths
            and mw.albums_scroll.widget()
            and mw.albums_scroll.widget().layout().count() > 0
            and mw.data_manager.albums_data
        )
        is_genres_populated = (
            has_library_paths
            and mw.genres_scroll.widget()
            and mw.genres_scroll.widget().layout().count() > 0
            and mw.data_manager.genres_data
        )
        is_composers_populated = (
            has_library_paths
            and mw.composers_scroll.widget()
            and mw.composers_scroll.widget().layout().count() > 0
            and mw.data_manager.composers_data
        )
        is_catalog_populated = has_library_paths and mw.catalog_stack.count() > 0
        is_playlists_populated = (
            mw.playlists_scroll.widget()
            and mw.playlists_scroll.widget().layout().count() > 0
        )
        is_favorites_populated = (
            mw.favorites_scroll.widget()
            and mw.favorites_scroll.widget().layout().count() > 0
        )
        is_charts_populated = (
            mw.charts_scroll.widget()
            and mw.charts_scroll.widget().layout()
            and mw.charts_scroll.widget().layout().count() > 0
        )

        if (
            icon_name == "artist"
            and mw.artists_stack.currentIndex() == 0
            and not is_artists_populated
        ):
            self.populate_artists_tab()
        elif (
            icon_name == "album"
            and mw.albums_stack.currentIndex() == 0
            and not is_albums_populated
        ):
            self.populate_albums_tab()
        elif icon_name == "genre" and not is_genres_populated:
            self.populate_genres_tab()
        elif icon_name == "composer" and not is_composers_populated:
            self.populate_composers_tab()
        elif (
            icon_name == "folder"
            and mw.catalog_stack.currentIndex() == 0
            and not is_catalog_populated
        ):
            self.populate_catalog_tab()
        elif (
            icon_name == "playlist"
            and mw.playlists_stack.currentIndex() == 0
            and not is_playlists_populated
        ):
            self.populate_playlists_tab()
        elif (
            icon_name == "favorite"
            and mw.favorites_stack.currentIndex() == 0
            and not is_favorites_populated
        ):
            self.favorites_ui_manager.populate_favorites_tab()
        elif icon_name == "charts":
            if mw.charts_stack.currentIndex() == 0 and (
                mw.charts_data_is_stale or not is_charts_populated
            ):
                self.charts_ui_manager.populate_charts_tab()
                mw.charts_data_is_stale = False
        elif icon_name == "history":
            if not mw.is_restoring_state:
                self.populate_history_tab()

        if not mw.is_restoring_state:
            context_data = None
            if icon_name in ["track", "history"]:
                context_data = {"context": "main"}
            elif icon_name in [
                "artist",
                "album",
                "genre",
                "folder",
                "playlist",
                "favorite",
                "charts",
                "composer",
            ]:
                current_sub_stack = mw.main_stack.widget(index).findChild(
                    QFrame
                )
                context_data = {}

            if context_data is not None:
                mw.update_current_view_state(
                    main_tab_index=index, context_data=context_data
                )

    def _on_separator_clicked(self, source_view, letters, anchor_widget):
        """Emits a signal requesting the AlphaJumpPopup to appear."""
        self.alphaJumpRequested.emit(source_view, letters, anchor_widget)

    def navigate_to_genre(self, genre_name):
        """Jumps directly to the specified genre's detailed view."""
        self.genres_ui_manager.navigate_to_genre(genre_name)

    def update_queue_header(self):
        """Updates the header details (title, track count, duration) in the active playback queue."""
        mw = self.main_window
        queue = mw.player.get_current_queue()
        track_count = len(queue)
        total_duration = sum(t.get("duration", 0) for t in queue)
        details = translate(
            "{count} track(s) - {duration}",
            count=track_count,
            duration=format_time(total_duration * 1000),
        )

        name = mw.current_queue_name
        context_text = ""
        pixmap_key = "default"
        current_path = mw.current_queue_context_path
        context_data = mw.current_queue_context_data

        if isinstance(context_data, dict) and "type" in context_data:
            c_type = context_data["type"]
            if c_type == "composer":
                context_text = translate("Composer")
                pixmap_key = "composer"
            elif c_type == "genre":
                context_text = translate("Genre")
                pixmap_key = "genre"
            elif c_type == "artist":
                context_text = translate("Artist")
                pixmap_key = "artist"

        elif isinstance(context_data, str):
            if context_data in mw.data_manager.artists_data:
                context_text = translate("Artist")
                pixmap_key = "artist"
            elif context_data in mw.data_manager.genres_data:
                context_text = translate("Genre")
                pixmap_key = "genre"
            elif os.path.isdir(context_data):
                context_text = translate("Folder")
                pixmap_key = "folder"
            elif os.path.isfile(context_data) and context_data.lower().endswith(
                (".m3u", ".m3u8")
            ):
                context_text = translate("Playlist")
                pixmap_key = "playlist"
            elif context_data == "favorite_tracks":
                context_text = translate("Favorites")
                pixmap_key = "favorite"
            elif context_data == "all_tracks":
                context_text = translate("Library")
                pixmap_key = "default"
            elif context_data == "all_favorite_artists":
                context_text = translate("Favorites")
                pixmap_key = "fav_artist"
            elif context_data == "all_favorite_albums":
                context_text = translate("Favorites")
                pixmap_key = "fav_album"
            elif context_data == "all_favorite_genres":
                context_text = translate("Favorites")
                pixmap_key = "fav_genre"
            elif context_data == "all_favorite_folders":
                context_text = translate("Favorites")
                pixmap_key = "fav_folder"
            elif context_data == "all_favorite_playlists":
                context_text = translate("Favorites")
                pixmap_key = "fav_playlist"
            elif context_data == "playback_history":
                context_text = translate("Playlist")
                pixmap_key = "history"
            elif context_data == "all_top_tracks":
                context_text = translate("Charts")
                pixmap_key = "top_track"
            elif context_data == "all_top_artists":
                context_text = translate("Charts")
                pixmap_key = "top_artist"
            elif context_data == "all_top_albums":
                context_text = translate("Charts")
                pixmap_key = "top_album"
            elif context_data == "all_top_genres":
                context_text = translate("Charts")
                pixmap_key = "top_genre"
            elif context_data == "all_top_composers":
                context_text = translate("Charts")
                pixmap_key = "top_artist"

        elif isinstance(context_data, tuple):
            context_text = translate("Album")
            pixmap_key = "album"

        mw.right_panel.update_queue_header(
            name=name,
            context_text=context_text,
            details=details,
            pixmap_key=pixmap_key,
            current_path=current_path,
        )

    def apply_queue_view_options(self):
        """Applies configured settings (compact mode, cover visibility) to the queue widgets."""
        mw = self.main_window

        mw.right_panel.queue_widget.set_drag_export_enabled(mw.allow_drag_export)

        if hasattr(mw.right_panel, "vinyl_queue_widget"):
            mw.right_panel.vinyl_queue_widget.set_drag_export_enabled(mw.allow_drag_export)

        mw.right_panel.apply_view_options(
            is_compact = mw.queue_compact_mode,
            hide_artist = mw.queue_compact_hide_artist,
            show_cover = mw.queue_show_cover,
        )

    def _capture_current_scroll(self):
        """
        Captures current scroll position based on the logical state being saved.
        """
        mw = self.main_window
        scroll_attr_name = None
        scroll_val = 0

        try:
            if getattr(mw, "rescan_initiated_from_dialog", False):
                return None, 0

            state = mw.current_view_state
            if not state:
                return None, 0

            tab_name = state.get("main_tab_name")
            ctx = state.get("context_data", {})

            if tab_name == "artist" and not ctx:
                scroll_attr_name = "artists_scroll"
            elif tab_name == "album" and not ctx:
                scroll_attr_name = "albums_scroll"
            elif tab_name == "genre" and not ctx:
                scroll_attr_name = "genres_scroll"
            elif tab_name == "composer" and not ctx:
                scroll_attr_name = "composers_scroll"
            elif tab_name == "track":
                scroll_attr_name = "songs_scroll"
            elif tab_name == "playlist" and not ctx:
                scroll_attr_name = "playlists_scroll"
            elif tab_name == "folder" and not ctx:
                scroll_attr_name = "catalog_scroll"
            elif tab_name == "favorite" and not ctx:
                scroll_attr_name = "favorites_scroll"
            elif tab_name == "charts" and not ctx:
                scroll_attr_name = "charts_scroll"
            elif tab_name == "history":
                scroll_attr_name = "history_scroll"
            elif tab_name == "search" and not ctx:
                scroll_attr_name = "search_scroll"

            if scroll_attr_name:
                widget = getattr(mw, scroll_attr_name, None)
                if widget and hasattr(widget, "verticalScrollBar"):
                    scroll_val = widget.verticalScrollBar().value()

        except Exception as e:
            print(f"Error capturing scroll: {e}")

        return scroll_attr_name, scroll_val

    def _schedule_scroll_restore(self, attr_name, target_value):
        """
        Deterministically restores scroll position by listening to layout changes.
        Triggers lazy loading automatically until the target position is reachable.
        """
        if not attr_name or target_value <= 0:
            return

        mw = self.main_window
        widget = getattr(mw, attr_name, None)
        if not widget:
            return

        scrollbar = widget.verticalScrollBar()

        load_funcs = {
            "artists_scroll": self.load_more_artists,
            "artist_albums_scroll": getattr(self, "load_more_artist_albums", None),
            "albums_scroll": self.load_more_albums,
            "songs_scroll": self.load_more_songs,
            "genres_scroll": self.load_more_genres,
            "genre_albums_scroll": getattr(self, "load_more_genre_albums", None),
            "composers_scroll": self.load_more_composers,
            "composer_albums_scroll": getattr(self, "load_more_composer_albums", None),
            "catalog_scroll": self.load_more_catalog,
            "playlists_scroll": self.load_more_playlists,
            "history_scroll": self.load_more_history,
            "search_scroll": getattr(self.search_ui_manager, "load_more_search_results", None) if hasattr(self, "search_ui_manager") else None
        }

        load_func = load_funcs.get(attr_name)

        state = {'last_max': -1, 'finished': False}

        timeout_timer = QTimer()
        timeout_timer.setSingleShot(True)
        timeout_timer.setInterval(2000)

        def cleanup():
            state['finished'] = True
            timeout_timer.stop()
            try:
                scrollbar.rangeChanged.disconnect(on_range_changed)
            except TypeError:
                pass

        def on_range_changed(min_val=0, max_val=0):
            if state['finished']:
                return

            current_max = scrollbar.maximum()

            if current_max >= target_value:
                scrollbar.setValue(target_value)
                cleanup()
            elif current_max > state['last_max']:
                state['last_max'] = current_max
                if load_func and callable(load_func):
                    load_func()
            else:
                scrollbar.setValue(current_max)
                cleanup()

        def on_timeout():
            if not state['finished']:
                scrollbar.setValue(min(target_value, scrollbar.maximum()))
                cleanup()

        timeout_timer.timeout.connect(on_timeout)

        scrollbar.rangeChanged.connect(on_range_changed)
        timeout_timer.start()

        def initial_trigger():
            if not state['finished']:
                on_range_changed()

        if getattr(mw, "is_processing_library", False) and hasattr(mw, "processor") and mw.processor:
            mw.processor.finished.connect(lambda: QTimer.singleShot(50, initial_trigger))
        else:
            QTimer.singleShot(0, initial_trigger)

    def navigate_back(self):
        """
        Universal back button history stack for selected tab.
        """
        mw = self.main_window
        current_tab_index = mw.main_stack.currentIndex()

        current_tab_name = None
        if current_tab_index < len(mw.nav_button_icon_names):
            current_tab_name = mw.nav_button_icon_names[current_tab_index]
        elif hasattr(mw, "global_search_page_index") and current_tab_index == mw.global_search_page_index:
            current_tab_name = "search"

        if not current_tab_name:
            return

        if not hasattr(mw, 'tab_history'):
            return

        history_stack = mw.tab_history.get(current_tab_name, [])

        def reset_sub_stack_to_root():
            if current_tab_name == "artist" and mw.artists_stack.currentIndex() != 0:
                mw.artists_stack.setCurrentIndex(0)
            elif current_tab_name == "album" and mw.albums_stack.currentIndex() != 0:
                mw.albums_stack.setCurrentIndex(0)
            elif current_tab_name == "genre" and mw.genres_stack.currentIndex() != 0:
                mw.genres_stack.setCurrentIndex(0)
            elif current_tab_name == "composer" and mw.composers_stack.currentIndex() != 0:
                mw.composers_stack.setCurrentIndex(0)
            elif current_tab_name == "playlist" and mw.playlists_stack.currentIndex() != 0:
                mw.playlists_stack.setCurrentIndex(0)
            elif current_tab_name == "folder" and mw.catalog_stack.currentIndex() != 0:
                mw.catalog_stack.setCurrentIndex(0)
            elif current_tab_name == "favorite" and mw.favorites_stack.currentIndex() != 0:
                mw.favorites_stack.setCurrentIndex(0)
                mw.current_favorites_context = None
            elif current_tab_name == "charts" and mw.charts_stack.currentIndex() != 0:
                mw.charts_stack.setCurrentIndex(0)
                mw.current_charts_context = None
            elif current_tab_name == "search" and mw.search_stack.currentIndex() != 0:
                mw.search_stack.setCurrentIndex(0)

        if history_stack:
            previous_state = history_stack.pop()

            mw.is_restoring_state = True
            try:
                mw.current_view_state = previous_state

                context_data = previous_state.get("context_data", {})
                ctx = context_data.get("context")
                data = context_data.get("data")

                handled_manually = False

                if current_tab_name == "favorite" and ctx:
                    if ctx == "all_artists" or (ctx == "artist" and not data):
                        self.favorites_ui_manager.show_all_favorite_artists_view()
                        handled_manually = True
                    elif ctx == "all_albums" or (ctx == "album" and not data):
                        self.favorites_ui_manager.show_all_favorite_albums_view()
                        handled_manually = True
                    elif ctx == "all_genres" or (ctx == "genre" and not data):
                        self.favorites_ui_manager.show_all_favorite_genres_view()
                        handled_manually = True
                    elif ctx == "all_composers" or (ctx == "composer" and not data):
                        self.favorites_ui_manager.show_all_favorite_composers_view()
                        handled_manually = True
                    elif ctx == "all_playlists" or (ctx == "playlist" and not data):
                        self.favorites_ui_manager.show_all_favorite_playlists_view()
                        handled_manually = True
                    elif ctx == "all_folders" or (ctx == "folder" and not data):
                        self.favorites_ui_manager.show_all_favorite_folders_view()
                        handled_manually = True
                    elif ctx == "tracks":
                        self.favorites_ui_manager.show_favorite_tracks_view()
                        handled_manually = True

                    elif ctx == "artist" and data:
                        self.favorites_ui_manager.show_favorite_artist_albums_view(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.favorites_stack)
                        handled_manually = True
                    elif ctx == "composer" and data:
                        self.favorites_ui_manager.show_favorite_composer_albums_view(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.favorites_stack)
                        handled_manually = True
                    elif ctx == "genre" and data:
                        self.favorites_ui_manager.show_favorite_genre_albums_view(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.favorites_stack)
                        handled_manually = True
                    elif ctx == "playlist" and data:
                        self.favorites_ui_manager.show_favorite_playlist_view(data)
                        handled_manually = True
                    elif ctx == "folder" and data:
                        self.favorites_ui_manager.show_favorite_folder_view(data)
                        handled_manually = True
                    elif ctx in ["album", "albums"] and data:
                        album_key = tuple(data) if isinstance(data, list) else data
                        self.show_album_tracks(album_key, source_stack=mw.favorites_stack)
                        handled_manually = True

                elif current_tab_name == "charts" and ctx:
                    if ctx in ["all_artists", "artist", "artists"] and not data:
                        self.charts_ui_manager.show_all_top_artists_view()
                        handled_manually = True
                    elif ctx in ["all_albums", "album", "albums"] and not data:
                        self.charts_ui_manager.show_all_top_albums_view()
                        handled_manually = True
                    elif ctx in ["all_genres", "genre", "genres"] and not data:
                        self.charts_ui_manager.show_all_top_genres_view()
                        handled_manually = True
                    elif ctx in ["all_composers", "composer", "composers"] and not data:
                        self.charts_ui_manager.show_all_top_composers_view()
                        handled_manually = True
                    elif ctx in ["all_tracks", "track", "tracks"] and not data:
                        self.charts_ui_manager.show_all_top_tracks_view()
                        handled_manually = True

                    elif ctx == "artist" and data:
                        self.charts_ui_manager.show_top_artist_albums_view(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.charts_stack)
                        handled_manually = True
                    elif ctx == "genre" and data:
                        self.charts_ui_manager.show_top_genre_albums_view(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.charts_stack)
                        handled_manually = True
                    elif ctx == "composer" and data:
                        self.charts_ui_manager.show_top_composer_albums_view(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.charts_stack)
                        handled_manually = True
                    elif ctx in ["album", "albums"] and data:
                        album_key = tuple(data) if isinstance(data, list) else data
                        self.show_album_tracks(album_key, source_stack=mw.charts_stack)
                        handled_manually = True

                    elif ctx == "archive_month" and data:
                        self.charts_ui_manager.show_archived_month_view(data)
                        handled_manually = True
                    elif ctx.startswith("archive_detail_") and data:
                        chart_type = ctx.replace("archive_detail_", "")
                        self.charts_ui_manager.show_archived_detail_view(data, chart_type)
                        handled_manually = True

                elif current_tab_name == "search" and ctx:
                    if ctx == "artist" and data:
                        self.search_ui_manager.show_search_artist_albums(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.search_stack)
                        handled_manually = True
                    elif ctx == "genre" and data:
                        self.search_ui_manager.show_search_genre_albums(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.search_stack)
                        handled_manually = True
                    elif ctx == "composer" and data:
                        self.search_ui_manager.show_search_composer_albums(data)
                        if "album_key" in context_data:
                            self.show_album_tracks(tuple(context_data["album_key"]), source_stack=mw.search_stack)
                        handled_manually = True
                    elif ctx in ["album", "albums"] and data:
                        album_key = tuple(data) if isinstance(data, list) else data
                        self.search_ui_manager.show_search_album_tracks(album_key)
                        handled_manually = True
                    elif ctx == "playlist" and data:
                        self.search_ui_manager.show_search_playlist_tracks(data)
                        handled_manually = True

                if not handled_manually:
                    mw._apply_view_state(previous_state)

                if "scroll_positions" in previous_state:
                    for attr_name, val in previous_state["scroll_positions"].items():
                        self._schedule_scroll_restore(attr_name, val)

                if not previous_state.get("context_data"):
                    reset_sub_stack_to_root()
            finally:
                mw.is_restoring_state = False
        else:
            mw.is_restoring_state = True
            try:
                reset_sub_stack_to_root()
                mw.current_view_state = {
                    "main_tab_name": current_tab_name,
                    "context_data": {}
                }
            finally:
                mw.is_restoring_state = False