"""
Vinyller — Custom widgets and classes
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
import json
import os
import re

from PyQt6.QtCore import (
    pyqtSignal, QByteArray, QEvent, QMimeData, QObject,
    QPoint, QRect, QRectF, QSize, Qt,
    QTimer
)
from PyQt6.QtGui import (
    QAction, QColor, QContextMenuEvent, QDrag, QIcon,
    QMouseEvent, QPainter, QPainterPath, QPen, QPixmap, QResizeEvent, QKeyEvent
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QCompleter, QFrame, QGraphicsOpacityEffect,
    QGridLayout,
    QLabel, QLayout, QLineEdit,
    QPushButton,
    QSizePolicy, QSlider,
    QStyle, QToolButton, QVBoxLayout, QWidget, QWidgetAction
)

from src.ui.custom_base_widgets import (
    StyledScrollArea,
    TranslucentCombo, TranslucentMenu, ShadowPopup, set_custom_tooltip
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


def highlight_text(text, query, bg_color_hex):
    """
    Wraps found occurrences of the query in a span tag with background color (bg_color_hex).
    Sets text color to white for contrast.
    """
    if not query or not text:
        return text

    escaped_query = re.escape(query)
    pattern = re.compile(f"({escaped_query})", re.IGNORECASE)

    return pattern.sub(
        f'<span style="background-color: {bg_color_hex}; color: {theme.COLORS.get("WHITE")}">\\1</span>',
        text,
    )


class ChartsPeriod:
    """Chart display periods."""
    MONTHLY = "monthly"
    ALL_TIME = "all_time"


class ViewMode:
    """List display modes."""
    GRID = 0
    TILE_BIG = 1
    TILE_SMALL = 2
    ALL_TRACKS = 3


class SearchMode:
    """Search categories"""
    EVERYWHERE = 0
    FAVORITES = 1
    ARTISTS = 2
    ALBUMS = 3
    GENRES = 4
    TRACKS = 5
    PLAYLISTS = 6
    COMPOSERS = 7
    LYRICS = 8


class SortMode:
    """Sorting modes."""
    ALPHA_ASC = 0
    ALPHA_DESC = 1
    YEAR_DESC = 2
    YEAR_ASC = 3
    ARTIST_ASC = 4
    ARTIST_DESC = 5
    DATE_ADDED_DESC = 6
    DATE_ADDED_ASC = 7


class HighDpiIconLabel(QWidget):
    """
    Widget for displaying  icons with correct Retina support.
    Forces the image to fit within the widget boundaries.
    """

    def __init__(self, pixmap, parent = None):
        """Initializes the high DPI icon label with the provided pixmap."""
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._pixmap = pixmap

    def setPixmap(self, pixmap):
        """Updates the pixmap displayed by the widget."""
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        """Draws the scaled pixmap with high DPI support."""
        if self._pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        dpr = self.devicePixelRatio()

        phy_w = int(self.width() * dpr)
        phy_h = int(self.height() * dpr)

        scaled = self._pixmap.scaled(
            QSize(phy_w, phy_h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        target_rect = QRectF(self.rect())
        source_rect = QRectF(scaled.rect())

        painter.drawPixmap(target_rect, scaled, source_rect)


class OverlayWidget(QWidget):
    """Widget for dimming the parent window."""

    def __init__(self, parent = None):
        """Initializes the overlay widget, defaulting to hidden and transparent for mouse events."""
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setVisible(False)
        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filters parent resize events to adjust the overlay geometry."""
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        """When showing the widget, resize it to match the parent and raise it to the top."""
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
            self.raise_()
        super().showEvent(event)


class RoundedCoverLabel(QWidget):
    """Widget for displaying cover art with rounded corners."""

    def __init__(self, pixmap, radius, parent = None):
        """Initializes the rounded cover label with the specified corner radius."""
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._pixmap = QPixmap(pixmap)
        self.radius = radius
        self._draw_overlay = False

    def setPixmap(self, pixmap):
        """Updates the cover art pixmap."""
        self._pixmap = QPixmap(pixmap)
        self.update()

    def setOverlayEnabled(self, enabled: bool):
        """Enables or disables the dark translucent overlay."""
        if self._draw_overlay != enabled:
            self._draw_overlay = enabled
            self.update()

    def paintEvent(self, event):
        """Paints the image, handling scaling, rounding, and overlays."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        dpr = self.devicePixelRatio()

        if not self._pixmap.isNull():
            path = QPainterPath()
            path.addRoundedRect(rect, self.radius, self.radius)
            painter.setClipPath(path)

            phy_w = int(self.width() * dpr)
            phy_h = int(self.height() * dpr)

            scaled_pixmap = self._pixmap.scaled(
                QSize(phy_w, phy_h),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )

            img_log_w = scaled_pixmap.width() / dpr
            img_log_h = scaled_pixmap.height() / dpr

            x = (self.width() - img_log_w) / 2
            y = (self.height() - img_log_h) / 2
            target_rect = QRectF(x, y, img_log_w, img_log_h)

            painter.drawPixmap(target_rect, scaled_pixmap, QRectF(scaled_pixmap.rect()))
            painter.setClipping(False)

        if self._draw_overlay:
            alpha = int(0.33 * 255)
            overlay_color = QColor(0, 0, 0, alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(overlay_color)
            painter.drawRoundedRect(rect, self.radius, self.radius)

        pen = QPen(QColor(0, 0, 0, int(255 * 0.07)))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        border_rect = rect.adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(border_rect, self.radius, self.radius)


class StackedCoverLabel(QWidget):
    """Widget for displaying a stack of cover art."""

    def __init__(self, pixmaps, radius, parent = None):
        """Initializes the stacked cover label with multiple pixmaps and a corner radius."""
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._pixmaps = pixmaps if pixmaps else []
        self.radius = radius
        self._draw_overlay = False

    def setPixmaps(self, pixmaps):
        """Updates the list of pixmaps to display in the stack."""
        self._pixmaps = pixmaps if pixmaps else []
        self.update()

    def setOverlayEnabled(self, enabled: bool):
        """Enables or disables the dark translucent overlay on the stack."""
        if self._draw_overlay != enabled:
            self._draw_overlay = enabled
            self.update()

    def paintEvent(self, event):
        """Draws the stacked images from bottom to top to create depth."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._pixmaps:
            return

        dpr = self.devicePixelRatio()

        pixmaps_to_draw = self._pixmaps[:3]
        num_pixmaps = len(pixmaps_to_draw)
        base_side_length = self.width()

        calculated_items = []

        for i in range(num_pixmaps - 1, -1, -1):
            pixmap = pixmaps_to_draw[i]
            size_reduction = i * 6
            new_side = base_side_length - size_reduction

            if new_side <= 0:
                continue

            offset_y = (num_pixmaps - 1 - i) * 8
            offset_x = size_reduction / 2

            rect = QRectF(offset_x, offset_y, new_side, new_side)
            calculated_items.append((rect, pixmap))

        for rect, pixmap in calculated_items:
            if pixmap.isNull():
                continue

            path = QPainterPath()
            path.addRoundedRect(rect, self.radius, self.radius)

            painter.save()
            painter.setClipPath(path)

            phy_w = int(rect.width() * dpr)
            phy_h = int(rect.height() * dpr)

            scaled_pixmap = pixmap.scaled(
                QSize(phy_w, phy_h),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )

            img_log_w = scaled_pixmap.width() / dpr
            img_log_h = scaled_pixmap.height() / dpr

            x = rect.x() + (rect.width() - img_log_w) / 2
            y = rect.y() + (rect.height() - img_log_h) / 2
            target_rect = QRectF(x, y, img_log_w, img_log_h)

            painter.drawPixmap(target_rect, scaled_pixmap, QRectF(scaled_pixmap.rect()))
            painter.restore()

        if self._draw_overlay:
            alpha = int(0.33 * 255)
            overlay_color = QColor(0, 0, 0, alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(overlay_color)

            finalOverlayPath = QPainterPath()
            for rect, _ in calculated_items:
                path = QPainterPath()
                path.addRoundedRect(rect, self.radius, self.radius)
                finalOverlayPath = finalOverlayPath.united(path)

            painter.drawPath(finalOverlayPath)

        pen = QPen(QColor(0, 0, 0, int(255 * 0.05)))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        paths = []
        for rect, _ in reversed(calculated_items):
            path = QPainterPath()
            path.addRoundedRect(
                rect.adjusted(0.5, 0.5, -0.5, -0.5), self.radius, self.radius
            )
            paths.append(path)

        path_to_subtract = QPainterPath()

        for path in paths:
            final_path_to_draw = path.subtracted(path_to_subtract)
            painter.drawPath(final_path_to_draw)
            path_to_subtract = path_to_subtract.united(path)


class ZoomableCoverLabel(QWidget):
    """Cover art widget with a 'Zoom' button on hover."""
    zoomRequested = pyqtSignal(QPixmap)

    def __init__(self, cover_pixmap, radius, parent = None):
        """Initializes the zoomable cover label and its interactive UI elements."""
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._clickable = True

        self.cover_label = RoundedCoverLabel(cover_pixmap, radius, self)
        self.overlay = QFrame(self)
        self.overlay.setStyleSheet(
            f"background-color: {theme.COLORS['HOVER_OVERLAY']}; border-radius: 3px; border: none;"
        )
        self.overlay.hide()
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        button_dim = 48
        icon_dim = int(button_dim * 0.75)

        self.zoom_button = QPushButton(self)
        self.zoom_button.setIcon(
            create_svg_icon(
                "assets/control/zoom.svg",
                theme.COLORS["WHITE"],
                QSize(icon_dim, icon_dim),
            )
        )
        self.zoom_button.setFixedSize(button_dim, button_dim)
        self.zoom_button.setIconSize(QSize(icon_dim, icon_dim))
        set_custom_tooltip(
            self.zoom_button,
            title = translate("View Image"),
        )
        self.zoom_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_button.setStyleSheet("border: none; background-color: none;")
        self.zoom_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.zoom_button.clicked.connect(self._on_zoom_clicked)

        self.opacity_effect = QGraphicsOpacityEffect(self.zoom_button)
        self.zoom_button.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.7)

        self.zoom_button.installEventFilter(self)
        self.zoom_button.hide()

    def setClickable(self, clickable):
        """Toggles the hover zoom interactions."""
        self._clickable = clickable
        if not clickable:
            self.overlay.hide()
            self.zoom_button.hide()

    def setPixmap(self, pixmap):
        """Updates the inner cover label pixmap."""
        self.cover_label.setPixmap(pixmap)
        self.update()

    def resizeEvent(self, event):
        """Ensures sub-widgets are resized when this widget resizes."""
        super().resizeEvent(event)
        size = event.size()
        self.cover_label.setGeometry(0, 0, size.width(), size.height())
        self.overlay.setGeometry(0, 0, size.width(), size.height())
        button_dim = self.zoom_button.width()
        self.zoom_button.move(
            (size.width() - button_dim) // 2, (size.height() - button_dim) // 2
        )

    def _on_zoom_clicked(self):
        """Emits the zoomRequested signal containing the cover pixmap."""
        if self._clickable and not self.cover_label._pixmap.isNull():
            self.zoomRequested.emit(self.cover_label._pixmap)

    def enterEvent(self, event: QEvent):
        """Shows the overlay and zoom button on mouse enter."""
        if self._clickable:
            self.overlay.show()
            self.zoom_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        """Hides the overlay and zoom button on mouse leave."""
        self.overlay.hide()
        self.zoom_button.hide()
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        """Manages the opacity transition for the zoom button."""
        if obj == self.zoom_button:
            if event.type() == QMouseEvent.Type.Enter:
                self.opacity_effect.setOpacity(1.0)
                return True
            elif event.type() == QMouseEvent.Type.Leave:
                self.opacity_effect.setOpacity(0.7)
                return True
        return super().eventFilter(obj, event)


class FlowLayout(QLayout):
    """Flow layout for arranging widgets."""

    def __init__(self, parent = None, stretch_items = False):
        """Initializes the flow layout with optional stretching configuration."""
        super().__init__(parent)
        self._stretch_items = stretch_items
        if parent is not None:
            self.setContentsMargins(0, 0, 0, 0)
        self._item_list = []

    def addItem(self, item):
        """Adds a layout item."""
        self._item_list.append(item)

    def count(self):
        """Returns the number of items in the layout."""
        return len(self._item_list)

    def itemAt(self, index):
        """Returns the layout item at the given index."""
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        """Removes and returns the layout item at the given index."""
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        """Indicates whether this layout expands (none by default)."""
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        """Indicates that the layout depends on width for calculating height."""
        return True

    def heightForWidth(self, width):
        """Calculates the height of the layout for a given width."""
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        """Sets the geometry of the layout and arranges the items."""
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        """Returns the preferred size of the layout."""
        return self.minimumSize()

    def minimumSize(self):
        """Calculates the minimum size required by the layout."""
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margin, _, _, _ = self.getContentsMargins()
        size += QSize(2 * margin, 2 * margin)
        return size

    def _do_layout(self, rect, test_only):
        """Determines placement strategy."""
        should_stretch = self._stretch_items

        if should_stretch and self._item_list:
            first_item = self._item_list[0]
            widget = first_item.widget()
            if widget:
                h_policy = widget.sizePolicy().horizontalPolicy()
                if h_policy == QSizePolicy.Policy.Fixed:
                    should_stretch = False

        if should_stretch:
            return self._do_layout_stretching(rect, test_only)
        else:
            return self._do_layout_simple(rect, test_only)

    def _do_layout_stretching(self, rect, test_only):
        """Layouts items dynamically, stretching them to fill available horizontal space."""
        x = rect.x()
        y = rect.y()

        if not self._item_list:
            return y

        prototype_item = self._item_list[0]
        widget = prototype_item.widget()
        if not widget:
            return self._do_layout_simple(rect, test_only)

        style = widget.style()
        spacing = self.spacing()

        layout_spacing_x = style.layoutSpacing(
            QSizePolicy.ControlType.PushButton,
            QSizePolicy.ControlType.PushButton,
            Qt.Orientation.Horizontal,
        )
        layout_spacing_y = style.layoutSpacing(
            QSizePolicy.ControlType.PushButton,
            QSizePolicy.ControlType.PushButton,
            Qt.Orientation.Vertical,
        )

        space_x = spacing + layout_spacing_x
        space_y = spacing + layout_spacing_y

        min_width = prototype_item.minimumSize().width()
        max_width = prototype_item.maximumSize().width()

        if min_width + space_x <= 0:
            return self._do_layout_simple(rect, test_only)

        num_cols = max(1, (rect.width() + space_x) // (min_width + space_x))
        available_width = rect.width() - (space_x * (num_cols - 1))
        target_width = available_width / num_cols
        final_width = int(max(min_width, min(target_width, max_width)))

        item_count = len(self._item_list)
        idx = 0

        while idx < item_count:
            row_items = []
            for _ in range(num_cols):
                if idx < item_count:
                    row_items.append(self._item_list[idx])
                    idx += 1
                else:
                    break

            current_row_height = 0
            for item in row_items:
                current_row_height = max(current_row_height, item.sizeHint().height())

            if not test_only:
                row_x = x
                for item in row_items:
                    item_h = item.sizeHint().height()
                    item_y_offset = int((current_row_height - item_h) / 2)

                    item.setGeometry(
                        QRect(row_x, y + item_y_offset, final_width, item_h)
                    )
                    row_x += final_width + space_x

            y += current_row_height + space_y

        return y - rect.y()

    def _do_layout_simple(self, rect, test_only):
        """Layouts items sequentially, wrapping to the next line when space runs out."""
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            widget = item.widget()
            if not widget:
                continue

            style = widget.style()
            layout_spacing_x = style.layoutSpacing(
                QSizePolicy.ControlType.PushButton,
                QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Horizontal,
            )
            layout_spacing_y = style.layoutSpacing(
                QSizePolicy.ControlType.PushButton,
                QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Vertical,
            )

            space_x = spacing + layout_spacing_x
            space_y = spacing + layout_spacing_y

            item_size = item.sizeHint()

            next_x = x + item_size.width() + space_x

            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item_size.width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y()


class ClickableCoverLabel(QWidget):
    """
    Widget for selecting cover art in the ArtworkSelectionWidget.
    Implements 3px rounding, 5% border, hand cursor, and hover overlay.
    """
    clicked = pyqtSignal(object)

    def __init__(self, pixmap, data, parent = None):
        """Initializes the clickable cover label with an image and assigned data."""
        super().__init__(parent)
        self.data = data
        self._pixmap = QPixmap(pixmap)
        self.radius = 3

        self.setFixedSize(64, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setProperty("class", "clickableCover")

        self.overlay = QFrame(self)
        self.overlay.setStyleSheet(
            f"background-color: {theme.COLORS['HOVER_OVERLAY']}; border: none; border-radius: 3px;"
        )
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.overlay.hide()

        self.replace_icon = QLabel(self)
        replace_pixmap = create_svg_icon(
            "assets/control/replace.svg", theme.COLORS["WHITE"], QSize(24, 24)
        ).pixmap(QSize(24, 24))
        self.replace_icon.setPixmap(replace_pixmap)
        self.replace_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.replace_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.replace_icon.hide()

    def resizeEvent(self, event):
        """Ensures overlay and icon scale with the widget."""
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())
        self.replace_icon.setGeometry(self.rect())

    def enterEvent(self, event):
        """Shows the replace overlay when the mouse enters the label."""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overlay.show()
        self.replace_icon.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hides the replace overlay when the mouse leaves."""
        self.overlay.hide()
        self.replace_icon.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Emits the clicked signal when left-clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        """Paints the scaled and rounded cover image with borders."""
        if self._pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(self.rect())
        dpr = self.devicePixelRatio()

        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        painter.save()
        painter.setClipPath(path)

        phy_w = int(self.width() * dpr)
        phy_h = int(self.height() * dpr)
        scaled_pixmap = self._pixmap.scaled(
            QSize(phy_w, phy_h),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        img_log_w = scaled_pixmap.width() / dpr
        img_log_h = scaled_pixmap.height() / dpr
        x = (self.width() - img_log_w) / 2
        y = (self.height() - img_log_h) / 2
        painter.drawPixmap(
            QRectF(x, y, img_log_w, img_log_h),
            scaled_pixmap,
            QRectF(scaled_pixmap.rect()),
        )
        painter.restore()

        pen = QPen(QColor(0, 0, 0, int(255 * 0.05)))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        border_rect = rect.adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(border_rect, self.radius, self.radius)


class ClickableProgressBar(QSlider):
    """Slider that moves on click."""

    def mousePressEvent(self, event):
        """Calculates value relative to click position and emits sliderReleased."""
        if event.button() == Qt.MouseButton.LeftButton:
            value = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), event.pos().x(), self.width()
            )
            self.setValue(value)
            self.sliderReleased.emit()
            super().mousePressEvent(event)


class ClickableSlider(QSlider):
    """A QSlider that allows clicking to set the value."""

    def mousePressEvent(self, event):
        """Updates the slider value instantly based on where the user clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.orientation() == Qt.Orientation.Horizontal:
                value = QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), event.pos().x(), self.width()
                )
            else:
                inverted_y = self.height() - event.pos().y()
                value = QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(), inverted_y, self.height()
                )

            self.setValue(value)
            super().mousePressEvent(event)


class ClickableWidget(QWidget):
    """Widget supporting clicks, double clicks, and context menus."""
    activated = pyqtSignal(object)
    contextMenuRequested = pyqtSignal(object, QPoint)

    def __init__(self, data, click_mode = "double", parent = None):
        """Initializes the clickable widget with its data and desired click mode."""
        super().__init__(parent)
        self.data = data
        self.click_mode = click_mode
        self.drag_start_position = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent):
        """Tracks the position of the left click to aid drag detection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Triggers the activated signal for single-click mode if it wasn't a drag."""
        if self.click_mode == "single":
            if (
                    event.button() == Qt.MouseButton.LeftButton
                    and self.drag_start_position is not None
            ):
                if (
                        event.pos() - self.drag_start_position
                ).manhattanLength() < QApplication.startDragDistance():
                    self.activated.emit(self.data)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Triggers the activated signal for double-click mode."""
        if self.click_mode == "double":
            self.activated.emit(self.data)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Emits a context menu request containing the object data and position."""
        self.contextMenuRequested.emit(self.data, event.globalPos())

    def mouseMoveEvent(self, event: QMouseEvent):
        """Initiates a drag operation if the user clicks and moves past the drag threshold."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self.drag_start_position is None:
            return
        if (
                event.pos() - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()

        data_str = ""

        if isinstance(self.data, dict):
            if "path" in self.data and "title" in self.data:
                data_str = f"track:{self.data['path']}"
            elif "type" in self.data and "name" in self.data:
                obj_type = self.data["type"]
                obj_name = self.data["name"]
                data_str = f"{obj_type}:{obj_name}"
            elif "path" in self.data:
                data_str = f"track:{self.data['path']}"

        elif isinstance(self.data, str):
            if self.data.lower().endswith((".m3u", ".m3u8")):
                data_str = f"playlist:{self.data}"
            elif os.path.isdir(self.data):
                data_str = f"folder:{self.data}"
            else:
                data_str = f"artist:{self.data}"

        elif isinstance(self.data, tuple):
            try:
                json_str = json.dumps(list(self.data))
                data_str = f"album_extended:{json_str}"
            except Exception:
                data_str = f"album:{self.data[0]}|{self.data[1]}"

        if data_str:
            mime_data.setData(
                "application/x-vinyller-data", QByteArray(data_str.encode("utf-8"))
            )
            drag.setMimeData(mime_data)

            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())

            drag.exec(Qt.DropAction.CopyAction)
            self.drag_start_position = None


class ElidedLabel(QLabel):
    """QLabel that automatically truncates text with '...' for a SINGLE line."""

    def __init__(self, text: str = "", parent = None, show_tooltip: bool = True):
        """Initializes the elided label with the given text."""
        super().__init__(text, parent)
        self._show_tooltip = show_tooltip
        self._original_text = ""
        self.setText(text)

    def setText(self, text: str):
        """Sets the label text and updates the tooltip with the unelided version."""
        text = text if text is not None else ""
        self._original_text = text

        if self._show_tooltip:
            safe_text = html.escape(text)
            set_custom_tooltip(
                self,
                title = safe_text,
            )

        self.updateGeometry()
        self._update_elided_text()

    def _update_elided_text(self):
        """Truncates the original text to fit the current label width."""
        fm = self.fontMetrics()
        elided = fm.elidedText(
            self._original_text, Qt.TextElideMode.ElideRight, self.width()
        )
        super().setText(elided)

    def resizeEvent(self, event: QResizeEvent):
        """Updates the elided text automatically when the label is resized."""
        super().resizeEvent(event)
        self._update_elided_text()

    def minimumSizeHint(self):
        """Allows the label to shrink to zero width while keeping its height."""
        return QSize(0, super().minimumSizeHint().height())

    def sizeHint(self):
        """Returns the natural size hint based on the original unelided text."""
        fm = self.fontMetrics()
        return fm.size(Qt.TextFlag.TextSingleLine, self._original_text)


class ClickableLabel(ElidedLabel):
    """ElidedLabel that emits a signal when clicked."""
    clicked = pyqtSignal(object)

    def __init__(self, data, text, parent = None):
        """Initializes the clickable label with assigned data and text styling."""
        super().__init__(text, parent = parent)
        self.data = data
        self.default_style = f"color: {theme.COLORS['TERTIARY']};"
        self.hover_style = f"color: {theme.COLORS['ACCENT']};"
        self.setMouseTracking(True)
        self.setStyleSheet(self.default_style)

        self._press_pos = None

        self.setText(text)

    def setText(self, text: str):
        """Sets the label text and updates the actionable tooltip."""
        super().setText(text)

        tooltip_text = f"{translate('Go to')} {text}" if text else None
        set_custom_tooltip(self, text = tooltip_text)

    def mousePressEvent(self, event: QMouseEvent):
        """Records the global position for drag determination on left clicks."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos_global = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Emits the clicked signal if the mouse release confirms a click."""
        if event.button() == Qt.MouseButton.LeftButton and getattr(self, '_press_pos_global', None):

            current_global_pos = event.globalPosition().toPoint()
            distance = (current_global_pos - self._press_pos_global).manhattanLength()

            if distance <= QApplication.startDragDistance():

                text_width = self.fontMetrics().horizontalAdvance(self.text())
                clickable_width = min(text_width, self.width())

                if self.rect().contains(event.pos()) and event.pos().x() <= clickable_width:
                    if self.data:
                        self.clicked.emit(self.data)

        self._press_pos_global = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Updates the cursor and text style based on hover position."""
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        if event.pos().x() <= text_width:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setStyleSheet(self.hover_style)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setStyleSheet(self.default_style)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Restores default styling and cursor when mouse leaves."""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setStyleSheet(self.default_style)
        super().leaveEvent(event)


class ClickableWordWrapLabel(QLabel):
    """WordWrapLabel that emits a signal when clicked."""
    clicked = pyqtSignal(object)

    def __init__(self, data, text, parent = None):
        """Initializes the clickable word-wrap label with assigned data and text styling."""
        super().__init__(text, parent = parent)
        self.data = data
        self.default_style = f"color: {theme.COLORS['TERTIARY']};"
        self.hover_style = f"color: {theme.COLORS['ACCENT']};"
        self.setMouseTracking(True)
        self.setStyleSheet(self.default_style)
        self._press_pos = None
        self.setText(text)

    def setText(self, text: str):
        """Sets the label text and standard tooltip formatting."""
        super().setText(text)
        set_custom_tooltip(self, text = text if text else None)

    def mousePressEvent(self, event: QMouseEvent):
        """Records local press position to ensure clean clicks."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Validates the click against drag thresholds and emits signal."""
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos:
            if (event.pos() - self._press_pos).manhattanLength() <= QApplication.startDragDistance():
                if self.rect().contains(event.pos()):
                    if self.data:
                        self.clicked.emit(self.data)

        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Adjusts the label hover styling dynamically."""
        if self.rect().contains(event.pos()):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setStyleSheet(self.hover_style)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setStyleSheet(self.default_style)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Resets default hover styling when the mouse leaves the widget area."""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setStyleSheet(self.default_style)
        super().leaveEvent(event)


class ClickableSeparatorLabel(QLabel):
    """QLabel that emits a signal when clicked."""
    clicked = pyqtSignal()

    def __init__(self, text, parent = None):
        """Initializes the clickable separator label."""
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event: QEvent):
        """Applies hover styling when mouse enters."""
        self.setStyleSheet(f"color: {theme.COLORS['ACCENT']};")
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        """Removes hover styling when mouse leaves."""
        self.setStyleSheet(f"color: {theme.COLORS['TERTIARY']};")
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Emits clicked signal immediately upon mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class AlphaJumpPopup(ShadowPopup):
    """Popup for quick alphabet navigation, inheriting shadow and styling from ShadowPopup."""
    letterSelected = pyqtSignal(str)

    def __init__(self, letters, parent = None):
        """Initializes the alpha jump popup with the provided letters grid."""
        super().__init__(parent)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._letters = letters

        self.container = QWidget(self)

        grid_layout = QGridLayout(self.container)
        grid_layout.setSpacing(4)
        grid_layout.setContentsMargins(8, 8, 8, 8)

        row, col = 0, 0
        cols = 6
        for letter in sorted(self._letters):
            btn = QPushButton(letter)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "btnAlphaJump")
            btn.setFixedHeight(36)
            btn.clicked.connect(self._on_letter_clicked)
            grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

        self.layout.addWidget(self.container)

        self.container.adjustSize()
        self.adjustSize()

    def _on_letter_clicked(self):
        """Emits the selected letter and closes the popup."""
        letter = self.sender().text()
        self.letterSelected.emit(letter)
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        """Handles keyboard selection and escape closing logic."""
        key_text = event.text().upper()
        if key_text in self._letters:
            self.letterSelected.emit(key_text)
            self.close()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


class InteractiveCoverWidget(ClickableWidget):
    """Cover art widget with 'Play'/'Pause' button on hover and informational icons."""
    playClicked = pyqtSignal()
    pauseClicked = pyqtSignal()

    def __init__(
            self,
            data,
            pixmap,
            size,
            icon_pixmap = None,
            disc_info_text = None,
            is_virtual = False,
            cue_icon_pixmap = None,
            parent = None,
    ):
        """Initializes the interactive cover widget and its overlay controls."""
        super().__init__(data = data, click_mode = "single", parent = parent)
        self.setFixedSize(size, size)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        self._is_current = False
        self._is_playing = False
        self._force_hover = False

        self.icon_pixmap = icon_pixmap
        self.disc_info_text = disc_info_text
        self.is_virtual = is_virtual
        self.cue_icon_pixmap = cue_icon_pixmap

        self.cover_label = RoundedCoverLabel(pixmap, 3, self)
        self.cover_label.setGeometry(0, 0, size, size)

        self.overlay = QFrame(self)
        self.overlay.setGeometry(0, 0, size, size)
        self.overlay.setStyleSheet(
            f"background-color: {theme.COLORS['HOVER_OVERLAY']}; border-radius: 3px; border: none;"
        )
        self.overlay.hide()
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        button_dim = 48
        icon_dim = int(button_dim * 0.8)

        self.play_button = QPushButton(self)
        self.play_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_button.setIcon(
            create_svg_icon(
                "assets/control/play_inverted.svg",
                theme.COLORS["WHITE"],
                QSize(icon_dim, icon_dim),
            )
        )
        self.play_button.setFixedSize(button_dim, button_dim)
        self.play_button.setIconSize(QSize(icon_dim, icon_dim))
        self.play_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_button.setStyleSheet("border: none; background-color: transparent;")
        self.play_button.clicked.connect(self.playClicked)

        self.play_opacity_effect = QGraphicsOpacityEffect(self.play_button)
        self.play_button.setGraphicsEffect(self.play_opacity_effect)
        self.play_opacity_effect.setOpacity(0.7)
        self.play_button.installEventFilter(self)
        self.play_button.hide()

        self.pause_button = QPushButton(self)
        self.pause_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pause_button.setIcon(
            create_svg_icon(
                "assets/control/pause_inverted.svg",
                theme.COLORS["WHITE"],
                QSize(icon_dim, icon_dim),
            )
        )
        self.pause_button.setFixedSize(button_dim, button_dim)
        self.pause_button.setIconSize(QSize(icon_dim, icon_dim))
        self.pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_button.setStyleSheet("border: none; background-color: transparent;")
        self.pause_button.clicked.connect(self.pauseClicked)

        self.pause_opacity_effect = QGraphicsOpacityEffect(self.pause_button)
        self.pause_button.setGraphicsEffect(self.pause_opacity_effect)
        self.pause_opacity_effect.setOpacity(0.7)
        self.pause_button.installEventFilter(self)
        self.pause_button.hide()

        self.type_icon_label = None
        self.disc_info_label = None
        self.cue_icon_label = None
        self._update_badges()

    def _update_badges(self):
        """Creates or updates informational badges on the cover."""
        size = self.width()

        if self.is_virtual and self.cue_icon_pixmap:
            if not self.cue_icon_label:
                self.cue_icon_label = HighDpiIconLabel(self.cue_icon_pixmap, self)
            self.cue_icon_label.setPixmap(self.cue_icon_pixmap)
            self.cue_icon_label.setFixedSize(16, 16)
            self.cue_icon_label.move(size - 20, 4)
            self.cue_icon_label.show()
        elif self.cue_icon_label:
            self.cue_icon_label.hide()

        if self.icon_pixmap:
            if not self.type_icon_label:
                self.type_icon_label = HighDpiIconLabel(self.icon_pixmap, self)
            self.type_icon_label.setPixmap(self.icon_pixmap)
            self.type_icon_label.setFixedSize(16, 16)
            self.type_icon_label.move(size - 20, size - 20)
            self.type_icon_label.show()
        elif self.type_icon_label:
            self.type_icon_label.hide()

        if self.disc_info_text:
            if not self.disc_info_label:
                self.disc_info_label = QLabel(self)
                self.disc_info_label.setProperty(
                    "class", "textSecondary bold textColorWhite"
                )
            self.disc_info_label.setText(self.disc_info_text)
            self.disc_info_label.adjustSize()

            x_pos = size - self.disc_info_label.width() - 4
            if self.icon_pixmap:
                x_pos -= 20
            self.disc_info_label.move(x_pos, size - self.disc_info_label.height() - 2)
            self.disc_info_label.show()
        elif self.disc_info_label:
            self.disc_info_label.hide()

    def resizeEvent(self, event):
        """Ensures badges, labels, and overlays maintain correct sizing during resize."""
        super().resizeEvent(event)
        size = self.width()
        self.cover_label.setGeometry(0, 0, size, size)
        self.overlay.setGeometry(0, 0, size, size)

        btn_size = self.play_button.width()
        pos = (size - btn_size) // 2
        self.play_button.move(pos, pos)
        self.pause_button.move(pos, pos)

        self._update_badges()

    def update_playback_state(self, is_current, is_playing):
        """Updates the widget's playback state."""
        changed = self._is_current != is_current or self._is_playing != is_playing
        if changed:
            self._is_current = is_current
            self._is_playing = is_playing
            self._update_visuals()

    def _update_visuals(self):
        """Updates button visibility based on state and hover."""
        try:
            is_hover = self.underMouse() or self._force_hover

            if is_hover:
                self.overlay.show()
                if self._is_current and self._is_playing:
                    self.pause_button.show()
                    self.play_button.hide()
                else:
                    self.play_button.show()
                    self.pause_button.hide()
            else:
                self.overlay.hide()
                self.play_button.hide()
                self.pause_button.hide()
        except RuntimeError:
            pass

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Maintains the hover state while displaying the context menu."""
        self._force_hover = True
        self._update_visuals()

        super().contextMenuEvent(event)

        self._force_hover = False
        self._update_visuals()

    def enterEvent(self, event: QEvent):
        """Applies visual hover states on mouse enter."""
        self._update_visuals()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        """Removes visual hover states on mouse leave."""
        self._update_visuals()
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        """Intercepts internal button hover events to apply dynamic opacity adjustments."""
        effect_to_change = None
        if obj is self.play_button:
            effect_to_change = self.play_opacity_effect
        elif obj is self.pause_button:
            effect_to_change = self.pause_opacity_effect

        if effect_to_change:
            if event.type() == QEvent.Type.Enter:
                effect_to_change.setOpacity(1.0)
                return True
            elif event.type() == QEvent.Type.Leave:
                effect_to_change.setOpacity(0.7)
                return True
        return super().eventFilter(obj, event)


class ArtworkSelectionWidget(QWidget):
    """A widget for displaying a grid of album covers for selection."""
    artworkSelected = pyqtSignal(str)

    def __init__(
            self,
            sorted_artworks,
            get_pixmap_func,
            encyclopedia_image_path = None,
            parent = None,
    ):
        """Initializes the artwork selection grid with available album covers."""
        super().__init__(parent)
        self.get_pixmap = get_pixmap_func
        self.setContentsMargins(8, 8, 8, 8)
        self.setProperty("class", "backgroundPrimary")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_area = StyledScrollArea()
        scroll_area.setContentsMargins(0, 0, 0, 0)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        scroll_content = QWidget()
        scroll_content.setContentsMargins(0, 0, 0, 0)
        scroll_content.setProperty("class", "backgroundPrimary")
        scroll_content.setCursor(Qt.CursorShape.ArrowCursor)

        self.grid_layout = QGridLayout(scroll_content)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(4)

        row, col = 0, 0
        cols = 4

        if encyclopedia_image_path and os.path.exists(encyclopedia_image_path):
            pixmap = self.get_pixmap(encyclopedia_image_path, 64)
            label = ClickableCoverLabel(pixmap, encyclopedia_image_path, self)
            set_custom_tooltip(
                label,
                title = translate("Encyclopedia Image"),
            )

            self.grid_layout.addWidget(label, row, col)
            label.clicked.connect(self.on_artwork_clicked)

            col += 1
            if col >= cols:
                col = 0
                row += 1

        artwork_paths = []
        for _, art_dict in sorted_artworks:
            artwork_paths.append(art_dict)

        for i, artwork_dict in enumerate(artwork_paths):
            album_title, _ = sorted_artworks[i]
            pixmap = self.get_pixmap(artwork_dict, 64)
            representative_path = next(iter(artwork_dict.values()), None)

            if representative_path == encyclopedia_image_path:
                continue

            label = ClickableCoverLabel(pixmap, representative_path, self)
            set_custom_tooltip(
                label,
                title = album_title,
            )
            label.clicked.connect(self.on_artwork_clicked)
            self.grid_layout.addWidget(label, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        total_items = len(artwork_paths) + (1 if encyclopedia_image_path else 0)
        max_height = 320
        num_rows = (total_items + cols - 1) // cols
        if num_rows == 0:
            num_rows = 1

        content_height = (
                num_rows * (64 + self.grid_layout.spacing()) + 8
        )
        self.setFixedHeight(min(content_height + 32, max_height))
        self.setFixedWidth(cols * (64 + self.grid_layout.spacing()) + 32)

    def on_artwork_clicked(self, path):
        """Emits the selected artwork path and propagates closing of parent menus."""
        self.artworkSelected.emit(path)
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, TranslucentMenu):
                parent.close()
                break
            parent = parent.parentWidget()


class EntityCoverButton(QToolButton):
    """Universal button for displaying and selecting a cover (Artist, Genre, Composer)."""
    artworkChanged = pyqtSignal(str, str)

    def __init__(
            self,
            entity_name: str,
            entity_data: dict,
            albums_of_entity: list,
            entity_type: str,
            get_pixmap_func,
            main_window = None,
            parent = None,
    ):
        """Initializes the interactive entity cover widget."""
        super().__init__(parent)
        self.entity_name = entity_name
        self.entity_data = entity_data
        self.albums_of_entity = albums_of_entity
        self.entity_type = entity_type
        self.get_pixmap = get_pixmap_func
        self.mw = main_window

        self.setProperty("class", "btnCover")
        self.setIconSize(QSize(36, 36))
        self.setFixedSize(36, 36)
        self.setMouseTracking(True)

        unique_options = set()

        for _, album_data in self.albums_of_entity:
            if artwork_dict := album_data.get("artwork"):
                rep_path = next(iter(sorted(artwork_dict.values())), None)
                if rep_path:
                    unique_options.add(rep_path)

        has_enc_image = False
        if self.mw:
            entry = self.mw.encyclopedia_manager.get_entry(self.entity_name, self.entity_type)
            if entry and (enc_path := entry.get("image_path")):
                has_enc_image = True
                unique_options.add(enc_path)

        self._can_change = len(unique_options) > 1

        self._menu_just_closed = False
        self._menu_close_timer = QTimer(self)
        self._menu_close_timer.setSingleShot(True)
        self._menu_close_timer.setInterval(300)
        self._menu_close_timer.timeout.connect(self._reset_menu_flag)

        self.overlay = QFrame(self)
        self.overlay.setStyleSheet(
            f"background-color: {theme.COLORS['HOVER_OVERLAY']}; border: none; border-radius: 3px;"
        )
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.overlay.hide()

        self.replace_icon = QLabel(self)
        pixmap = create_svg_icon(
            "assets/control/replace.svg", theme.COLORS["WHITE"], QSize(20, 20)
        ).pixmap(QSize(20, 20))
        self.replace_icon.setPixmap(pixmap)
        self.replace_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.replace_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.replace_icon.hide()

        if not self._can_change:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            set_custom_tooltip(
                self,
                title = translate("No other covers available"),
                text = translate("You can create an encyclopedia article to add an additional image"),
            )
            self.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            set_custom_tooltip(
                self,
                title = translate("Select cover"),
                text = translate("You can create an encyclopedia article to add an additional image"),
            )
            self.clicked.connect(self.show_artwork_menu)
            self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.update_icon()

    def _reset_menu_flag(self):
        """Resets the flag tracking if the menu was recently closed."""
        self._menu_just_closed = False

    def resizeEvent(self, event: QResizeEvent):
        """Updates the geometries of the overlay and icon on resize."""
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())
        self.replace_icon.setGeometry(self.rect())

    def enterEvent(self, event):
        """Displays the overlay and replacement icon on hover if changes are allowed."""
        if self.isEnabled() and self._can_change:
            self.overlay.show()
            self.replace_icon.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hides the overlay and replacement icon when the mouse leaves."""
        self.overlay.hide()
        self.replace_icon.hide()
        super().leaveEvent(event)

    def update_icon(self):
        """Re-renders the button icon based on the primary artwork data."""
        artworks = self.entity_data.get("artworks", [])
        primary_artwork_dict = artworks[0] if artworks else None

        source_pixmap = self.get_pixmap(primary_artwork_dict, 48)
        target_size = self.iconSize()

        final_pixmap = QPixmap(target_size)
        final_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(final_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(final_pixmap.rect())
        radius = 3

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(rect.toRect(), source_pixmap)
        painter.setClipping(False)

        pen = QPen(QColor(0, 0, 0, int(255 * 0.05)))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        border_rect = rect.adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(border_rect, radius, radius)

        painter.end()
        self.setIcon(QIcon(final_pixmap))

    def show_artwork_menu(self):
        """Displays a popup menu for selecting an alternative cover."""
        if self._menu_just_closed:
            return

        artwork_to_album = {}
        for album_key, album_data in self.albums_of_entity:
            if artwork_dict := album_data.get("artwork"):
                album_title = album_key[1]
                artwork_frozenset = frozenset(artwork_dict.items())
                if artwork_frozenset not in artwork_to_album:
                    artwork_to_album[artwork_frozenset] = (album_title, artwork_dict)

        enc_image_path = None
        if self.mw:
            entry = self.mw.encyclopedia_manager.get_entry(self.entity_name, self.entity_type)
            if entry and entry.get("image_path"):
                enc_image_path = entry["image_path"]

        if not artwork_to_album and not enc_image_path:
            return

        sorted_artworks = sorted(artwork_to_album.values(), key = lambda x: x[0])

        menu = TranslucentMenu(self)
        menu.setProperty("class", "popMenu")

        selection_widget = ArtworkSelectionWidget(
            sorted_artworks, self.get_pixmap, encyclopedia_image_path = enc_image_path
        )
        selection_widget.artworkSelected.connect(self.on_artwork_selected)

        action = QWidgetAction(menu)
        action.setDefaultWidget(selection_widget)
        menu.addAction(action)

        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

        self._menu_just_closed = True
        self._menu_close_timer.start()

        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def on_artwork_selected(self, new_artwork_path):
        """Emits a signal when a new artwork path is selected."""
        self.artworkChanged.emit(self.entity_name, new_artwork_path)


class ButtonOpacityEffect(QObject):
    """
    Class for managing button opacity effect based on its state
    (hover, pressed, enabled).
    """

    def __init__(self, parent):
        """Initializes the opacity effect manager for the given button."""
        super().__init__(parent)
        self.button = parent
        self.effect = QGraphicsOpacityEffect(self.button)
        self.button.setGraphicsEffect(self.effect)

        if self.button.isCheckable():
            self.button.toggled.connect(self._update_opacity)

        self._update_opacity()

    def eventFilter(self, obj, event):
        """Intercepts internal UI events to evaluate if visual opacity requires adjustment."""
        if obj is not self.button:
            return False

        if event.type() in {
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.EnabledChange,
            QEvent.Type.Polish,
        }:
            self._update_opacity()

        return False

    def _update_opacity(self, *args):
        """Updates button opacity according to its current state."""
        button = self.button
        is_active = button.property("active")

        if not button.isEnabled():
            self.effect.setOpacity(0.4)
        elif (button.isCheckable() and button.isChecked()) or is_active:
            self.effect.setOpacity(
                1.0
            )
        elif button.underMouse():
            self.effect.setOpacity(1.0)
        else:
            self.effect.setOpacity(0.7)


def apply_button_opacity_effect(button):
    """
    Applies a hover opacity effect to a button.
    Creates and sets an event handler for the specified button.
    """
    if not hasattr(button, "_opacity_handler"):
        button._opacity_handler = ButtonOpacityEffect(button)
        button.installEventFilter(button._opacity_handler)


class LabelOpacityEffect(QObject):
    """
    Class for managing label opacity effect based on its state
    (hover, active property, enabled).
    """

    def __init__(self, parent):
        """Initializes the opacity effect manager for the given label."""
        super().__init__(parent)
        self.label = parent
        self.effect = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(self.effect)

        self.label.setAttribute(Qt.WidgetAttribute.WA_Hover)

        self._update_opacity()

    def eventFilter(self, obj, event):
        """Watches for visual status changes and recomputes layout opacity."""
        if obj is not self.label:
            return False

        if event.type() in {
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.EnabledChange,
            QEvent.Type.Polish,
            QEvent.Type.DynamicPropertyChange
        }:
            self._update_opacity()

        return False

    def _update_opacity(self, *args):
        """Updates label opacity according to its current state."""
        label = self.label
        is_active = label.property("active")

        if not label.isEnabled():
            self.effect.setOpacity(0.4)
        elif is_active:
            self.effect.setOpacity(0.7)
        elif label.underMouse():
            self.effect.setOpacity(0.7)
        else:
            self.effect.setOpacity(0.7)


def apply_label_opacity_effect(label):
    """
    Applies a hover opacity effect to a label.
    Creates and sets an event handler for the specified label.
    """
    if not hasattr(label, "_opacity_handler"):
        label._opacity_handler = LabelOpacityEffect(label)
        label.installEventFilter(label._opacity_handler)


class RadialProgressButton(QToolButton):
    """
    QToolButton with an integrated radial progress bar that
    activates during processing.
    """

    def __init__(self, parent = None):
        """Initializes the radial progress button and its internal timers."""
        super().__init__(parent)
        self._is_processing = False
        self._is_indeterminate = False
        self._progress = 0
        self._max_value = 100
        self._indeterminate_angle = 0

        self._indeterminate_timer = QTimer(self)
        self._indeterminate_timer.setInterval(20)
        self._indeterminate_timer.timeout.connect(self._update_indeterminate_animation)

    def setProcessing(self, is_processing: bool):
        """Enables or disables progress display mode."""
        if self._is_processing == is_processing:
            return

        self._is_processing = is_processing
        if not is_processing:
            self.setIndeterminate(False)
            self.reset()
        self.update()

    def setIndeterminate(self, is_indeterminate: bool):
        """Sets whether the progress bar should be indeterminate (spinning)."""
        if self._is_indeterminate == is_indeterminate:
            return

        self._is_indeterminate = is_indeterminate
        if is_indeterminate:
            self._indeterminate_angle = 0
            if not self._indeterminate_timer.isActive():
                self._indeterminate_timer.start()
        else:
            if self._indeterminate_timer.isActive():
                self._indeterminate_timer.stop()
        self.update()

    def setRange(self, min_val: int, max_val: int):
        """Sets the range for the determinate progress bar."""
        self._max_value = max_val
        self.update()

    def setValue(self, value: int):
        """Sets the current progress value."""
        self._progress = value
        self.update()

    def reset(self):
        """Resets the progress."""
        self._progress = 0
        self._max_value = 100
        self._is_indeterminate = False
        self.update()

    def _update_indeterminate_animation(self):
        """Updates the angle for indeterminate progress animation."""
        self._indeterminate_angle = (self._indeterminate_angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        """Overridden paintEvent to draw the button and progress bar."""
        super().paintEvent(event)

        if not self._is_processing:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(theme.COLORS["ACCENT"]))
        pen.setWidth(4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        rect_margin = 8
        rect = QRectF(self.rect()).adjusted(
            rect_margin, rect_margin, -rect_margin, -rect_margin
        )

        if self._is_indeterminate:
            start_angle = self._indeterminate_angle * 16
            span_angle = 90 * 16
            painter.drawArc(rect, start_angle, span_angle)

        elif self._max_value > 0:
            progress_ratio = self._progress / self._max_value
            start_angle = 90 * 16
            span_angle = int(-progress_ratio * 360 * 16)
            painter.drawArc(rect, start_angle, span_angle)


class AccentIconFactory:
    """
    Factory for creating square icons with accent color background
    and rounded corners. Automatically switches to dark icon variant (_dk)
    if the accent color is too bright.
    """

    @staticmethod
    def create(
            icon_path: str, size: int, radius: int = 4, icon_scale: float = 1
    ) -> QPixmap:
        """
        icon_path: Path to the source transparent PNG (default white icon).
        size: Output square size (e.g., 128 or 48).
        radius: Corner radius.
        icon_scale: Icon scale relative to the background (0.6 = 60% of size).
        """
        result_pixmap = QPixmap(size, size)
        result_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        accent_color = QColor(theme.COLORS["ACCENT"])

        r, g, b = accent_color.red(), accent_color.green(), accent_color.blue()
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        if brightness < 52:
            base, ext = os.path.splitext(icon_path)
            dk_icon_path = f"{base}_dk{ext}"

            if os.path.exists(dk_icon_path):
                icon_path = dk_icon_path

        rect = QRectF(0, 0, size, size)

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, accent_color)

        if icon_path and os.path.exists(icon_path):
            source_icon = QPixmap(icon_path)
            if not source_icon.isNull():
                icon_size = int(size * icon_scale)

                scaled_icon = source_icon.scaled(
                    icon_size,
                    icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                x = (size - scaled_icon.width()) // 2
                y = (size - scaled_icon.height()) // 2

                painter.drawPixmap(x, y, scaled_icon)

        painter.end()
        return result_pixmap


class GapCompleter(QCompleter):
    """
    QCompleter with a gap, without system shadow, and with transparent window background.
    """

    def __init__(self, model, parent = None, gap = 6):
        """Initializes the gap completer and customizes its popup window flags."""
        super().__init__(model, parent)
        self.gap = gap

        popup = self.popup()

        popup.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )

        popup.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Catches visibility and move events to apply the custom popup position gap."""
        if obj == self.popup():
            if event.type() in (QEvent.Type.Show, QEvent.Type.Resize, QEvent.Type.Move):
                QTimer.singleShot(0, self._force_offset)

        return super().eventFilter(obj, event)

    def _force_offset(self):
        """Manually overrides the Y coordinate of the popup to impose a visual gap."""
        popup = self.popup()
        target = self.widget()

        if not popup or not target or not popup.isVisible():
            return

        target_global_pos = target.mapToGlobal(target.rect().bottomLeft())
        target_bottom_y = target_global_pos.y()

        geo = popup.geometry()

        if geo.top() >= target_bottom_y - 5:
            desired_y = target_bottom_y + self.gap

            if abs(geo.top() - desired_y) > 1:
                geo.moveTop(desired_y)
                popup.setGeometry(geo)


class MetadataMergeControl(TranslucentCombo):
    """
    ComboBox for selecting or entering metadata.
    Highlighted if the value has been changed.
    Has a reset (undo) button if the value differs from the original.
    """

    def __init__(
            self,
            current_value,
            fetched_value = None,
            border_style = "inputBorderSinglePadding",
            parent = None,
    ):
        """Initializes the metadata merge control and sets up UI logic."""
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.border_style = border_style

        self.current_val = (
            str(current_value).strip() if current_value is not None else ""
        )
        self.fetched_val = ""

        self.reset_action = QAction(self)
        self.reset_action.setIcon(
            QIcon(
                create_svg_icon(
                    "assets/control/undo.svg", theme.COLORS["ACCENT"], QSize(16, 16)
                )
            )
        )

        set_custom_tooltip(
            self.reset_action,
            title = translate("Reset to original value"),
        )
        self.reset_action.triggered.connect(self.reset_to_original)

        if self.lineEdit():
            self.lineEdit().setReadOnly(True)
            self.lineEdit().installEventFilter(self)
            self.lineEdit().textChanged.connect(self._update_style)

            self.lineEdit().addAction(
                self.reset_action, QLineEdit.ActionPosition.TrailingPosition
            )

        self.currentIndexChanged.connect(self._update_style)

        self.set_fetched_value(fetched_value)
        self._update_style()

    def _update_style(self):
        """Updates the styling depending on whether the metadata was modified."""
        current_text = self.currentText().strip()

        is_modified = current_text != self.current_val

        if is_modified:
            color_class = "textColorAccent"
            self.reset_action.setVisible(True)
        else:
            color_class = "textColorPrimary"
            self.reset_action.setVisible(False)

        full_class = f"{self.border_style} {color_class}"
        self.setProperty("class", full_class)

        self.style().unpolish(self)
        self.style().polish(self)

    def set_reset_value(self, value):
        """Sets a new base value and refreshes the style constraints."""
        self.current_val = str(value).strip() if value is not None else ""
        self._update_style()

    def reset_to_original(self):
        """Resets the value to the original (current_val)."""
        if self.count() > 0:
            self.setCurrentIndex(0)

        self.setEditText(self.current_val)

        if self.lineEdit():
            self.lineEdit().setCursorPosition(0)

    def showPopup(self):
        """Modifies and launches the selection popup to ensure text visibility."""
        view = self.view()
        combo_width = self.width()
        fm = self.fontMetrics()
        max_text_width = 0
        for i in range(self.count()):
            text = self.itemText(i)
            w = fm.horizontalAdvance(text)
            if w > max_text_width:
                max_text_width = w
        popup_width = max_text_width + 40
        view.setMinimumWidth(max(combo_width, popup_width))
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        super().showPopup()

    def update_current_value(self, value):
        """Sets the new finalized value and clears fetched history."""
        self.current_val = str(value).strip() if value is not None else ""
        self.set_fetched_value(None)

    def set_fetched_value(self, fetched_value):
        """Populates the combo box options with existing versus fetched metadata."""
        self.blockSignals(True)
        self.clear()
        self.fetched_val = (
            str(fetched_value).strip() if fetched_value is not None else ""
        )

        if self.fetched_val and self.fetched_val != self.current_val:
            text_old = (
                translate("Keep {value}", value = self.current_val)
                if self.current_val
                else translate("Keep (empty)")
            )
            self.addItem(text_old)
            self.setItemData(0, self.current_val, Qt.ItemDataRole.UserRole)
            self.setItemData(0, text_old, Qt.ItemDataRole.ToolTipRole)

            text_new = translate("Replace with {value}", value = self.fetched_val)
            self.addItem(text_new)
            self.setItemData(1, self.fetched_val, Qt.ItemDataRole.UserRole)
            self.setItemData(1, text_new, Qt.ItemDataRole.ToolTipRole)
            self.setCurrentIndex(1)
        else:
            self.addItem(self.current_val)
            self.setItemData(0, self.current_val, Qt.ItemDataRole.UserRole)
            self.setCurrentIndex(0)

        if self.lineEdit():
            self.lineEdit().setCursorPosition(0)

        self.blockSignals(False)
        self._update_style()

    def get_final_value(self):
        """Returns the ultimate selected text or validated data object."""
        idx = self.currentIndex()
        current_text = self.currentText()
        if idx >= 0 and current_text == self.itemText(idx):
            data = self.itemData(idx, Qt.ItemDataRole.UserRole)
            if data is not None:
                return str(data)
            return current_text.strip()
        else:
            return current_text.strip()

    def eventFilter(self, obj, event):
        """Filters input box interactions enabling read-only toggle behavior."""
        if obj == self.lineEdit():
            if event.type() == QEvent.Type.MouseButtonPress:
                if obj.isReadOnly():
                    obj.setReadOnly(False)
            elif event.type() == QEvent.Type.FocusOut:
                obj.setReadOnly(True)
                obj.setCursorPosition(0)
        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        """Overrides and ignores wheel events to prevent accidental scrolling changes."""
        event.ignore()


class RotatingIconLabel(QLabel):
    """A label that displays an auto-rotating icon animation."""

    def __init__(
            self, icon_path, size = QSize(48, 48), color = None, interval = 30, parent = None
    ):
        """Initializes the rotating icon label and starts the animation timer."""
        super().__init__(parent)
        self.setFixedSize(size)

        self._icon_path = icon_path
        self._icon_color = color if color else theme.COLORS.get("PRIMARY")
        self.target_size = size

        self.frames = []
        self.current_frame = 0

        self._cache_frames()

        if self.frames:
            self.setPixmap(self.frames[0])

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_frame)
        self.timer.start(interval)

    def _cache_frames(self):
        """Pre-render all 36 rotation frames."""
        base_icon = create_svg_icon(self._icon_path, self._icon_color, self.target_size)
        dpr = self.devicePixelRatio()

        for angle in range(0, 360, 10):
            canvas = QPixmap(self.target_size * dpr)
            canvas.setDevicePixelRatio(dpr)
            canvas.fill(Qt.GlobalColor.transparent)

            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            cx, cy = self.target_size.width() / 2, self.target_size.height() / 2
            painter.translate(cx, cy)
            painter.rotate(angle)
            painter.translate(-cx, -cy)

            icon_pixmap = base_icon.pixmap(self.target_size)
            painter.drawPixmap(0, 0, icon_pixmap)
            painter.end()

            self.frames.append(canvas)

    def _advance_frame(self):
        """Very lightweight method, just changes the Pixmap pointer."""
        if not self.frames:
            return
        if not self.isVisible():
            return

        self.current_frame = (self.current_frame + 1) % len(self.frames)
        self.setPixmap(self.frames[self.current_frame])

    def stop(self):
        """Stops the underlying rotation animation timer."""
        self.timer.stop()

    def start(self):
        """Starts the underlying rotation animation timer."""
        self.timer.start()
