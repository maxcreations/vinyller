"""
Vinyller — Mini mode widget
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

from functools import partial

from PyQt6.QtCore import (
    pyqtSignal, QEvent, QPoint, QSize, Qt,
    QRect
)
from PyQt6.QtGui import (
    QIcon,
    QPixmap, QAction, QShortcut, QKeySequence, QPainter, QColor
)
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QStackedWidget, QListWidgetItem, QSizePolicy, QApplication
)

from src.core.hotkey_manager import HotkeyManager
from src.ui.custom_base_widgets import TranslucentMenu, StyledScrollArea, StyledLabel, set_custom_tooltip
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ClickableLabel, ClickableProgressBar, ElidedLabel, RoundedCoverLabel
)
from src.ui.custom_lists import QueueWidget, QueueDelegate, CustomRoles
from src.utils import theme
from src.utils.constants import ArtistSource
from src.utils.constants_linux import IS_LINUX
from src.utils.utils import (
    create_svg_icon, resource_path
)
from src.utils.utils_translator import translate


class QueueLyricsPopup(QWidget):
    """
    Separate frameless floating window for Queue and Lyrics.
    Acts as a thin UI client; animation and state are driven by MiniVinny.
    """

    def __init__(self, parent_window, main_window):
        """
        Initializes the frameless floating window for displaying the playback queue and lyrics.

        :param parent_window: The parent MiniVinny widget.
        :param main_window: The main application window reference.
        """
        super().__init__()
        self.parent_window = parent_window
        self.mw = main_window

        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.lyrics_base_font_size = 12
        self.lyrics_font_level = 0
        self.max_lyrics_font_level = 4

        self._setup_ui()
        self._connect_internal_signals()

        self.setMouseTracking(True)

        self.setMinimumHeight(200)
        self.resize(552, 332)

        self._is_resizing = False
        self._resize_edge = None
        self._mouse_press_global_y = 0
        self._mouse_press_geometry = QRect()
        self.MARGIN_TOP = 20
        self.MARGIN_BOTTOM = 20
        self.RESIZE_TOLERANCE = 20

    def _setup_ui(self):
        """Sets up the UI elements for the queue and lyrics popup."""
        self.window_layout = QVBoxLayout(self)
        self.window_layout.setContentsMargins(20, 20, 20, 20)
        self.window_layout.setSpacing(0)

        self.main_frame = QFrame(self)
        self.main_frame.setProperty("class", "miniVinny")
        self.window_layout.addWidget(self.main_frame)

        self.main_vbox = QVBoxLayout(self.main_frame)
        self.main_vbox.setContentsMargins(0, 0, 0, 0)
        self.main_vbox.setSpacing(0)

        self.stack_container = QStackedWidget()

        self.queue_page = QWidget()
        queue_layout = QVBoxLayout(self.queue_page)
        queue_layout.setContentsMargins(8, 0, 8, 0)
        queue_layout.setSpacing(8)

        self.mini_queue_widget = QueueWidget(self.mw)
        delegate = QueueDelegate(self.mini_queue_widget)
        delegate.set_compact_mode(True)
        delegate.set_hide_artist_in_compact(False)
        self.mini_queue_widget.setItemDelegate(delegate)
        self.mini_queue_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.mini_queue_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        queue_layout.addWidget(self.mini_queue_widget)

        self.stack_container.addWidget(self.queue_page)

        self.lyrics_page = QWidget()
        lyrics_layout = QVBoxLayout(self.lyrics_page)
        lyrics_layout.setContentsMargins(0, 0, 0, 0)
        lyrics_layout.setSpacing(0)

        l_header_widget = QWidget()
        l_header_widget.setProperty("class", "borderBottom")
        l_header_layout = QHBoxLayout(l_header_widget)
        l_header_layout.setContentsMargins(8, 8, 8, 8)
        l_header_layout.setSpacing(8)

        self.btn_lyrics_back = QPushButton()
        self.btn_lyrics_back.setIcon(
            create_svg_icon("assets/control/arrow_back.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_lyrics_back.setIconSize(QSize(24, 24))
        self.btn_lyrics_back.setFixedSize(36, 36)
        self.btn_lyrics_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lyrics_back.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_lyrics_back,
            title = translate("Back"),
        )
        apply_button_opacity_effect(self.btn_lyrics_back)
        l_header_layout.addWidget(self.btn_lyrics_back)

        l_title = QLabel(translate("Lyrics"))
        l_title.setProperty("class", "textHeaderSecondary textColorPrimary")
        l_header_layout.addWidget(l_title, 1)

        self.btn_lyrics_dec = QPushButton()
        self.btn_lyrics_dec.setIcon(
            create_svg_icon("assets/control/text_size_smaller.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_lyrics_dec.setIconSize(QSize(24, 24))
        self.btn_lyrics_dec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lyrics_dec.setFixedSize(36, 36)
        self.btn_lyrics_dec.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_lyrics_dec,
            title = translate("Decrease font size"),
        )
        apply_button_opacity_effect(self.btn_lyrics_dec)
        l_header_layout.addWidget(self.btn_lyrics_dec)

        self.btn_lyrics_inc = QPushButton()
        self.btn_lyrics_inc.setIcon(
            create_svg_icon("assets/control/text_size_bigger.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_lyrics_inc.setIconSize(QSize(24, 24))
        self.btn_lyrics_inc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lyrics_inc.setFixedSize(36, 36)
        self.btn_lyrics_inc.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_lyrics_inc,
            title = translate("Increase font size"),
        )
        apply_button_opacity_effect(self.btn_lyrics_inc)
        l_header_layout.addWidget(self.btn_lyrics_inc)

        lyrics_layout.addWidget(l_header_widget)

        self.mini_lyrics_scroll = StyledScrollArea()
        self.mini_lyrics_scroll.setStyleSheet("background-color: transparent;")
        self.mini_lyrics_scroll.setWidgetResizable(True)
        self.mini_lyrics_scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(16, 16, 16, 16)

        self.mini_lyrics_label = StyledLabel(translate("Lyrics not found"))
        self.mini_lyrics_label.setProperty("class", "textColorPrimary")
        self.mini_lyrics_label.setWordWrap(True)
        self.mini_lyrics_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.mini_lyrics_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.mini_lyrics_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_layout.addWidget(self.mini_lyrics_label)
        scroll_layout.addStretch()
        self.mini_lyrics_scroll.setWidget(scroll_widget)

        lyrics_layout.addWidget(self.mini_lyrics_scroll)
        self.stack_container.addWidget(self.lyrics_page)

        self.main_vbox.addWidget(self.stack_container)
        self._update_lyrics_font_ui()

    def _connect_internal_signals(self):
        """Connects signals for lyrics page navigation and formatting actions."""
        self.btn_lyrics_dec.clicked.connect(lambda: self._change_lyrics_font_size(-1))
        self.btn_lyrics_inc.clicked.connect(lambda: self._change_lyrics_font_size(1))
        self.btn_lyrics_back.clicked.connect(self.hide_lyrics)
        self.mini_queue_widget.lyricsClicked.connect(self.show_lyrics)

    def paintEvent(self, event):
        """Handles custom painting of the popup window to apply a drop shadow effect."""
        if not self.isActiveWindow():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg_rect = self.rect().marginsRemoved(self.layout().contentsMargins())
        shadow_color = QColor(0, 0, 0)
        layers = 20
        start_alpha = 6
        shadow_shift_y = 4

        for i in range(layers):
            progress = i / layers
            alpha = int(start_alpha * ((1.0 - progress) ** 2))
            if alpha == 0: break
            shadow_color.setAlpha(alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            shadow_rect = bg_rect.adjusted(-(i + 1), -(i + 1), (i + 1), (i + 1))
            shadow_rect.translate(0, shadow_shift_y)
            radius = 6 + i
            painter.drawRoundedRect(shadow_rect, radius, radius)
        painter.end()

    def show_lyrics(self, track_data):
        """Displays the lyrics view with text populated from the current track data."""
        if not track_data:
            lyrics = translate("Lyrics not found")
        else:
            lyrics = track_data.get("lyrics")
            if not lyrics:
                lyrics = translate("Lyrics not found")

        self.mini_lyrics_label.setText(lyrics.replace("\n", "<br>"))
        self.mini_lyrics_scroll.verticalScrollBar().setValue(0)
        self.stack_container.setCurrentWidget(self.lyrics_page)

    def hide_lyrics(self):
        """Switches from the lyrics view back to the queue view and highlights the active track."""
        self.stack_container.setCurrentWidget(self.queue_page)
        self.parent_window._highlight_current_track()

    def _change_lyrics_font_size(self, delta):
        """Adjusts the lyrics font size level based on the provided delta value."""
        new_level = self.lyrics_font_level + delta
        if 0 <= new_level <= self.max_lyrics_font_level:
            self.lyrics_font_level = new_level
            self._update_lyrics_font_ui()

    def _update_lyrics_font_ui(self):
        """Updates the lyrics label style with the current font size and sets button enabled states."""
        new_size = self.lyrics_base_font_size + (self.lyrics_font_level * 2)
        self.mini_lyrics_label.setStyleSheet(f"font-size: {new_size}px;")
        self.btn_lyrics_dec.setEnabled(self.lyrics_font_level > 0)
        self.btn_lyrics_inc.setEnabled(self.lyrics_font_level < self.max_lyrics_font_level)

    def enterEvent(self, event):
        """Handles cursor entering the widget space to update window opacity."""
        self.parent_window._update_opacity()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handles cursor leaving the widget space to update window opacity."""
        self.parent_window._update_opacity()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        """Handles window resizing via mouse drag movements on the edges."""
        if self._is_resizing:
            delta_y = int(event.globalPosition().y() - self._mouse_press_global_y)
            geom = self._mouse_press_geometry

            if self._resize_edge == 'bottom':
                new_height = geom.height() + delta_y
                if new_height >= self.minimumHeight():
                    self.resize(geom.width(), new_height)
            elif self._resize_edge == 'top':
                new_height = geom.height() - delta_y
                if new_height >= self.minimumHeight():
                    self.setGeometry(geom.x(), geom.y() + delta_y, geom.width(), new_height)

            event.accept()
            return

        pos_y = event.pos().y()
        expanded_upwards = getattr(self.parent_window, '_expanded_upwards', False)

        if not expanded_upwards and abs(pos_y - (self.height() - self.MARGIN_BOTTOM)) <= self.RESIZE_TOLERANCE:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self._hover_edge = 'bottom'
        elif expanded_upwards and abs(pos_y - self.MARGIN_TOP) <= self.RESIZE_TOLERANCE:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self._hover_edge = 'top'
        else:
            self.unsetCursor()
            self._hover_edge = None

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        """Initiates resizing if the mouse clicks on the resizable edges."""
        if event.button() == Qt.MouseButton.LeftButton and hasattr(self, '_hover_edge') and self._hover_edge:
            self._is_resizing = True
            self._resize_edge = self._hover_edge
            self._mouse_press_global_y = event.globalPosition().y()
            self._mouse_press_geometry = self.geometry()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Finalizes the resize action when the left mouse button is released."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_resizing:
            self._is_resizing = False
            self._resize_edge = None
            self.parent_window._update_popup_position()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class MiniVinny(QWidget):
    """
    Mini frameless widget that stays always on top.
    Functions strictly as a thin client. Data and state must be pushed to it via set_* methods.
    """
    restore_requested = pyqtSignal()

    def __init__(self, main_window, parent = None):
        """
        Initializes the MiniVinny widget, setting up its frameless UI, drop zones, and state variables.

        :param main_window: The main application window reference.
        :param parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.mw = main_window
        self.setWindowIcon(QIcon(resource_path("assets/logo/app_icon.png")))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos = None
        self._is_queue_expanded = False
        self._expanded_upwards = False
        self._is_playing = False
        self._is_muted = False
        self._current_index = -1
        self._current_track_data = {}

        self.queue_popup = QueueLyricsPopup(self, self.mw)

        self.setFixedWidth(552)
        self.setFixedHeight(104)

        self.setAcceptDrops(True)
        self.active_drop_zone = -1

        self._setup_ui()
        self._setup_drop_zones()
        self._connect_signals()

    def _setup_ui(self):
        """Sets up the layout, buttons, and track information elements for the Mini Vinny."""
        self.window_layout = QVBoxLayout(self)
        self.window_layout.setContentsMargins(20, 20, 20, 20)
        self.window_layout.setSpacing(0)

        self.main_frame = QFrame(self)
        self.main_frame.setContentsMargins(0, 0, 0, 0)
        self.main_frame.setProperty("class", "miniVinny")
        self.window_layout.addWidget(self.main_frame)

        self.main_vbox = QVBoxLayout(self.main_frame)
        self.main_vbox.setContentsMargins(0, 0, 0, 0)
        self.main_vbox.setSpacing(0)

        self.top_controls_widget = QWidget()
        self.top_controls_widget.setFixedHeight(64)
        self.top_controls_widget.setContentsMargins(0, 0, 0, 0)

        layout = QHBoxLayout(self.top_controls_widget)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.cover_label = RoundedCoverLabel("", 4)
        self.cover_label.setFixedSize(48, 48)
        self.cover_label.setProperty("class", "coverImage")
        missing_cover_path = theme.COLORS.get("MISSING_COVER", "assets/view/missing_cover.png")
        self.cover_label.setPixmap(QIcon(resource_path(missing_cover_path)).pixmap(48, 48))

        layout.addWidget(self.cover_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        self.title_label = ElidedLabel("")
        self.title_label.setContentsMargins(0, 0, 0, 0)
        self.title_label.setProperty("class", "textPrimary textColorPrimary")
        text_layout.addWidget(self.title_label)

        self.artist_info_layout = QHBoxLayout()
        self.artist_info_layout.setContentsMargins(0, 0, 0, 0)
        self.artist_info_layout.setSpacing(0)
        self.artist_label = ClickableLabel("", None, self)
        self.artist_label.setContentsMargins(0, 0, 0, 0)
        self.artist_label.setProperty("class", "textSecondary textColorTertiary")
        self.artist_info_layout.addWidget(self.artist_label)
        self.artist_info_layout.addStretch()
        text_layout.addLayout(self.artist_info_layout)

        self.album_info_layout = QHBoxLayout()
        self.album_info_layout.setContentsMargins(0, 0, 0, 0)
        self.album_info_layout.setSpacing(0)
        self.year_label = ClickableLabel("", None, self)
        self.year_label.setProperty("class", "textSecondary textColorTertiary")
        self.year_label.setContentsMargins(0, 0, 0, 0)
        self.year_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.comma_label = QLabel(", ", self)
        self.comma_label.setContentsMargins(1, 0, 0, 0)
        self.comma_label.setProperty("class", "textSecondary textColorTertiary")
        self.comma_label.setVisible(False)
        self.album_label = ClickableLabel("", None, self)
        self.album_label.setProperty("class", "textSecondary textColorTertiary")
        self.album_label.setContentsMargins(0, 0, 0, 0)

        self.album_info_layout.addWidget(self.year_label)
        self.album_info_layout.addWidget(self.comma_label)
        self.album_info_layout.addWidget(self.album_label, 1)

        text_layout.addLayout(self.album_info_layout)
        layout.addLayout(text_layout)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        track_control_layout = QVBoxLayout()
        track_control_layout.setContentsMargins(0, 0, 0, 0)
        track_control_layout.setSpacing(4)
        track_control_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        track_btns_layout = QHBoxLayout()
        track_btns_layout.setContentsMargins(0, 0, 0, 0)
        track_btns_layout.setSpacing(8)
        track_btns_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.btn_fav = QPushButton()
        self.btn_fav.setIcon(self.mw.favorite_icon)
        self.btn_fav.setFixedSize(36, 36)
        self.btn_fav.setIconSize(QSize(24, 24))
        self.btn_fav.setProperty("class", "btnTool")
        self.btn_fav.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(self.btn_fav)
        track_btns_layout.addWidget(self.btn_fav)

        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(create_svg_icon("assets/control/skip_prev.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_prev.setIconSize(QSize(24, 24))
        self.btn_prev.setFixedSize(36, 36)
        set_custom_tooltip(
            self.btn_prev,
            title = translate("Previous track"),
            hotkey = HotkeyManager.get_hotkey_str("prev_track")
        )
        self.btn_prev.setProperty("class", "btnTool")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(self.btn_prev)
        track_btns_layout.addWidget(self.btn_prev)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(create_svg_icon("assets/control/play.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_play.setIconSize(QSize(24, 24))
        self.btn_play.setFixedSize(36, 36)
        set_custom_tooltip(
            self.btn_play,
            title = translate("Play"),
            hotkey = HotkeyManager.get_hotkey_str("play_pause")
        )
        self.btn_play.setProperty("class", "btnTool")
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(self.btn_play)
        track_btns_layout.addWidget(self.btn_play)

        self.btn_next = QPushButton()
        self.btn_next.setIcon(create_svg_icon("assets/control/skip_next.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_next.setIconSize(QSize(24, 24))
        self.btn_next.setFixedSize(36, 36)
        set_custom_tooltip(
            self.btn_next,
            title = translate("Next track"),
            hotkey = HotkeyManager.get_hotkey_str("next_track")
        )
        self.btn_next.setProperty("class", "btnTool")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(self.btn_next)
        track_btns_layout.addWidget(self.btn_next)

        self.btn_volume = QPushButton()
        self.btn_volume.setIconSize(QSize(24, 24))
        self.btn_volume.setFixedSize(36, 36)
        self.btn_volume.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_volume,
            title = translate("Volume"),
        )
        self.btn_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_volume.setCheckable(True)
        apply_button_opacity_effect(self.btn_volume)
        track_btns_layout.addWidget(self.btn_volume)

        self.btn_queue = QPushButton()
        self.btn_queue.setIcon(
            create_svg_icon("assets/control/playback_queue.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_queue.setIconSize(QSize(24, 24))
        self.btn_queue.setFixedSize(36, 36)
        self.btn_queue.setProperty("class", "btnTool")
        set_custom_tooltip(
            self.btn_queue,
            title = translate("Playback Queue"),
        )
        self.btn_queue.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(self.btn_queue)
        track_btns_layout.addWidget(self.btn_queue)

        track_control_layout.addLayout(track_btns_layout)

        self.progress_slider = ClickableProgressBar(Qt.Orientation.Horizontal, self)
        self.progress_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress_slider.setFixedHeight(8)

        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.addWidget(self.progress_slider)

        track_control_layout.addLayout(progress_layout)
        controls_layout.addLayout(track_control_layout)
        layout.addLayout(controls_layout)

        separator = QWidget()
        separator.setFixedSize(1, 48)
        separator.setProperty("class", "borderRight")
        layout.addWidget(separator)

        self.btn_expand = QPushButton()
        self.btn_expand.setIcon(
            create_svg_icon("assets/control/view_normal.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_expand.setIconSize(QSize(24, 24))
        self.btn_expand.setFixedSize(36, 36)
        set_custom_tooltip(
            self.btn_expand,
            title = translate("Expand"),
        )
        self.btn_expand.setProperty("class", "btnTool")
        self.btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button_opacity_effect(self.btn_expand)
        layout.addWidget(self.btn_expand)



        self.main_vbox.addWidget(self.top_controls_widget)



    def paintEvent(self, event):
        """Paints a custom drop shadow directly on the widget to give it depth."""
        if not self.isActiveWindow():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg_rect = self.rect().marginsRemoved(self.layout().contentsMargins())
        shadow_color = QColor(0, 0, 0)
        layers = 20
        start_alpha = 6
        shadow_shift_y = 4

        for i in range(layers):
            progress = i / layers
            alpha = int(start_alpha * ((1.0 - progress) ** 2))
            if alpha == 0: break
            shadow_color.setAlpha(alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            shadow_rect = bg_rect.adjusted(-(i + 1), -(i + 1), (i + 1), (i + 1))
            shadow_rect.translate(0, shadow_shift_y)
            radius = 6 + i
            painter.drawRoundedRect(shadow_rect, radius, radius)
        painter.end()

    def _connect_signals(self):
        """Connects playback controls, user interface elements, and queue actions to their corresponding methods."""
        self.btn_expand.clicked.connect(self.restore_requested.emit)
        self.btn_prev.clicked.connect(self.mw.player.previous)
        self.btn_play.clicked.connect(self.mw.player_controller.toggle_play_pause)
        self.btn_next.clicked.connect(self.mw.player.next)

        self.btn_fav.clicked.connect(lambda _: self.mw.control_panel.favorite_clicked.emit())
        self.btn_queue.clicked.connect(self._toggle_queue)
        self.btn_volume.clicked.connect(self._toggle_volume_popup)

        self.progress_slider.sliderReleased.connect(
            lambda: self.mw.player.set_position(self.progress_slider.value())
        )

        qw = self.queue_popup.mini_queue_widget
        qw.itemDelegate().playButtonClicked.connect(self.mw.player_controller.play_from_queue_action)
        qw.itemDoubleClicked.connect(self.mw.player_controller.play_from_queue_double_click)
        qw.playActionRequested.connect(self.mw.player_controller.play_from_queue_action)
        qw.customContextMenuRequested.connect(
            lambda pos: self.mw.action_handler.show_queue_context_menu(pos, self.queue_popup.mini_queue_widget)
        )
        qw.tracksDropped.connect(self.mw.action_handler.handle_tracks_dropped)
        qw.orderChanged.connect(
            lambda: self.mw.action_handler.handle_queue_reordered(self.queue_popup.mini_queue_widget)
        )
        qw.artistClicked.connect(self._on_artist_action_triggered)

        self.artist_label.clicked.connect(self._on_artist_clicked)
        self.album_label.clicked.connect(self._on_album_clicked)
        self.year_label.clicked.connect(self._on_year_clicked)

        self._setup_hotkeys()


    def set_track_data(self, track_data: dict, cover_pixmap: QPixmap = None, is_favorite: bool = False,
                       nav_artist_data = None, nav_album_data = None, nav_year_data = None):
        """Pushed from controller to populate track metadata, cover art, and relevant tooltip states."""
        self._current_track_data = track_data if track_data else {}
        self._nav_artist_data = nav_artist_data
        self._nav_album_data = nav_album_data
        self._nav_year_data = nav_year_data

        self.artist_label.data = nav_artist_data
        self.album_label.data = nav_album_data
        self.year_label.data = nav_year_data

        if not self._current_track_data:
            self.title_label.setText("")
            self.artist_label.setText("")
            self.album_label.setText("")
            self.year_label.setText("")
            self.comma_label.setVisible(False)

            missing_cover_path = theme.COLORS.get("MISSING_COVER", "assets/view/missing_cover.png")
            self.cover_label.setPixmap(QIcon(resource_path(missing_cover_path)).pixmap(48, 48))

            self.progress_slider.setValue(0)
            self.progress_slider.setEnabled(False)
            return

        title = self._current_track_data.get("title", "")
        self.title_label.setText(title)

        artists = self._current_track_data.get("artists", [])
        artist_text = ", ".join(artists) if artists else self._current_track_data.get("artist", translate("Unknown"))
        self.artist_label.setText(artist_text)

        if hasattr(self.mw, 'artist_source_tag') and self.mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
            target_artist = self._current_track_data.get("album_artist") or self._current_track_data.get(
                "artist") or artist_text
            set_custom_tooltip(
                self.artist_label,
                title = translate("Go to Album Artist"),
                text = target_artist
            )
        else:
            set_custom_tooltip(
                self.artist_label,
                title = translate("Go to artist"),
                text = artist_text
            )

        album = self._current_track_data.get("album", translate("Unknown Album"))
        self.album_label.setText(album)
        set_custom_tooltip(
            self.album_label,
            title = translate("Go to Album"),
            text = album
        )
        year = str(self._current_track_data.get("year", ""))
        self.year_label.setText(year)
        if year:
            set_custom_tooltip(
                self.year_label,
                title = translate("Go to year"),
                text = year
            )
        show_comma = bool(year) and bool(album)
        self.comma_label.setVisible(show_comma)
        self.year_label.setVisible(bool(year))

        if cover_pixmap and not cover_pixmap.isNull():
            self.cover_label.setPixmap(
                cover_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation))
        else:
            self.cover_label.setPixmap(QPixmap())

        self.set_favorite_state(is_favorite = is_favorite, is_enabled = True)

    def set_playback_state(self, is_playing: bool):
        """Pushed from controller when playback pauses/resumes."""
        self._is_playing = is_playing
        icon_name = "pause.svg" if is_playing else "play.svg"
        self.btn_play.setIcon(create_svg_icon(f"assets/control/{icon_name}", theme.COLORS["PRIMARY"], QSize(24, 24)))
        if is_playing:
            set_custom_tooltip(
                self.btn_play,
                title = translate("Pause"),
                hotkey = HotkeyManager.get_hotkey_str("play_pause")
            )
        else:
            set_custom_tooltip(
                self.btn_play,
                title = translate("Play"),
                hotkey = HotkeyManager.get_hotkey_str("play_pause")
            )
        self._highlight_current_track()

    def set_queue(self, tracks: list, current_index: int):
        """Pushed from controller when queue is reordered, added to, or cleared."""
        self._current_index = current_index
        qw = self.queue_popup.mini_queue_widget
        qw.clear()

        if not tracks:
            return

        for track in tracks:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, track)
            item.setData(CustomRoles.IsCurrentRole, False)
            item.setData(CustomRoles.IsPlayingRole, False)
            qw.addItem(item)

        self._highlight_current_track()

    def set_current_index(self, current_index: int):
        """Pushed from controller when moving to next/prev track without altering queue list."""
        self._current_index = current_index
        self._highlight_current_track()

    def set_volume_state(self, volume: int, is_muted: bool):
        """Pushed from controller when volume changes or is muted."""
        self._is_muted = is_muted
        self.btn_volume.setChecked(is_muted)

        if is_muted or volume == 0:
            icon = create_svg_icon("assets/control/volume_off.svg", theme.COLORS["ACCENT"], QSize(24, 24))
        else:
            icon = create_svg_icon("assets/control/volume_on.svg", theme.COLORS["PRIMARY"], QSize(24, 24))
        self.btn_volume.setIcon(icon)

    def set_favorite_state(self, is_favorite: bool, is_enabled: bool = True):
        """Pushed from controller when favorite status changes."""
        self.btn_fav.setEnabled(is_enabled)
        self.btn_fav.setIcon(self.mw.favorite_filled_icon if is_favorite else self.mw.favorite_icon)
        self.btn_fav.setProperty("active", is_favorite)
        if is_favorite:
            set_custom_tooltip(
                self.btn_fav,
                title = translate("Remove from favorites"),
                hotkey = HotkeyManager.get_hotkey_str("favorite")
            )
        else:
            set_custom_tooltip(
                self.btn_fav,
                title = translate("Add to favorites"),
                hotkey = HotkeyManager.get_hotkey_str("favorite")
            )
        if self.btn_fav.graphicsEffect():
            self.btn_fav.graphicsEffect().setEnabled(not is_favorite)
        self.style().polish(self.btn_fav)

    def set_animation_frame(self, frame: int):
        """Pushed from the main window timer to advance the equalizer animation."""
        if not self.queue_popup.isVisible():
            return
        delegate = self.queue_popup.mini_queue_widget.itemDelegate()
        if delegate and hasattr(delegate, 'set_animation_frame'):
            delegate.set_animation_frame(frame)
            if self._is_playing:
                self.queue_popup.mini_queue_widget.viewport().update()

    def set_position(self, position_val: int):
        """Pushed from controller to update progress bar."""
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(position_val)
        self.progress_slider.blockSignals(False)

    def set_duration(self, duration_val: int):
        """Pushed from controller to update progress bar range."""
        self.progress_slider.setRange(0, duration_val)
        self.progress_slider.setEnabled(duration_val > 0)


    def _highlight_current_track(self):
        """Applies highlighting (visual styles and scrolling) to the currently active track in the queue list."""
        qw = self.queue_popup.mini_queue_widget
        for i in range(qw.count()):
            item = qw.item(i)
            is_current = (i == self._current_index)
            item.setData(CustomRoles.IsCurrentRole, is_current)
            item.setData(CustomRoles.IsPlayingRole, is_current and self._is_playing)

            if is_current and self._is_queue_expanded and self.queue_popup.stack_container.currentWidget() == self.queue_popup.queue_page:
                qw.scrollToItem(item)

        qw.viewport().update()

    def _toggle_queue(self):
        """Toggles the visibility state of the external playback queue window and calculates positioning logic."""
        if self._is_queue_expanded:
            self._is_queue_expanded = False
            self.update_queue_toggle_button(False)
            self.queue_popup.hide()
        else:
            self._is_queue_expanded = True
            self.update_queue_toggle_button(True)

            screen = self.screen()
            if screen:
                screen_geom = screen.availableGeometry()
                space_below = screen_geom.bottom() - self.geometry().bottom()
                self._expanded_upwards = space_below < self.queue_popup.height()
            else:
                self._expanded_upwards = False

            self._update_popup_position()
            self.queue_popup.show()

            if self.queue_popup.stack_container.currentWidget() == self.queue_popup.queue_page:
                self._highlight_current_track()

    def _update_popup_position(self):
        """Determines and updates the correct placement of the queue popup relative to the Mini Vinny."""
        gap = 8
        if self._expanded_upwards:
            popup_y = self.y() - self.queue_popup.height() + 32 - gap
        else:
            popup_y = self.y() + 64 + gap

        self.queue_popup.move(self.x(), popup_y)

    def update_queue_toggle_button(self, is_visible):
        """Updates the styling and tooltip of the queue toggle button based on visibility."""
        color = theme.COLORS["ACCENT"] if is_visible else theme.COLORS["PRIMARY"]
        self.btn_queue.setIcon(
            create_svg_icon("assets/control/playback_queue.svg", color, QSize(24, 24))
        )
        if is_visible:
            set_custom_tooltip(
                self.btn_queue,
                title = translate("Hide Playback Queue"),
            )
        else:
            set_custom_tooltip(
                self.btn_queue,
                title = translate("Show Playback Queue"),
            )
        self.btn_queue.setProperty("active", is_visible)

        if effect := self.btn_queue.graphicsEffect():
            target_opacity = 1.0 if (is_visible or self.btn_queue.underMouse()) else 0.7
            effect.setOpacity(target_opacity)

        self.style().unpolish(self.btn_queue)
        self.style().polish(self.btn_queue)

    def _on_album_clicked(self, *args):
        """Handles a click event on the album name, requesting view restoration and sending the navigation event."""
        if self._nav_album_data:
            self.restore_requested.emit()
            self.mw.control_panel.album_clicked.emit(self._nav_album_data)

    def _on_year_clicked(self, *args):
        """Handles a click event on the album year, requesting view restoration and sending the navigation event."""
        if self._nav_year_data:
            self.restore_requested.emit()
            self.mw.control_panel.year_clicked.emit(self._nav_year_data)

    def _on_artist_clicked(self, *args):
        """Handles click events for the artist label, displaying an action menu if there are multiple artists."""
        if not self._current_track_data: return

        if hasattr(self.mw, 'artist_source_tag') and self.mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
            if self._nav_artist_data:
                self.restore_requested.emit()
                self.mw.control_panel.artist_clicked.emit(self._nav_artist_data)
            return

        artists = self._current_track_data.get("artists", [])
        if not artists:
            if self._nav_artist_data: artists = [self._nav_artist_data]

        if not artists: return

        if len(artists) == 1:
            self.restore_requested.emit()
            self.mw.control_panel.artist_clicked.emit(artists[0])
        else:
            menu = TranslucentMenu(self)
            for artist in artists:
                action = QAction(artist, menu)
                action.triggered.connect(partial(self._on_artist_action_triggered, artist))
                menu.addAction(action)
            menu.exec(self.artist_label.mapToGlobal(QPoint(0, self.artist_label.height())))

    def _on_artist_action_triggered(self, artist):
        """Helper to invoke artist navigation from the pop-up menu."""
        self.restore_requested.emit()
        self.mw.control_panel.artist_clicked.emit(artist)

    def _toggle_volume_popup(self):
        """Toggles the visibility and manages the placement of the quick-access volume control popup."""
        popup = self.mw.control_panel.volume_popup
        if self.mw.control_panel._popup_just_closed:
            return
        if popup.isVisible():
            popup.hide()
            return
        point = self.btn_volume.mapToGlobal(QPoint(0, 0))
        popup_x = point.x() + (self.btn_volume.width() - popup.width()) // 2
        popup_y = point.y() - popup.height() - 5
        screen = self.btn_volume.screen()
        if screen:
            screen_geom = screen.availableGeometry()
            if popup_y < screen_geom.top():
                popup_y = point.y() + self.btn_volume.height() + 5
                if popup_y + popup.height() > screen_geom.bottom():
                    popup_y = screen_geom.bottom() - popup.height() - 5
        popup.move(popup_x, popup_y)
        popup.show()
        popup.raise_()

    def showEvent(self, event):
        """Fires when the window is shown, initiating the opacity logic."""
        super().showEvent(event)
        self._update_opacity()

    def hideEvent(self, event):
        """Ensures the external popup (queue/lyrics) is hidden alongside the parent window."""
        if self._is_queue_expanded:
            self._is_queue_expanded = False
            self.update_queue_toggle_button(False)

        self.queue_popup.hide()
        super().hideEvent(event)

    def moveEvent(self, event):
        """Ensures that the queue popup always follows the window, even if the window is moved by the OS itself."""
        super().moveEvent(event)
        if getattr(self, '_is_queue_expanded', False):
            self._update_popup_position()

    def mousePressEvent(self, event):
        """Captures mouse clicks strictly within the frame boundary for drag functionality."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.main_frame.geometry().contains(event.pos()):

                is_wayland = QApplication.platformName() == "wayland"

                if is_wayland:
                    window_handle = self.window().windowHandle()
                    if window_handle and window_handle.startSystemMove():
                        return

                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        """Calculates window translation and implements screen-edge snapping logic while dragging (Fallback)."""
        if event.buttons() == Qt.MouseButton.LeftButton and getattr(self, '_drag_pos', None) is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_pos

            current_screen = QApplication.screenAt(event.globalPosition().toPoint())

            if current_screen:
                screen_geom = current_screen.availableGeometry()

                margins = self.window_layout.contentsMargins()
                m_left, m_top = margins.left(), margins.top()
                m_right, m_bottom = margins.right(), margins.bottom()

                screen_left, screen_right = screen_geom.x(), screen_geom.x() + screen_geom.width()
                screen_top, screen_bottom = screen_geom.y(), screen_geom.y() + screen_geom.height()
                snap_margin = 20

                visible_left = new_pos.x() + m_left
                visible_right = new_pos.x() + self.width() - m_right
                visible_top = new_pos.y() + m_top
                visible_bottom = new_pos.y() + self.height() - m_bottom

                if abs(visible_left - screen_left) < snap_margin:
                    new_pos.setX(screen_left - m_left)
                elif abs(visible_right - screen_right) < snap_margin:
                    new_pos.setX(screen_right - self.width() + m_right)

                if abs(visible_top - screen_top) < snap_margin:
                    new_pos.setY(screen_top - m_top)
                elif abs(visible_bottom - screen_bottom) < snap_margin:
                    new_pos.setY(screen_bottom - self.height() + m_bottom)

                min_x = screen_geom.x() - m_left
                max_x = screen_geom.x() + screen_geom.width() - self.width() + m_right
                min_y = screen_geom.y() - m_top
                max_y = screen_geom.y() + screen_geom.height() - self.height() + m_bottom

                clamped_x = max(min_x, min(new_pos.x(), max_x))
                clamped_y = max(min_y, min(new_pos.y(), max_y))

                new_pos.setX(clamped_x)
                new_pos.setY(clamped_y)

            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Clears drag position state after a mouse movement completes."""
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _update_opacity(self):
        """Applies dynamic opacity logic depending on window focus, mouse hover state, or user settings."""
        opacity_enabled = getattr(self.mw, 'mini_opacity', True)

        if IS_LINUX:
            opacity_enabled = False

        is_active = (self.isActiveWindow() or self.underMouse() or
                     self.queue_popup.isActiveWindow() or self.queue_popup.underMouse())

        if is_active or not opacity_enabled:
            self.setWindowOpacity(1.0)
            self.queue_popup.setWindowOpacity(1.0)
        else:
            self.setWindowOpacity(0.5)
            self.queue_popup.setWindowOpacity(0.5)

        self.update()
        self.queue_popup.update()

    def enterEvent(self, event):
        """Hooks the hover event to restore full opacity."""
        self._update_opacity()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hooks the un-hover event to restore configured standby opacity."""
        self._update_opacity()
        super().leaveEvent(event)

    def changeEvent(self, event):
        """Updates opacity whenever the active focus changes."""
        if event.type() == QEvent.Type.ActivationChange:
            self._update_opacity()
        super().changeEvent(event)

    def _setup_hotkeys(self):
        """Initializes application-wide keyboard shortcuts for the Mini Vinny."""
        hotkey_map = {
            "C": self.mw.cycle_window_mode,
            "P": self.mw.open_settings,
            "Space": self.mw.player_controller.toggle_play_pause,
            "Ctrl+Right": self.mw.player.next,
            "F": self.mw.player.next,
            "Ctrl+Left": self.mw.player.previous,
            "B": self.mw.player.previous,
            "Ctrl+Up": self.mw.hotkey_manager.increase_volume,
            "Ctrl+Down": self.mw.hotkey_manager.decrease_volume,
            "=": self.mw.hotkey_manager.increase_volume,
            "+": self.mw.hotkey_manager.increase_volume,
            "-": self.mw.hotkey_manager.decrease_volume,
            "M": self.mw.toggle_mute,
            "L": self.mw.action_handler.toggle_current_track_favorite,
            Qt.Key.Key_MediaTogglePlayPause: self.mw.player_controller.toggle_play_pause,
            Qt.Key.Key_MediaPlay: self.mw.player_controller.toggle_play_pause,
            Qt.Key.Key_MediaNext: self.mw.player.next,
            Qt.Key.Key_MediaPrevious: self.mw.player.previous,
        }
        self.shortcuts = []
        for key_sequence, function in hotkey_map.items():
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(function)
            self.shortcuts.append(shortcut)

    def _setup_drop_zones(self):
        """Creates a horizontal overlay with drop zones on top of the main frame."""
        self.drop_zone_container = QFrame(self.main_frame)
        self.drop_zone_container.setObjectName("dropZoneContainer")
        self.drop_zone_container.hide()

        layout = QHBoxLayout(self.drop_zone_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.dz_library = QFrame()
        self.dz_append = QFrame()
        self.dz_replace = QFrame()

        zones_data = [
            (self.dz_library, "folder_add", translate("Add to Library")),
            (self.dz_append, "add", translate("Add to Queue")),
            (self.dz_replace, "replace", translate("Replace Queue")),
        ]

        self.drop_zones = []

        for zone, icon_name, text in zones_data:
            zone.setObjectName("dropZone")
            zone.setProperty("active", False)

            z_layout = QVBoxLayout(zone)
            z_layout.setContentsMargins(4, 8, 4, 8)
            z_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon_label = QLabel()
            icon_pixmap = create_svg_icon(
                f"assets/control/{icon_name}.svg",
                theme.COLORS["SECONDARY"],
                QSize(32, 32),
            ).pixmap(QSize(32, 32))
            icon_label.setPixmap(icon_pixmap)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            z_layout.addWidget(icon_label)


            layout.addWidget(zone)
            self.drop_zones.append(zone)

    def resizeEvent(self, event):
        """Aligns the file drop zone containers whenever the main UI is resized."""
        super().resizeEvent(event)
        if hasattr(self, 'drop_zone_container'):
            self.drop_zone_container.setGeometry(self.main_frame.rect())


    def dragEnterEvent(self, event):
        """Permits URL objects to be tracked as drop actions over the UI widget."""
        if event.mimeData().hasUrls():
            self.drop_zone_container.setGeometry(self.main_frame.rect())
            self.drop_zone_container.show()
            self.drop_zone_container.raise_()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Updates internal state indicating which internal drop region the cursor currently occupies."""
        if event.mimeData().hasUrls():
            pos = event.position().toPoint()
            mapped_pos = self.main_frame.mapFrom(self, pos)
            self._update_active_drop_zone(mapped_pos)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Resets variables hiding visual indicators when dragging operations abort or leave bounds."""
        self.drop_zone_container.hide()
        self.active_drop_zone = -1
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        """Translates the dropped object paths depending on the exact drop region chosen."""
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        pos = event.position().toPoint()
        mapped_pos = self.main_frame.mapFrom(self, pos)
        target_zone = self._get_active_drop_zone(mapped_pos)

        self.drop_zone_container.hide()
        self.active_drop_zone = -1

        if target_zone != -1:
            paths = [url.toLocalFile() for url in event.mimeData().urls()]

            if target_zone == 0:
                self.restore_requested.emit()
                self.mw.action_handler.handle_drop_library(paths)
            elif target_zone == 1:
                self.mw.action_handler.handle_drop_add_to_queue(paths)
            elif target_zone == 2:
                self.mw.action_handler.handle_drop_replace_queue(paths)

            event.acceptProposedAction()
        else:
            event.ignore()

    def _update_active_drop_zone(self, pos):
        """Applies hover styling logic depending on current coordinate bounds."""
        new_active_zone = self._get_active_drop_zone(pos)

        if new_active_zone != self.active_drop_zone:
            self.active_drop_zone = new_active_zone
            for i, zone in enumerate(self.drop_zones):
                is_active = (i == self.active_drop_zone)
                zone.setProperty("active", is_active)
                self.style().unpolish(zone)
                self.style().polish(zone)

    def _get_active_drop_zone(self, pos):
        """Matches internal bounding rects against coordinates to extract zone index."""
        for i, zone in enumerate(self.drop_zones):
            if zone.geometry().contains(pos):
                return i
        return -1

    def closeEvent(self, event):
        """Handles closing directly from the mini mode (e.g., via Alt+F4 or Taskbar)."""
        self.mw.mini_geometry = self.saveGeometry().toHex().data().decode()

        self.mw.mini_pos = self.pos()

        self.mw.save_current_settings()
        event.accept()

        QApplication.instance().quit()