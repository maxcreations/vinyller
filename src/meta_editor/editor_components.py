"""
Vinyller — Editor components
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

from PyQt6.QtCore import Qt, QRect, QEvent, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QStyleOptionViewItem, QStyle, QApplication,
    QStyledItemDelegate, QGridLayout, QFormLayout, QFileDialog,
    QTabWidget, QFrame
)

from src.ui.custom_base_widgets import (
    StyledTextEdit, TranslucentCombo, StyledScrollArea, set_custom_tooltip
)
from src.ui.custom_classes import (
    GapCompleter, MetadataMergeControl, RoundedCoverLabel,
    ElidedLabel, apply_label_opacity_effect
)
from src.ui.search_services_tools import SearchToolButton
from src.utils import theme
from src.utils.utils import create_svg_icon, fetch_lyrics_from_lrclib
from src.utils.utils_translator import translate

TAG_DEFINITIONS = {
    "Title": {"MP3": "TIT2", "FLAC": "TITLE", "OggVorbis": "TITLE", "MP4": "©nam", "ASF": "Title"},
    "Artist": {"MP3": "TPE1", "FLAC": "ARTIST", "OggVorbis": "ARTIST", "MP4": "©ART", "ASF": "Author"},
    "Album": {"MP3": "TALB", "FLAC": "ALBUM", "OggVorbis": "ALBUM", "MP4": "©alb", "ASF": "WM/AlbumTitle"},
    "Album Artist": {"MP3": "TPE2", "FLAC": "ALBUMARTIST", "OggVorbis": "ALBUMARTIST", "MP4": "aART", "ASF": "WM/AlbumArtist"},
    "Composer": {"MP3": "TCOM", "FLAC": "COMPOSER", "OggVorbis": "COMPOSER", "MP4": "©wrt", "ASF": "WM/Composer"},
    "Genre": {"MP3": "TCON", "FLAC": "GENRE", "OggVorbis": "GENRE", "MP4": "©gen", "ASF": "WM/Genre"},
    "Year": {"MP3": "TDRC/TYER", "FLAC": "DATE", "OggVorbis": "DATE", "MP4": "©day", "ASF": "WM/Year"},
    "Track Number": {"MP3": "TRCK", "FLAC": "TRACKNUMBER", "OggVorbis": "TRACKNUMBER", "MP4": "trkn", "ASF": "WM/TrackNumber"},
    "Disc Number": {"MP3": "TPOS", "FLAC": "DISCNUMBER", "OggVorbis": "DISCNUMBER", "MP4": "disk", "ASF": "WM/PartOfSet"},
    "Lyrics": {"MP3": "USLT", "FLAC": "LYRICS", "OggVorbis": "LYRICS", "MP4": "©lyr", "ASF": "WM/Lyrics"},

    "original_year": {
        "MP3": "TDOR", "FLAC": "ORIGINALDATE", "OggVorbis": "ORIGINALDATE",
        "MP4": "©day", "ASF": "OriginalReleaseYear"
    },
    "comment": {
        "MP3": "COMM", "FLAC": "COMMENT", "OggVorbis": "COMMENT",
        "MP4": "©cmt", "ASF": "Description"
    },
    "copyright": {
        "MP3": "TCOP", "FLAC": "COPYRIGHT", "OggVorbis": "COPYRIGHT",
        "MP4": "©cpy", "ASF": "Copyright"
    },
    "source_url": {
        "MP3": "WOAS", "FLAC": "SOURCE", "OggVorbis": "SOURCE",
        "MP4": "-", "ASF": "-"
    },
    "user_url": {
        "MP3": "WXXX", "FLAC": "CONTACT", "OggVorbis": "CONTACT",
        "MP4": "-", "ASF": "-"
    },
    "bpm": {
        "MP3": "TBPM", "FLAC": "BPM", "OggVorbis": "BPM",
        "MP4": "tmpo", "ASF": "-"
    },
    "isrc": {
        "MP3": "TSRC", "FLAC": "ISRC", "OggVorbis": "ISRC",
        "MP4": "----:com.apple.iTunes:ISRC", "ASF": "ISRC"
    },
    "media_type": {
        "MP3": "TMED", "FLAC": "MEDIA", "OggVorbis": "MEDIA",
        "MP4": "-", "ASF": "-"
    },
    "encoded_by": {
        "MP3": "TENC", "FLAC": "ENCODEDBY", "OggVorbis": "ENCODEDBY",
        "MP4": "©enc", "ASF": "-"
    },
    "encoder_settings": {
        "MP3": "TSSE", "FLAC": "ENCODERSETTINGS", "OggVorbis": "ENCODERSETTINGS",
        "MP4": "-", "ASF": "-"
    }
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
    Generates an HTML-formatted tooltip displaying the underlying metadata tag code for a given field and format.
    """
    fmt_key = get_format_key(format_str)
    code = TAG_DEFINITIONS.get(field_key, {}).get(fmt_key, translate("Unknown"))
    return f"{translate('Target Tag')}: <b>{code}</b>"

def apply_field_tooltip(widget, key, format_str):
    """
    Applies standardized tooltips. Sets the target tag as the title,
    and adds supplementary instructions for specific fields.
    """
    title = get_tag_tooltip(key, format_str)

    extra_text = None
    if key in ["Artist", "Composer", "Genre"]:
        extra_text = translate("Use semicolons (;) to separate multiple values")

    set_custom_tooltip(widget, title = title, text = extra_text)

def get_original_tag_value(key, track, library_manager=None):
    """Extracts the original unedited value of a specific tag from a track dict."""
    if key == "Artist":
        artists = track.get("artists", [])
        if not artists and track.get("artist"): artists = [track.get("artist")]
        return "; ".join([x for x in artists if x]) if isinstance(artists, list) else str(artists)
    elif key == "Genre":
        g = track.get("genre", [])
        return "; ".join([x for x in g if x]) if isinstance(g, list) else str(g)
    elif key == "Album Artist": return track.get("album_artist", "")
    elif key == "Disc Number": return str(track.get("discnumber", ""))
    elif key == "Track Number": return str(track.get("tracknumber", ""))
    elif key == "Album": return track.get("album", "")
    elif key == "Year": return str(track.get("year", ""))
    elif key == "Title": return track.get("title", "")
    elif key == "Composer": return track.get("composer", "")
    elif key == "Lyrics": return track.get("lyrics", "")
    else:
        if library_manager:
            ext = library_manager.get_extended_track_info(track["path"])
            return str(ext.get(key, ""))
        return str(track.get(key.lower(), ""))


class FilenameDelegate(QStyledItemDelegate):
    """Delegate for displaying filenames with ellipsis AND icons."""
    def paint(self, painter, option, index):
        """
        Renders the item, displaying an icon and eliding text if it exceeds the available width.
        """
        painter.save()
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, opt.widget)

        rect = QRect(opt.rect)
        if not opt.icon.isNull():
            icon_size = opt.decorationSize
            if icon_size.isEmpty():
                icon_size = QSize(16, 16)
            icon_y = rect.y() + (rect.height() - icon_size.height()) // 2
            opt.icon.paint(painter, rect.x() + 12, icon_y, icon_size.width(), icon_size.height())
            rect.setLeft(rect.left() + icon_size.width() + 20)
        else:
            rect.setLeft(rect.left() + 12)

        rect.setRight(rect.right() - 12)

        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text:
            fm = opt.fontMetrics
            elided_text = fm.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)
        painter.restore()

    def sizeHint(self, option, index):
        """
        Returns the recommended size for the item.
        """
        return super().sizeHint(option, index)


class LyricsTextEdit(StyledTextEdit):
    """Text field for song lyrics with robust manual vertical resizing."""
    def __init__(self, parent=None):
        """
        Initializes the lyrics editor with a custom resize handle.
        """
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setProperty("class", "lyricsEditor")

        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)

        self._is_resizing = False
        self._resize_start_pos = None
        self._resize_start_height = None

        self.resize_icon_label = QLabel(self)
        apply_label_opacity_effect(self.resize_icon_label)

        try:
            icon_pixmap = QIcon(create_svg_icon("assets/control/resize.svg", theme.COLORS["PRIMARY"], QSize(16, 16))).pixmap(16, 16)
            self.resize_icon_label.setPixmap(icon_pixmap)
        except Exception:
            pass

        self.resize_icon_label.setFixedSize(16, 16)
        self.resize_icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def _update_icon_position(self):
        """
        Updates the position of the resize icon to stay in the bottom-right corner.
        """
        v_rect = self.viewport().geometry()
        self.resize_icon_label.move(v_rect.right() - 16, v_rect.bottom() - 16)

    def resizeEvent(self, event):
        """
        Handles widget resize events to keep the icon positioned correctly.
        """
        super().resizeEvent(event)
        self._update_icon_position()

    def insertFromMimeData(self, source):
        """
        Overrides default paste behavior to strip rich text formatting.
        """
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

    def _get_resize_zone(self):
        """
        Calculates the rectangular area in the bottom-right corner used for resizing.
        """
        rect = self.viewport().rect()
        return QRect(rect.width() - 24, rect.height() - 24, 24, 24)

    def eventFilter(self, obj, event):
        """
        Intercepts mouse events on the viewport to implement custom manual resizing.
        """
        if obj == self.viewport():
            if event.type() == QEvent.Type.Resize:
                self._update_icon_position()
            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton and self._get_resize_zone().contains(event.pos()):
                    self._is_resizing = True
                    self._resize_start_pos = event.globalPosition()
                    self._resize_start_height = self.height()
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                if self._is_resizing:
                    delta = event.globalPosition().y() - self._resize_start_pos.y()
                    new_height = max(100, self._resize_start_height + delta)
                    self.setFixedHeight(int(new_height))
                    return True
                else:
                    if self._get_resize_zone().contains(event.pos()):
                        self.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor)
                    else:
                        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if self._is_resizing and event.button() == Qt.MouseButton.LeftButton:
                    self._is_resizing = False
                    if not self._get_resize_zone().contains(event.pos()):
                        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
                    return True
        return super().eventFilter(obj, event)


class AdvancedMetadataWidget(QWidget):
    """Widget for the 'Advanced' tab in the Metadata Editor."""
    dataChanged = pyqtSignal()

    SUPPORTED_FIELDS = {
        "MP3": "all",
        "FLAC": "all",
        "OggVorbis": "all",
        "MP4": {"original_year", "comment", "copyright", "encoded_by", "encoder_settings", "bpm", "isrc"},
        "ASF": {"original_year", "comment", "copyright", "encoded_by", "isrc"}
    }

    def __init__(self, parent=None):
        """
        Initializes the advanced metadata widget.
        """
        super().__init__(parent)
        self.inputs = {}
        self.field_containers = {}
        self.field_labels = {}
        self.extended_data = {}
        self.current_fmt = "MP3"
        self.setupUi()

    def setupUi(self):
        """
        Constructs the layout and initializes all input fields for advanced tags.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 16, 0, 0)
        self.content_layout.setSpacing(16)

        info_group = QWidget()
        info_group.setProperty("class", "infoBox")
        info_layout = QGridLayout(info_group)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(12)

        self.lbl_format = self._create_info_label(translate("Format"), info_layout, 0, 0)
        self.lbl_duration = self._create_info_label(translate("Duration"), info_layout, 0, 1)
        self.lbl_bitrate = self._create_info_label(translate("Bitrate"), info_layout, 1, 0)
        self.lbl_sample = self._create_info_label(translate("Sample Rate"), info_layout, 1, 1)
        self.lbl_channels = self._create_info_label(translate("Channels"), info_layout, 2, 0)

        self.content_layout.addWidget(info_group)

        adv_fields = [
            ("original_year", translate("Original Release Year")),
            ("comment", translate("Comment")),
            ("copyright", translate("Copyright")),
            ("source_url", translate("Source URL")),
            ("user_url", translate("User URL")),
            ("bpm", translate("BPM")),
            ("isrc", translate("ISRC")),
            ("media_type", translate("Media Type")),
            ("encoded_by", translate("Encoded By")),
            ("encoder_settings", translate("Encoder Settings")),
        ]

        for key, label_text in adv_fields:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(8)

            lbl = QLabel(label_text)
            lbl.setProperty("class", "textTertiary textColorTertiary")
            lbl.setCursor(Qt.CursorShape.WhatsThisCursor)

            inp = MetadataMergeControl("", border_style="inputBorderSinglePadding")
            inp.currentIndexChanged.connect(self.dataChanged)
            if inp.lineEdit():
                inp.lineEdit().textChanged.connect(self.dataChanged)

            self.inputs[key] = inp
            self.field_labels[key] = lbl

            container_layout.addWidget(lbl)
            container_layout.addWidget(inp)
            self.content_layout.addWidget(container)
            self.field_containers[key] = container

        self.content_layout.addSpacing(16)
        other_lbl = QLabel(translate("Other Tags (Read-only)"))
        other_lbl.setProperty("class", "textHeaderSecondary textColorPrimary")
        self.content_layout.addWidget(other_lbl)

        self.other_tags_layout = QFormLayout()
        self.other_tags_layout.setSpacing(8)
        self.other_tags_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.content_layout.addLayout(self.other_tags_layout)
        self.content_layout.addStretch()

        main_layout.addWidget(self.content_widget)

    def _create_info_label(self, title, layout, row, col):
        """
        Helper method to create and add a read-only information label to the grid layout.
        """
        container = QVBoxLayout()
        container.setSpacing(2)
        t_lbl = QLabel(title)
        t_lbl.setProperty("class", "textTertiary textColorTertiary")
        v_lbl = QLabel("-")
        v_lbl.setProperty("class", "textSecondary textColorPrimary")
        container.addWidget(t_lbl)
        container.addWidget(v_lbl)
        layout.addLayout(container, row, col)
        return v_lbl

    def load_data(self, extended_data):
        """
        Populates the inputs and read-only fields with the provided extended metadata.
        """
        self.extended_data = extended_data
        fmt = extended_data.get("format", "Unknown")
        self.current_fmt = fmt

        self.lbl_format.setText(fmt)
        self.lbl_duration.setText(extended_data.get("duration_str", "00:00:00"))
        self.lbl_bitrate.setText(extended_data.get("bitrate", "N/A"))
        self.lbl_sample.setText(extended_data.get("sample_rate", "N/A"))
        self.lbl_channels.setText(extended_data.get("channels", "N/A"))

        self._update_ui_for_format()

        for key, inp in self.inputs.items():
            val = extended_data.get(key, "")
            inp.update_current_value(str(val) if val else "")

        while self.other_tags_layout.rowCount() > 0:
            self.other_tags_layout.removeRow(0)

        for tag, val in extended_data.get("other_tags", []):
            label = QLabel(f"{tag}:")
            label.setProperty("class", "textTertiary textColorTertiary")
            value = ElidedLabel(str(val))
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.other_tags_layout.addRow(label, value)

    def _update_ui_for_format(self):
        """
        Shows or hides specific input fields based on what the current audio format supports.
        """
        fmt_key = get_format_key(self.current_fmt)
        allowed = self.SUPPORTED_FIELDS.get(fmt_key, "all")

        for key, container in self.field_containers.items():
            is_visible = (allowed == "all" or key in allowed)
            container.setVisible(is_visible)
            if is_visible:
                apply_field_tooltip(self.field_labels[key], key, self.current_fmt)

    def get_data(self):
        """
        Collects and returns all modified advanced tag values.
        """
        data = {}
        fmt_key = get_format_key(self.current_fmt)
        allowed = self.SUPPORTED_FIELDS.get(fmt_key, "all")

        for key, inp in self.inputs.items():
            if not (allowed == "all" or key in allowed):
                continue
            final_val = inp.get_final_value()
            if final_val != inp.current_val:
                data[key] = final_val
        return data

    def has_modifications(self):
        """
        Checks if any of the advanced fields have been changed from their original values.
        """
        fmt_key = get_format_key(self.current_fmt)
        allowed = self.SUPPORTED_FIELDS.get(fmt_key, "all")
        for key, inp in self.inputs.items():
            if not (allowed == "all" or key in allowed):
                continue
            if inp.get_final_value() != inp.current_val:
                return True
        return False


class BatchTrackDetailWidget(QWidget):
    """Detailed track information for batch mode (single track selected)."""
    dataChanged = pyqtSignal()
    coverChanged = pyqtSignal(str)
    statusMessage = pyqtSignal(str)

    def __init__(self, local_track, all_artists, all_genres, main_window, is_mixed_mode=False, all_albums=None, parent=None):
        """
        Initializes the detail widget for a single track within the batch editor.
        """
        super().__init__(parent)
        self.local_track = local_track
        self.all_artists = all_artists
        self.all_genres = all_genres
        self.all_albums = all_albums or []
        self.mw = main_window
        self.is_mixed_mode = is_mixed_mode
        self.inputs = {}
        self._cached_fetched_tracks = []
        self.new_cover_path = None
        self.cached_new_cover_path = None
        self.extended_data = self.mw.library_manager.get_extended_track_info(local_track["path"])

        self.setupUi()
        self.load_initial_data()

    def setupUi(self):
        """
        Builds the UI layout including cover art, basic tags, Apple Music match, and lyrics.
        """
        current_fmt = self.extended_data.get("format", "MP3")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setProperty("class", "tabWidget")
        basic_page = QWidget()

        if self.is_mixed_mode:
            main_basic_layout = QHBoxLayout(basic_page)
            main_basic_layout.setContentsMargins(0, 16, 0, 0)
            main_basic_layout.setSpacing(24)

            column_left = QWidget()
            left_layout = QVBoxLayout(column_left)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            left_layout.setSpacing(8)

            cover_select_label = QLabel(translate("Artwork & File Path"))
            cover_select_label.setProperty("class", "textTertiary textColorTertiary")
            left_layout.addWidget(cover_select_label)

            self.cover_label = RoundedCoverLabel(QPixmap(), 8)
            self.cover_label.setFixedSize(256, 256)

            cover_btns_layout = QHBoxLayout()
            cover_btns_layout.setContentsMargins(0, 0, 0, 0)
            cover_btns_layout.setSpacing(0)

            change_cover_btn = QPushButton(translate("Change..."))
            change_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            change_cover_btn.setProperty("class", "btnText inputBorderMultiLeft")
            change_cover_btn.clicked.connect(self._change_cover)
            cover_btns_layout.addWidget(change_cover_btn, 1)

            self.reset_cover_btn = QPushButton()
            self.reset_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.reset_cover_btn.setProperty("class", "inputBorderMultiMiddle")
            self.reset_cover_btn.setIcon(QIcon(create_svg_icon("assets/control/undo.svg", theme.COLORS["PRIMARY"], QSize(20, 20))))
            self.reset_cover_btn.setIconSize(QSize(20, 20))
            self.reset_cover_btn.clicked.connect(self._reset_cover)
            self.reset_cover_btn.setEnabled(False)
            set_custom_tooltip(self.reset_cover_btn, title = translate("Reset to original cover"))

            self.redo_cover_btn = QPushButton()
            self.redo_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.redo_cover_btn.setProperty("class", "inputBorderMultiRight")
            self.redo_cover_btn.setIcon(QIcon(create_svg_icon("assets/control/redo.svg", theme.COLORS["PRIMARY"], QSize(20, 20))))
            self.redo_cover_btn.setIconSize(QSize(20, 20))
            self.redo_cover_btn.clicked.connect(self._restore_new_cover)
            self.redo_cover_btn.setEnabled(False)
            set_custom_tooltip(self.redo_cover_btn, title = translate("Restore new cover"))

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

            left_layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)
            left_layout.addSpacing(8)
            left_layout.addLayout(cover_btns_layout)
            left_layout.addSpacing(16)
            left_layout.addLayout(info_layout)
            left_layout.addStretch()

            main_basic_layout.addWidget(column_left, 0)
            column_right = QWidget()
            target_layout = QVBoxLayout(column_right)
            target_layout.setContentsMargins(0, 0, 0, 0)
            target_layout.setSpacing(16)
            main_basic_layout.addWidget(column_right, 1)

        else:
            target_layout = QVBoxLayout(basic_page)
            target_layout.setContentsMargins(0, 16, 0, 0)
            target_layout.setSpacing(16)

        self.match_container = QWidget()
        match_layout = QVBoxLayout(self.match_container)
        match_layout.setSpacing(8)
        match_layout.setContentsMargins(0, 0, 0, 0)
        match_lbl = QLabel(translate("Apple Music Match"))
        match_lbl.setProperty("class", "textTertiary textColorTertiary")
        self.match_combo = TranslucentCombo()
        self.match_combo.setProperty("class", "inputBorderSinglePadding")
        self.match_combo.addItem(translate("No Match"), None)
        self.match_combo.currentIndexChanged.connect(self._on_match_selected)
        match_layout.addWidget(match_lbl)
        match_layout.addWidget(self.match_combo)
        target_layout.addWidget(self.match_container)
        self.match_container.setVisible(False)

        numbers_container = QWidget()
        numbers_hbox = QHBoxLayout(numbers_container)
        numbers_hbox.setContentsMargins(0, 0, 0, 0)
        numbers_hbox.setSpacing(0)

        def create_number_field(key, label_text, style):
            container = QWidget()
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setProperty("class", "textTertiary textColorTertiary")
            apply_field_tooltip(lbl, key, current_fmt)
            lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
            inp = MetadataMergeControl("", border_style=style)
            inp.currentIndexChanged.connect(self.dataChanged)
            if inp.lineEdit(): inp.lineEdit().textChanged.connect(self.dataChanged)
            v_layout.addWidget(lbl)
            v_layout.addWidget(inp)
            self.inputs[key] = inp
            return container

        numbers_hbox.addWidget(create_number_field("Disc Number", translate("Disc #"), "inputBorderMultiLeft inputBorderPaddingTextEdit"))
        numbers_hbox.addWidget(create_number_field("Track Number", translate("Track #"), "inputBorderMultiRight inputBorderPaddingTextEdit"))
        target_layout.addWidget(numbers_container)

        fields = [("Title", translate("Title"), None), ("Artist", translate("Artist"), self.all_artists)]
        if self.is_mixed_mode:
            fields.extend([("Album", translate("Album"), self.all_albums), ("Album Artist", translate("Album Artist"), self.all_artists), ("Year", translate("Year"), None)])
        fields.extend([("Composer", translate("Composer"), self.all_artists), ("Genre", translate("Genre"), self.all_genres)])

        for key, label_text, suggestions in fields:
            field_layout = QVBoxLayout()
            field_layout.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setProperty("class", "textTertiary textColorTertiary")
            apply_field_tooltip(lbl, key, current_fmt)
            lbl.setCursor(Qt.CursorShape.WhatsThisCursor)

            inp = MetadataMergeControl("", border_style="inputBorderSinglePadding")
            if suggestions:
                completer = GapCompleter(suggestions, inp, gap=4)
                popup = completer.popup()
                popup.setProperty("class", "listWidget")
                popup.setContentsMargins(0, 8, 0, 0)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                if inp.lineEdit(): inp.lineEdit().setCompleter(completer)

            inp.currentIndexChanged.connect(self.dataChanged)
            if inp.lineEdit(): inp.lineEdit().textChanged.connect(self.dataChanged)
            self.inputs[key] = inp
            field_layout.addWidget(lbl)
            field_layout.addWidget(inp)
            target_layout.addLayout(field_layout)

        lyrics_group = QVBoxLayout()
        lyrics_group.setContentsMargins(0, 0, 0, 0)
        lyrics_group.setSpacing(8)
        lyrics_lbl = QLabel(translate("Lyrics"))
        lyrics_lbl.setProperty("class", "textTertiary textColorTertiary")
        apply_field_tooltip(lyrics_lbl, "Lyrics", current_fmt)
        lyrics_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
        lyrics_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lyrics_edit = LyricsTextEdit()
        self.lyrics_edit.setPlaceholderText(translate("Enter song lyrics..."))
        self.lyrics_edit.textChanged.connect(self.dataChanged)

        btn_container = QWidget()
        btn_lyrics_layout = QHBoxLayout(btn_container)
        btn_lyrics_layout.setContentsMargins(0, 0, 0, 0)
        btn_lyrics_layout.setSpacing(8)

        self.btn_search_lyrics = SearchToolButton(self.mw)
        self.btn_search_lyrics.set_lyrics_mode(True)
        self.btn_search_lyrics.set_data_getter(lambda: (self.inputs["Artist"].get_final_value(), self.inputs["Title"].get_final_value()))
        self.btn_dl_lyrics = QPushButton(translate("Download from LRCLIB"))
        self.btn_dl_lyrics.setProperty("class", "btnText")
        self.btn_dl_lyrics.clicked.connect(self._download_lyrics)

        btn_lyrics_layout.addWidget(self.btn_search_lyrics)
        btn_lyrics_layout.addWidget(self.btn_dl_lyrics)

        lyrics_group.addWidget(lyrics_lbl, 0, Qt.AlignmentFlag.AlignTop)
        lyrics_group.addWidget(btn_container, 0, Qt.AlignmentFlag.AlignTop)
        lyrics_group.addWidget(self.lyrics_edit, 1, Qt.AlignmentFlag.AlignTop)
        target_layout.addLayout(lyrics_group)

        self.tabs.addTab(basic_page, translate("Basic Tags"))
        self.advanced_widget = AdvancedMetadataWidget(self)
        self.advanced_widget.dataChanged.connect(self.dataChanged)
        self.tabs.addTab(self.advanced_widget, translate("Advanced Tags"))
        layout.addWidget(self.tabs)

    def load_initial_data(self):
        """
        Fills the form fields with the track's existing metadata.
        """
        track = self.local_track
        self.inputs["Title"].update_current_value(track.get("title", ""))

        artists = track.get("artists", [])
        if not artists and track.get("artist"): artists = [track.get("artist")]
        artist_str = "; ".join([x for x in artists if x]) if isinstance(artists, list) else str(artists)
        self.inputs["Artist"].update_current_value(artist_str)

        if self.is_mixed_mode:
            self.inputs["Album"].update_current_value(track.get("album", ""))
            self.inputs["Album Artist"].update_current_value(track.get("album_artist", ""))
            self.inputs["Year"].update_current_value(str(track.get("year", "")))

            if hasattr(self, 'lbl_path'):
                self.lbl_path.setText(track.get("path", ""))

            pixmap = QPixmap()
            artwork_data = track.get("artwork")
            if artwork_data:
                if isinstance(artwork_data, dict):
                    avail = sorted([int(s) for s in artwork_data.keys()])
                    path = artwork_data.get(str(avail[-1])) if avail else None
                else:
                    path = artwork_data
                if path and os.path.exists(path): pixmap = QPixmap(path)

            if pixmap.isNull():
                pixmap = QPixmap(256, 256)
                pixmap.fill(Qt.GlobalColor.gray)

            self.original_cover_pixmap = pixmap.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.cover_label.setPixmap(self.original_cover_pixmap)

        self.inputs["Composer"].update_current_value(track.get("composer", ""))
        g = track.get("genre", [])
        genre_str = "; ".join([x for x in g if x]) if isinstance(g, list) else str(g)
        self.inputs["Genre"].update_current_value(genre_str)
        self.inputs["Track Number"].update_current_value(str(track.get("tracknumber", "")))
        self.inputs["Disc Number"].update_current_value(str(track.get("discnumber", "")))
        self.lyrics_edit.setText(track.get("lyrics", ""))
        self.advanced_widget.load_data(self.extended_data)

    def _update_cover_buttons(self):
        """
        Updates the enabled state of the undo/redo cover art buttons.
        """
        self.reset_cover_btn.setEnabled(self.new_cover_path is not None)
        can_redo = (self.new_cover_path is None) and (self.cached_new_cover_path is not None)
        self.redo_cover_btn.setEnabled(can_redo)

    def _change_cover(self):
        """
        Opens a file dialog for the user to select a new cover image.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, translate("Select New Cover"), "", translate("Image Files (*.png *.jpg *.jpeg)"))
        if file_path: self._apply_new_cover(file_path)

    def _apply_new_cover(self, path):
        """
        Applies the selected cover image to the UI and marks it as modified.
        """
        self.new_cover_path = path
        self.cached_new_cover_path = path
        self.cover_label.setPixmap(QPixmap(path).scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self._update_cover_buttons()
        self.coverChanged.emit(path)
        self.dataChanged.emit()

    def _reset_cover(self):
        """
        Reverts the cover art to its original image.
        """
        if hasattr(self, "original_cover_pixmap"):
            self.cover_label.setPixmap(self.original_cover_pixmap)
            self.new_cover_path = None
            self._update_cover_buttons()
            self.coverChanged.emit("__RESET_MIXED__")
            self.dataChanged.emit()

    def _restore_new_cover(self):
        """
        Re-applies the user's newly selected cover image if it was previously reset.
        """
        if self.cached_new_cover_path and os.path.exists(self.cached_new_cover_path):
            self._apply_new_cover(self.cached_new_cover_path)

    def get_data(self):
        """
        Gathers all the finalized tag data and lyrics from the widget inputs.
        """
        data = {
            "title": self.inputs["Title"].get_final_value(),
            "artist": self.inputs["Artist"].get_final_value(),
            "composer": self.inputs["Composer"].get_final_value(),
            "genre": self.inputs["Genre"].get_final_value(),
            "tracknumber": self.inputs["Track Number"].get_final_value(),
            "discnumber": self.inputs["Disc Number"].get_final_value(),
            "lyrics": self.lyrics_edit.toPlainText(),
            "path": self.local_track["path"],
        }
        if self.is_mixed_mode:
            data["album"] = self.inputs["Album"].get_final_value()
            data["albumartist"] = self.inputs["Album Artist"].get_final_value()
            data["date"] = self.inputs["Year"].get_final_value()
            if self.new_cover_path: data["artwork_path"] = self.new_cover_path

        data.update(self.advanced_widget.get_data())
        return data

    def has_modifications(self):
        """
        Checks if any metadata, lyrics, or cover art have been modified.
        """
        for inp in self.inputs.values():
            if inp.get_final_value() != inp.current_val: return True
        if self.lyrics_edit.toPlainText() != self.local_track.get("lyrics", ""): return True
        if self.is_mixed_mode and self.new_cover_path: return True
        if self.advanced_widget.has_modifications(): return True
        return False

    def show_match_container(self):
        """
        Makes the Apple Music match dropdown visible.
        """
        self.match_container.setVisible(True)

    def set_match_options(self, fetched_tracks):
        """
        Populates the match dropdown with fetched track results.
        """
        self._cached_fetched_tracks = fetched_tracks
        current_data = self.match_combo.currentData()
        self.match_combo.blockSignals(True)
        self.match_combo.clear()
        self.match_combo.addItem(translate("No Match"), None)
        for i, ft in enumerate(fetched_tracks):
            disc = ft["_raw"].get("discNumber", 1)
            track_n = ft["track_number"]
            display = f"{disc}-{track_n:02d}. {ft['title']}"
            self.match_combo.addItem(display, i)

        if current_data is not None:
            idx = self.match_combo.findData(current_data)
            if idx >= 0: self.match_combo.setCurrentIndex(idx)
        self.match_combo.blockSignals(False)

    def _on_match_selected(self):
        """
        Applies the metadata from the selected Apple Music match to the input fields.
        """
        idx = self.match_combo.currentData()
        if idx is not None and 0 <= idx < len(self._cached_fetched_tracks):
            ft = self._cached_fetched_tracks[idx]
            self.inputs["Title"].set_fetched_value(ft["title"])
            self.inputs["Artist"].set_fetched_value(ft["artist"])
            self.inputs["Genre"].set_fetched_value(ft.get("genre", ""))
            self.inputs["Track Number"].set_fetched_value(str(ft["track_number"]))
            self.inputs["Disc Number"].set_fetched_value(str(ft["_raw"].get("discNumber", 1)))
        else:
            for inp in self.inputs.values(): inp.set_fetched_value(None)
        self.dataChanged.emit()

    def _download_lyrics(self):
        """
        Fetches lyrics from LRCLIB based on the current artist and title.
        """
        artist = self.inputs["Artist"].get_final_value()
        title = self.inputs["Title"].get_final_value()
        album = self.local_track.get("album", "")
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
            self.dataChanged.emit()
            self.statusMessage.emit(translate("Lyrics downloaded successfully"))
        else:
            self.statusMessage.emit(translate("Lyrics not found"))


class MultiTrackEditWidget(QWidget):
    """View handling mass edits on multiple tracks."""
    fieldApplied = pyqtSignal(str, str)
    coverApplied = pyqtSignal(str)

    def __init__(self, all_artists, all_genres, fmt_raw="MP3", is_mixed_mode=False, all_albums=None, parent=None):
        """
        Initializes the multi-track editor widget for applying bulk changes.
        """
        super().__init__(parent)
        self.all_artists = all_artists
        self.all_genres = all_genres
        self.all_albums = all_albums or []
        self.current_fmt = fmt_raw
        self.is_mixed_mode = is_mixed_mode
        self.inputs = {}
        self._is_loading = False
        self._changed_keys = set()
        self.new_cover_path = None
        self.cached_new_cover_path = None
        self.setupUi()

    def setupUi(self):
        """
        Builds the UI including the cover art editor and batch input fields.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        info_lbl = QLabel(translate("Multi-Edit Mode"))
        info_lbl.setProperty("class", "textHeaderSecondary textColorPrimary")
        layout.addWidget(info_lbl)

        desc_lbl = QLabel(translate("Changes will be applied to all selected tracks. Unmodified fields will keep their original values."))
        desc_lbl.setProperty("class", "textSecondary textColorPrimary")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        layout.addSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.setProperty("class", "tabWidget")

        basic_page = QWidget()
        basic_layout = QHBoxLayout(basic_page)
        basic_layout.setContentsMargins(0, 16, 0, 0)
        basic_layout.setSpacing(24)

        if self.is_mixed_mode:
            column_left = QWidget()
            left_column_layout = QVBoxLayout(column_left)
            left_column_layout.setContentsMargins(0, 0, 0, 0)
            left_column_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            left_column_layout.setSpacing(8)

            cover_select_label = QLabel(translate("Artwork & File Path"))
            cover_select_label.setProperty("class", "textTertiary textColorTertiary")
            left_column_layout.addWidget(cover_select_label)

            self.original_cover_pixmap = QPixmap(256, 256)
            self.original_cover_pixmap.fill(Qt.GlobalColor.transparent)

            self.cover_label = RoundedCoverLabel(self.original_cover_pixmap, 8)
            self.cover_label.setFixedSize(256, 256)

            cover_btns_layout = QHBoxLayout()
            cover_btns_layout.setContentsMargins(0, 0, 0, 0)
            cover_btns_layout.setSpacing(0)

            change_cover_btn = QPushButton(translate("Change..."))
            change_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            change_cover_btn.setProperty("class", "btnText inputBorderMultiLeft")
            change_cover_btn.clicked.connect(self._change_cover)
            cover_btns_layout.addWidget(change_cover_btn, 1)

            self.reset_cover_btn = QPushButton()
            self.reset_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.reset_cover_btn.setProperty("class", "inputBorderMultiMiddle")
            self.reset_cover_btn.setIcon(QIcon(create_svg_icon("assets/control/undo.svg", theme.COLORS["PRIMARY"], QSize(20, 20))))
            self.reset_cover_btn.setIconSize(QSize(20, 20))
            self.reset_cover_btn.clicked.connect(self._reset_cover)
            self.reset_cover_btn.setEnabled(False)
            set_custom_tooltip(self.reset_cover_btn, title = translate("Reset to original cover"))

            self.redo_cover_btn = QPushButton()
            self.redo_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.redo_cover_btn.setProperty("class", "inputBorderMultiRight")
            self.redo_cover_btn.setIcon(QIcon(create_svg_icon("assets/control/redo.svg", theme.COLORS["PRIMARY"], QSize(20, 20))))
            self.redo_cover_btn.setIconSize(QSize(20, 20))
            self.redo_cover_btn.clicked.connect(self._restore_new_cover)
            self.redo_cover_btn.setEnabled(False)
            set_custom_tooltip(self.redo_cover_btn, title = translate("Restore new cover"))

            cover_btns_layout.addWidget(self.reset_cover_btn)
            cover_btns_layout.addWidget(self.redo_cover_btn)

            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(0)
            path_title = QLabel(translate("File Path:"))
            path_title.setWordWrap(True)
            path_title.setProperty("class", "textTertiary textColorTertiary")
            self.lbl_path = QLabel()
            self.lbl_path.setWordWrap(True)
            self.lbl_path.setProperty("class", "textSecondary textColorPrimary")
            info_layout.addWidget(path_title)
            info_layout.addSpacing(8)
            info_layout.addWidget(self.lbl_path)

            left_column_layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)
            left_column_layout.addSpacing(8)
            left_column_layout.addLayout(cover_btns_layout)
            left_column_layout.addSpacing(16)
            left_column_layout.addLayout(info_layout)
            left_column_layout.addStretch()
            basic_layout.addWidget(column_left, 0)

        column_right = QWidget()
        right_column_layout = QVBoxLayout(column_right)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        right_column_layout.setSpacing(8)

        fields_basic = [("Artist", translate("Artist"), self.all_artists)]
        if self.is_mixed_mode:
            fields_basic.extend([("Album", translate("Album"), self.all_albums), ("Album Artist", translate("Album Artist"), self.all_artists), ("Year", translate("Year"), None)])
        fields_basic.extend([("Composer", translate("Composer"), self.all_artists), ("Genre", translate("Genre"), self.all_genres), ("Disc Number", translate("Disc #"), None)])

        for key, label_text, suggestions in fields_basic:
            self._create_field(key, label_text, suggestions, right_column_layout)

        right_column_layout.addStretch()
        basic_layout.addWidget(column_right, 1)
        self.tabs.addTab(basic_page, translate("Basic Tags"))

        adv_page = QWidget()
        adv_layout = QVBoxLayout(adv_page)
        adv_layout.setContentsMargins(0, 16, 0, 0)
        adv_layout.setSpacing(0)

        adv_scroll = StyledScrollArea()
        adv_scroll.setWidgetResizable(True)
        adv_scroll.setFrameShape(QFrame.Shape.NoFrame)
        adv_scroll.setProperty("class", "backgroundPrimary")

        adv_content = QWidget()
        adv_content.setProperty("class", "backgroundPrimary")
        adv_content_layout = QVBoxLayout(adv_content)
        adv_content_layout.setContentsMargins(0, 0, 16, 0)
        adv_content_layout.setSpacing(8)

        fields_adv = [
            ("original_year", translate("Original Release Year")), ("comment", translate("Comment")),
            ("copyright", translate("Copyright")), ("source_url", translate("Source URL")),
            ("user_url", translate("User URL")), ("bpm", translate("BPM")), ("isrc", translate("ISRC")),
            ("media_type", translate("Media Type")), ("encoded_by", translate("Encoded By")), ("encoder_settings", translate("Encoder Settings")),
        ]

        fmt_key = get_format_key(self.current_fmt)
        allowed = AdvancedMetadataWidget.SUPPORTED_FIELDS.get(fmt_key, "all")

        for key, label_text in fields_adv:
            if allowed == "all" or key in allowed:
                self._create_field(key, label_text, None, adv_content_layout)

        adv_content_layout.addStretch()
        adv_scroll.setWidget(adv_content)
        adv_layout.addWidget(adv_scroll)
        self.tabs.addTab(adv_page, translate("Advanced Tags"))
        layout.addWidget(self.tabs)

    def _create_field(self, key, label_text, suggestions, parent_layout):
        """
        Helper method to create a labeled input field with optional auto-completion.
        """
        field_layout = QVBoxLayout()
        field_layout.setSpacing(8)
        lbl = QLabel(label_text)
        lbl.setProperty("class", "textTertiary textColorTertiary")
        apply_field_tooltip(lbl, key, self.current_fmt)
        lbl.setCursor(Qt.CursorShape.WhatsThisCursor)

        inp = MetadataMergeControl("", border_style="inputBorderSinglePadding")
        if suggestions:
            completer = GapCompleter(suggestions, inp, gap=4)
            popup = completer.popup()
            popup.setProperty("class", "listWidget")
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            if inp.lineEdit(): inp.lineEdit().setCompleter(completer)

        inp.editTextChanged.connect(lambda text, k=key, w=inp: self._on_field_changed(k, w))
        inp.currentIndexChanged.connect(lambda idx, k=key, w=inp: self._on_field_changed(k, w))

        self.inputs[key] = inp
        field_layout.addWidget(lbl)
        field_layout.addWidget(inp)
        parent_layout.addLayout(field_layout)

    def _update_cover_buttons(self):
        """
        Updates the enabled state of the undo/redo cover art buttons.
        """
        self.reset_cover_btn.setEnabled(self.new_cover_path is not None)
        can_redo = (self.new_cover_path is None) and (self.cached_new_cover_path is not None)
        self.redo_cover_btn.setEnabled(can_redo)

    def _change_cover(self):
        """
        Opens a file dialog for the user to select a new cover image for all selected tracks.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, translate("Select New Cover"), "", translate("Image Files (*.png *.jpg *.jpeg)"))
        if file_path: self._apply_new_cover(file_path)

    def _apply_new_cover(self, path):
        """
        Applies the selected cover image to the UI and emits the change.
        """
        self.new_cover_path = path
        self.cached_new_cover_path = path
        self.cover_label.setPixmap(QPixmap(path).scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self._update_cover_buttons()
        self.coverApplied.emit(path)

    def _reset_cover(self):
        """
        Reverts the cover art to its original image across all selected tracks.
        """
        self.cover_label.setPixmap(self.original_cover_pixmap)
        self.new_cover_path = None
        self._update_cover_buttons()
        self.coverApplied.emit("__RESET_MIXED__")

    def _restore_new_cover(self):
        """
        Re-applies the user's newly selected cover image.
        """
        if self.cached_new_cover_path and os.path.exists(self.cached_new_cover_path):
            self._apply_new_cover(self.cached_new_cover_path)

    def set_common_cover(self, pixmap):
        """
        Sets a common cover image if all selected tracks share the same artwork.
        """
        if self.is_mixed_mode and hasattr(self, 'cover_label'):
            self.original_cover_pixmap = pixmap.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.cover_label.setPixmap(self.original_cover_pixmap)
            self.new_cover_path = None
            self.cached_new_cover_path = None
            self._update_cover_buttons()

    def load_selection(self, selected_indices, batch_detail_widgets, all_tracks, pending_batch_edits):
        """
        Loads the combined metadata for the currently selected tracks, showing placeholders where they diverge.
        """
        self._is_loading = True
        self._changed_keys.clear()

        if hasattr(self, 'lbl_path'):
            paths = [all_tracks[idx]["path"] for idx in selected_indices]
            if paths:
                common_dir = os.path.dirname(paths[0])
                for p in paths[1:]:
                    if os.path.dirname(p) != common_dir:
                        common_dir = translate("<Multiple directories>")
                        break
                self.lbl_path.setText(common_dir)
            else:
                self.lbl_path.setText("")

        mixed_placeholder = translate("<Different Values>")

        for key, inp in self.inputs.items():
            current_values, original_values = set(), set()
            for idx in selected_indices:
                widget = batch_detail_widgets[idx]
                if widget is not None:
                    source_dict = widget.inputs if key in widget.inputs else widget.advanced_widget.inputs
                    if key in source_dict:
                        current_values.add("" if source_dict[key].get_final_value() is None else str(source_dict[key].get_final_value()).strip())
                        original_values.add("" if source_dict[key].current_val is None else str(source_dict[key].current_val).strip())
                else:
                    track = all_tracks[idx]
                    orig_val = ""
                    if key == "Artist":
                        artists = track.get("artists", [])
                        if not artists and track.get("artist"): artists = [track.get("artist")]
                        orig_val = "; ".join([x for x in artists if x]) if isinstance(artists, list) else str(artists)
                    elif key == "Genre":
                        g = track.get("genre", [])
                        orig_val = "; ".join([x for x in g if x]) if isinstance(g, list) else str(g)
                    elif key == "Album Artist": orig_val = track.get("album_artist", "")
                    elif key == "Disc Number": orig_val = str(track.get("discnumber", ""))
                    elif key == "Track Number": orig_val = str(track.get("tracknumber", ""))
                    else: orig_val = str(track.get(key.lower(), ""))

                    orig_str = str(orig_val).strip()
                    original_values.add(orig_str)

                    pending = pending_batch_edits.get(idx, {})
                    if key in pending:
                        current_values.add(str(pending[key]).strip())
                    else:
                        current_values.add(orig_str)

                if len(current_values) > 50: break

            final_display_val, placeholder_text = "", ""
            if len(current_values) == 1: final_display_val = list(current_values)[0]
            elif len(current_values) > 1: placeholder_text = mixed_placeholder

            base_val = list(original_values)[0] if len(original_values) == 1 else ""

            inp.update_current_value(base_val)
            inp.blockSignals(True)
            inp.clear()

            combo_items = sorted([v for v in current_values if v])
            if combo_items:
                inp.addItem("")
                inp.setItemData(0, "", Qt.ItemDataRole.UserRole)
                for i, text_val in enumerate(combo_items, start=1):
                    inp.addItem(text_val)
                    inp.setItemData(i, text_val, Qt.ItemDataRole.UserRole)

            inp.setCurrentText(final_display_val)
            if inp.lineEdit():
                inp.lineEdit().setText(final_display_val)
                inp.lineEdit().setPlaceholderText(placeholder_text)
                inp.lineEdit().setCursorPosition(0)

            inp.blockSignals(False)
            inp._update_style()

            if final_display_val != base_val:
                self._changed_keys.add(key)

        self._is_loading = False

    def _on_field_changed(self, key, widget):
        """
        Emits a signal when a batch field is modified by the user.
        """
        if self._is_loading: return
        current_text = "" if widget.get_final_value() is None else str(widget.get_final_value())
        original_text = "" if widget.current_val is None else str(widget.current_val)

        if current_text != original_text:
            self._changed_keys.add(key)
            self.fieldApplied.emit(key, current_text)
        else:
            if key in self._changed_keys:
                self._changed_keys.remove(key)
                if original_text == "" and widget.lineEdit() and widget.lineEdit().placeholderText():
                    self.fieldApplied.emit(key, "__RESET_MIXED__")
                else:
                    self.fieldApplied.emit(key, original_text)