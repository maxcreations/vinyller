"""
Vinyller — State manager
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
import random
from collections import defaultdict

from PyQt6.QtCore import (
    QModelIndex, QSize, Qt, QTimer
)
from PyQt6.QtGui import (
    QPalette
)
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QSizePolicy
)

from src.ui.custom_classes import (
    SearchMode, ViewMode
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon, format_time, format_month_year
)
from src.utils.utils_translator import translate


class StateManager:
    """
    Manages the UI state for the main application window.
    """

    def __init__(self):
        """
        Initializes the state manager with default empty or loading states
        for various UI components, contexts, and views.
        """
        self.current_artist_view = None
        self.current_genre_view = None
        self.current_composer_view = None
        self.current_favorites_context = None
        self.current_charts_context = None

        self.current_favorite_folder_path_nav = ""
        self.current_catalog_path = ""
        self.current_view_state = {}
        self.active_drop_zone = -1

        self.current_ui_queue = []
        self.queue_tracks_generator = None
        self.tracks_to_append_generator = None
        self.current_queue_name = translate("Playback Queue")
        self.current_queue_context_path = None
        self.current_queue_context_data = None
        self.current_open_playlist_path = None
        self.queue_state_before_soft_reload = None

        self.artists_loaded_count = 0
        self.albums_loaded_count = 0
        self.songs_loaded_count = 0
        self.search_loaded_count = 0
        self.genres_loaded_count = 0
        self.composers_loaded_count = 0
        self.is_loading_search = False
        self.is_loading_artists = False
        self.is_loading_genres = False
        self.is_loading_composers = False
        self.is_loading_albums = False
        self.is_loading_songs = False

        self.current_artist_all_tracks_list = []
        self.artist_all_tracks_loaded_count = 0
        self.is_loading_artist_all_tracks = False

        self.current_genre_all_tracks_list = []
        self.genre_all_tracks_loaded_count = 0
        self.is_loading_genre_all_tracks = False

        self.current_composer_albums_list = []
        self.composer_albums_loaded_count = 0
        self.is_loading_composer_albums = False

        self.current_history_display_list = []
        self.history_loaded_count = 0
        self.is_loading_history = False
        self.history_separator_widgets = {}
        self.last_history_group = None
        self.current_history_flow_layout = None
        self.history_groups = set()

        self.current_catalog_display_list = []
        self.catalog_loaded_count = 0
        self.is_loading_catalog = False

        self.scroll_positions = {}
        self.last_splitter_sizes = []
        self.last_artist_letter = None
        self.last_album_group = None
        self.last_composer_letter = None
        self.current_artist_flow_layout = None
        self.current_album_flow_layout = None
        self.current_genre_flow_layout = None
        self.current_composer_flow_layout = None
        self.main_view_track_widgets = defaultdict(list)
        self.main_view_cover_widgets = defaultdict(list)
        self.main_view_card_widgets = defaultdict(list)
        self.main_view_header_play_buttons = {}
        self.pixmap_cache = {}
        self.original_geometry = None
        self.queue_visible_before_vinyl = True
        self.reload_angle = 0

        self.favorites = {}
        self.artist_artworks = {}
        self.genre_artworks = {}
        self.scan_thread = None
        self.processor = None
        self.is_processing_library = False
        self.is_initial_cache_load = False
        self.rescan_initiated_from_dialog = False
        self.active_metadata_dialog = None
        self.current_artwork_path = None
        self.current_search_results = []

        self.is_scrubbing = False
        self.was_playing_before_scrub = False


class PlayerController:
    """
    Acts as a bridge between the user interface and the underlying playback engine,
    handling logic for queuing, seeking, playing contexts, and tracking state.
    """

    def __init__(self, main_window):
        """
        Initializes the PlayerController with a reference to the main window.
        """
        self.main_window = main_window

    def _determine_universal_context(self, track_to_play):
        """
        Determines the appropriate playback queue name, context data, and entity type
        based on the currently active tab and view in the main window.
        """
        mw = self.main_window

        album_artist = track_to_play.get("album_artist")
        album_title = track_to_play.get("album")

        track_year = track_to_play.get("year", 0)

        if mw.treat_folders_as_unique:
            album_key = (
                album_artist,
                album_title,
                track_year,
                os.path.dirname(track_to_play["path"]),
            )
        else:
            album_key = (album_artist, album_title, track_year)

        context_data = album_key
        queue_name = album_title
        entity_type = "album"

        current_tab = mw.main_stack.currentIndex()

        try:
            artist_idx = mw.nav_button_icon_names.index("artist")
            genre_idx = mw.nav_button_icon_names.index("genre")
            composer_idx = mw.nav_button_icon_names.index("composer")
            playlist_idx = mw.nav_button_icon_names.index("playlist")
            fav_idx = mw.nav_button_icon_names.index("favorite")
            track_idx = mw.nav_button_icon_names.index("track")
            search_idx = mw.search_tab_index
            charts_idx = mw.nav_button_icon_names.index("charts")
            try:
                history_idx = mw.nav_button_icon_names.index("history")
            except ValueError:
                history_idx = -1
        except ValueError:
            return queue_name, context_data, entity_type

        if current_tab == artist_idx and mw.artists_stack.currentIndex() > 0:
            if mw.artist_album_view_mode == ViewMode.ALL_TRACKS:
                context_data = mw.current_artist_view
                queue_name = mw.current_artist_view
                entity_type = "artist"

        elif current_tab == genre_idx and mw.genres_stack.currentIndex() > 0:
            if mw.artist_album_view_mode == ViewMode.ALL_TRACKS:
                context_data = mw.current_genre_view
                queue_name = mw.current_genre_view
                entity_type = "genre"

        elif current_tab == composer_idx and mw.composers_stack.currentIndex() > 0:
            if mw.composer_album_view_mode == ViewMode.ALL_TRACKS:
                context_data = {"type": "composer", "data": mw.current_composer_view}
                queue_name = mw.current_composer_view
                entity_type = "composer"

        elif current_tab == fav_idx:
            if mw.current_favorites_context == "tracks":
                context_data = "favorite_tracks"
                queue_name = translate("Favorite Tracks")
                entity_type = None
            elif mw.current_favorites_context == "artist":
                if mw.artist_album_view_mode == ViewMode.ALL_TRACKS:
                    context_data = mw.current_artist_view
                    queue_name = mw.current_artist_view
                    entity_type = "artist"
            elif mw.current_favorites_context == "folder":
                context_data = mw.current_favorite_folder_path_nav
                queue_name = os.path.basename(mw.current_favorite_folder_path_nav)
                entity_type = "folder"
            elif mw.current_favorites_context == "playlist":
                playlist_path = mw.current_view_state.get("context_data", {}).get(
                    "data"
                )
                if playlist_path:
                    context_data = playlist_path
                    queue_name = os.path.splitext(os.path.basename(playlist_path))[0]
                    entity_type = "playlist"

        elif current_tab == charts_idx:
            if mw.current_charts_context and mw.current_charts_context.startswith(
                "archive_detail_"
            ):
                chart_type = mw.current_charts_context.replace("archive_detail_", "")
                month_key = mw.current_view_state.get("context_data", {}).get("data")

                context_data = (chart_type, month_key)
                queue_name = f"{translate(chart_type.capitalize())} ({month_key})"
                entity_type = "charts_archive"
                return queue_name, context_data, entity_type
            if mw.current_charts_context == "all_tracks":
                context_data = "all_top_tracks"
                queue_name = translate("Top Tracks")
                entity_type = None
            elif mw.current_charts_context == "artist":
                if mw.artist_album_view_mode == ViewMode.ALL_TRACKS:
                    context_data = mw.current_artist_view
                    queue_name = mw.current_artist_view
                    entity_type = "artist"
            elif mw.current_charts_context == "genre":
                if mw.artist_album_view_mode == ViewMode.ALL_TRACKS:
                    context_data = mw.current_genre_view
                    queue_name = mw.current_genre_view
                    entity_type = "genre"
            elif mw.current_charts_context == "composer":
                if (
                    mw.composer_album_view_mode == ViewMode.ALL_TRACKS
                ):
                    context_data = {
                        "type": "composer",
                        "data": mw.current_composer_view,
                    }
                    queue_name = mw.current_composer_view
                    entity_type = "composer"

        elif current_tab == playlist_idx and mw.playlists_stack.currentIndex() == 1:
            if mw.current_open_playlist_path:
                context_data = mw.current_open_playlist_path
                queue_name = os.path.splitext(
                    os.path.basename(mw.current_open_playlist_path)
                )[0]
                entity_type = "playlist"


        elif current_tab == track_idx:
            group_name = getattr(mw, "current_songs_group", None)
            if group_name:
                context_data = f"songs_group_{group_name}"
                queue_name = f"{translate('All tracks')} ({group_name})"
            else:
                context_data = "all_tracks"
                queue_name = translate("All tracks")
            entity_type = "songs_group"

        elif current_tab == search_idx:
            if getattr(mw, "current_search_context", None) == "playlist":
                playlist_path = getattr(mw, "current_search_context_data", None)
                if playlist_path:
                    context_data = playlist_path
                    queue_name = os.path.splitext(os.path.basename(playlist_path))[0]
                    entity_type = "playlist"

        elif current_tab == history_idx:
            context_data = "playback_history"
            queue_name = translate("Playback history")
            entity_type = None

        return queue_name, context_data, entity_type

    def play_track_from_playlist_context(
        self, track_to_play, playlist_path, force_restart=False, track_index=None
    ):
        """
        Starts playback of a specific track within the scope of a given playlist.
        """
        mw = self.main_window

        playlist = mw.library_manager.load_playlist(
            playlist_path, mw.data_manager.path_to_track_map
        )
        if not playlist:
            return

        mw.current_queue_name = os.path.splitext(os.path.basename(playlist_path))[0]
        mw.current_queue_context_path = playlist_path
        mw.current_queue_context_data = playlist_path

        mw.conscious_choice_data = (playlist_path, "playlist")

        mw.player.set_queue(playlist)

        if (
            track_index is not None
            and 0 <= track_index < len(playlist)
            and playlist[track_index]["path"] == track_to_play["path"]
        ):
            mw.player.play(track_index)
        else:
            mw.player.play(track_to_play)

    def handle_scrubbing_started(self):
        """
        Pauses playback and tracks state when the user begins to drag the progress scrubber.
        """
        mw = self.main_window
        if mw.player.player.duration() <= 0:
            return
        mw.is_scrubbing = True
        mw.was_playing_before_scrub = (
            mw.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState
        )
        mw.player.pause()

    def handle_position_scrubbed(self, delta_angle: float):
        """
        Adjusts the track position relative to the angle delta scrubbed by the user.
        """
        mw = self.main_window
        if not mw.is_scrubbing:
            return

        current_index = mw.player.get_current_index()
        queue = mw.player.get_current_queue()

        if 0 <= current_index < len(queue):
            track = queue[current_index]
            duration_ms = track.get("duration_ms", track.get("duration", 0) * 1000)
        else:
            duration_ms = mw.player.player.duration()

        if duration_ms <= 0:
            return

        current_virtual_position = mw.control_panel.progress_slider.value()

        delta_ms = int(delta_angle * mw.SCRUB_SENSITIVITY_MS_PER_DEGREE)
        new_virtual_position = current_virtual_position + delta_ms
        new_virtual_position = max(0, min(new_virtual_position, duration_ms))

        self.seek_position(new_virtual_position)

    def handle_scrubbing_finished(self):
        """
        Finalizes the scrubbing action and resumes playback if it was previously playing.
        """
        mw = self.main_window
        if not mw.is_scrubbing:
            return
        mw.is_scrubbing = False
        if mw.was_playing_before_scrub:
            mw.player.resume()

    def update_track_info(self, artist, title, received_index):
        """
        Updates the UI elements (control panel, vinyl widget, etc.) with the metadata
        of the track currently loaded in the player.
        """
        mw = self.main_window
        mw.ui_manager.update_all_track_widgets()
        player_queue = mw.player.get_current_queue()

        if not (0 <= received_index < len(player_queue)):
            default_pixmap = mw.ui_manager.components.get_pixmap(None, 128)
            mw.control_panel.clear_track_info(default_pixmap)
            mw.vinyl_widget.set_cover(None)
            mw.vinyl_widget.update_unbox_button_state(False)
            mw.current_artwork_path = None

            if getattr(mw, "mini_window", None):
                try:
                    mw.mini_window.set_track_data({}, None, False, None, None, None)
                    mw.mini_window.set_current_index(-1)
                except Exception as e:
                    print(f"MiniVinny cleanup error: {e}")
            return

        current_track = player_queue[received_index]
        artist_text = ", ".join(current_track.get("artists", [translate("Unknown")]))
        title_text = current_track.get("title", translate("Untitled"))
        album_title = current_track.get("album", translate("Unknown Album"))
        album_artist = current_track.get("album_artist", translate("Unknown"))
        year = current_track.get("year", 0)
        year_text = str(year) if year > 0 else ""
        genres = current_track.get("genre", [])
        mw.current_artwork_path = current_track.get("artwork")
        cover_pixmap_128 = mw.ui_manager.components.get_pixmap(
            mw.current_artwork_path, 128
        )
        has_real_artwork = bool(mw.current_artwork_path)

        artist_for_nav = ""
        if mw.artist_source_tag == "artist":
            artists = current_track.get("artists")
            if artists:
                artist_for_nav = artists[0]

        if not artist_for_nav:
            artist_for_nav = (
                    current_track.get("album_artist")
                    or (current_track.get("artists") and current_track.get("artists")[0])
                    or ""
            )

        if mw.treat_folders_as_unique:
            album_data_key = (
                album_artist,
                album_title,
                year,
                os.path.dirname(current_track["path"]),
            )
        else:
            album_data_key = (album_artist, album_title, year)

        mw.control_panel.update_track_info(
            artist = artist_text,
            title = title_text,
            album = album_title,
            year = year_text,
            genres = genres,
            cover_pixmap = cover_pixmap_128,
            has_real_artwork = has_real_artwork,
            album_data = album_data_key,
            artist_data = artist_for_nav,
            track_data = current_track,
        )

        virt_duration_ms = current_track.get(
            "duration_ms", current_track.get("duration", 0) * 1000
        )
        self.update_duration(virt_duration_ms)

        direction = "forward"

        if hasattr(mw, "last_played_index") and mw.last_played_index != -1:
            if received_index < mw.last_played_index:
                direction = "backward"

        mw.last_played_index = received_index

        if mw.current_artwork_path:
            vinyl_cover_pixmap = mw.ui_manager.components.get_pixmap(
                mw.current_artwork_path, 512
            )
            mw.vinyl_widget.set_cover(vinyl_cover_pixmap, direction = direction)
        else:
            mw.vinyl_widget.set_cover(None, direction = direction)

        self.update_favorite_button_ui()

        if hasattr(mw, "mac_media_manager"):
            is_playing = mw.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState
            mw.mac_media_manager.update_now_playing_info(current_track, is_playing)

        if getattr(mw, "mini_window", None):
            try:
                is_fav = bool(mw.control_panel.favorite_button_ctrl.property("active"))
                mw.mini_window.set_track_data(
                    track_data = current_track,
                    cover_pixmap = cover_pixmap_128,
                    is_favorite = is_fav,
                    nav_artist_data = artist_for_nav,
                    nav_album_data = album_data_key,
                    nav_year_data = year_text
                )
                mw.mini_window.set_current_index(received_index)
            except Exception as e:
                print(f"MiniVinny update error: {e}")

    def update_player_state(self, state: QMediaPlayer.PlaybackState):
        """
        Synchronizes UI elements (control panel status, vinyl rotation, track widgets)
        and the macOS media manager with the media player's state.
        """
        mw = self.main_window
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        mw.control_panel.update_playback_state(is_playing)

        if hasattr(mw, "mac_media_manager"):
            current_queue = mw.player.get_current_queue()
            current_index = mw.player.get_current_index()
            if 0 <= current_index < len(current_queue):
                mw.mac_media_manager.update_now_playing_info(current_queue[current_index], is_playing)

        if mw.is_scrubbing:
            return

        if is_playing:
            mw.vinyl_widget.start_rotation()
        else:
            mw.vinyl_widget.stop_rotation()
        mw.ui_manager.update_all_track_widgets()

    def play_data_shuffled(self, data):
        """
        Starts playback after shuffling the track list.
        The global shuffle mode remains unchanged.
        """
        self.play_data(data, shuffle=True)

    def play_data(self, data, shuffle=False):
        """
        Gathers tracks associated with the given data entity (album, artist, playlist, etc.)
        and begins playback, optionally shuffling the new queue.
        """
        mw = self.main_window
        mw.current_queue_context_path = None

        entity_type = None
        item_name_for_queue = translate("Playback Queue")

        current_sort_mode = mw.artist_album_sort_mode

        if isinstance(data, dict) and data.get("type") == "composer":
            current_sort_mode = getattr(
                mw, "composer_album_sort_mode", mw.artist_album_sort_mode
            )
        elif isinstance(data, str) and data in mw.data_manager.composers_data:
            current_sort_mode = getattr(
                mw, "composer_album_sort_mode", mw.artist_album_sort_mode
            )

        if isinstance(data, dict) and data.get("type") == "search_results":
            mw.current_queue_name = translate("Search Results")
            mw.current_queue_context_data = "search_results"
            mw.conscious_choice_data = ("search_results", "search")

            tracks = []

            if mw.search_mode in [
                SearchMode.EVERYWHERE,
                SearchMode.FAVORITES,
                SearchMode.TRACKS,
            ]:
                for _, album_tracks in mw.current_search_results:
                    tracks.extend(album_tracks)
            elif mw.search_mode == SearchMode.LYRICS:
                for t_data, _ in mw.current_search_results:
                    tracks.append(t_data)
            else:
                for item_key, _ in mw.current_search_results:
                    fetch_data = item_key
                    if mw.search_mode == SearchMode.COMPOSERS:
                        fetch_data = {"type": "composer", "data": item_key}

                    tracks.extend(
                        mw.data_manager.get_tracks_from_data(
                            fetch_data,
                            mw.library_manager,
                            current_sort_mode,
                            mw.favorite_tracks_sort_mode,
                            mw.favorites,
                        )
                    )

            if tracks:
                tracks = [
                    dict(t, **{"__original_index": i}) for i, t in enumerate(tracks)
                ]
                if shuffle:
                    random.shuffle(tracks)
                mw.player.set_queue(tracks)
                mw.player.play(0)
            return

        mw.current_queue_context_data = data

        if isinstance(data, str):
            if data in mw.data_manager.artists_data:
                entity_type = "artist"
                item_name_for_queue = data
            elif data in mw.data_manager.genres_data:
                entity_type = "genre"
                item_name_for_queue = data
            elif data in mw.data_manager.composers_data:
                entity_type = "composer"
                item_name_for_queue = data
            elif os.path.isdir(data):
                entity_type = "folder"
                item_name_for_queue = os.path.basename(data)
            elif os.path.isfile(data) and data.lower().endswith((".m3u", ".m3u8")):
                entity_type = "playlist"
                mw.current_queue_context_path = data
                item_name_for_queue = os.path.splitext(os.path.basename(data))[0]

            elif data == "favorite_tracks":
                item_name_for_queue = translate("Favorite Tracks")
            elif data == "all_tracks":
                item_name_for_queue = translate("All tracks")
            elif data == "all_favorite_artists":
                item_name_for_queue = translate("All Favorite Artists")
            elif data == "all_favorite_albums":
                item_name_for_queue = translate("All Favorite Albums")
            elif data == "all_favorite_genres":
                item_name_for_queue = translate("All Favorite Genres")
            elif data == "all_favorite_composers":
                item_name_for_queue = translate("All Favorite Composers")
            elif data == "all_favorite_folders":
                item_name_for_queue = translate("All Favorite Folders")
            elif data == "all_favorite_playlists":
                item_name_for_queue = translate("All Favorite Playlists")
            elif data == "playback_history":
                item_name_for_queue = translate("Playback history")
            elif data == "all_top_tracks":
                item_name_for_queue = translate("Top Tracks")
            elif data == "all_top_artists":
                item_name_for_queue = translate("Top Artists")
            elif data == "all_top_albums":
                item_name_for_queue = translate("Top Albums")
            elif data == "all_top_genres":
                item_name_for_queue = translate("Top Genres")
            elif data == "all_top_composers":
                item_name_for_queue = translate("Top Composers")

        elif isinstance(data, tuple):
            try:
                if (
                    len(data) == 2
                    and data[0] in ["tracks", "artists", "albums", "genres"]
                    and isinstance(data[1], str)
                    and len(data[1]) == 7
                ):
                    cat_key, month_key = data
                    formatted_date = format_month_year(month_key)
                    title_map = {
                        "tracks": translate("Top Tracks"),
                        "artists": translate("Top Artists"),
                        "albums": translate("Top Albums"),
                        "genres": translate("Top Genres"),
                    }
                    item_name_for_queue = (
                        title_map.get(cat_key, cat_key) + f" ({formatted_date})"
                    )
                    entity_type = "charts_archive"

                elif len(data) > 1 and data[1] == "month_overview":
                    month_key = data[0]
                    formatted_date = format_month_year(month_key)
                    item_name_for_queue = (
                        translate("Top Tracks") + f" ({formatted_date})"
                    )
                    entity_type = "charts_archive"

                elif len(data) == 3 and data[0] in [
                    "tracks",
                    "artists",
                    "albums",
                    "genres",
                ]:
                    month_key = data[1]
                    formatted_date = format_month_year(month_key)
                    item_name_for_queue = (
                        translate("Charts Archive") + f" ({formatted_date})"
                    )
                    entity_type = "charts_archive"
                else:
                    item_name_for_queue = data[1]
                    entity_type = "album"

            except Exception:
                item_name_for_queue = data[1] if len(data) > 1 else str(data)
                entity_type = "album"

        elif isinstance(data, dict):
            item_name_for_queue = data.get("album", translate("Playback Queue"))

        mw.current_queue_name = item_name_for_queue

        if entity_type:
            if (
                entity_type == "charts_archive"
                and isinstance(data, tuple)
                and len(data) >= 2
            ):
                hashable_key = (data[0], data[1])
                mw.conscious_choice_data = (hashable_key, entity_type)
            else:
                mw.conscious_choice_data = (data, entity_type)

        tracks = mw.data_manager.get_tracks_from_data(
            data,
            mw.library_manager,
            current_sort_mode,
            mw.favorite_tracks_sort_mode,
            mw.favorites,
        )

        if tracks:
            tracks = [dict(t, **{"__original_index": i}) for i, t in enumerate(tracks)]

            if shuffle:
                random.shuffle(tracks)

            if not self._ensure_track_file_exists(tracks[0]):
                return

            mw.player.set_queue(tracks)
            mw.player.play(0)

    def perform_search(self, query: str):
        """
        Executes a library search based on the provided query string and the
        currently selected SearchMode, updating the UI with results.
        """
        mw = self.main_window
        mw.current_search_context = None
        mw.current_search_context_data = None
        if not query:
            mw.current_search_results = []
            if mw.data_manager.is_empty():
                mw.search_bar.setEnabled(False)
                mw.search_bar.setPlaceholderText(translate("Nothing to search for yet"))
                mw.ui_manager.search_ui_manager.show_no_library_message_on_search_tab()
            else:
                mw.search_bar.setEnabled(True)
                mw.search_bar.setPlaceholderText(
                    translate("Search by title, artist, album...")
                )
                mw.ui_manager.search_ui_manager.show_random_album_on_search_tab()
            return

        search_text = query.lower()
        results = []
        search_mode = mw.search_mode

        if search_mode == SearchMode.EVERYWHERE:
            matching_tracks = [
                t
                for t in mw.data_manager.all_tracks
                if search_text in t.get("title", "").lower()
                or any(search_text in a.lower() for a in t.get("artists", []))
                or search_text in t.get("album", "").lower()
                or any(search_text in g.lower() for g in t.get("genre", []))
                or search_text in t.get("composer", "").lower()
                or search_text in t.get("lyrics", "").lower()
            ]

            grouped_results = defaultdict(list)
            for track in matching_tracks:
                track_year = track.get("year", 0)

                if mw.treat_folders_as_unique:
                    album_key = (
                        track.get("album_artist", translate("Unknown Artist")),
                        track.get("album", translate("Unknown Album")),
                        track_year,
                        os.path.dirname(track["path"]),
                    )
                else:
                    album_key = (
                        track.get("album_artist", translate("Unknown Artist")),
                        track.get("album", translate("Unknown Album")),
                        track_year,
                    )
                grouped_results[album_key].append(track)
            results = [(k, grouped_results[k]) for k in sorted(grouped_results.keys())]

        elif search_mode == SearchMode.FAVORITES:
            favs = mw.library_manager.load_favorites()
            fav_track_paths = set(favs.get("tracks", {}).keys())
            fav_album_keys = {tuple(k) for k in favs.get("albums", [])}
            fav_artist_names = set(favs.get("artists", []))

            fav_tracks = [
                t
                for t in mw.data_manager.all_tracks
                if t["path"] in fav_track_paths
                or (t.get("album_artist"), t.get("album")) in fav_album_keys
                or any(artist in fav_artist_names for artist in t.get("artists", []))
            ]

            matching_tracks = [
                t
                for t in fav_tracks
                if search_text in t.get("title", "").lower()
                or any(search_text in a.lower() for a in t.get("artists", []))
                or search_text in t.get("album", "").lower()
                or search_text in t.get("lyrics", "").lower()
            ]

            grouped_results = defaultdict(list)
            for track in matching_tracks:
                track_year = track.get("year", 0)

                if mw.treat_folders_as_unique:
                    album_key = (
                        track.get("album_artist", translate("Unknown Artist")),
                        track.get("album", translate("Unknown Album")),
                        track_year,
                        os.path.dirname(track["path"]),
                    )
                else:
                    album_key = (
                        track.get("album_artist", translate("Unknown Artist")),
                        track.get("album", translate("Unknown Album")),
                        track_year,
                    )
                grouped_results[album_key].append(track)
            results = [(k, grouped_results[k]) for k in sorted(grouped_results.keys())]

        elif search_mode == SearchMode.ARTISTS:
            results = [
                (name, data)
                for name, data in mw.data_manager.artists_data.items()
                if search_text in name.lower()
            ]

        elif search_mode == SearchMode.ALBUMS:
            results = [
                (key, data)
                for key, data in mw.data_manager.albums_data.items()
                if search_text in key[1].lower()
            ]

        elif search_mode == SearchMode.GENRES:
            results = [
                (name, data)
                for name, data in mw.data_manager.genres_data.items()
                if search_text in name.lower()
            ]

        elif search_mode == SearchMode.COMPOSERS:
            results = [
                (name, data)
                for name, data in mw.data_manager.composers_data.items()
                if search_text in name.lower()
            ]

        elif search_mode == SearchMode.TRACKS:
            matching_tracks = [
                t
                for t in mw.data_manager.all_tracks
                if search_text in t.get("title", "").lower()
                or search_text in t.get("lyrics", "").lower()
            ]

            grouped_results = defaultdict(list)
            for track in matching_tracks:
                track_year = track.get("year", 0)

                if mw.treat_folders_as_unique:
                    album_key = (
                        track.get("album_artist", translate("Unknown Artist")),
                        track.get("album", translate("Unknown Album")),
                        track_year,
                        os.path.dirname(track["path"]),
                    )
                else:
                    album_key = (
                        track.get("album_artist", translate("Unknown Artist")),
                        track.get("album", translate("Unknown Album")),
                        track_year,
                    )
                grouped_results[album_key].append(track)
            results = [(k, grouped_results[k]) for k in sorted(grouped_results.keys())]

        elif search_mode == SearchMode.PLAYLISTS:
            all_playlists = mw.library_manager.get_playlists()
            results = [
                p
                for p in all_playlists
                if search_text in os.path.splitext(os.path.basename(p))[0].lower()
            ]

        elif search_mode == SearchMode.LYRICS:
            matching_items = []
            for t in mw.data_manager.all_tracks:
                lyrics = t.get("lyrics", "")
                if not lyrics:
                    continue

                idx = lyrics.lower().find(search_text)
                if idx != -1:
                    start = max(0, idx - 30)
                    end = min(len(lyrics), idx + len(search_text) + 50)

                    snippet = lyrics[start:end]
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(lyrics):
                        snippet = snippet + "..."

                    snippet = snippet.replace("\n", " / ").replace("\r", "")

                    matching_items.append((t, snippet))

            results = sorted(matching_items, key=lambda x: x[0].get("title", ""))

        mw.current_search_results = results
        mw.ui_manager.search_ui_manager.populate_search_results()

        if mw.main_stack.currentIndex() != mw.search_tab_index:
            mw.main_stack.setCurrentIndex(mw.search_tab_index)

            for btn in mw.nav_buttons:
                btn.setChecked(False)

            mw.ui_manager.update_nav_button_icons()

    def play_from_search(self, track_data):
        """
        Starts playback of a specific track originating from the search results,
        contextualizing the playback queue to its containing album.
        """
        if not self._ensure_track_file_exists(track_data):
            return

        mw = self.main_window

        album_artist = track_data.get("album_artist")
        album_title = track_data.get("album")
        track_year = track_data.get("year", 0)

        if mw.treat_folders_as_unique:
            album_key = (
                album_artist,
                album_title,
                track_year,
                os.path.dirname(track_data["path"]),
            )
        else:
            album_key = (album_artist, album_title, track_year)

        mw.current_queue_name = album_title
        mw.current_queue_context_path = None
        mw.current_queue_context_data = album_key

        mw.conscious_choice_data = (track_data["path"], "track")

        queue_for_this_album = next(
            (tracks for key, tracks in mw.current_search_results if key == album_key),
            [],
        )

        if queue_for_this_album:
            sorted_queue = sorted(
                queue_for_this_album,
                key=lambda t: (t.get("discnumber", 0), t.get("tracknumber", 0)),
            )
            mw.player.set_queue(sorted_queue)
            mw.player.play(track_data)

    def play_specific_track(self, track_data):
        """
        Plays an arbitrary track directly and contextualizes the queue to that track's album.
        """
        if not self._ensure_track_file_exists(track_data):
            return
        mw = self.main_window

        track_year = track_data.get("year", 0)

        if mw.treat_folders_as_unique:
            album_key = (
                track_data.get("album_artist"),
                track_data.get("album"),
                track_year,
                os.path.dirname(track_data["path"]),
            )
        else:
            album_key = (
                track_data.get("album_artist"),
                track_data.get("album"),
                track_year,
            )

        mw.current_queue_name = track_data.get("album", translate("Playback Queue"))
        mw.current_queue_context_path = None
        mw.current_queue_context_data = album_key

        mw.conscious_choice_data = (track_data["path"], "track")

        album_tracks = sorted(
            mw.data_manager.albums_data.get(album_key, {}).get("tracks", [track_data]),
            key=lambda t: (t.get("discnumber", 0), t.get("tracknumber", 0)),
        )
        mw.player.set_queue(album_tracks)
        mw.player.play(track_data)

    def play_or_pause_track_universal(self, track_to_play, track_index=None):
        """
        Toggles playback for a track if it's already active and matches the context,
        otherwise starts the track from the beginning within its universal context.
        """
        mw = self.main_window
        queue = mw.player.get_current_queue()
        current_index = mw.player.get_current_index()

        current_track = (
            queue[current_index] if queue and 0 <= current_index < len(queue) else None
        )

        expected_queue_name, expected_context_data, _ = (
            self._determine_universal_context(track_to_play)
        )

        is_same_track = current_track and current_track["path"] == track_to_play["path"]
        is_same_context = mw.current_queue_context_data == expected_context_data

        is_same_index = True
        if track_index is not None:
            is_same_index = current_index == track_index

        if is_same_track and is_same_context and is_same_index:
            self.toggle_play_pause()
        else:
            if not self._ensure_track_file_exists(track_to_play):
                return
            self.play_track_from_start_universal(track_to_play, track_index)

    def play_track_from_start_universal(self, track_to_play, track_index=None):
        """
        Always starts the specified track from the beginning, validating
        and applying its universal queue context.
        """
        mw = self.main_window

        queue_name, context_data_for_dm, entity_type = (
            self._determine_universal_context(track_to_play)
        )

        mw.current_queue_context_data = context_data_for_dm
        mw.current_queue_name = queue_name

        mw.conscious_choice_data = (track_to_play["path"], "track")

        queue = []

        if (
                mw.main_stack.currentIndex() == mw.search_tab_index
                and entity_type == "album"
        ):
            album_key = context_data_for_dm
            album_tracks = mw.data_manager.albums_data.get(album_key, {}).get(
                "tracks", []
            )
            if album_tracks:
                queue = sorted(
                    album_tracks,
                    key = lambda t: (t.get("discnumber", 0), t.get("tracknumber", 0)),
                )
        elif mw.main_stack.currentIndex() == mw.nav_button_icon_names.index("track"):
            if hasattr(mw, "current_songs_display_list") and mw.current_songs_display_list:
                for _, tracks in mw.current_songs_display_list:
                    queue.extend(sorted(tracks,
                    key = lambda t: (t.get("discnumber", 0), t.get("tracknumber", 0))))

        if not queue and context_data_for_dm:
            queue = mw.data_manager.get_tracks_from_data(
                context_data_for_dm,
                mw.library_manager,
                mw.artist_album_sort_mode,
                mw.favorite_tracks_sort_mode,
                mw.favorites,
            )

        if queue:
            mw.player.set_queue(queue)

            target_index = -1

            if track_index is not None and 0 <= track_index < len(queue):
                if queue[track_index]["path"] == track_to_play["path"]:
                    target_index = track_index

            if target_index == -1:
                for i, t in enumerate(queue):
                    if t["path"] == track_to_play["path"]:
                        target_index = i
                        break

            if target_index != -1:
                target_index = max(0, target_index)
                self.validate_and_play(target_index)
            else:
                mw.player.play(0)

            playing_track = queue[mw.player.get_current_index()]
            if "::" in playing_track.get("path", ""):
                start_ms = playing_track.get("start_ms", 0)
                if start_ms > 0:
                    mw.player.set_position(start_ms)

    def play_from_queue_action(self, index: QModelIndex):
        """
        Handles an action (like pressing Enter) to play a track from the queue UI view.
        """
        mw = self.main_window
        if not index.isValid():
            return

        current_track_index = mw.player.get_current_index()
        player_state = mw.player.get_current_state()

        if index.row() == current_track_index:
            if player_state == QMediaPlayer.PlaybackState.PlayingState:
                mw.player.pause()
            elif player_state == QMediaPlayer.PlaybackState.PausedState:
                mw.player.resume()
            elif player_state == QMediaPlayer.PlaybackState.StoppedState:
                mw.player.play(current_track_index)
        else:
            queue = mw.player.get_current_queue()
            if 0 <= index.row() < len(queue):
                track_data = queue[index.row()]
                mw.conscious_choice_data = (track_data["path"], "track")

            self.validate_and_play(index.row())

            track_to_play = queue[index.row()]
            if "::" in track_to_play.get("path", ""):
                start_ms = track_to_play.get("start_ms", 0)
                if start_ms > 0:
                    mw.player.set_position(start_ms)

    def play_from_queue_double_click(self, item):
        """
        Handles double click events to play a track directly from the queue UI list widget.
        """
        mw = self.main_window
        source_widget = item.listWidget()
        if not source_widget:
            return
        index = source_widget.row(item)

        if 0 <= index < len(mw.current_ui_queue):
            track_data = mw.current_ui_queue[index]

            if not self._ensure_track_file_exists(track_data):
                return

            mw.conscious_choice_data = (track_data["path"], "track")
            mw.player.play(index)

            if "::" in track_data.get("path", ""):
                start_ms = track_data.get("start_ms", 0)
                if start_ms > 0:
                    mw.player.set_position(start_ms)

    def toggle_play_pause(self):
        """
        Toggles between playing and paused states.
        If stopped, it either plays a random album or restarts playback.
        """
        mw = self.main_window
        state = mw.player.get_current_state()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            mw.player.pause()
        elif state == QMediaPlayer.PlaybackState.PausedState:
            mw.player.resume()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            if not mw.player.get_current_queue():
                if not mw.data_manager.is_empty():
                    self.play_data(
                        random.choice(list(mw.data_manager.albums_data.keys()))
                    )
                else:
                    print(translate("Library is empty. Nothing to play."))
            else:
                mw.player.play(mw.player.get_current_index())

    def handle_resume_request(self):
        """
        Resumes playback if it is paused or stopped (and the queue isn't empty).
        """
        mw = self.main_window
        state = mw.player.get_current_state()
        if state == QMediaPlayer.PlaybackState.PausedState:
            mw.player.resume()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            if mw.player.get_current_index() != -1:
                mw.player.play(mw.player.get_current_index())

    def update_position(self, position):
        """
        Updates the playback position display and handles virtual tracks
        (like individual tracks in CUE files).
        """
        mw = self.main_window

        current_index = mw.player.get_current_index()
        queue = mw.player.get_current_queue()

        if 0 <= current_index < len(queue):
            current_track = queue[current_index]

            if "::" in current_track.get("path", ""):
                start_ms = current_track.get("start_ms", 0)
                duration_ms = current_track.get(
                    "duration_ms", current_track.get("duration", 0) * 1000
                )

                end_ms = start_ms + duration_ms

                if position >= end_ms and duration_ms > 0:
                    mw.player.next()
                    return

                virtual_position = max(0, position - start_ms)

                mw.control_panel.update_position(
                    virtual_position, format_time(virtual_position)
                )

                if getattr(mw, "mini_window", None):
                    mw.mini_window.set_position(virtual_position)
                return

        self.main_window.control_panel.update_position(position, format_time(position))

        if getattr(mw, "mini_window", None):
            mw.mini_window.set_position(position)

    def update_duration(self, duration):
        """
        Updates the UI to reflect the total track duration, taking CUE tracks into account.
        """
        mw = self.main_window
        current_index = mw.player.get_current_index()
        queue = mw.player.get_current_queue()

        real_duration = duration

        if 0 <= current_index < len(queue):
            current_track = queue[current_index]
            if "::" in current_track.get("path", ""):
                virt_duration = current_track.get(
                    "duration_ms", current_track.get("duration", 0) * 1000
                )
                real_duration = virt_duration

        duration_str = format_time(real_duration)
        self.main_window.control_panel.update_duration(real_duration, duration_str)

        if getattr(mw, "mini_window", None):
            mw.mini_window.set_duration(real_duration)

    def seek_position(self, position):
        """
        Changes the playback position within the media, adjusting correctly
        for tracks inside a CUE file.
        """
        mw = self.main_window
        current_index = mw.player.get_current_index()
        queue = mw.player.get_current_queue()

        real_position = position

        if 0 <= current_index < len(queue):
            track = queue[current_index]
            if "::" in track.get("path", ""):
                start_ms = track.get("start_ms", 0)
                real_position = start_ms + position

        mw.player.set_position(real_position)

    def update_shuffle_button_ui(self):
        """
        Updates the toggle state of the shuffle button in the control panel.
        """
        mw = self.main_window
        mw.control_panel.update_shuffle_button(mw.player.is_shuffled())

    def toggle_shuffle(self):
        """
        Toggles playback shuffle functionality and updates the corresponding UI elements.
        """
        mw = self.main_window
        mw.player.toggle_shuffle()
        self.update_shuffle_button_ui()

    def cycle_repeat_mode(self):
        """
        Cycles the playback repeat mode (off, track, album/queue) and updates the UI button.
        """
        mw = self.main_window
        new_mode = mw.player.cycle_repeat_mode()
        mw.control_panel.update_repeat_button(new_mode)

    def update_favorite_button_ui(self):
        """
        Updates the favorite button state depending on whether the currently
        playing track is in the favorites list.
        """
        mw = self.main_window
        player_queue = mw.player.get_current_queue()
        current_index = mw.player.get_current_index()
        is_enabled = 0 <= current_index < len(player_queue)
        is_favorite = False
        if is_enabled:
            current_track = player_queue[current_index]
            is_favorite = mw.library_manager.is_favorite(current_track["path"], "track")
        mw.control_panel.update_favorite_button(is_enabled, is_favorite)
        mw.vinyl_widget.update_unbox_button_state(is_enabled)

    def on_queue_changed(self, update_only=False):
        """
        Synchronizes all UI components displaying the queue (right panel, vinyl queue, etc.)
        when the underlying player queue structure changes.
        """
        mw = self.main_window
        queue = mw.player.get_current_queue()

        if not update_only:
            mw.current_ui_queue = queue

        mw.right_panel.update_right_queue(queue)
        mw.right_panel.update_vinyl_queue(queue)

        mw.ui_manager.update_queue_header()
        mw.ui_manager.update_all_track_widgets()

    def smart_play(self, data):
        """
        If the data matches the current queue, resumes playback.
        If the data is new, loads it via play_data.
        """
        mw = self.main_window

        if data == mw.current_queue_context_data:
            if mw.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState:
                mw.player.pause()
            else:
                self.handle_resume_request()
        else:
            self.play_data(data)

    def _ensure_track_file_exists(self, track_data, silent = True):
        """
        Checks for physical file existence.
        If missing: marks track, stops player, triggers background monitoring.
        """
        if not track_data:
            return False

        mw = self.main_window
        path = track_data.get("real_path", track_data.get("path", ""))
        if isinstance(path, str) and "::" in path:
            path = path.split("::")[0]

        if path and not os.path.exists(path):
            missing_tag = translate("File not found")
            current_title = track_data.get("title", "")
            if not current_title.startswith(f"[{missing_tag}]"):
                track_data["title"] = f"[{missing_tag}] {current_title}"

            mw.player.stop()

            mw.ui_manager.update_all_track_widgets()

            if hasattr(mw, "start_library_change_detection"):
                 QTimer.singleShot(500, mw.start_library_change_detection)

            if not silent:
                print(f"Playback prevented: file not found at {path}")

            return False
        return True

    def validate_and_play(self, index, direction = 1):
        """
        Finds the first available track in the queue starting from the given index.
        If a track is unavailable, marks it and tries the next one.
        """
        mw = self.main_window
        queue = mw.player.get_current_queue()

        while 0 <= index < len(queue):
            track = queue[index]
            if self._ensure_track_file_exists(track, silent = True):
                mw.player.play(index)
                return True
            index += direction

        mw.player.stop()
        return False


    def _handle_missing_file(self, track_data):
        """
        Centralized handling for a missing file.
        Adjusts the track title and forces UI components to reflect the missing state.
        """
        mw = self.main_window
        path = track_data.get("path", "")

        if not path:
            return

        missing_title = f"[{translate('File not found')}] {track_data.get('title', '')}"

        track_data['title'] = missing_title

        mw.player.stop()

        self.refresh_track_widgets_status(path, missing_title)

        mw.pending_external_changes_count += 1
        mw._update_pending_updates_widget()

    def refresh_track_widgets_status(self, path, new_title):
        """
        Updates the text in all TrackListWidget, CardWidget, and other UI instances
        to reflect the new title (e.g., when marking a track as missing).
        """
        mw = self.main_window

        widgets = mw.main_view_track_widgets.get(path, [])
        for widget in widgets:
            if hasattr(widget, 'title_label'):
                widget.title_label.setText(new_title)
                widget.setEnabled(False)
            if hasattr(widget, 'update_metadata'):
                widget.update_metadata()

        for track_list in mw.main_view_track_lists:
            for i in range(track_list.count()):
                item = track_list.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)

                if data and isinstance(data, dict) and data.get('path') == path:
                    item.setText(new_title)


                    break

        mw.right_panel.queue_widget.viewport().update()
        if hasattr(mw.right_panel, "vinyl_queue_widget"):
            mw.right_panel.vinyl_queue_widget.viewport().update()


class DropZoneManager:
    """
    Manages the drag-and-drop zones shown when the user drags files into
    the application interface.
    """

    def __init__(self, main_window):
        """
        Initializes the DropZoneManager and sets up the visual overlay zones.
        """
        self.mw = main_window
        self.setup_drop_zones()

    def setup_drop_zones(self):
        """
        Creates and configures the overlay frames (Add to Library, Add to Queue, Replace Queue)
        shown during drag-and-drop operations.
        """
        self.mw.drop_zone_container = QFrame(self.mw)
        self.mw.drop_zone_container.setObjectName("dropZoneContainer")
        self.mw.drop_zone_container.hide()
        self.mw.drop_zone_library = QFrame(self.mw.drop_zone_container)
        self.mw.drop_zone_append = QFrame(self.mw.drop_zone_container)
        self.mw.drop_zone_replace = QFrame(self.mw.drop_zone_container)

        zones_data = [
            (self.mw.drop_zone_library, "folder_add", translate("Add to Library")),
            (self.mw.drop_zone_append, "add", translate("Add to Queue")),
            (self.mw.drop_zone_replace, "replace", translate("Replace Queue")),
        ]

        for zone, icon_name, text in zones_data:
            zone.setObjectName("dropZone")
            zone.setProperty("active", False)

            layout = QVBoxLayout(zone)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(16)
            layout.addStretch()

            icon_label = QLabel()
            icon_pixmap = create_svg_icon(
                f"assets/control/{icon_name}.svg",
                theme.COLORS["SECONDARY"],
                QSize(48, 48),
            ).pixmap(QSize(48, 48))
            icon_label.setPixmap(icon_pixmap)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label)

            text_label = QLabel(text)
            text_label.setWordWrap(True)
            text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            p = text_label.palette()
            p.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            text_label.setPalette(p)
            text_label.setStyleSheet(
                f"font-size: 16px; color: {theme.COLORS["WHITE"]};"
            )
            layout.addWidget(text_label)

            layout.addStretch()

    def resize_drop_zones(self):
        """
        Recalculates the geometry of the drag-and-drop zones.
        In standard mode: Library on the left, Queue on the right (top/bottom).
        In Vinyl mode: All zones vertically stacked.
        """
        if (
            not hasattr(self.mw, "drop_zone_container")
            or not self.mw.drop_zone_container
        ):
            return

        rect = self.mw.rect()
        self.mw.drop_zone_container.setGeometry(rect)

        main_width = rect.width()
        control_panel_height = (
            self.mw.control_panel.height() if self.mw.control_panel.isVisible() else 0
        )
        main_height = rect.height() - control_panel_height

        if self.mw.vinyl_toggle_button.isChecked():
            zone_height = main_height // 3

            self.mw.drop_zone_replace.setGeometry(0, 0, main_width, zone_height)

            self.mw.drop_zone_append.setGeometry(
                0, zone_height, main_width, zone_height
            )

            remaining_height = main_height - (zone_height * 2)
            self.mw.drop_zone_library.setGeometry(
                0, zone_height * 2, main_width, remaining_height
            )

            self.mw.drop_zone_replace.show()
            self.mw.drop_zone_append.show()
            self.mw.drop_zone_library.show()

            return

        left_zone_width = 0

        if self.mw.right_panel.isVisible():
            if self.mw.splitter.count() > 0:
                left_zone_width = self.mw.splitter.widget(0).width() + 58
            else:
                left_zone_width = int(main_width * 0.7)
        else:
            left_zone_width = main_width

        self.mw.drop_zone_library.setGeometry(0, 0, left_zone_width, main_height)
        self.mw.drop_zone_library.show()

        right_zone_x = left_zone_width
        right_zone_width = main_width - left_zone_width

        if right_zone_width > 0:
            queue_zone_height = main_height // 2

            self.mw.drop_zone_replace.setGeometry(
                right_zone_x, 0, right_zone_width, queue_zone_height
            )

            self.mw.drop_zone_append.setGeometry(
                right_zone_x,
                queue_zone_height,
                right_zone_width,
                main_height - queue_zone_height,
            )

            self.mw.drop_zone_replace.show()
            self.mw.drop_zone_append.show()
        else:
            self.mw.drop_zone_replace.hide()
            self.mw.drop_zone_append.hide()

    def show_drop_zones(self):
        """
        Makes the drag-and-drop target zones visible over the UI.
        """
        if hasattr(self.mw, "drop_zone_container"):
            self.resize_drop_zones()
            self.mw.drop_zone_container.show()
            self.mw.drop_zone_container.raise_()

    def hide_drop_zones(self):
        """
        Hides the drag-and-drop target zones.
        """
        if hasattr(self.mw, "drop_zone_container"):
            self.mw.drop_zone_container.hide()
        self.mw.active_drop_zone = -1

    def update_active_drop_zone(self, pos):
        """
        Updates visual feedback to indicate which drop zone the cursor is currently hovering over.
        """
        zones = [
            self.mw.drop_zone_library,
            self.mw.drop_zone_append,
            self.mw.drop_zone_replace,
        ]
        new_active_zone = -1

        for i, zone in enumerate(zones):
            if zone.geometry().contains(pos):
                new_active_zone = i
                break

        if new_active_zone != self.mw.active_drop_zone:
            self.mw.active_drop_zone = new_active_zone
            for i, zone in enumerate(zones):
                is_active = i == self.mw.active_drop_zone
                zone.setProperty("active", is_active)
                self.mw.style().unpolish(zone)
                self.mw.style().polish(zone)

    def get_active_drop_zone(self, pos):
        """
        Returns the index of the drop zone corresponding to the specified pointer position.
        """
        zones = [
            self.mw.drop_zone_library,
            self.mw.drop_zone_append,
            self.mw.drop_zone_replace,
        ]
        for i, zone in enumerate(zones):
            if zone.geometry().contains(pos):
                return i
        return -1

    def handle_resize_event(self, event):
        """
        Handles main window resize events, adjusting the drop zones accordingly.
        """
        self.resize_drop_zones()

    def handle_drag_enter_event(self, event):
        """
        Handles when dragged content enters the main window boundaries.
        Shows drop zones if valid URLs are being dragged.
        """
        if event.mimeData().hasUrls():
            self.show_drop_zones()
            event.acceptProposedAction()
        else:
            event.ignore()

    def handle_drag_move_event(self, event):
        """
        Handles pointer movement during a drag operation, updating the active drop zone.
        """
        if event.mimeData().hasUrls():
            self.update_active_drop_zone(event.position().toPoint())
            event.accept()
        else:
            event.ignore()

    def handle_drag_leave_event(self, event):
        """
        Handles when the dragged content leaves the main window boundaries, hiding drop zones.
        """
        self.hide_drop_zones()

    def handle_drop_event(self, event):
        """
        Handles the final drop action, initiating the library addition or queue modification
        based on the target drop zone.
        """
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        target_zone = self.get_active_drop_zone(event.position().toPoint())
        self.hide_drop_zones()

        if target_zone != -1:
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            if target_zone == 0:
                self.mw.action_handler.handle_drop_library(paths)

                if paths:
                    target_path = paths[0]
                    if os.path.isfile(target_path):
                        target_path = os.path.dirname(target_path)

                    try:
                        folder_tab_index = self.mw.nav_button_icon_names.index("folder")

                        self.mw.main_stack.setCurrentIndex(folder_tab_index)

                        for btn in self.mw.nav_buttons:
                            btn.setChecked(False)
                        if folder_tab_index < len(self.mw.nav_buttons):
                            self.mw.nav_buttons[folder_tab_index].setChecked(True)
                        self.mw.ui_manager.update_nav_button_icons()

                        self.mw.ui_manager.navigate_to_directory(target_path)
                    except ValueError:
                        pass

            elif target_zone == 1:
                self.mw.action_handler.handle_drop_add_to_queue(paths)
            elif target_zone == 2:
                self.mw.action_handler.handle_drop_replace_queue(paths)
            event.acceptProposedAction()
        else:
            event.ignore()