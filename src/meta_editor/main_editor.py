"""
Vinyller — Metadata editor dialog
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

import tempfile

import requests
from PyQt6.QtCore import (
    pyqtSignal, QSize, Qt, QTimer
)
from PyQt6.QtGui import (
    QColor, QIcon, QPixmap
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDialog, QDialogButtonBox,
    QHBoxLayout, QHeaderView, QLabel, QListWidgetItem, QPushButton,
    QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from src.meta_editor.album_batch_editor import AlbumBatchEditor
from src.meta_editor.mixed_batch_editor import MixedBatchEditor
from src.meta_editor.single_track_editor import SingleTrackEditor
from src.ui.custom_base_dialogs import StyledDialog
from src.ui.custom_base_widgets import (
    StyledLineEdit, StyledListWidget, set_custom_tooltip
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate

TAG_DEFINITIONS = {
    "Title": {"MP3": "TIT2", "FLAC": "TITLE", "OggVorbis": "TITLE", "MP4": "©nam", "ASF": "Title"},
    "Artist": {"MP3": "TPE1", "FLAC": "ARTIST", "OggVorbis": "ARTIST", "MP4": "©ART", "ASF": "Author"},
    "Album": {"MP3": "TALB", "FLAC": "ALBUM", "OggVorbis": "ALBUM", "MP4": "©alb", "ASF": "WM/AlbumTitle"},
    "Album Artist": {"MP3": "TPE2", "FLAC": "ALBUMARTIST", "OggVorbis": "ALBUMARTIST", "MP4": "aART",
                     "ASF": "WM/AlbumArtist"},
    "Composer": {"MP3": "TCOM", "FLAC": "COMPOSER", "OggVorbis": "COMPOSER", "MP4": "©wrt", "ASF": "WM/Composer"},
    "Genre": {"MP3": "TCON", "FLAC": "GENRE", "OggVorbis": "GENRE", "MP4": "©gen", "ASF": "WM/Genre"},
    "Year": {"MP3": "TDRC/TYER", "FLAC": "DATE", "OggVorbis": "DATE", "MP4": "©day", "ASF": "WM/Year"},
    "Track Number": {"MP3": "TRCK", "FLAC": "TRACKNUMBER", "OggVorbis": "TRACKNUMBER", "MP4": "trkn",
                     "ASF": "WM/TrackNumber"},
    "Disc Number": {"MP3": "TPOS", "FLAC": "DISCNUMBER", "OggVorbis": "DISCNUMBER", "MP4": "disk",
                    "ASF": "WM/PartOfSet"},
    "Lyrics": {"MP3": "USLT", "FLAC": "LYRICS", "OggVorbis": "LYRICS", "MP4": "©lyr", "ASF": "WM/Lyrics"},
    "original_year": {"MP3": "TDOR", "FLAC": "ORIGINALDATE", "OggVorbis": "ORIGINALDATE", "MP4": "©day",
                      "ASF": "OriginalReleaseYear"},
    "comment": {"MP3": "COMM", "FLAC": "COMMENT", "OggVorbis": "COMMENT", "MP4": "©cmt", "ASF": "Description"},
    "copyright": {"MP3": "TCOP", "FLAC": "COPYRIGHT", "OggVorbis": "COPYRIGHT", "MP4": "©cpy", "ASF": "Copyright"},
    "source_url": {"MP3": "WOAS", "FLAC": "SOURCE", "OggVorbis": "SOURCE", "MP4": "-", "ASF": "-"},
    "user_url": {"MP3": "WXXX", "FLAC": "CONTACT", "OggVorbis": "CONTACT", "MP4": "-", "ASF": "-"},
    "bpm": {"MP3": "TBPM", "FLAC": "BPM", "OggVorbis": "BPM", "MP4": "tmpo", "ASF": "-"},
    "isrc": {"MP3": "TSRC", "FLAC": "ISRC", "OggVorbis": "ISRC", "MP4": "----:com.apple.iTunes:ISRC", "ASF": "ISRC"},
    "media_type": {"MP3": "TMED", "FLAC": "MEDIA", "OggVorbis": "MEDIA", "MP4": "-", "ASF": "-"},
    "encoded_by": {"MP3": "TENC", "FLAC": "ENCODEDBY", "OggVorbis": "ENCODEDBY", "MP4": "©enc", "ASF": "-"},
    "encoder_settings": {"MP3": "TSSE", "FLAC": "ENCODERSETTINGS", "OggVorbis": "ENCODERSETTINGS", "MP4": "-",
                         "ASF": "-"}
}


def get_format_key(format_str):
    """
    Determines the internal format key based on the provided format string.
    """
    if any(x in format_str.upper() for x in ["MP3", "WAVE", "WAV", "AAC"]): return "MP3"
    if "FLAC" in format_str.upper(): return "FLAC"
    if any(x in format_str.upper() for x in ["VORBIS", "OGG"]): return "OggVorbis"
    if "MP4" in format_str.upper(): return "MP4"
    if any(x in format_str.upper() for x in ["ASF", "WMA"]): return "ASF"
    return "MP3"


def get_tag_tooltip(field_key, format_str):
    """
    Generates a formatted tooltip displaying the underlying metadata tag code for a given field and format.
    """
    fmt_key = get_format_key(format_str)
    code = TAG_DEFINITIONS.get(field_key, {}).get(fmt_key, translate("Unknown"))
    return f"{translate('Target Tag')}: {code}"


def fetch_itunes_album_tracks(collection_id):
    """
    Fetches the track list for a specific album from the Apple Music API using its collection ID.

    Args:
        collection_id (int or str): The iTunes collection ID for the album.

    Returns:
        list: A sorted list of track dictionaries containing metadata, or an empty list if the request fails.
    """
    try:
        url = "https://itunes.apple.com/lookup"
        params = {"id": collection_id, "entity": "song", "limit": 200}
        response = requests.get(url, params = params, timeout = 10)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        tracks = []
        for item in results:
            if item.get("wrapperType") == "track":
                tracks.append({
                    "track_number": item.get("trackNumber"),
                    "title": item.get("trackName"),
                    "artist": item.get("artistName"),
                    "album": item.get("collectionName"),
                    "year": item.get("releaseDate", "")[:4],
                    "genre": item.get("primaryGenreName"),
                    "duration": item.get("trackTimeMillis", 0) / 1000,
                    "_raw": item,
                })
        tracks.sort(key = lambda x: (x.get("_raw", {}).get("discNumber", 1), x.get("track_number", 0)))
        return tracks
    except Exception as e:
        print(f"Error fetching album tracks: {e}")
        return []


class UniversalMetadataEditorDialog(StyledDialog):
    """
    Main dialog acting as an orchestrator.
    It determines the mode and delegates UI and logic to specialized editor widgets.
    """
    save_requested = pyqtSignal(dict, bool)

    def __init__(self, tracks, main_window):
        """
        Initializes the universal metadata editor dialog, resolving the correct editor mode based on the selection.
        """
        super().__init__(main_window)
        self.setMinimumWidth(1024)
        self.mw = main_window
        self.tracks = tracks

        self.editor_widget = self._resolve_editor_mode()

        self.setupUi()

    def _is_mixed_mode(self):
        """
        Checks if the selected tracks belong to different albums or album artists.

        Returns:
            bool: True if the tracks are from mixed albums, False if they belong to the same album.
        """
        if len(self.tracks) <= 1:
            return False
        first_t = self.tracks[0]
        base_album = first_t.get("album", "")
        base_album_artist = first_t.get("album_artist", "")
        for t in self.tracks[1:]:
            if t.get("album", "") != base_album or t.get("album_artist", "") != base_album_artist:
                return True
        return False

    def _resolve_editor_mode(self):
        """
        Factory method to select and instantiate the appropriate editor widget class based on the track selection.
        """
        if len(self.tracks) == 1:
            return SingleTrackEditor(self.tracks, self.mw, parent = self)
        elif self._is_mixed_mode():
            return MixedBatchEditor(self.tracks, self.mw, parent = self)
        else:
            return AlbumBatchEditor(self.tracks, self.mw, parent = self)

    def setupUi(self):
        """
        Constructs the main dialog layout, header, bottom control panel, and the stacked widget for managing views.
        """
        self.setWindowTitle(translate("Edit Metadata"))
        self.setProperty("class", "backgroundPrimary")
        self.resize(1200, 720)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        self.editor_page = QWidget()
        editor_layout = QVBoxLayout(self.editor_page)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        top_panel = QWidget()
        top_panel.setContentsMargins(24, 24, 24, 24)
        top_panel.setProperty("class", "headerBackground headerBorder")

        top_layout = QHBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(24)

        title_block = QVBoxLayout()
        title_block.setSpacing(8)

        if len(self.tracks) == 1:
            header_title = translate("Edit Track Metadata")
        elif self._is_mixed_mode():
            header_title = translate("Edit Multiple Files Metadata")
        else:
            header_title = translate("Edit Album Metadata")

        info_label = QLabel(header_title)
        info_label.setProperty("class", "textHeaderPrimary textColorPrimary")

        desc_label = QLabel(translate("Edit metadata description text..."))
        desc_label.setWordWrap(True)
        desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc_label.setProperty("class", "textSecondary textColorPrimary")

        title_block.addWidget(info_label)
        title_block.addWidget(desc_label, 1)

        self.search_btn = QPushButton(translate("Search on Apple Music"))
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setProperty("class", "btnText")
        self.search_btn.setIcon(
            QIcon(create_svg_icon("assets/control/search_album.svg", theme.COLORS["PRIMARY"], QSize(20, 20))))
        set_custom_tooltip(
            self.search_btn,
            title = translate("Search on Apple Music"),
            text = translate(
                "If a match for the artist and album is found on Apple Music, you can auto-fill metadata for the entire album or individual tracks."),
            activity_type = "network_activity"
        )
        self.search_btn.setIconSize(QSize(20, 20))
        self.search_btn.clicked.connect(self.open_search_dialog)

        top_layout.addLayout(title_block, 1)
        top_layout.addWidget(self.search_btn)

        editor_layout.addWidget(top_panel)

        self.content_widget = QWidget()
        self.content_widget.setProperty("class", "backgroundPrimary")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.editor_widget)

        editor_layout.addWidget(self.content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")

        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 24, 24, 24)
        bottom_layout.setSpacing(16)

        self.status_label = QLabel("")
        self.status_label.setProperty("class", "textSecondary")

        self.btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.btn_save = self.btn_box.button(QDialogButtonBox.StandardButton.Save)
        self.btn_save.setEnabled(False)

        if self.btn_box.layout():
            self.btn_box.layout().setSpacing(16)

        for btn in self.btn_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_box.accepted.connect(self.initiate_save)
        self.btn_box.rejected.connect(self.reject)

        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_box)

        editor_layout.addWidget(bottom_panel)
        self.stack.addWidget(self.editor_page)

        if hasattr(self.editor_widget, 'dataChanged'):
            self.editor_widget.dataChanged.connect(self._update_save_button_state)
            self._update_save_button_state()

        if hasattr(self.editor_widget, 'statusMessage'):
            self.editor_widget.statusMessage.connect(self.status_label.setText)

        self.confirmation_widget = self._create_confirmation_widget()
        self.stack.addWidget(self.confirmation_widget)

        self.loading_page = self._create_loading_widget()
        self.stack.addWidget(self.loading_page)

    def _update_save_button_state(self):
        """
        Enables or disables the save button depending on whether there are pending modifications in the editor.
        """
        if hasattr(self.editor_widget, 'has_modifications'):
            self.btn_save.setEnabled(self.editor_widget.has_modifications())
        else:
            self.btn_save.setEnabled(True)

    def open_search_dialog(self):
        """
        Search orchestrator. Requests query data from the active editor, opens the Apple Music search dialog,
        and passes the results back to the editor.
        """
        artist, album = self.editor_widget.get_search_queries()

        dialog = MetadataSearchDialog(artist, album, self)
        if dialog.exec():
            result = dialog.get_result()
            raw_data = dialog.selected_data

            if "artwork_url" in result:
                self._download_cover(result["artwork_url"])

            fetched_tracks = []
            if raw_data:
                collection_id = raw_data.get("collectionId")
                self.status_label.setText(translate("Fetching tracks from Apple Music..."))
                QApplication.processEvents()
                fetched_tracks = fetch_itunes_album_tracks(collection_id)
                self.status_label.setText(translate("Data loaded from Apple Music"))

            self.editor_widget.apply_search_results(result, raw_data, fetched_tracks)

    def _download_cover(self, url):
        """
        Downloads a cover image from the provided URL, saves it to a temporary file,
        and passes the local file path to the active editor.
        """
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            response = requests.get(url, timeout = 10)
            response.raise_for_status()
            tf = tempfile.NamedTemporaryFile(delete = False, suffix = ".jpg")
            tf.write(response.content)
            tf.close()
            if hasattr(self.editor_widget, "apply_new_cover"):
                self.editor_widget.apply_new_cover(tf.name)
        except Exception as e:
            print(f"Cover download failed: {e}")
            self.status_label.setText(translate("Cover download failed"))
        finally:
            QApplication.restoreOverrideCursor()

    def initiate_save(self):
        """
        Initiates the save process by requesting a diff summary from the editor
        and displaying the confirmation view.
        """
        diff_summary = self.editor_widget.get_diff_summary()

        if not diff_summary:
            super().accept()
            return

        self._populate_confirmation_view(diff_summary)
        self.stack.setCurrentIndex(1)

    def _create_confirmation_widget(self):
        """
        Builds the UI widget for reviewing pending metadata changes before saving.
        """
        widget = QWidget()
        widget.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_panel = QWidget()
        top_panel.setContentsMargins(24, 24, 24, 24)
        top_panel.setProperty("class", "headerBackground headerBorder")
        top_layout = QHBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(24)
        title_block = QVBoxLayout()
        title_block.setSpacing(8)
        info_label = QLabel(translate("Check Changes"))
        info_label.setProperty("class", "textHeaderPrimary textColorPrimary")
        desc_label = QLabel(translate("New data will be written to local files after confirmation."))
        desc_label.setWordWrap(True)
        desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        desc_label.setProperty("class", "textSecondary textColorPrimary")
        title_block.addWidget(info_label)
        title_block.addWidget(desc_label, 1)
        top_layout.addLayout(title_block)
        layout.addWidget(top_panel)

        table_layout = QVBoxLayout(widget)
        table_layout.setContentsMargins(24, 24, 24, 24)
        table_layout.setSpacing(0)
        self.diff_table = QTableWidget()
        self.diff_table.setColumnCount(4)
        self.diff_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.diff_table.setHorizontalHeaderLabels([
            translate("File"), translate("Tag"), translate("Old Value"), translate("New Value")
        ])
        self.diff_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.diff_table)
        layout.addLayout(table_layout, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 24, 24, 24)
        bottom_layout.setSpacing(16)

        self.fast_save_chk = QCheckBox(translate("Fast save without library update"))
        self.fast_save_chk.setMinimumHeight(18)
        self.fast_save_chk.setProperty("class", "textColorPrimary")
        self.fast_save_chk.setChecked(False)
        set_custom_tooltip(
            self.fast_save_chk,
            title = translate("Fast Save"),
            text = translate(
                "Changes will be saved to files, but the library view will not update until you manually refresh it.")
        )

        if hasattr(self.editor_widget, 'supports_fast_save') and self.editor_widget.supports_fast_save:
            bottom_layout.addWidget(self.fast_save_chk)
        else:
            self.fast_save_chk.setVisible(False)

        btn_box = QDialogButtonBox()
        btn_apply = btn_box.addButton(translate("Confirm"), QDialogButtonBox.ButtonRole.AcceptRole)
        btn_back = btn_box.addButton(translate("Back"), QDialogButtonBox.ButtonRole.RejectRole)

        for btn in btn_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_box.accepted.connect(self._perform_save)
        btn_box.rejected.connect(lambda: self.stack.setCurrentIndex(0))

        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_box)
        layout.addWidget(bottom_panel)
        return widget

    def _populate_confirmation_view(self, diff_data):
        """
        Fills the confirmation table with the calculated metadata differences.
        """
        self.diff_table.setRowCount(len(diff_data))
        for i, (fname, tag, old, new) in enumerate(diff_data):
            self.diff_table.setItem(i, 0, QTableWidgetItem(fname))
            self.diff_table.setItem(i, 1, QTableWidgetItem(tag))
            self.diff_table.setItem(i, 2, QTableWidgetItem(old))
            new_item = QTableWidgetItem(new)
            new_item.setForeground(QColor(theme.COLORS["ACCENT"]))
            self.diff_table.setItem(i, 3, new_item)

    def _perform_save(self):
        """
        Finalizes the save operation, switches to the loading screen, and emits the save_requested signal.
        """
        self.stack.setCurrentIndex(2)
        QApplication.processEvents()
        is_fast = self.fast_save_chk.isChecked()
        final_data_map = self.editor_widget.get_data()
        self.save_requested.emit(final_data_map, is_fast)

    def _create_loading_widget(self):
        """
        Builds the loading screen widget displayed while changes are being written to files and the library.
        """
        widget = QWidget()
        widget.setProperty("class", "backgroundPrimary")
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        label = QLabel(translate("Updating library..."))
        label.setProperty("class", "textHeaderPrimary textColorPrimary")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label = QLabel(translate("Please wait while changes are being applied."))
        sub_label.setProperty("class", "textSecondary textColorPrimary")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addWidget(sub_label)
        return widget

    def force_close(self):
        """
        Forcefully accepts and closes the dialog.
        """
        self.done(QDialog.DialogCode.Accepted)


class MetadataSearchDialog(StyledDialog):
    """
    Sub-dialog allowing the user to search metadata and album information
    via the Apple Music API dynamically.
    """

    def __init__(self, artist_query, album_query, parent = None):
        """
        Initializes the metadata search dialog with initial queries for the artist and album.
        """
        super().__init__(parent)
        self.setWindowTitle(translate("Search Metadata on Apple Music"))
        self.setMinimumSize(720, 512)
        self.setProperty("class", "backgroundPrimary")

        self.selected_data = None
        self.artist_query = artist_query or ""
        self.album_query = album_query or ""

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        search_label = QLabel()
        search_label.setText(translate("Search query (e.g. Artist Album title)"))
        search_label.setProperty("class", "textTertiary textColorTertiary")
        layout.addWidget(search_label)

        search_row = QHBoxLayout()
        search_row.setSpacing(0)

        initial_query = f"{self.artist_query} {self.album_query}".strip()
        self.query_input = StyledLineEdit(initial_query)
        self.query_input.setPlaceholderText(translate("Artist Album title"))
        self.query_input.setProperty("class", "inputBorderMultiLeft inputBorderPaddingTextEdit")
        self.query_input.returnPressed.connect(self.perform_search)

        search_btn = QPushButton(translate("Search"))
        search_btn.setProperty("class", "btnText inputBorderMultiRight inputBorderPaddingButton")
        search_btn.setFixedHeight(36)
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self.perform_search)

        search_row.addWidget(self.query_input, 1)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)
        layout.addSpacing(8)

        results_label = QLabel()
        results_label.setText(translate("Search Results"))
        results_label.setProperty("class", "textTertiary textColorTertiary")
        layout.addWidget(results_label)

        self.results_list = StyledListWidget()
        self.results_list.setProperty("class", "listWidget")
        self.results_list.setIconSize(QSize(64, 64))
        self.results_list.setSpacing(4)
        layout.addWidget(self.results_list)

        main_layout.addWidget(content_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        for btn in self.button_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if self.button_box.layout():
            self.button_box.layout().setSpacing(16)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.button_box)
        main_layout.addWidget(bottom_panel)

        if initial_query:
            self.results_list.addItem(translate("Searching Apple Music..."))
            QTimer.singleShot(100, self.perform_search)

    def perform_search(self):
        """
        Executes a search query against the Apple Music API and populates the results list with matching albums.
        """
        self.results_list.clear()
        query = self.query_input.text().strip()
        if not query:
            return
        self.results_list.addItem(translate("Searching Apple Music..."))
        QApplication.processEvents()
        try:
            url = "https://itunes.apple.com/search"
            params = {"term": query, "media": "music", "entity": "album", "limit": 20}
            response = requests.get(url, params = params, timeout = 10)
            response.raise_for_status()
            data = response.json()
            self.results_list.clear()
            results = data.get("results", [])
            if not results:
                self.results_list.addItem(translate("Nothing found."))
                return
            for item in results:
                artist = item.get("artistName", "Unknown")
                album = item.get("collectionName", "Unknown")
                year = item.get("releaseDate", "????")[:4]
                genre = item.get("primaryGenreName", "")
                count = item.get("trackCount", 0)
                track_str = translate("{count} tracks", count = count)
                display_text = f"{artist} - {album}\n{year} • {genre} • {track_str}"
                list_item = QListWidgetItem(display_text)
                list_item.setData(Qt.ItemDataRole.UserRole, item)
                artwork_url = item.get("artworkUrl100")
                if artwork_url:
                    try:
                        img_resp = requests.get(artwork_url, timeout = 2)
                        if img_resp.status_code == 200:
                            pixmap = QPixmap()
                            pixmap.loadFromData(img_resp.content)
                            list_item.setIcon(QIcon(pixmap))
                    except Exception:
                        pass
                self.results_list.addItem(list_item)
        except Exception as e:
            self.results_list.clear()
            self.results_list.addItem(f"Error: {str(e)}")

    def accept(self):
        """
        Handles the acceptance of the dialog, storing the selected search result data.
        """
        current_item = self.results_list.currentItem()
        if current_item:
            data = current_item.data(Qt.ItemDataRole.UserRole)
            if data:
                self.selected_data = data
                super().accept()

    def get_result(self):
        """
        Extracts and formats the necessary metadata from the selected Apple Music search result,
        including generating a high-resolution artwork URL.

        Returns:
            dict or None: The formatted metadata dictionary, or None if no valid data was selected.
        """
        if not hasattr(self, "selected_data") or not self.selected_data:
            return None
        raw = self.selected_data
        data = {
            "artist": raw.get("artistName"),
            "album_artist": raw.get("artistName"),
            "album": raw.get("collectionName"),
            "genre": raw.get("primaryGenreName")
        }
        release_date = raw.get("releaseDate", "")
        data["year"] = release_date[:4] if release_date else ""
        data["track_count"] = raw.get("trackCount")
        if "artworkUrl100" in raw:
            original_url = raw["artworkUrl100"]
            hd_url = original_url.replace("100x100bb", "1000x1000bb")
            data["artwork_url"] = hd_url
        return data