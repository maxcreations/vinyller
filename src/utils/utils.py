"""
Vinyller — Utilities
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

import html
import os
import re
import sys
from datetime import datetime
from typing import Optional

import requests
from PyQt6.QtCore import (
    QByteArray, QSize, Qt
)
from PyQt6.QtGui import (
    QColor, QIcon,
    QPainter, QPixmap
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication
)

from src.utils.utils_translator import translate


def resource_path(relative_path):
    """
    Get the absolute path to a resource.
    Works for development and for PyInstaller bundles.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def format_time(ms):
    """
    Formats time from milliseconds to a string in HH:MM:SS or MM:SS format.
    """
    seconds = ms // 1000
    if seconds >= 3600:
        return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"
    else:
        return f"{seconds // 60:02}:{seconds % 60:02}"


def format_month_year(value) -> str:
    """
    Formats a date into a localized 'Month YYYY' string.

    Args:
        value: Can be a float/int (Unix timestamp) or a string in 'YYYY-MM' format.

    Returns:
        str: Formatted date or localized 'Unknown date' on failure.
    """
    try:
        dt = None
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value)
        elif isinstance(value, str):
            dt = datetime.strptime(value, "%Y-%m")

        if dt:
            month_keys = [
                translate("January"),
                translate("February"),
                translate("March"),
                translate("April"),
                translate("May"),
                translate("June"),
                translate("July"),
                translate("August"),
                translate("September"),
                translate("October"),
                translate("November"),
                translate("December")
            ]
            # month is 1-indexed in datetime objects
            month_name = month_keys[dt.month - 1]
            return f"{month_name} {dt.year}"
    except Exception:
        pass

    # Fallback: return original value as string if parsing fails
    return str(value) if value is not None else translate("Unknown date")

def create_svg_icon(
    svg_path: str, color: str | QColor, size: Optional[QSize] = None
) -> QIcon:
    """
    Creates a QIcon from an SVG file, recoloring it to the specified color.
    Accounts for high pixel density screens (HiDPI/Retina).

    For correct operation, the fill color in the SVG file should be set
    to "currentColor" (e.g., fill="currentColor").

    Args:
        svg_path (str): Relative path to the SVG file.
        color (str | QColor): New color for the icon (e.g., "#ff0000" or QColor object).
        size (Optional[QSize]): Desired logical size. If None, the default SVG size is used.

    Returns:
        QIcon: The colored icon.
    """
    full_path = resource_path(svg_path)
    if not os.path.exists(full_path):
        print(f"Warning: SVG file not found at {full_path}")
        return QIcon()

    with open(full_path, "r", encoding="utf-8") as f:
        svg_data = f.read()

    if isinstance(color, QColor):
        color_str = color.name()
    else:
        color_str = color

    if "currentColor" in svg_data:
        modified_svg = svg_data.replace("currentColor", color_str)
    else:
        # Fallback for SVGs that don't use "currentColor" attribute
        temp_svg = svg_data.replace('fill="#000000"', f'fill="{color_str}"')
        temp_svg = temp_svg.replace('fill="black"', f'fill="{color_str}"')
        temp_svg = temp_svg.replace('stroke="#000000"', f'stroke="{color_str}"')
        modified_svg = temp_svg.replace('stroke="black"', f'stroke="{color_str}"')
        if svg_data == modified_svg:
            print(
                f"Warning: Could not automatically recolor SVG: {full_path}. "
                f"For best results, edit the SVG and set the desired fill/stroke to 'currentColor'."
            )

    renderer = QSvgRenderer(QByteArray(modified_svg.encode("utf-8")))

    # Handle High DPI / Retina scaling
    logical_size = size if size else renderer.defaultSize()

    app_instance = QApplication.instance()
    dpr = app_instance.devicePixelRatio() if app_instance else 1.0

    physical_size = QSize(
        int(logical_size.width() * dpr), int(logical_size.height() * dpr)
    )
    pixmap = QPixmap(physical_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    # Reset device pixel ratio so the pixmap displays correctly in the UI
    pixmap.setDevicePixelRatio(dpr)

    return QIcon(pixmap)


def sanitize_lyrics(text):
    """
    Cleans song lyrics by removing HTML tags, special Unicode characters,
    and excessive line breaks.
    """
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\u200b\ufeff]", "", text) # Remove zero-width spaces/BOM
    text = text.replace("\u00a0", " ") # Replace non-breaking spaces
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text) # Limit consecutive newlines

    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()


def fetch_lyrics_from_lrclib(artist, title, album=None, duration=None):
    """
    Fetches lyrics from LRCLIB API with a prioritized matching system.

    Search Strategy:
    1. Exact match via /get endpoint.
    2. Search via /search + duration match (±3 sec).
    3. Search via /search + duration match (±20 sec).
    4. Fallback to the first search result.
    """

    def clean_title(text):
        """Removes metadata like '(feat. ...)' or '[Live]' from the track title."""
        if not text:
            return ""
        text = re.sub(
            r"\s*[\[\(](feat|ft|remast|live|deluxe|edit).*?[\]\)]",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip()

    def get_clean_text(item):
        """Extracts and sanitizes plain or synced lyrics from an API result item."""
        if not item:
            return None

        raw_text = ""
        plain = item.get("plainLyrics")

        if plain:
            raw_text = plain
        else:
            synced = item.get("syncedLyrics")
            if synced:
                # Strip timestamps [mm:ss.xx] from synced lyrics
                clean = re.sub(r"\[\d+:\d+(\.\d+)?\]", "", synced)
                raw_text = clean

        return sanitize_lyrics(raw_text) if raw_text else None

    try:
        # Step 1: Attempt exact match
        url_get = "https://lrclib.net/api/get"
        params_get = {"artist_name": artist, "track_name": title}
        if album:
            params_get["album_name"] = album
        if duration:
            params_get["duration"] = int(duration)

        try:
            response = requests.get(url_get, params=params_get, timeout=5)
            if response.status_code == 200:
                return get_clean_text(response.json())
        except:
            pass

        # Step 2: Wider search with duration-based filtering
        clean_track_name = clean_title(title)
        if not clean_track_name:
            clean_track_name = title

        search_url = "https://lrclib.net/api/search"
        search_params = {"q": f"{artist} {clean_track_name}"}

        resp_search = requests.get(search_url, params=search_params, timeout=5)

        if resp_search.status_code != 200:
            return None

        results = resp_search.json()

        if not results:
            return False

        if not duration:
            return get_clean_text(results[0])

        target_duration = int(duration)

        # Priority: match within 3 seconds
        for item in results:
            item_dur = item.get("duration")
            if item_dur and abs(item_dur - target_duration) <= 3:
                return get_clean_text(item)

        # Priority: match within 20 seconds
        for item in results:
            item_dur = item.get("duration")
            if item_dur and abs(item_dur - target_duration) <= 20:
                return get_clean_text(item)

        # Fallback: take the first result
        result = get_clean_text(results[0])
        return result if result else False

    except Exception as e:
        print(f"Lyrics fetch error: {e}")
        return None


def parse_cue_sheet(cue_path):
    """
    Parses a .cue file to extract the target audio file name and track metadata.

    Returns:
        tuple: (audio_file_name, tracks_list)
        tracks_list contains dictionaries with:
        number, title, artist, album, album_artist, start_ms, duration_ms.
    """
    tracks = []
    current_file = None

    album_artist = None
    album_title = None

    lines = []
    encodings = ["utf-8", "cp1251", "latin1"]

    # Try different encodings to handle localized CUE sheets
    for enc in encodings:
        try:
            with open(cue_path, "r", encoding = enc) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue

    if not lines:
        return None, []

    current_track = {}

    for line in lines:
        line = line.strip()

        if line.startswith("FILE"):
            parts = line.split('"')
            if len(parts) >= 2:
                current_file = parts[1]

        elif line.startswith("PERFORMER") and not current_track:
            # Album artist
            parts = line.split('"')
            if len(parts) >= 2:
                album_artist = parts[1]

        elif line.startswith("TITLE") and not current_track:
            # Album title
            parts = line.split('"')
            if len(parts) >= 2:
                album_title = parts[1]

        elif line.startswith("TRACK"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    current_track = {"number": int(parts[1]), "title": "", "artist": ""}
                    tracks.append(current_track)
                except ValueError:
                    pass

        elif line.startswith("TITLE") and current_track:
            # Track title
            parts = line.split('"')
            if len(parts) >= 2:
                current_track["title"] = parts[1]

        elif line.startswith("PERFORMER") and current_track:
            # Track artist
            parts = line.split('"')
            if len(parts) >= 2:
                current_track["artist"] = parts[1]

        elif line.startswith("REM COMPOSER") and current_track:
            if '"' in line:
                parts = line.split('"')
                if len(parts) >= 2:
                    current_track["composer"] = parts[1]
            else:
                parts = line.split(maxsplit = 2)
                if len(parts) >= 3:
                    current_track["composer"] = parts[2]

        elif line.startswith("SONGWRITER") and current_track:
            parts = line.split('"')
            if len(parts) >= 2:
                current_track["composer"] = parts[1]

        elif line.startswith("INDEX 01") and current_track:
            # Track start time in MM:SS:FF format (FF = frames, 75 frames per second)
            parts = line.split()
            if len(parts) >= 3:
                time_str = parts[2]
                try:
                    m, s, f = map(int, time_str.split(":"))
                    ms = (m * 60 * 1000) + (s * 1000) + int((f / 75) * 1000)
                    current_track["start_ms"] = ms
                except ValueError:
                    pass

    # Calculate durations based on the start time of the next track
    for i in range(len(tracks)):
        if i < len(tracks) - 1:
            if "start_ms" in tracks[i] and "start_ms" in tracks[i + 1]:
                tracks[i]["duration_ms"] = (
                        tracks[i + 1]["start_ms"] - tracks[i]["start_ms"]
                )
        else:
            # Last track duration is unknown without the audio file length
            tracks[i]["duration_ms"] = 0

    # Apply album-level metadata to individual tracks if specific data is missing
    for t in tracks:
        if album_artist:
            t["album_artist"] = album_artist
            if not t.get("artist"):
                t["artist"] = album_artist

        if album_title:
            t["album"] = album_title

    return current_file, tracks


def is_onefile_build() -> bool:
    """
    Determines if the application is running as a single executable (--onefile) via PyInstaller.
    Compatible with Windows, Linux, and macOS (.app bundles).
    """
    if not getattr(sys, 'frozen', False) or not hasattr(sys, '_MEIPASS'):
        return False

    # Indicator 1: In --onefile mode, PyInstaller unpacks files into a temporary _MEIxxxxxx folder
    meipass_basename = os.path.basename(os.path.normpath(sys._MEIPASS))
    if meipass_basename.startswith('_MEI'):
        return True

    # Indicator 2: Handle macOS .app bundles (--onedir equivalent)
    if sys.platform == 'darwin' and '.app/Contents/' in sys._MEIPASS:
        return False

    # Indicator 3: Check where _MEIPASS is located relative to the executable (Windows/Linux)
    exe_dir = os.path.normcase(os.path.abspath(os.path.dirname(sys.executable)))
    meipass_dir = os.path.normcase(os.path.abspath(sys._MEIPASS))

    # In --onedir mode, resources are either right next to the exe or in the _internal subfolder
    if meipass_dir == exe_dir or meipass_dir.startswith(exe_dir + os.sep):
        return False

    # Fallback for edge cases
    return True