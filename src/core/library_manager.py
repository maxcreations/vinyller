"""
Vinyller — Library manager
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

import base64
import hashlib
import io
import json
import os
import random
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import mutagen
import mutagen.asf
import mutagen.oggvorbis
from PIL import Image
from mutagen.aac import AAC
from mutagen.flac import FLAC, Picture
from mutagen.id3 import (
    COMM, TCOP, WOAS, WXXX, TBPM, TSRC, TMED, TENC, TSSE, TDOR, TDRC,
    TIT2, TPE1, TPE2, TALB, TCOM, TCON, TRCK, TPOS, APIC, USLT, ID3
)
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.wave import WAVE
from send2trash import send2trash

from src.encyclopedia.encyclopedia_manager import EncyclopediaManager
from src.utils.constants import (
    HISTORY_LIMIT,
    VINYLLER_FOLDER, MY_WAVE_OVERSAMPLE_MULTIPLIER, MY_WAVE_BONUS_FAV_GENRE, MY_WAVE_BONUS_FAV_ALBUM,
    MY_WAVE_BONUS_FAV_ARTIST, MY_WAVE_BONUS_FAV_TRACK, MY_WAVE_BASE_SCORE, MY_WAVE_SAMPLE_POOL_SIZE,
    MY_WAVE_DEFAULT_LIMIT
)
from src.utils.utils_translator import translate


class LibraryManager:
    """
    A class for scanning the music library, extracting metadata,
    caching, and managing application settings and statistics.
    """

    def __init__(self):
        """
        Initializes the LibraryManager, sets up supported formats, creates
        necessary application data directories, and defines file paths for
        various configurations, caches, and statistics.
        """
        self.supported_formats = (
            ".mp3",
            ".flac",
            ".ogg",
            ".wav",
            ".m4a",
            ".mp4",
            ".wma",
            ".aac",
        )
        self.artwork_sizes = (512, 128, 48)
        self.app_data_dir = Path.home() / VINYLLER_FOLDER
        self.cache_dir = self.app_data_dir / "cache"
        self.artwork_cache_dir = self.app_data_dir / "artwork"
        self.playlists_dir = Path.home() / "Music" / "Playlists"
        self.settings_path = self.app_data_dir / "settings.json"
        self.last_queue_path = self.app_data_dir / "last_queue.json"
        self.last_view_path = self.app_data_dir / "last_view.json"
        self.favorites_path = self.app_data_dir / "favorites.json"
        self.artist_artworks_path = self.app_data_dir / "artist_artworks.json"
        self.genre_artworks_path = self.app_data_dir / "genre_artworks.json"
        self.composer_artworks_path = self.app_data_dir / "composer_artworks.json"
        self.blacklist_path = self.app_data_dir / "blacklist.json"
        self.unavailable_favorites_path = (
            self.app_data_dir / "unavailable_favorites.json"
        )
        self.pending_updates_path = self.app_data_dir / "pending_updates.json"
        self.playback_history_path = self.app_data_dir / "playback_history.json"
        self.play_stats_path = self.app_data_dir / "play_stats.json"
        self.play_stats_log_path = self.app_data_dir / "play_stats.log"
        self.charts_archive_path = self.app_data_dir / "charts_archive.json"
        self.external_cache_path = self.app_data_dir / "external_tracks_cache.json"
        self.search_links_path = self.app_data_dir / "search_links.json"
        self.disabled_search_providers_path = (
            self.app_data_dir / "disabled_search_providers.json"
        )
        self.structure_cache_path = self.app_data_dir / "library_structure.json"

        self.last_played_entity_metadata = {
            "album_key": None,
            "album_artist": None,
            "genres": set(),
        }

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.artwork_cache_dir.mkdir(parents=True, exist_ok=True)
        self.playlists_dir.mkdir(parents=True, exist_ok=True)
        self.folder_artwork_cache = {}

        self.playlists_index = {}
        self.playlists_metadata = {}
        self.external_tracks_cache = self.load_external_cache()

        self.encyclopedia_manager = EncyclopediaManager(self.app_data_dir)

    def save_library_structure(self, library_paths):
        """
        Saves a snapshot of the physical library structure to a JSON file,
        independently of blacklists or memory caches.
        """
        print("[LibraryManager] Saving physical library structure snapshot...")
        structure = {}
        for path in library_paths:
            if not os.path.isdir(path):
                continue
            for root, _, files in os.walk(path):
                for file in files:
                    if file.lower().endswith(self.supported_formats):
                        full_path = os.path.normpath(os.path.join(root, file))
                        try:
                            stat = os.stat(full_path)
                            structure[full_path] = [stat.st_size, stat.st_mtime]
                        except OSError:
                            pass

        try:
            with open(self.structure_cache_path, "w", encoding="utf-8") as f:
                json.dump(structure, f)
            print(f"[LibraryManager] Snapshot saved. Tracks: {len(structure)}")
        except IOError as e:
            print(f"[LibraryManager] Failed to save snapshot: {e}")

    def load_library_structure(self) -> dict:
        """
        Loads the previously saved library structure snapshot from disk.
        Returns an empty dictionary if the cache file does not exist or fails to load.
        """
        if not self.structure_cache_path.exists():
            return {}
        try:
            with open(self.structure_cache_path, "r", encoding = "utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def load_external_cache(self) -> dict:
        """
        Loads the cache containing metadata for tracks located outside the main library paths.
        """
        if not self.external_cache_path.exists():
            return {}
        try:
            with open(self.external_cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_external_cache(self):
        """
        Saves the external tracks cache to disk.
        """
        try:
            with open(self.external_cache_path, "w", encoding="utf-8") as f:
                json.dump(self.external_tracks_cache, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def get_playlist_track_set(self, playlist_path):
        """
        Returns a set of track paths belonging to the specified playlist.
        """
        return set(self.playlists_index.get(playlist_path, []))

    def update_index_entry(self, path, tracks_list):
        """
        Updates the internal playlist index with a new list of tracks for a given path,
        and invalidates its cached metadata.
        """
        self.playlists_index[path] = tracks_list
        if path in self.playlists_metadata:
            del self.playlists_metadata[path]

    def get_playlist_metadata(self, playlist_path, all_tracks_map):
        """
        Retrieves metadata (track count, total duration, artwork) for a specific playlist.
        Uses cached metadata if the file modification time hasn't changed.
        """
        try:
            current_mtime = os.path.getmtime(playlist_path)
        except OSError:
            current_mtime = 0

        if playlist_path in self.playlists_metadata:
            cached_meta = self.playlists_metadata[playlist_path]
            if cached_meta.get("mtime") == current_mtime:
                return cached_meta
            else:
                if playlist_path in self.playlists_index:
                    del self.playlists_index[playlist_path]

        paths = self.playlists_index.get(playlist_path)
        if paths is None:
            try:
                paths = []
                playlist_dir = os.path.dirname(playlist_path)
                with open(playlist_path, "r", encoding = "utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if os.path.isabs(line):
                            paths.append(os.path.normpath(line))
                        else:
                            paths.append(
                                os.path.normpath(os.path.join(playlist_dir, line))
                            )
                self.playlists_index[playlist_path] = paths
            except Exception as e:
                return {"count": 0, "duration": 0, "artwork": None}

        total_duration = 0
        track_count = 0
        first_artwork = None

        for path in paths:
            track_count += 1
            track = all_tracks_map.get(path)

            if not track:
                track = self.external_tracks_cache.get(path)

            if track:
                total_duration += track.get("duration", 0)
                if first_artwork is None:
                    first_artwork = track.get("artwork")

        meta = {
            "count": track_count,
            "duration": total_duration,
            "artwork": first_artwork,
            "mtime": current_mtime,
        }
        self.playlists_metadata[playlist_path] = meta
        return meta

    def _update_playlist_index(self, playlist_path, tracks):
        """
        Updates the memory index of a playlist with a new list of track dictionaries.
        """
        track_paths = [track["path"] for track in tracks]
        self.playlists_index[playlist_path] = track_paths

    def _fix_encoding(self, text: str) -> str:
        """
        Attempts to fix mojibake encoding issues (typically CP1251 decoded as Latin-1)
        commonly found in older ID3 tags containing Cyrillic characters.
        """
        if not text or not isinstance(text, str):
            return text
        try:
            fixed_text = text.encode("latin-1").decode("cp1251")
            has_cyrillic = bool(re.search(r"[а-яА-Я]", fixed_text))
            has_latin = bool(re.search(r"[a-zA-Z]", fixed_text))
            if not has_cyrillic:
                return text
            if has_cyrillic and has_latin:
                cyrillic_chars = len(re.findall(r"[а-яА-Я]", fixed_text))
                latin_chars = len(re.findall(r"[a-zA-Z]", fixed_text))
                if latin_chars > cyrillic_chars:
                    return text
            return fixed_text
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text

    def load_play_stats(self) -> dict:
        """
        Loads playback statistics from disk. Performs migrations on the data structure
        if an older format is detected, and ensures default keys are present.
        """
        current_month_str = datetime.now().strftime("%Y-%m")
        default_stats = {
            "current_month": current_month_str,
            "tracks": {},
            "artists": {},
            "albums": {},
            "genres": {},
            "playlists": {},
            "folders": {},
            "composers": {},
        }
        if not self.play_stats_path.exists():
            return default_stats
        try:
            with open(self.play_stats_path, "r", encoding="utf-8") as f:
                stats = json.load(f)
            migration_needed = False
            if "current_month" not in stats:
                stats["current_month"] = current_month_str
                migration_needed = True
            if "tracks" in stats and stats["tracks"]:
                first_track_key = next(iter(stats["tracks"]))
                if isinstance(stats["tracks"][first_track_key], (int, float)):
                    migration_needed = True
            if migration_needed:
                stats = self._migrate_old_stats(stats, current_month_str)
                self.save_play_stats(stats)
            for key in default_stats:
                if key not in stats:
                    stats[key] = default_stats[key]
            return stats
        except (json.JSONDecodeError, IOError):
            return default_stats

    def _migrate_old_stats(self, old_stats: dict, current_month: str) -> dict:
        """
        Migrates old playback statistics formats (simple counts) to the newer format
        that separates 'all_time' and 'monthly' play counts.
        """
        new_stats = {
            "current_month": current_month,
            "tracks": {},
            "artists": {},
            "albums": {},
            "genres": {},
            "playlists": {},
            "folders": {},
            "composers": {},
        }
        for key_type in [
            "tracks",
            "artists",
            "albums",
            "genres",
            "playlists",
            "folders",
            "composers",
        ]:
            old_dict = old_stats.get(key_type, {})
            if not isinstance(old_dict, dict):
                continue
            for item_key, count in old_dict.items():
                if isinstance(count, (int, float)):
                    new_stats[key_type][item_key] = {"all_time": count, "monthly": 0}
                elif isinstance(count, dict):
                    new_stats[key_type][item_key] = count
        return new_stats

    def save_play_stats(self, stats: dict):
        """
        Saves the structured playback statistics back to disk.
        """
        try:
            with open(self.play_stats_path, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def process_stats_log(self):
        """
        Reads pending play increments from the statistics log file and merges
        them into the main play statistics JSON file, then clears the log.
        """
        if not self.play_stats_log_path.exists():
            return False
        lines = []
        try:
            with open(self.play_stats_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            os.remove(self.play_stats_log_path)
        except Exception:
            return False
        if not lines:
            return False

        total_stats = self.load_play_stats()
        for line in lines:
            try:
                log_entry = json.loads(line)
                entry_type = log_entry.get("t")
                increment_value = log_entry.get("inc", 1)
                if entry_type == "track":
                    key = log_entry.get("p")
                    if key:
                        current_stats = total_stats["tracks"].get(
                            key, {"all_time": 0, "monthly": 0}
                        )
                        current_stats["all_time"] = (
                            current_stats.get("all_time", 0) + increment_value
                        )
                        current_stats["monthly"] = (
                            current_stats.get("monthly", 0) + increment_value
                        )
                        total_stats["tracks"][key] = current_stats
                elif entry_type in [
                    "artist",
                    "album",
                    "genre",
                    "playlist",
                    "folder",
                    "composer",
                ]:
                    key = log_entry.get("k")
                    stats_dict_key = f"{entry_type}s"
                    if key and stats_dict_key in total_stats:
                        current_stats = total_stats[stats_dict_key].get(
                            key, {"all_time": 0, "monthly": 0}
                        )
                        current_stats["all_time"] = (
                            current_stats.get("all_time", 0) + increment_value
                        )
                        current_stats["monthly"] = (
                            current_stats.get("monthly", 0) + increment_value
                        )
                        total_stats[stats_dict_key][key] = current_stats
            except json.JSONDecodeError:
                pass

        self.save_play_stats(total_stats)
        self.reset_last_played_entity_metadata()
        return True

    def clear_play_stats(self):
        """
        Completely clears all playback statistics and logs.
        """
        current_month_str = datetime.now().strftime("%Y-%m")
        self.save_play_stats(
            {
                "current_month": current_month_str,
                "tracks": {},
                "artists": {},
                "albums": {},
                "genres": {},
                "playlists": {},
                "folders": {},
            }
        )
        try:
            if self.play_stats_log_path.exists():
                os.remove(self.play_stats_log_path)
        except OSError:
            pass
        self.reset_last_played_entity_metadata()

    def clear_charts_archive(self):
        """
        Deletes the historical monthly charts archive file.
        """
        try:
            if self.charts_archive_path.exists():
                os.remove(self.charts_archive_path)
        except OSError:
            pass

    def reset_entity_stats(self, item_data, item_type: str, mode: int = 1) -> bool:
        """
        Resets the playback statistics for a specific entity.
        mode=1 (All Time): Deletes the entire record.
        mode=0 (Monthly): Subtracts the monthly count from the total and zeroes out the month.
        """
        try:
            self.process_stats_log()
            stats = self.load_play_stats()
            stats_dict_key = None
            item_key_str = None

            if item_type == "track":
                stats_dict_key = "tracks"
                item_key_str = item_data.get("path")
            elif item_type == "album":
                stats_dict_key = "albums"
                item_key_str = json.dumps(list(item_data))
            elif item_type in ["artist", "genre", "composer"]:
                stats_dict_key = f"{item_type}s"
                item_key_str = item_data

            if not stats_dict_key or not item_key_str:
                return False

            target_dict = stats.get(stats_dict_key, {})
            if item_key_str in target_dict:
                if mode == 1:
                    del target_dict[item_key_str]
                else:
                    current = target_dict[item_key_str]
                    if isinstance(current, dict):
                        monthly_val = current.get("monthly", 0)
                        all_time_val = current.get("all_time", 0)
                        current["all_time"] = max(0, all_time_val - monthly_val)
                        current["monthly"] = 0

                self.save_play_stats(stats)
                return True
            return False
        except Exception as e:
            print(f"Error resetting stats: {e}")
            return False

    def increment_track_play(
        self, track_path: str, collect_statistics_enabled: bool, increment_by: int = 1
    ):
        """
        Appends a track play event to the statistics log for asynchronous processing.
        """
        if not collect_statistics_enabled or not track_path or increment_by <= 0:
            return
        try:
            log_entry = {
                "t": "track",
                "p": track_path,
                "ts": int(time.time()),
                "inc": increment_by,
            }
            log_line = json.dumps(log_entry, ensure_ascii=False) + "\n"
            with open(self.play_stats_log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception:
            pass

    def increment_entity_play(
        self,
        context_data: any,
        entity_type: str,
        collect_statistics_enabled: bool,
        increment_by: int = 1,
    ):
        """
        Appends a generic entity (album, artist, etc.) play event to the statistics log.
        """
        if not collect_statistics_enabled or increment_by <= 0:
            return
        entity_key_str = None
        if entity_type == "artist" and isinstance(context_data, str):
            entity_key_str = context_data
        elif entity_type == "album" and isinstance(context_data, (tuple, list)):
            entity_key_str = json.dumps(list(context_data))
        elif entity_type == "genre" and isinstance(context_data, str):
            entity_key_str = context_data
        elif entity_type == "playlist" and isinstance(context_data, str):
            entity_key_str = context_data
        elif entity_type == "folder" and isinstance(context_data, str):
            entity_key_str = context_data
        elif entity_type == "composer" and isinstance(context_data, str):
            entity_key_str = context_data
        if not entity_key_str:
            return
        try:
            log_entry = {
                "t": entity_type,
                "k": entity_key_str,
                "ts": int(time.time()),
                "inc": increment_by,
            }
            log_line = json.dumps(log_entry, ensure_ascii=False) + "\n"
            with open(self.play_stats_log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception:
            pass

    def reset_last_played_entity_metadata(self):
        """
        Clears the cached metadata mapping of the last played entity.
        """
        self.last_played_entity_metadata = {
            "album_key": None,
            "album_artist": None,
            "genres": set(),
            "composers": set(),
        }

    def load_charts_archive(self) -> dict:
        """
        Loads the historical charts archive (monthly summaries) from disk.
        """
        if not self.charts_archive_path.exists():
            return {}
        try:
            with open(self.charts_archive_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_charts_archive(self, data: dict):
        """
        Saves the historical charts archive to disk.
        """
        try:
            with open(self.charts_archive_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def archive_monthly_stats_if_needed(self):
        """
        Checks if the month has rolled over, and if so, calculates the top N items
        for the past month, saves them into the charts archive, and resets monthly stats.
        """
        try:
            current_time = datetime.now()
            current_month_str = current_time.strftime("%Y-%m")
            stats = self.load_play_stats()
            stats_month = stats.get("current_month")

            if not stats_month:
                stats["current_month"] = current_month_str
                self.save_play_stats(stats)
                return

            if stats_month == current_month_str:
                return

            archive_key = stats_month
            charts_archive = self.load_charts_archive()
            archive_data = {}
            top_n = 50

            key_types_to_archive = [
                "tracks",
                "artists",
                "albums",
                "genres",
                "composers",
            ]
            for key_type in key_types_to_archive:
                source_dict = stats.get(key_type, {})
                monthly_list = []
                for item_key, counts_dict in source_dict.items():
                    if isinstance(counts_dict, dict):
                        monthly_count = counts_dict.get("monthly", 0)
                        if monthly_count > 0:
                            monthly_list.append((item_key, monthly_count))
                monthly_list.sort(key=lambda x: x[1], reverse=True)
                archive_data[key_type] = monthly_list[:top_n]

            charts_archive[archive_key] = archive_data
            self.save_charts_archive(charts_archive)

            stats["current_month"] = current_month_str
            all_key_types = [
                "tracks",
                "artists",
                "albums",
                "genres",
                "playlists",
                "folders",
                "composers",
            ]
            for key_type in all_key_types:
                if key_type not in stats:
                    continue
                for item_key in stats[key_type]:
                    if isinstance(stats[key_type][item_key], dict):
                        stats[key_type][item_key]["monthly"] = 0
            self.save_play_stats(stats)
        except Exception:
            pass

    def load_pending_updates(self) -> list:
        """
        Loads the list of files that have pending metadata updates.
        """
        if not self.pending_updates_path.exists():
            return []
        try:
            with open(self.pending_updates_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save_pending_updates(self, paths: list):
        """
        Saves a list of file paths that require metadata updates.
        """
        try:
            with open(self.pending_updates_path, "w", encoding="utf-8") as f:
                json.dump(paths, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def clear_pending_updates(self):
        """
        Clears the list of pending metadata updates.
        """
        self.save_pending_updates([])

    def get_extended_track_info(self, file_path: str) -> dict:
        """
        Reads audio properties and raw tags for the Advanced Editor tab.
        Does not use the cache.
        """
        info = {
            "format": "Unknown",
            "bitrate": "N/A",
            "sample_rate": "N/A",
            "channels": "N/A",
            "duration_str": "00:00:00",
            "original_year": "",
            "comment": "",
            "copyright": "",
            "source_url": "",
            "user_url": "",
            "bpm": "",
            "isrc": "",
            "media_type": "",
            "encoded_by": "",
            "encoder_settings": "",
            "other_tags": []
        }

        try:
            audio = mutagen.File(file_path)
            if not audio:
                return info

            info["format"] = type(audio).__name__.replace("mutagen.", "")
            if hasattr(audio, "info"):
                d = int(audio.info.length)
                ms = int((audio.info.length - d) * 1000)
                m, s = divmod(d, 60)
                h, m = divmod(m, 60)
                info["duration_str"] = f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

                if hasattr(audio.info, "bitrate") and audio.info.bitrate:
                    info["bitrate"] = f"{int(audio.info.bitrate / 1000)} kbps"
                if hasattr(audio.info, "sample_rate") and audio.info.sample_rate:
                    info["sample_rate"] = f"{audio.info.sample_rate} Hz"
                if hasattr(audio.info, "channels"):
                    info["channels"] = str(audio.info.channels)

            def get_val_safe(keys):
                """
                Safely retrieves the first available value for a given list of tag keys.
                Returns a string representation of the value or an empty string if not found.
                """
                if hasattr(audio, "tags") and audio.tags:
                    for k in keys:
                        if k in audio.tags:
                            val = audio.tags[k]
                            if isinstance(val, list):
                                return str(val[0])
                            return str(val)
                return ""

            if isinstance(audio, mutagen.mp3.MP3):
                tags = audio.tags if audio.tags else {}

                info["original_year"] = get_val_safe(["TDOR", "TWOR"])
                info["copyright"] = get_val_safe(["TCOP"])
                info["bpm"] = get_val_safe(["TBPM"])
                info["isrc"] = get_val_safe(["TSRC"])
                info["media_type"] = get_val_safe(["TMED"])
                info["encoded_by"] = get_val_safe(["TENC"])
                info["encoder_settings"] = get_val_safe(["TSSE"])

                comm_keys = [k for k in tags.keys() if k.startswith("COMM")]
                if comm_keys:
                    info["comment"] = str(tags[comm_keys[0]])

                if "WOAS" in tags:
                    info["source_url"] = getattr(tags["WOAS"], 'url', str(tags["WOAS"]))

                wxxx_keys = [k for k in tags.keys() if k.startswith("WXXX")]
                if wxxx_keys:
                    target_key = "WXXX:" if "WXXX:" in tags else wxxx_keys[0]
                    info["user_url"] = getattr(tags[target_key], 'url', str(tags[target_key]))

            elif isinstance(audio, (mutagen.flac.FLAC, mutagen.oggvorbis.OggVorbis)):
                info["original_year"] = get_val_safe(["ORIGINALDATE", "ORIGINALYEAR"])
                info["comment"] = get_val_safe(["COMMENT", "DESCRIPTION"])
                info["copyright"] = get_val_safe(["COPYRIGHT"])
                info["source_url"] = get_val_safe(["SOURCE", "WOAS"])
                info["user_url"] = get_val_safe(["CONTACT", "USERURL"])
                info["bpm"] = get_val_safe(["BPM"])
                info["isrc"] = get_val_safe(["ISRC"])
                info["media_type"] = get_val_safe(["MEDIA", "MEDIATYPE"])
                info["encoded_by"] = get_val_safe(["ENCODEDBY", "ENCODED-BY"])
                info["encoder_settings"] = get_val_safe(["ENCODERSETTINGS"])

            elif isinstance(audio, mutagen.mp4.MP4):
                info["original_year"] = get_val_safe(["\xa9day"])
                info["comment"] = get_val_safe(["\xa9cmt"])
                info["copyright"] = get_val_safe(["\xa9cpy"])
                info["encoded_by"] = get_val_safe(["\xa9enc"])
                info["isrc"] = get_val_safe(["----:com.apple.iTunes:ISRC"])
                info["bpm"] = get_val_safe(["tmpo"])

            elif isinstance(audio, mutagen.wave.WAVE):
                info["original_year"] = get_val_safe(["ICRD"])
                info["comment"] = get_val_safe(["ICMT"])
                info["copyright"] = get_val_safe(["ICOP"])
                info["encoded_by"] = get_val_safe(["ISFT"])

            handled_keys = set([
                "TIT2", "TPE1", "TALB", "TYER", "TRCK", "TPOS", "TCON", "TPE2", "TCOM", "USLT", "APIC",
                "TDOR", "TWOR", "COMM", "TCOP", "WOAS", "WXXX", "TBPM", "TSRC", "TMED", "TENC", "TSSE",
                "TITLE", "ARTIST", "ALBUM", "DATE", "TRACKNUMBER", "DISCNUMBER", "GENRE", "ALBUMARTIST", "COMPOSER",
                "LYRICS", "METADATA_BLOCK_PICTURE",
                "ORIGINALDATE", "COMMENT", "COPYRIGHT", "SOURCE", "CONTACT", "BPM", "ISRC", "MEDIA", "ENCODEDBY",
                "ENCODERSETTINGS",
                "\xa9nam", "\xa9ART", "\xa9alb", "\xa9day", "trkn", "disk", "\xa9gen", "aART", "\xa9wrt", "\xa9lyr",
                "covr",
                "\xa9cmt", "\xa9cpy", "\xa9enc", "tmpo"
            ])

            if hasattr(audio, "tags") and audio.tags:
                for k, v in audio.tags.items():
                    k_str = str(k)
                    is_handled = k_str in handled_keys
                    if not is_handled and isinstance(audio, mutagen.mp3.MP3):
                        if k_str.startswith("COMM") or k_str.startswith("WXXX") or k_str.startswith(
                                "APIC") or k_str.startswith("USLT"):
                            is_handled = True

                    if not is_handled:
                        val_str = str(v)
                        if len(val_str) > 100: val_str = val_str[:100] + "..."
                        info["other_tags"].append((k_str, val_str))

            info["other_tags"].sort(key = lambda x: x[0])

        except Exception as e:
            print(f"Error reading extended info: {e}")

        return info

    def save_metadata_for_tracks(self, tracks, data_to_save):
        """
        Saves updated metadata (ID3/Vorbis/MP4 tags, lyrics, artwork) directly
        to the track files. Returns a list of paths that were successfully changed.
        """
        changed_paths = set()
        new_lyrics = data_to_save.pop("lyrics", None)
        new_artwork_path = data_to_save.pop("artwork_path", None)

        adv_fields = {
            "original_year": data_to_save.pop("original_year", None),
            "comment": data_to_save.pop("comment", None),
            "copyright": data_to_save.pop("copyright", None),
            "source_url": data_to_save.pop("source_url", None),
            "user_url": data_to_save.pop("user_url", None),
            "bpm": data_to_save.pop("bpm", None),
            "isrc": data_to_save.pop("isrc", None),
            "media_type": data_to_save.pop("media_type", None),
            "encoded_by": data_to_save.pop("encoded_by", None),
            "encoder_settings": data_to_save.pop("encoder_settings", None),
        }

        if "genre" in data_to_save:
            genre_input = data_to_save["genre"]
            if isinstance(genre_input, str):
                split_genres = [g.strip() for g in re.split(r"[,;/|]", genre_input) if g.strip()]
                data_to_save["genre"] = split_genres

        if "artist" in data_to_save:
            artist_input = data_to_save["artist"]
            if isinstance(artist_input, str):
                split_artists = [a.strip() for a in artist_input.split(";") if a.strip()]
                data_to_save["artist"] = split_artists

        for track in tracks:
            if track.get("is_virtual", False):
                continue
            file_path = track["path"]
            try:
                if data_to_save:
                    audio_easy = mutagen.File(file_path, easy = True)
                    if audio_easy and not type(audio_easy).__name__ in ('WAVE', 'AAC', 'ASF'):
                        for key, value in data_to_save.items():
                            if value:
                                audio_easy[key] = value
                            elif key in audio_easy:
                                try:
                                    del audio_easy[key]
                                except Exception:
                                    pass
                        audio_easy.save()
                        changed_paths.add(file_path)

                audio = mutagen.File(file_path)
                if audio:
                    is_modified = False


                    def set_id3_text(frame_cls, val):
                        """
                        Sets or removes a standard ID3 text frame.
                        Returns True if the tags were modified.
                        """
                        frame_id = frame_cls.__name__
                        if val:
                            audio.tags.add(frame_cls(encoding = 3, text = val))
                            return True
                        elif frame_id in audio.tags:
                            audio.tags.delall(frame_id)
                            return True
                        return False

                    def set_id3_url_frame(frame_cls, val):
                        """
                        Sets or removes an ID3 URL frame.
                        Returns True if the tags were modified.
                        """
                        frame_id = frame_cls.__name__
                        if val:
                            audio.tags.add(frame_cls(url = val))
                            return True
                        elif frame_id in audio.tags:
                            audio.tags.delall(frame_id)
                            return True
                        return False

                    def set_vorbis(key, val):
                        """
                        Sets or removes a Vorbis comment/tag (used in FLAC/Ogg).
                        Returns True if the tags were modified.
                        """
                        if val:
                            audio[key] = val if isinstance(val, list) else [val]
                            return True
                        elif key in audio:
                            del audio[key]
                            return True
                        return False

                    if isinstance(audio, (MP3, WAVE, AAC)):
                        if isinstance(audio, (WAVE, AAC)) and audio.tags is None:
                            try:
                                audio.add_tags()
                            except Exception:
                                pass

                        if isinstance(audio, (WAVE, AAC)) and data_to_save:
                            if "title" in data_to_save: is_modified |= set_id3_text(TIT2, data_to_save["title"])
                            if "artist" in data_to_save: is_modified |= set_id3_text(TPE1, data_to_save["artist"])
                            if "album_artist" in data_to_save: is_modified |= set_id3_text(TPE2,
                                                                                           data_to_save["album_artist"])
                            if "album" in data_to_save: is_modified |= set_id3_text(TALB, data_to_save["album"])
                            if "composer" in data_to_save: is_modified |= set_id3_text(TCOM, data_to_save["composer"])
                            if "genre" in data_to_save: is_modified |= set_id3_text(TCON, data_to_save["genre"])
                            if "tracknumber" in data_to_save: is_modified |= set_id3_text(TRCK, str(
                                data_to_save["tracknumber"]))
                            if "discnumber" in data_to_save: is_modified |= set_id3_text(TPOS, str(
                                data_to_save["discnumber"]))
                            if "year" in data_to_save: is_modified |= set_id3_text(TDRC, str(data_to_save["year"]))

                        if adv_fields["comment"] is not None:
                            had_comm = "COMM" in audio.tags or any(k.startswith("COMM") for k in audio.tags.keys())
                            audio.tags.delall("COMM")
                            if adv_fields["comment"]:
                                audio.tags.add(
                                    COMM(encoding = 3, lang = 'eng', desc = '', text = [adv_fields["comment"]]))
                                is_modified = True
                            elif had_comm:
                                is_modified = True

                        if adv_fields["copyright"] is not None: is_modified |= set_id3_text(TCOP,
                                                                                            adv_fields["copyright"])
                        if adv_fields["source_url"] is not None: is_modified |= set_id3_url_frame(WOAS, adv_fields[
                            "source_url"])
                        if adv_fields["user_url"] is not None:
                            had_wxxx = "WXXX" in audio.tags or any(k.startswith("WXXX") for k in audio.tags.keys())
                            audio.tags.delall("WXXX")
                            if adv_fields["user_url"]:
                                audio.tags.add(WXXX(encoding = 3, desc = '', url = adv_fields["user_url"]))
                                is_modified = True
                            elif had_wxxx:
                                is_modified = True

                        if adv_fields["bpm"] is not None: is_modified |= set_id3_text(TBPM, adv_fields["bpm"])
                        if adv_fields["isrc"] is not None: is_modified |= set_id3_text(TSRC, adv_fields["isrc"])
                        if adv_fields["media_type"] is not None: is_modified |= set_id3_text(TMED,
                                                                                             adv_fields["media_type"])
                        if adv_fields["encoded_by"] is not None: is_modified |= set_id3_text(TENC,
                                                                                             adv_fields["encoded_by"])
                        if adv_fields["encoder_settings"] is not None: is_modified |= set_id3_text(TSSE, adv_fields[
                            "encoder_settings"])
                        if adv_fields["original_year"] is not None: is_modified |= set_id3_text(TDOR, adv_fields[
                            "original_year"])


                    elif isinstance(audio, (FLAC, mutagen.oggvorbis.OggVorbis)):
                        if adv_fields["comment"] is not None:
                            is_modified |= set_vorbis("COMMENT", adv_fields["comment"])
                        if adv_fields["copyright"] is not None:
                            is_modified |= set_vorbis("COPYRIGHT", adv_fields["copyright"])
                        if adv_fields["source_url"] is not None:
                            is_modified |= set_vorbis("SOURCE", adv_fields["source_url"])
                        if adv_fields["user_url"] is not None:
                            is_modified |= set_vorbis("CONTACT", adv_fields["user_url"])
                        if adv_fields["bpm"] is not None:
                            is_modified |= set_vorbis("BPM", adv_fields["bpm"])
                        if adv_fields["isrc"] is not None:
                            is_modified |= set_vorbis("ISRC", adv_fields["isrc"])
                        if adv_fields["media_type"] is not None:
                            is_modified |= set_vorbis("MEDIA",adv_fields["media_type"])
                        if adv_fields["encoded_by"] is not None:
                            is_modified |= set_vorbis("ENCODEDBY", adv_fields["encoded_by"])
                        if adv_fields["encoder_settings"] is not None:
                            is_modified |= set_vorbis("ENCODERSETTINGS", adv_fields["encoder_settings"])
                        if adv_fields["original_year"] is not None:
                            is_modified |= set_vorbis("ORIGINALDATE", adv_fields["original_year"])


                    elif isinstance(audio, MP4):
                        def set_mp4_text(key, val):
                            """
                            Sets or removes a standard MP4 atom/tag.
                            Returns True if the tags were modified.
                            """
                            if val:
                                audio[key] = [val]
                                return True
                            elif key in audio:
                                del audio[key]
                                return True
                            return False

                        def set_mp4_freeform(name, val):
                            """
                            Sets or removes a custom iTunes freeform MP4 tag.
                            Returns True if the tags were modified.
                            """
                            key = f"----:com.apple.iTunes:{name}"
                            if val:
                                audio[key] = [val.encode("utf-8")]
                                return True
                            elif key in audio:
                                del audio[key]
                                return True
                            return False

                        if adv_fields["comment"] is not None: is_modified |= set_mp4_text("\xa9cmt",
                                                                                          adv_fields["comment"])
                        if adv_fields["copyright"] is not None: is_modified |= set_mp4_text("\xa9cpy",
                                                                                            adv_fields["copyright"])
                        if adv_fields["encoded_by"] is not None: is_modified |= set_mp4_text("\xa9enc",
                                                                                             adv_fields["encoded_by"])
                        if adv_fields["original_year"] is not None: is_modified |= set_mp4_text("\xa9day", adv_fields[
                            "original_year"])
                        if adv_fields["bpm"] is not None:
                            if adv_fields["bpm"]:
                                try:
                                    bpm_int = int(float(adv_fields["bpm"]))
                                    audio["tmpo"] = [bpm_int]
                                    is_modified = True
                                except ValueError:
                                    pass
                            elif "tmpo" in audio:
                                del audio["tmpo"]
                                is_modified = True
                        if adv_fields["isrc"] is not None: is_modified |= set_mp4_freeform("ISRC", adv_fields["isrc"])


                    elif isinstance(audio, mutagen.asf.ASF):
                        if data_to_save:
                            if "title" in data_to_save: is_modified |= set_vorbis("Title", data_to_save["title"])
                            if "artist" in data_to_save: is_modified |= set_vorbis("Author", data_to_save["artist"])
                            if "album_artist" in data_to_save: is_modified |= set_vorbis("WM/AlbumArtist",
                                                                                         data_to_save["album_artist"])
                            if "album" in data_to_save: is_modified |= set_vorbis("WM/AlbumTitle",
                                                                                  data_to_save["album"])
                            if "composer" in data_to_save: is_modified |= set_vorbis("WM/Composer",
                                                                                     data_to_save["composer"])
                            if "genre" in data_to_save: is_modified |= set_vorbis("WM/Genre", data_to_save["genre"])
                            if "tracknumber" in data_to_save: is_modified |= set_vorbis("WM/TrackNumber", str(
                                data_to_save["tracknumber"]))
                            if "discnumber" in data_to_save: is_modified |= set_vorbis("WM/PartOfSet",
                                                                                       str(data_to_save["discnumber"]))
                            if "year" in data_to_save: is_modified |= set_vorbis("WM/Year", str(data_to_save["year"]))

                        if adv_fields["comment"] is not None: is_modified |= set_vorbis("Description",
                                                                                        adv_fields["comment"])
                        if adv_fields["copyright"] is not None: is_modified |= set_vorbis("Copyright",
                                                                                          adv_fields["copyright"])
                        if adv_fields["encoded_by"] is not None: is_modified |= set_vorbis("WM/EncodingSettings",
                                                                                           adv_fields["encoded_by"])
                        if adv_fields["original_year"] is not None: is_modified |= set_vorbis("WM/Year", adv_fields[
                            "original_year"])
                        if adv_fields["bpm"] is not None: is_modified |= set_vorbis("WM/BeatsPerMinute",
                                                                                    adv_fields["bpm"])
                        if adv_fields["isrc"] is not None: is_modified |= set_vorbis("WM/ISRC", adv_fields["isrc"])

                    if is_modified:
                        audio.save()
                        changed_paths.add(file_path)

                if new_lyrics is not None:
                    audio_full_lyrics = mutagen.File(file_path)
                    if audio_full_lyrics:
                        try:
                            if isinstance(audio_full_lyrics, (MP3, WAVE, AAC)):
                                if isinstance(audio_full_lyrics, (WAVE, AAC)) and audio_full_lyrics.tags is None:
                                    try:
                                        audio_full_lyrics.add_tags()
                                    except Exception:
                                        pass

                                if audio_full_lyrics.tags is not None:
                                    existing_keys = [k for k in audio_full_lyrics.keys() if k.startswith("USLT")]
                                    for k in existing_keys: del audio_full_lyrics[k]
                                    if new_lyrics:
                                        audio_full_lyrics.tags.add(
                                            USLT(encoding = 3, lang = "XXX", desc = "Lyrics", text = new_lyrics))

                            elif isinstance(audio_full_lyrics, (FLAC, mutagen.oggvorbis.OggVorbis)):
                                audio_full_lyrics["LYRICS"] = ([new_lyrics] if new_lyrics else [])

                            elif isinstance(audio_full_lyrics, MP4):
                                if new_lyrics:
                                    audio_full_lyrics["\xa9lyr"] = [new_lyrics]
                                elif "\xa9lyr" in audio_full_lyrics:
                                    del audio_full_lyrics["\xa9lyr"]

                            elif isinstance(audio_full_lyrics, mutagen.asf.ASF):
                                if new_lyrics:
                                    audio_full_lyrics["WM/Lyrics"] = [new_lyrics]
                                elif "WM/Lyrics" in audio_full_lyrics:
                                    del audio_full_lyrics["WM/Lyrics"]

                            audio_full_lyrics.save()
                            changed_paths.add(file_path)
                        except Exception:
                            pass

                if new_artwork_path:
                    audio_full = mutagen.File(file_path)
                    if audio_full:
                        with open(new_artwork_path, "rb") as art_file:
                            artwork_data = art_file.read()
                        mime_type = "image/jpeg"
                        if new_artwork_path.lower().endswith(".png"): mime_type = "image/png"

                        if isinstance(audio_full, (MP3, WAVE, AAC)):
                            if isinstance(audio_full, (WAVE, AAC)) and audio_full.tags is None:
                                try:
                                    audio_full.add_tags()
                                except Exception:
                                    pass

                            if audio_full.tags is not None:
                                audio_full.tags.delall("APIC")
                                audio_full.tags.add(
                                    APIC(encoding = 3, mime = mime_type, type = 3, desc = "Cover", data = artwork_data))

                        elif isinstance(audio_full, FLAC):
                            pic = Picture()
                            pic.data = artwork_data
                            pic.type = 3
                            pic.mime = mime_type
                            audio_full.clear_pictures()
                            audio_full.add_picture(pic)

                        elif isinstance(audio_full, mutagen.oggvorbis.OggVorbis):
                            pic = Picture()
                            pic.data = artwork_data
                            pic.type = 3
                            pic.mime = mime_type
                            pic_data = base64.b64encode(pic.write()).decode('ascii')
                            audio_full["metadata_block_picture"] = [pic_data]

                        elif isinstance(audio_full, MP4):
                            cov_type = MP4Cover.FORMAT_JPEG if mime_type == "image/jpeg" else MP4Cover.FORMAT_PNG
                            audio_full["covr"] = [MP4Cover(artwork_data, imageformat = cov_type)]

                        elif isinstance(audio_full, mutagen.asf.ASF):
                            pic = mutagen.asf.ASFPicture()
                            pic.picture_type = 3
                            pic.mime_type = mime_type
                            pic.picture_data = artwork_data
                            audio_full["WM/Picture"] = [pic]

                        audio_full.save()
                        changed_paths.add(file_path)

            except Exception as e:
                print(f"Error saving metadata for {file_path}: {e}")
                pass

        return list(changed_paths)

    def load_artist_artworks(self) -> dict:
        """
        Loads the mapping between artists and their cached artwork paths.
        """
        if not self.artist_artworks_path.exists():
            return {}
        try:
            with open(self.artist_artworks_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_artist_artworks(self, artworks: dict):
        """
        Saves the artist artwork mapping to disk.
        """
        try:
            with open(self.artist_artworks_path, "w", encoding="utf-8") as f:
                json.dump(artworks, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def load_genre_artworks(self) -> dict:
        """
        Loads the mapping between genres and their assigned artwork paths.
        """
        if not self.genre_artworks_path.exists():
            return {}
        try:
            with open(self.genre_artworks_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_genre_artworks(self, artworks: dict):
        """
        Saves the genre artwork mapping to disk.
        """
        try:
            with open(self.genre_artworks_path, "w", encoding="utf-8") as f:
                json.dump(artworks, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def load_composer_artworks(self) -> dict:
        """
        Loads the mapping between composers and their cached artwork paths.
        """
        if not self.composer_artworks_path.exists():
            return {}
        try:
            with open(self.composer_artworks_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_composer_artworks(self, artworks: dict):
        """
        Saves the composer artwork mapping to disk.
        """
        try:
            with open(self.composer_artworks_path, "w", encoding="utf-8") as f:
                json.dump(artworks, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def get_default_settings(self) -> dict:
        """
        Returns a dictionary containing the default settings for the application.
        """
        return {
            "musicLibraryPaths": [],
            "volume": 50,
            "shuffle": False,
            "repeatMode": 0,
            "playlistVisible": True,
            "artist_source_tag": "artist",
            "show_separators": True,
            "show_favorites_separators": False,
            "ignore_articles": True,
            "ignore_genre_case": True,
            "treat_folders_as_unique": False,
            "dismissed_album_merge_warning": False,
            "playback_history_mode": 2,
            "history_store_unique_only": True,
            "remember_last_view": True,
            "remember_window_size": True,
            "warm_sound": False,
            "scratch_sound": False,
            "show_random_suggestions": True,
            "windowGeometry": None,
            "splitterSizes": None,
            "playlistCompactMode": False,
            "playlistCompactHideArtist": False,
            "view_modes": {
                "artists": 0,
                "artist_albums": 0,
                "albums": 0,
                "genres": 0,
                "catalog": 2,
                "playlists": 1,
                "favorites": 0,
            },
            "sort_modes": {
                "artists": 0,
                "albums": 2,
                "genres": 0,
                "artist_albums": 2,
                "songs": 4,
                "playlists": 0,
                "catalog": 0,
                "favorite_tracks": 6,
            },
            "collect_statistics": True,
            "pending_settings_rescan": False,
            "theme": "Light",
            "accent_color": "Crimson",
            "encyclopedia_collapsed": False,
        }

    def load_settings(self) -> dict:
        """
        Loads application settings from disk, ensuring missing keys fallback
        to their defaults and handling structural migrations.
        """
        default_settings = self.get_default_settings()
        if not self.settings_path.exists():
            return default_settings
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
                for key, value in default_settings.items():
                    if key not in settings:
                        settings[key] = value
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if sub_key not in settings[key]:
                                settings[key][sub_key] = sub_value
                if (
                    "musicLibraryPath" in settings
                    and "musicLibraryPaths" not in settings
                ):
                    if settings["musicLibraryPath"]:
                        settings["musicLibraryPaths"] = [settings["musicLibraryPath"]]
                    del settings["musicLibraryPath"]
                return settings
        except (json.JSONDecodeError, IOError):
            return default_settings

    def reset_settings(self):
        """
        Resets the application settings to defaults, while preserving
        the user's configured music library paths.
        """
        current_settings = self.load_settings()
        paths_to_keep = current_settings.get("musicLibraryPaths", [])
        new_settings = self.get_default_settings()
        new_settings["musicLibraryPaths"] = paths_to_keep
        self.save_settings(new_settings)

    def save_settings(self, settings: dict):
        """
        Saves the current application settings dictionary to disk.
        """
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def save_last_view_state(self, state: dict):
        """
        Saves the UI's last viewed state (e.g. specific album/artist open)
        so it can be restored on restart.
        """
        try:
            with open(self.last_view_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def load_last_view_state(self) -> dict | None:
        """
        Loads the previously saved UI view state, or None if it doesn't exist.
        """
        if not self.last_view_path.exists():
            return None
        try:
            with open(self.last_view_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            if self.last_view_path.exists():
                os.remove(self.last_view_path)
            return None

    def clear_last_view_state(self):
        """
        Clears the stored last view state, effectively forcing the app to
        open to the default view on the next startup.
        """
        try:
            if self.last_view_path.exists():
                os.remove(self.last_view_path)
        except OSError:
            pass

    def load_blacklist(self) -> dict:
        """
        Loads the blacklisted entities (artists, tracks, folders) that are
        excluded from recommendations or the main library view.
        """
        default_blacklist = {
            "artists": [],
            "albums": [],
            "tracks": [],
            "folders": [],
            "composers": [],
        }
        if not self.blacklist_path.exists():
            return default_blacklist
        try:
            with open(self.blacklist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in default_blacklist:
                    if key not in data:
                        data[key] = []
                return data
        except (json.JSONDecodeError, IOError):
            return default_blacklist

    def save_blacklist(self, blacklist_data: dict):
        """
        Saves the blacklist data to disk.
        """
        try:
            with open(self.blacklist_path, "w", encoding="utf-8") as f:
                json.dump(blacklist_data, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def load_unavailable_favorites(self) -> dict:
        """
        Loads the list of favorited items that are currently unavailable
        (e.g., deleted or moved files).
        """
        default_unavailable = {
            "tracks": {},
            "albums": {},
            "artists": {},
            "genres": {},
            "folders": {},
            "playlists": {},
            "composers": {},
        }
        if not self.unavailable_favorites_path.exists():
            return default_unavailable
        try:
            with open(self.unavailable_favorites_path, "r", encoding="utf-8") as f:
                unavailable = json.load(f)
            needs_resave = False
            for key in default_unavailable.keys():
                if key in unavailable and isinstance(unavailable.get(key), list):
                    item_list = unavailable[key]
                    if key == "albums":
                        unavailable[key] = {
                            json.dumps(item): time.time() for item in item_list
                        }
                    else:
                        unavailable[key] = {item: time.time() for item in item_list}
                    needs_resave = True
            if needs_resave:
                self.save_unavailable_favorites(unavailable)
            for key in default_unavailable:
                if key not in unavailable:
                    unavailable[key] = default_unavailable[key]
            return unavailable
        except (json.JSONDecodeError, IOError):
            return default_unavailable

    def save_unavailable_favorites(self, unavailable_items: dict):
        """
        Saves the list of unavailable favorites to disk.
        """
        try:
            with open(self.unavailable_favorites_path, "w", encoding="utf-8") as f:
                json.dump(unavailable_items, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def load_playback_history(self) -> list[str]:
        """
        Loads the user's playback history (a list of track paths) from disk.
        """
        if not self.playback_history_path.exists():
            return []
        try:
            with open(self.playback_history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save_playback_history(self, track_paths: list[str]):
        """
        Saves the user's playback history to disk.
        """
        try:
            with open(self.playback_history_path, "w", encoding="utf-8") as f:
                json.dump(track_paths, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def add_track_to_history(
        self,
        track_path: str,
        history_mode: int,
        store_unique_only: bool,
        history_limit: int = HISTORY_LIMIT,
    ):
        """
        Adds a track to the playback history, enforcing size limits and uniqueness
        constraints according to the user's settings.
        """
        if history_mode == 0:
            return
        try:
            history = self.load_playback_history()
        except Exception:
            history = []
        if store_unique_only:
            if track_path in history:
                history.remove(track_path)
        history.insert(0, track_path)
        if history_mode == 2:
            if len(history) > history_limit:
                history = history[:history_limit]
        self.save_playback_history(history)

    def get_cache_path(self, library_paths: list[str]) -> Path:
        """
        Returns the path to the unified cache file.
        """
        return self.cache_dir / "library_cache.json"

    def load_cache(self, library_paths: list[str]) -> list | None:
        """
        Loads the library cache and filters out tracks whose parent folders
        are no longer present in the active library settings.
        """
        if not library_paths:
            return None

        cache_path = self.get_cache_path(library_paths)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                all_cached_tracks = json.load(f)

            active_roots = [os.path.normpath(os.path.abspath(p)) for p in library_paths]

            valid_tracks = []
            for track in all_cached_tracks:
                track_path = track.get("path", "")
                if not track_path:
                    continue

                abs_track_path = os.path.normpath(os.path.abspath(track_path))

                if any(
                    abs_track_path.startswith(root + os.sep) or abs_track_path == root
                    for root in active_roots
                ):
                    valid_tracks.append(track)

            return valid_tracks

        except (json.JSONDecodeError, IOError):
            if cache_path.exists():
                try:
                    os.remove(cache_path)
                except:
                    pass
            return None

    def save_cache(self, library_paths: list[str], tracks: list):
        """
        Saves the current tracked list to a unified cache file.
        """
        if not library_paths:
            return

        cache_path = self.get_cache_path(library_paths)

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(tracks, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Error saving cache: {e}")

    def get_playlist_info_light(self, playlist_path, all_tracks_map):
        """
        Quickly scans a playlist file to return the total track count and the
        artwork of the first available track.
        """
        track_count = 0
        first_artwork = None
        if not os.path.exists(playlist_path):
            return 0, None
        playlist_dir = os.path.dirname(playlist_path)
        try:
            with open(playlist_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return 0, None
        for line in lines:
            path_from_playlist = line.strip()
            if not path_from_playlist or path_from_playlist.startswith("#"):
                continue
            track_count += 1
            if first_artwork is None:
                if os.path.isabs(path_from_playlist):
                    resolved_path = os.path.normpath(path_from_playlist)
                else:
                    resolved_path = os.path.normpath(
                        os.path.join(playlist_dir, path_from_playlist)
                    )
                if track := all_tracks_map.get(resolved_path):
                    if track.get("artwork"):
                        first_artwork = track.get("artwork")
        return track_count, first_artwork

    def get_playlists(self):
        """
        Retrieves a list of absolute paths for all available `.m3u` and `.m3u8` playlists
        in the designated playlists directory.
        """
        playlists = []
        for filename in os.listdir(self.playlists_dir):
            if filename.lower().endswith((".m3u", "m3u8")):
                playlists.append(os.path.join(self.playlists_dir, filename))
        return playlists

    def load_playlist(self, playlist_path, all_tracks_map):
        """
        Reads a playlist file and reconstructs the list of track metadata dictionaries.
        Handles both internal library tracks and external files dynamically.
        """
        if playlist_path == "playback_history":
            history_paths = self.load_playback_history()
            return [
                all_tracks_map[path] for path in history_paths if path in all_tracks_map
            ]

        tracks = []
        path_to_open = playlist_path
        if isinstance(path_to_open, tuple):
            path_to_open = path_to_open[0]
        if not isinstance(path_to_open, (str, bytes, os.PathLike)):
            return []
        if not os.path.exists(path_to_open):
            return []

        playlist_dir = os.path.dirname(path_to_open)
        lines = []
        try:
            with open(path_to_open, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(path_to_open, "r", encoding="cp1251") as f:
                    lines = f.readlines()
            except Exception:
                return []
        except Exception:
            return []

        for line in lines:
            path_from_playlist = line.strip()
            if not path_from_playlist or path_from_playlist.startswith("#"):
                continue

            if os.path.isabs(path_from_playlist):
                resolved_path = os.path.normpath(path_from_playlist)
            else:
                resolved_path = os.path.normpath(
                    os.path.join(playlist_dir, path_from_playlist)
                )

            if track := all_tracks_map.get(resolved_path):
                tracks.append(track)
            elif cached_track := self.external_tracks_cache.get(resolved_path):
                try:
                    current_mtime = os.path.getmtime(resolved_path)
                except OSError:
                    current_mtime = 0
                if cached_track.get("mtime") == current_mtime and current_mtime > 0:
                    tracks.append(cached_track)
                else:
                    if os.path.exists(resolved_path):
                        track_metadata = self.get_track_metadata_light(resolved_path)
                        tracks.append(track_metadata)
                        self.external_tracks_cache[resolved_path] = track_metadata
                    else:
                        tracks.append(
                            {
                                "path": resolved_path,
                                "title": translate(
                                    "[File not found] {filename}",
                                    filename=os.path.basename(resolved_path),
                                ),
                                "artist": "---",
                                "artists": ["---"],
                                "album_artist": "---",
                                "album": "---",
                                "artwork": {},
                                "duration": 0,
                                "tracknumber": 0,
                                "discnumber": 0,
                                "year": 0,
                                "genre": [],
                                "lyrics": "",
                                "date_added": time.time(),
                            }
                        )
            else:
                if os.path.exists(resolved_path):
                    track_metadata = self.get_track_metadata_light(resolved_path)
                    tracks.append(track_metadata)
                    self.external_tracks_cache[resolved_path] = track_metadata
                else:
                    tracks.append(
                        {
                            "path": resolved_path,
                            "title": translate(
                                "[File not found] {filename}",
                                filename=os.path.basename(resolved_path),
                            ),
                            "artist": "---",
                            "artists": ["---"],
                            "album_artist": "---",
                            "album": "---",
                            "artwork": {},
                            "duration": 0,
                            "tracknumber": 0,
                            "discnumber": 0,
                            "year": 0,
                            "genre": [],
                            "lyrics": "",
                            "date_added": time.time(),
                        }
                    )
        return tracks

    def save_playlist(self, playlist_name, tracks):
        """
        Saves a given list of tracks as an M3U playlist and updates internal indices.
        Returns a tuple indicating success and the resulting file path.
        """
        if not playlist_name.lower().endswith((".m3u", ".m3u8")):
            playlist_name += ".m3u"
        playlist_path = self.playlists_dir / playlist_name
        try:
            with open(playlist_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for track in tracks:
                    f.write(f"{track['path']}\n")

            self._update_playlist_index(str(playlist_path), tracks)
            total_duration = sum(t.get("duration", 0) for t in tracks)
            first_artwork = tracks[0].get("artwork") if tracks else None
            try:
                new_mtime = os.path.getmtime(playlist_path)
            except OSError:
                new_mtime = 0

            self.playlists_metadata[str(playlist_path)] = {
                "count": len(tracks),
                "duration": total_duration,
                "artwork": first_artwork,
                "mtime": new_mtime,
            }
            return True, str(playlist_path)
        except Exception as e:
            return False, str(e)

    def delete_playlist(self, playlist_path):
        """
        Sends the specified playlist file to the trash and clears it from memory.
        """
        try:
            send2trash(playlist_path)
            if playlist_path in self.playlists_index:
                del self.playlists_index[playlist_path]
            if playlist_path in self.playlists_metadata:
                del self.playlists_metadata[playlist_path]
            return True, translate(
                "Playlist {playlist_name} deleted.",
                playlist_name=os.path.basename(playlist_path),
            )
        except Exception as e:
            return False, str(e)

    def rename_playlist(self, old_path, new_name):
        """
        Renames an existing playlist file and updates internal index maps.
        """
        if not os.path.exists(old_path):
            return False, "Not found", None
        directory = os.path.dirname(old_path)
        if not new_name.lower().endswith((".m3u", ".m3u8")):
            _, ext = os.path.splitext(old_path)
            new_name += ext if ext else ".m3u"
        new_path = os.path.join(directory, new_name)
        if os.path.normpath(old_path) == os.path.normpath(new_path):
            return True, "Unchanged", old_path
        if os.path.exists(new_path):
            return False, "EXISTS", None
        try:
            os.rename(old_path, new_path)
            if old_path in self.playlists_index:
                self.playlists_index[new_path] = self.playlists_index.pop(old_path)
            if old_path in self.playlists_metadata:
                self.playlists_metadata[new_path] = self.playlists_metadata.pop(
                    old_path
                )
            return True, "Renamed", new_path
        except Exception as e:
            return False, str(e), None

    def import_playlist(self, source_path):
        """
        Imports an external M3U playlist file into the app's playlist directory,
        resolving relative paths against the source location.
        """
        if not os.path.isfile(source_path) or not source_path.lower().endswith(
            (".m3u", ".m3u8")
        ):
            return False, "Not a playlist"
        file_name = os.path.basename(source_path)
        destination_path = self.playlists_dir / file_name
        source_dir = os.path.dirname(source_path)
        if os.path.abspath(source_path) == os.path.abspath(destination_path):
            return True, "Already exists"
        new_tracks_paths = []
        try:
            with open(source_path, "r", encoding="utf-8") as src, open(
                destination_path, "w", encoding="utf-8"
            ) as dst:
                for line in src:
                    sline = line.strip()
                    if not sline or sline.startswith("#"):
                        dst.write(line)
                        continue
                    if os.path.isabs(sline):
                        rpath = os.path.normpath(sline)
                    else:
                        rpath = os.path.abspath(os.path.join(source_dir, sline))
                    dst.write(rpath + "\n")
                    new_tracks_paths.append(rpath)
            dstr = str(destination_path)
            self.playlists_index[dstr] = new_tracks_paths
            if dstr in self.playlists_metadata:
                del self.playlists_metadata[dstr]
            return True, "Imported"
        except Exception as e:
            return False, str(e)

    def save_last_queue(self, queue_state: dict):
        """
        Saves the current playback queue (tracks, position, etc.) so it can be
        resumed later.
        """
        try:
            tracks = queue_state.get("tracks", [])
            track_paths = [track["path"] for track in tracks]
            data_to_save = {
                "name": queue_state.get("name"),
                "path": queue_state.get("path"),
                "track_paths": track_paths,
                "context_data": queue_state.get("context_data"),
                "current_track_index": queue_state.get("current_track_index"),
                "playback_position": queue_state.get("playback_position"),
            }
            with open(self.last_queue_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def load_last_queue(self, all_tracks_map) -> dict | None:
        """
        Loads the previously saved playback queue state and reconstructing the tracks list.
        """
        if not self.last_queue_path.exists():
            return None
        try:
            with open(self.last_queue_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            track_paths = loaded_data.get("track_paths", [])
            tracks = []
            for path in track_paths:
                if track := all_tracks_map.get(path):
                    tracks.append(track)
                elif track := self.external_tracks_cache.get(path):
                    tracks.append(track)
                elif os.path.exists(path):
                    meta = self.get_track_metadata_light(path)
                    tracks.append(meta)
                    self.external_tracks_cache[path] = meta

            return {
                "name": loaded_data.get("name"),
                "path": loaded_data.get("path"),
                "tracks": tracks,
                "context_data": loaded_data.get("context_data"),
                "current_track_index": loaded_data.get("current_track_index"),
                "playback_position": loaded_data.get("playback_position"),
            }
        except Exception:
            return None

    def clear_last_queue(self):
        """
        Deletes the last saved queue state file from disk.
        """
        try:
            if self.last_queue_path.exists():
                os.remove(self.last_queue_path)
        except OSError:
            pass

    def clean_artwork_cache(self, all_tracks: list):
        """
        Scans the artwork cache directory and removes any image files
        that are no longer referenced by the currently active tracks.
        """
        if not self.artwork_cache_dir.exists():
            return
        try:
            used_paths = set()
            for t in all_tracks:
                if art := t.get("artwork"):
                    for p in art.values():
                        used_paths.add(str(Path(p).resolve()))
            for fn in os.listdir(self.artwork_cache_dir):
                fp = self.artwork_cache_dir / fn
                if str(fp.resolve()) not in used_paths:
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
        except Exception:
            pass

    def scan_directories(self, paths: list[str]) -> list:
        """
        Crawls the designated directories for supported audio formats,
        extracts their full metadata, and returns a list of track dicts.
        """
        self.folder_artwork_cache.clear()
        tracks = []
        processed_files = set()
        for path in paths:
            if not os.path.isdir(path):
                continue
            for root, _, files in os.walk(path):
                for file in sorted(files):
                    if file.lower().endswith(self.supported_formats):
                        fp = os.path.join(root, file)
                        np = os.path.normpath(fp)
                        if np not in processed_files:
                            tracks.append(self.get_track_metadata(fp))
                            processed_files.add(np)
        return tracks

    def _find_and_save_folder_artwork(self, folder_path: str) -> dict | None:
        """
        Looks for common album art files (cover, folder, albumart) inside a directory.
        If found, caches thumbnails and returns the size-to-path mapping.
        """
        if folder_path in self.folder_artwork_cache:
            return self.folder_artwork_cache[folder_path]
        patterns = ("cover", "folder", "albumart")
        try:
            for fn in sorted(os.listdir(folder_path)):
                fn_lower = fn.lower()
                if "small" in fn_lower:
                    continue
                if fn_lower.startswith(patterns) and fn_lower.endswith(
                    (".jpg", ".jpeg", ".png")
                ):
                    cover_path = Path(folder_path) / fn
                    with open(cover_path, "rb") as f:
                        original_data = f.read()
                    image = Image.open(io.BytesIO(original_data))
                    ahash = hashlib.md5(original_data).hexdigest()
                    ext = cover_path.suffix.lower()
                    fmt = "JPEG" if ext in [".jpg", ".jpeg"] else "PNG"
                    paths = {}
                    for size in self.artwork_sizes:
                        acp = self.artwork_cache_dir / f"{ahash}_{size}{ext}"
                        if not acp.exists():
                            rimg = image.copy()
                            rimg.thumbnail((size, size), Image.Resampling.LANCZOS)
                            if fmt == "JPEG":
                                rimg.save(acp, format=fmt, quality=95, subsampling=0)
                            else:
                                rimg.save(acp, format=fmt)
                        paths[str(size)] = str(acp)
                    self.folder_artwork_cache[folder_path] = paths
                    return paths
        except OSError:
            pass
        self.folder_artwork_cache[folder_path] = None
        return None

    def _save_artwork(self, audio) -> dict | None:
        """
        Extracts embedded artwork directly from an audio file's tags, caches
        rescaled versions, and returns the path dictionary.
        """
        try:
            adata = None
            mime = "image/jpeg"
            if "covr" in audio and audio["covr"]:
                adata = audio["covr"][0]
                if audio["covr"][0].imageformat == mutagen.mp4.MP4Cover.FORMAT_PNG:
                    mime = "image/png"
            elif hasattr(audio, "pictures") and audio.pictures:
                p = audio.pictures[0]
                adata = p.data
                mime = p.mime
            elif "WM/Picture" in audio:
                try:
                    attr = audio["WM/Picture"][0]
                    pdata = attr.value
                    dlen = int.from_bytes(pdata[1:5], "little")
                    mend = pdata.find(b"\x00\x00", 5) + 2
                    mbytes = pdata[5 : mend - 2]
                    mime = mbytes.decode("utf-16-le")
                    dend = pdata.find(b"\x00\x00", mend) + 2
                    adata = pdata[dend : dend + dlen]
                except Exception:
                    adata = None
            else:
                apic = next(
                    (audio[k] for k in audio.keys() if k.startswith("APIC:")), None
                )
                if apic:
                    adata = apic.data
                    mime = apic.mime

            if not adata:
                return None
            image = Image.open(io.BytesIO(adata))
            ahash = hashlib.md5(adata).hexdigest()
            ext = ".jpg" if "jpeg" in mime else ".png"
            fmt = "JPEG" if "jpeg" in mime else "PNG"
            paths = {}
            for size in self.artwork_sizes:
                ap = self.artwork_cache_dir / f"{ahash}_{size}{ext}"
                if not ap.exists():
                    rimg = image.copy()
                    rimg.thumbnail((size, size), Image.Resampling.LANCZOS)
                    if fmt == "JPEG":
                        rimg.save(ap, format=fmt, quality=95, subsampling=0)
                    else:
                        rimg.save(ap, format=fmt)
                paths[str(size)] = str(ap)
            return paths
        except Exception:
            return None

    def get_track_metadata_light(self, file_path: str) -> dict:
        """
        Performs a fast extraction of essential track metadata using Mutagen's
        easy mode. Useful for displaying basic info without processing artwork.
        """
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            mtime = 0
        info = {
            "path": os.path.abspath(file_path),
            "title": os.path.basename(file_path),
            "artist": translate("Unknown Artist"),
            "artists": [translate("Unknown Artist")],
            "album_artist": translate("Unknown Artist"),
            "album": translate("Unknown Album"),
            "composer": translate("Unknown Composer"),
            "artwork": {},
            "duration": 0,
            "tracknumber": 0,
            "discnumber": 0,
            "year": 0,
            "genre": [],
            "lyrics": "",
            "mtime": mtime,
        }
        try:
            audio = mutagen.File(file_path, easy = True)
            if not audio:
                return info
            if hasattr(audio, "info"):
                info["duration"] = int(audio.info.length)

            info["title"] = self._fix_encoding(
                str(audio.get("title", [info["title"]])[0])
            )

            raw_artist_list = audio.get("artist", [translate("Unknown Artist")])
            raw_art_str = ";".join([str(x) for x in raw_artist_list])
            raw_art_fixed = self._fix_encoding(raw_art_str)

            artists = [a.strip() for a in raw_art_fixed.split(";") if a.strip()]

            if artists:
                info["artists"] = artists
                info["artist"] = artists[0]
            else:
                info["artist"] = raw_art_fixed

            info["album"] = self._fix_encoding(
                str(audio.get("album", [info["album"]])[0])
            )

            raw_genre_list = audio.get("genre", [""])
            raw_gen_str = ";".join([str(x) for x in raw_genre_list])
            raw_gen_fixed = self._fix_encoding(raw_gen_str)

            info["genre"] = [
                g.strip() for g in re.split(r"[,;/|]", raw_gen_fixed) if g.strip()
            ]

            raw_comp = self._fix_encoding(str(audio.get("composer", [""])[0]))
            if raw_comp:
                info["composer"] = raw_comp.strip()

            return info
        except Exception:
            return info

    def get_track_metadata(self, file_path: str) -> dict:
        """
        Performs a comprehensive extraction of track metadata, including artwork,
        lyrics, disc numbers, and handles various quirks across file formats.
        """
        info = {
            "path": os.path.abspath(file_path),
            "title": os.path.basename(file_path),
            "artist": translate("Unknown Artist"),
            "artists": [translate("Unknown Artist")],
            "album_artist": translate("Unknown Artist"),
            "album": translate("Unknown Album"),
            "composer": translate("Unknown Composer"),
            "artwork": {},
            "duration": 0,
            "tracknumber": 0,
            "discnumber": 0,
            "year": 0,
            "genre": [],
            "lyrics": "",
        }
        try:
            audio = mutagen.File(file_path, easy = False)
            if not audio:
                return info

            info["artwork"] = self._save_artwork(audio)

            if hasattr(audio, "info") and hasattr(audio.info, "length"):
                info["duration"] = int(audio.info.length)

            easy = mutagen.File(file_path, easy = True)
            if easy:
                info["title"] = self._fix_encoding(str(easy.get("title", [info["title"]])[0]))

                raw_artist_list = easy.get("artist", [translate("Unknown Artist")])
                raw_art_str = ";".join([str(x) for x in raw_artist_list])
                raw_art_fixed = self._fix_encoding(raw_art_str)
                artists = [a.strip() for a in raw_art_fixed.split(";") if a.strip()]
                if artists:
                    info["artists"] = artists
                    info["artist"] = artists[0]
                else:
                    info["artist"] = raw_art_fixed

                raw_aa = self._fix_encoding(str(easy.get("albumartist", [info["artist"]])[0]))
                info["album_artist"] = raw_aa if raw_aa else info["artist"]

                info["album"] = self._fix_encoding(str(easy.get("album", [info["album"]])[0]))

                raw_genre_list = easy.get("genre", [""])
                raw_gen_str = ";".join([str(x) for x in raw_genre_list])
                raw_gen_fixed = self._fix_encoding(raw_gen_str)
                info["genre"] = [g.strip() for g in re.split(r"[,;/|]", raw_gen_fixed) if g.strip()]

                raw_comp = self._fix_encoding(str(easy.get("composer", [""])[0]))
                info["composer"] = raw_comp.strip()

                raw_tn = str(easy.get("tracknumber", ["0"])[0])
                try:
                    info["tracknumber"] = int(str(raw_tn).split("/")[0])
                except (ValueError, IndexError):
                    pass

                raw_dn = str(easy.get("discnumber", ["0"])[0])
                try:
                    info["discnumber"] = int(str(raw_dn).split("/")[0])
                except (ValueError, IndexError):
                    info["discnumber"] = 0

                raw_dt = str(easy.get("date", ["0"])[0])
                try:
                    info["year"] = int(str(raw_dt).strip()[:4])
                except (ValueError, IndexError):
                    info["year"] = 0

            if isinstance(audio, WAVE):

                if audio.tags and isinstance(audio.tags, ID3):
                    if "TIT2" in audio.tags: info["title"] = self._fix_encoding(str(audio.tags["TIT2"]))

                    if "TPE1" in audio.tags:
                        val = self._fix_encoding(str(audio.tags["TPE1"]))
                        info["artist"] = val
                        info["artists"] = [val]
                        if info["album_artist"] == translate("Unknown Artist"):
                            info["album_artist"] = val

                    if "TPE2" in audio.tags: info["album_artist"] = self._fix_encoding(str(audio.tags["TPE2"]))
                    if "TALB" in audio.tags: info["album"] = self._fix_encoding(str(audio.tags["TALB"]))

                    if "TYER" in audio.tags:
                        try:
                            info["year"] = int(str(audio.tags["TYER"])[:4])
                        except:
                            pass
                    elif "TDRC" in audio.tags:
                        try:
                            info["year"] = int(str(audio.tags["TDRC"])[:4])
                        except:
                            pass

                    if "TCON" in audio.tags:
                        raw_genre = self._fix_encoding(str(audio.tags["TCON"]))
                        info["genre"] = [g.strip() for g in re.split(r"[,;/|]", raw_genre) if g.strip()]

                    if "TRCK" in audio.tags:
                        try:
                            val = str(audio.tags["TRCK"])
                            if "/" in val: val = val.split("/")[0]
                            info["tracknumber"] = int(val)
                        except:
                            pass

                else:
                    if info["title"] == os.path.basename(file_path) and "INAM" in audio.tags:
                        info["title"] = self._fix_encoding(str(audio.tags["INAM"]))

                    if info["artist"] == translate("Unknown Artist") and "IART" in audio.tags:
                        val = self._fix_encoding(str(audio.tags["IART"]))
                        info["artist"] = val
                        info["artists"] = [val]
                        info["album_artist"] = val

                    if info["album"] == translate("Unknown Album") and "IPRD" in audio.tags:
                        info["album"] = self._fix_encoding(str(audio.tags["IPRD"]))

                    if info["year"] == 0 and "ICRD" in audio.tags:
                        try:
                            info["year"] = int(str(audio.tags["ICRD"]).strip()[:4])
                        except:
                            pass

                    if not info["genre"] and "IGNR" in audio.tags:
                        raw_genre = self._fix_encoding(str(audio.tags["IGNR"]))
                        info["genre"] = [g.strip() for g in re.split(r"[,;/|]", raw_genre) if g.strip()]

            if info["tracknumber"] == 0:
                m = re.match(r"^\s*(\d+)", os.path.basename(file_path))
                if m:
                    info["tracknumber"] = int(m.group(1))

            try:
                if isinstance(audio, mutagen.mp3.MP3):
                    uslt = [v for k, v in audio.items() if k.startswith("USLT")]
                    if uslt:
                        info["lyrics"] = self._fix_encoding(uslt[0].text)
                elif isinstance(audio, mutagen.flac.FLAC):
                    if "LYRICS" in audio and audio["LYRICS"]:
                        info["lyrics"] = self._fix_encoding(audio["LYRICS"][0])
                elif isinstance(audio, mutagen.mp4.MP4):
                    if "\xa9lyr" in audio and audio["\xa9lyr"]:
                        info["lyrics"] = self._fix_encoding(audio["\xa9lyr"][0])
                elif "mutagen.asf" in sys.modules and isinstance(audio, mutagen.asf.ASF):
                    if "WM/Lyrics" in audio and audio["WM/Lyrics"]:
                        info["lyrics"] = self._fix_encoding(str(audio["WM/Lyrics"][0].value))
                elif isinstance(audio, WAVE) and isinstance(audio.tags, ID3):
                    uslt = [v for k, v in audio.tags.items() if k.startswith("USLT")]
                    if uslt:
                        info["lyrics"] = self._fix_encoding(uslt[0].text)

            except Exception:
                pass

            if not info["artwork"]:
                fpath = os.path.dirname(file_path)
                fart = self._find_and_save_folder_artwork(fpath)
                if fart:
                    info["artwork"] = fart

            return info

        except Exception:
            return info

    def load_favorites(self) -> dict:
        """
        Loads the saved favorites database (tracks, albums, artists, etc.) from disk.
        """
        default_favorites = {
            "tracks": {},
            "albums": {},
            "artists": {},
            "genres": {},
            "folders": {},
            "playlists": {},
            "composers": {},
        }
        if not self.favorites_path.exists():
            return default_favorites
        try:
            with open(self.favorites_path, "r", encoding="utf-8") as f:
                favorites = json.load(f)
            needs_resave = False
            for key in default_favorites.keys():
                if key in favorites and isinstance(favorites.get(key), list):
                    item_list = favorites[key]
                    if key == "albums":
                        favorites[key] = {
                            json.dumps(item): time.time() for item in item_list
                        }
                    else:
                        favorites[key] = {item: time.time() for item in item_list}
                    needs_resave = True

            if needs_resave:
                self.save_favorites(favorites)
            for key in default_favorites:
                if key not in favorites:
                    favorites[key] = default_favorites[key]
            return favorites
        except (json.JSONDecodeError, IOError):
            return default_favorites

    def save_favorites(self, favorites: dict):
        """
        Saves the favorites database to disk.
        """
        try:
            with open(self.favorites_path, "w", encoding="utf-8") as f:
                json.dump(favorites, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def add_to_favorites(self, item_data, item_type):
        """
        Marks a specific item (track, artist, etc.) as a favorite, saving its timestamp.
        """
        favorites = self.load_favorites()
        key_map = {
            "track": "tracks",
            "album": "albums",
            "artist": "artists",
            "genre": "genres",
            "folder": "folders",
            "playlist": "playlists",
            "composer": "composers",
        }
        fav_key = key_map.get(item_type)
        if not fav_key:
            return
        dict_key = json.dumps(item_data) if item_type == "album" else item_data
        if dict_key not in favorites[fav_key]:
            favorites[fav_key][dict_key] = time.time()
            self.save_favorites(favorites)

        unavailable_items = self.load_unavailable_favorites()
        if fav_key in unavailable_items and dict_key in unavailable_items[fav_key]:
            del unavailable_items[fav_key][dict_key]
            self.save_unavailable_favorites(unavailable_items)

    def remove_from_favorites(self, item_data, item_type):
        """
        Removes an item from the user's favorites list.
        """
        favorites = self.load_favorites()
        key_map = {
            "track": "tracks",
            "album": "albums",
            "artist": "artists",
            "genre": "genres",
            "folder": "folders",
            "playlist": "playlists",
            "composer": "composers",
        }
        fav_key = key_map.get(item_type)
        if not fav_key:
            return
        dict_key = json.dumps(item_data) if item_type == "album" else item_data
        if dict_key in favorites.get(fav_key, {}):
            del favorites[fav_key][dict_key]
            self.save_favorites(favorites)

    def remove_items_from_favorites(self, items_to_remove):
        """
        Batch removes a list of items from the user's favorites list.
        Expects a list of tuples containing (item_data, item_type).
        """
        favorites = self.load_favorites()
        unavailable_items = self.load_unavailable_favorites()
        key_map = {
            "track": "tracks",
            "album": "albums",
            "artist": "artists",
            "genre": "genres",
            "folder": "folders",
            "playlist": "playlists",
            "composer": "composers",
        }
        favorites_changed = False
        unavailable_changed = False
        for item_data, item_type in items_to_remove:
            fav_key = key_map.get(item_type)
            if not fav_key:
                continue
            dict_key = json.dumps(item_data) if item_type == "album" else item_data
            if dict_key in favorites.get(fav_key, {}):
                del favorites[fav_key][dict_key]
                favorites_changed = True
            if dict_key in unavailable_items.get(fav_key, {}):
                del unavailable_items[fav_key][dict_key]
                unavailable_changed = True
        if favorites_changed:
            self.save_favorites(favorites)
        if unavailable_changed:
            self.save_unavailable_favorites(unavailable_items)

    def is_favorite(self, item_data, item_type):
        """
        Checks whether a specific item is marked as a favorite.
        """
        favorites = self.load_favorites()
        key_map = {
            "track": "tracks",
            "album": "albums",
            "artist": "artists",
            "genre": "genres",
            "folder": "folders",
            "playlist": "playlists",
            "composer": "composers",
        }
        fav_key = key_map.get(item_type)
        if not fav_key:
            return False
        dict_key = json.dumps(item_data) if item_type == "album" else item_data
        return dict_key in favorites.get(fav_key, {})

    def create_mixtape(self, playlist_name, tracks, target_dir):
        """
        Copies a set of tracks into a newly created folder and generates an M3U
        playlist, effectively creating a portable mixtape.
        """
        mixtape_folder_path = Path(target_dir) / playlist_name
        try:
            mixtape_folder_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, str(e), None

        playlist_file_path = mixtape_folder_path / f"{playlist_name}.m3u"
        relative_paths = []
        padding = len(str(len(tracks)))
        if padding < 2:
            padding = 2

        for i, track in enumerate(tracks, 1):
            original_path = Path(track["path"])
            if not original_path.exists():
                continue
            prefix = str(i).zfill(padding)
            clean_name = original_path.name
            new_file_name = f"{prefix} - {clean_name}"
            destination_path = mixtape_folder_path / new_file_name
            try:
                if not destination_path.exists():
                    shutil.copy2(original_path, destination_path)
                relative_paths.append(new_file_name)
            except Exception:
                pass

        try:
            with open(playlist_file_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for rel_path in relative_paths:
                    f.write(f"{rel_path}\n")
            return True, "Success", str(mixtape_folder_path)
        except Exception as e:
            return False, str(e), str(mixtape_folder_path)

    def migrate_entity_keys(self, old_key, new_key, entity_type="album"):
        """
        Updates an entity key (e.g., after an album name edit) across favorites,
        stats, and chart archives, preserving user history for the item.
        """
        old_key_str = (
            json.dumps(list(old_key)) if isinstance(old_key, tuple) else old_key
        )
        new_key_str = (
            json.dumps(list(new_key)) if isinstance(new_key, tuple) else new_key
        )

        favorites = self.load_favorites()
        fav_key_map = {
            "album": "albums",
            "artist": "artists",
            "genre": "genres",
            "composer": "composers",
        }
        section = fav_key_map.get(entity_type)
        if section and old_key_str in favorites.get(section, {}):
            timestamp = favorites[section].pop(old_key_str)
            favorites[section][new_key_str] = timestamp
            self.save_favorites(favorites)

        stats = self.load_play_stats()
        if section and old_key_str in stats.get(section, {}):
            stat_data = stats[section].pop(old_key_str)
            if new_key_str in stats[section]:
                existing = stats[section][new_key_str]
                existing["all_time"] += stat_data.get("all_time", 0)
                existing["monthly"] += stat_data.get("monthly", 0)
            else:
                stats[section][new_key_str] = stat_data
            self.save_play_stats(stats)

        archives = self.load_charts_archive()
        archives_changed = False
        for month, month_data in archives.items():
            if section and section in month_data:
                updated_list = []
                for item in month_data[section]:
                    key, count = item[0], item[1]
                    if key == old_key_str:
                        updated_list.append([new_key_str, count])
                        archives_changed = True
                    else:
                        updated_list.append(item)
                month_data[section] = updated_list
        if archives_changed:
            self.save_charts_archive(archives)

        self.reset_last_played_entity_metadata()

    def migrate_album_favorites_on_setting_change(
        self, all_tracks, to_unique_folders: bool
    ):
        """
        Migrates album favorite keys when the user changes the 'treat folders
        as unique albums' setting to ensure favorites are not lost.
        """
        favorites = self.load_favorites()
        if "albums" not in favorites:
            return
        old_fav_albums = favorites["albums"]
        new_fav_albums = {}
        count_migrated = 0

        album_year_map = {}
        for track in all_tracks:
            aa = (
                track.get("album_artist")
                or track.get("artist")
                or translate("Unknown Artist")
            )
            alb = track.get("album") or translate("Unknown Album")
            yr = track.get("year", 0)
            simple_key = (aa, alb)
            if simple_key not in album_year_map:
                album_year_map[simple_key] = yr

        for track in all_tracks:
            aa = (
                track.get("album_artist")
                or track.get("artist")
                or translate("Unknown Artist")
            )
            alb = track.get("album") or translate("Unknown Album")
            folder = os.path.dirname(track["path"])
            yr = track.get("year", 0)

            if to_unique_folders:
                old_key_list = [aa, alb, yr]
                new_key_list = [aa, alb, yr, folder]
            else:
                old_key_list = [aa, alb, yr, folder]
                new_key_list = [aa, alb, yr]

            old_key_str = json.dumps(old_key_list)
            new_key_str = json.dumps(new_key_list)

            if old_key_str in old_fav_albums:
                timestamp = old_fav_albums[old_key_str]
                new_fav_albums[new_key_str] = timestamp
                count_migrated += 1
            else:
                if to_unique_folders:
                    old_key_list_legacy = [aa, alb]
                else:
                    old_key_list_legacy = [aa, alb, folder]

                old_key_str_legacy = json.dumps(old_key_list_legacy)

                if old_key_str_legacy in old_fav_albums:
                    timestamp = old_fav_albums[old_key_str_legacy]
                    new_fav_albums[new_key_str] = timestamp
                    count_migrated += 1

        if count_migrated > 0:
            favorites["albums"] = new_fav_albums
            self.save_favorites(favorites)

    def get_top_tracks_of_month(self, all_tracks_map, limit=10, sort_func=None):
        """Returns top popular tracks for the current month with unified sorting."""
        stats = self.load_play_stats()
        track_stats = stats.get("tracks", {})

        scored_tracks = []
        for path, data in track_stats.items():
            count = data.get("monthly", 0) if isinstance(data, dict) else 0
            if count > 0 and path in all_tracks_map:
                scored_tracks.append((all_tracks_map[path], count))

        if sort_func is None:
            sort_func = lambda s: str(s).lower() if s else ""

        scored_tracks.sort(
            key=lambda x: (
                -x[1],
                sort_func(x[0].get("title", "")),
                sort_func(x[0].get("artist", "")),
            )
        )

        return [t[0] for t in scored_tracks[:limit]]

    def generate_my_wave_queue(self, data_manager, limit=MY_WAVE_DEFAULT_LIMIT):
        """
        Generates a 'My Wave' queue based on interest weights.
        """
        favorites = self.load_favorites()
        fav_tracks = set(favorites.get("tracks", {}).keys())
        fav_artists = set(favorites.get("artists", {}).keys())
        fav_genres = set(favorites.get("genres", {}).keys())
        fav_albums = {tuple(json.loads(k)) for k in favorites.get("albums", {}).keys()}

        candidates = []
        weights = []

        all_tracks = data_manager.all_tracks
        sample_size = min(len(all_tracks), MY_WAVE_SAMPLE_POOL_SIZE)
        sample_pool = random.sample(all_tracks, sample_size)

        for track in sample_pool:
            score = MY_WAVE_BASE_SCORE

            if track["path"] in fav_tracks:
                score += MY_WAVE_BONUS_FAV_TRACK

            track_artist = track.get("artist")
            if track_artist in fav_artists:
                score += MY_WAVE_BONUS_FAV_ARTIST

            if (track.get("album_artist"), track.get("album")) in fav_albums:
                score += MY_WAVE_BONUS_FAV_ALBUM

            for g in track.get("genre", []):
                if g in fav_genres:
                    score += MY_WAVE_BONUS_FAV_GENRE
                    break

            candidates.append(track)
            weights.append(score)

        if not candidates:
            return []

        chosen = random.choices(candidates, weights=weights, k=limit * MY_WAVE_OVERSAMPLE_MULTIPLIER)

        seen = set()
        unique_queue = []
        for t in chosen:
            if t["path"] not in seen:
                unique_queue.append(t)
                seen.add(t["path"])
            if len(unique_queue) >= limit:
                break

        return unique_queue

    def get_default_search_providers(self):
        """Returns a base (immutable) list of search providers."""
        return [
            {
                "name": "Google",
                "url": "https://www.google.com/search?q={query}",
                "is_custom": False,
                "lyrics": True,
            },
            {
                "name": "DuckDuckGo",
                "url": "https://duckduckgo.com/?q={query}",
                "is_custom": False,
                "lyrics": True,
            },
            {
                "name": "Genius",
                "url": "https://genius.com/search?q={query}",
                "is_custom": False,
                "lyrics": True,
            },
            {
                "name": "Discogs",
                "url": "https://www.discogs.com/search/?q={query}&type=all",
                "is_custom": False,
                "lyrics": False,
            },
            {
                "name": "LRCLIB",
                "url": "https://lrclib.net/search/{query}",
                "is_custom": False,
                "lyrics": True,
            },
            {
                "name": "MusicBrainz",
                "url": "https://musicbrainz.org/search?query={query}&type=artist&method=indexed",
                "is_custom": False,
                "lyrics": False,
            },
            {
                "name": "Spotify",
                "url": "https://open.spotify.com/search/{query}",
                "is_custom": False,
                "lyrics": False,
            },
            {
                "name": "YouTube",
                "url": "https://www.youtube.com/results?search_query={query}",
                "is_custom": False,
                "lyrics": False,
            },
        ]

    def load_disabled_search_providers(self) -> list:
        """Loads a list of disabled search provider names."""
        if not self.disabled_search_providers_path.exists():
            return []
        try:
            with open(self.disabled_search_providers_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save_disabled_search_providers(self, disabled_list: list):
        """
        Saves the list of disabled search providers to disk.
        """
        try:
            with open(self.disabled_search_providers_path, "w", encoding="utf-8") as f:
                json.dump(disabled_list, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    def toggle_search_provider_visibility(self, name: str):
        """Toggles the visibility of a search provider by name."""
        disabled = self.load_disabled_search_providers()
        if name in disabled:
            disabled.remove(name)
        else:
            disabled.append(name)
        self.save_disabled_search_providers(disabled)

    def load_search_links(self) -> list:
        """
        Loads the combined list of default and custom search providers,
        marking them enabled or disabled based on user preferences.
        """
        links = self.get_default_search_providers()

        if self.search_links_path.exists():
            try:
                with open(self.search_links_path, "r", encoding="utf-8") as f:
                    custom_links = json.load(f)
                    if isinstance(custom_links, list):
                        links.extend(custom_links)
            except Exception as e:
                print(f"Error loading custom search links: {e}")

        disabled_names = set(self.load_disabled_search_providers())

        for link in links:
            link["enabled"] = link["name"] not in disabled_names

        return links

    def add_custom_search_link(self, name, url_template, is_lyrics_suitable=False):
        """
        Creates a new user-defined external search link and saves it to disk.
        """
        current_custom = []
        if self.search_links_path.exists():
            try:
                with open(self.search_links_path, "r", encoding="utf-8") as f:
                    current_custom = json.load(f)
                    if not isinstance(current_custom, list):
                        current_custom = []
            except:
                current_custom = []

        new_link = {
            "name": name,
            "url": url_template,
            "is_custom": True,
            "lyrics": is_lyrics_suitable,
        }
        current_custom.append(new_link)

        try:
            with open(self.search_links_path, "w", encoding="utf-8") as f:
                json.dump(current_custom, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"Error saving search link: {e}")
            return False

    def edit_custom_search_link(self, old_name, new_name, new_url, new_lyrics_flag):
        """Edits an existing custom search link."""
        if not self.search_links_path.exists():
            return False

        try:
            with open(self.search_links_path, "r", encoding="utf-8") as f:
                current_custom = json.load(f)
                if not isinstance(current_custom, list):
                    return False

            updated = False
            for link in current_custom:
                if link.get("name") == old_name and link.get("is_custom"):
                    link["name"] = new_name
                    link["url"] = new_url
                    link["lyrics"] = new_lyrics_flag
                    updated = True
                    break

            if updated:
                with open(self.search_links_path, "w", encoding="utf-8") as f:
                    json.dump(current_custom, f, ensure_ascii=False, indent=4)
                return True
            return False

        except Exception as e:
            print(f"Error editing search link: {e}")
            return False

    def remove_custom_search_link(self, name):
        """
        Deletes a custom user-defined search link by name.
        """
        if not self.search_links_path.exists():
            return False
        try:
            with open(self.search_links_path, "r", encoding="utf-8") as f:
                current_custom = json.load(f)
            new_custom = [l for l in current_custom if l.get("name") != name]
            with open(self.search_links_path, "w", encoding="utf-8") as f:
                json.dump(new_custom, f, ensure_ascii=False, indent=4)
            return True
        except Exception:
            return False

    def add_tracks_to_playlist(self, playlist_path, track_paths, path_to_track_map):
        """
        Adds a list of track paths to an existing m3u/m3u8 playlist.
        Returns tuple (new_count, total_duration_seconds) or False.
        """
        if not playlist_path or not os.path.exists(playlist_path):
            return False

        if not track_paths:
            return False

        try:
            with open(playlist_path, "r", encoding = "utf-8") as f:
                content = f.read()

            needs_newline = content and not content.endswith("\n")

            with open(playlist_path, "a", encoding = "utf-8") as f:
                if needs_newline:
                    f.write("\n")
                for path in track_paths:
                    f.write(f"{path}\n")

            if playlist_path in self.playlists_index:
                del self.playlists_index[playlist_path]

            tracks = self.load_playlist(playlist_path, path_to_track_map)

            new_count = len(tracks)
            total_seconds = sum(t.get('duration', 0) for t in tracks)

            first_artwork = next((t.get("artwork") for t in tracks if t.get("artwork")), None)

            try:
                new_mtime = os.path.getmtime(playlist_path)
            except OSError:
                new_mtime = 0

            self.playlists_metadata[playlist_path] = {
                "count": new_count,
                "duration": total_seconds,
                "artwork": first_artwork,
                "mtime": new_mtime
            }

            return new_count, total_seconds

        except Exception as e:
            print(f"Error adding tracks to playlist: {e}")
            return False

    def insert_tracks_into_playlist(self, playlist_path, track_paths, index):
        """
        Inserts a list of track paths into a playlist at a specific index.
        """
        if not playlist_path or not os.path.exists(playlist_path):
            return False

        if not track_paths:
            return False

        try:
            with open(playlist_path, "r", encoding = "utf-8") as f:
                lines = f.read().splitlines()

            insert_line_idx = len(lines)
            track_counter = 0

            for i, line in enumerate(lines):
                sline = line.strip()
                if sline and not sline.startswith("#"):
                    if track_counter == index:
                        insert_line_idx = i
                        break
                    track_counter += 1

            for path in reversed(track_paths):
                lines.insert(insert_line_idx, path)

            with open(playlist_path, "w", encoding = "utf-8") as f:
                f.write("\n".join(lines))
                f.write("\n")

            if playlist_path in self.playlists_index:
                del self.playlists_index[playlist_path]

            if playlist_path in self.playlists_metadata:
                del self.playlists_metadata[playlist_path]

            return True

        except Exception as e:
            print(f"Error inserting tracks into playlist: {e}")
            return False

    def get_raw_metadata(self, file_path: str) -> list:
        """
        Extracts all raw metadata from a file using Mutagen.
        Returns a list of tuples: [(Readable Key, Value), ...].
        Results are not cached.
        """
        results = []

        tag_mapping = {
            "TIT2": "Title",
            "TPE1": "Artist",
            "TALB": "Album",
            "TYER": "Year",
            "TRCK": "Track #",
            "TPOS": "Disc #",
            "TCON": "Genre",
            "TPE2": "Album Artist",
            "TCOM": "Composer",
            "TDRC": "Recording Date",
            "USLT": "Lyrics",
            "APIC": "Cover Art",

            "COMM": "Comment",
            "TSRC": "ISRC",
            "TSSE": "Encoder Settings",
            "TCOP": "Copyright",
            "WOAS": "Source URL",
            "POPM": "Popularimeter",
            "PRIV": "Private Data",
            "UFID": "Unique File ID",
            "TBPM": "BPM",
            "TLEN": "Length (ms)",
            "MCDI": "CD Identifier",
            "TENC": "Encoded By",
            "WXXX": "User URL",
            "TXXX": "User Defined",
        }

        try:
            audio = mutagen.File(file_path)
            if not audio:
                return []

            if hasattr(audio, "info"):
                results.append(("Format", type(audio).__name__))
                results.append(("Duration", f"{int(audio.info.length)} s"))

                if hasattr(audio.info, "bitrate") and audio.info.bitrate:
                    results.append(("Bitrate", f"{int(audio.info.bitrate / 1000)} kbps"))
                else:
                    results.append(("Bitrate", "N/A"))

                if hasattr(audio.info, "sample_rate") and audio.info.sample_rate:
                    results.append(("Sample Rate", f"{audio.info.sample_rate} Hz"))

                channels = getattr(audio.info, "channels", "N/A")
                results.append(("Channels", str(channels)))

                results.append(("---", "---"))

            if hasattr(audio, "tags") and audio.tags:
                for key, value in audio.tags.items():
                    key_str = str(key)
                    val_str = str(value)

                    readable_key = key_str

                    if key_str.startswith("COMM"):
                        readable_key = "Comment"
                        if ":" in key_str:
                            parts = key_str.split(":")
                            if len(parts) > 2 and parts[1]:
                                readable_key = f"Comment ({parts[1]})"

                    elif key_str.startswith("TXXX"):
                        if ":" in key_str:
                            readable_key = key_str.split(":", 1)[1]
                        else:
                            readable_key = "User Defined Text"

                    elif key_str.startswith("WXXX"):
                        if ":" in key_str:
                            readable_key = f"URL ({key_str.split(':', 1)[1]})"
                        else:
                            readable_key = "User URL"

                    elif key_str[:4] in tag_mapping:
                        readable_key = tag_mapping[key_str[:4]]

                    elif key_str.isupper():
                        readable_key = key_str.replace("_", " ").title()


                    if "APIC" in key_str or "Picture" in key_str:
                        val_str = f"<{len(audio.tags[key].data)} bytes image data>"
                    elif len(val_str) > 200:
                        val_str = val_str[:200] + "..."

                    results.append((readable_key, val_str))

            results.sort(key = lambda x: x[0])

        except Exception as e:
            results.append(("Error reading tags", str(e)))

        return results