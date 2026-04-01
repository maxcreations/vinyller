"""
Vinyller — Control panel
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
    QTimer
)
from PyQt6.QtGui import (
    QIcon,
    QPixmap, QAction
)
from PyQt6.QtWidgets import (
    QBoxLayout, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QSizePolicy
)

from src.core.hotkey_manager import HotkeyManager
from src.player.player import RepeatMode
from src.ui.custom_base_widgets import TranslucentMenu, set_custom_tooltip
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ClickableLabel, ClickableProgressBar, ClickableSlider, ElidedLabel, FlowLayout, ZoomableCoverLabel
)
from src.utils import theme
from src.utils.constants import ArtistSource
from src.utils.constants_linux import IS_LINUX, WINDOW_RADIUS
from src.utils.utils import (
    create_svg_icon, resource_path
)
from src.utils.utils_translator import translate


class ControlPanel(QWidget):
    """
    A standalone control panel widget for a music player.
    It encapsulates all control elements and can switch
    between horizontal (standard) and vertical (vinyl) layouts.
    """

    play_pause_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    shuffle_clicked = pyqtSignal()
    repeat_clicked = pyqtSignal()
    queue_toggle_clicked = pyqtSignal()
    favorite_clicked = pyqtSignal()
    volume_toggle_clicked = pyqtSignal()
    vinyl_queue_toggle_clicked = pyqtSignal(bool)
    lyrics_toggle_clicked = pyqtSignal(bool)

    hide_panel_clicked = pyqtSignal()

    always_on_top_toggled = pyqtSignal(bool)
    mini_requested = pyqtSignal()

    position_seeked = pyqtSignal(int)
    volume_changed = pyqtSignal(int)

    artist_clicked = pyqtSignal(object)
    album_clicked = pyqtSignal(object)
    genre_clicked = pyqtSignal(str)
    cover_zoom_requested = pyqtSignal(QPixmap)
    year_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._is_track_loaded = False
        self._is_vinyl_mode = False

        self.current_track_data = None

        self._popup_just_closed = False
        self._popup_close_timer = QTimer(self)
        self._popup_close_timer.setSingleShot(True)
        self._popup_close_timer.setInterval(300)
        self._popup_close_timer.timeout.connect(self._reset_popup_flag)

        self._create_widgets()
        self._setup_layout()
        self._connect_internal_signals()

    def showEvent(self, event):
        """
        Subscribes to main window events when the widget is shown.
        This is needed to catch window resize events, even if the panel
        itself has a fixed width (e.g., in island mode).
        """
        super().showEvent(event)
        if self.window():
            self.window().removeEventFilter(self)
            self.window().installEventFilter(self)


    def eventFilter(self, source, event):
        """
        Intercepts and processes specific events like hiding the volume popup or resizing the main window.

        Args:
            source (QObject): The object that generated the event.
            event (QEvent): The event to be intercepted.

        Returns:
            bool: True if the event was filtered out, False otherwise.
        """
        if source is self.volume_popup and event.type() == QEvent.Type.Hide:
            self._popup_just_closed = True
            self._popup_close_timer.start()

        if source is self.window() and event.type() == QEvent.Type.Resize:
            self._update_background_style()

        return super().eventFilter(source, event)

    def _reset_popup_flag(self):
        """Slot to reset the flag after timeout."""
        self._popup_just_closed = False

    def _create_widgets(self):
        """Creates all individual widgets on the control panel."""
        self.progress_widget = QWidget(self)
        self.progress_widget.setFixedHeight(36)
        progress_widget_layout = QHBoxLayout(self.progress_widget)
        progress_widget_layout.setContentsMargins(0, 0, 0, 0)
        progress_widget_layout.setSpacing(8)
        progress_widget_layout.addStretch()

        self.current_time_label = QLabel("00:00", self)
        self.current_time_label.setProperty("class", "textSecondary textColorPrimary")
        progress_widget_layout.addWidget(self.current_time_label)

        self.progress_slider = ClickableProgressBar(Qt.Orientation.Horizontal, self)
        self.progress_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress_slider.setEnabled(False)
        progress_widget_layout.addWidget(self.progress_slider, 1)

        self.total_time_label = QLabel("00:00", self)
        self.total_time_label.setProperty("class", "textSecondary textColorPrimary")
        progress_widget_layout.addWidget(self.total_time_label)
        progress_widget_layout.addSpacing(8)

        self.queue_toggle_button = QPushButton("", self)
        self.queue_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            self.queue_toggle_button,
            title = translate("Playback Queue"),
        )
        self.queue_toggle_button.setCheckable(True)
        self.queue_toggle_button.setIconSize(QSize(24, 24))
        self.queue_toggle_button.setProperty("class", "btnTool")
        apply_button_opacity_effect(self.queue_toggle_button)
        progress_widget_layout.addWidget(self.queue_toggle_button)

        self.vinyl_queue_button = QPushButton("", self)
        set_custom_tooltip(
            self.vinyl_queue_button,
            title = translate("Playback Queue"),
        )
        self.vinyl_queue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.vinyl_queue_button.setIconSize(QSize(24, 24))
        self.vinyl_queue_button.setIcon(
            create_svg_icon(
                "assets/control/playback_queue.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.vinyl_queue_button.setProperty("class", "btnTool")
        self.vinyl_queue_button.setCheckable(True)
        self.vinyl_queue_button.setVisible(False)
        apply_button_opacity_effect(self.vinyl_queue_button)
        progress_widget_layout.addWidget(self.vinyl_queue_button)

        self.hide_panel_button = QPushButton("", self)
        self.hide_panel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_panel_button.setIconSize(QSize(24, 24))
        self.hide_panel_button.setIcon(
            create_svg_icon(
                "assets/control/more_horiz.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.hide_panel_button.setProperty("class", "btnTool")
        self.hide_panel_button.setVisible(False)
        set_custom_tooltip(
            self.hide_panel_button,
            title = translate("View Options"),
        )
        self.hide_panel_button.clicked.connect(self._show_panel_menu)
        apply_button_opacity_effect(self.hide_panel_button)

        progress_widget_layout.addWidget(self.hide_panel_button)

        self.track_info_widget = QWidget(self)
        self.track_widget_layout = QHBoxLayout(self.track_info_widget)
        self.track_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.track_widget_layout.setSpacing(8)

        default_missing_cover = "assets/view/missing_cover.png"
        missing_cover_path = theme.COLORS.get("MISSING_COVER", default_missing_cover)
        missing_cover_pixmap = QIcon(resource_path(missing_cover_path)).pixmap(72, 72)
        self.album_art_label = ZoomableCoverLabel(missing_cover_pixmap, 3, self)
        self.album_art_label.setFixedSize(72, 72)
        self.album_art_label.setClickable(False)
        self.track_widget_layout.addWidget(self.album_art_label)

        self.track_info_layout = QVBoxLayout()
        self.track_info_layout.setContentsMargins(0, 0, 0, 0)
        self.track_info_layout.setSpacing(2)

        self.song_title_label = ElidedLabel("", self)
        self.song_title_label.setProperty("class", "textPrimary textColorPrimary")

        self.artist_info_layout = QHBoxLayout()
        self.artist_info_layout.setContentsMargins(0, 0, 0, 0)
        self.artist_info_layout.setSpacing(0)
        self.artist_name_label = ClickableLabel("", None, self)
        self.artist_name_label.setProperty("class", "textSecondary textColorTertiary")
        self.artist_info_layout.addWidget(self.artist_name_label)
        self.artist_info_layout.addStretch()

        self.title_artist_layout = QHBoxLayout()
        self.title_artist_layout.setContentsMargins(0, 0, 0, 0)
        self.title_artist_layout.setSpacing(8)

        self.album_info_layout = QHBoxLayout()
        self.album_info_layout.setContentsMargins(0, 0, 0, 0)
        self.album_info_layout.setSpacing(0)
        self.album_name_label = ClickableLabel("", None, self)
        self.album_name_label.setProperty("class", "textSecondary textColorTertiary")
        self.album_comma_label = QLabel(", ", self)
        self.album_comma_label.setContentsMargins(1, 0, 0, 0)
        self.album_comma_label.setProperty("class", "textSecondary textColorTertiary")
        self.album_comma_label.setVisible(False)
        self.album_year_label = ClickableLabel("", None, self)
        self.album_year_label.setProperty("class", "textSecondary textColorTertiary")
        self.album_year_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        self.album_info_layout.addWidget(self.album_year_label)
        self.album_info_layout.addWidget(self.album_comma_label)
        self.album_info_layout.addWidget(self.album_name_label)
        self.album_info_layout.addStretch()

        self.lyrics_toggle_button_vinyl = QPushButton("", self)
        set_custom_tooltip(
            self.lyrics_toggle_button_vinyl,
            title = translate("Show Lyrics"),
        )
        self.lyrics_toggle_button_vinyl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lyrics_toggle_button_vinyl.setProperty("class", "btnTool")
        self.lyrics_toggle_button_vinyl.setIconSize(QSize(24, 24))
        self.lyrics_toggle_button_vinyl.setCheckable(True)
        self.lyrics_toggle_button_vinyl.setVisible(False)
        apply_button_opacity_effect(self.lyrics_toggle_button_vinyl)

        self.genres_widget = QWidget(self)
        self.genres_layout = FlowLayout(self.genres_widget)
        self.genres_layout.setContentsMargins(0, 4, 0, 0)
        self.genres_layout.setSpacing(0)

        self.track_info_layout.addWidget(self.song_title_label)
        self.track_info_layout.addLayout(self.artist_info_layout)
        self.track_info_layout.addLayout(self.album_info_layout)
        self.track_info_layout.addWidget(self.genres_widget)
        self.track_info_layout.addStretch()

        self.track_widget_layout.addLayout(self.track_info_layout)

        self.buttons_widget = QWidget(self)
        buttons_layout = QHBoxLayout(self.buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(24)

        inner_buttons_layout = QHBoxLayout()
        inner_buttons_layout.setContentsMargins(0, 0, 0, 0)
        inner_buttons_layout.setSpacing(8)

        self.favorite_button_vinyl = QPushButton("", self)
        set_custom_tooltip(
            self.favorite_button_vinyl,
            title = translate("Add to favorites"),
        )
        self.favorite_button_vinyl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorite_button_vinyl.setProperty("class", "btnTool")
        self.favorite_button_vinyl.setIconSize(QSize(24, 24))
        self.favorite_button_vinyl.setVisible(False)
        apply_button_opacity_effect(self.favorite_button_vinyl)

        buttons_layout.addWidget(self.favorite_button_vinyl)
        buttons_layout.addStretch()

        button_configs = [
            ("shuffle", translate("Shuffle mode"), "shuffle", 24, "btnControl"),
            ("prev_track", translate("Previous track"), "skip_prev", 24, "btnControl"),
            ("play_pause", translate("Play"), "play", 32, "btnControl btnPlay"),
            ("next_track", translate("Next track"), "skip_next", 24, "btnControl"),
            ("repeat", translate("Repeat mode"), "repeat_all", 24, "btnControl"),
        ]

        self.control_buttons = {}
        for name, tooltip, icon, size, prop_class in button_configs:
            button = QPushButton(self)
            set_custom_tooltip(
                button,
                title = tooltip,
                hotkey = HotkeyManager.get_hotkey_str(name)
            )
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(
                create_svg_icon(
                    f"assets/control/{icon}.svg",
                    theme.COLORS["PRIMARY"],
                    QSize(size, size),
                )
            )
            button.setProperty("class", prop_class)
            button.setIconSize(QSize(size, size))
            apply_button_opacity_effect(button)
            inner_buttons_layout.addWidget(button)
            self.control_buttons[name] = button

        buttons_layout.addLayout(inner_buttons_layout)

        self.volume_button_vinyl = QPushButton("", self)
        set_custom_tooltip(
            self.volume_button_vinyl,
            title = translate("Volume"),
        )
        self.volume_button_vinyl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volume_button_vinyl.setIconSize(QSize(24, 24))
        self.volume_button_vinyl.setProperty("class", "btnTool")
        self.volume_button_vinyl.setVisible(False)
        self.volume_button_vinyl.setCheckable(True)
        apply_button_opacity_effect(self.volume_button_vinyl)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.volume_button_vinyl)

        self.volume_widget = QWidget(self)
        volume_layout = QHBoxLayout(self.volume_widget)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(16)
        volume_layout.addStretch()

        self.lyrics_toggle_button_ctrl = QPushButton("", self)
        set_custom_tooltip(
            self.lyrics_toggle_button_ctrl,
            title = translate("Show Lyrics"),
        )
        self.lyrics_toggle_button_ctrl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lyrics_toggle_button_ctrl.setProperty("class", "btnTool")
        self.lyrics_toggle_button_ctrl.setIconSize(QSize(24, 24))
        self.lyrics_toggle_button_ctrl.setCheckable(True)
        self.lyrics_toggle_button_ctrl.setVisible(False)
        apply_button_opacity_effect(self.lyrics_toggle_button_ctrl)
        volume_layout.addWidget(
            self.lyrics_toggle_button_ctrl, 0, Qt.AlignmentFlag.AlignVCenter
        )

        self.favorite_button_ctrl = QPushButton("", self)
        set_custom_tooltip(
            self.favorite_button_ctrl,
            title = translate("Add to favorites"),
            hotkey = HotkeyManager.get_hotkey_str("favorite")
        )
        self.favorite_button_ctrl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorite_button_ctrl.setProperty("class", "btnTool")
        self.favorite_button_ctrl.setIconSize(QSize(24, 24))
        self.favorite_button_ctrl.setVisible(False)
        apply_button_opacity_effect(self.favorite_button_ctrl)
        volume_layout.addWidget(
            self.favorite_button_ctrl, 0, Qt.AlignmentFlag.AlignVCenter
        )

        self.volume_toggle_button = QPushButton("", self)
        set_custom_tooltip(
            self.volume_toggle_button,
            title = translate("Mute"),
            hotkey = HotkeyManager.get_hotkey_str("mute")
        )
        self.volume_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volume_toggle_button.setCheckable(True)
        self.volume_toggle_button.setIconSize(QSize(24, 24))
        self.volume_toggle_button.setProperty("class", "btnTool")
        apply_button_opacity_effect(self.volume_toggle_button)
        volume_layout.addWidget(self.volume_toggle_button)

        self.volume_slider = ClickableSlider(Qt.Orientation.Horizontal, self)
        self.volume_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setFixedWidth(120)
        volume_layout.addWidget(self.volume_slider)

        self.volume_popup = QWidget(self)
        self.volume_popup.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.volume_popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.volume_popup.setFixedSize(54, 180)

        self.volume_popup.installEventFilter(self)

        container_layout = QVBoxLayout(self.volume_popup)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self.popup_frame = QFrame(self.volume_popup)
        self.popup_frame.setProperty("class", "popup")
        container_layout.addWidget(self.popup_frame)

        inner_layout = QVBoxLayout(self.popup_frame)
        inner_layout.setContentsMargins(8, 16, 8, 8)
        inner_layout.setSpacing(8)

        self.popup_volume_slider = ClickableSlider(Qt.Orientation.Vertical, self)
        self.popup_volume_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popup_volume_slider.setRange(0, 100)
        inner_layout.addWidget(
            self.popup_volume_slider, 1, Qt.AlignmentFlag.AlignHCenter
        )

        self.popup_mute_button = QPushButton("", self)
        set_custom_tooltip(
            self.popup_mute_button,
            title = translate("Mute"),
            hotkey = HotkeyManager.get_hotkey_str("mute")
        )
        self.popup_mute_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.popup_mute_button.setCheckable(True)
        self.popup_mute_button.setIconSize(QSize(24, 24))
        self.popup_mute_button.setProperty("class", "btnTool")
        apply_button_opacity_effect(self.popup_mute_button)
        inner_layout.addWidget(self.popup_mute_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def _setup_layout(self):
        """Sets up the main layout of the control panel."""
        main_control_layout = QVBoxLayout(self)
        main_control_layout.setContentsMargins(0, 0, 0, 0)
        main_control_layout.setSpacing(0)

        self.background_widget = QWidget()
        self.background_widget.setProperty("class", "controlPanel")

        self.background_layout = QVBoxLayout(self.background_widget)
        self.background_layout.setContentsMargins(16, 12, 16, 16)
        self.background_layout.setSpacing(8)

        self.background_layout.addWidget(self.progress_widget)

        self.info_panel_container = QWidget()
        self.info_panel_container.setFixedHeight(72)
        self.info_buttons_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.info_panel_container.setLayout(self.info_buttons_layout)
        self.info_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.info_buttons_layout.setSpacing(16)

        self.info_buttons_layout.addWidget(self.track_info_widget, 1)
        self.info_buttons_layout.addWidget(self.buttons_widget, 0)
        self.info_buttons_layout.addWidget(self.volume_widget, 1)

        self.background_layout.addWidget(self.info_panel_container)
        main_control_layout.addWidget(self.background_widget)

        self.setViewMode(is_vinyl_mode=False)

    def _connect_internal_signals(self):
        """Connects internal widget signals to the class's public signals."""
        self.control_buttons["play_pause"].clicked.connect(self.play_pause_clicked)
        self.control_buttons["next_track"].clicked.connect(self.next_clicked)
        self.control_buttons["prev_track"].clicked.connect(self.prev_clicked)
        self.control_buttons["shuffle"].clicked.connect(self.shuffle_clicked)
        self.control_buttons["repeat"].clicked.connect(self.repeat_clicked)
        self.queue_toggle_button.clicked.connect(self.queue_toggle_clicked)
        self.favorite_button_ctrl.clicked.connect(self.favorite_clicked)
        self.favorite_button_vinyl.clicked.connect(self.favorite_clicked)

        self.lyrics_toggle_button_ctrl.clicked.connect(self._on_lyrics_toggled)
        self.lyrics_toggle_button_vinyl.clicked.connect(self._on_lyrics_toggled)

        self.vinyl_queue_button.toggled.connect(self._on_vinyl_queue_toggled)

        self.volume_toggle_button.clicked.connect(self.volume_toggle_clicked)
        self.popup_mute_button.clicked.connect(self.volume_toggle_clicked)

        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)
        self.popup_volume_slider.valueChanged.connect(self._on_volume_slider_changed)

        self.volume_button_vinyl.clicked.connect(self._show_volume_popup)

        self.progress_slider.sliderReleased.connect(
            lambda: self.position_seeked.emit(self.progress_slider.value())
        )
        self.artist_name_label.clicked.connect(self._on_artist_label_clicked)
        self.album_name_label.clicked.connect(self.album_clicked)
        self.album_art_label.zoomRequested.connect(self.cover_zoom_requested)
        self.album_year_label.clicked.connect(self._on_year_clicked)

    def _on_year_clicked(self):
        """Emits year_clicked signal if year data is available."""
        if hasattr(self.album_year_label, "data") and self.album_year_label.data:
            self.year_clicked.emit(str(self.album_year_label.data))

    def _on_lyrics_toggled(self):
        """
        Internal slot that synchronizes both buttons
        and emits the public signal.
        """
        sender = self.sender()
        is_checked = sender.isChecked()

        self.lyrics_toggle_button_ctrl.blockSignals(True)
        self.lyrics_toggle_button_vinyl.blockSignals(True)

        self.lyrics_toggle_button_ctrl.setChecked(is_checked)
        self.lyrics_toggle_button_vinyl.setChecked(is_checked)

        self.lyrics_toggle_button_ctrl.blockSignals(False)
        self.lyrics_toggle_button_vinyl.blockSignals(False)

        self.update_lyrics_toggle_button(is_visible=True, is_checked=is_checked)

        self.lyrics_toggle_clicked.emit(is_checked)

    def _on_vinyl_queue_toggled(self, shown):
        """
        Handles queue toggling in vinyl mode,
        emitting a signal for MainWindow, which manages element visibility.
        """
        self.vinyl_queue_toggle_clicked.emit(shown)

    def _on_volume_slider_changed(self, value):
        """Internal slot for synchronizing sliders and sending the signal."""
        self.volume_slider.blockSignals(True)
        self.popup_volume_slider.blockSignals(True)
        self.volume_slider.setValue(value)
        self.popup_volume_slider.setValue(value)
        self.volume_slider.blockSignals(False)
        self.popup_volume_slider.blockSignals(False)
        self.volume_changed.emit(value)

    def _show_volume_popup(self):
        """Shows or hides the volume popup window above the button."""
        if self.volume_popup.isVisible():
            self.volume_popup.hide()
            return
        if self._popup_just_closed:
            return
        point = self.volume_button_vinyl.mapToGlobal(QPoint(0, 0))
        popup_x = (
            point.x()
            + (self.volume_button_vinyl.width() - self.volume_popup.width()) // 2
        )
        popup_y = point.y() - self.volume_popup.height() - 5
        self.volume_popup.move(popup_x, popup_y)
        self.volume_popup.show()

    def _update_background_style(self):
        """Updates the background style based on window width and current mode."""
        width = self.window().width()
        height = self.window().height()

        if self._is_vinyl_mode and width > 720:
            if height > (720 + 200 + 32):
                new_class = "controlPanelVinylFloat"
            else:
                new_class = "controlPanelVinyl"
        else:
            new_class = "controlPanel"

        if self.background_widget.property("class") != new_class:
            self.background_widget.setProperty("class", new_class)
            self.background_widget.style().unpolish(self.background_widget)
            self.background_widget.style().polish(self.background_widget)

        if new_class == "controlPanel" and IS_LINUX:
            self.background_widget.setStyleSheet(f"""
                border-bottom-left-radius: {WINDOW_RADIUS}px;
                border-bottom-right-radius: {WINDOW_RADIUS}px;
            """)
        else:
            self.background_widget.setStyleSheet("")


    def resizeEvent(self, event):
        """Handle resize events to update style dynamically."""
        self._update_background_style()
        super().resizeEvent(event)

    def setViewMode(self, is_vinyl_mode: bool):
        """
        Switches the layout between standard (horizontal) and vertical (vinyl) modes.

        Args:
            is_vinyl_mode (bool): True to enable vertical vinyl mode, False for standard horizontal mode.
        """

        mode_changed = (self._is_vinyl_mode != is_vinyl_mode)
        self._is_vinyl_mode = is_vinyl_mode

        self._update_background_style()

        if not mode_changed:
            return

        self.background_widget.style().unpolish(self.background_widget)
        self.background_widget.style().polish(self.background_widget)

        self.lyrics_toggle_button_vinyl.setParent(None)

        while self.track_info_layout.count():
            self.track_info_layout.takeAt(0)
        while self.title_artist_layout.count():
            self.title_artist_layout.takeAt(0)

        if is_vinyl_mode:
            self.background_layout.setContentsMargins(16, 12, 16, 16)
            self.info_panel_container.setFixedHeight(128)
            self.track_info_layout.setSpacing(2)

            self.track_info_layout.addWidget(self.song_title_label)
            self.track_info_layout.addLayout(self.artist_info_layout)
            self.track_info_layout.addLayout(self.title_artist_layout)

            self.track_info_layout.addLayout(self.album_info_layout)

            self.track_widget_layout.addWidget(self.lyrics_toggle_button_vinyl)

            self.track_info_layout.addWidget(self.genres_widget)
            self.track_info_layout.addStretch()

        else:
            self.info_panel_container.setFixedHeight(72)
            self.track_info_layout.setSpacing(2)

            self.track_info_layout.addWidget(self.song_title_label)
            self.track_info_layout.addLayout(self.artist_info_layout)
            self.track_info_layout.addLayout(self.album_info_layout)
            self.track_info_layout.addWidget(self.genres_widget)
            self.track_info_layout.addStretch()

        if is_vinyl_mode:
            self.queue_toggle_button.hide()
            self.album_art_label.hide()
            self.volume_widget.hide()
            self.volume_button_vinyl.show()
            self.favorite_button_vinyl.show()
            self.vinyl_queue_button.show()

            self.hide_panel_button.show()

            self.lyrics_toggle_button_ctrl.hide()

            self.info_buttons_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.info_buttons_layout.setSpacing(8)
            self.info_buttons_layout.setStretch(0, 0)
            self.info_buttons_layout.setStretch(1, 0)
            self.info_buttons_layout.setStretch(2, 0)

            self.track_info_widget.setVisible(True)
        else:
            self.queue_toggle_button.show()
            self.album_art_label.show()
            self.volume_widget.show()
            self.volume_button_vinyl.hide()
            self.favorite_button_vinyl.hide()
            self.vinyl_queue_button.hide()

            self.hide_panel_button.hide()

            self.lyrics_toggle_button_vinyl.hide()

            self.track_info_widget.setVisible(True)

            self.info_buttons_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.info_buttons_layout.setSpacing(16)
            self.info_buttons_layout.setStretch(0, 1)
            self.info_buttons_layout.setStretch(1, 0)
            self.info_buttons_layout.setStretch(2, 1)

        is_fav = self.favorite_button_ctrl.property("active") or False
        self.update_favorite_button(self._is_track_loaded, is_fav)

        has_lyrics = False
        is_checked = False

        try:
            main_window = self.window()
            if main_window and hasattr(main_window, "player"):
                player = main_window.player
                player_queue = player.get_current_queue()
                current_index = player.get_current_index()

                if 0 <= current_index < len(player_queue):
                    track_data = player_queue[current_index]
                    has_lyrics = bool(track_data and track_data.get("lyrics"))

                is_checked = (
                        self.lyrics_toggle_button_ctrl.isChecked()
                        or self.lyrics_toggle_button_vinyl.isChecked()
                )

        except Exception:
            pass

        self.update_lyrics_toggle_button(is_visible = has_lyrics, is_checked = is_checked)

    def update_track_info(
            self,
            artist,
            title,
            album,
            year,
            genres,
            cover_pixmap,
            has_real_artwork,
            album_data,
            artist_data,
            track_data,
    ):
        """
        Updates the UI elements with the current track's metadata.

        Args:
            artist (str): The name of the artist.
            title (str): The title of the track.
            album (str): The name of the album.
            year (str or int): The release year of the track/album.
            genres (list): A list of genre names.
            cover_pixmap (QPixmap): The pixmap of the album cover.
            has_real_artwork (bool): True if the track has embedded/real artwork, False if using a placeholder.
            album_data (dict): The full metadata dictionary for the album.
            artist_data (dict): The full metadata dictionary for the artist.
            track_data (dict): The full metadata dictionary for the track.
        """
        self._is_track_loaded = True
        self.current_track_data = track_data
        self.artist_name_label.setText(artist)
        self.artist_name_label.data = artist_data

        mw = self.window()
        if mw and hasattr(mw, 'artist_source_tag') and mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
            target_artist = track_data.get("album_artist") or track_data.get("artist") or artist
            set_custom_tooltip(
                self.artist_name_label,
                title = translate("Go to Album Artist"),
                text = target_artist
            )
        else:
            set_custom_tooltip(
                self.artist_name_label,
                title = translate("Go to artist"),
                text = artist
            )

        self.song_title_label.setText(title)
        self.album_name_label.setText(album)
        self.album_name_label.data = album_data
        set_custom_tooltip(
            self.album_name_label,
            title = translate("Go to Album"),
            text = album
        )
        show_comma = bool(year) and bool(album)
        self.album_comma_label.setVisible(show_comma)
        self.album_year_label.setText(year)
        self.album_year_label.data = year
        self.album_year_label.setVisible(bool(year))
        if year:
            set_custom_tooltip(
                self.album_year_label,
                title = translate("Go to year"),
                text = str(year)
            )
        self.album_art_label.setPixmap(cover_pixmap)
        self.album_art_label.setClickable(has_real_artwork)

        self.album_year_label.setVisible(bool(year))

        while self.genres_layout.count():
            item = self.genres_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if genres:
            for i, genre in enumerate(genres):
                genre_text = genre
                genre_label = ClickableLabel(genre, genre_text, self)
                genre_label.setProperty("class", "textSecondary textColorTertiary")
                genre_label.setCursor(Qt.CursorShape.PointingHandCursor)
                genre_label.clicked.connect(partial(self.genre_clicked.emit, genre))
                set_custom_tooltip(
                    genre_label,
                    title = translate("Go to genre"),
                    text = genre_text
                )
                self.genres_layout.addWidget(genre_label)

                if i < len(genres) - 1:
                    comma_label = QLabel(", ", self)
                    comma_label.setContentsMargins(1, 0, 0, 0)
                    comma_label.setProperty("class", "textSecondary textColorTertiary")
                    self.genres_layout.addWidget(comma_label)
            self.genres_widget.show()
        else:
            self.genres_widget.hide()

        has_lyrics = bool(track_data and track_data.get("lyrics"))
        self.update_lyrics_toggle_button(is_visible=has_lyrics, is_checked=False)

    def _on_artist_label_clicked(self):
        """
        Handles clicks on the artist label.
        Adapts to ArtistSource preference:
        - ALBUM_ARTIST: Goes directly to Album Artist.
        - ARTIST: Shows menu if multiple artists, or goes to specific artist.
        """
        if not self.current_track_data:
            return

        mw = self.window()
        if mw and hasattr(mw, 'artist_source_tag') and mw.artist_source_tag == ArtistSource.ALBUM_ARTIST:
            target_artist = self.current_track_data.get("album_artist")
            if not target_artist:
                target_artist = self.current_track_data.get("artist")

            if target_artist:
                self.artist_clicked.emit(target_artist)
            return

        artists = self.current_track_data.get("artists", [])

        if not artists:
            text = self.artist_name_label.text()
            if text:
                artists = [text]

        if not artists:
            return

        if len(artists) == 1:
            self.artist_clicked.emit(artists[0])
        else:
            menu = TranslucentMenu(self)
            for artist in artists:
                action = QAction(artist, menu)
                action.triggered.connect(partial(self.artist_clicked.emit, artist))
                menu.addAction(action)

            menu.exec(self.artist_name_label.mapToGlobal(QPoint(0, self.artist_name_label.height())))

    def clear_track_info(self, default_pixmap):
        """Clears all track information and resets the UI to its default state."""
        self._is_track_loaded = False
        self.current_track_data = None
        self.artist_name_label.setText("")
        self.artist_name_label.data = ""
        self.song_title_label.setText("")
        self.album_name_label.setText("")
        self.album_name_label.data = ""
        self.album_comma_label.setVisible(False)
        self.album_year_label.setText("")
        self.album_year_label.data = None

        while self.genres_layout.count():
            item = self.genres_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.genres_widget.hide()

        self.album_art_label.setPixmap(default_pixmap)
        self.album_art_label.setClickable(False)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)
        self.update_favorite_button(is_enabled=False, is_favorite=False)

        self.update_lyrics_toggle_button(is_visible=False, is_checked=False)

    def update_playback_state(self, is_playing):
        """
        Updates the play/pause button icon and tooltip based on the playback state.

        Args:
            is_playing (bool): True if audio is currently playing, False if paused or stopped.
        """
        button = self.control_buttons["play_pause"]
        if is_playing:
            icon = create_svg_icon("assets/control/pause.svg", theme.COLORS["PRIMARY"], QSize(32, 32))
            button.setIcon(icon)
            set_custom_tooltip(
                button,
                title = translate("Pause"),
                hotkey = HotkeyManager.get_hotkey_str("play_pause")
            )
        else:
            icon = create_svg_icon("assets/control/play.svg", theme.COLORS["PRIMARY"], QSize(32, 32))
            button.setIcon(icon)
            set_custom_tooltip(
                button,
                title = translate("Play"),
                hotkey = HotkeyManager.get_hotkey_str("play_pause")
            )


    def update_position(self, position_val, position_str):
        """
        Updates the progress slider and current time label with the playback position.

        Args:
            position_val (int): The current position in milliseconds.
            position_str (str): The formatted string representation of the current position (e.g., "01:23").
        """
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(position_val)
        self.progress_slider.blockSignals(False)
        self.current_time_label.setText(position_str)

    def update_duration(self, duration_val, duration_str):
        """Updates the progress slider range and total time label."""
        self.progress_slider.setRange(0, duration_val)
        self.total_time_label.setText(duration_str)
        self.progress_slider.setEnabled(duration_val > 0)

    def update_shuffle_button(self, is_shuffled):
        """Updates the visual state of the shuffle button."""
        button = self.control_buttons["shuffle"]
        button.setProperty("active", is_shuffled)
        color = theme.COLORS["ACCENT"] if is_shuffled else theme.COLORS["PRIMARY"]
        button.setIcon(
            create_svg_icon("assets/control/shuffle.svg", color, QSize(24, 24))
        )
        button.style().polish(button)

    def update_repeat_button(self, mode):
        """Updates the icon of the repeat button according to the current repeat mode."""
        button = self.control_buttons["repeat"]
        is_active = mode != RepeatMode.NO_REPEAT
        button.setProperty("active", is_active)
        if mode == RepeatMode.NO_REPEAT:
            icon_to_set = create_svg_icon(
                "assets/control/repeat_all.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        elif mode == RepeatMode.REPEAT_ALL:
            icon_to_set = create_svg_icon(
                "assets/control/repeat_all.svg", theme.COLORS["ACCENT"], QSize(24, 24)
            )
        else:
            icon_to_set = create_svg_icon(
                "assets/control/repeat_one.svg", theme.COLORS["ACCENT"], QSize(24, 24)
            )
        button.setIcon(icon_to_set)
        button.style().polish(button)

    def update_volume_ui(self, is_muted, volume):
        """
        Updates all volume-related UI elements (buttons, sliders, popup) to reflect current volume and mute state.

        Args:
            is_muted (bool): True if the audio is currently muted.
            volume (int): The current volume level (0-100).
        """
        for w in [
            self.volume_toggle_button,
            self.popup_mute_button,
            self.volume_slider,
            self.popup_volume_slider,
        ]:
            w.blockSignals(True)

        self.volume_toggle_button.setChecked(is_muted)
        self.popup_mute_button.setChecked(is_muted)
        self.volume_button_vinyl.setChecked(is_muted)
        self.volume_slider.setValue(volume)
        self.popup_volume_slider.setValue(volume)

        if is_muted or volume == 0:
            icon = create_svg_icon(
                "assets/control/volume_off.svg", theme.COLORS["ACCENT"], QSize(24, 24)
            )
            tooltip = translate("Unmute")
            slider_class = "muted"
        else:
            icon = create_svg_icon(
                "assets/control/volume_on.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
            tooltip = translate("Mute")
            slider_class = "unmuted"

        self.volume_toggle_button.setIcon(icon)
        set_custom_tooltip(
            self.volume_toggle_button,
            title = tooltip,
            hotkey = HotkeyManager.get_hotkey_str("mute")
        )
        self.popup_mute_button.setIcon(icon)
        set_custom_tooltip(
            self.popup_mute_button,
            title = tooltip,
            hotkey = HotkeyManager.get_hotkey_str("mute")
        )
        self.volume_button_vinyl.setIcon(icon)

        self.volume_slider.setProperty("class", slider_class)
        self.popup_volume_slider.setProperty("class", slider_class)

        for w in [self.volume_slider, self.popup_volume_slider]:
            self.style().unpolish(w)
            self.style().polish(w)
            w.update()

        for w in [
            self.volume_toggle_button,
            self.popup_mute_button,
            self.volume_slider,
            self.popup_volume_slider,
        ]:
            w.blockSignals(False)

    def update_favorite_button(self, is_enabled, is_favorite):
        """Updates the favorite button status across normal and vinyl layouts, and mini mode if open."""
        main_window = self.window()
        if not main_window:
            return

        for button in [self.favorite_button_ctrl, self.favorite_button_vinyl]:
            button.setEnabled(is_enabled)
            button.setProperty("active", is_favorite)

            if button.graphicsEffect():
                button.graphicsEffect().setEnabled(not is_favorite)

            if is_favorite:
                button.setIcon(main_window.favorite_filled_icon)
                set_custom_tooltip(
                    button,
                    title = translate("Remove from favorites"),
                    hotkey = HotkeyManager.get_hotkey_str("favorite")
                )
            else:
                button.setIcon(main_window.favorite_icon)
                set_custom_tooltip(
                    button,
                    title = translate("Add to favorites"),
                    hotkey = HotkeyManager.get_hotkey_str("favorite")
                )
            self.style().polish(button)

        self.favorite_button_ctrl.setVisible(not self._is_vinyl_mode)
        self.favorite_button_vinyl.setVisible(self._is_vinyl_mode)

        if getattr(main_window, "mini_window", None):
            main_window.mini_window.set_favorite_state(
                is_favorite = is_favorite,
                is_enabled = is_enabled
            )

    def update_lyrics_toggle_button(self, is_visible, is_checked):
        """Updates the state and icon of the lyrics toggle buttons."""

        if is_checked:
            color = theme.COLORS["ACCENT"]
            tooltip = translate("Hide Lyrics")
        else:
            color = theme.COLORS["PRIMARY"]
            tooltip = translate("Show Lyrics")

        icon = create_svg_icon("assets/control/lyrics.svg", color, QSize(24, 24))

        buttons_to_update = [
            self.lyrics_toggle_button_ctrl,
            self.lyrics_toggle_button_vinyl,
        ]

        for button in buttons_to_update:
            button.blockSignals(True)

            button.setIcon(icon)
            set_custom_tooltip(
                button,
                title = tooltip,
            )
            button.setChecked(is_checked)
            button.setProperty("active", is_checked)

            if not is_visible:
                button.setVisible(False)
            else:
                if button == self.lyrics_toggle_button_ctrl:
                    button.setVisible(not self._is_vinyl_mode)
                elif button == self.lyrics_toggle_button_vinyl:
                    button.setVisible(self._is_vinyl_mode)

            if button.isVisible():
                if effect := button.graphicsEffect():
                    if is_checked or button.property("active") or button.underMouse():
                        target_opacity = 1.0
                    else:
                        target_opacity = 0.7
                    effect.setOpacity(target_opacity)

            self.style().polish(button)
            button.blockSignals(False)

    def update_queue_toggle_button(self, is_visible):
        """Updates the queue toggle button icon and its active state."""
        self.queue_toggle_button.setChecked(is_visible)
        color = theme.COLORS["ACCENT"] if is_visible else theme.COLORS["PRIMARY"]
        self.queue_toggle_button.setIcon(
            create_svg_icon("assets/control/playback_queue.svg", color, QSize(24, 24))
        )
        if is_visible:
            set_custom_tooltip(
                self.queue_toggle_button,
                title = translate("Hide Playback Queue"),
            )
        else:
            set_custom_tooltip(
                self.queue_toggle_button,
                title = translate("Show Playback Queue"),
            )

    def update_vinyl_queue_toggle_button(self, is_visible):
        """Updates the queue toggle button icon and state specifically for vinyl mode."""
        self.vinyl_queue_button.setChecked(is_visible)
        color = theme.COLORS["ACCENT"] if is_visible else theme.COLORS["PRIMARY"]
        self.vinyl_queue_button.setIcon(
            create_svg_icon("assets/control/playback_queue.svg", color, QSize(24, 24))
        )
        if is_visible:
            set_custom_tooltip(
                self.vinyl_queue_button,
                title = translate("Hide Playback Queue"),
            )
        else:
            set_custom_tooltip(
                self.vinyl_queue_button,
                title = translate("Show Playback Queue"),
            )

    def _show_panel_menu(self):
        """Displays the context menu for panel options such as hide, always on top, and mini mode."""
        menu = TranslucentMenu(self)
        menu.setProperty("class", "popMenu")

        action_hide = QAction(translate("Hide control panel"), menu)
        action_hide.triggered.connect(self.hide_panel_clicked.emit)
        menu.addAction(action_hide)

        if not IS_LINUX:
            action_top = QAction(translate("Always on top"), menu)
            action_top.setCheckable(True)
            is_on_top = self.window().windowFlags() & Qt.WindowType.WindowStaysOnTopHint
            action_top.setChecked(bool(is_on_top))
            action_top.toggled.connect(self.always_on_top_toggled.emit)
            menu.addAction(action_top)

        menu.addSeparator()

        action_mini = QAction(translate("Mini mode"), menu)
        action_mini.triggered.connect(self.mini_requested.emit)
        menu.addAction(action_mini)

        global_pos = self.hide_panel_button.mapToGlobal(QPoint(0, self.hide_panel_button.height()))
        menu.exec(global_pos)
