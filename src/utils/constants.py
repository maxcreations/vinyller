"""
Vinyller — Constants
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

# Base info
VINYLLER_FOLDER = ".vinyller"
APP_VERSION = "1.1.0"

class ArtistSource:
    ARTIST = "artist"
    ALBUM_ARTIST = "albumartist"

# Batch of mini-cards for initial loading
BATCH_SIZE = 24

# Batch of track cards for initial loading
BATCH_SIZE_ALLTRACKS = 4

# Delay before awarding rating points (seconds)
STATS_AWARD_DELAY_S = 20

# How often to check if rating can be saved (seconds)
STATS_POLL_INTERVAL_S = 30

# Trigger for saving rating (minutes)
STATS_SAVE_TRIGGER_INTERVAL_M = 10


# Minimum time required to count a listen (seconds)
STATS_AWARD_MIN_S = 15

# Percentage of track length required to count a listen
STATS_AWARD_PERCENTAGE = 0.5  # 50%

# Maximum time (cap) after which a track is counted regardless (seconds)
STATS_AWARD_CAP_S = 240  # 4 minutes

# N seconds to be included in history
HISTORY_MIN_S = 5

# Maximum number of tracks in history
HISTORY_LIMIT = 1000

# Maximum number of backups
MAX_BACKUPS = 5

# Maximum number of tracks in charts
TOP_TRACKS_LIMIT = 1000

# My Wave algorithm settings

# Default size of the generated queue
MY_WAVE_DEFAULT_LIMIT = 50

# Maximum number of tracks randomly sampled from the entire library for initial analysis.
# Prevents high CPU load on massive libraries.
MY_WAVE_SAMPLE_POOL_SIZE = 2000

# Oversampling multiplier. The algorithm initially picks more tracks (limit * MULTIPLIER)
# to guarantee enough unique tracks remain after deduplication.
MY_WAVE_OVERSAMPLE_MULTIPLIER = 2

# Base selection weight (chance) for any track in the sample pool
MY_WAVE_BASE_SCORE = 1

# Weight bonus applied if the track itself is in favorites
MY_WAVE_BONUS_FAV_TRACK = 50

# Weight bonus applied if the track's artist is in favorites
MY_WAVE_BONUS_FAV_ARTIST = 30

# Weight bonus applied if the track's album is in favorites
MY_WAVE_BONUS_FAV_ALBUM = 20

# Weight bonus applied if at least one of the track's genres is in favorites
MY_WAVE_BONUS_FAV_GENRE = 15

# List of translations included
SUPPORTED_LANGUAGES = {
    "Dansk": ("da", "assets/flags/dk.svg"),
    "Deutsch": ("de", "assets/flags/de.svg"),
    "English": ("en", "assets/flags/gb.svg"),
    "Español": ("es", "assets/flags/es.svg"),
    "Français": ("fr", "assets/flags/fr.svg"),
    "हिन्दी": ("hi", "assets/flags/in.svg"),
    "Italiano": ("it", "assets/flags/it.svg"),
    "日本語": ("ja", "assets/flags/jp.svg"),
    "한국어": ("ko", "assets/flags/kr.svg"),
    "Nederlands": ("nl", "assets/flags/nl.svg"),
    "Norsk": ("nb", "assets/flags/no.svg"),
    "Polski": ("pl", "assets/flags/pl.svg"),
    "Português": ("pt", "assets/flags/pt.svg"),
    "Русский": ("ru", "assets/flags/ru.svg"),
    "Svenska": ("sv", "assets/flags/se.svg"),
    "Tiếng Việt": ("vi", "assets/flags/vn.svg"),
    "Türkçe": ("tr", "assets/flags/tr.svg"),
    "中文": ("zh", "assets/flags/cn.svg"),
}

# List of articles to ignore when sorting
ARTICLES_TO_IGNORE = (
    # English
    "the", "a", "an",
    # German
    "der", "die", "das", "ein", "eine",
    # Spanish & Portuguese
    "el", "la", "los", "las", "un", "una", "unos", "unas", "o", "os", "as", "um", "uma", "uns", "umas",
    # French
    "le", "les", "une", "des",
    # Italian
    "il", "lo", "gli", "uno",
    # Dutch
    "de", "het", "een",
    # Swedish
    "en", "ett", "den", "det"
)

# List of favorite icons
FAVORITE_ICONS = [
    ("Heart", "favorite_heart"),
    ("Star", "favorite_star"),
    ("Rock", "favorite_rock"),
]