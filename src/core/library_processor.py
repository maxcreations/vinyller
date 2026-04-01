"""
Vinyller — Data manager and library processor
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
import re
import time
from collections import defaultdict

from PyQt6.QtCore import (
    pyqtSignal, QObject
)

from src.core.library_manager import LibraryManager
from src.ui.custom_classes import (
    ChartsPeriod,
    SortMode
)
from src.utils.constants import (
    ARTICLES_TO_IGNORE
)
from src.utils.utils import (
    parse_cue_sheet
)
from src.utils.utils_translator import translate


class DataManager:
    """
    A class for managing all music library data.
    Encapsulates lists of tracks, artists, albums, and methods for working with them.
    """

    def __init__(self):
        """
        Initializes the DataManager with empty collections for tracks, artists,
        albums, genres, composers, and various sorted lists used for UI presentation.
        """
        self.all_tracks = []
        self.artists_data = {}
        self.albums_data = {}
        self.genres_data = {}
        self.composers_data = {}
        self.sorted_artists = []
        self.sorted_albums = []
        self.sorted_genres = []
        self.sorted_composers = []
        self.sorted_songs_groups = []
        self.sorted_tracks_by_play_count = []

        self.path_to_track_map = {}
        self.all_music_folders = []
        self.ignore_articles = True

    @staticmethod
    def make_album_key(artist, album, year):
        """
        Creates a standard album key for the encyclopedia (3-element tuple).
        Used wherever an album needs to be referenced without being tied to a specific file/folder.
        """
        try:
            y = int(year) if year is not None else 0
        except ValueError:
            y = 0

        a = str(artist).strip() if artist else ""
        t = str(album).strip() if album else ""

        return (a, t, y)

    def recalculate_ratings(self, period: str, play_stats: dict):
        """
        Recalculates ratings (entity_rating and play_count) in memory
        based on the selected period (monthly or all_time).
        """
        print(f"DataManager: Recalculating ratings for period: {period}")

        stat_key = "monthly" if period == ChartsPeriod.MONTHLY else "all_time"

        stats_tracks = play_stats.get("tracks", {})
        stats_artists = play_stats.get("artists", {})
        stats_albums = play_stats.get("albums", {})
        stats_genres = play_stats.get("genres", {})
        stats_composers = play_stats.get("composers", {})

        updated_tracks_with_play_count = []
        for track in self.all_tracks:
            track_path = track["path"]
            track_stats = stats_tracks.get(track_path, {})
            count = track_stats.get(stat_key, 0) if isinstance(track_stats, dict) else 0

            track["play_count"] = count
            if count > 0:
                updated_tracks_with_play_count.append(track)

            if track_path in self.path_to_track_map:
                self.path_to_track_map[track_path]["play_count"] = count

        self.sorted_tracks_by_play_count = sorted(
            updated_tracks_with_play_count,
            key=lambda t: (
                -t["play_count"],
                self.get_sort_key(t.get("title", "")),
                self.get_sort_key(t.get("artist", "")),
            ),
        )

        for artist_name, artist_data in self.artists_data.items():
            st = stats_artists.get(artist_name, {})
            artist_data["entity_rating"] = (
                st.get(stat_key, 0) if isinstance(st, dict) else 0
            )

        for album_key, album_data in self.albums_data.items():
            try:
                album_key_str = json.dumps(list(album_key))
                st = stats_albums.get(album_key_str, {})
                album_data["entity_rating"] = (
                    st.get(stat_key, 0) if isinstance(st, dict) else 0
                )
            except Exception:
                pass

        for genre_name, genre_data in self.genres_data.items():
            st = stats_genres.get(genre_name, {})
            genre_data["entity_rating"] = (
                st.get(stat_key, 0) if isinstance(st, dict) else 0
            )

        for comp_name, comp_data in self.composers_data.items():
            st = stats_composers.get(comp_name, {})
            comp_data["entity_rating"] = (
                st.get(stat_key, 0) if isinstance(st, dict) else 0
            )

        print("DataManager: Ratings updated.")

    def update_stats_from_json(self, play_stats: dict):
        """
        Quickly updates only the playback counters in memory
        from the loaded play_stats.json file.
        """
        print("DataManager: Updating statistics in memory...")

        stats_tracks = play_stats.get("tracks", {})
        stats_artists = play_stats.get("artists", {})
        stats_albums = play_stats.get("albums", {})
        stats_genres = play_stats.get("genres", {})
        stats_composers = play_stats.get("composers", {})

        updated_tracks_with_play_count = []
        for track in self.all_tracks:
            track_path = track["path"]
            track_stats = stats_tracks.get(track_path, {"all_time": 0})
            track_play_count = track_stats.get("all_time", 0)
            track["play_count"] = track_play_count

            if track_play_count > 0:
                updated_tracks_with_play_count.append(track)

            if track_path in self.path_to_track_map:
                self.path_to_track_map[track_path]["play_count"] = track_play_count

        for artist_name, artist_data in self.artists_data.items():
            artist_stats = stats_artists.get(artist_name, {"all_time": 0})
            artist_data["entity_rating"] = artist_stats.get("all_time", 0)

        for album_key, album_data in self.albums_data.items():
            try:
                album_key_str = json.dumps(list(album_key))
                album_stats = stats_albums.get(album_key_str, {"all_time": 0})
                album_data["entity_rating"] = album_stats.get("all_time", 0)
            except Exception:
                pass

        for genre_name, genre_data in self.genres_data.items():
            genre_stats = stats_genres.get(genre_name, {"all_time": 0})
            genre_data["entity_rating"] = genre_stats.get("all_time", 0)

        for composer_name, composer_data in self.composers_data.items():
            comp_stats = stats_composers.get(composer_name, {"all_time": 0})
            composer_data["entity_rating"] = comp_stats.get("all_time", 0)

        self.sorted_tracks_by_play_count = sorted(
            updated_tracks_with_play_count,
            key=lambda t: (
                -t["play_count"],
                self.get_sort_key(t.get("title", "")),
                self.get_sort_key(t.get("artist", "")),
            ),
        )

        print("DataManager: Statistics updated in memory.")

    def update_data(self, result_data):
        """
        Updates all library data (tracks, artists, albums, etc.) from a provided
        dictionary, typically generated by the LibraryProcessor.
        """
        self.all_tracks = result_data.get("all_tracks", [])
        for track in self.all_tracks:
            track["path"] = os.path.abspath(track["path"])

        self.artists_data = result_data.get("artists_data", {})
        self.albums_data = result_data.get("albums_data", {})
        self.genres_data = result_data.get("genres_data", {})
        self.composers_data = result_data.get("composers_data", {})
        self.sorted_artists = result_data.get("sorted_artists", [])
        self.sorted_albums = result_data.get("sorted_albums", [])
        self.sorted_genres = result_data.get("sorted_genres", [])
        self.sorted_composers = result_data.get("sorted_composers", [])
        self.sorted_songs_groups = result_data.get("sorted_songs_groups", [])
        tracks_with_plays = [t for t in self.all_tracks if t.get("play_count", 0) > 0]
        self.sorted_tracks_by_play_count = sorted(
            tracks_with_plays,
            key=lambda t: (
                -t["play_count"],
                self.get_sort_key(t.get("title", "")),
                self.get_sort_key(t.get("artist", "")),
            ),
        )

        self.all_music_folders = result_data.get("all_music_folders", [])

        self.path_to_track_map = {track["path"]: track for track in self.all_tracks}

    def clear_data(self):
        """
        Clears all in-memory structures containing library data.
        """
        self.all_tracks.clear()
        self.artists_data.clear()
        self.albums_data.clear()
        self.genres_data.clear()
        self.composers_data.clear()
        self.sorted_artists.clear()
        self.sorted_albums.clear()
        self.sorted_genres.clear()
        self.sorted_composers.clear()
        self.sorted_songs_groups.clear()
        self.sorted_tracks_by_play_count.clear()

        self.all_music_folders.clear()
        self.path_to_track_map.clear()

    def is_empty(self):
        """
        Returns True if there are no tracks loaded in the library.
        """
        return not self.all_tracks

    def get_track_by_path(self, path):
        """
        Retrieves a track dictionary by its absolute file path.
        Returns None if the track is not found.
        """
        return self.path_to_track_map.get(os.path.abspath(path))

    def get_sort_key(self, name):
        """
        Generates a lowercase sorting key for a given string.
        If `ignore_articles` is enabled, it strips leading common articles
        (like "the", "a", "an") before sorting.
        """
        if not isinstance(name, str):
            name = str(name)
        name_lower = name.lower()

        pattern = r"^(" + "|".join(ARTICLES_TO_IGNORE) + r")\s+"
        if self.ignore_articles and (match := re.match(pattern, name_lower)):
            return name_lower[len(match.group(0)):]
        return name_lower

    def get_tracks_from_data(
        self,
        data,
        library_manager,
        artist_album_sort_mode,
        favorite_tracks_sort_mode,
        favorites,
    ):
        """
        Extracts a flat list of tracks based on various input criteria (e.g., a genre name,
        an artist name, a folder path, a playlist, or specific dictionary filters).
        Applies sorting rules according to the specified sort modes.
        """
        if isinstance(data, list):
            return [t for t in data if isinstance(t, dict) and "path" in t]

        if isinstance(data, dict) and "type" in data and "data" in data:
            req_type = data["type"]
            req_data = data["data"]

            if req_type == "composer" and req_data in self.composers_data:
                composer_data = self.composers_data[req_data]
                album_keys = composer_data.get("albums", [])

                albums_of_composer = []
                for key in album_keys:
                    t_key = tuple(key) if isinstance(key, list) else key
                    if t_key in self.albums_data:
                        albums_of_composer.append((t_key, self.albums_data[t_key]))

                sort_mode = artist_album_sort_mode
                if sort_mode == SortMode.ALPHA_ASC:
                    albums_of_composer.sort(key=lambda x: self.get_sort_key(x[0][1]))
                elif sort_mode == SortMode.ALPHA_DESC:
                    albums_of_composer.sort(
                        key=lambda x: self.get_sort_key(x[0][1]), reverse=True
                    )
                elif sort_mode == SortMode.YEAR_ASC:
                    albums_of_composer.sort(
                        key=lambda x: (
                            x[1].get("year", 9999),
                            self.get_sort_key(x[0][1]),
                        )
                    )
                elif sort_mode == SortMode.YEAR_DESC:
                    albums_of_composer.sort(
                        key=lambda x: (x[1].get("year", 0), self.get_sort_key(x[0][1])),
                        reverse=True,
                    )

                final_tracks = []
                for _, album_data in albums_of_composer:
                    album_tracks = album_data.get("tracks", [])
                    filtered_tracks = []
                    for t in album_tracks:
                        raw_c = t.get("composer", "")
                        if raw_c:
                            comps = [
                                c.strip() for c in re.split(r"[;/]", raw_c) if c.strip()
                            ]
                            if req_data in comps:
                                filtered_tracks.append(t)
                    final_tracks.extend(
                        sorted(
                            filtered_tracks,
                            key=lambda t: (
                                t.get("discnumber", 0),
                                t.get("tracknumber", 0),
                            ),
                        )
                    )
                return final_tracks

            elif req_type == "genre" and req_data in self.genres_data:
                album_keys_in_genre = self.genres_data[req_data]["albums"]
                albums_of_genre = [
                    (key, self.albums_data[key])
                    for key in album_keys_in_genre
                    if key in self.albums_data
                ]

                sort_mode = artist_album_sort_mode
                if sort_mode == SortMode.ALPHA_ASC:
                    albums_of_genre.sort(key=lambda x: self.get_sort_key(x[0][1]))
                elif sort_mode == SortMode.ALPHA_DESC:
                    albums_of_genre.sort(
                        key=lambda x: self.get_sort_key(x[0][1]), reverse=True
                    )
                elif sort_mode == SortMode.YEAR_ASC:
                    albums_of_genre.sort(
                        key=lambda x: (
                            x[1].get("year", 9999),
                            self.get_sort_key(x[0][1]),
                        )
                    )
                elif sort_mode == SortMode.YEAR_DESC:
                    albums_of_genre.sort(
                        key=lambda x: (x[1].get("year", 0), self.get_sort_key(x[0][1])),
                        reverse=True,
                    )

                final_tracks = []
                for _, album_data in albums_of_genre:
                    final_tracks.extend(
                        sorted(
                            album_data.get("tracks", []),
                            key=lambda t: (
                                t.get("discnumber", 0),
                                t.get("tracknumber", 0),
                            ),
                        )
                    )
                return final_tracks

            elif req_type == "artist" and req_data in self.artists_data:
                return self.get_tracks_from_data(
                    req_data,
                    library_manager,
                    artist_album_sort_mode,
                    favorite_tracks_sort_mode,
                    favorites,
                )

            data = req_data

        if isinstance(data, dict):
            return [data]

        if isinstance(data, tuple) and len(data) > 1:

            def _get_tracks_from_archive_list(path_list):
                tracks = []
                for item in path_list:
                    if isinstance(item, (list, tuple)) and len(item) > 0:
                        path = item[0]
                        if track_obj := self.path_to_track_map.get(path):
                            tracks.append(track_obj)
                return tracks

            def _get_items_from_archive_list(item_list):
                items = []
                for item in item_list:
                    if isinstance(item, (list, tuple)) and len(item) > 0:
                        items.append(item[0])
                return items

            try:
                if data[1] == "month_overview":
                    month_key = data[0]
                    archive = library_manager.load_charts_archive()
                    if month_data := archive.get(month_key, {}).get("tracks"):
                        return _get_tracks_from_archive_list(month_data)

                elif (
                    len(data) == 2
                    and data[0] in ["tracks", "artists", "albums", "genres"]
                    and isinstance(data[1], str)
                    and len(data[1]) == 7
                ):

                    cat_key, month_key = data
                    archive = library_manager.load_charts_archive()
                    chart_list = archive.get(month_key, {}).get(cat_key)

                    if not chart_list:
                        return []

                    if cat_key == "tracks":
                        return _get_tracks_from_archive_list(chart_list)

                    elif cat_key in ["artists", "albums", "genres"]:
                        item_keys_str = _get_items_from_archive_list(chart_list)
                        all_tracks = []
                        item_keys = []
                        if cat_key == "albums":
                            for k_str in item_keys_str:
                                try:
                                    item_keys.append(tuple(json.loads(k_str)))
                                except Exception:
                                    pass
                        else:
                            item_keys = item_keys_str

                        for item_key in item_keys:
                            all_tracks.extend(
                                self.get_tracks_from_data(
                                    item_key,
                                    library_manager,
                                    artist_album_sort_mode,
                                    favorite_tracks_sort_mode,
                                    favorites,
                                )
                            )
                        return all_tracks

                elif len(data) == 3 and data[0] == "tracks":
                    return _get_tracks_from_archive_list(data[2])

                elif len(data) == 3 and data[0] in ["artists", "albums", "genres"]:
                    item_keys_str = _get_items_from_archive_list(data[2])
                    all_tracks = []
                    item_keys = []
                    if data[0] == "albums":
                        for k_str in item_keys_str:
                            try:
                                item_keys.append(tuple(json.loads(k_str)))
                            except Exception:
                                pass
                    else:
                        item_keys = item_keys_str

                    for item_key in item_keys:
                        all_tracks.extend(
                            self.get_tracks_from_data(
                                item_key,
                                library_manager,
                                artist_album_sort_mode,
                                favorite_tracks_sort_mode,
                                favorites,
                            )
                        )
                    return all_tracks
            except Exception as e:
                print(f"Error processing archive data: {e}")
                return []

        if isinstance(data, tuple):
            if data in self.albums_data:
                tracks = self.albums_data.get(data, {}).get("tracks", [])
                return sorted(
                    tracks,
                    key=lambda t: (t.get("discnumber", 0), t.get("tracknumber", 0)),
                )

            matched_tracks = []
            target_artist = data[0]
            target_album = data[1]

            target_path = (
                data[2] if len(data) > 2 and isinstance(data[2], str) else None
            )

            for key, album_data in self.albums_data.items():
                if key[0] == target_artist and key[1] == target_album:
                    if target_path:
                        if len(key) >= 4 and key[-1] == target_path:
                            matched_tracks.extend(album_data.get("tracks", []))
                    else:
                        matched_tracks.extend(album_data.get("tracks", []))

            if matched_tracks:
                return sorted(
                    matched_tracks,
                    key=lambda t: (t.get("discnumber", 0), t.get("tracknumber", 0)),
                )

        if isinstance(data, str):
            if data in self.artists_data:
                artist_data = self.artists_data[data]
                album_keys_for_artist = artist_data.get("albums", [])
                albums_of_artist = [
                    (tuple(key), self.albums_data[tuple(key)])
                    for key in album_keys_for_artist
                    if tuple(key) in self.albums_data
                ]

                sort_mode = artist_album_sort_mode
                if sort_mode == SortMode.ALPHA_ASC:
                    albums_of_artist.sort(key=lambda x: self.get_sort_key(x[0][1]))
                elif sort_mode == SortMode.ALPHA_DESC:
                    albums_of_artist.sort(
                        key=lambda x: self.get_sort_key(x[0][1]), reverse=True
                    )
                elif sort_mode == SortMode.YEAR_ASC:
                    albums_of_artist.sort(
                        key=lambda x: (
                            x[1].get("year", 9999),
                            self.get_sort_key(x[0][1]),
                        )
                    )
                elif sort_mode == SortMode.YEAR_DESC:
                    albums_of_artist.sort(
                        key=lambda x: (x[1].get("year", 0), self.get_sort_key(x[0][1])),
                        reverse=True,
                    )

                final_tracks = []
                for _, album_data in albums_of_artist:
                    final_tracks.extend(
                        sorted(
                            album_data.get("tracks", []),
                            key=lambda t: (
                                t.get("discnumber", 0),
                                t.get("tracknumber", 0),
                            ),
                        )
                    )
                return final_tracks

            elif data in self.genres_data:
                album_keys_in_genre = self.genres_data[data]["albums"]
                albums_of_genre = [
                    (key, self.albums_data[key])
                    for key in album_keys_in_genre
                    if key in self.albums_data
                ]

                sort_mode = artist_album_sort_mode

                if sort_mode == SortMode.ALPHA_ASC:
                    albums_of_genre.sort(key=lambda x: self.get_sort_key(x[0][1]))
                elif sort_mode == SortMode.ALPHA_DESC:
                    albums_of_genre.sort(
                        key=lambda x: self.get_sort_key(x[0][1]), reverse=True
                    )
                elif sort_mode == SortMode.YEAR_ASC:
                    albums_of_genre.sort(
                        key=lambda x: (
                            x[1].get("year", 9999),
                            self.get_sort_key(x[0][1]),
                        )
                    )
                elif sort_mode == SortMode.YEAR_DESC:
                    albums_of_genre.sort(
                        key=lambda x: (x[1].get("year", 0), self.get_sort_key(x[0][1])),
                        reverse=True,
                    )

                final_tracks = []

                for _, album_data in albums_of_genre:
                    final_tracks.extend(
                        sorted(
                            album_data.get("tracks", []),
                            key=lambda t: (
                                t.get("discnumber", 0),
                                t.get("tracknumber", 0),
                            ),
                        )
                    )

                return final_tracks

            elif data in self.composers_data:
                composer_data = self.composers_data[data]
                album_keys = composer_data.get("albums", [])
                albums_of_composer = []

                for key in album_keys:
                    t_key = tuple(key) if isinstance(key, list) else key
                    if t_key in self.albums_data:
                        albums_of_composer.append((t_key, self.albums_data[t_key]))

                sort_mode = artist_album_sort_mode
                if sort_mode == SortMode.ALPHA_ASC:
                    albums_of_composer.sort(key=lambda x: self.get_sort_key(x[0][1]))
                elif sort_mode == SortMode.ALPHA_DESC:
                    albums_of_composer.sort(
                        key=lambda x: self.get_sort_key(x[0][1]), reverse=True
                    )
                elif sort_mode == SortMode.YEAR_ASC:
                    albums_of_composer.sort(
                        key=lambda x: (
                            x[1].get("year", 9999),
                            self.get_sort_key(x[0][1]),
                        )
                    )
                elif sort_mode == SortMode.YEAR_DESC:
                    albums_of_composer.sort(
                        key=lambda x: (x[1].get("year", 0), self.get_sort_key(x[0][1])),
                        reverse=True,
                    )

                final_tracks = []

                for album_data in [
                    x[1] for x in albums_of_composer
                ]:
                    album_tracks = album_data.get("tracks", [])
                    filtered_tracks = []

                    for t in album_tracks:
                        raw_c = t.get("composer", "")

                        if raw_c:
                            comps = [
                                c.strip() for c in re.split(r"[;/]", raw_c) if c.strip()
                            ]

                            if data in comps:
                                filtered_tracks.append(t)

                    final_tracks.extend(
                        sorted(
                            filtered_tracks,
                            key=lambda t: (
                                t.get("discnumber", 0),
                                t.get("tracknumber", 0),
                            ),
                        )
                    )

                return final_tracks

            elif data == "playback_history":
                history_paths = library_manager.load_playback_history()
                return [
                    self.path_to_track_map[path]
                    for path in history_paths
                    if path in self.path_to_track_map
                ]

            elif data == "all_favorite_artists":
                fav_artists_dict = favorites.get("artists", {})
                all_fav_tracks = []
                for artist_name in fav_artists_dict.keys():
                    all_fav_tracks.extend(
                        self.get_tracks_from_data(
                            artist_name,
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_fav_tracks

            elif data == "all_favorite_albums":
                fav_albums_dict = favorites.get("albums", {})
                all_fav_tracks = []
                for key_str in fav_albums_dict.keys():
                    try:
                        album_key = tuple(json.loads(key_str))
                        all_fav_tracks.extend(
                            self.get_tracks_from_data(
                                album_key,
                                library_manager,
                                artist_album_sort_mode,
                                favorite_tracks_sort_mode,
                                favorites,
                            )
                        )
                    except json.JSONDecodeError:
                        continue
                return all_fav_tracks

            elif data == "all_favorite_genres":
                fav_genres_dict = favorites.get("genres", {})
                all_fav_tracks = []
                for genre_name in fav_genres_dict.keys():
                    all_fav_tracks.extend(
                        self.get_tracks_from_data(
                            genre_name,
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_fav_tracks

            elif data == "all_favorite_composers":
                fav_comp_dict = favorites.get("composers", {})
                all_fav_tracks = []
                for comp_name in fav_comp_dict.keys():
                    all_fav_tracks.extend(
                        self.get_tracks_from_data(
                            {"type": "composer", "data": comp_name},
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_fav_tracks

            elif data == "all_favorite_folders":
                fav_folders_dict = favorites.get("folders", {})
                all_fav_tracks = []
                for path in fav_folders_dict.keys():
                    all_fav_tracks.extend(
                        self.get_tracks_from_data(
                            path,
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_fav_tracks

            elif data == "all_favorite_playlists":
                fav_playlists_dict = favorites.get("playlists", {})
                all_fav_tracks = []
                for path in fav_playlists_dict.keys():
                    all_fav_tracks.extend(
                        self.get_tracks_from_data(
                            path,
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_fav_tracks

            elif os.path.isdir(data):
                return sorted(
                    [t for t in self.all_tracks if t["path"].startswith(data)],
                    key=lambda t: t.get("path"),
                )

            elif os.path.isfile(data) and data.lower().endswith((".m3u", ".m3u8")):
                return library_manager.load_playlist(data, self.path_to_track_map)

            elif data == "all_tracks":
                final_tracks = []
                for _, tracks in self.sorted_songs_groups:
                    final_tracks.extend(
                        sorted(
                            tracks,
                            key=lambda t: (
                                t.get("discnumber", 0),
                                t.get("tracknumber", 0),
                            ),
                        )
                    )
                return final_tracks

            elif data == "favorite_tracks":
                fav_tracks_dict = favorites.get("tracks", {})
                reverse_sort = favorite_tracks_sort_mode == SortMode.DATE_ADDED_DESC
                sorted_paths = sorted(
                    fav_tracks_dict.keys(),
                    key=lambda path: fav_tracks_dict[path],
                    reverse=reverse_sort,
                )
                return [
                    self.path_to_track_map[path]
                    for path in sorted_paths
                    if path in self.path_to_track_map
                ]

            elif data == "all_top_tracks":
                return self.sorted_tracks_by_play_count

            elif data == "all_top_artists":
                sorted_artists = sorted(
                    [
                        item
                        for item in self.artists_data.items()
                        if item[1].get("entity_rating", 0) > 0
                    ],
                    key=lambda i: i[1].get("entity_rating", 0),
                    reverse=True,
                )
                all_top_tracks = []
                for artist_name, _ in sorted_artists:
                    all_top_tracks.extend(
                        self.get_tracks_from_data(
                            artist_name,
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_top_tracks

            elif data == "all_top_albums":
                sorted_albums = sorted(
                    [
                        item
                        for item in self.albums_data.items()
                        if item[1].get("entity_rating", 0) > 0
                    ],
                    key=lambda i: i[1].get("entity_rating", 0),
                    reverse=True,
                )
                all_top_tracks = []
                for album_key, _ in sorted_albums:
                    all_top_tracks.extend(
                        self.get_tracks_from_data(
                            album_key,
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_top_tracks

            elif data == "all_top_genres":
                sorted_genres = sorted(
                    [
                        item
                        for item in self.genres_data.items()
                        if item[1].get("entity_rating", 0) > 0
                    ],
                    key=lambda i: i[1].get("entity_rating", 0),
                    reverse=True,
                )
                all_top_tracks = []
                for genre_name, _ in sorted_genres:
                    all_top_tracks.extend(
                        self.get_tracks_from_data(
                            genre_name,
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_top_tracks

            elif data == "all_top_composers":
                sorted_composers = sorted(
                    [
                        item
                        for item in self.composers_data.items()
                        if item[1].get("entity_rating", 0) > 0
                    ],
                    key=lambda i: i[1].get("entity_rating", 0),
                    reverse=True,
                )
                all_top_tracks = []
                for comp_name, _ in sorted_composers:
                    all_top_tracks.extend(
                        self.get_tracks_from_data(
                            {"type": "composer", "data": comp_name},
                            library_manager,
                            artist_album_sort_mode,
                            favorite_tracks_sort_mode,
                            favorites,
                        )
                    )
                return all_top_tracks

        return []

    def get_best_metadata_for_key(self, key, item_type):
        """
        Finds the name and path to the original cover for an encyclopedia key.
        Ignores path differences for albums (CD1/CD2).
        """
        name = str(key)
        image_path = None

        if item_type == "album" and isinstance(key, (list, tuple)):
            name = key[1]
            search_key = tuple(key[:3])

            for k, data in self.albums_data.items():
                if tuple(k[:3]) == search_key:
                    art_dict = data.get("artwork")
                    if art_dict:
                        sizes = sorted([int(s) for s in art_dict.keys() if s.isdigit()])
                        if sizes:
                            image_path = art_dict.get(str(sizes[-1]))
                    break

        elif item_type in ["artist", "composer", "genre"]:
            data = None
            if item_type == "artist":
                data = self.artists_data.get(key)
            elif item_type == "composer":
                data = self.composers_data.get(key)
            elif item_type == "genre":
                data = self.genres_data.get(key)

            if data:
                name = key
                artworks = data.get("artworks", [])
                if artworks:
                    art_dict = artworks[0]
                    sizes = sorted([int(s) for s in art_dict.keys() if s.isdigit()])
                    if sizes:
                        image_path = art_dict.get(str(sizes[-1]))

        if not name and not image_path:
            return None

        return {"name": name, "image_path": image_path}


class LibraryProcessor(QObject):
    """
    A background worker class responsible for scanning the file system,
    parsing media files, and building the library database.
    """

    finished = pyqtSignal(dict)
    progressUpdated = pyqtSignal(int, int)

    def __init__(
        self,
        library_paths,
        artist_source_tag,
        ignore_genre_case,
        play_stats,
        tracks_to_process=None,
        artist_artworks=None,
        composer_artworks=None,
        genre_artworks=None,
        partial_scan_paths=None,
        blacklist=None,
        treat_folders_as_unique=False,
        old_date_map=None,
        charts_period=ChartsPeriod.MONTHLY,
        encyclopedia_manager=None,
    ):
        """
        Initializes the library processor with configuration parameters such as
        library paths, sorting preferences, existing statistics, and artwork overrides.
        """
        super().__init__()
        self.library_paths = library_paths
        self.artist_source_tag = artist_source_tag
        self.ignore_genre_case = ignore_genre_case
        self.treat_folders_as_unique = treat_folders_as_unique
        self.play_stats = play_stats
        self.tracks_to_process = tracks_to_process
        self.library_manager = LibraryManager()
        self.artist_artworks = artist_artworks if artist_artworks else {}
        self.genre_artworks = genre_artworks if genre_artworks else {}
        self.composer_artworks = composer_artworks if composer_artworks else {}
        self.partial_scan_paths = partial_scan_paths
        self.old_date_map = old_date_map if old_date_map else {}
        self.blacklist = blacklist if blacklist else {}
        self.user_initiated = True
        self.charts_period = charts_period
        self.encyclopedia_manager = encyclopedia_manager

    def run(self):
        """
        Executes the main library scanning and processing routine. Extracts metadata,
        handles CUE sheets, applies blacklists, aggregates entities (artists, albums,
        genres, etc.), and emits the final compiled dictionary.
        """
        files_to_scan = []
        existing_tracks = []

        paths_to_discover = []
        if self.partial_scan_paths:
            paths_to_discover = self.partial_scan_paths
            existing_tracks = (
                self.tracks_to_process if self.tracks_to_process is not None else []
            )
        elif self.tracks_to_process is not None:
            existing_tracks = self.tracks_to_process
        else:
            paths_to_discover = self.library_paths

        cue_files_map = {}
        files_covered_by_cue = set()

        if paths_to_discover:
            temp_files_to_scan = []
            processed_paths = set()

            for path in paths_to_discover:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            if file.lower().endswith(".cue"):
                                cue_full_path = os.path.join(root, file)
                                is_split_cue = False
                                try:
                                    with open(
                                        cue_full_path,
                                        "r",
                                        encoding="utf-8",
                                        errors="ignore",
                                    ) as f:
                                        content = f.read()
                                        if content.upper().count('FILE "') > 1:
                                            is_split_cue = True
                                except Exception:
                                    pass

                                if is_split_cue:
                                    continue

                                audio_filename, tracks = parse_cue_sheet(cue_full_path)
                                if audio_filename and tracks:
                                    audio_full_path = os.path.normpath(
                                        os.path.join(root, audio_filename)
                                    )
                                    if os.path.exists(audio_full_path):
                                        cue_files_map[audio_full_path] = tracks
                                        files_covered_by_cue.add(audio_full_path)

            for path in paths_to_discover:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            if file.lower().endswith(
                                self.library_manager.supported_formats
                            ):
                                full_path = os.path.normpath(os.path.join(root, file))
                                if full_path in files_covered_by_cue:
                                    continue
                                if full_path not in processed_paths:
                                    temp_files_to_scan.append(full_path)
                                    processed_paths.add(full_path)
                elif os.path.isfile(path):
                    if path.lower().endswith(self.library_manager.supported_formats):
                        full_path = os.path.normpath(path)
                        if full_path in files_covered_by_cue:
                            continue
                        if full_path not in processed_paths:
                            temp_files_to_scan.append(full_path)
                            processed_paths.add(full_path)

            if self.partial_scan_paths:
                existing_paths = {track["path"] for track in existing_tracks}
                files_to_scan = [
                    f
                    for f in temp_files_to_scan
                    if os.path.normpath(f) not in existing_paths
                ]
            else:
                files_to_scan = temp_files_to_scan

        newly_scanned_tracks = []

        for audio_path, tracks in cue_files_map.items():
            base_meta = self.library_manager.get_track_metadata(audio_path)
            total_file_duration_ms = base_meta.get("duration", 0) * 1000

            for t in tracks:
                v_track = base_meta.copy()
                v_track["path"] = f"{audio_path}::{t['number']}"
                v_track["title"] = t.get("title") or f"Track {t['number']}"

                if t.get("album"):
                    v_track["album"] = t["album"]

                if t.get("album_artist"):
                    v_track["album_artist"] = t["album_artist"]

                if t.get("artist"):
                    raw_artist = t["artist"]
                    artists_list = [a.strip() for a in raw_artist.split(";") if a.strip()]

                    if artists_list:
                        v_track["artists"] = artists_list
                        v_track["artist"] = artists_list[0]
                    else:
                        v_track["artists"] = [raw_artist]
                        v_track["artist"] = raw_artist

                if t.get("composer"):
                    v_track["composer"] = t["composer"]

                v_track["tracknumber"] = t["number"]
                v_track["is_virtual"] = True
                v_track["real_path"] = audio_path
                v_track["start_ms"] = t.get("start_ms", 0)
                dur = t.get("duration_ms", 0)
                if dur == 0:
                    dur = max(0, total_file_duration_ms - v_track["start_ms"])
                v_track["duration"] = int(dur / 1000)
                v_track["duration_ms"] = dur
                if old_date := self.old_date_map.get(v_track["path"]):
                    v_track["date_added"] = old_date
                newly_scanned_tracks.append(v_track)

        total = len(files_to_scan)
        if total > 0:
            for i, file_path in enumerate(files_to_scan):
                track_data = self.library_manager.get_track_metadata(file_path)
                if old_date := self.old_date_map.get(file_path):
                    track_data["date_added"] = old_date
                newly_scanned_tracks.append(track_data)
                self.progressUpdated.emit(i + 1, total)
        else:
            self.progressUpdated.emit(0, 0)

        all_tracks = existing_tracks + newly_scanned_tracks

        current_time = time.time()
        for track in all_tracks:
            if "date_added" not in track or not track["date_added"]:
                track["date_added"] = current_time

        if self.blacklist:
            bl_artists = set(self.blacklist.get("artists", []))
            bl_albums = set(tuple(a) for a in self.blacklist.get("albums", []))
            bl_tracks = set(self.blacklist.get("tracks", []))
            bl_folders = [
                os.path.normpath(f) for f in self.blacklist.get("folders", [])
            ]
            bl_composers = set(self.blacklist.get("composers", []))

            filtered_tracks = []
            for track in all_tracks:
                track_path_check = track["path"]
                real_path = track.get("real_path", track["path"])
                track_path_norm = os.path.normpath(real_path)

                if track_path_check in bl_tracks:
                    continue

                if any(track_path_norm == folder or track_path_norm.startswith(folder + os.sep) for folder in bl_folders):
                    continue

                if track.get("album_artist") in bl_artists or any(
                    artist in bl_artists for artist in track.get("artists", [])
                ):
                    continue

                album_title = track.get("album", translate("Unknown Album"))
                album_artist = track.get("album_artist", translate("Unknown Artist"))
                key_year = track.get("year", 0)

                if self.treat_folders_as_unique:
                    album_key = (album_artist, album_title, key_year, os.path.dirname(track_path_norm))
                else:
                    album_key = (album_artist, album_title, key_year)

                if album_key in bl_albums:
                    continue

                track_composers = []
                if comp_raw := track.get("composer"):
                    track_composers = [
                        c.strip() for c in re.split(r"[;/]", comp_raw) if c.strip()
                    ]
                if any(comp in bl_composers for comp in track_composers):
                    continue

                filtered_tracks.append(track)
            all_tracks = filtered_tracks

        artists_data, albums_data, genres_data, composers_data = {}, {}, {}, {}

        stat_key = (
            "monthly" if self.charts_period == ChartsPeriod.MONTHLY else "all_time"
        )

        stats_tracks = self.play_stats.get("tracks", {})
        stats_artists = self.play_stats.get("artists", {})
        stats_albums = self.play_stats.get("albums", {})
        stats_genres = self.play_stats.get("genres", {})
        stats_composers = self.play_stats.get("composers", {})

        temp_artists = defaultdict(
            lambda: {
                "albums": set(),
                "tracks": [],
                "total_duration": 0,
                "track_play_count": 0,
            }
        )
        temp_albums = defaultdict(
            lambda: {
                "tracks": [],
                "total_duration": 0,
                "year": 9999,
                "track_play_count": 0,
            }
        )
        temp_genres = defaultdict(
            lambda: {
                "albums": set(),
                "tracks": [],
                "total_duration": 0,
                "track_play_count": 0,
            }
        )
        temp_composers = defaultdict(
            lambda: {
                "albums": set(),
                "tracks": [],
                "total_duration": 0,
                "track_play_count": 0,
            }
        )

        genre_case_map = {}
        all_music_folders = set()
        sorted_tracks_with_play_count = []

        for track in all_tracks:
            real_path = track.get("real_path", track["path"])
            all_music_folders.add(os.path.dirname(real_path))

            track_stats = stats_tracks.get(track["path"], {})

            track_play_count = (
                track_stats.get(stat_key, 0) if isinstance(track_stats, dict) else 0
            )

            track["play_count"] = track_play_count
            if track_play_count > 0:
                sorted_tracks_with_play_count.append(track)

            track_artists = (
                track.get("artists", [translate("Unknown Artist")])
                if self.artist_source_tag == "artist"
                else [track.get("album_artist", translate("Unknown Artist"))]
            )
            if not track_artists or not any(track_artists):
                track_artists = [track.get("album_artist", translate("Unknown Artist"))]
            if not track_artists or not any(track_artists):
                track_artists = [translate("Unknown Artist")]

            album_title = track.get("album", translate("Unknown Album"))
            album_artist = track.get("album_artist", translate("Unknown Artist"))

            key_year = track.get("year", 0)

            if self.treat_folders_as_unique:
                album_key = (
                    album_artist,
                    album_title,
                    key_year,
                    os.path.dirname(real_path),
                )
            else:
                album_key = (album_artist, album_title, key_year)

            for artist in track_artists:
                temp_artists[artist]["albums"].add(album_key)
                temp_artists[artist]["tracks"].append(track)
                temp_artists[artist]["total_duration"] += track.get("duration", 0)
                temp_artists[artist]["track_play_count"] += track_play_count
                if (
                    "date_added" not in temp_artists[artist]
                    or track["date_added"] < temp_artists[artist]["date_added"]
                ):
                    temp_artists[artist]["date_added"] = track["date_added"]

            current_album_artist = track.get("album_artist")
            if (
                current_album_artist
                and current_album_artist != translate("Unknown Artist")
                and current_album_artist not in track_artists
            ):
                temp_artists[current_album_artist]["albums"].add(album_key)
                temp_artists[current_album_artist]["tracks"].append(track)
                temp_artists[current_album_artist]["total_duration"] += track.get(
                    "duration", 0
                )
                temp_artists[current_album_artist][
                    "track_play_count"
                ] += track_play_count
                if (
                    "date_added" not in temp_artists[current_album_artist]
                    or track["date_added"]
                    < temp_artists[current_album_artist]["date_added"]
                ):
                    temp_artists[current_album_artist]["date_added"] = track[
                        "date_added"
                    ]

            track_genres = track.get("genre", [])
            for genre in track_genres:
                key = genre.lower() if self.ignore_genre_case else genre
                if key not in genre_case_map:
                    genre_case_map[key] = genre
                display_genre = genre_case_map[key]

                temp_genres[display_genre]["albums"].add(album_key)
                temp_genres[display_genre]["tracks"].append(track)
                temp_genres[display_genre]["total_duration"] += track.get("duration", 0)
                temp_genres[display_genre]["track_play_count"] += track_play_count
                if (
                    "date_added" not in temp_genres[display_genre]
                    or track["date_added"] < temp_genres[display_genre]["date_added"]
                ):
                    temp_genres[display_genre]["date_added"] = track["date_added"]

            composer_raw = track.get("composer")
            if composer_raw:
                composers_list = [
                    c.strip() for c in re.split(r"[;/]", composer_raw) if c.strip()
                ]
                for composer in composers_list:
                    temp_composers[composer]["albums"].add(album_key)
                    temp_composers[composer]["tracks"].append(track)
                    temp_composers[composer]["total_duration"] += track.get(
                        "duration", 0
                    )
                    temp_composers[composer]["track_play_count"] += track_play_count
                    if (
                        "date_added" not in temp_composers[composer]
                        or track["date_added"] < temp_composers[composer]["date_added"]
                    ):
                        temp_composers[composer]["date_added"] = track["date_added"]

            temp_albums[album_key]["tracks"].append(track)
            temp_albums[album_key]["total_duration"] += track.get("duration", 0)
            temp_albums[album_key]["track_play_count"] += track_play_count
            if (
                "date_added" not in temp_albums[album_key]
                or track["date_added"] < temp_albums[album_key]["date_added"]
            ):
                temp_albums[album_key]["date_added"] = track["date_added"]

            track_year = track.get("year", 0)
            if 1000 < track_year < temp_albums[album_key]["year"]:
                temp_albums[album_key]["year"] = track_year

        for artist, data in temp_artists.items():
            artist_artworks = []
            seen_artworks = set()
            sorted_albums = sorted(
                list(data["albums"]), key=lambda x: temp_albums[x].get("year", 0)
            )

            for album_key in sorted_albums:
                album_artwork_dict = next(
                    (
                        t.get("artwork")
                        for t in temp_albums[album_key]["tracks"]
                        if t.get("artwork")
                    ),
                    None,
                )
                if album_artwork_dict:
                    artwork_key = next(iter(sorted(album_artwork_dict.values())), None)
                    if artwork_key and artwork_key not in seen_artworks:
                        artist_artworks.append(album_artwork_dict)
                        seen_artworks.add(artwork_key)

            preferred_artwork_path = self.artist_artworks.get(artist)
            if preferred_artwork_path:
                found_in_albums = False
                for art_dict in artist_artworks:
                    if preferred_artwork_path in art_dict.values():
                        artist_artworks.remove(art_dict)
                        artist_artworks.insert(0, art_dict)
                        found_in_albums = True
                        break

                if not found_in_albums and os.path.exists(preferred_artwork_path):
                    new_art_dict = {"512": preferred_artwork_path}
                    artist_artworks.insert(0, new_art_dict)

            artist_stats = stats_artists.get(artist, {})
            entity_rating = (
                artist_stats.get(stat_key, 0) if isinstance(artist_stats, dict) else 0
            )

            artists_data[artist] = {
                "album_count": len(data["albums"]),
                "track_count": len(data["tracks"]),
                "total_duration": data["total_duration"],
                "artworks": artist_artworks[:4],
                "albums": sorted(list(data["albums"])),
                "track_play_count": data["track_play_count"],
                "entity_rating": entity_rating,
                "date_added": data.get("date_added", current_time),
            }

        for album_key, data in temp_albums.items():
            first_artwork_dict = next(
                (t.get("artwork") for t in data["tracks"] if t.get("artwork")), None
            )
            year = data["year"] if data["year"] != 9999 else 0
            album_genres = set()
            for track in data["tracks"]:
                if track_genres := track.get("genre"):
                    if self.ignore_genre_case:
                        canonical_genres = {
                            genre_case_map.get(g.lower(), g) for g in track_genres
                        }
                        album_genres.update(canonical_genres)
                    else:
                        album_genres.update(track_genres)

            album_key_str = json.dumps(list(album_key))
            album_stats = stats_albums.get(album_key_str, {})
            entity_rating = (
                album_stats.get(stat_key, 0) if isinstance(album_stats, dict) else 0
            )

            albums_data[album_key] = {
                "album_artist": album_key[0],
                "track_count": len(data["tracks"]),
                "total_duration": data["total_duration"],
                "artwork": first_artwork_dict,
                "year": year,
                "tracks": data["tracks"],
                "genre": sorted(list(album_genres)),
                "track_play_count": data["track_play_count"],
                "entity_rating": entity_rating,
                "date_added": data.get("date_added", current_time),
            }

        for genre, data in temp_genres.items():
            genre_artworks = []
            seen_artworks = set()
            sorted_albums = sorted(
                list(data["albums"]), key=lambda x: temp_albums[x].get("year", 0)
            )

            preferred_artwork_path = self.genre_artworks.get(genre)
            found_priority_dict = None

            for album_key in sorted_albums:
                if len(genre_artworks) >= 4 and (
                    not preferred_artwork_path or found_priority_dict
                ):
                    break
                album_artwork_dict = next(
                    (
                        t.get("artwork")
                        for t in temp_albums[album_key]["tracks"]
                        if t.get("artwork")
                    ),
                    None,
                )

                if album_artwork_dict:
                    artwork_key = next(iter(sorted(album_artwork_dict.values())), None)
                    is_preferred = False
                    if preferred_artwork_path and artwork_key:
                        if preferred_artwork_path in album_artwork_dict.values():
                            is_preferred = True
                            found_priority_dict = album_artwork_dict
                    if artwork_key and artwork_key not in seen_artworks:
                        if len(genre_artworks) < 4 or is_preferred:
                            genre_artworks.append(album_artwork_dict)
                            seen_artworks.add(artwork_key)

            if found_priority_dict and found_priority_dict in genre_artworks:
                genre_artworks.remove(found_priority_dict)
                genre_artworks.insert(0, found_priority_dict)
            elif preferred_artwork_path and os.path.exists(preferred_artwork_path):
                new_art_dict = {"512": preferred_artwork_path}
                genre_artworks.insert(0, new_art_dict)

            genre_artworks = genre_artworks[:4]

            genre_stats = stats_genres.get(genre, {})
            entity_rating = (
                genre_stats.get(stat_key, 0) if isinstance(genre_stats, dict) else 0
            )

            genres_data[genre] = {
                "album_count": len(data["albums"]),
                "track_count": len(data["tracks"]),
                "total_duration": data["total_duration"],
                "artworks": genre_artworks,
                "albums": data["albums"],
                "track_play_count": data["track_play_count"],
                "entity_rating": entity_rating,
                "date_added": data.get("date_added", current_time),
            }

        for composer, data in temp_composers.items():
            composer_artworks = []
            seen_artworks = set()
            sorted_albums = sorted(
                list(data["albums"]), key=lambda x: temp_albums[x].get("year", 0)
            )

            preferred_artwork_path = self.composer_artworks.get(composer)
            found_priority_dict = None

            for album_key in sorted_albums:
                if len(composer_artworks) >= 4 and (
                    not preferred_artwork_path or found_priority_dict
                ):
                    break
                album_artwork_dict = next(
                    (
                        t.get("artwork")
                        for t in temp_albums[album_key]["tracks"]
                        if t.get("artwork")
                    ),
                    None,
                )

                if album_artwork_dict:
                    artwork_key = next(iter(sorted(album_artwork_dict.values())), None)
                    is_preferred = False
                    if preferred_artwork_path and artwork_key:
                        if preferred_artwork_path in album_artwork_dict.values():
                            is_preferred = True
                            found_priority_dict = album_artwork_dict

                    if artwork_key and artwork_key not in seen_artworks:
                        if len(composer_artworks) < 4 or is_preferred:
                            composer_artworks.append(album_artwork_dict)
                            seen_artworks.add(artwork_key)

            if found_priority_dict and found_priority_dict in composer_artworks:
                composer_artworks.remove(found_priority_dict)
                composer_artworks.insert(0, found_priority_dict)
            elif preferred_artwork_path and os.path.exists(preferred_artwork_path):
                new_art_dict = {"512": preferred_artwork_path}
                composer_artworks.insert(0, new_art_dict)

            composer_artworks = composer_artworks[:4]

            comp_stats = stats_composers.get(composer, {})
            entity_rating = (
                comp_stats.get(stat_key, 0) if isinstance(comp_stats, dict) else 0
            )

            composers_data[composer] = {
                "album_count": len(data["albums"]),
                "track_count": len(data["tracks"]),
                "total_duration": data["total_duration"],
                "artworks": composer_artworks,
                "albums": sorted(list(data["albums"])),
                "track_play_count": data["track_play_count"],
                "entity_rating": entity_rating,
                "date_added": data.get("date_added", current_time),
            }

        enc_data = {}
        if self.encyclopedia_manager:
            enc_data = self.encyclopedia_manager.load_data()

        try:
            available_tracks = set(track["path"] for track in all_tracks)
            available_albums = set(albums_data.keys())
            available_artists = set(artists_data.keys())
            available_genres = set(genres_data.keys())
            available_composers = set(composers_data.keys())

            current_favorites = self.library_manager.load_favorites()
            current_unavailable = self.library_manager.load_unavailable_favorites()

            new_favorites = defaultdict(dict)
            new_unavailable = defaultdict(dict)

            available_item_sets = {
                "tracks": available_tracks,
                "albums": available_albums,
                "artists": available_artists,
                "genres": available_genres,
                "composers": available_composers,
            }

            key_map = {
                "tracks": "tracks",
                "albums": "albums",
                "artists": "artists",
                "genres": "genres",
                "folders": "folders",
                "playlists": "playlists",
                "composers": "composers",
            }

            def is_item_available(item_data_key, item_type):
                if item_type in available_item_sets:
                    return item_data_key in available_item_sets[item_type]
                if item_type in ["folders", "playlists"]:
                    return os.path.exists(item_data_key)
                return False

            for item_type_key, items_dict in current_favorites.items():
                if item_type_key not in key_map:
                    continue

                for item_key_str, timestamp in items_dict.items():
                    item_data_key = (
                        json.loads(item_key_str)
                        if item_type_key == "albums"
                        else item_key_str
                    )
                    check_key = (
                        tuple(item_data_key)
                        if item_type_key == "albums"
                        else item_data_key
                    )

                    if is_item_available(check_key, item_type_key):
                        new_favorites[item_type_key][item_key_str] = timestamp
                    else:
                        new_unavailable[item_type_key][item_key_str] = timestamp

            for item_type_key, items_dict in current_unavailable.items():
                if item_type_key not in key_map:
                    continue

                for item_key_str, timestamp in items_dict.items():
                    item_data_key = (
                        json.loads(item_key_str)
                        if item_type_key == "albums"
                        else item_key_str
                    )
                    check_key = (
                        tuple(item_data_key)
                        if item_type_key == "albums"
                        else item_data_key
                    )

                    if is_item_available(check_key, item_type_key):
                        new_favorites[item_type_key][item_key_str] = timestamp
                    else:
                        new_unavailable[item_type_key][item_key_str] = timestamp

            self.library_manager.save_favorites(new_favorites)
            self.library_manager.save_unavailable_favorites(new_unavailable)

        except Exception as e:
            print(f"Error reconciling favorites: {e}")

        sorted_songs_groups = []
        for album_key, data in temp_albums.items():
            sorted_songs_groups.append((album_key, data["tracks"]))

        sorted_tracks_by_play_count = sorted(
            sorted_tracks_with_play_count, key=lambda t: t["play_count"], reverse=True
        )

        result = {
            "all_tracks": all_tracks,
            "artists_data": artists_data,
            "albums_data": albums_data,
            "genres_data": genres_data,
            "composers_data": composers_data,
            "sorted_artists": sorted(artists_data.items()),
            "sorted_albums": sorted(albums_data.items()),
            "sorted_genres": sorted(genres_data.items()),
            "sorted_composers": sorted(composers_data.items()),
            "sorted_songs_groups": sorted_songs_groups,
            "sorted_tracks_by_play_count": sorted_tracks_by_play_count,
            "all_music_folders": sorted(list(all_music_folders)),
        }
        self.finished.emit(result)


class PlaylistIndexingWorker(QObject):
    """Background worker for indexing playlist contents."""

    finished = pyqtSignal()
    playlist_indexed = pyqtSignal(str, list)

    def __init__(self, playlists_dir):
        """
        Initializes the worker with the directory containing playlists.
        """
        super().__init__()
        self.playlists_dir = playlists_dir

    def run(self):
        """
        Reads all m3u/m3u8 playlists in the directory, parses their track paths,
        and emits the indexed data.
        """
        if not self.playlists_dir.exists():
            self.finished.emit()
            return
        try:
            for filename in os.listdir(self.playlists_dir):
                if not filename.lower().endswith((".m3u", ".m3u8")):
                    continue
                full_path = os.path.join(self.playlists_dir, filename)
                track_paths = []
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if os.path.isabs(line):
                            track_paths.append(os.path.normpath(line))
                        else:
                            track_paths.append(
                                os.path.normpath(os.path.join(self.playlists_dir, line))
                            )
                    self.playlist_indexed.emit(full_path, track_paths)
                except Exception as e:
                    print(f"Error indexing playlist {filename}: {e}")
        except Exception as e:
            print(f"Critical error in playlist worker: {e}")
        self.finished.emit()


class LibraryChangeChecker(QObject):
    """
    A background worker class that checks for modifications, additions,
    or deletions in the monitored library directories against a cached structure.
    """
    finished = pyqtSignal(bool, list, list)

    def __init__(self, library_paths, cached_structure, supported_extensions):
        """
        Initializes the checker with target library paths, the previously cached
        file structure, and a list of supported audio extensions.
        """
        super().__init__()
        self.library_paths = [os.path.normpath(p) for p in library_paths]
        self.cached_structure = {os.path.normpath(k): v for k, v in cached_structure.items()}
        self.supported_extensions = supported_extensions
        self._is_running = True

    def run(self):
        """
        Executes the file system scan to detect changes (modified, new, or removed files)
        and emits the results.
        """
        print("[LibraryChecker] Starting background check...")
        if not self.cached_structure:
            self.finished.emit(False, [], [])
            return

        changed_files = []
        removed_files = []
        current_files_on_disk = set()

        for path in self.library_paths:
            if not os.path.exists(path):
                continue

            for root, _, files in os.walk(path):
                if not self._is_running: break

                for file in files:
                    if file.lower().endswith(self.supported_extensions):
                        full_path = os.path.normpath(os.path.join(root, file))
                        current_files_on_disk.add(full_path)

                        saved_state = self.cached_structure.get(full_path)

                        if not saved_state:
                            changed_files.append(("new", full_path))
                            continue

                        try:
                            stat = os.stat(full_path)
                            curr_size = stat.st_size
                            curr_mtime = stat.st_mtime

                            saved_size = saved_state[0]
                            saved_mtime = saved_state[1]

                            if (curr_size != saved_size) or (abs(curr_mtime - saved_mtime) > 2.0):
                                changed_files.append(("modified", full_path))

                        except OSError:
                            pass

        if self._is_running:
            for cached_path in self.cached_structure.keys():
                is_managed = any(cached_path.startswith(lib) for lib in self.library_paths)

                if is_managed and cached_path not in current_files_on_disk:
                    removed_files.append(cached_path)

        has_changes = (len(changed_files) > 0 or len(removed_files) > 0)

        print(f"[LibraryChecker] Finished. New/Mod: {len(changed_files)}, Removed: {len(removed_files)}")
        self.finished.emit(has_changes, changed_files, removed_files)

    def stop(self):
        """
        Safely stops the background scanning process.
        """
        self._is_running = False