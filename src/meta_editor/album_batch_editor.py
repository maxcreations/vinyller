"""
Vinyller — Album batch editor widget
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
import html
import os

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QFileDialog, QListWidgetItem, QStackedWidget, QAbstractItemView, QFrame
)

from src.meta_editor.editor_components import (
    FilenameDelegate, BatchTrackDetailWidget, MultiTrackEditWidget, get_original_tag_value,
    apply_field_tooltip
)
from src.ui.custom_base_widgets import (
    StyledScrollArea, StyledListWidget, set_custom_tooltip, TranslucentMenu
)
from src.ui.custom_classes import MetadataMergeControl, RoundedCoverLabel
from src.utils import theme
from src.utils.utils import create_svg_icon, resource_path
from src.utils.utils_translator import translate


class AlbumBatchEditor(QWidget):
    """
    Editor widget for modifying multiple tracks belonging to the same album.
    Implements standard interface for UniversalMetadataEditorDialog.
    """
    supports_fast_save = False
    dataChanged = pyqtSignal()
    statusMessage = pyqtSignal(str)

    def __init__(self, tracks, main_window, parent = None):
        """
        Initializes the AlbumBatchEditor.

        Args:
            tracks (list): A list of track data dictionaries belonging to the album.
            main_window (QMainWindow): Reference to the main application window.
            parent (QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.mw = main_window
        self.tracks = tracks

        self.all_artists = sorted(list(self.mw.data_manager.artists_data.keys()))
        self.all_genres = sorted(list(self.mw.data_manager.genres_data.keys()))
        self.all_albums = sorted(set(k[1] for k in self.mw.data_manager.albums_data.keys()))

        self.batch_detail_widgets = [None] * len(self.tracks)
        self.pending_batch_edits = {}
        self.fetched_tracks = []

        self.new_cover_path = None
        self.cached_new_cover_path = None

        self.status_icon = QIcon(create_svg_icon("assets/control/caution.svg", theme.COLORS["ACCENT"], QSize(16, 16)))

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
        """Builds a streamlined 2-column layout for batch editing."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        files_scroll = StyledScrollArea()
        files_scroll.setWidgetResizable(True)
        files_scroll.setFrameShape(QFrame.Shape.NoFrame)
        files_scroll.setProperty("class", "backgroundTransparent borderRight")
        files_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        files_scroll.setFixedWidth(280)

        files_container = QWidget()
        files_container.setProperty("class", "backgroundPrimary")
        files_layout = QVBoxLayout(files_container)
        files_layout.setContentsMargins(16, 16, 16, 16)
        files_layout.setSpacing(8)
        files_scroll.setWidget(files_container)

        tracks_list_layout_lbl = QLabel(translate("Album Files"))
        tracks_list_layout_lbl.setProperty("class", "textTertiary textColorTertiary")
        files_layout.addWidget(tracks_list_layout_lbl)

        self.tracks_list_widget = StyledListWidget()
        self.tracks_list_widget.setProperty("class", "listWidgetNav")
        self.tracks_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tracks_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tracks_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tracks_list_widget.setItemDelegate(FilenameDelegate(self.tracks_list_widget))
        self.tracks_list_widget.itemSelectionChanged.connect(self._on_track_selection_changed)

        self.tracks_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tracks_list_widget.customContextMenuRequested.connect(self._show_track_list_context_menu)

        files_layout.addWidget(self.tracks_list_widget)

        right_scroll = StyledScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setProperty("class", "backgroundPrimary")
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        right_container = QWidget()
        right_container.setProperty("class", "backgroundPrimary")

        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(24, 24, 24, 24)
        right_layout.setSpacing(32)
        right_scroll.setWidget(right_container)

        cover_block = QVBoxLayout()
        cover_block.setContentsMargins(0, 0, 0, 0)
        cover_block.setSpacing(8)
        cover_block.setAlignment(Qt.AlignmentFlag.AlignTop)

        cover_select_label = QLabel(translate("Artwork & Album Info"))
        cover_select_label.setProperty("class", "textTertiary textColorTertiary")

        self.cover_label = RoundedCoverLabel(self.missing_cover_pixmap, 8)
        self.cover_label.setFixedSize(256, 256)

        cover_btns_layout = QHBoxLayout()
        cover_btns_layout.setContentsMargins(0, 0, 0, 0)
        cover_btns_layout.setSpacing(0)

        change_cover_btn = QPushButton(translate("Change..."))
        change_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_cover_btn.setProperty("class", "btnText inputBorderMultiLeft")
        change_cover_btn.clicked.connect(self._change_cover_manual)
        cover_btns_layout.addWidget(change_cover_btn, 1)

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

        cover_btns_layout.addWidget(self.reset_cover_btn)
        cover_btns_layout.addWidget(self.redo_cover_btn)

        cover_block.addWidget(cover_select_label)
        cover_block.addWidget(self.cover_label)
        cover_block.addSpacing(8)
        cover_block.addLayout(cover_btns_layout)
        cover_block.addSpacing(16)

        self.batch_common_labels = {}

        def create_merge_control(key, label_text):
            l = QLabel(label_text)
            l.setProperty("class", "textTertiary textColorTertiary")
            self.batch_common_labels[key] = l
            ctrl = MetadataMergeControl("")
            return l, ctrl

        l_album, self.album_ctrl = create_merge_control("Album", translate("Album"))
        l_artist, self.album_artist_ctrl = create_merge_control("Album Artist", translate("Album Artist"))
        l_year, self.year_ctrl = create_merge_control("Year", translate("Year"))

        self.album_ctrl.currentIndexChanged.connect(self.dataChanged.emit)
        if self.album_ctrl.lineEdit(): self.album_ctrl.lineEdit().textChanged.connect(self.dataChanged.emit)
        self.album_artist_ctrl.currentIndexChanged.connect(self.dataChanged.emit)
        if self.album_artist_ctrl.lineEdit(): self.album_artist_ctrl.lineEdit().textChanged.connect(
            self.dataChanged.emit)
        self.year_ctrl.currentIndexChanged.connect(self.dataChanged.emit)
        if self.year_ctrl.lineEdit(): self.year_ctrl.lineEdit().textChanged.connect(self.dataChanged.emit)

        cover_block.addWidget(l_album)
        cover_block.addWidget(self.album_ctrl)
        cover_block.addSpacing(16)
        cover_block.addWidget(l_artist)
        cover_block.addWidget(self.album_artist_ctrl)
        cover_block.addSpacing(16)
        cover_block.addWidget(l_year)
        cover_block.addWidget(self.year_ctrl)

        cover_widget = QWidget()
        cover_widget.setLayout(cover_block)
        cover_widget.setFixedWidth(256)

        right_layout.addWidget(cover_widget, 0, Qt.AlignmentFlag.AlignTop)

        self.details_stack = QStackedWidget()
        right_layout.addWidget(self.details_stack, 1)

        layout.addWidget(files_scroll, 0)
        layout.addWidget(right_scroll, 1)

    def load_data(self):
        """Loads physical track data, common cover art, and populates the list view."""
        first_track = self.tracks[0]
        pixmap = QPixmap()
        artwork_data = first_track.get("artwork")
        is_common = all(t.get("artwork") == artwork_data for t in self.tracks)

        if is_common and artwork_data:
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

        extended_info = self.mw.library_manager.get_extended_track_info(first_track["path"])
        fmt_raw = extended_info.get("format", "MP3")

        for key, lbl in self.batch_common_labels.items():
            apply_field_tooltip(lbl, key, fmt_raw)
            lbl.setCursor(Qt.CursorShape.WhatsThisCursor)

        self.album_ctrl.update_current_value(first_track.get("album", ""))
        self.album_artist_ctrl.update_current_value(first_track.get("album_artist", ""))
        self.year_ctrl.update_current_value(str(first_track.get("year", "")))

        self.tracks_list_widget.clear()
        for i, track in enumerate(self.tracks):
            filename = os.path.basename(track["path"])
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, track["path"])
            item.setData(Qt.ItemDataRole.UserRole + 1, i)

            safe_text = html.escape(filename)
            set_custom_tooltip(item, title = translate("File Name"), text = safe_text)
            self.tracks_list_widget.addItem(item)

        self.multi_edit_widget = MultiTrackEditWidget(
            self.all_artists, self.all_genres, fmt_raw,
            is_mixed_mode = False, all_albums = self.all_albums, parent = self
        )
        self.multi_edit_widget.fieldApplied.connect(self._apply_multi_edit)
        self.details_stack.addWidget(self.multi_edit_widget)

        if self.tracks:
            self.tracks_list_widget.setCurrentRow(0)

    def _on_track_selection_changed(self):
        """Switches between individual track editor and multi-track bulk editor dynamically."""
        selected_items = self.tracks_list_widget.selectedItems()
        if not selected_items:
            return

        if len(selected_items) == 1:
            idx = selected_items[0].data(Qt.ItemDataRole.UserRole + 1)

            if self.batch_detail_widgets[idx] is None:
                track = self.tracks[idx]
                detail_widget = BatchTrackDetailWidget(
                    track, self.all_artists, self.all_genres, self.mw,
                    is_mixed_mode = False, all_albums = self.all_albums
                )

                pending = self.pending_batch_edits.get(idx, {})
                for ui_key, val in pending.items():
                    target = detail_widget.inputs if ui_key in detail_widget.inputs else detail_widget.advanced_widget.inputs
                    if ui_key in target:
                        target[ui_key].setCurrentText(val)
                        if target[ui_key].lineEdit():
                            target[ui_key].lineEdit().setText(val)
                        target[ui_key]._update_style()

                detail_widget.dataChanged.connect(lambda i = idx: self._update_track_status_icon(i))
                detail_widget.dataChanged.connect(self.dataChanged.emit)

                detail_widget.statusMessage.connect(self.statusMessage.emit)

                self.details_stack.addWidget(detail_widget)
                self.batch_detail_widgets[idx] = detail_widget

            self.details_stack.setCurrentWidget(self.batch_detail_widgets[idx])

        elif len(selected_items) > 1:
            indices = [item.data(Qt.ItemDataRole.UserRole + 1) for item in selected_items]
            self.multi_edit_widget.load_selection(indices, self.batch_detail_widgets, self.tracks,
                                                  self.pending_batch_edits)
            self.details_stack.setCurrentWidget(self.multi_edit_widget)

    def _apply_multi_edit(self, key, value):
        """
        Applies a specific metadata change to all currently selected tracks in the batch editor.
        Handles both instantiated detail widgets and pending background edits.
        """
        selected_items = self.tracks_list_widget.selectedItems()
        is_reset_mixed = (value == "__RESET_MIXED__")
        if value is None: value = ""

        for item in selected_items:
            idx = item.data(Qt.ItemDataRole.UserRole + 1)
            widget = self.batch_detail_widgets[idx]
            track = self.tracks[idx]

            if widget is not None:
                target_inputs = widget.inputs if key in widget.inputs else widget.advanced_widget.inputs
                if key in target_inputs:
                    inp = target_inputs[key]
                    if is_reset_mixed:
                        inp.reset_to_original()
                    else:
                        inp.setCurrentText(value)
                        if inp.lineEdit(): inp.lineEdit().setText(value)
                    inp._update_style()
            else:
                if is_reset_mixed:
                    if idx in self.pending_batch_edits and key in self.pending_batch_edits[idx]:
                        del self.pending_batch_edits[idx][key]
                else:
                    orig_val = get_original_tag_value(key, track, self.mw.library_manager)

                    if str(value).strip() == str(orig_val).strip():
                        if idx in self.pending_batch_edits and key in self.pending_batch_edits[idx]:
                            del self.pending_batch_edits[idx][key]
                    else:
                        if idx not in self.pending_batch_edits:
                            self.pending_batch_edits[idx] = {}
                        self.pending_batch_edits[idx][key] = value

            if idx in self.pending_batch_edits and not self.pending_batch_edits[idx]:
                del self.pending_batch_edits[idx]

            self._update_track_status_icon(idx)
        self.dataChanged.emit()

    def _update_track_status_icon(self, index):
        """
        Updates the warning/status icon next to a track in the list if it has unsaved modifications.
        """
        if 0 <= index < len(self.batch_detail_widgets):
            widget = self.batch_detail_widgets[index]
            item = self.tracks_list_widget.item(index)

            has_mods = False
            if widget is not None:
                has_mods = widget.has_modifications()
            else:
                has_mods = index in self.pending_batch_edits and bool(self.pending_batch_edits[index])

            if has_mods:
                item.setIcon(self.status_icon)
            else:
                item.setIcon(QIcon())

    def get_data(self):
        """Compiles finalized data from common controls, active widgets, and pending edits."""
        results = {}

        common_data = {
            "album": self.album_ctrl.get_final_value(),
            "albumartist": self.album_artist_ctrl.get_final_value(),
            "date": self.year_ctrl.get_final_value(),
        }
        if self.new_cover_path:
            common_data["artwork_path"] = self.new_cover_path

        for idx, track in enumerate(self.tracks):
            widget = self.batch_detail_widgets[idx]
            if widget is not None:
                row_data = widget.get_data()
                path = row_data.pop("path")
                final = common_data.copy()
                final.update(row_data)
                results[path] = final
            else:
                pending = self.pending_batch_edits.get(idx, {})
                row_data = self._build_lazy_data(track, pending)
                final = common_data.copy()
                final.update(row_data)
                results[track["path"]] = final

        return results

    def _build_lazy_data(self, track, pending_edits):
        """Constructs final data dictionary for a track without instantiating its UI widget."""
        artists = track.get("artists", [])
        if not artists and track.get("artist"): artists = [track.get("artist")]
        artist_str = "; ".join([x for x in artists if x]) if isinstance(artists, list) else str(artists)

        g = track.get("genre", [])
        genre_str = "; ".join([x for x in g if x]) if isinstance(g, list) else str(g)

        data = {
            "title": track.get("title", ""),
            "artist": artist_str,
            "composer": track.get("composer", ""),
            "genre": genre_str,
            "tracknumber": str(track.get("tracknumber", "")),
            "discnumber": str(track.get("discnumber", "")),
            "lyrics": track.get("lyrics", ""),
        }

        key_map = {
            "Title": "title", "Artist": "artist", "Composer": "composer", "Genre": "genre",
            "Track Number": "tracknumber", "Disc Number": "discnumber"
        }

        for ui_key, val in pending_edits.items():
            if ui_key in key_map:
                data[key_map[ui_key]] = val
            else:
                data[ui_key] = val

        return data

    def get_diff_summary(self):
        """Generates the difference table comparing original files to current editor state."""
        diff_summary = []
        new_data_map = self.get_data()

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

        if self.new_cover_path:
            diff_summary.append(
                (translate("All files"), display_names["artwork_path"], translate("Current"), translate("New Image")))

        for i, track in enumerate(self.tracks):
            path = track["path"]
            if path not in new_data_map:
                continue

            new_tags = new_data_map[path]

            widget = self.batch_detail_widgets[i]
            if widget is not None:
                original_ext = widget.extended_data
            else:
                original_ext = self.mw.library_manager.get_extended_track_info(path)

            for key, new_val in new_tags.items():
                if key == "artwork_path":
                    continue

                old_val = ""
                if key in advanced_keys:
                    old_val = original_ext.get(key, "")
                else:
                    if key == "genre":
                        g = track.get("genre", [])
                        old_val = "; ".join([x for x in g if x]) if isinstance(g, list) else str(g) if g else ""
                    elif key == "artist":
                        a = track.get("artists", [])
                        if not a and track.get("artist"): a = [track.get("artist")]
                        old_val = "; ".join([x for x in a if x]) if isinstance(a, list) else str(a) if a else ""
                    elif key == "date":
                        old_val = track.get("year", "")
                    elif key == "albumartist":
                        old_val = track.get("album_artist", "")
                    else:
                        old_val = track.get(key, "")

                s_old = str(old_val).strip() if old_val is not None else ""
                s_new = str(new_val).strip() if new_val is not None else ""

                if s_old != s_new:
                    if key == "lyrics":
                        disp_old = (s_old[:20] + "...") if len(s_old) > 20 else s_old
                        disp_new = (s_new[:20] + "...") if len(s_new) > 20 else s_new
                    else:
                        disp_old, disp_new = s_old, s_new

                    diff_summary.append((os.path.basename(path), display_names.get(key, key), disp_old, disp_new))

        return diff_summary

    def get_search_queries(self):
        """Returns Artist and Album data for Apple Music search querying."""
        artist = self.album_artist_ctrl.get_final_value()
        if not artist and self.tracks:
            artist = self.tracks[0].get("artist", "")
        return (artist, self.album_ctrl.get_final_value())

    def apply_search_results(self, result, raw_data, fetched_tracks):
        """Applies global search results and auto-maps tracks internally."""
        self.fetched_tracks = fetched_tracks

        self.album_ctrl.set_fetched_value(result.get("album", ""))
        self.album_artist_ctrl.set_fetched_value(result.get("artist", ""))
        self.year_ctrl.set_fetched_value(result.get("year", ""))

        for i, track in enumerate(self.tracks):
            found_idx = self._find_best_match_index(track, fetched_tracks, i)

            if found_idx != -1:
                ft = fetched_tracks[found_idx]
                widget = self.batch_detail_widgets[i]

                if widget is not None:
                    widget.show_match_container()
                    widget.set_match_options(fetched_tracks)
                    widget.match_combo.setCurrentIndex(found_idx + 1)
                else:
                    if i not in self.pending_batch_edits:
                        self.pending_batch_edits[i] = {}

                    self.pending_batch_edits[i]["Title"] = ft["title"]
                    self.pending_batch_edits[i]["Artist"] = ft["artist"]
                    self.pending_batch_edits[i]["Genre"] = ft.get("genre", "")
                    self.pending_batch_edits[i]["Track Number"] = str(ft["track_number"])
                    self.pending_batch_edits[i]["Disc Number"] = str(ft["_raw"].get("discNumber", 1))

    def apply_new_cover(self, path):
        """Sets a globally applied cover image."""
        self.new_cover_path = path
        self.cached_new_cover_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.cover_label.setPixmap(
                pixmap.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.reset_cover_btn.setEnabled(True)
        self._update_cover_buttons()
        self.dataChanged.emit()

    def _find_best_match_index(self, local_track_data, fetched_tracks_list, default_index):
        """Matches a local physical file to an Apple Music track result."""
        local_title = local_track_data.get("title", "")
        filename = os.path.splitext(os.path.basename(local_track_data.get("path", "")))[0]
        try:
            local_disc = int(str(local_track_data.get("discnumber", "1")).split("/")[0])
            local_track = int(str(local_track_data.get("tracknumber", "0")).split("/")[0])
        except:
            local_disc, local_track = 1, 0

        if local_title:
            best_score, best_idx = 0.0, -1
            for i, ft in enumerate(fetched_tracks_list):
                score = difflib.SequenceMatcher(None, str(local_title).lower().strip(),
                                                str(ft["title"]).lower().strip()).ratio()
                if score > best_score: best_score, best_idx = score, i
            if best_score > 0.85: return best_idx

        if local_track > 0:
            for i, ft in enumerate(fetched_tracks_list):
                if ft["_raw"].get("discNumber", 1) == local_disc and ft["track_number"] == local_track:
                    return i

        best_score, best_idx = 0.0, -1
        for i, ft in enumerate(fetched_tracks_list):
            score = difflib.SequenceMatcher(None, filename.lower().strip(), str(ft["title"]).lower().strip()).ratio()
            if score > best_score: best_score, best_idx = score, i
        if best_score > 0.6: return best_idx

        if 0 <= default_index < len(fetched_tracks_list):
            return default_index
        return -1

    def _change_cover_manual(self):
        """
        Opens a file dialog allowing the user to manually select a new cover image for the album.
        """
        initial_dir = os.path.dirname(self.tracks[0]["path"]) if self.tracks else ""
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
        Resets the album cover back to its original state before any modifications were made.
        """
        self.cover_label.setPixmap(self.original_cover_pixmap)
        self.new_cover_path = None
        self._update_cover_buttons()
        self.dataChanged.emit()

    def _restore_new_cover(self):
        """
        Restores the newly selected cover image if the user previously clicked the reset button.
        """
        if self.cached_new_cover_path and os.path.exists(self.cached_new_cover_path):
            self.apply_new_cover(self.cached_new_cover_path)

    def has_modifications(self):
        """
        Checks if any track or common album field has unsaved modifications.

        Returns:
            bool: True if there are pending edits, False otherwise.
        """
        if self.new_cover_path: return True
        if bool(self.pending_batch_edits): return True

        if self.album_ctrl.get_final_value() != self.album_ctrl.current_val: return True
        if self.album_artist_ctrl.get_final_value() != self.album_artist_ctrl.current_val: return True
        if self.year_ctrl.get_final_value() != self.year_ctrl.current_val: return True

        for widget in self.batch_detail_widgets:
            if widget is not None and widget.has_modifications():
                return True
        return False

    def _show_track_list_context_menu(self, pos):
        """Spawns a context menu directly from a selected track item in the left-hand track panel."""
        item = self.tracks_list_widget.itemAt(pos)
        if not item:
            return

        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        menu = TranslucentMenu(self)
        icn_folder = QIcon(
            create_svg_icon(
                "assets/control/search_folder.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        action = QAction(icn_folder, translate("Show File Location"), self)
        action.triggered.connect(lambda: self.mw.action_handler.show_in_explorer(path))
        menu.addAction(action)
        menu.exec(self.tracks_list_widget.mapToGlobal(pos))