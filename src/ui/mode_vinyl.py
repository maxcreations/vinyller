"""
Vinyller — Vinyl mode classes and methods
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

import math
import random

from PyQt6.QtCore import (
    pyqtProperty, pyqtSignal, QEvent, QEasingCurve,
    QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt,
    QTimer, QSequentialAnimationGroup
)
from PyQt6.QtGui import (
    QBrush, QColor, QImage, QPainter, QPainterPath, QPixmap, QRadialGradient
)
from PyQt6.QtWidgets import (
    QLabel, QPushButton,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget, QGraphicsOpacityEffect, QHBoxLayout
)

from src.core.hotkey_manager import HotkeyManager
from src.ui.custom_base_widgets import set_custom_tooltip
from src.ui.custom_classes import (
    apply_button_opacity_effect
)
from src.utils import theme
from src.utils.constants_linux import WINDOW_RADIUS, IS_LINUX
from src.utils.utils import (
    create_svg_icon, resource_path
)
from src.utils.utils_translator import translate

MAX_SIZE = 720


def get_dominant_color(pixmap: QPixmap, default_color=QColor(theme.COLORS["TERTIARY"])):
    """
    Analyzes a QPixmap, finds the dominant color, and returns it
    as a darkened and less saturated QColor suitable for a background.
    Colors with lightness below 0.25 are filtered out during analysis.
    """
    if not pixmap or pixmap.isNull():
        return default_color

    image = pixmap.toImage().scaled(
        100,
        100,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if (
        image.format() != QImage.Format.Format_ARGB32
        and image.format() != QImage.Format.Format_RGB32
    ):
        image = image.convertToFormat(QImage.Format.Format_ARGB32)

    brighter_colors = []
    for x in range(image.width()):
        for y in range(image.height()):
            color = QColor(image.pixel(x, y))
            if color.alpha() != 0:
                h, s, l, a = color.getHslF()
                if l >= 0.25 and l <= 0.8:
                    brighter_colors.append(color)

    if not brighter_colors:
        return default_color

    color_counts = {}
    for color in brighter_colors:
        r = round(color.red() / 20) * 20
        g = round(color.green() / 20) * 20
        b = round(color.blue() / 20) * 20
        rgb_tuple = (r, g, b)
        color_counts[rgb_tuple] = color_counts.get(rgb_tuple, 0) + 1

    if not color_counts:
        return default_color

    dominant_rgb = max(color_counts, key=color_counts.get)

    dominant_color = QColor(*dominant_rgb)

    h, s, l, a = dominant_color.getHslF()

    new_lightness = min(l, 1)
    new_saturation = s * 0.8

    adjusted_color = QColor.fromHslF(h, new_saturation, new_lightness, a)

    return adjusted_color


class ScaledPixmapLabel(QWidget):
    """Widget that displays a pixmap with an overlay texture."""

    def __init__(self, parent=None):
        """Initializes the widget with empty pixmaps and default shadow padding."""
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._mask_pixmap = QPixmap()
        self.shadow_padding = 24
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setPixmap(self, pixmap: QPixmap):
        """Sets the primary pixmap to be displayed and triggers a repaint."""
        self._pixmap = pixmap if pixmap else QPixmap()
        self.update()

    def setMask(self, mask_pixmap: QPixmap):
        """Sets the texture mask to be overlaid on top of the pixmap."""
        self._mask_pixmap = mask_pixmap if mask_pixmap else QPixmap()
        self.update()

    def paintEvent(self, event):
        """Handles custom painting of the pixmap with rounded corners, shadows, and an optional mask overlay."""
        if self._pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        content_rect = self.rect().adjusted(
            self.shadow_padding, self.shadow_padding,
            -self.shadow_padding, -self.shadow_padding
        )

        scaled_pixmap = self._pixmap.scaled(
            content_rect.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = content_rect.x() + (content_rect.width() - scaled_pixmap.width()) // 2
        y = content_rect.y() + (content_rect.height() - scaled_pixmap.height()) // 2
        target_rect = QRect(x, y, scaled_pixmap.width(), scaled_pixmap.height())
        target_rect_f = QRectF(target_rect)

        dynamic_radius = max(2, int(target_rect.width() * 0.015))

        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(1, 16):
            alpha = int(10 * (1 - i / 15))
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(
                target_rect_f.adjusted(-i, -i + 6, i, i + 6),
                dynamic_radius + i, dynamic_radius + i
            )

        path = QPainterPath()
        path.addRoundedRect(target_rect_f, dynamic_radius, dynamic_radius)

        painter.save()
        painter.setClipPath(path)
        painter.drawPixmap(target_rect, scaled_pixmap)
        if not self._mask_pixmap.isNull():
            scaled_mask = self._mask_pixmap.scaled(
                target_rect.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(target_rect, scaled_mask)
        painter.restore()


class VinylLabel(QLabel):
    """QLabel capable of rotation for a vinyl effect."""

    def __init__(self, pixmap, parent=None):
        """Initializes the label with a pixmap and sets the default rotation angle to 0."""
        super().__init__(parent)
        self.setPixmap(pixmap)
        self._rotation_angle = 0

    def set_rotation(self, angle):
        """Sets the rotation angle and requests a widget update."""
        self._rotation_angle = angle
        self.update()

    @pyqtProperty(float)
    def rotation(self):
        """Property to get the current rotation angle."""
        return self._rotation_angle

    @rotation.setter
    def rotation(self, angle):
        """Property to set the current rotation angle."""
        self.set_rotation(angle)

    def paintEvent(self, event):
        """Paints the pixmap rotated by the specified rotation angle around its center."""
        if self.pixmap():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            w, h = self.width(), self.height()
            center = QPoint(w // 2, h // 2)

            painter.translate(center)
            painter.rotate(self._rotation_angle)
            painter.translate(-center)

            painter.drawPixmap(
                0,
                0,
                self.pixmap().scaled(
                    w,
                    h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )
        else:
            super().paintEvent(event)


class VinylDrawingWidget(QWidget):
    """
    Widget that draws a rotating vinyl record and cover independently.
    All drawing logic and manual control (scratching) is encapsulated here.
    """

    scrubbingStarted = pyqtSignal()
    positionScrubbed = pyqtSignal(float)
    scrubbingFinished = pyqtSignal()

    def __init__(self, player, parent=None):
        """Initializes the drawing widget with required pixmaps, state flags, and a scratch stop timer."""
        super().__init__(parent)
        self.player = player
        self._rotation = 0.0
        self.vinyl_pixmap = QPixmap(resource_path("assets/view/vinyl.png"))
        self.cover_pixmap = QPixmap(resource_path("assets/view/missing_apple.png"))
        self.setMinimumSize(100, 100)

        self.apple_mask_pixmap = QPixmap(resource_path("assets/view/vinyl_mask_apple.png"))

        self._is_scrubbing = False
        self._last_angle = 0.0
        self._current_scratch_state = 0

        self._scratch_stop_timer = QTimer(self)
        self._scratch_stop_timer.setInterval(60)
        self._scratch_stop_timer.setSingleShot(True)
        self._scratch_stop_timer.timeout.connect(self._on_scratch_stopped)

    def set_cover_pixmap(self, pixmap: QPixmap):
        """Sets the center cover (apple) image and requests a repaint."""
        if not pixmap or pixmap.isNull():
            self.cover_pixmap = QPixmap(resource_path("assets/view/missing_apple.png"))
        else:
            self.cover_pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        """Paints the background shadow, the rotating vinyl record, the center cover, and the spindle."""
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

        padding = 24
        widget_size = min(self.width(), self.height()) - (padding * 2)
        offset_x = (self.width() - widget_size) // 2
        offset_y = (self.height() - widget_size) // 2
        target_rect = QRect(offset_x, offset_y, widget_size, widget_size)
        target_rect_f = QRectF(target_rect)
        center = QPointF(self.width() / 2, self.height() / 2)

        shadow_rect = target_rect_f.translated(0, 6).adjusted(-12, -12, 12, 12)

        gradient = QRadialGradient(shadow_rect.center(), shadow_rect.width() / 2)
        gradient.setColorAt(0, QColor(0, 0, 0, 110))
        gradient.setColorAt(0.7, QColor(0, 0, 0, 30))
        gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(shadow_rect)

        painter.save()
        painter.translate(center)
        painter.rotate(self._rotation)
        painter.translate(-center)
        painter.drawPixmap(target_rect, self.vinyl_pixmap)

        if not self.cover_pixmap.isNull():
            cover_size = int(widget_size * 0.33)
            cover_pos_coord = (widget_size - cover_size) // 2
            cover_rect = QRect(offset_x + cover_pos_coord, offset_y + cover_pos_coord, cover_size, cover_size)

            zoom = 1.1
            scaled_cover = self.cover_pixmap.scaled(cover_rect.size() * zoom,
                                                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                    Qt.TransformationMode.SmoothTransformation)
            scaled_cover_rect = scaled_cover.rect()
            scaled_cover_rect.moveCenter(cover_rect.center())

            path = QPainterPath()
            path.addEllipse(QRectF(cover_rect))

            painter.setClipPath(path)

            painter.drawPixmap(scaled_cover_rect, scaled_cover)

            if not self.apple_mask_pixmap.isNull():
                scaled_mask = self.apple_mask_pixmap.scaled(
                    cover_rect.size(),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                painter.drawPixmap(cover_rect, scaled_mask)

        painter.restore()

        spindle_radius = int(widget_size * 0.011)
        gradient = QRadialGradient(center, spindle_radius)
        gradient.setColorAt(0, QColor("#ffffff"))
        gradient.setColorAt(0.8, QColor("#f0f0f0"))
        gradient.setColorAt(1, QColor("#cccccc"))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, spindle_radius, spindle_radius)

    def _get_rotation(self):
        """Returns the current rotation angle of the vinyl."""
        return self._rotation

    def _set_rotation(self, angle):
        """Sets the rotation angle of the vinyl (modulo 360) and requests a repaint."""
        if self._rotation != angle:
            self._rotation = angle % 360
            self.update()

    rotation = pyqtProperty(float, fget=_get_rotation, fset=_set_rotation)

    def _on_scratch_stopped(self):
        """Called when mouse movement has stopped to halt the scratch sound effect."""
        if self._is_scrubbing:
            self.player.stop_scratch_sound()
            self._current_scratch_state = 0

    def _get_angle_from_pos(self, pos: QPointF) -> float:
        """Calculates the angle in degrees from a point relative to the widget's center."""
        center = self.rect().center()
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        return math.degrees(math.atan2(dy, dx))

    def mousePressEvent(self, event):
        """Handles the left mouse click to initiate the manual scrubbing (scratching) state."""
        if event.button() == Qt.MouseButton.LeftButton:
            center = self.rect().center()
            widget_size = min(self.width(), self.height())
            distance = math.sqrt(
                (event.pos().x() - center.x()) ** 2
                + (event.pos().y() - center.y()) ** 2
            )
            if distance <= widget_size / 2:
                self._is_scrubbing = True
                self.grabMouse()
                self._last_angle = self._get_angle_from_pos(event.pos())
                self.scrubbingStarted.emit()
                self._current_scratch_state = 0
                event.accept()

    def mouseMoveEvent(self, event):
        """Handles mouse movement during scrubbing to rotate the vinyl and trigger directional scratch sounds."""
        if self._is_scrubbing:
            current_angle = self._get_angle_from_pos(event.pos())
            delta_angle = current_angle - self._last_angle

            if delta_angle > 180:
                delta_angle -= 360
            elif delta_angle < -180:
                delta_angle += 360

            self.rotation += delta_angle
            self.positionScrubbed.emit(delta_angle)

            threshold = 0.1
            new_state = 0
            if delta_angle > threshold:
                new_state = 1
            elif delta_angle < -threshold:
                new_state = -1

            if new_state != 0 and new_state != self._current_scratch_state:
                if new_state == 1:
                    self.player.play_scratch_forward()
                    self.player.stop_scratch_backward()
                elif new_state == -1:
                    self.player.play_scratch_backward()
                    self.player.stop_scratch_forward()

                self._current_scratch_state = new_state

            if delta_angle != 0:
                self._scratch_stop_timer.start()

            self._last_angle = current_angle
            event.accept()

    def mouseReleaseEvent(self, event):
        """Handles mouse release to end the manual scrubbing state and cleanup."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_scrubbing:
            self._is_scrubbing = False
            self.releaseMouse()
            self._scratch_stop_timer.stop()
            self.scrubbingFinished.emit()
            self.player.stop_scratch_sound()
            self._current_scratch_state = 0
            event.accept()


class VinylWidget(QWidget):
    """
    Widget displaying a vinyl record with an animated cover
    that 'slides out' to reveal the record.
    Also supports slide transition animation for track changes.
    """

    backClicked = pyqtSignal()
    scrubbingStarted = pyqtSignal()
    positionScrubbed = pyqtSignal(float)
    scrubbingFinished = pyqtSignal()

    controlPanelToggled = pyqtSignal()

    play_pause_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()


    def __init__(self, player, parent=None):
        """Initializes the main vinyl widget, UI layouts, timers, and connects core signals."""
        super().__init__(parent)
        self.player = player
        self.setObjectName("vinylWidget")

        self.setMinimumSize(392, 392)

        self._is_mini_mode = False
        self._is_playing = False

        self._stylize_covers = True

        self._full_cover_pixmap = QPixmap()
        self._should_be_rotating = False
        self._is_unboxed = False
        self._vinyl_offset = 0

        self.queue_page_index = -1
        self.lyrics_page_index = -1

        self._slide_animation_group = None
        self._slide_label_out = None
        self._slide_label_in = None

        self._button_visibility_timer = QTimer(self)
        self._button_visibility_timer.setSingleShot(True)
        self._button_visibility_timer.setInterval(100)
        self._button_visibility_timer.timeout.connect(self._hide_buttons)

        self._current_mask_index = random.randint(1, 5)

        self._attached_control_panel = None

        self._setup_ui()
        self._setup_animation()
        self.hide()

    def _get_vinyl_offset(self):
        """Returns the current horizontal sliding offset of the vinyl record."""
        return self._vinyl_offset

    def _set_vinyl_offset(self, offset):
        """Sets the horizontal sliding offset of the vinyl record and forces a layout resize update."""
        if self._vinyl_offset != offset:
            self._vinyl_offset = offset
            self.resizeEvent(None)

    vinyl_offset = pyqtProperty(float, fget=_get_vinyl_offset, fset=_set_vinyl_offset)

    def set_stylize_covers(self, enabled: bool):
        """Enables or disables the texture mask overlay on the cover."""
        if self._stylize_covers == enabled:
            return

        self._stylize_covers = enabled

        if self._stylize_covers:
            mask_path = resource_path(f"assets/view/vinyl_mask_{self._current_mask_index}.png")
            self.full_cover_label.setMask(QPixmap(mask_path))
        else:
            self.full_cover_label.setMask(QPixmap())

    def _setup_ui(self):
        """Constructs and arranges the internal view stack, background layouts, buttons, and vinyl containers."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.view_stack = QStackedWidget()
        self.main_layout.addWidget(self.view_stack, 1)

        cover_page = QWidget()
        cover_page_layout = QVBoxLayout(cover_page)
        cover_page_layout.setContentsMargins(0, 0, 0, 0)
        cover_page_layout.setSpacing(0)

        self.main_background_widget = QWidget()
        self.main_background_widget.setObjectName("mainVinylBackground")

        self.background_layout = QVBoxLayout(self.main_background_widget)
        self.background_layout.setContentsMargins(0, 0, 0, 0)
        self.background_layout.setSpacing(0)

        self.vinyl_container = QWidget()
        self.vinyl_container.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.vinyl_container.installEventFilter(self)

        self.background_layout.addWidget(self.vinyl_container, 1)

        cover_page_layout.addWidget(self.main_background_widget)
        self.view_stack.addWidget(cover_page)

        self.vinyl_drawing_widget = VinylDrawingWidget(
            self.player, self.vinyl_container
        )

        self.vinyl_opacity_effect = QGraphicsOpacityEffect(self.vinyl_drawing_widget)
        self.vinyl_opacity_effect.setOpacity(0)
        self.vinyl_drawing_widget.setGraphicsEffect(self.vinyl_opacity_effect)

        self.full_cover_label = ScaledPixmapLabel(self.vinyl_container)

        if self._stylize_covers:
            mask_path = resource_path(f"assets/view/vinyl_mask_{self._current_mask_index}.png")
            self.full_cover_label.setMask(QPixmap(mask_path))
        else:
            self.full_cover_label.setMask(QPixmap())

        self.cover_opacity_effect = QGraphicsOpacityEffect(self.full_cover_label)
        self.cover_opacity_effect.setOpacity(1.0)
        self.full_cover_label.setGraphicsEffect(self.cover_opacity_effect)

        self.back_button = QPushButton(self)
        self.back_button.setProperty("class", "btnToolVinny")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            self.back_button,
            title = translate("Exit Vinyl mode"),
        )
        self.back_button.setIcon(
            create_svg_icon(
                "assets/control/view_normal.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.back_button.setIconSize(QSize(24, 24))
        self.back_button.setFixedSize(36, 36)
        apply_button_opacity_effect(self.back_button)
        self.back_button.clicked.connect(self.backClicked)
        self.back_button.installEventFilter(self)
        self.back_button.hide()

        self.unbox_button = QPushButton(self)
        self.unbox_button.setProperty("class", "btnToolVinny")
        self.unbox_button.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            self.unbox_button,
            title = translate("Show/hide record"),
        )
        self.unbox_button.setIcon(
            create_svg_icon(
                "assets/control/unbox.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.unbox_button.setIconSize(QSize(24, 24))
        self.unbox_button.setFixedSize(36, 36)
        apply_button_opacity_effect(self.unbox_button)
        self.unbox_button.clicked.connect(self._toggle_unboxing)
        self.unbox_button.installEventFilter(self)
        self.unbox_button.hide()


        self.mini_controls_container = QWidget(self)
        self.mini_controls_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.mini_controls_container.setProperty("class", "widgetVinnyHiddenControl")
        mini_layout = QHBoxLayout(self.mini_controls_container)
        mini_layout.setContentsMargins(8, 8, 8, 8)
        mini_layout.setSpacing(16)

        self.btn_mini_prev = QPushButton(self)
        self.btn_mini_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mini_prev.setFixedSize(36, 36)
        self.btn_mini_prev.setIcon(
            create_svg_icon("assets/control/skip_prev.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_mini_prev.setIconSize(QSize(24, 24))
        self.btn_mini_prev.setProperty("class", "btnToolVinny btnVinnyControl")
        set_custom_tooltip(
            self.btn_mini_prev,
            title = translate("Previous track"),
            hotkey = HotkeyManager.get_hotkey_str("prev_track")
        )
        apply_button_opacity_effect(self.btn_mini_prev)
        self.btn_mini_prev.clicked.connect(self.prev_clicked.emit)

        self.btn_mini_play = QPushButton(self)
        self.btn_mini_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mini_play.setFixedSize(36, 36)
        self.btn_mini_play.setIcon(
            create_svg_icon("assets/control/play.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_mini_play.setIconSize(QSize(24, 24))
        self.btn_mini_play.setProperty("class", "btnToolVinny btnVinnyControlPlay")
        set_custom_tooltip(
            self.btn_mini_play,
            title = translate("Play"),
            hotkey = HotkeyManager.get_hotkey_str("play_pause")
        )
        apply_button_opacity_effect(self.btn_mini_play)
        self.btn_mini_play.clicked.connect(self.play_pause_clicked.emit)

        self.btn_mini_next = QPushButton(self)
        self.btn_mini_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mini_next.setFixedSize(36, 36)
        self.btn_mini_next.setIcon(
            create_svg_icon("assets/control/skip_next.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_mini_next.setIconSize(QSize(24, 24))
        self.btn_mini_next.setProperty("class", "btnToolVinny btnVinnyControl")
        set_custom_tooltip(
            self.btn_mini_next,
            title = translate("Next track"),
            hotkey = HotkeyManager.get_hotkey_str("next_track")
        )
        apply_button_opacity_effect(self.btn_mini_next)
        self.btn_mini_next.clicked.connect(self.next_clicked.emit)

        self.btn_mini_expand = QPushButton(self)
        self.btn_mini_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mini_expand.setFixedSize(36, 36)
        self.btn_mini_expand.setIcon(
            create_svg_icon("assets/control/arrow_chevron_up.svg", theme.COLORS["PRIMARY"], QSize(24, 24)))
        self.btn_mini_expand.setIconSize(QSize(24, 24))
        self.btn_mini_expand.setProperty("class", "btnToolVinny btnVinnyControl")
        set_custom_tooltip(
            self.btn_mini_expand,
            title = translate("Show controls"),
        )
        apply_button_opacity_effect(self.btn_mini_expand)
        self.btn_mini_expand.clicked.connect(self.controlPanelToggled.emit)

        self.btn_mini_prev.installEventFilter(self)
        self.btn_mini_play.installEventFilter(self)
        self.btn_mini_next.installEventFilter(self)
        self.btn_mini_expand.installEventFilter(self)

        mini_layout.addWidget(self.btn_mini_prev)
        mini_layout.addWidget(self.btn_mini_play)
        mini_layout.addWidget(self.btn_mini_next)
        mini_layout.addWidget(self.btn_mini_expand)

        self.mini_controls_container.adjustSize()
        self.mini_controls_container.hide()

        self.vinyl_drawing_widget.scrubbingStarted.connect(self._on_scrub_start)
        self.vinyl_drawing_widget.positionScrubbed.connect(self.positionScrubbed)
        self.vinyl_drawing_widget.scrubbingFinished.connect(self._on_scrub_finish)

    def attach_control_panel(self, panel):
        """
        Attaches the ControlPanel as a floating overlay on top of the vinyl view.
        """
        if self._attached_control_panel == panel:
            return

        panel.setParent(self)

        panel.raise_()
        panel.show()

        self._attached_control_panel = panel

        self.resizeEvent(None)

    def detach_control_panel(self, panel):
        """
        Detaches the floating ControlPanel.
        """
        if self._attached_control_panel == panel:
            panel.hide()
            panel.setParent(None)
            self._attached_control_panel = None

    def set_mini_mode(self, enabled: bool):
        """
        Sets the mini-player mode state.
        Enabled = Panel Hidden (Show mini buttons).
        Disabled = Panel Visible.
        """
        self._is_mini_mode = enabled

        if enabled:
            self.mini_controls_container.show()
        else:
            self.mini_controls_container.hide()

        self._hide_buttons()

    def update_play_state(self, is_playing: bool):
        """Updates the play/pause icon in the mini controls."""
        self._is_playing = is_playing
        icon_name = "pause.svg" if is_playing else "play.svg"
        tooltip_text = translate("Pause") if is_playing else translate("Play")
        self.btn_mini_play.setIcon(
            create_svg_icon(f"assets/control/{icon_name}", theme.COLORS["PRIMARY"], QSize(56, 56))
        )
        set_custom_tooltip(
            self.btn_mini_play,
            title = tooltip_text,
            hotkey = HotkeyManager.get_hotkey_str("play_pause")
        )

    def add_queue_page(self, queue_widget):
        """Adds the provided widget as a playback queue page."""
        self.queue_page_index = self.view_stack.addWidget(queue_widget)

    def add_lyrics_page(self, lyrics_widget):
        """Adds the provided widget as a lyrics page."""
        self.lyrics_page_index = self.view_stack.addWidget(lyrics_widget)

    def toggle_stacked_view(self, show_queue):
        """Switches the view to cover or playback queue."""
        if show_queue and self.queue_page_index != -1:
            self.view_stack.setCurrentIndex(self.queue_page_index)
        else:
            self.view_stack.setCurrentIndex(0)
            self.resizeEvent(None)

    def toggle_lyrics_view(self, show_lyrics):
        """Switches the view to cover or lyrics."""
        if show_lyrics and self.lyrics_page_index != -1:
            self.view_stack.setCurrentIndex(self.lyrics_page_index)
        else:
            self.view_stack.setCurrentIndex(0)
            self.resizeEvent(None)

    def is_queue_visible(self):
        """Checks if the playback queue is currently visible."""
        return self.view_stack.currentIndex() == self.queue_page_index

    def is_lyrics_visible(self):
        """Checks if the lyrics are currently visible."""
        if self.lyrics_page_index == -1:
            return False
        return self.view_stack.currentIndex() == self.lyrics_page_index

    def update_unbox_button_state(self, is_enabled: bool):
        """Enables or disables the unbox button depending on track availability."""
        self.unbox_button.setEnabled(is_enabled)

    def _setup_animation(self):
        """Configures all property animations for vinyl rotation, unboxing offset, and cover fade/scaling."""
        self.animation = QPropertyAnimation(
            self.vinyl_drawing_widget, b"rotation", self
        )
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setDuration(5000)
        self.animation.setLoopCount(-1)
        self.animation.setEasingCurve(QEasingCurve.Type.Linear)

        self.cover_animation = QPropertyAnimation(
            self.full_cover_label, b"geometry", self
        )
        self.cover_animation.setDuration(800)
        self.cover_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.cover_animation.finished.connect(self._on_cover_animation_finished)

        self.vinyl_animation = QPropertyAnimation(self, b"vinyl_offset", self)
        self.vinyl_animation.setDuration(1200)
        self.vinyl_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)


        self.cover_opacity_anim = QPropertyAnimation(self.cover_opacity_effect, b"opacity", self)
        self.cover_opacity_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.cover_opacity_seq = QSequentialAnimationGroup(self)
        self.cover_opacity_seq.addPause(100)
        self.cover_opacity_seq.addAnimation(self.cover_opacity_anim)

        self.vinyl_opacity_anim = QPropertyAnimation(self.vinyl_opacity_effect, b"opacity", self)
        self.vinyl_opacity_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.vinyl_opacity_seq = QSequentialAnimationGroup(self)
        self.vinyl_opacity_seq.addPause(100)
        self.vinyl_opacity_seq.addAnimation(self.vinyl_opacity_anim)

    def _on_cover_animation_finished(self):
        """Called when the cover animation finishes to re-enable the button."""
        self.unbox_button.setEnabled(True)
        self.unbox_button.style().unpolish(self.unbox_button)
        self.unbox_button.style().polish(self.unbox_button)

    def _toggle_unboxing(self):
        """Toggles the vinyl unboxing animation by calculating target geometries and starting grouped animations."""
        self.unbox_button.setEnabled(False)
        container_rect = self.vinyl_container.rect()
        w, h = container_rect.width(), container_rect.height()

        PADDING = 48

        reserved_bottom_space = 0
        if not self._is_mini_mode:
            reserved_bottom_space = 200

        available_h = h - reserved_bottom_space

        base_size = min(w, available_h, MAX_SIZE)

        cover_full_rect = QRect(0, 0, base_size + PADDING, base_size + PADDING)

        cf_x = (w - cover_full_rect.width()) // 2
        cf_y = (available_h - cover_full_rect.height()) // 2
        cover_full_rect.moveTopLeft(QPoint(cf_x, cf_y))

        margin = 24

        vinyl_center_rect = QRect(0, 0, base_size - margin + PADDING, base_size - margin + PADDING)

        vc_x = (w - vinyl_center_rect.width()) // 2
        vc_y = (available_h - vinyl_center_rect.height()) // 2
        vinyl_center_rect.moveTopLeft(QPoint(vc_x, vc_y))

        cover_small_rect = QRect(vinyl_center_rect)

        shift_amount = base_size - margin
        cover_small_rect.moveLeft(vinyl_center_rect.left() - shift_amount)

        if not self._is_unboxed:
            self._is_unboxed = True

            self.cover_animation.setStartValue(cover_full_rect)
            self.cover_animation.setEndValue(cover_small_rect)
            self.vinyl_animation.setStartValue(80)
            self.vinyl_animation.setEndValue(0)

            self.cover_opacity_anim.setDuration(600)
            self.cover_opacity_anim.setStartValue(1.0)
            self.cover_opacity_anim.setEndValue(0.0)

            self.vinyl_opacity_anim.setDuration(1000)
            self.vinyl_opacity_anim.setStartValue(0.0)
            self.vinyl_opacity_anim.setEndValue(1.0)

            if self._should_be_rotating:
                self.start_rotation()
        else:
            self._is_unboxed = False

            self.cover_animation.setStartValue(cover_small_rect)
            self.cover_animation.setEndValue(cover_full_rect)
            self.vinyl_animation.setStartValue(0)
            self.vinyl_animation.setEndValue(30)

            self.cover_opacity_anim.setDuration(800)
            self.cover_opacity_anim.setStartValue(0.0)
            self.cover_opacity_anim.setEndValue(1.0)

            self.vinyl_opacity_anim.setDuration(600)
            self.vinyl_opacity_anim.setStartValue(1.0)
            self.vinyl_opacity_anim.setEndValue(0.0)

            if self.animation.state() == QPropertyAnimation.State.Running:
                self.animation.pause()

        self.cover_animation.start()
        self.vinyl_animation.start()
        self.cover_opacity_seq.start()
        self.vinyl_opacity_seq.start()

    def _on_scrub_start(self):
        """Handles the start of manual control by pausing automated rotation."""
        if self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.pause()
        self.scrubbingStarted.emit()

    def _on_scrub_finish(self):
        """Handles the end of manual control and resumes rotation if necessary."""
        self.scrubbingFinished.emit()
        if self._should_be_rotating:
            self.start_rotation()

    def set_cover(self, pixmap: QPixmap, direction = "forward"):
        """
        Sets the cover with a slide animation.
        Fixed: Render order to prevent layout jumps.
        """
        new_effective_pixmap = (
            pixmap
            if pixmap and not pixmap.isNull()
            else QPixmap(resource_path("assets/view/missing_vinyl.png"))
        )

        if self._full_cover_pixmap and not self._full_cover_pixmap.isNull():
            if new_effective_pixmap.cacheKey() != self._full_cover_pixmap.cacheKey():
                available_masks = [i for i in range(1, 5) if i != self._current_mask_index]
                self._current_mask_index = random.choice(available_masks)

                if self._stylize_covers:
                    mask_path = resource_path(f"assets/view/vinyl_mask_{self._current_mask_index}.png")
                    self.full_cover_label.setMask(QPixmap(mask_path))
                else:
                    self.full_cover_label.setMask(QPixmap())
            else:
                self._update_internal_content(pixmap)
                return

        if not self.isVisible() or not self.vinyl_container.isVisible():
            self._update_internal_content(pixmap)
            self.vinyl_drawing_widget._rotation = 0
            self.vinyl_drawing_widget.update()
            return

        if (
                self._slide_animation_group
                and self._slide_animation_group.state() == QPropertyAnimation.State.Running
        ):
            self._slide_animation_group.stop()
            self._cleanup_slide_animation()

        old_pixmap = self.main_background_widget.grab()

        self._slide_label_out = QLabel(self)
        self._slide_label_out.setPixmap(old_pixmap)

        container_pos = self.main_background_widget.mapTo(self, QPoint(0, 0))
        geom = QRect(container_pos, self.main_background_widget.size())

        self._slide_label_out.setGeometry(geom)
        self._slide_label_out.show()

        was_running = (
                              self.animation.state() == QPropertyAnimation.State.Running
                      ) or self._should_be_rotating
        self.animation.stop()
        self.vinyl_drawing_widget._rotation = 0
        self.vinyl_drawing_widget.update()

        self._update_internal_content(pixmap)

        self.resizeEvent(None)

        new_pixmap = self.main_background_widget.grab()

        self.main_background_widget.hide()

        self._slide_label_in = QLabel(self)
        self._slide_label_in.setPixmap(new_pixmap)

        shift_w = geom.width()

        if direction == "backward":
            end_rect_out = geom.translated(shift_w, 0)
            start_rect_in = geom.translated(-shift_w, 0)
        else:
            end_rect_out = geom.translated(-shift_w, 0)
            start_rect_in = geom.translated(shift_w, 0)

        self._slide_label_in.setGeometry(start_rect_in)
        self._slide_label_in.show()

        self.back_button.raise_()
        self.unbox_button.raise_()
        self.mini_controls_container.raise_()

        if self._attached_control_panel:
            self._attached_control_panel.raise_()

        self._slide_animation_group = QParallelAnimationGroup(self)

        anim_out = QPropertyAnimation(self._slide_label_out, b"geometry")
        anim_out.setDuration(500)
        anim_out.setStartValue(geom)
        anim_out.setEndValue(end_rect_out)
        anim_out.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim_in = QPropertyAnimation(self._slide_label_in, b"geometry")
        anim_in.setDuration(500)
        anim_in.setStartValue(start_rect_in)
        anim_in.setEndValue(geom)
        anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._slide_animation_group.addAnimation(anim_out)
        self._slide_animation_group.addAnimation(anim_in)

        if was_running:
            self._should_be_rotating = True
            self._slide_animation_group.finished.connect(self.start_rotation)

        self._slide_animation_group.finished.connect(self._cleanup_slide_animation)
        self._slide_animation_group.start()

    def _update_internal_content(self, pixmap):
        """Helper method to update the internal state of widgets."""

        self.vinyl_drawing_widget.set_cover_pixmap(pixmap)
        self._full_cover_pixmap = (
            pixmap
            if pixmap and not pixmap.isNull()
            else QPixmap(resource_path("assets/view/missing_vinyl.png"))
        )
        self.full_cover_label.setPixmap(self._full_cover_pixmap)

        base_color = get_dominant_color(self._full_cover_pixmap)
        noise_image = resource_path("assets/view/noise.png").replace("\\", "/")

        if IS_LINUX:
            style = f"""
                        #mainVinylBackground {{
                            background-color: {base_color.name()};
                            background-image: url('{noise_image}');
                            border-bottom-left-radius: {WINDOW_RADIUS}px;
                            border-bottom-right-radius: {WINDOW_RADIUS}px;
                        }}
                    """
        else:
            style = f"""
                        #mainVinylBackground {{
                            background-color: {base_color.name()};
                            background-image: url('{noise_image}');
                        }}
                    """
        self.main_background_widget.setStyleSheet(style)

        self.resizeEvent(None)

    def _cleanup_slide_animation(self):
        """Cleans up temporary widgets after animation."""
        if self._slide_label_out:
            self._slide_label_out.hide()
            self._slide_label_out.deleteLater()
            self._slide_label_out = None

        if self._slide_label_in:
            self._slide_label_in.hide()
            self._slide_label_in.deleteLater()
            self._slide_label_in = None

        self._slide_animation_group = None

        self.main_background_widget.show()

    def showEvent(self, event):
        """Handles widget show events and triggers a deferred layout resize."""
        super().showEvent(event)
        QTimer.singleShot(0, lambda: self.resizeEvent(None))


    def resizeEvent(self, event):
        """Handles widget resizing to correctly calculate layout and offset constraints for unbox animations."""
        if event:
            super().resizeEvent(event)

        w, h = self.width(), self.height()

        PADDING = 48

        reserved_bottom_space = 0
        if not self._is_mini_mode:
            reserved_bottom_space = 200

        available_h = h - reserved_bottom_space

        base_size = min(w, available_h, MAX_SIZE)

        margin = 24
        vinyl_widget_rect = QRect(0, 0, base_size - margin + PADDING, base_size - margin + PADDING)

        v_x = (w - vinyl_widget_rect.width()) // 2
        v_y = (available_h - vinyl_widget_rect.height()) // 2
        vinyl_widget_rect.moveTopLeft(QPoint(v_x, v_y))

        vinyl_widget_rect.moveLeft(int(vinyl_widget_rect.left() - self.vinyl_offset))

        self.vinyl_drawing_widget.setGeometry(vinyl_widget_rect)

        if self.cover_animation.state() != QPropertyAnimation.State.Running:
            if not self._is_unboxed:
                cover_widget_rect = QRect(0, 0, base_size + PADDING, base_size + PADDING)

                c_x = (w - cover_widget_rect.width()) // 2
                c_y = (available_h - cover_widget_rect.height()) // 2
                cover_widget_rect.moveTopLeft(QPoint(c_x, c_y))

                self.full_cover_label.setGeometry(cover_widget_rect)
            else:
                actual_vinyl_w = base_size - margin
                c_rect = QRect(self.vinyl_drawing_widget.geometry())
                c_rect.moveLeft(self.vinyl_drawing_widget.geometry().left() - actual_vinyl_w)
                self.full_cover_label.setGeometry(c_rect)

        if self._attached_control_panel and self._attached_control_panel.isVisible():
            panel = self._attached_control_panel
            panel_width = min(self.width(), 720)
            panel_height = panel.sizeHint().height()
            panel.resize(panel_width, panel_height)

            pos_x = (self.width() - panel_width) // 2
            pos_y = self.height() - panel_height

            if self.window().height() > (720 + 200 + 32) and self.window().width() > 720:
                pos_y -= 24

            panel.move(pos_x, pos_y)
            panel.raise_()

        btn_margin = 16
        self.back_button.move(btn_margin, btn_margin)
        self.unbox_button.move(self.width() - self.unbox_button.width() - btn_margin, btn_margin)

        cw, ch = self.mini_controls_container.width(), self.mini_controls_container.height()
        self.mini_controls_container.move((self.width() - cw) // 2, self.height() - ch - btn_margin)

    def _show_buttons(self):
        """Shows the floating buttons and stops the auto-hide timer."""
        self._button_visibility_timer.stop()
        self.back_button.show()
        self.unbox_button.show()

        if self._is_mini_mode:
            self.mini_controls_container.show()
        else:
            self.mini_controls_container.hide()

    def _hide_buttons(self):
        """Hides the buttons only if mouse is not hovering over them."""
        interactive_widgets = [
            self.vinyl_container,
            self.back_button,
            self.unbox_button,
            self.mini_controls_container,
            self.btn_mini_prev,
            self.btn_mini_play,
            self.btn_mini_next,
            self.btn_mini_expand
        ]

        for widget in interactive_widgets:
            if widget and widget.isVisible() and widget.underMouse():
                return

        self.back_button.hide()
        self.unbox_button.hide()
        self.mini_controls_container.hide()

    def eventFilter(self, source, event):
        """Filters events for the container and buttons to manage their visibility on hover."""
        if (not hasattr(self, "back_button")
            or not hasattr(self, "unbox_button")
            or not hasattr(self, "mini_controls_container")):
            return super().eventFilter(source, event)

        monitored_widgets = [
            self.vinyl_container,
        ]

        if source in monitored_widgets:
            if event.type() == QEvent.Type.Enter:
                self._show_buttons()
            elif event.type() == QEvent.Type.Leave:
                self._start_hide_timer()
        return super().eventFilter(source, event)

    def _start_hide_timer(self):
        """Starts the timer to hide the buttons after a short delay."""
        self._button_visibility_timer.start()

    def start_rotation(self):
        """Starts or resumes the vinyl record rotation animation."""
        self._should_be_rotating = True
        if not self._is_unboxed or self.vinyl_drawing_widget._is_scrubbing:
            return
        if self.animation.state() != QPropertyAnimation.State.Running:
            if self.animation.state() == QPropertyAnimation.State.Paused:
                self.animation.resume()
            else:
                self.animation.start()

    def stop_rotation(self):
        """Pauses the vinyl record rotation animation."""
        self._should_be_rotating = False
        if self.vinyl_drawing_widget._is_scrubbing:
            return
        if self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.pause()