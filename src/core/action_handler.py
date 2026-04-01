"""
Vinyller — Actions handler and stats reward
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
import re
import subprocess
import sys
from collections import defaultdict
from urllib.parse import quote

from PyQt6.QtCore import (
    Qt,
    QTimer, QUrl
)
from PyQt6.QtGui import (
    QDesktopServices
)
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog
)
from send2trash import send2trash

from src.core.context_menu_handler import ContextMenuHandler
from src.meta_editor.main_editor import UniversalMetadataEditorDialog
from src.player.player import RepeatMode
from src.ui.custom_dialogs import (
    AddFoldersConfirmDialog, CustomConfirmDialog,
    CustomInputDialog, DeleteWithCheckboxDialog, RemoveFromLibraryDialog, ResetStatsOptionsDialog
)
from src.ui.search_services_tools import AddSearchLinkDialog
from src.utils.constants import (
    HISTORY_LIMIT,
    HISTORY_MIN_S, STATS_AWARD_DELAY_S
)
from src.utils.utils_translator import translate


class PlaybackStatsHandler:
    """
    Handles playback statistics, history logging, and related timers.
    """
    def __init__(self, main_window):
        """
        Initializes the playback stats handler and its timers.

        Args:
            main_window: The main application window instance.
        """
        self.main_window = main_window

        self.stats_award_timer = QTimer(main_window)
        self.stats_award_timer.setSingleShot(True)
        self.stats_award_timer.setInterval(STATS_AWARD_DELAY_S * 1000)
        self.stats_award_timer.timeout.connect(self._award_playback_stats)

        self.pending_track_for_stats = None

        self.history_timer = QTimer(main_window)
        self.history_timer.setSingleShot(True)
        self.history_timer.setInterval(HISTORY_MIN_S * 1000)
        self.history_timer.timeout.connect(self._add_to_history_log)
        self.history_added_for_current_track = False

    def _handle_track_changed(self, artist, title, index):
        """
        Resets timers and tracking states when the current track changes.
        """
        self.stats_award_timer.stop()
        self.history_timer.stop()
        self.pending_track_for_stats = None
        self.history_added_for_current_track = False

    def _handle_playback_state_changed(self, state):
        """
        Handles timer logic based on the player's playback state (playing, paused, stopped).
        Calculates and sets the required listening threshold to award stats for the current track.
        """
        mw = self.main_window

        if state in [
            QMediaPlayer.PlaybackState.PausedState,
            QMediaPlayer.PlaybackState.StoppedState,
        ]:
            self.stats_award_timer.stop()
            self.history_timer.stop()
            self.pending_track_for_stats = None
            return

        if state == QMediaPlayer.PlaybackState.PlayingState:
            player_queue = mw.player.get_current_queue()
            received_index = mw.player.get_current_index()
            if not (0 <= received_index < len(player_queue)):
                return
            if getattr(mw, "is_restoring_queue", False):
                return

            current_track = player_queue[received_index]
            track_path = current_track.get("path")
            if not track_path:
                return

            if (
                    self.pending_track_for_stats
                    and self.pending_track_for_stats.get("path") == track_path
            ):
                return

            self.stats_award_timer.stop()

            total_duration_s = current_track.get("duration", 0)
            if total_duration_s == 0:
                return

            threshold_pct_ms = (total_duration_s * 1000) * mw.STATS_AWARD_PERCENTAGE
            threshold_cap_ms = mw.STATS_AWARD_CAP_S * 1000
            final_threshold_ms = min(threshold_pct_ms, threshold_cap_ms)
            min_threshold_ms = mw.STATS_AWARD_MIN_S * 1000
            if final_threshold_ms < min_threshold_ms:
                final_threshold_ms = min_threshold_ms

            self.pending_track_for_stats = current_track
            self.stats_award_timer.setInterval(int(final_threshold_ms))
            self.stats_award_timer.start()

        if not self.history_added_for_current_track:
            self.history_timer.start()

    def _award_playback_stats(self):
        """
        Awards playback statistics to the current track and its associated entities
        (album, artist, genre, composer) after the listening threshold is met.
        """
        mw = self.main_window
        current_track = self.pending_track_for_stats
        if not current_track:
            return
        track_path = current_track.get("path")
        if not track_path:
            return

        conscious_choice = mw.conscious_choice_data
        mw.conscious_choice_data = None

        conscious_entity_data = None
        conscious_entity_type = None
        if conscious_choice:
            conscious_entity_data, conscious_entity_type = conscious_choice
            if conscious_entity_type not in [
                "track",
                "album",
                "artist",
                "genre",
                "playlist",
                "folder",
                "composer",
            ]:
                conscious_entity_type = None

        mw.library_manager.increment_track_play(
            track_path, mw.collect_statistics, increment_by = 1
        )
        last_played = mw.library_manager.last_played_entity_metadata

        artists_to_credit = set(current_track.get("artists", []))
        if current_track.get("artist"):
            artists_to_credit.add(current_track.get("artist"))
        if current_track.get("album_artist"):
            artists_to_credit.add(current_track.get("album_artist"))

        artists_to_credit.discard("")
        artists_to_credit.discard(None)

        current_genres = set(current_track.get("genre", []))

        current_composers = set()
        if comp_raw := current_track.get("composer"):
            current_composers = {
                c.strip() for c in re.split(r"[;/]", comp_raw) if c.strip()
            }

        if mw.treat_folders_as_unique:
            current_album_key = (
                current_track.get("album_artist"),
                current_track.get("album"),
                os.path.dirname(current_track["path"]),
            )
        else:
            current_album_key = (
                current_track.get("album_artist"),
                current_track.get("album"),
            )

        last_artists = last_played.get("artists_credited", set())
        new_artists_to_credit = artists_to_credit - last_artists

        if conscious_entity_type:
            if conscious_entity_type == "track":
                mw.library_manager.increment_track_play(
                    track_path, mw.collect_statistics, increment_by = 1
                )
            else:
                mw.library_manager.increment_entity_play(
                    conscious_entity_data,
                    conscious_entity_type,
                    mw.collect_statistics,
                    increment_by = 2,
                )

            if current_album_key and current_album_key != last_played.get("album_key"):
                if conscious_entity_type != "album":
                    mw.library_manager.increment_entity_play(
                        current_album_key,
                        "album",
                        mw.collect_statistics,
                        increment_by = 1,
                    )
                last_played["album_key"] = current_album_key

            for artist_name in new_artists_to_credit:
                if artist_name and (conscious_entity_type != "artist" or conscious_entity_data != artist_name):
                    mw.library_manager.increment_entity_play(
                        artist_name,
                        "artist",
                        mw.collect_statistics,
                        increment_by = 1,
                    )
            last_played["artists_credited"] = artists_to_credit

            last_genres = last_played.get("genres", set())
            new_genres_to_add = current_genres - last_genres
            for genre in new_genres_to_add:
                if genre and (conscious_entity_type != "genre" or conscious_entity_data != genre):
                    mw.library_manager.increment_entity_play(
                        genre, "genre", mw.collect_statistics, increment_by = 1
                    )
            last_played["genres"] = current_genres

            last_composers = last_played.get("composers", set())
            new_composers_to_add = current_composers - last_composers

            for comp in new_composers_to_add:
                if comp and (
                        conscious_entity_type != "composer" or conscious_entity_data != comp
                ):
                    mw.library_manager.increment_entity_play(
                        comp, "composer", mw.collect_statistics, increment_by = 1
                    )

            last_played["composers"] = current_composers

        else:
            if current_album_key and current_album_key != last_played.get("album_key"):
                mw.library_manager.increment_entity_play(
                    current_album_key, "album", mw.collect_statistics, increment_by = 1
                )
                last_played["album_key"] = current_album_key

            for artist_name in new_artists_to_credit:
                if artist_name:
                    mw.library_manager.increment_entity_play(
                        artist_name,
                        "artist",
                        mw.collect_statistics,
                        increment_by = 1,
                    )
            last_played["artists_credited"] = artists_to_credit

            last_genres = last_played.get("genres", set())
            new_genres_to_add = current_genres - last_genres
            for genre in new_genres_to_add:
                if genre:
                    mw.library_manager.increment_entity_play(
                        genre, "genre", mw.collect_statistics, increment_by = 1
                    )
            last_played["genres"] = current_genres

            last_composers = last_played.get("composers", set())
            new_composers_to_add = current_composers - last_composers
            for comp in new_composers_to_add:
                if comp:
                    mw.library_manager.increment_entity_play(
                        comp, "composer", mw.collect_statistics, increment_by = 1
                    )
            last_played["composers"] = current_composers

        is_playing_from_history = mw.current_queue_context_data == "playback_history"

        self.pending_track_for_stats = None

    def _add_to_history_log(self):
        """
        Logs the currently playing track to the user's playback history
        after the minimum history time threshold is met.
        """
        mw = self.main_window
        player_queue = mw.player.get_current_queue()
        index = mw.player.get_current_index()
        if not (0 <= index < len(player_queue)):
            return

        current_track = player_queue[index]
        track_path = current_track.get("path")
        if not track_path:
            return

        is_playing_from_history = mw.current_queue_context_data == "playback_history"

        if mw.playback_history_mode != 0 and not is_playing_from_history:
            mw.library_manager.add_track_to_history(
                track_path,
                mw.playback_history_mode,
                store_unique_only = mw.history_store_unique_only,
                history_limit = HISTORY_LIMIT,
            )
            try:
                history_tab_index = mw.nav_button_icon_names.index("history")
                if mw.main_stack.currentIndex() == history_tab_index:
                    mw.ui_manager.populate_history_tab()
            except (ValueError, AttributeError):
                pass

        self.history_added_for_current_track = True


class ActionHandler:
    """
    Central handler for application actions, UI interactions, and contextual menus.
    """
    def __init__(self, main_window):
        """
        Initializes the action handler.

        Args:
            main_window: The main application window instance.
        """
        self.main_window = main_window
        self.context_menu_handler = ContextMenuHandler(main_window, self)
        self.stats_handler = PlaybackStatsHandler(main_window)

    def show_context_menu(self, data, global_pos, is_queue_item=False, context=None):
        """
        Displays a standard context menu for a track, album, or entity.
        """
        self.context_menu_handler.show_context_menu(data, global_pos, is_queue_item, context)

    def show_queue_context_menu(self, pos, source_widget=None):
        """
        Displays the context menu specifically for items currently in the playback queue.
        """
        self.context_menu_handler.show_queue_context_menu(pos, source_widget)

    def show_playlist_card_context_menu(self, playlist_path, global_pos):
        """
        Displays the context menu for a playlist card.
        """
        self.context_menu_handler.show_playlist_card_context_menu(playlist_path, global_pos)

    def show_favorite_tracks_card_context_menu(self, data, global_pos):
        """
        Displays the context menu for a favorite track card.
        """
        self.context_menu_handler.show_favorite_tracks_card_context_menu(data, global_pos)

    def show_favorite_tracks_context_menu(self, data, global_pos):
        """
        Displays the context menu for favorite tracks.
        """
        self.context_menu_handler.show_favorite_tracks_context_menu(data, global_pos)

    def show_lyrics(self, track_data):
        """
        Launches or updates the lyrics display panel for the specified track.
        """
        mw = self.main_window

        player_queue = mw.player.get_current_queue()
        current_index = mw.player.get_current_index()
        current_track_has_lyrics = False

        if 0 <= current_index < len(player_queue):
            current_track = player_queue[current_index]
            if current_track and current_track.get("lyrics"):
                current_track_has_lyrics = True

        mw.control_panel.update_lyrics_toggle_button(
            is_visible = current_track_has_lyrics, is_checked = current_track_has_lyrics
        )

        if mw.vinyl_toggle_button.isChecked():
            mw.right_panel.updateVinylLyricsPage(track_data)
            mw.vinyl_widget.toggle_lyrics_view(True)
        else:
            if not mw.right_panel.isVisible():
                mw.right_panel.show()
                if mw.last_splitter_sizes and sum(mw.last_splitter_sizes) > 0:
                    mw.splitter.setSizes(mw.last_splitter_sizes)
                else:
                    mw.splitter.setSizes(
                        [int(mw.splitter.width() * 0.7), int(mw.splitter.width() * 0.3)]
                    )

                mw.queue_visible = True
                mw.update_queue_toggle_button_ui()

            mw.right_panel.toggleLyricsView(True, track_data)

    def _handle_track_changed(self, artist, title, index):
        """
        Delegates track change events to the playback stats handler.
        """
        self.stats_handler._handle_track_changed(artist, title, index)

    def _handle_playback_state_changed(self, state):
        """
        Delegates playback state change events to the playback stats handler.
        """
        self.stats_handler._handle_playback_state_changed(state)

    def start_library_processing_with_restore(
            self,
            from_cache = False,
            user_initiated = False,
            tracks_to_reprocess = None,
            partial_scan_paths = None,
    ):
        """
        Saves the current queue state, starts library processing, and prepares
        to restore the exact queue state once the scan finishes.
        """
        mw = self.main_window
        current_queue = mw.player.get_current_queue()
        current_index = mw.player.get_current_index()

        current_path = (
            current_queue[current_index]["path"]
            if current_queue and 0 <= current_index < len(current_queue)
            else None
        )

        mw.queue_state_before_soft_reload = {
            "paths": [track["path"] for track in current_queue],
            "current_path": current_path,
            "position": mw.player.player.position(),
            "is_playing": mw.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState,
            "is_shuffled": mw.player.is_shuffled(),
            "repeat_mode": mw.player.get_repeat_mode(),
            "name": getattr(mw, "current_queue_name", None),
            "context": getattr(mw, "current_queue_context_data", None),
            "playlist_path": getattr(mw, "current_queue_context_path", None),
        }

        mw.start_library_processing(
            from_cache = from_cache,
            user_initiated = user_initiated,
            tracks_to_reprocess = tracks_to_reprocess,
            partial_scan_paths = partial_scan_paths,
        )

    def on_scan_finished_restore(self, new_tracks, user_initiated = False):
        """
        Restores the player's queue, playback position, and state after a library scan completes.
        """
        mw = self.main_window
        state = getattr(mw, "queue_state_before_soft_reload", None)
        mw.queue_state_before_soft_reload = None

        if not state:
            return

        current_queue = mw.player.get_current_queue()
        if not current_queue:
            return

        new_tracks_map = {}
        for track in new_tracks:
            if isinstance(track, dict) and "path" in track:
                new_tracks_map[track["path"]] = track
            elif isinstance(track, str):
                if track_data := mw.data_manager.get_track_by_path(track):
                    new_tracks_map[track] = track_data

        updated_queue = [
            new_tracks_map.get(track["path"], track) for track in current_queue
        ]

        current_path = state.get("current_path")
        current_index = 0
        if current_path:
            current_index = next(
                (
                    i
                    for i, t in enumerate(updated_queue)
                    if os.path.normpath(t["path"]) == os.path.normpath(current_path)
                ),
                0,
            )

        mw.player.set_queue(updated_queue, preserve_playback = False)
        mw.player._current_index = current_index

        target_shuffle = state.get("is_shuffled", False)
        if mw.player.is_shuffled() != target_shuffle:
            mw.player.toggle_shuffle()

        rep_mode_value = state.get("repeat_mode", 0)
        if isinstance(rep_mode_value, int):
            try:
                mw.player.set_repeat_mode(RepeatMode(rep_mode_value))
            except ValueError:
                mw.player.set_repeat_mode(RepeatMode.NO_REPEAT)
        else:
            mw.player.set_repeat_mode(rep_mode_value)

        was_playing = state.get("is_playing", False)

        if was_playing:
            track_info = updated_queue[current_index]
            mw.player.currentTrackChanged.emit(
                ", ".join(track_info.get("artists", [translate("Unknown")])),
                track_info.get("title", os.path.basename(track_info.get("path"))),
                current_index,
            )
        else:
            mw.player.play(current_index)
            position = state.get("position", 0)
            if 0 < position:
                mw.player.set_position(position)
            mw.player.pause()

        mw.refresh_current_view()


    def play_next(self, data):
        """
        Inserts tracks from data immediately after the currently playing track in the queue.
        """
        mw = self.main_window
        tracks = mw.data_manager.get_tracks_from_data(
            data,
            mw.library_manager,
            mw.artist_album_sort_mode,
            mw.favorite_tracks_sort_mode,
            mw.favorites,
        )

        if not tracks:
            return

        if not mw.player.get_current_queue():
            self.add_to_queue(data)
            return

        current_index = mw.player.get_current_index()
        insert_index = current_index + 1
        mw.player.insert_tracks(tracks, insert_index)
        print(translate("Inserted {count} tracks to play next.", count = len(tracks)))

    def play_playlist_next(self, playlist_path):
        """
        Loads a playlist and inserts its tracks to play immediately after the current track.
        """
        mw = self.main_window
        tracks = mw.library_manager.load_playlist(
            playlist_path, mw.data_manager.path_to_track_map
        )
        if not tracks:
            print(translate("Could not load tracks from playlist."))
            return
        if not mw.player.get_current_queue():
            self.add_playlist_to_queue(playlist_path)
            return
        current_index = mw.player.get_current_index()
        insert_index = current_index + 1
        mw.player.insert_tracks(tracks, insert_index)
        print(
            translate(
                "Inserted {count} tracks from playlist to play next.", count = len(tracks)
            )
        )

    def search_in_internet(
            self, query, url_pattern = "https://www.google.com/search?q={}"
    ):
        """
        Opens the user's default browser to search the internet for the given query.
        """
        if not query:
            return

        if "{query}" in url_pattern:
            url = url_pattern.format(query = quote(query))
        else:
            url = url_pattern.format(quote(query))

        QDesktopServices.openUrl(QUrl(url))

    def open_add_search_link_dialog(self):
        """
        Opens a dialog to allow the user to add a custom search engine link.
        """
        mw = self.main_window
        dlg = AddSearchLinkDialog(mw)
        if dlg.exec():
            data = dlg.get_data()
            if data:
                mw.library_manager.add_custom_search_link(data["name"], data["url"])

    def handle_remove_from_library_request(self, data, item_type):
        """
        Handles removing items (tracks, albums, folders, etc.) from the library,
        either by blacklisting them or permanently deleting the files from disk.
        """
        mw = self.main_window

        item_name = ""
        item_type_str_map = {
            "track": translate("Track"),
            "album": translate("Album"),
            "artist": translate("Artist"),
            "folder": translate("Folder"),
            "composer": translate("Composer"),
        }
        item_type_str = item_type_str_map.get(item_type, translate("Item"))

        tracks = []
        items_to_check_fav = []

        if item_type == "track":
            if isinstance(data, list):
                if not data:
                    return
                data = data[0]
            item_name = data.get("title", os.path.basename(data.get("path", "")))
            tracks = [data]
            items_to_check_fav.append((data["path"], "track"))

        elif item_type == "album":
            item_name = data[1]
            tracks = mw.data_manager.get_tracks_from_data(
                data,
                mw.library_manager,
                mw.artist_album_sort_mode,
                mw.favorite_tracks_sort_mode,
                mw.favorites,
            )
            items_to_check_fav.append((data, "album"))
            for t in tracks:
                items_to_check_fav.append((t["path"], "track"))

        elif item_type == "artist":
            item_name = data
            tracks = mw.data_manager.get_tracks_from_data(
                {"type": "artist", "data": data},
                mw.library_manager,
                mw.artist_album_sort_mode,
                mw.favorite_tracks_sort_mode,
                mw.favorites,
            )
            items_to_check_fav.append((data, "artist"))
            for t in tracks:
                items_to_check_fav.append((t["path"], "track"))
            if artist_data := mw.data_manager.artists_data.get(data):
                for alb_key in artist_data.get("albums", []):
                    items_to_check_fav.append((tuple(alb_key), "album"))

        elif item_type == "folder":
            item_name = os.path.basename(data)
            tracks = mw.data_manager.get_tracks_from_data(
                data,
                mw.library_manager,
                mw.artist_album_sort_mode,
                mw.favorite_tracks_sort_mode,
                mw.favorites,
            )
            items_to_check_fav.append((data, "folder"))
            for t in tracks:
                items_to_check_fav.append((t["path"], "track"))

        elif item_type == "composer":
            item_name = data
            tracks = mw.data_manager.get_tracks_from_data(
                {"type": "composer", "data": data},
                mw.library_manager,
                mw.artist_album_sort_mode,
                mw.favorite_tracks_sort_mode,
                mw.favorites,
            )
            items_to_check_fav.append((data, "composer"))
            for t in tracks:
                items_to_check_fav.append((t["path"], "track"))

        track_count = len(tracks)
        if track_count == 0:
            print(translate("No tracks found for this item."))
            return

        has_favorites = False
        for i_data, i_type in items_to_check_fav:
            if mw.library_manager.is_favorite(i_data, i_type):
                has_favorites = True
                break

        has_virtual_tracks = any(track.get("is_virtual", False) for track in tracks)

        removal_mode, remove_favs = RemoveFromLibraryDialog.select_removal_mode(
            mw, item_name, track_count, item_type_str,
            has_favorites = has_favorites,
            has_virtual_tracks = has_virtual_tracks
        )

        if not removal_mode:
            return

        if not CustomConfirmDialog.confirm_removal(
                mw, item_name, track_count, item_type_str, removal_mode
        ):
            return

        scroll_attr, scroll_val = mw.ui_manager._capture_current_scroll()

        if remove_favs:
            mw.library_manager.remove_items_from_favorites(items_to_check_fav)
            QTimer.singleShot(
                0, mw.ui_manager.favorites_ui_manager.populate_favorites_tab
            )

        if removal_mode == "blacklist":
            blacklist = mw.library_manager.load_blacklist()
            identifier = None
            if item_type == "track":
                identifier = data["path"]
            elif item_type == "album":
                identifier = list(data)
            elif item_type in ["artist", "folder", "composer"]:
                identifier = data

            list_key = f"{item_type}s"
            if list_key not in blacklist:
                blacklist[list_key] = []
            if identifier and identifier not in blacklist[list_key]:
                blacklist[list_key].append(identifier)

            mw.library_manager.save_blacklist(blacklist)
            print(
                translate(
                    "'{item_name}' added to blacklist. Updating library...",
                    item_name = item_name,
                )
            )


        elif removal_mode == "delete":
            files_to_delete = set()
            cue_files_to_delete = set()

            for track in tracks:
                if track.get("is_virtual", False):
                    real_path = track.get("real_path")

                    if real_path and os.path.exists(real_path):
                        files_to_delete.add(real_path)

                        audio_dir = os.path.dirname(real_path)
                        audio_name = os.path.splitext(os.path.basename(real_path))[0]

                        for file in os.listdir(audio_dir):
                            if file.lower().endswith('.cue'):
                                cue_path = os.path.join(audio_dir, file)
                                try:
                                    with open(cue_path, 'r', encoding = 'utf-8', errors = 'ignore') as f:
                                        content = f.read()
                                        if os.path.basename(real_path) in content or audio_name in content:
                                            cue_files_to_delete.add(cue_path)
                                except:
                                    if os.path.splitext(file)[0] == audio_name:
                                        cue_files_to_delete.add(cue_path)
                else:
                    path = track["path"]
                    if os.path.exists(path):
                        files_to_delete.add(path)

            all_files_to_delete = list(files_to_delete.union(cue_files_to_delete))
            deleted_count = 0
            errors = []

            for path in all_files_to_delete:
                try:
                    send2trash(path)
                    deleted_count += 1
                except Exception as e:
                    errors.append(str(e))

            if errors:
                print(
                    translate(
                        "Successfully deleted: {deleted_count}. Failed to delete: {count}. Updating library...",
                        deleted_count = deleted_count,
                        count = len(errors),
                    )
                )
            else:
                print(
                    translate(
                        "Successfully deleted {count} files. Updating library...",
                        count = deleted_count,
                    )
                )
        paths_to_remove = set()

        for track in tracks:
            if track.get("is_virtual", False):
                real_path = track.get("real_path")
                if real_path:
                    paths_to_remove.update(
                        path for path in mw.data_manager.path_to_track_map.keys()
                        if path.startswith(f"{real_path}::")
                    )
            else:
                paths_to_remove.add(track["path"])

        mw.data_manager.all_tracks = [
            t for t in mw.data_manager.all_tracks if t["path"] not in paths_to_remove
        ]
        mw.library_manager.save_cache(
            mw.music_library_paths, mw.data_manager.all_tracks
        )

        self.start_library_processing_with_restore(
            from_cache = False,
            user_initiated = True,
            tracks_to_reprocess = mw.data_manager.all_tracks,
        )

        mw.ui_manager._schedule_scroll_restore(scroll_attr, scroll_val)

    def handle_reset_stats_request(self, data, item_type):
        """
        Presents a dialog to reset the playback stats (monthly or all-time) for a specific entity.
        """
        mw = self.main_window

        item_name = ""
        item_type_str_map = {
            "track": translate("Track"),
            "album": translate("Album"),
            "artist": translate("Artist"),
            "genre": translate("Genre"),
            "composer": translate("Composer"),
        }
        item_type_str = item_type_str_map.get(item_type, translate("Item"))

        if item_type == "track":
            item_name = data.get("title", os.path.basename(data.get("path", "")))
        elif item_type == "album":
            item_name = data[1]
        elif item_type in ["artist", "genre", "composer"]:
            item_name = data

        if not item_name:
            return

        dialog = ResetStatsOptionsDialog(item_name, item_type_str, mw)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_mode = dialog.get_selected_mode()

        scroll_attr, scroll_val = mw.ui_manager._capture_current_scroll()

        success = mw.library_manager.reset_entity_stats(
            data, item_type, mode = selected_mode
        )

        if success:
            mode_text = "Monthly" if selected_mode == 0 else "All Time"
            print(f"Stats reset ({mode_text}) for {item_type}: {item_name}")
            mw.start_library_processing(from_cache = True, user_initiated = True)
            mw.ui_manager._schedule_scroll_restore(scroll_attr, scroll_val)
        else:
            print(f"Failed to reset stats for {item_type}: {item_name}")

    def add_tracks_to_playlist(self, tracks_to_add: list, playlist_path):
        """
        Appends a list of tracks to an existing local playlist file without duplicating entries.
        """
        mw = self.main_window
        playlist_name = os.path.splitext(os.path.basename(playlist_path))[0]

        existing_tracks = mw.library_manager.load_playlist(
            playlist_path, mw.data_manager.path_to_track_map
        )
        existing_paths = {t["path"] for t in existing_tracks}

        new_tracks_added_count = 0
        for track in tracks_to_add:
            if track["path"] not in existing_paths:
                existing_tracks.append(track)
                existing_paths.add(track["path"])
                new_tracks_added_count += 1

        if new_tracks_added_count == 0:
            if len(tracks_to_add) > 1:
                print(
                    translate(
                        "All tracks are already in playlist '{playlist_name}'",
                        playlist_name=playlist_name,
                    )
                )
            else:
                print(
                    translate(
                        "Track is already in playlist '{playlist_name}'",
                        playlist_name=playlist_name,
                    )
                )
            return

        success, message = mw.library_manager.save_playlist(
            playlist_name, existing_tracks
        )

        if success:
            print(
                translate(
                    "Added {count} track(s) to '{playlist_name}'",
                    count=new_tracks_added_count,
                    playlist_name=playlist_name,
                )
            )

            if mw.current_open_playlist_path == playlist_path:
                mw.ui_manager.show_playlist_tracks(playlist_path)
                mw.playlists_need_refresh = True
            else:
                mw.ui_manager.populate_playlists_tab()
        else:
            print(translate("Error saving: {message}", message=message))

    def create_new_playlist_from_context(self, data):
        """
        Prompts the user for a name and creates a new playlist containing the contextual data.
        """
        mw = self.main_window

        tracks_to_add = []
        if isinstance(data, list):
            tracks_to_add = data
        elif isinstance(data, dict):
            tracks_to_add = [data]

        if not tracks_to_add:
            return

        dialog = CustomInputDialog(
            mw,
            title = translate("Create Playlist"),
            label = translate("Enter playlist title"),
            ok_text = translate("Create"),
            cancel_text = translate("Cancel"),
        )

        try:
            dialog.button_box.accepted.disconnect()
        except TypeError:
            pass

        def attempt_create():
            text = dialog.textValue().strip()
            if not text:
                dialog.show_error(translate("Playlist title cannot be empty."))
                return

            success, message = mw.library_manager.save_playlist(text, tracks_to_add)
            if success:
                print(
                    translate(
                        "Playlist '{text}' created and {count} track(s) added.",
                        text = text,
                        count = len(tracks_to_add),
                    )
                )
                mw.ui_manager.populate_playlists_tab()
                dialog.accept()
            else:
                dialog.show_error(translate("Error creating playlist: {message}", message = message))

        dialog.button_box.accepted.connect(attempt_create)
        dialog.exec()

    def remove_track_from_viewed_playlist(self, playlist_path, index_to_remove):
        """
        Removes a specific track from a playlist by its index and saves the changes.
        """
        mw = self.main_window
        playlist_name = os.path.splitext(os.path.basename(playlist_path))[0]

        tracks = mw.library_manager.load_playlist(
            playlist_path, mw.data_manager.path_to_track_map
        )

        if index_to_remove < 0 or index_to_remove >= len(tracks):
            print(f"Error: Index {index_to_remove} out of range for playlist.")
            return

        removed_track = tracks.pop(index_to_remove)

        success, message = mw.library_manager.save_playlist(
            playlist_name, tracks
        )

        if success:
            track_title = removed_track.get('title', 'Unknown')
            print(translate("Track '{title}' removed from '{playlist_name}'", title=track_title, playlist_name=playlist_name))

            if mw.current_open_playlist_path == playlist_path:
                mw.ui_manager.show_playlist_tracks(playlist_path)
                mw.playlists_need_refresh = True
            else:
                mw.ui_manager.populate_playlists_tab()
        else:
            print(translate("Error saving: {message}", message=message))

    def toggle_current_track_favorite(self):
        """
        Toggles the favorite status of the track currently loaded in the player.
        """
        mw = self.main_window
        player_queue = mw.player.get_current_queue()
        current_index = mw.player.get_current_index()
        if not (0 <= current_index < len(player_queue)):
            return

        current_track = player_queue[current_index]
        self.toggle_favorite(current_track, "track")

    def toggle_favorite(self, data, item_type):
        """
        Toggles the favorite status for a generic entity (track, album, artist, etc.)
        and updates the corresponding UI components.
        """
        mw = self.main_window

        scroll_attr, scroll_val = mw.ui_manager._capture_current_scroll()

        item_data_key = None

        if item_type == "track":
            if isinstance(data, list):
                if not data:
                    return
                data = data[0]
            item_data_key = data["path"]
        elif item_type == "album":
            item_data_key = list(data)
        elif item_type == "artist":
            item_data_key = data
        elif item_type == "folder":
            item_data_key = data
        elif item_type == "playlist":
            item_data_key = data
        elif item_type == "genre":
            item_data_key = data
        elif item_type == "composer":
            item_data_key = data

        if item_data_key is None:
            return

        is_currently_favorite = mw.library_manager.is_favorite(item_data_key, item_type)

        if is_currently_favorite:
            mw.library_manager.remove_from_favorites(item_data_key, item_type)
            print(translate("Removed from favorites"))
        else:
            if item_type == "track":
                track_path = data["path"]
                track_folder = os.path.dirname(track_path)
                is_in_library = any(
                    os.path.abspath(track_folder).startswith(os.path.abspath(lib_path))
                    for lib_path in mw.music_library_paths
                )

                if not is_in_library:
                    confirmed = CustomConfirmDialog.confirm(
                        mw,
                        title = translate("Folder not in library"),
                        label = translate(
                            "The folder for this track is not in the library..."
                        ),
                        ok_text = translate("Add and Update"),
                        cancel_text = translate("Cancel"),
                    )
                    if confirmed:
                        mw.library_manager.add_to_favorites(item_data_key, item_type)
                        if track_folder not in mw.music_library_paths:
                            mw.music_library_paths.append(track_folder)
                            mw.save_current_settings()
                        mw.start_library_processing(
                            from_cache = False, partial_scan_paths = [track_folder]
                        )
                        mw.ui_manager._schedule_scroll_restore(scroll_attr, scroll_val)
                        return
                    else:
                        return

            mw.library_manager.add_to_favorites(item_data_key, item_type)
            print(translate("Added to favorites"))

        mw.favorites = mw.library_manager.load_favorites()
        mw.player_controller.update_favorite_button_ui()

        QTimer.singleShot(0, mw.ui_manager.favorites_ui_manager.populate_favorites_tab)

        try:
            if mw.favorites_stack.currentIndex() > 0:
                context = mw.current_favorites_context
                fav_ui = mw.ui_manager.favorites_ui_manager

                if context == "tracks":
                    QTimer.singleShot(0, fav_ui.show_favorite_tracks_view)
                elif context == "all_albums":
                    QTimer.singleShot(0, fav_ui.show_all_favorite_albums_view)
                elif context == "all_artists":
                    QTimer.singleShot(0, fav_ui.show_all_favorite_artists_view)
                elif context == "all_genres":
                    QTimer.singleShot(0, fav_ui.show_all_favorite_genres_view)
                elif context == "all_composers":
                    QTimer.singleShot(0, fav_ui.show_all_favorite_composers_view)
                elif context == "all_playlists":
                    QTimer.singleShot(0, fav_ui.show_all_favorite_playlists_view)
                elif context == "all_folders":
                    QTimer.singleShot(0, fav_ui.show_all_favorite_folders_view)
        except (ValueError, AttributeError):
            pass

        mw.ui_manager._schedule_scroll_restore(scroll_attr, scroll_val)

    def add_to_queue(self, data):
        """
        Parses tracks from the provided data and appends them to the current player queue.
        Starts playback automatically if the queue was empty and autoplay is enabled.
        """
        mw = self.main_window
        is_queue_empty = len(mw.player.get_current_queue()) == 0

        tracks = mw.data_manager.get_tracks_from_data(
            data,
            mw.library_manager,
            mw.artist_album_sort_mode,
            mw.favorite_tracks_sort_mode,
            mw.favorites,
        )

        if tracks:
            mw.current_queue_name = translate("Playback Queue")
            mw.current_queue_context_path = None
            mw.current_queue_context_data = None
            mw.player.add_to_queue(tracks)
            print(translate("Added tracks: {count}", count = len(tracks)))

            if mw.autoplay_on_queue and is_queue_empty:
                mw.player.play(0)

    def remove_selected_from_queue(self, source_widget=None):
        """
        Removes the currently selected tracks from the queue widget.
        """
        mw = self.main_window
        if source_widget is None or isinstance(source_widget, bool):
            source_widget = mw.right_panel.queue_widget

        if not (selected_items := source_widget.selectedItems()):
            return
        indices_to_remove = sorted(
            [source_widget.row(item) for item in selected_items],
            reverse = True,
        )
        if not indices_to_remove:
            return

        mw.current_queue_name = translate("Playback Queue")
        mw.current_queue_context_path = None
        mw.current_queue_context_data = None
        mw.player.remove_tracks(indices_to_remove)

    def show_in_explorer(self, data):
        """
        Opens the system's file explorer and highlights the file/directory
        associated with the passed data (track, album, playlist, etc.).
        """
        mw = self.main_window
        path = ""

        if isinstance(data, list):
            if not data:
                return
            data = data[0]

        if isinstance(data, dict):
            path = data.get("real_path", data.get("path"))

        elif isinstance(data, str):
            if os.path.exists(data):
                path = data
            elif "::" in data:
                path = data.split("::")[0]
            else:
                tracks = mw.data_manager.get_tracks_from_data(
                    data,
                    mw.library_manager,
                    mw.artist_album_sort_mode,
                    mw.favorite_tracks_sort_mode,
                    mw.favorites,
                )
                if tracks:
                    path = tracks[0].get("real_path", tracks[0].get("path"))

        elif isinstance(data, tuple):
            tracks = mw.data_manager.get_tracks_from_data(
                data,
                mw.library_manager,
                mw.artist_album_sort_mode,
                mw.favorite_tracks_sort_mode,
                mw.favorites,
            )
            if tracks:
                path = tracks[0].get("real_path", tracks[0].get("path"))

        if isinstance(path, str) and "::" in path:
            path = path.split("::")[0]

        if not path or not os.path.exists(path):
            print(translate("Could not determine path."))
            return

        is_playlist_file = isinstance(data, str) and data.lower().endswith(
            (".m3u", ".m3u8")
        )

        if is_playlist_file:
            target_path = os.path.dirname(path)
            is_file_to_select = False
        elif os.path.isfile(path):
            target_path = path
            is_file_to_select = True
        else:
            target_path = path
            is_file_to_select = False

        try:
            norm_target_path = os.path.normpath(target_path)
            if sys.platform == "win32":
                if is_file_to_select:
                    subprocess.run(["explorer", "/select,", norm_target_path])
                else:
                    subprocess.run(["explorer", norm_target_path])
            elif sys.platform == "darwin":
                if is_file_to_select:
                    subprocess.run(["open", "-R", norm_target_path])
                else:
                    subprocess.run(["open", norm_target_path])
            else:
                if is_file_to_select:
                    subprocess.run(["xdg-open", os.path.dirname(norm_target_path)])
                else:
                    subprocess.run(["xdg-open", norm_target_path])
        except Exception as e:
            print(translate("Error opening explorer: {e}", e = e))

    def handle_tracks_dropped(self, data_list, drop_index):
        """
        Handles drag-and-drop events inside the application, inserting the dropped
        data into the queue at the specified drop index.
        """
        mw = self.main_window
        all_tracks_to_add = []
        for data_str in data_list:
            try:
                mime_type, data = data_str.split(":", 1)
                tracks_to_add = []

                if mime_type == "track":
                    if track_obj := mw.data_manager.get_track_by_path(data):
                        tracks_to_add = [track_obj]
                    elif os.path.exists(data):
                        metadata = mw.library_manager.get_track_metadata(data)
                        if metadata:
                            metadata["path"] = os.path.abspath(data)
                            tracks_to_add = [metadata]

                elif mime_type in [
                    "artist",
                    "album",
                    "album_extended",
                    "playlist",
                    "folder",
                ]:
                    context_data = data

                    if mime_type == "album":
                        artist, title = data.split("|", 1)
                        context_data = (artist, title)

                    elif mime_type == "album_extended":
                        try:
                            context_data = tuple(json.loads(data))
                        except Exception as e:
                            print(f"Error decoding album drop data: {e}")
                            continue

                    tracks_to_add = mw.data_manager.get_tracks_from_data(
                        context_data,
                        mw.library_manager,
                        mw.artist_album_sort_mode,
                        mw.favorite_tracks_sort_mode,
                        mw.favorites,
                    )

                if tracks_to_add:
                    all_tracks_to_add.extend(tracks_to_add)
            except ValueError:
                print(
                    translate(
                        "Could not parse dropped data: {data_str}", data_str = data_str
                    )
                )

        if all_tracks_to_add:
            mw.current_queue_name = translate("Playback Queue")
            mw.current_queue_context_path = None
            mw.current_queue_context_data = None
            mw.player.insert_tracks(all_tracks_to_add, drop_index)
            print(translate("Added tracks: {count}", count = len(all_tracks_to_add)))

    def handle_queue_reordered(self, source_widget=None):
        """
        Syncs the internal player queue list when the user visually reorders items
        in the UI queue widget.
        """
        mw = self.main_window
        if source_widget is None or isinstance(source_widget, bool):
            source_widget = mw.right_panel.queue_widget

        mw.current_queue_name = translate("Playback Queue")
        mw.current_queue_context_path, mw.current_queue_context_data = None, None
        new_track_order = [
            source_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(source_widget.count())
        ]
        mw.current_ui_queue = new_track_order
        mw.player.set_queue(new_track_order, preserve_playback = True, silent = True)
        mw.ui_manager.update_all_track_widgets()

    def open_metadata_editor(self, data):
        """
        Launches the universal metadata editor dialog for the provided entity data.
        """
        mw = self.main_window

        tracks_to_edit = mw.data_manager.get_tracks_from_data(
            data,
            mw.library_manager,
            mw.artist_album_sort_mode,
            mw.favorite_tracks_sort_mode,
            mw.favorites,
        )

        unique_tracks = {}
        if tracks_to_edit:
            for t in tracks_to_edit:
                if isinstance(t, dict) and "path" in t:
                    unique_tracks[t["path"]] = t
            tracks_to_edit = list(unique_tracks.values())

        if not tracks_to_edit:
            print(translate("No tracks selected for editing."))
            return

        dialog = UniversalMetadataEditorDialog(tracks_to_edit, mw)
        mw.active_metadata_dialog = dialog
        dialog.save_requested.connect(self._handle_universal_metadata_save)
        dialog.exec()
        mw.active_metadata_dialog = None

    def _handle_universal_metadata_save(self, results, is_fast_save):
        """
        Unified metadata save handler that applies the chosen tags to the physical files
        and schedules necessary library updates.
        """
        mw = self.main_window

        scroll_attr, scroll_val = mw.ui_manager._capture_current_scroll()

        all_changed_paths = set()

        paths = list(results.keys())
        if paths:
            first_track = mw.data_manager.get_track_by_path(paths[0])
            old_album_key = None
            is_consistent_album = True

            if first_track:
                aa = first_track.get("album_artist") or first_track.get("artist")
                alb = first_track.get("album")
                yr = first_track.get("year", 0)

                if mw.treat_folders_as_unique:
                    old_album_key = (aa, alb, yr, os.path.dirname(first_track["path"]))
                else:
                    old_album_key = (aa, alb, yr)

                for p in paths[1:]:
                    t = mw.data_manager.get_track_by_path(p)
                    if not t:
                        continue
                    curr_aa = t.get("album_artist") or t.get("artist")
                    curr_alb = t.get("album")
                    curr_yr = t.get("year", 0)

                    curr_key = (
                        (curr_aa, curr_alb, curr_yr, os.path.dirname(t["path"]))
                        if mw.treat_folders_as_unique
                        else (curr_aa, curr_alb, curr_yr)
                    )

                    if curr_key != old_album_key:
                        is_consistent_album = False
                        break

            new_album_key = None
            if is_consistent_album and old_album_key:
                new_tags = results[paths[0]]
                new_alb = new_tags.get("album") or first_track.get("album")
                new_aa_tag = new_tags.get("albumartist")
                if not new_aa_tag:
                    if "artist" in new_tags and not first_track.get("album_artist"):
                        new_aa_tag = new_tags.get("artist")
                    else:
                        new_aa_tag = first_track.get("album_artist") or first_track.get(
                            "artist"
                        )

                new_yr = old_album_key[2]

                if mw.treat_folders_as_unique:
                    new_album_key = (
                        new_aa_tag,
                        new_alb,
                        new_yr,
                        os.path.dirname(first_track["path"]),
                    )
                else:
                    new_album_key = (new_aa_tag, new_alb, new_yr)

                if new_album_key != old_album_key:
                    mw.library_manager.migrate_entity_keys(
                        old_album_key, new_album_key, "album"
                    )
                    view_state = mw.current_view_state
                    context_data = view_state.get("context_data", {})
                    if "album_key" in context_data:
                        current_view_key = tuple(context_data["album_key"])
                        if current_view_key == old_album_key:
                            print(
                                f"Updating view state from {old_album_key} to {new_album_key}"
                            )
                            context_data["album_key"] = list(new_album_key)
                            mw.current_view_state["context_data"] = context_data
                            if context_data.get("artist_name") == old_album_key[0]:
                                context_data["artist_name"] = new_album_key[0]
                    if mw.current_queue_context_data == old_album_key:
                        mw.current_queue_context_data = new_album_key
                        mw.current_queue_name = new_album_key[1]
                        mw.ui_manager.update_queue_header()

        try:
            for path, tags in results.items():
                track_data = mw.data_manager.get_track_by_path(path)
                if not track_data:
                    track_data = {"path": path}

                changed = mw.library_manager.save_metadata_for_tracks(
                    [track_data], tags
                )
                all_changed_paths.update(changed)

        except Exception as e:
            print(f"Error during save: {e}")

        if not all_changed_paths:
            if mw.active_metadata_dialog:
                mw.active_metadata_dialog.force_close()
            return

        if is_fast_save:
            self._update_data_manager_in_memory(list(all_changed_paths))

            mw.pending_metadata_updates.update(all_changed_paths)
            mw.pending_metadata_items_count = len(mw.pending_metadata_updates)
            mw.library_manager.save_pending_updates(list(mw.pending_metadata_updates))

            mw._update_pending_updates_widget()

            if mw.active_metadata_dialog:
                mw.active_metadata_dialog.force_close()
        else:
            self._handle_metadata_saved(list(all_changed_paths))

        mw.ui_manager._schedule_scroll_restore(scroll_attr, scroll_val)

    def _update_data_manager_in_memory(self, changed_paths):
        """
        Partially updates the DataManager's in-memory track list after a fast save.
        Avoids a full library scan to keep UI responsive.
        """
        mw = self.main_window
        print(
            translate(
                "Fast save: updating {count} track(s) in memory...",
                count = len(changed_paths),
            )
        )

        for path in changed_paths:
            new_track_data = mw.library_manager.get_track_metadata(path)
            new_track_data["path"] = os.path.abspath(path)

            if path in mw.data_manager.path_to_track_map:
                try:
                    old_index = next(
                        i
                        for i, t in enumerate(mw.data_manager.all_tracks)
                        if t["path"] == path
                    )
                    mw.data_manager.all_tracks[old_index] = new_track_data
                except StopIteration:
                    mw.data_manager.all_tracks.append(new_track_data)
            else:
                mw.data_manager.all_tracks.append(new_track_data)

            mw.data_manager.path_to_track_map[path] = new_track_data

        mw.library_manager.save_cache(
            mw.music_library_paths, mw.data_manager.all_tracks
        )

    def _handle_metadata_saved(self, changed_paths):
        """
        Handles the full library update AFTER metadata has been formally saved.
        """
        mw = self.main_window
        print(translate("Updating data for {count} track(s)", count = len(changed_paths)))

        self._update_data_manager_in_memory(changed_paths)

        self.start_library_processing_with_restore(
            from_cache = False,
            user_initiated = True,
            tracks_to_reprocess = self.main_window.data_manager.all_tracks,
        )

    def save_playlist(self):
        """
        Prompts the user to save the current playback queue as a new playlist file.
        """
        mw = self.main_window
        if not mw.current_ui_queue:
            print(translate("Playlist is empty, nothing to save."))
            return

        suggested_name = mw.current_queue_name if mw.current_queue_context_path else ""

        dialog = CustomInputDialog(
            mw,
            title = translate("Save Playlist"),
            label = translate("Enter file name"),
            text = suggested_name,
            ok_text = translate("Save"),
            cancel_text = translate("Cancel"),
        )

        try:
            dialog.button_box.accepted.disconnect()
        except TypeError:
            pass

        def attempt_save():
            text = dialog.textValue().strip()
            if not text:
                dialog.show_error(translate("Playlist title cannot be empty."))
                return

            success, message = mw.library_manager.save_playlist(
                text, mw.current_ui_queue
            )
            if success:
                print(translate("Playlist saved: {message}", message = message))
                mw.ui_manager.populate_playlists_tab()
                mw.current_queue_context_path = message
                mw.current_queue_name = os.path.splitext(os.path.basename(message))[0]
                mw.ui_manager.update_queue_header()
                dialog.accept()
            else:
                dialog.show_error(translate("Error saving: {message}", message = message))

        dialog.button_box.accepted.connect(attempt_save)
        dialog.exec()

    def create_mixtape_from_data(self, data, name_suggestion):
        """
        Creates a new mixtape (copies files into a target directory) based on the supplied data.
        """
        mw = self.main_window
        tracks = mw.data_manager.get_tracks_from_data(
            data,
            mw.library_manager,
            mw.artist_album_sort_mode,
            mw.favorite_tracks_sort_mode,
            mw.favorites,
        )
        if not tracks:
            print(translate("No tracks to create mixtape."))
            return

        target_dir = QFileDialog.getExistingDirectory(
            mw, translate("Select folder to save mixtape")
        )
        if not target_dir:
            return

        success, message, created_folder_path = mw.library_manager.create_mixtape(
            name_suggestion, tracks, target_dir
        )

        print(message)

        if success and created_folder_path:
            try:
                if sys.platform == "win32":
                    os.startfile(created_folder_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", created_folder_path])
                else:
                    subprocess.run(["xdg-open", created_folder_path])
            except Exception as e:
                print(translate("Mixtape created, but could not open folder: {e}", e = e))

    def add_playlist_to_queue(self, playlist_path):
        """
        Loads the specified playlist and appends all its tracks to the current queue.
        """
        mw = self.main_window
        is_queue_empty = len(mw.player.get_current_queue()) == 0

        if tracks := mw.library_manager.load_playlist(
                playlist_path, mw.data_manager.path_to_track_map
        ):
            mw.current_queue_name = translate("Playback Queue")
            mw.current_queue_context_path = None
            mw.current_queue_context_data = None
            mw.player.add_to_queue(tracks)
            print(translate("Added {count} tracks from playlist.", count = len(tracks)))

            if mw.autoplay_on_queue and is_queue_empty:
                mw.player.play(0)
        else:
            print(translate("Could not load tracks from playlist."))

    def delete_playlist(self, playlist_path = None):
        """
        Deletes the specified playlist file from the system after user confirmation.
        """
        mw = self.main_window
        if playlist_path is None:
            if not mw.current_queue_context_path:
                return
            playlist_path = mw.current_queue_context_path

        playlist_name = os.path.basename(playlist_path)

        is_fav = mw.library_manager.is_favorite(playlist_path, "playlist")
        remove_from_favs = False

        if is_fav:
            confirmed, remove_from_favs = DeleteWithCheckboxDialog.confirm(
                mw,
                title = translate("Delete Playlist"),
                label = translate(
                    "Are you sure you want to delete playlist '{playlist_name}'?",
                    playlist_name = playlist_name,
                ),
                checkbox_text = translate("Also remove from favorites"),
                ok_text = translate("Delete"),
                cancel_text = translate("Cancel"),
                checkbox_checked_by_default = True,
            )
        else:
            confirmed = CustomConfirmDialog.confirm(
                mw,
                title = translate("Delete Playlist"),
                label = translate(
                    "Are you sure you want to delete playlist '{playlist_name}'?",
                    playlist_name = playlist_name,
                ),
                ok_text = translate("Delete"),
                cancel_text = translate("Cancel"),
            )

        if confirmed:
            if remove_from_favs:
                mw.library_manager.remove_from_favorites(playlist_path, "playlist")
                mw.ui_manager.favorites_ui_manager.populate_favorites_tab()

            is_current_playlist = mw.current_queue_context_path == playlist_path
            success, message = mw.library_manager.delete_playlist(playlist_path)
            print(message)
            if success:
                mw.ui_manager.populate_playlists_tab()
                if is_current_playlist:
                    self.clear_queue()

    def clear_queue(self):
        """
        Empties the player's current queue and resets associated queue metadata.
        """
        mw = self.main_window
        (
            mw.current_queue_name,
            mw.current_queue_context_path,
            mw.current_queue_context_data,
        ) = (translate("Playback Queue"), None, None)
        mw.player.set_queue([])

    def handle_artist_artwork_changed(self, artist_name, new_artwork_path):
        """
        Updates the stored artwork path for a specific artist and triggers a library reprocess.
        """
        mw = self.main_window
        mw.artist_artworks[artist_name] = new_artwork_path
        mw.library_manager.save_artist_artworks(mw.artist_artworks)
        self._trigger_soft_reprocess()

    def handle_genre_artwork_changed(self, genre_name, new_artwork_path):
        """
        Updates the stored artwork path for a specific genre and triggers a library reprocess.
        """
        mw = self.main_window
        mw.genre_artworks[genre_name] = new_artwork_path
        mw.library_manager.save_genre_artworks(mw.genre_artworks)
        self._trigger_soft_reprocess()

    def handle_composer_artwork_changed(self, composer_name, new_artwork_path):
        """
        Updates the stored artwork path for a specific composer and triggers a library reprocess.
        """
        mw = self.main_window
        mw.composer_artworks[composer_name] = new_artwork_path
        mw.library_manager.save_composer_artworks(mw.composer_artworks)
        self._trigger_soft_reprocess()

    def _trigger_soft_reprocess(self):
        """
        Triggers a non-destructive library scan to apply artwork or cache changes without full re-indexing.
        """
        self.start_library_processing_with_restore(
            from_cache = False,
            user_initiated = True,
            tracks_to_reprocess = self.main_window.data_manager.all_tracks,
        )

    def handle_drop_get_tracks(self, paths):
        """
        Scans external dropped paths (files/folders) and returns a list of viable audio tracks.
        """
        mw = self.main_window
        new_queue = []
        supported_formats = mw.library_manager.supported_formats
        playlist_formats = (".m3u", ".m3u8")

        print(translate("Processing dragged files..."))
        QApplication.processEvents()

        for path in paths:
            path = os.path.abspath(path)
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.lower().endswith(supported_formats):
                            full_path = os.path.join(root, file)
                            if track_data := mw.data_manager.get_track_by_path(
                                    full_path
                            ):
                                new_queue.append(track_data)
                            else:
                                metadata = mw.library_manager.get_track_metadata(
                                    full_path
                                )
                                metadata["path"] = os.path.abspath(full_path)
                                new_queue.append(metadata)
            elif os.path.isfile(path):
                if path.lower().endswith(supported_formats):
                    if track_data := mw.data_manager.get_track_by_path(path):
                        new_queue.append(track_data)
                    else:
                        metadata = mw.library_manager.get_track_metadata(path)
                        metadata["path"] = os.path.abspath(path)
                        new_queue.append(metadata)
                elif path.lower().endswith(playlist_formats):
                    tracks_from_playlist = mw.library_manager.load_playlist(
                        path, mw.data_manager.path_to_track_map
                    )
                    new_queue.extend(tracks_from_playlist)

        new_queue.sort(key = lambda t: t["path"])
        return new_queue

    def handle_drop_replace_queue(self, paths):
        """
        Replaces the current player queue completely with the externally dropped tracks.
        """
        mw = self.main_window
        new_queue = self.handle_drop_get_tracks(paths)
        if new_queue:
            mw.library_manager.reset_last_played_entity_metadata()

            mw.current_queue_context_path = None
            dropped_item_name = os.path.basename(paths[0])
            mw.current_queue_name = (
                dropped_item_name if len(paths) == 1 else translate("Dragged Tracks")
            )
            mw.current_queue_context_data = paths[0] if len(paths) == 1 else paths

            mw.player.set_queue(new_queue)

            if mw.autoplay_on_queue:
                mw.player.play(0)
                print(translate("Playing {count} track(s).", count = len(new_queue)))
            else:
                mw.player.play(0, pause = True)
                print(
                    translate(
                        "Queue replaced with {count} track(s).", count = len(new_queue)
                    )
                )
        else:
            print(translate("No supported audio files found."))

    def handle_drop_add_to_queue(self, paths):
        """
        Appends externally dropped files to the end of the current player queue.
        """
        tracks_to_add = self.handle_drop_get_tracks(paths)
        if tracks_to_add:
            self.add_to_queue(tracks_to_add)
        else:
            print(translate("No supported audio files found."))

    def handle_drop_library(self, paths):
        """
        Processes dropped directories or files to be integrated as permanent library paths or imported playlists.
        """
        mw = self.main_window
        new_library_paths = set()
        playlist_paths_to_import = []

        for path in paths:
            path = os.path.abspath(path)
            if path.lower().endswith((".m3u", ".m3u8")):
                playlist_paths_to_import.append(path)
            elif os.path.isdir(path):
                new_library_paths.add(path)
            elif os.path.isfile(path):
                new_library_paths.add(os.path.dirname(path))

        current_paths_set = set(mw.music_library_paths)
        added_paths_count = 0
        paths_to_scan = []
        for new_path in new_library_paths:
            if new_path not in current_paths_set:
                mw.music_library_paths.append(new_path)
                paths_to_scan.append(new_path)
                added_paths_count += 1

        if added_paths_count > 0:
            print(
                translate(
                    "Added {count} new folders. Scanning...", count = added_paths_count
                )
            )
            mw.save_current_settings()
            self.start_library_processing_with_restore(
                from_cache = False, partial_scan_paths = paths_to_scan
            )
        elif not playlist_paths_to_import:
            print(translate("All dragged folders are already in the library."))

        if playlist_paths_to_import:
            imported_count = 0
            for p_path in playlist_paths_to_import:
                success, message = mw.library_manager.import_playlist(p_path)
                if success:
                    imported_count += 1
            if imported_count > 0:
                print(translate("Imported {count} playlists.", count = imported_count))
                mw.ui_manager.populate_playlists_tab()
            elif added_paths_count == 0:
                print(translate("Failed to import playlists."))

    def has_music_files(self, path):
        """
        Determines if a given path contains any music files currently registered in the database.
        """
        mw = self.main_window
        norm_path = os.path.normpath(path)
        path_with_sep = norm_path + os.path.sep
        for track_path in mw.data_manager.path_to_track_map:
            if os.path.normpath(track_path).startswith(path_with_sep):
                return True
        return False

    def _is_safe_path(self, path):
        """
        Verifies if a path is safe to index (avoids indexing the entire hard drive or root directories).
        """
        path = os.path.abspath(path)
        drive, tail = os.path.splitdrive(path)

        if path == os.path.abspath(os.sep) or path == (drive + os.sep):
            return False

        user_home = os.path.abspath(os.path.expanduser("~"))
        if path == user_home:
            return False

        if path == os.path.dirname(user_home):
            return False

        downloads_path = os.path.join(user_home, "Downloads")
        if path == downloads_path:
            return False

        return True

    def _optimize_folder_list(self, folders):
        """
        Optimizes a list of folders by finding safe common root paths to reduce redundancy.
        """
        if not folders:
            return []

        drives_map = defaultdict(list)
        for f in folders:
            drive, _ = os.path.splitdrive(f)
            drives_map[drive].append(f)

        optimized_result = []

        for drive, paths in drives_map.items():
            try:
                common = os.path.commonpath(paths)
                if self._is_safe_path(common):
                    optimized_result.append(common)
                else:
                    optimized_result.extend(paths)
            except ValueError:
                optimized_result.extend(paths)

        return sorted(list(set(optimized_result)))

    def get_missing_folders_from_playlist(self, playlist_path):
        """
        Analyzes a playlist file and identifies any folder paths within it that are not yet part of the library.
        """
        mw = self.main_window
        raw_missing_folders = set()
        existing_roots = [
            os.path.normpath(os.path.abspath(p)) for p in mw.music_library_paths
        ]
        playlist_dir = os.path.dirname(os.path.abspath(playlist_path))

        try:
            with open(playlist_path, "r", encoding = "utf-8") as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if os.path.isabs(line):
                    file_path = os.path.normpath(line)
                else:
                    file_path = os.path.normpath(os.path.join(playlist_dir, line))

                if not os.path.exists(file_path):
                    continue

                track_folder = os.path.dirname(file_path)
                is_covered = False
                for root in existing_roots:
                    try:
                        if os.path.commonpath([root, track_folder]) == root:
                            is_covered = True
                            break
                    except ValueError:
                        continue

                if not is_covered:
                    raw_missing_folders.add(track_folder)

            return self._optimize_folder_list(list(raw_missing_folders))

        except Exception as e:
            print(f"Error analyzing playlist folders: {e}")
            return []

    def add_playlist_sources_to_library(self, raw_folders_list):
        """
        Prompts the user to permanently add the raw folders to the music library paths.
        """
        mw = self.main_window
        if not raw_folders_list:
            return

        optimized_list = self._optimize_folder_list(raw_folders_list)
        dialog = AddFoldersConfirmDialog(raw_folders_list, optimized_list, mw)

        if dialog.exec():
            folders_to_add = dialog.get_selected_folders()
            added_count = 0
            for folder in folders_to_add:
                if folder not in mw.music_library_paths:
                    mw.music_library_paths.append(folder)
                    added_count += 1

            if added_count > 0:
                mw.save_current_settings()
                print(
                    translate(
                        "Adding {count} folders and scanning...", count = added_count
                    )
                )
                mw.library_manager.playlists_metadata.clear()
                self.start_library_processing_with_restore(
                    from_cache = False,
                    user_initiated = True,
                    partial_scan_paths = folders_to_add,
                )

    def rename_playlist_dialog(self, playlist_path):
        """
        Presents a dialog allowing the user to rename a given playlist.
        """
        mw = self.main_window
        current_name = os.path.splitext(os.path.basename(playlist_path))[0]

        dialog = CustomInputDialog(
            mw,
            title = translate("Rename Playlist"),
            label = translate("Enter playlist title"),
            text = current_name,
            ok_text = translate("Rename"),
            cancel_text = translate("Cancel"),
        )

        try:
            dialog.button_box.accepted.disconnect()
        except TypeError:
            pass

        def attempt_rename():
            text = dialog.textValue().strip()
            if not text:
                dialog.show_error(translate("Playlist title cannot be empty."))
                return
            if text == current_name:
                dialog.accept()
                return

            success, message, new_path = mw.library_manager.rename_playlist(
                playlist_path, text
            )

            if success:
                self._on_playlist_renamed_success(playlist_path, new_path, text)
                dialog.accept()
            else:
                if message == "EXISTS":
                    dialog.show_error(
                        translate("A playlist with this name already exists.")
                    )
                else:
                    dialog.show_error(translate("Error: {message}", message = message))

        dialog.button_box.accepted.connect(attempt_rename)
        dialog.exec()

    def _on_playlist_renamed_success(self, old_path, new_path, new_name):
        """
        Updates UI state and contextual paths following a successful playlist rename operation.
        """
        mw = self.main_window
        if mw.current_open_playlist_path == old_path:
            mw.current_open_playlist_path = new_path
            if mw.current_queue_context_path == old_path:
                mw.current_queue_context_path = new_path
                mw.current_queue_name = new_name
                mw.ui_manager.update_queue_header()
            mw.ui_manager.show_playlist_tracks(new_path)

        if mw.library_manager.is_favorite(old_path, "playlist"):
            mw.library_manager.remove_from_favorites(old_path, "playlist")
            mw.library_manager.add_to_favorites(new_path, "playlist")
            mw.ui_manager.favorites_ui_manager.populate_favorites_tab()

        mw.ui_manager.populate_playlists_tab()

    def handle_shake_queue(self):
        """
        Shuffles the current queue while maintaining the currently playing track
        at the top of the new arrangement.
        """
        mw = self.main_window
        queue = mw.player.get_current_queue()
        if len(queue) < 2:
            return

        current_index = mw.player.get_current_index()
        current_track = None
        if 0 <= current_index < len(queue):
            current_track = queue[current_index]

        tracks_to_shuffle = []

        queue_with_indices = []
        for i, t in enumerate(queue):
            if "__original_index" not in t:
                queue_with_indices.append(dict(t, **{"__original_index": i}))
            else:
                queue_with_indices.append(t)

        if current_track:
            current_track = queue_with_indices[current_index]
            tracks_to_shuffle = [
                t for i, t in enumerate(queue_with_indices) if i != current_index
            ]
        else:
            tracks_to_shuffle = list(queue_with_indices)

        random.shuffle(tracks_to_shuffle)

        new_queue = []
        if current_track:
            new_queue.append(current_track)
            new_queue.extend(tracks_to_shuffle)
        else:
            new_queue = tracks_to_shuffle

        mw.current_queue_name = translate("Shuffled Queue")

        was_playing = (
                mw.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState
        )
        current_pos = mw.player.player.position()

        mw.player.set_queue(new_queue, preserve_playback = False, silent = True)

        if current_track:
            mw.player.play(0)
            if current_pos > 0:
                mw.player.set_position(current_pos)

            if not was_playing:
                mw.player.pause()

        mw.ui_manager.update_queue_header()
        mw.player_controller.on_queue_changed()
        print(translate("Queue shaken!"))


