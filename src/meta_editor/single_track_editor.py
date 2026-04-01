"""
Vinyller — Single track editor widget
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

import difflib
import os

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QFileDialog, QApplication
)

from src.meta_editor.editor_components import LyricsTextEdit, AdvancedMetadataWidget, apply_field_tooltip
from src.ui.custom_base_widgets import (
    StyledScrollArea, TranslucentCombo, set_custom_tooltip
)
from src.ui.custom_classes import GapCompleter, MetadataMergeControl, RoundedCoverLabel
from src.ui.search_services_tools import SearchToolButton
from src.utils import theme
from src.utils.utils import create_svg_icon, fetch_lyrics_from_lrclib, resource_path
from src.utils.utils_translator import translate


class SingleTrackEditor(QWidget):
    """
    Editor widget specifically designed for modifying metadata of a single audio file.
    Implements the standard interface required by UniversalMetadataEditorDialog.
    """
    supports_fast_save = True
    dataChanged = pyqtSignal()
    statusMessage = pyqtSignal(str)

    def __init__(self, tracks, main_window, parent = None):
        """
        Initializes the SingleTrackEditor.

        Args:
            tracks (list): A list containing a single track data dictionary.
            main_window (QMainWindow): Reference to the main application window.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.mw = main_window
        self.track = tracks[0]
        self.extended_data = self.mw.library_manager.get_extended_track_info(self.track["path"])

        self.all_artists = sorted(list(self.mw.data_manager.artists_data.keys()))
        self.all_genres = sorted(list(self.mw.data_manager.genres_data.keys()))
        self.all_albums = sorted(set(k[1] for k in self.mw.data_manager.albums_data.keys()))

        self.new_cover_path = None
        self.cached_new_cover_path = None
        self.fetched_tracks = []
        self.inputs = {}
        self.basic_labels = {}

        default_missing = "assets/view/missing_cover.png"
        missing_path = theme.COLORS.get("MISSING_COVER", default_missing)
        try:
            self.missing_cover_pixmap = QIcon(resource_path(missing_path)).pixmap(256, 256)
        except Exception:
            self.missing_cover_pixmap = QPixmap(256, 256)
            self.missing_cover_pixmap.fill(Qt.GlobalColor.gray)

        self.setupUi()
        self.load_data()

    def setupUi(self):
        """
        Builds the 3-column layout specific to single track editing, including cover art, basic tags, and advanced/lyrics tabs.
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        single_scroll = StyledScrollArea()
        single_scroll.setWidgetResizable(True)
        single_scroll.setFrameShape(StyledScrollArea.Shape.NoFrame)
        single_scroll.setProperty("class", "backgroundTransparent borderRight")
        single_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        single_page = QWidget()
        single_page.setProperty("class", "backgroundPrimary")
        single_page_layout = QHBoxLayout(single_page)
        single_page_layout.setContentsMargins(0, 0, 0, 0)
        single_page_layout.setSpacing(0)
        single_scroll.setWidget(single_page)

        column_left = QWidget()
        column_left.setContentsMargins(24, 24, 24, 24)
        left_column = QVBoxLayout(column_left)
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        left_column.setSpacing(8)

        cover_select_label = QLabel(translate("Artwork & File Path"))
        cover_select_label.setProperty("class", "textTertiary textColorTertiary")
        left_column.addWidget(cover_select_label)

        self.cover_label = RoundedCoverLabel(self.missing_cover_pixmap, 8)
        self.cover_label.setFixedSize(256, 256)

        cover_btns_layout = QHBoxLayout()
        cover_btns_layout.setContentsMargins(0, 0, 0, 0)
        cover_btns_layout.setSpacing(0)

        change_cover_btn = QPushButton(translate("Change..."))
        change_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_cover_btn.setProperty("class", "btnText inputBorderMultiLeft")
        change_cover_btn.clicked.connect(self._change_cover_manual)

        self.reset_cover_btn = QPushButton()
        self.reset_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_cover_btn.setProperty("class", "inputBorderMultiMiddle")
        self.reset_cover_btn.setIcon(
            QIcon(create_svg_icon("assets/control/undo.svg", theme.COLORS["PRIMARY"], QSize(20, 20))))
        self.reset_cover_btn.setIconSize(QSize(20, 20))
        self.reset_cover_btn.clicked.connect(self._reset_cover)
        self.reset_cover_btn.setEnabled(False)
        set_custom_tooltip(self.reset_cover_btn, title = translate("Reset to original cover"))

        self.redo_cover_btn = QPushButton()
        self.redo_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redo_cover_btn.setProperty("class", "inputBorderMultiRight")
        self.redo_cover_btn.setIcon(
            QIcon(create_svg_icon("assets/control/redo.svg", theme.COLORS["PRIMARY"], QSize(20, 20))))
        self.redo_cover_btn.setIconSize(QSize(20, 20))
        self.redo_cover_btn.clicked.connect(self._restore_new_cover)
        self.redo_cover_btn.setEnabled(False)
        set_custom_tooltip(self.redo_cover_btn, title = translate("Restore new cover"))

        cover_btns_layout.addWidget(change_cover_btn, 1)
        cover_btns_layout.addWidget(self.reset_cover_btn)
        cover_btns_layout.addWidget(self.redo_cover_btn)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)
        path_title = QLabel(translate("File Path:"))
        path_title.setWordWrap(True)
        path_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        path_title.setProperty("class", "textTertiary textColorTertiary")
        self.lbl_path = QLabel()
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.lbl_path.setProperty("class", "textSecondary textColorPrimary")
        info_layout.addWidget(path_title)
        info_layout.addSpacing(8)
        info_layout.addWidget(self.lbl_path)

        left_column.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)
        left_column.addSpacing(8)
        left_column.addLayout(cover_btns_layout)
        left_column.addSpacing(16)
        left_column.addLayout(info_layout)
        left_column.addStretch()

        tags_widget = QWidget()
        tags_widget.setContentsMargins(0, 24, 24, 24)
        tags_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tags_widget.setProperty("class", "borderRight")
        col_tags = QVBoxLayout(tags_widget)
        col_tags.setContentsMargins(0, 0, 0, 0)
        col_tags.setAlignment(Qt.AlignmentFlag.AlignTop)
        col_tags.setSpacing(16)

        self.single_match_container = QWidget()
        match_layout = QVBoxLayout(self.single_match_container)
        match_layout.setSpacing(8)
        match_layout.setContentsMargins(0, 0, 0, 0)

        match_label = QLabel(translate("Apple Music Match"))
        match_label.setProperty("class", "textTertiary textColorTertiary")
        self.match_combo = TranslucentCombo()
        self.match_combo.setProperty("class", "inputBorderSinglePadding")
        self.match_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.match_combo.addItem(translate("No Match"), None)
        self.match_combo.currentIndexChanged.connect(self._on_single_match_selected)

        match_layout.addWidget(match_label)
        match_layout.addWidget(self.match_combo)
        col_tags.addWidget(self.single_match_container)
        self.single_match_container.setVisible(False)

        def create_number_field(key, label_text, style):
            container = QWidget()
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setProperty("class", "textTertiary textColorTertiary")
            self.basic_labels[key] = lbl
            inp = MetadataMergeControl("", border_style = style)
            v_layout.addWidget(lbl)
            v_layout.addWidget(inp)
            self.inputs[key] = inp
            return container

        numbers_container = QWidget()
        numbers_hbox = QHBoxLayout(numbers_container)
        numbers_hbox.setContentsMargins(0, 0, 0, 0)
        numbers_hbox.setSpacing(0)
        numbers_hbox.addWidget(
            create_number_field("Disc Number", translate("Disc #"), "inputBorderMultiLeft inputBorderPaddingTextEdit"))
        numbers_hbox.addWidget(create_number_field("Track Number", translate("Track #"),
                                                   "inputBorderMultiRight inputBorderPaddingTextEdit"))
        col_tags.addWidget(numbers_container)

        fields = [
            ("Title", translate("Title"), None),
            ("Artist", translate("Artist"), self.all_artists),
            ("Album", translate("Album"), self.all_albums),
            ("Album Artist", translate("Album Artist"), self.all_artists),
            ("Composer", translate("Composer"), self.all_artists),
            ("Genre", translate("Genre"), self.all_genres),
            ("Year", translate("Year"), None),
        ]

        for key, label_text, suggestions in fields:
            field_layout = QVBoxLayout()
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setProperty("class", "textTertiary textColorTertiary")
            self.basic_labels[key] = lbl
            inp = MetadataMergeControl("", border_style = "inputBorderSinglePadding")
            inp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            if suggestions:
                completer = GapCompleter(suggestions, inp, gap = 4)
                popup = completer.popup()
                popup.setProperty("class", "listWidget")
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                if inp.lineEdit():
                    inp.lineEdit().setCompleter(completer)

            self.inputs[key] = inp
            field_layout.addWidget(lbl)
            field_layout.addWidget(inp)
            col_tags.addLayout(field_layout)

        lyrics_widget = QWidget()
        lyrics_widget.setContentsMargins(0, 0, 0, 0)
        col_lyrics = QVBoxLayout(lyrics_widget)
        col_lyrics.setContentsMargins(0, 0, 0, 0)
        col_lyrics.setSpacing(8)

        lyrics_lbl = QLabel(translate("Lyrics"))
        lyrics_lbl.setProperty("class", "textTertiary textColorTertiary")
        lyrics_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
        lyrics_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.basic_labels["Lyrics"] = lyrics_lbl

        btn_container = QWidget()
        btn_lyrics_layout = QHBoxLayout(btn_container)
        btn_lyrics_layout.setContentsMargins(0, 0, 0, 0)
        btn_lyrics_layout.setSpacing(8)

        self.btn_search_lyrics = SearchToolButton(self.mw)
        self.btn_search_lyrics.set_lyrics_mode(True)
        self.btn_search_lyrics.set_data_getter(
            lambda: (self.inputs["Artist"].get_final_value(), self.inputs["Title"].get_final_value()))
        btn_lyrics_layout.addWidget(self.btn_search_lyrics)

        self.btn_dl_lyrics = QPushButton(translate("Download from LRCLIB"))
        self.btn_dl_lyrics.setProperty("class", "btnText")
        set_custom_tooltip(
            self.btn_dl_lyrics,
            title = translate("Download lyrics from LRCLIB"),
            text = translate(
                "If matching lyrics are found on LRCLIB, they will be auto-filled into the field after a successful download"),
            activity_type = "network_activity"
        )
        self.btn_dl_lyrics.clicked.connect(self._download_lyrics)
        btn_lyrics_layout.addWidget(self.btn_dl_lyrics)

        self.lyrics_edit = LyricsTextEdit()
        self.lyrics_edit.setPlaceholderText(translate("Enter song lyrics..."))
        self.lyrics_edit.setProperty("class", "lyricsEditor")

        col_lyrics.addWidget(lyrics_lbl, 0, Qt.AlignmentFlag.AlignTop)
        col_lyrics.addWidget(btn_container, 0, Qt.AlignmentFlag.AlignTop)
        col_lyrics.addWidget(self.lyrics_edit, 1, Qt.AlignmentFlag.AlignTop)
        col_tags.addWidget(lyrics_widget)

        right_tabs_container = QWidget()
        right_tabs_container.setContentsMargins(24, 24, 24, 24)
        right_tabs_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        right_tabs_layout = QVBoxLayout(right_tabs_container)
        right_tabs_layout.setContentsMargins(0, 0, 0, 0)
        right_tabs_layout.setSpacing(0)

        adv_lbl = QLabel(translate("Advanced Tags"))
        adv_lbl.setProperty("class", "textHeaderSecondary textColorPrimary")
        right_tabs_layout.addWidget(adv_lbl)

        self.advanced_widget = AdvancedMetadataWidget(self)
        right_tabs_layout.addWidget(self.advanced_widget)

        single_page_layout.addWidget(column_left, 0)
        single_page_layout.addWidget(tags_widget, 3)
        single_page_layout.addWidget(right_tabs_container, 2)

        layout.addWidget(single_scroll)

        self.advanced_widget.dataChanged.connect(self.dataChanged.emit)
        self.lyrics_edit.textChanged.connect(self.dataChanged.emit)

        for inp in self.inputs.values():
            inp.currentIndexChanged.connect(self.dataChanged.emit)
            if inp.lineEdit():
                inp.lineEdit().textChanged.connect(self.dataChanged.emit)

    def load_data(self):
        """
        Populates the UI inputs and read-only fields with the track's existing metadata and cover art.
        """
        pixmap = QPixmap()
        artwork_data = self.track.get("artwork")
        if artwork_data:
            if isinstance(artwork_data, dict):
                avail = sorted([int(s) for s in artwork_data.keys()])
                path = artwork_data.get(str(avail[-1])) if avail else None
            else:
                path = artwork_data
            if path and os.path.exists(path):
                pixmap = QPixmap(path)

        if pixmap.isNull():
            pixmap = self.missing_cover_pixmap

        self.original_cover_pixmap = pixmap.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
        self.cover_label.setPixmap(self.original_cover_pixmap)

        self.advanced_widget.load_data(self.extended_data)
        fmt = self.extended_data.get("format", "MP3")
        for key, lbl in self.basic_labels.items():
            apply_field_tooltip(lbl, key, fmt)
            lbl.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.inputs["Title"].update_current_value(self.track.get("title", ""))

        artists = self.track.get("artists", [])
        if not artists and self.track.get("artist"): artists = [self.track.get("artist")]
        artist_str = "; ".join([x for x in artists if x]) if isinstance(artists, list) else str(artists)
        self.inputs["Artist"].update_current_value(artist_str)

        self.inputs["Album"].update_current_value(self.track.get("album", ""))
        self.inputs["Album Artist"].update_current_value(self.track.get("album_artist", ""))
        self.inputs["Composer"].update_current_value(self.track.get("composer", ""))

        g = self.track.get("genre", [])
        genre_str = "; ".join([x for x in g if x]) if isinstance(g, list) else str(g)
        self.inputs["Genre"].update_current_value(genre_str)

        self.inputs["Year"].update_current_value(str(self.track.get("year", "")))
        self.inputs["Track Number"].update_current_value(str(self.track.get("tracknumber", "")))
        self.inputs["Disc Number"].update_current_value(str(self.track.get("discnumber", "")))

        self.lyrics_edit.setText(self.track.get("lyrics", ""))
        self.lbl_path.setText(self.track["path"])

    def get_data(self):
        """
        Compiles the finalized metadata and cover art changes into a dictionary formatted for the orchestrator.

        Returns:
            dict: A dictionary mapping the track's path to its new metadata tags.
        """
        tags = {
            "title": self.inputs["Title"].get_final_value(),
            "artist": self.inputs["Artist"].get_final_value(),
            "composer": self.inputs["Composer"].get_final_value(),
            "album": self.inputs["Album"].get_final_value(),
            "albumartist": self.inputs["Album Artist"].get_final_value(),
            "genre": self.inputs["Genre"].get_final_value(),
            "date": self.inputs["Year"].get_final_value(),
            "tracknumber": self.inputs["Track Number"].get_final_value(),
            "discnumber": self.inputs["Disc Number"].get_final_value(),
            "lyrics": self.lyrics_edit.toPlainText(),
        }
        if self.new_cover_path:
            tags["artwork_path"] = self.new_cover_path

        tags.update(self.advanced_widget.get_data())

        return {self.track["path"]: tags}

    def get_diff_summary(self):
        """
        Generates a detailed summary of all modifications made to the track's metadata for the confirmation view.

        Returns:
            list: A list of tuples containing (filename, tag name, old value, new value).
        """
        diff_summary = []
        new_tags = self.get_data().get(self.track["path"], {})

        display_names = {
            "title": translate("Title"), "artist": translate("Artist"),
            "album": translate("Album"), "albumartist": translate("Album Artist"),
            "composer": translate("Composer"), "genre": translate("Genre"),
            "date": translate("Year"), "tracknumber": translate("Track #"),
            "discnumber": translate("Disc #"), "lyrics": translate("Lyrics"),
            "artwork_path": translate("Cover Art"),
            "original_year": translate("Original Release Year"),
            "comment": translate("Comment"), "copyright": translate("Copyright"),
            "source_url": translate("Source URL"), "user_url": translate("User URL"),
            "bpm": translate("BPM"), "isrc": translate("ISRC"),
            "media_type": translate("Media Type"), "encoded_by": translate("Encoded By"),
            "encoder_settings": translate("Encoder Settings")
        }

        advanced_keys = {
            "original_year", "comment", "copyright", "source_url", "user_url",
            "bpm", "isrc", "media_type", "encoded_by", "encoder_settings"
        }

        filename = os.path.basename(self.track["path"])

        for key, new_val in new_tags.items():
            if key == "artwork_path":
                diff_summary.append(
                    (filename, display_names["artwork_path"], translate("Current"), translate("New Image")))
                continue

            old_val = ""
            if key in advanced_keys:
                old_val = self.extended_data.get(key, "")
            else:
                if key == "genre":
                    g = self.track.get("genre", [])
                    old_val = "; ".join([x for x in g if x]) if isinstance(g, list) else str(g) if g else ""
                elif key == "artist":
                    a = self.track.get("artists", [])
                    if not a and self.track.get("artist"): a = [self.track.get("artist")]
                    old_val = "; ".join([x for x in a if x]) if isinstance(a, list) else str(a) if a else ""
                elif key == "date":
                    old_val = self.track.get("year", "")
                elif key == "albumartist":
                    old_val = self.track.get("album_artist", "")
                else:
                    old_val = self.track.get(key, "")

            s_old = str(old_val).strip() if old_val is not None else ""
            s_new = str(new_val).strip() if new_val is not None else ""

            if s_old != s_new:
                if key == "lyrics":
                    disp_old = (s_old[:20] + "...") if len(s_old) > 20 else s_old
                    disp_new = (s_new[:20] + "...") if len(s_new) > 20 else s_new
                else:
                    disp_old, disp_new = s_old, s_new

                diff_summary.append((filename, display_names.get(key, key), disp_old, disp_new))

        return diff_summary

    def get_search_queries(self):
        """
        Returns the search parameters (artist, album) based on the current inputs for Apple Music querying.
        """
        return (
            self.inputs["Artist"].get_final_value(),
            self.inputs["Album"].get_final_value()
        )

    def apply_search_results(self, result, raw_data, fetched_tracks):
        """
        Processes the fetched Apple Music search response, populates the match dropdown, and attempts auto-mapping.
        """
        self.fetched_tracks = fetched_tracks
        if fetched_tracks:
            self.single_match_container.setVisible(True)
            self._update_single_match_options()
            self._auto_map_single_track()

    def apply_new_cover(self, path):
        """
        Applies a newly downloaded or selected cover art path to the UI and marks it as modified.
        """
        self.new_cover_path = path
        self.cached_new_cover_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.cover_label.setPixmap(
                pixmap.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self._update_cover_buttons()
        self.dataChanged.emit()

    def _change_cover_manual(self):
        """
        Opens a file dialog allowing the user to manually select a new cover image for the track.
        """
        initial_dir = os.path.dirname(self.track["path"])
        file_path, _ = QFileDialog.getOpenFileName(
            self, translate("Select New Cover"), initial_dir, translate("Image Files (*.png *.jpg *.jpeg)")
        )
        if file_path:
            self.apply_new_cover(file_path)

    def _update_cover_buttons(self):
        """
        Updates the enabled/disabled state of the undo and redo buttons for cover art modifications.
        """
        self.reset_cover_btn.setEnabled(self.new_cover_path is not None)
        can_redo = (self.new_cover_path is None) and (self.cached_new_cover_path is not None)
        self.redo_cover_btn.setEnabled(can_redo)

    def _reset_cover(self):
        """
        Reverts the cover art back to its original image before any modifications were made.
        """
        self.cover_label.setPixmap(self.original_cover_pixmap)
        self.new_cover_path = None
        self._update_cover_buttons()
        self.dataChanged.emit()

    def _restore_new_cover(self):
        """
        Re-applies the user's newly selected cover image if they previously clicked the reset button.
        """
        if self.cached_new_cover_path and os.path.exists(self.cached_new_cover_path):
            self.apply_new_cover(self.cached_new_cover_path)

    def _download_lyrics(self):
        """
        Fetches lyrics from LRCLIB based on the track's artist and title inputs.
        """
        artist = self.inputs["Artist"].get_final_value()
        title = self.inputs["Title"].get_final_value()
        album = self.inputs["Album"].get_final_value()
        if not artist or not title:
            self.statusMessage.emit(translate("Artist and Title are required to search lyrics"))
            return

        self.btn_dl_lyrics.setEnabled(False)
        self.btn_dl_lyrics.setText(translate("Searching..."))
        self.statusMessage.emit(translate("Searching for lyrics on LRCLIB..."))
        QApplication.processEvents()

        lyrics = fetch_lyrics_from_lrclib(artist, title, album, 0)

        self.btn_dl_lyrics.setEnabled(True)
        self.btn_dl_lyrics.setText(translate("Download from LRCLIB"))

        if lyrics:
            self.lyrics_edit.setText(lyrics)
            self.statusMessage.emit(translate("Lyrics downloaded successfully"))
        else:
            self.statusMessage.emit(translate("Lyrics not found"))

    def _update_single_match_options(self):
        """
        Populates the Apple Music match dropdown with fetched track results.
        """
        current_data = self.match_combo.currentData()
        self.match_combo.blockSignals(True)
        self.match_combo.clear()
        self.match_combo.addItem(translate("No Match"), None)

        for i, ft in enumerate(self.fetched_tracks):
            disc = ft["_raw"].get("discNumber", 1)
            track_n = ft["track_number"]
            display = f"{disc}-{track_n:02d}. {ft['title']}"
            self.match_combo.addItem(display, i)

        if current_data is not None:
            idx = self.match_combo.findData(current_data)
            if idx >= 0:
                self.match_combo.setCurrentIndex(idx)
        self.match_combo.blockSignals(False)

    def _auto_map_single_track(self):
        """
        Attempts to automatically select the best matching Apple Music track based on title similarity and track numbers.
        """
        local_title = self.track.get("title", "")
        filename = os.path.splitext(os.path.basename(self.track.get("path", "")))[0]
        try:
            local_disc = int(str(self.track.get("discnumber", "1")).split("/")[0])
            local_track = int(str(self.track.get("tracknumber", "0")).split("/")[0])
        except:
            local_disc, local_track = 1, 0

        found_idx = -1
        if local_title:
            best_score, best_idx = 0.0, -1
            for i, ft in enumerate(self.fetched_tracks):
                score = difflib.SequenceMatcher(None, str(local_title).lower().strip(),
                                                str(ft["title"]).lower().strip()).ratio()
                if score > best_score: best_score, best_idx = score, i
            if best_score > 0.85: found_idx = best_idx

        if found_idx == -1 and local_track > 0:
            for i, ft in enumerate(self.fetched_tracks):
                if ft["_raw"].get("discNumber", 1) == local_disc and ft["track_number"] == local_track:
                    found_idx = i
                    break

        if found_idx == -1:
            best_score, best_idx = 0.0, -1
            for i, ft in enumerate(self.fetched_tracks):
                score = difflib.SequenceMatcher(None, filename.lower().strip(),
                                                str(ft["title"]).lower().strip()).ratio()
                if score > best_score: best_score, best_idx = score, i
            if best_score > 0.6: found_idx = best_idx

        if found_idx == -1 and self.fetched_tracks:
            found_idx = 0

        if found_idx != -1:
            self.match_combo.setCurrentIndex(found_idx + 1)

    def _on_single_match_selected(self):
        """
        Applies the metadata from the currently selected Apple Music match to the input fields.
        """
        idx = self.match_combo.currentData()
        if idx is not None and 0 <= idx < len(self.fetched_tracks):
            ft = self.fetched_tracks[idx]
            self.inputs["Title"].set_fetched_value(ft["title"])
            self.inputs["Artist"].set_fetched_value(ft["artist"])
            self.inputs["Album"].set_fetched_value(ft["album"])
            self.inputs["Genre"].set_fetched_value(ft.get("genre", ""))
            self.inputs["Year"].set_fetched_value(ft.get("year", ""))
            self.inputs["Track Number"].set_fetched_value(str(ft["track_number"]))
            self.inputs["Disc Number"].set_fetched_value(str(ft["_raw"].get("discNumber", 1)))
            self.inputs["Album Artist"].set_fetched_value(ft["artist"])
        else:
            for inp in self.inputs.values():
                inp.set_fetched_value(None)

    def has_modifications(self):
        """
        Checks if any metadata, lyrics, or cover art have been modified by the user.

        Returns:
            bool: True if there are pending edits, False otherwise.
        """
        if self.new_cover_path is not None: return True
        if self.lyrics_edit.toPlainText() != self.track.get("lyrics", ""): return True
        if self.advanced_widget.has_modifications(): return True

        for inp in self.inputs.values():
            if inp.get_final_value() != inp.current_val: return True

        return False