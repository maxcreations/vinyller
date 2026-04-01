"""
Vinyller — Customized base PyQt6 dialogs for shadow fix on Linux
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

from PyQt6.QtCore import Qt, QRectF, QSize, QEvent, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap
from PyQt6.QtWidgets import QMainWindow, QDialog, QPushButton, QLabel, QHBoxLayout, QWidget, QVBoxLayout

from src.ui.custom_base_widgets import set_custom_tooltip
from src.ui.custom_classes import apply_button_opacity_effect
from src.utils import theme
from src.utils.constants_linux import IS_LINUX, WINDOW_RADIUS
from src.utils.utils import create_svg_icon, resource_path
from src.utils.utils_translator import translate

SHADOW_SIZE = 16
OFFSET_Y = 4
SHADOW_SHIFT_Y = OFFSET_Y
RESIZE_GRIP_SIZE = 8

class CustomTitleBar(QWidget):
    """
    Custom window title bar for Linux.
    Handles button rendering, double-click actions, and window dragging.
    """

    def __init__(self, parent=None, title="Vinyller"):
        """Initializes the custom title bar layout, logo, title, and window control buttons."""
        super().__init__(parent)
        self.setFixedHeight(36)
        self._drag_pos = None

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_widget = QWidget()
        main_widget.setContentsMargins(0, 0, 0, 0)
        main_widget.setProperty("class", "borderBottom")

        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(8, 0, 6, 0)
        layout.setSpacing(8)

        app_pixmap = QPixmap(resource_path("assets/logo/app_icon.png"))
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setPixmap(
            app_pixmap.scaled(
                QSize(20, 20),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(title)
        self.title_label.setProperty("class", "textSecondary textColorPrimary")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.btn_minimize = self._create_button("minimize.svg", translate("Minimize"))
        self.btn_maximize = self._create_button("maximize.svg", translate("Maximize"))
        self.btn_close = self._create_button("clear.svg", translate("Close"))

        self.btn_minimize.clicked.connect(self._minimize_window)
        self.btn_maximize.clicked.connect(self._toggle_maximize_window)
        self.btn_close.clicked.connect(self._close_window)

        layout.addWidget(self.btn_minimize)
        layout.addWidget(self.btn_maximize)
        layout.addWidget(self.btn_close)
        main_layout.addWidget(main_widget)

    def _create_button(self, icon_name, tooltip):
        """Helper method to create and configure a standard window control button."""
        btn = QPushButton()
        btn.setFixedSize(24, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            btn,
            title = tooltip,
        )
        btn.setProperty("class", "btnWndControl")
        btn.setIcon(create_svg_icon(f"assets/control/{icon_name}", theme.COLORS["PRIMARY"], QSize(12, 12)))
        btn.setIconSize(QSize(12, 12))
        apply_button_opacity_effect(btn)
        return btn

    def _update_maximize_button(self, is_maximized):
        """Updates the maximize/restore button icon and tooltip based on window state."""
        if is_maximized:
            self.btn_maximize.setIcon(
                create_svg_icon("assets/control/maximize_restore.svg", theme.COLORS["PRIMARY"], QSize(12, 12)))
            set_custom_tooltip(
                self.btn_maximize,
                title = translate("Restore"),
            )
        else:
            self.btn_maximize.setIcon(
                create_svg_icon("assets/control/maximize.svg", theme.COLORS["PRIMARY"], QSize(12, 12)))
            set_custom_tooltip(
                self.btn_maximize,
                title = translate("Maximize"),
            )

    def _minimize_window(self):
        """Minimizes the parent window."""
        if self.window():
            self.window().showMinimized()

    def _toggle_maximize_window(self):
        """Toggles the parent window between maximized and normal states."""
        if self.window():
            if self.window().isMaximized():
                self.window().showNormal()
                self._update_maximize_button(False)
            else:
                self.window().showMaximized()
                self._update_maximize_button(True)

    def _close_window(self):
        """Closes the parent window."""
        if self.window():
            self.window().close()

    def mouseDoubleClickEvent(self, event):
        """Handles double-click events to toggle window maximization."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize_window()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        """Handles mouse press events to initiate window dragging."""
        if event.button() == Qt.MouseButton.LeftButton and self.window():
            if not self.window().isMaximized() and not self.window().isFullScreen():
                window_handle = self.window().windowHandle()
                if window_handle:
                    if window_handle.startSystemMove():
                        return

                self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handles mouse move events to drag the frameless window."""
        if event.buttons() == Qt.MouseButton.LeftButton and getattr(self, '_drag_pos',
                                                                    None) is not None and self.window():
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handles mouse release events to stop window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
        super().mouseReleaseEvent(event)


class LinuxShadowMixin:
    """
    Mixin for adding custom shadows, rounded corners, margins,
    and resizing logic exclusively for Linux-based systems.
    """

    def setup_linux_shadow(self):
        """Configures window flags and attributes necessary for custom frameless rendering on Linux."""
        if IS_LINUX:
            self.setWindowFlags(
                self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

            self.setMouseTracking(True)
            self._resizing = False
            self._resize_dir = 0
            self._drag_start_global = None
            self._drag_start_geometry = None

            self.update_shadow_margins()

    def _is_resizable(self):
        """Checks if the window can be resized (i.e., its size is not fixed)."""
        return self.minimumWidth() < self.maximumWidth() or self.minimumHeight() < self.maximumHeight()

    def _get_resize_direction(self, pos):
        """Calculates the edge of the window the mouse is currently hovering over."""
        if not self._is_resizable() or self.isMaximized() or self.isFullScreen():
            return 0

        m = self.contentsMargins()
        rect = self.rect()

        left = m.left()
        right = rect.width() - m.right()
        top = m.top()
        bottom = rect.height() - m.bottom()

        dir_mask = 0

        if left - RESIZE_GRIP_SIZE <= pos.x() <= left + 2:
            dir_mask |= 1
        elif right - 2 <= pos.x() <= right + RESIZE_GRIP_SIZE:
            dir_mask |= 2

        if top - RESIZE_GRIP_SIZE <= pos.y() <= top + 2:
            dir_mask |= 4
        elif bottom - 2 <= pos.y() <= bottom + RESIZE_GRIP_SIZE:
            dir_mask |= 8

        return dir_mask

    def _update_cursor(self, dir_mask):
        """Changes the system cursor based on the resize grab area."""
        if dir_mask == 1 or dir_mask == 2:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif dir_mask == 4 or dir_mask == 8:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif dir_mask == 5 or dir_mask == 10:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif dir_mask == 6 or dir_mask == 9:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.unsetCursor()

    def handle_mouse_press(self, event):
        """Processes mouse press events to start custom window resizing on Linux."""
        if not IS_LINUX: return False
        if event.button() == Qt.MouseButton.LeftButton:
            dir_mask = self._get_resize_direction(event.pos())
            if dir_mask != 0:
                self._resizing = True
                self._resize_dir = dir_mask
                self._drag_start_global = event.globalPosition().toPoint()
                self._drag_start_geometry = self.geometry()
                return True
        return False

    def handle_mouse_move(self, event):
        """Processes mouse move events to calculate and apply new window geometry during resizing."""
        if not IS_LINUX: return False

        if not self._resizing:
            dir_mask = self._get_resize_direction(event.pos())
            self._update_cursor(dir_mask)
            return False

        delta = event.globalPosition().toPoint() - self._drag_start_global
        new_geom = QRect(self._drag_start_geometry)

        if self._resize_dir & 1:
            new_geom.setLeft(new_geom.left() + delta.x())
        elif self._resize_dir & 2:
            new_geom.setRight(new_geom.right() + delta.x())

        if self._resize_dir & 4:
            new_geom.setTop(new_geom.top() + delta.y())
        elif self._resize_dir & 8:
            new_geom.setBottom(new_geom.bottom() + delta.y())

        min_size = self.minimumSize()
        if new_geom.width() < min_size.width():
            if self._resize_dir & 1:
                new_geom.setLeft(new_geom.right() - min_size.width())
            else:
                new_geom.setRight(new_geom.left() + min_size.width())

        if new_geom.height() < min_size.height():
            if self._resize_dir & 4:
                new_geom.setTop(new_geom.bottom() - min_size.height())
            else:
                new_geom.setBottom(new_geom.top() + min_size.height())

        self.setGeometry(new_geom)
        return True

    def handle_mouse_release(self, event):
        """Processes mouse release events to terminate the resizing action."""
        if not IS_LINUX: return False
        if event.button() == Qt.MouseButton.LeftButton and self._resizing:
            self._resizing = False
            self._resize_dir = 0
            self.unsetCursor()
            return True
        return False

    def update_shadow_margins(self):
        """Updates the window layout margins to accommodate the custom drop shadow."""
        if not IS_LINUX:
            return

        if self.isMaximized() or self.isFullScreen():
            self.setContentsMargins(0, 0, 0, 0)
        else:
            self.setContentsMargins(
                SHADOW_SIZE,
                SHADOW_SIZE - SHADOW_SHIFT_Y,
                SHADOW_SIZE,
                SHADOW_SIZE + SHADOW_SHIFT_Y
            )

    def draw_linux_shadow(self):
        """Paints the custom drop shadow and rounded background using QPainter."""
        if not IS_LINUX:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        base_color = QColor(theme.get_qcolor(theme.COLORS["SECONDARY"]))

        if self.isMaximized() or self.isFullScreen():
            painter.fillRect(self.rect(), base_color)
            painter.end()
            return

        rect = self.rect()
        bg_rect = rect.marginsRemoved(self.contentsMargins())

        shadow_color = QColor(0, 0, 0)
        layers = 20
        start_alpha = 6
        shadow_shift_y = SHADOW_SHIFT_Y

        for i in range(layers):
            progress = i / layers
            alpha = int(start_alpha * ((1.0 - progress) ** 2))
            if alpha == 0: break
            shadow_color.setAlpha(alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)

            shadow_rect = bg_rect.adjusted(-(i + 1), -(i + 1), (i + 1), (i + 1))
            shadow_rect.translate(0, shadow_shift_y)

            radius = WINDOW_RADIUS + i
            painter.drawRoundedRect(shadow_rect, radius, radius)

        draw_rect = QRectF(bg_rect)
        draw_rect.adjust(-0.5, -0.5, 0.5, 0.5)

        painter.setBrush(base_color)
        border_color = QColor(theme.get_qcolor(theme.COLORS["INPUT_BRD_HOVER"]))
        painter.setPen(QPen(border_color, 1))

        painter.drawRoundedRect(draw_rect, WINDOW_RADIUS, WINDOW_RADIUS)
        painter.end()


class StyledMainWindow(QMainWindow, LinuxShadowMixin):
    """
    Custom QMainWindow subclass that applies a custom title bar
    and Linux-specific frameless window styling with shadows.
    """
    def __init__(self, parent = None):
        """Initializes the window and applies the custom Linux shadow configuration."""
        super().__init__(parent)
        self.setup_linux_shadow()

    def setCentralWidget(self, widget):
        """Overrides the standard setCentralWidget to inject the custom title bar and layout container."""
        if IS_LINUX:
            container = QWidget()
            container.setCursor(Qt.CursorShape.ArrowCursor)

            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            self.title_bar = CustomTitleBar(container)
            layout.addWidget(self.title_bar)
            layout.addWidget(widget)

            super().setCentralWidget(container)
        else:
            super().setCentralWidget(widget)

    def changeEvent(self, event):
        """Handles state change events, such as maximizing or restoring, to update shadow margins."""
        if event.type() == QEvent.Type.WindowStateChange:
            self.update_shadow_margins()
        super().changeEvent(event)

    def paintEvent(self, event):
        """Overrides the paint event to draw the custom background and shadow."""
        self.draw_linux_shadow()
        super().paintEvent(event)

    def leaveEvent(self, event):
        """Handles the mouse leave event to reset the system cursor."""
        if IS_LINUX and not getattr(self, '_resizing', False):
            self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Routes the mouse event to the Linux shadow mixin for resize handling, or falls back to default."""
        if self.handle_mouse_press(event):
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Routes the mouse move event to the Linux shadow mixin for resize handling, or falls back to default."""
        if self.handle_mouse_move(event):
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Routes the mouse release event to the Linux shadow mixin to terminate resizing, or falls back to default."""
        if self.handle_mouse_release(event):
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class StyledDialog(QDialog, LinuxShadowMixin):
    """
    Custom QDialog subclass that applies a custom title bar,
    manages user layouts, and implements Linux-specific frameless styling.
    """
    def __init__(self, parent = None, title = ""):
        """Initializes the dialog with an optional custom title and applies the Linux shadow configuration."""
        super().__init__(parent)
        self._custom_title = title
        self.setup_linux_shadow()

    def showEvent(self, event):
        """Intercepts the show event for dialogs before displaying to inject the custom title bar and layout wrapper."""
        if IS_LINUX and not getattr(self, '_linux_ui_wrapped', False):
            self._linux_ui_wrapped = True

            wrapper = QWidget(self)
            wrapper.setCursor(Qt.CursorShape.ArrowCursor)
            master_layout = QVBoxLayout(wrapper)
            master_layout.setContentsMargins(0, 0, 0, 0)
            master_layout.setSpacing(0)

            display_title = self._custom_title if self._custom_title else self.windowTitle()
            self.title_bar = CustomTitleBar(wrapper, title = display_title)
            self.title_bar.btn_minimize.hide()
            self.title_bar.btn_maximize.hide()
            master_layout.addWidget(self.title_bar)

            user_layout = self.layout()
            if user_layout:
                content = QWidget(wrapper)
                content.setCursor(Qt.CursorShape.ArrowCursor)
                content.setLayout(user_layout)
                master_layout.addWidget(content)

                if self.layout() is not None:
                    QWidget().setLayout(self.layout())

            new_dialog_layout = QVBoxLayout(self)
            new_dialog_layout.setContentsMargins(0, 0, 0, 0)
            new_dialog_layout.setSpacing(0)
            new_dialog_layout.addWidget(wrapper)

        super().showEvent(event)

    def changeEvent(self, event):
        """Handles state change events to update shadow margins."""
        if event.type() == QEvent.Type.WindowStateChange:
            self.update_shadow_margins()
        super().changeEvent(event)

    def paintEvent(self, event):
        """Overrides the paint event to draw the custom background and shadow."""
        self.draw_linux_shadow()
        super().paintEvent(event)

    def leaveEvent(self, event):
        """Handles the mouse leave event to reset the system cursor."""
        if IS_LINUX and not getattr(self, '_resizing', False):
            self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Routes the mouse press event to the Linux shadow mixin for resize handling, or falls back to default."""
        if self.handle_mouse_press(event):
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Routes the mouse move event to the Linux shadow mixin for resize handling, or falls back to default."""
        if self.handle_mouse_move(event):
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Routes the mouse release event to the Linux shadow mixin to terminate resizing, or falls back to default."""
        if self.handle_mouse_release(event):
            event.accept()
        else:
            super().mouseReleaseEvent(event)
