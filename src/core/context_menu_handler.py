"""
Vinyller — Context menu handler
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
import re
from functools import partial

from PyQt6.QtCore import (
    QModelIndex, QSize, Qt
)
from PyQt6.QtGui import (
    QAction, QIcon
)
from PyQt6.QtWidgets import (
    QApplication
)

from src.ui.custom_base_widgets import (
    TranslucentMenu
)
from src.ui.custom_cards import (
    CardWidget
)
from src.ui.custom_lists import (
    QueueWidget, TrackListWidget
)
from src.utils import theme
from src.utils.constants import (
    ArtistSource
)
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


class ContextMenuHandler:
    """
    Handles the creation and displaying of all context menus.
    Delegates the actual actions back to ActionHandler.
    """
    def __init__(self, main_window, action_handler):
        """
        Initializes the context menu handler.

        Args:
            main_window: The main application window instance.
            action_handler: The ActionHandler instance to delegate menu actions to.
        """
        self.main_window = main_window
        self.action_handler = action_handler

    def _get_common_artists(self, tracks_list):
        """
        Finds and returns a sorted list of artists that are common to all tracks in the provided list.
        """
        if not tracks_list:
            return []
        first_track_artists = set(
            artist for artist in tracks_list[0].get("artists", []) if artist
        )
        common_set = first_track_artists
        for track in tracks_list[1:]:
            track_artists = set(artist for artist in track.get("artists", []) if artist)
            common_set.intersection_update(track_artists)
            if not common_set:
                return []
        return sorted(list(common_set))

    def _get_common_album_key(self, tracks_list):
        """
        Checks if all tracks in the list belong to the same album and returns the common album key.
        Returns None if the tracks belong to different albums.
        """
        mw = self.main_window
        if not tracks_list:
            return None
        first_track = tracks_list[0]
        album_artist = first_track.get("album_artist")
        album_title = first_track.get("album")
        year = first_track.get("year", 0)

        if (
                not album_artist
                or not album_title
                or album_title == translate("Unknown Album")
        ):
            return None

        if mw.treat_folders_as_unique:
            common_key = (
                album_artist,
                album_title,
                year,
                os.path.dirname(first_track["path"]),
            )
        else:
            common_key = (album_artist, album_title, year)

        for track in tracks_list[1:]:
            current_artist = track.get("album_artist")
            current_title = track.get("album")
            current_year = track.get("year", 0)

            if mw.treat_folders_as_unique:
                current_key = (
                    current_artist,
                    current_title,
                    current_year,
                    os.path.dirname(track["path"]),
                )
            else:
                current_key = (current_artist, current_title, current_year)

            if current_key != common_key:
                return None
        return common_key

    def _get_common_composers(self, tracks_list):
        """
        Finds and returns a sorted list of composers that are common to all tracks in the provided list.
        """
        if not tracks_list:
            return []
        first_comp_raw = tracks_list[0].get("composer", "")
        if not first_comp_raw:
            return []
        common_set = set(
            c.strip() for c in re.split(r"[;/]", first_comp_raw) if c.strip()
        )
        for track in tracks_list[1:]:
            comp_raw = track.get("composer", "")
            track_composers = set(
                c.strip() for c in re.split(r"[;/]", comp_raw) if c.strip()
            )
            common_set.intersection_update(track_composers)
            if not common_set:
                return []
        return sorted(list(common_set))

    def _get_common_genres(self, tracks_list):
        """
        Finds and returns a sorted list of genres that are common to all tracks in the provided list.
        """
        if not tracks_list:
            return []
        common_set = None
        start_index = 0
        for i, track in enumerate(tracks_list):
            track_genres = set(g for g in track.get("genre", []) if g)
            if track_genres:
                common_set = track_genres
                start_index = i + 1
                break
        if common_set is None:
            return []
        for track in tracks_list[start_index:]:
            track_genres = set(g for g in track.get("genre", []) if g)
            common_set.intersection_update(track_genres)
            if not common_set:
                return []
        return sorted(list(common_set))

    def _navigate_to_composer_safe(self, composer_name):
        """
        Safely navigates the application UI to the specified composer's view.
        """
        mw = self.main_window
        if hasattr(mw.ui_manager, "navigate_to_composer"):
            mw.ui_manager.navigate_to_composer(composer_name)
        else:
            try:
                composer_idx = mw.nav_button_icon_names.index("composer")
                mw.main_stack.setCurrentIndex(composer_idx)
                mw.nav_buttons[composer_idx].setChecked(True)
                mw.ui_manager.update_nav_button_icons()
                mw.ui_manager.show_composer_albums(composer_name)
            except:
                print("Composer tab not found")

    def _add_go_to_composer_actions(self, menu, composers, current_view_composer=None):
        """
        Adds 'Go to Composer' navigation actions to the context menu.
        Creates a submenu if multiple composers are present.
        """
        mw = self.main_window
        if not composers:
            return
        if len(composers) == 1:
            composer = composers[0]
            if composer in mw.data_manager.composers_data:
                action = QAction(translate("Go to Composer"), mw)
                action.triggered.connect(
                    lambda: self._navigate_to_composer_safe(composer)
                )
                if composer == current_view_composer:
                    action.setEnabled(False)
                menu.addAction(action)
        else:
            sub_menu = menu.addMenu(translate("Go to Composer"))
            for composer in composers:
                if composer in mw.data_manager.composers_data:
                    action = QAction(composer, mw)
                    action.triggered.connect(
                        partial(self._navigate_to_composer_safe, composer)
                    )
                    if composer == current_view_composer:
                        action.setEnabled(False)
                    sub_menu.addAction(action)

    def _add_go_to_artist_actions(self, menu, artists, current_view_artist=None, album_artist_target=None):
        """
        Adds 'Go to Artist' or 'Go to Album Artist' navigation actions to the context menu.
        Creates a submenu if multiple artists are present.
        """
        mw = self.main_window
        if not artists:
            return

        if hasattr(mw, 'artist_source_tag') and mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
            target = album_artist_target
            if not target and artists:
                target = artists[0]

            if target:
                action = QAction(translate("Go to Album Artist"), mw)
                action.triggered.connect(lambda: mw.ui_manager.navigate_to_artist(target))

                if target == current_view_artist:
                    action.setEnabled(False)

                menu.addAction(action)
            return

        if len(artists) == 1:
            artist = artists[0]
            action = QAction(translate("Go to Artist"), mw)
            action.triggered.connect(lambda: mw.ui_manager.navigate_to_artist(artist))
            if artist == current_view_artist:
                action.setEnabled(False)
            menu.addAction(action)
        else:
            sub_menu = menu.addMenu(translate("Go to Artist"))
            for artist in artists:
                action = QAction(artist, mw)
                action.triggered.connect(
                    partial(mw.ui_manager.navigate_to_artist, artist)
                )
                if artist == current_view_artist:
                    action.setEnabled(False)
                sub_menu.addAction(action)

    def _add_go_to_genre_actions(self, menu, genres, current_view_genre=None):
        """
        Adds 'Go to Genre' navigation actions to the context menu.
        Creates a submenu if multiple genres are present.
        """
        mw = self.main_window
        if not genres:
            return

        if len(genres) == 1:
            genre = genres[0]
            action = QAction(translate("Go to Genre"), mw)
            action.triggered.connect(lambda: mw.ui_manager.navigate_to_genre(genre))
            if genre == current_view_genre:
                action.setEnabled(False)
            menu.addAction(action)
        else:
            sub_menu = menu.addMenu(translate("Go to Genre"))
            for genre in genres:
                action = QAction(genre, mw)
                action.triggered.connect(
                    partial(mw.ui_manager.navigate_to_genre, genre)
                )
                if genre == current_view_genre:
                    action.setEnabled(False)
                sub_menu.addAction(action)

    def show_context_menu(self, data, global_pos, is_queue_item=False, context=None):
        """
        Constructs and displays a dynamic, universal context menu based on the selected item's data and type.
        """
        mw = self.main_window
        menu = TranslucentMenu(mw)

        clicked_widget = QApplication.widgetAt(global_pos)
        card_widget_under_cursor = None
        if clicked_widget:
            temp_widget = clicked_widget
            while temp_widget is not None:
                if isinstance(temp_widget, CardWidget):
                    card_widget_under_cursor = temp_widget
                    break
                temp_widget = temp_widget.parent()

        widget = None
        index = QModelIndex()
        if context:
            widget = context.get("widget")

            ctx_index = context.get("index")

            if ctx_index and isinstance(ctx_index, QModelIndex) and ctx_index.isValid():
                index = ctx_index
            elif widget and hasattr(widget, "currentIndex"):
                current = widget.currentIndex()
                if current.isValid():
                    index = current

        track_list_widget = None
        if isinstance(widget, (TrackListWidget, QueueWidget)) and index.isValid():
            track_list_widget = widget
            track_list_widget.set_pressed_index(index)
        elif card_widget_under_cursor:
            pass

        current_view_artist = None
        current_view_album_key = None
        current_view_genre = None
        current_view_composer = None

        is_queue_context = context and context.get("parent_context") == "queue"

        if not is_queue_context:
            try:
                view_state = mw.current_view_state
                if view_state:
                    view_context_data = view_state.get("context_data", {})
                    main_tab_name = view_state.get("main_tab_name")

                    if "artist_name" in view_context_data:
                        current_view_artist = view_context_data.get("artist_name")
                    if "album_key" in view_context_data:
                        current_view_album_key = tuple(view_context_data["album_key"])
                    if "genre_name" in view_context_data:
                        current_view_genre = view_context_data.get("genre_name")
                    if "composer_name" in view_context_data:
                        current_view_composer = view_context_data.get("composer_name")

                    if main_tab_name == "favorite":
                        fav_context = view_context_data.get("context")
                        if fav_context == "artist":
                            current_view_artist = view_context_data.get("data")
                        elif fav_context == "genre":
                            current_view_genre = view_context_data.get("data")
                        elif fav_context == "composer":
                            current_view_composer = view_context_data.get("data")
                    elif main_tab_name == "charts":
                        charts_context = view_context_data.get("context")
                        if charts_context == "artist":
                            current_view_artist = view_context_data.get("data")
                        elif charts_context == "genre":
                            current_view_genre = view_context_data.get("data")
            except Exception:
                pass

        icn_play = QIcon(
            create_svg_icon(
                f"assets/control/play_outline.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_shake = QIcon(
            create_svg_icon(
                f"assets/control/shake_queue.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_play_next = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_play.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_add_to_queue = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_add.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_remove_from_queue = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_remove.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_edit = QIcon(
            create_svg_icon(
                f"assets/control/edit.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        icn_folder = QIcon(
            create_svg_icon(
                f"assets/control/search_folder.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_remove = QIcon(
            create_svg_icon(
                f"assets/control/delete.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        icn_lyrics = QIcon(
            create_svg_icon(
                f"assets/control/lyrics.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        icn_edit_desc = QIcon(
            create_svg_icon(
                f"assets/control/article_edit.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_search_web = QIcon(
            create_svg_icon(
                f"assets/control/search_web.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )

        tracks_list = []
        is_multi_select = False
        is_track = False
        is_album = False
        is_artist = False
        is_genre = False
        is_composer = False
        is_folder = False
        is_playlist = False

        common_artists = None
        common_album_key = None
        common_genres = None
        common_composers = None

        forced_type = context.get("forced_type") if context else None

        if isinstance(data, list):
            tracks_list = mw.data_manager.get_tracks_from_data(
                data,
                mw.library_manager,
                mw.artist_album_sort_mode,
                mw.favorite_tracks_sort_mode,
                mw.favorites,
            )
            if tracks_list:
                is_track = True
                is_multi_select = len(data) > 1
                common_artists = self._get_common_artists(tracks_list)
                common_album_key = self._get_common_album_key(tracks_list)
                common_genres = self._get_common_genres(tracks_list)
                common_composers = self._get_common_composers(tracks_list)
            else:
                return

        elif isinstance(data, dict) and "path" in data:
            tracks_list = [data]
            is_track = True
            common_artists = data.get("artists", [])
            album_artist = data.get("album_artist")
            album_title = data.get("album")
            if (
                    album_artist
                    and album_title
                    and album_title != translate("Unknown Album")
            ):
                track_year = data.get("year", 0)
                if mw.treat_folders_as_unique:
                    common_album_key = (
                        album_artist,
                        album_title,
                        track_year,
                        os.path.dirname(data["path"]),
                    )
                else:
                    common_album_key = (album_artist, album_title, track_year)
            common_genres = data.get("genre", [])
            if comp_raw := data.get("composer"):
                common_composers = [
                    c.strip() for c in re.split(r"[;/]", comp_raw) if c.strip()
                ]
            else:
                common_composers = []

        elif isinstance(data, tuple):
            is_album = True
            tracks_list = mw.data_manager.get_tracks_from_data(
                data,
                mw.library_manager,
                mw.artist_album_sort_mode,
                mw.favorite_tracks_sort_mode,
                mw.favorites,
            )
            common_album_key = data
            common_artists = [data[0]]
            album_data = mw.data_manager.albums_data.get(data, {})
            common_genres = album_data.get("genre", [])

        elif isinstance(data, str):
            if forced_type == "composer":
                is_composer = True
                common_composers = [data]
                tracks_list = mw.data_manager.get_tracks_from_data(
                    {"type": "composer", "data": data},
                    mw.library_manager,
                    mw.artist_album_sort_mode,
                    mw.favorite_tracks_sort_mode,
                    mw.favorites,
                )

            elif forced_type == "genre":
                is_genre = True
                common_genres = [data]
                tracks_list = mw.data_manager.get_tracks_from_data(
                    {"type": "genre", "data": data},
                    mw.library_manager,
                    mw.artist_album_sort_mode,
                    mw.favorite_tracks_sort_mode,
                    mw.favorites,
                )

            elif forced_type == "artist":
                is_artist = True
                common_artists = [data]
                tracks_list = mw.data_manager.get_tracks_from_data(
                    {"type": "artist", "data": data},
                    mw.library_manager,
                    mw.artist_album_sort_mode,
                    mw.favorite_tracks_sort_mode,
                    mw.favorites,
                )

            else:
                if data in mw.data_manager.artists_data:
                    is_artist = True
                    tracks_list = mw.data_manager.get_tracks_from_data(
                        data,
                        mw.library_manager,
                        mw.artist_album_sort_mode,
                        mw.favorite_tracks_sort_mode,
                        mw.favorites,
                    )
                    common_artists = [data]
                elif data in mw.data_manager.genres_data:
                    is_genre = True
                    tracks_list = mw.data_manager.get_tracks_from_data(
                        data,
                        mw.library_manager,
                        mw.artist_album_sort_mode,
                        mw.favorite_tracks_sort_mode,
                        mw.favorites,
                    )
                    common_genres = [data]
                elif data in mw.data_manager.composers_data:
                    is_composer = True
                    tracks_list = mw.data_manager.get_tracks_from_data(
                        data,
                        mw.library_manager,
                        mw.artist_album_sort_mode,
                        mw.favorite_tracks_sort_mode,
                        mw.favorites,
                    )
                    common_composers = [data]
                elif os.path.isdir(data):
                    is_folder = True
                    tracks_list = mw.data_manager.get_tracks_from_data(
                        data,
                        mw.library_manager,
                        mw.artist_album_sort_mode,
                        mw.favorite_tracks_sort_mode,
                        mw.favorites,
                    )
                elif os.path.isfile(data) and data.lower().endswith((".m3u", ".m3u8")):
                    is_playlist = True
                    tracks_list = mw.library_manager.load_playlist(
                        data, mw.data_manager.path_to_track_map
                    )
                elif data in [
                    "all_top_tracks",
                    "all_top_artists",
                    "all_top_albums",
                    "all_top_genres",
                    "all_top_folders",
                    "all_top_playlists",
                ]:
                    is_track = data == "all_top_tracks"
                    tracks_list = mw.data_manager.get_tracks_from_data(
                        data,
                        mw.library_manager,
                        mw.artist_album_sort_mode,
                        mw.favorite_tracks_sort_mode,
                        mw.favorites,
                    )

        has_virtual_tracks = False
        if tracks_list:
            has_virtual_tracks = any(t.get("is_virtual", False) for t in tracks_list)

        item_data_key, item_type = None, None

        if is_multi_select:
            pass
        elif is_track:
            item_data_key, item_type = tracks_list[0]["path"], "track"
        elif is_album:
            item_data_key, item_type = list(data), "album"

        elif forced_type == "composer":
            item_data_key, item_type = data, "composer"
        elif forced_type == "genre":
            item_data_key, item_type = data, "genre"
        elif forced_type == "artist":
            item_data_key, item_type = data, "artist"

        elif is_composer:
            item_data_key, item_type = data, "composer"
        elif is_artist:
            item_data_key, item_type = data, "artist"
        elif is_genre:
            item_data_key, item_type = data, "genre"
        elif is_folder:
            item_data_key, item_type = data, "folder"
        elif is_playlist:
            item_data_key, item_type = data, "playlist"

        if is_queue_item:
            remove_action = QAction(
                icn_remove_from_queue, translate("Remove from Queue"), mw
            )
            remove_widget = context.get("widget") if context else None
            remove_action.triggered.connect(
                lambda checked = False, w = remove_widget: self.action_handler.remove_selected_from_queue(w)
            )
            menu.addAction(remove_action)
        else:
            play_data = data
            if is_composer or forced_type == "composer":
                play_data = {"type": "composer", "data": data}
            elif is_genre or forced_type == "genre":
                play_data = {"type": "genre", "data": data}
            elif is_artist or forced_type == "artist":
                play_data = {"type": "artist", "data": data}

            play_action = QAction(icn_play, translate("Play"), mw)
            play_action.triggered.connect(
                lambda: mw.player_controller.play_data(play_data)
            )
            menu.addAction(play_action)

            shake_action = QAction(icn_shake, translate("Shake and Play"), mw)
            shake_action.triggered.connect(
                lambda: mw.player_controller.play_data_shuffled(play_data)
            )
            menu.addAction(shake_action)

            play_next_action = QAction(icn_play_next, translate("Play Next"), mw)
            play_next_action.triggered.connect(lambda: self.action_handler.play_next(play_data))
            menu.addAction(play_next_action)

            add_to_queue_action = QAction(
                icn_add_to_queue, translate("Add to Queue"), mw
            )
            add_to_queue_action.triggered.connect(lambda: self.action_handler.add_to_queue(play_data))
            menu.addAction(add_to_queue_action)

        if is_track and not is_multi_select:
            track_data = tracks_list[0]
            if track_data.get("lyrics"):
                show_lyrics_action = QAction(icn_lyrics, translate("Show Lyrics"), mw)
                show_lyrics_action.triggered.connect(
                    lambda: self.action_handler.show_lyrics(track_data)
                )
                menu.addAction(show_lyrics_action)

        menu.addSeparator()

        if item_data_key and item_type:
            if mw.library_manager.is_favorite(item_data_key, item_type):
                fav_action = QAction(
                    mw.favorite_filled_icon, translate("Remove from Favorites"), mw
                )
            else:
                fav_action = QAction(
                    mw.favorite_icon, translate("Add to Favorites"), mw
                )

            def on_favorite_toggle():
                self.action_handler.toggle_favorite(data, item_type)
                is_favorites_view = (
                        context and context.get("playlist_path") == "favorite_tracks"
                )
                if is_favorites_view:
                    mw.ui_manager.favorites_ui_manager.show_favorite_tracks_view()

            fav_action.triggered.connect(on_favorite_toggle)
            menu.addAction(fav_action)

        if is_track:
            add_to_playlist_menu = menu.addMenu(translate("Add to Playlist"))

            create_new_action = QAction(translate("Create New Playlist..."), mw)
            create_new_action.triggered.connect(
                lambda: self.action_handler.create_new_playlist_from_context(tracks_list)
            )
            add_to_playlist_menu.addAction(create_new_action)

            playlists = mw.library_manager.get_playlists()
            if not playlists:
                no_playlists_action = QAction(translate("No playlists created"), mw)
                no_playlists_action.setEnabled(False)
                add_to_playlist_menu.addAction(no_playlists_action)
            else:
                playlists.sort(key = lambda p: os.path.basename(p).lower())
                add_to_playlist_menu.addSeparator()

                for p_path in playlists:
                    p_name = os.path.splitext(os.path.basename(p_path))[0]
                    action = QAction(p_name, mw)
                    action.triggered.connect(
                        partial(self.action_handler.add_tracks_to_playlist, tracks_list, p_path)
                    )

                    playlist_track_paths = mw.library_manager.get_playlist_track_set(
                        p_path
                    )
                    all_in = True
                    if not tracks_list:
                        all_in = False
                    for t in tracks_list:
                        if t["path"] not in playlist_track_paths:
                            all_in = False
                            break
                    if all_in:
                        action.setIcon(mw.check_icon)

                    add_to_playlist_menu.addAction(action)

            is_history_context = context and context.get("source") == "history"
            is_charts_context = context and context.get("source") == "charts"
            is_favorites_context = (
                    context and context.get("playlist_path") == "favorite_tracks"
            )

            target_index = -1
            if context and "index" in context:
                idx_obj = context["index"]
                if isinstance(idx_obj, QModelIndex) and idx_obj.isValid():
                    target_index = idx_obj.row()

            if (
                    not is_multi_select
                    and context
                    and "playlist_path" in context
                    and target_index >= 0
                    and not is_history_context
                    and not is_charts_context
                    and not is_favorites_context
            ):
                playlist_path = context["playlist_path"]
                remove_from_plist_action = QAction(
                    translate("Remove from Playlist"), mw
                )
                remove_from_plist_action.triggered.connect(
                    lambda: self.action_handler.remove_track_from_viewed_playlist(playlist_path, target_index)
                )
                menu.addAction(remove_from_plist_action)

        menu.addSeparator()

        if is_track or is_album or is_artist or is_genre or is_composer:

            if is_track and not is_multi_select and not common_artists:
                if isinstance(data, dict) and data.get("artist"):
                    common_artists = [data.get("artist")]

            album_artist_target = None
            if isinstance(data, dict):
                album_artist_target = data.get("album_artist") or data.get("artist")
            elif isinstance(data, list) and data:
                album_artist_target = data[0].get("album_artist") or data[0].get("artist")
            elif isinstance(data, tuple) and len(data) > 0:
                album_artist_target = data[0]
            elif is_artist:
                album_artist_target = data

            if common_artists:
                self._add_go_to_artist_actions(
                    menu, common_artists, current_view_artist, album_artist_target
                )
            if common_album_key:
                go_to_album_action = QAction(translate("Go to Album"), mw)
                go_to_album_action.triggered.connect(
                    lambda: mw.ui_manager.navigate_to_album_tab_and_show(
                        common_album_key
                    )
                )
                if common_album_key == current_view_album_key:
                    go_to_album_action.setEnabled(False)
                menu.addAction(go_to_album_action)

                if len(common_album_key) > 2:
                    album_year = common_album_key[2]
                    if album_year and int(album_year) > 0:
                        go_to_year_action = QAction(
                            translate("Go to Albums from {year}", year = album_year), mw
                        )
                        go_to_year_action.triggered.connect(
                            lambda: mw.ui_manager.navigate_to_year(str(album_year))
                        )
                        menu.addAction(go_to_year_action)
            if common_genres:
                self._add_go_to_genre_actions(menu, common_genres, current_view_genre)
            if common_composers:
                self._add_go_to_composer_actions(
                    menu, common_composers, current_view_composer
                )

            menu.addSeparator()

            search_query = None
            if is_track and not is_multi_select:
                t = tracks_list[0]
                artist_name = t.get("artist") or (
                    t.get("artists")[0] if t.get("artists") else ""
                )
                title_name = t.get("title", "")
                if artist_name and title_name:
                    search_query = f"{artist_name} {title_name}"
            elif is_album and len(data) >= 2:
                search_query = f"{data[0]} {data[1]}"
            elif is_artist:
                search_query = data
            elif is_genre:
                search_query = f"{data} genre"
            elif is_composer:
                search_query = f"{data} composer"

            if search_query:
                search_menu = menu.addMenu(
                    icn_search_web, translate("Search Online...")
                )

                links = mw.library_manager.load_search_links()

                for link in links:
                    if not link.get("enabled", True):
                        continue

                    name = link["name"]
                    url = link["url"]

                    action = QAction(name, mw)
                    action.triggered.connect(
                        partial(self.action_handler.search_in_internet, search_query, url)
                    )
                    search_menu.addAction(action)

                search_menu.addSeparator()

                add_custom_action = QAction(
                    create_svg_icon(
                        "assets/control/add.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
                    ),
                    translate("Add Custom..."),
                    mw,
                )
                add_custom_action.triggered.connect(self.action_handler.open_add_search_link_dialog)
                search_menu.addAction(add_custom_action)

        menu.addSeparator()

        current_idx = mw.main_stack.currentIndex()
        is_charts_view = False
        if 0 <= current_idx < len(mw.nav_button_icon_names):
            is_charts_view = mw.nav_button_icon_names[current_idx] == "charts"

        if (
                is_charts_view
                and not is_multi_select
                and (is_track or is_album or is_artist or is_genre or is_composer)
        ):
            icn_reset_stats = QIcon(
                create_svg_icon(
                    "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
                )
            )
            reset_stats_action = QAction(icn_reset_stats, translate("Reset Rating"), mw)
            reset_stats_action.triggered.connect(
                lambda: self.action_handler.handle_reset_stats_request(data, item_type)
            )
            menu.addAction(reset_stats_action)

        menu.addSeparator()

        if is_track or is_album or is_folder:
            if has_virtual_tracks:
                edit_metadata_action = QAction(
                    icn_edit, translate("Editing CUE not supported"), mw
                )
                edit_metadata_action.setEnabled(False)
                menu.addAction(edit_metadata_action)
            else:
                edit_metadata_action = QAction(icn_edit, translate("Edit Metadata"), mw)
                edit_metadata_action.triggered.connect(
                    lambda: self.action_handler.open_metadata_editor(data)
                )
                edit_metadata_action.setEnabled(not mw.is_processing_library)
                menu.addAction(edit_metadata_action)
            menu.addSeparator()

        if not is_multi_select and (is_artist or is_album or is_genre or is_composer):
            enc_key = None
            enc_type = None

            if is_artist:
                enc_key = data
                enc_type = "artist"
            elif is_genre:
                enc_key = data
                enc_type = "genre"
            elif is_composer:
                enc_key = data
                enc_type = "composer"
            elif is_album:
                enc_key = data
                enc_type = "album"

            if enc_key and enc_type:
                has_desc = bool(mw.encyclopedia_manager.get_entry(enc_key, enc_type))

                icn_open = QIcon(
                    create_svg_icon(
                        "assets/control/encyclopedia.svg",
                        theme.COLORS["PRIMARY"],
                        QSize(24, 24),
                    )
                )
                open_action = QAction(icn_open, translate("Open Encyclopedia"), mw)
                open_action.triggered.connect(
                    lambda: mw.open_encyclopedia_manager(enc_key, enc_type)
                )
                menu.addAction(open_action)

                if has_desc:
                    icn_read = QIcon(
                        create_svg_icon(
                            "assets/control/article_read.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        )
                    )
                    read_action = QAction(icn_read, translate("Read Article"), mw)
                    read_action.triggered.connect(
                        lambda: mw.ui_manager.open_encyclopedia_full_view(
                            enc_key, enc_type
                        )
                    )
                    menu.addAction(read_action)

                if has_desc:
                    action_text = translate("Edit Article")
                    icn_enc = QIcon(
                        create_svg_icon(
                            "assets/control/article_edit.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        )
                    )
                else:
                    action_text = translate("Create Encyclopedia Article")
                    icn_enc = QIcon(
                        create_svg_icon(
                            "assets/control/encyclopedia_add.svg",
                            theme.COLORS["PRIMARY"],
                            QSize(24, 24),
                        )
                    )

                edit_action = QAction(icn_enc, action_text, mw)

                edit_action.triggered.connect(
                    lambda: mw.ui_manager.open_encyclopedia_editor(enc_key, enc_type)
                )

                menu.addAction(edit_action)

                menu.addSeparator()

        if not is_multi_select and item_type != "genre" and item_type != "composer":
            show_in_explorer_action = QAction(
                icn_folder, translate("Show File Location"), mw
            )

            target_for_explorer = data
            if has_virtual_tracks and tracks_list:
                target_for_explorer = tracks_list[0].get(
                    "real_path", tracks_list[0]["path"]
                )
            elif isinstance(data, str) and (os.path.exists(data) or "::" in data):
                target_for_explorer = data

            if target_for_explorer:
                show_in_explorer_action.triggered.connect(
                    lambda: self.action_handler.show_in_explorer(target_for_explorer)
                )
                menu.addAction(show_in_explorer_action)

        if not is_multi_select and item_type in [
            "track",
            "album",
            "artist",
            "folder",
            "composer",
        ]:
            remove_from_library_action = QAction(
                icn_remove, translate("Remove from Library..."), mw
            )
            remove_from_library_action.triggered.connect(
                lambda: self.action_handler.handle_remove_from_library_request(data, item_type)
            )
            remove_from_library_action.setEnabled(not mw.is_processing_library)
            menu.addAction(remove_from_library_action)

        menu.exec(global_pos)

        try:
            if track_list_widget:
                track_list_widget.set_pressed_index(QModelIndex())
            elif card_widget_under_cursor:
                card_widget_under_cursor.style().unpolish(card_widget_under_cursor)
                card_widget_under_cursor.style().polish(card_widget_under_cursor)
                card_widget_under_cursor.update()
        except RuntimeError:
            pass

    def show_queue_context_menu(self, pos, source_widget=None):
        """
        Constructs and displays a context menu specifically tailored for items within the playback queue widget.
        """
        mw = self.main_window

        if source_widget is None:
            source_widget = mw.right_panel.queue_widget

        index = source_widget.indexAt(pos)
        if not index.isValid():
            return

        is_already_selected = index in source_widget.selectedIndexes()

        if not is_already_selected:
            source_widget.clearSelection()
            source_widget.setCurrentIndex(index)

        selected_items = source_widget.selectedItems()
        if not selected_items:
            item = source_widget.itemAt(pos)
            if not item:
                return
            selected_items = [item]

        selected_data = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in selected_items
            if item.data(Qt.ItemDataRole.UserRole)
        ]
        if not selected_data:
            return

        context_index = source_widget.indexFromItem(selected_items[0])
        context = {
            "source": "queuelist",
            "parent_context": "queue",
            "widget": source_widget,
            "index": context_index,
        }

        self.show_context_menu(
            selected_data,
            source_widget.mapToGlobal(pos),
            is_queue_item = True,
            context = context,
        )

    def show_playlist_card_context_menu(self, playlist_path, global_pos):
        """
        Constructs and displays the context menu for playlist representation cards.
        """
        mw = self.main_window
        menu = TranslucentMenu(mw)

        icn_play = QIcon(
            create_svg_icon(
                f"assets/control/play_outline.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_shake = QIcon(
            create_svg_icon(
                f"assets/control/shake_queue.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_play_next = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_play.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )

        icn_add_to_queue = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_add.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_folder = QIcon(
            create_svg_icon(
                f"assets/control/search_folder.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_remove = QIcon(
            create_svg_icon(
                f"assets/control/delete.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        icn_add_lib = QIcon(
            create_svg_icon(
                f"assets/control/folder_add.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )

        play_action = QAction(icn_play, translate("Play"), mw)
        play_action.triggered.connect(
            lambda: mw.player_controller.play_data(playlist_path)
        )
        menu.addAction(play_action)

        shake_action = QAction(icn_shake, translate("Shake and Play"), mw)
        shake_action.triggered.connect(
            lambda: mw.player_controller.play_data_shuffled(playlist_path)
        )
        menu.addAction(shake_action)

        play_next_action = QAction(icn_play_next, translate("Play Next"), mw)
        play_next_action.triggered.connect(
            lambda: self.action_handler.play_playlist_next(playlist_path)
        )
        menu.addAction(play_next_action)

        add_to_queue_action = QAction(icn_add_to_queue, translate("Add to Queue"), mw)
        add_to_queue_action.triggered.connect(
            lambda: self.action_handler.add_playlist_to_queue(playlist_path)
        )
        menu.addAction(add_to_queue_action)
        menu.addSeparator()

        missing_folders = self.action_handler.get_missing_folders_from_playlist(playlist_path)

        if missing_folders:
            action_text = translate(
                "Import missing folders ({count})", count = len(missing_folders)
            )
            add_lib_action = QAction(icn_add_lib, action_text, mw)
            add_lib_action.triggered.connect(
                lambda: self.action_handler.add_playlist_sources_to_library(missing_folders)
            )
            menu.addAction(add_lib_action)
            menu.addSeparator()

        if mw.library_manager.is_favorite(playlist_path, "playlist"):
            fav_action = QAction(
                mw.favorite_filled_icon, translate("Remove from Favorites"), mw
            )
        else:
            fav_action = QAction(mw.favorite_icon, translate("Add to Favorites"), mw)
        fav_action.triggered.connect(
            lambda: self.action_handler.toggle_favorite(playlist_path, "playlist")
        )
        menu.addAction(fav_action)
        menu.addSeparator()

        create_mixtape_action = QAction(
            mw.mixtape_icon, translate("Create Mixtape"), mw
        )
        playlist_name = os.path.splitext(os.path.basename(str(playlist_path)))[0]
        create_mixtape_action.triggered.connect(
            lambda: self.action_handler.create_mixtape_from_data(playlist_path, playlist_name)
        )
        menu.addAction(create_mixtape_action)
        menu.addSeparator()

        icn_edit = QIcon(
            create_svg_icon(
                "assets/control/edit.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        rename_action = QAction(icn_edit, translate("Rename"), mw)
        rename_action.triggered.connect(
            lambda: self.action_handler.rename_playlist_dialog(playlist_path)
        )
        menu.addAction(rename_action)

        show_in_explorer_action = QAction(
            icn_folder, translate("Show File Location"), mw
        )
        show_in_explorer_action.triggered.connect(
            lambda: self.action_handler.show_in_explorer(playlist_path)
        )
        menu.addAction(show_in_explorer_action)

        delete_action = QAction(icn_remove, translate("Delete Playlist"), mw)
        delete_action.triggered.connect(lambda: self.action_handler.delete_playlist(playlist_path))
        menu.addAction(delete_action)

        menu.exec(global_pos)

    def show_favorite_tracks_card_context_menu(self, data, global_pos):
        """
        Constructs and displays the context menu specifically for favorite track cards.
        """
        mw = self.main_window
        menu = TranslucentMenu(mw)

        icn_play = QIcon(
            create_svg_icon(
                f"assets/control/play_outline.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_shake = QIcon(
            create_svg_icon(
                f"assets/control/shake_queue.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_play_next = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_play.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        icn_add_to_queue = QIcon(
            create_svg_icon(
                f"assets/control/playback_queue_add.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )

        play_action = QAction(icn_play, translate("Play"), mw)
        play_action.triggered.connect(lambda: mw.player_controller.play_data(data))
        menu.addAction(play_action)

        if data != "playback_history":
            shake_action = QAction(icn_shake, translate("Shake and Play"), mw)
            shake_action.triggered.connect(
                lambda: mw.player_controller.play_data_shuffled(data)
            )
            menu.addAction(shake_action)

        play_next_action = QAction(icn_play_next, translate("Play Next"), mw)
        play_next_action.triggered.connect(lambda: self.action_handler.play_next(data))
        menu.addAction(play_next_action)

        add_to_queue_action = QAction(icn_add_to_queue, translate("Add to Queue"), mw)
        add_to_queue_action.triggered.connect(lambda: self.action_handler.add_to_queue(data))
        menu.addAction(add_to_queue_action)
        menu.addSeparator()

        if data == "favorite_tracks":
            create_mixtape_action = QAction(
                mw.mixtape_icon, translate("Create Mixtape"), mw
            )
            create_mixtape_action.triggered.connect(
                lambda: self.action_handler.create_mixtape_from_data(
                    "favorite_tracks", translate("Favorite Tracks")
                )
            )
            menu.addAction(create_mixtape_action)

        menu.exec(global_pos)

    def show_favorite_tracks_context_menu(self, data, global_pos):
        """
        A convenience wrapper to show the context menu specifically for the favorite tracks general view.
        """
        self.show_favorite_tracks_card_context_menu("favorite_tracks", global_pos)


