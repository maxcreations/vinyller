"""
Vinyller — Customized base PyQt6 widgets with translucent menus and buttons
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

import time
from functools import partial

from PyQt6.QtCore import (
    QSize, Qt, pyqtSignal, QPoint, QRectF, QRect, QObject, QEvent, QTimer
)
from PyQt6.QtGui import (
    QAction, QIcon, QColor, QPainter, QPen, QCursor
)
from PyQt6.QtWidgets import (
    QComboBox, QLabel, QLineEdit,
    QListWidget, QMenu, QPushButton,
    QScrollArea, QScrollBar, QSizePolicy, QTextBrowser,
    QTextEdit, QApplication, QWidget, QFrame, QListWidgetItem, QToolButton, QTableWidgetItem,
    QTreeWidgetItem, QAbstractItemView, QVBoxLayout, QHBoxLayout, QLayout
)

from src.utils import theme
from src.utils.utils import create_svg_icon
from src.utils.utils_translator import translate

SHADOW_SIZE = 16
OFFSET_Y = 4
SHADOW_SHIFT_Y = OFFSET_Y
# Using a safe offset from the base UserRole to avoid colliding with your data (item)
CUSTOM_TOOLTIP_ROLE = Qt.ItemDataRole.UserRole + 99


class StyledLineEdit(QLineEdit):
    """
    A QLineEdit subclass that replaces the standard context menu
    with a custom translucent menu.
    """
    def contextMenuEvent(self, event):
        """Intercepts the context menu event to display a custom translucent menu."""
        std_menu = self.createStandardContextMenu()
        if not std_menu:
            return

        custom_menu = TranslucentMenu(self)
        custom_menu.setProperty("class", "popMenu")

        custom_menu.addActions(std_menu.actions())

        custom_menu.exec(event.globalPos())


class StyledScrollBar(QScrollBar):
    """
    A QScrollBar subclass that consumes context menu events
    to prevent the default menu from appearing.
    """
    def contextMenuEvent(self, event):
        """Accepts the context menu event without action to suppress the default menu."""
        event.accept()


class StyledScrollArea(QScrollArea):
    """
    A QScrollArea subclass that uses StyledScrollBar for both
    vertical and horizontal scrollbars.
    """
    def __init__(self, *args, **kwargs):
        """Initializes the scroll area and applies custom styled scrollbars."""
        super().__init__(*args, **kwargs)
        self.setVerticalScrollBar(StyledScrollBar(Qt.Orientation.Vertical, self))
        self.setHorizontalScrollBar(StyledScrollBar(Qt.Orientation.Horizontal, self))


class StyledTextEdit(QTextEdit):
    """
    A QTextEdit subclass with custom scrollbars and a translucent context menu.
    """
    def __init__(self, *args, **kwargs):
        """Initializes the text edit and applies custom styled scrollbars."""
        super().__init__(*args, **kwargs)
        self.setVerticalScrollBar(StyledScrollBar(Qt.Orientation.Vertical, self))
        self.setHorizontalScrollBar(StyledScrollBar(Qt.Orientation.Horizontal, self))

    def contextMenuEvent(self, event):
        """Intercepts the context menu event to display a custom translucent menu."""
        std_menu = self.createStandardContextMenu()
        if std_menu:
            custom_menu = TranslucentMenu(self)
            custom_menu.setProperty("class", "popMenu")
            custom_menu.addActions(std_menu.actions())
            custom_menu.exec(event.globalPos())


class StyledLabel(QLabel):
    """
    A QLabel subclass that provides a custom translucent context menu
    for copying selected text to the clipboard.
    """
    def contextMenuEvent(self, event):
        """Displays a translucent context menu with a copy action if text is selectable."""
        if not (self.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse):
            return

        custom_menu = TranslucentMenu(self)
        custom_menu.setProperty("class", "popMenu")

        selected_text = self.selectedText()

        copy_action = QAction(translate("Copy"))
        copy_action.setEnabled(bool(selected_text))
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(selected_text))

        custom_menu.addAction(copy_action)

        custom_menu.exec(event.globalPos())

    def _copy_to_clipboard(self, text):
        """Copies the provided text to the system clipboard."""
        QApplication.clipboard().setText(text)


class StyledTextBrowser(QTextBrowser):
    """
    A QTextBrowser subclass equipped with custom scrollbars and
    a translucent context menu.
    """
    def __init__(self, *args, **kwargs):
        """Initializes the text browser and applies custom styled scrollbars."""
        super().__init__(*args, **kwargs)
        self.setVerticalScrollBar(StyledScrollBar(Qt.Orientation.Vertical, self))
        self.setHorizontalScrollBar(StyledScrollBar(Qt.Orientation.Horizontal, self))

    def contextMenuEvent(self, event):
        """Intercepts the context menu event to display a custom translucent menu."""
        std_menu = self.createStandardContextMenu()
        if std_menu:
            custom_menu = TranslucentMenu(self)
            custom_menu.setProperty("class", "popMenu")
            custom_menu.addActions(std_menu.actions())
            custom_menu.exec(event.globalPos())


class StyledListWidget(QListWidget):
    """
    A QListWidget subclass with custom scrollbars and custom painting logic
    for the drop indicator during drag-and-drop operations.
    """
    def __init__(self, *args, **kwargs):
        """Initializes the list widget, applies custom scrollbars, and hides default drop indicators."""
        super().__init__(*args, **kwargs)
        self.setVerticalScrollBar(StyledScrollBar(Qt.Orientation.Vertical, self))
        self.setHorizontalScrollBar(StyledScrollBar(Qt.Orientation.Horizontal, self))

        self.setDropIndicatorShown(False)

        self.drop_indicator_rect = QRect()

    def paintEvent(self, event):
        """Overrides paintEvent to manually draw the drag-and-drop indicator."""
        super().paintEvent(event)

        if not self.drop_indicator_rect.isNull():
            painter = QPainter(self.viewport())
            color = QColor(theme.COLORS["ACCENT"])
            painter.fillRect(self.drop_indicator_rect, color)
            painter.end()

    def dragMoveEvent(self, event):
        """Calculates and updates the position of the custom drop indicator during a drag."""
        pos = event.position().toPoint()
        index = self.indexAt(pos)

        if event.mimeData():
            event.acceptProposedAction()

        if index.isValid():
            rect = self.visualRect(index)
            if pos.y() - rect.top() < rect.height() / 2:
                self.drop_indicator_rect = QRect(rect.left(), rect.top(), rect.width(), 2)
            else:
                self.drop_indicator_rect = QRect(rect.left(), rect.bottom(), rect.width(), 2)
        else:
            if self.count() > 0:
                last_rect = self.visualRect(self.model().index(self.count() - 1, 0))
                self.drop_indicator_rect = QRect(last_rect.left(), last_rect.bottom(), last_rect.width(), 2)
            else:
                self.drop_indicator_rect = QRect(0, 0, self.viewport().width(), 2)

        self.viewport().update()

    def dragLeaveEvent(self, event):
        """Clears the drop indicator when the drag operation leaves the widget."""
        super().dragLeaveEvent(event)
        self.drop_indicator_rect = QRect()
        self.viewport().update()

    def dropEvent(self, event):
        """Handles the drop event and clears the drop indicator."""
        super().dropEvent(event)
        self.drop_indicator_rect = QRect()
        self.viewport().update()


class ShadowPopup(QWidget):
    """
    A universal popup widget with a custom shadow effect, matching the style
    of DropDownList and TranslucentMenu.

    Usage:
      popup = ShadowPopup(parent)
      popup.layout.addWidget(my_widget)
      popup.show_under(target_widget)
    """

    def __init__(self, parent = None):
        """Initializes the popup, configuring flags and layout for shadow rendering."""
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setProperty("should_be_visible", False)

        if parent:
            parent.installEventFilter(self)

        self.layout = QVBoxLayout(self)

        self.layout.setContentsMargins(
            SHADOW_SIZE,
            SHADOW_SIZE - SHADOW_SHIFT_Y,
            SHADOW_SIZE,
            SHADOW_SIZE + SHADOW_SHIFT_Y
        )
        self.layout.setSpacing(0)
        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

    def paintEvent(self, event):
        """Paints the translucent background and multi-layered shadow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        bg_rect = rect.marginsRemoved(self.layout.contentsMargins())

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
            radius = 6 + i
            painter.drawRoundedRect(shadow_rect, radius, radius)

        base_color = QColor(theme.get_qcolor(theme.COLORS["SECONDARY"]))

        draw_rect = QRectF(bg_rect)
        draw_rect.adjust(-0.5, -0.5, 0.5, 0.5)

        painter.setBrush(base_color)

        border_color = QColor(theme.get_qcolor(theme.COLORS["INPUT_BRD_HOVER"]))
        painter.setPen(QPen(border_color, 1))

        painter.drawRoundedRect(draw_rect, 6, 6)

        painter.end()

    def mousePressEvent(self, event):
        """Closes the popup if the user clicks outside its primary content bounds."""
        rect = self.rect()
        bg_rect = rect.marginsRemoved(self.layout.contentsMargins())

        if not bg_rect.contains(event.pos()):
            self.close()
        else:
            super().mousePressEvent(event)

    def show_under(self, target_widget, offset_y = 4):
        """
        Displays the popup below the specified target widget,
        automatically compensating for shadow margins.

        Args:
            target_widget (QWidget): The widget under which the popup will be shown.
            offset_y (int, optional): Vertical offset in pixels. Defaults to 4.
        """
        global_pos = target_widget.mapToGlobal(QPoint(0, target_widget.height()))

        margins = self.layout.contentsMargins()

        x = global_pos.x() - margins.left()
        y = global_pos.y() - margins.top() + offset_y

        self.show()
        self.move(x, y)
        self.raise_()

    def eventFilter(self, obj, event):
        """Filters parent events to automatically hide or show the popup on state changes."""
        if obj == self.parent():
            if event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.WindowDeactivate):
                if self.parent().isMinimized() or event.type() == QEvent.Type.WindowDeactivate:
                    super().hide()

            elif event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.WindowActivate):
                if not self.parent().isMinimized() and self.property("should_be_visible"):
                    self.show()

        return super().eventFilter(obj, event)

    def hideEvent(self, event):
        """Tracks visibility state when the popup is hidden."""
        if self.parent() and not self.parent().isMinimized():
            self.setProperty("should_be_visible", False)
        super().hideEvent(event)

    def showEvent(self, event):
        """Tracks visibility state when the popup is shown."""
        self.setProperty("should_be_visible", True)
        super().showEvent(event)


class GlobalTooltipFilter(QObject):
    """
    A global event filter that monitors tooltip events application-wide to
    intercept them and trigger custom styled tooltips instead.
    """
    _instance = None
    _dynamic_item_tooltip = None

    _current_item_key = None

    _active_tooltip_rect = None
    _active_tooltip_viewport = None

    @classmethod
    def install(cls):
        """Installs the global tooltip filter singleton onto the main QApplication."""
        if cls._instance is None:
            cls._instance = cls()
            if QApplication.instance():
                QApplication.instance().installEventFilter(cls._instance)

    @classmethod
    def show_rect_tooltip(cls, view, data, rect):
        """Explicitly triggers a custom tooltip for a specific rectangular area within a widget."""
        if cls._instance is None:
            cls.install()

        if cls._instance:
            viewport = view.viewport() if hasattr(view, 'viewport') else view

            if (cls._instance._active_tooltip_rect == rect and
                    cls._instance._active_tooltip_viewport == viewport and
                    cls._instance._dynamic_item_tooltip is not None):
                return

            cls._instance._show_dynamic_tooltip(view, data)

            cls._instance._active_tooltip_rect = rect
            cls._instance._active_tooltip_viewport = viewport

    def eventFilter(self, obj, event):
        """Intercepts specific events (ToolTip, Leave, MouseMove) to manage custom tooltip lifecycle."""
        if event.type() == QEvent.Type.ToolTip:
            action = self._get_action(obj)
            if action and hasattr(action, '_custom_tooltip') and action._custom_tooltip:
                action._custom_tooltip._show_tooltip()
                return True

            if isinstance(obj, QWidget) and isinstance(obj.parent(), QAbstractItemView):
                view = obj.parent()
                index = view.indexAt(event.pos())

                if index.isValid():
                    item_key = (id(view), index.row(), index.column())

                    if self._dynamic_item_tooltip and self._current_item_key == item_key:
                        return True

                    tooltip_data = index.data(CUSTOM_TOOLTIP_ROLE)
                    if not tooltip_data:
                        std_text = index.data(Qt.ItemDataRole.ToolTipRole)
                        if std_text and std_text.strip() and std_text != " ":
                            tooltip_data = {"text": std_text}

                    if tooltip_data:
                        self._current_item_key = item_key
                        self._show_dynamic_tooltip(view, tooltip_data)
                        return True

        elif event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.Hide, QEvent.Type.Wheel):
            action = self._get_action(obj)
            if action and hasattr(action, '_custom_tooltip') and action._custom_tooltip:
                action._custom_tooltip._timer.stop()
                action._custom_tooltip.hide()

            self._hide_dynamic_tooltip()

        elif event.type() == QEvent.Type.Leave:
            if isinstance(obj, QWidget):
                local_pos = obj.mapFromGlobal(QCursor.pos())
                if obj.rect().contains(local_pos):
                    return super().eventFilter(obj, event)

            action = self._get_action(obj)
            if action and hasattr(action, '_custom_tooltip') and action._custom_tooltip:
                action._custom_tooltip._timer.stop()
                action._custom_tooltip.hide()

            self._hide_dynamic_tooltip()

        elif event.type() == QEvent.Type.MouseMove:
            if self._active_tooltip_rect is not None and obj == self._active_tooltip_viewport:
                if self._active_tooltip_rect.contains(event.pos()):
                    return super().eventFilter(obj, event)
                else:
                    self._hide_dynamic_tooltip()

            if isinstance(obj, QWidget) and isinstance(obj.parent(), QAbstractItemView):
                view = obj.parent()
                index = view.indexAt(event.pos())
                item_key = (id(view), index.row(), index.column()) if index.isValid() else None

                if item_key != self._current_item_key:
                    self._hide_dynamic_tooltip()

        return super().eventFilter(obj, event)

    def _get_action(self, obj):
        """Helper to extract a default action from a widget, if it exists."""
        if hasattr(obj, 'defaultAction') and callable(obj.defaultAction):
            return obj.defaultAction()
        return None

    def _show_dynamic_tooltip(self, view, data):
        """Destroys any existing dynamic tooltip and creates a new one for list/tree/table items."""
        self._hide_dynamic_tooltip()

        self._dynamic_item_tooltip = CustomTooltip(
            target_widget = view,
            title = data.get("title"),
            text = data.get("text"),
            hotkey = data.get("hotkey"),
            activity_type = data.get("activity_type")
        )
        view.removeEventFilter(self._dynamic_item_tooltip)
        self._dynamic_item_tooltip._show_tooltip()

    def _hide_dynamic_tooltip(self):
        """Hides and deletes the currently active dynamic tooltip, clearing rect trackers."""
        self._active_tooltip_rect = None
        self._active_tooltip_viewport = None

        tooltip = self._dynamic_item_tooltip
        if tooltip is not None:
            self._dynamic_item_tooltip = None
            self._current_item_key = None

            tooltip.hide()
            tooltip.deleteLater()


class CustomTooltip(ShadowPopup):
    """
    A stylized custom tooltip widget that extends ShadowPopup, supporting
    rich content including titles, text, hotkeys, and icons.
    """
    _active_tooltip = None

    def __init__(self, target_widget, title = None, text = None, hotkey = None, activity_type = None):
        """
        Initializes the custom tooltip with a target widget and optional rich text elements.
        """
        super().__init__(None)

        self.setFont(QApplication.instance().font())

        self.target_widget = target_widget
        self._tracked_window = None

        if self.target_widget:
            self.target_widget.destroyed.connect(self.deleteLater)

        if isinstance(self.target_widget, QWidget):
            self.target_widget.installEventFilter(self)

        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._title_label = None
        self._text_label = None
        self._hotkey_label = None
        self._icon_label = None

        self._current_title = title
        self._current_text = text
        self._current_hotkey = hotkey
        self._current_activity = activity_type

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._show_tooltip)

        self._setup_ui(title, text, hotkey, activity_type)

    def _setup_ui(self, title, text, hotkey, activity_type):
        """Constructs the internal layout and labels based on the provided tooltip data."""
        container = QWidget(self)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        has_header = False

        if title:
            self._title_label = QLabel(title, container)
            self._title_label.setProperty("class", "textPrimary textColorPrimary")
            self._title_label.style().unpolish(self._title_label)
            self._title_label.style().polish(self._title_label)

            header_layout.addWidget(self._title_label)
            has_header = True

        if hotkey or activity_type:
            if has_header:
                header_layout.addStretch()

            if hotkey:
                hotkey_container = QWidget(container)
                hotkey_container.setProperty("class", "hotkeyContainer borderRadius4")
                hotkey_container.setFixedHeight(20)
                hotkey_layout = QHBoxLayout(hotkey_container)
                hotkey_layout.setContentsMargins(4, 2, 4, 2)

                self._hotkey_label = QLabel(hotkey)
                self._hotkey_label.setProperty("class", "textPrimary textColorTertiary")
                self._hotkey_label.style().unpolish(self._hotkey_label)
                self._hotkey_label.style().polish(self._hotkey_label)

                hotkey_layout.addWidget(self._hotkey_label)
                header_layout.addWidget(hotkey_container)

            if activity_type:
                icon_map = {
                    "external": "activity_external.svg",
                    "network_activity": "activity_network.svg"
                }

                icon_filename = icon_map.get(activity_type)

                if icon_filename:
                    self._icon_label = QLabel(container)
                    icon_pixmap = create_svg_icon(
                        f"assets/control/{icon_filename}",
                        theme.COLORS["TERTIARY"],
                        QSize(20, 20)
                    ).pixmap(20, 20)

                    self._icon_label.setPixmap(icon_pixmap)
                    self._icon_label.setFixedSize(20, 20)
                    header_layout.addWidget(self._icon_label)

            has_header = True

        if has_header:
            layout.addLayout(header_layout)

        if text:
            self._text_label = QLabel(text, container)
            self._text_label.setProperty("class", "textSecondary textColorPrimary")
            self._text_label.style().unpolish(self._text_label)
            self._text_label.style().polish(self._text_label)
            self._text_label.setWordWrap(True)

            self._text_label.setStyleSheet("font-weight: normal;")

            layout.addWidget(self._text_label)

        self.layout.addWidget(container)

    def update_content(self, title = None, text = None, hotkey = None, activity_type = None):
        """Updates the existing tooltip's content dynamically, reconstructing UI if structure changes."""
        if (self._current_title == title and
                self._current_text == text and
                self._current_hotkey == hotkey and
                self._current_activity == activity_type):
            return

        structure_changed = False
        if bool(title) != bool(self._title_label): structure_changed = True
        if bool(text) != bool(self._text_label): structure_changed = True
        if bool(hotkey) != bool(self._hotkey_label): structure_changed = True
        if activity_type != self._current_activity: structure_changed = True

        self._current_title = title
        self._current_text = text
        self._current_hotkey = hotkey
        self._current_activity = activity_type

        if not structure_changed:
            if self._title_label and title:
                self._title_label.setText(title)
            if self._text_label and text:
                self._text_label.setText(text)
            if self._hotkey_label and hotkey:
                self._hotkey_label.setText(hotkey)

            container = self.layout.itemAt(0).widget() if self.layout.count() > 0 else None

            if container and container.layout():
                container.layout().invalidate()
            self.layout.invalidate()

            for widget in [self._title_label, self._text_label, self._hotkey_label, self._icon_label]:
                if widget:
                    widget.resize(0, 0)

            if container:
                container.resize(0, 0)

            self.resize(0, 0)

            if container:
                container.adjustSize()
            self.adjustSize()

            if self.isVisible():
                pos = QCursor.pos()
                self.move(pos.x() + 2, pos.y() + 2)
            return

        self.setUpdatesEnabled(False)

        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._title_label = None
        self._text_label = None
        self._hotkey_label = None
        self._icon_label = None

        self._setup_ui(title, text, hotkey, activity_type)

        container = self.layout.itemAt(0).widget() if self.layout.count() > 0 else None

        if container and container.layout():
            container.layout().invalidate()
        self.layout.invalidate()

        if container:
            container.resize(0, 0)
        self.resize(0, 0)

        if container:
            container.adjustSize()
        self.adjustSize()

        if self.isVisible():
            pos = QCursor.pos()
            self.move(pos.x() + 2, pos.y() + 2)

        self.setUpdatesEnabled(True)

    def eventFilter(self, obj, event):
        """Listens to target widget mouse events and dynamically tracks window state."""

        if self._tracked_window and obj == self._tracked_window:
            if event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.WindowDeactivate):
                if self._tracked_window.isMinimized() or event.type() == QEvent.Type.WindowDeactivate:
                    self._timer.stop()
                    self.hide()

        if obj == self.target_widget:
            if event.type() == QEvent.Type.Enter:
                self._timer.start()
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.Hide):
                self._timer.stop()
                self.hide()
            elif event.type() == QEvent.Type.ToolTip:
                return True

        return super().eventFilter(obj, event)

    def _show_tooltip(self):
        """Displays the tooltip at the current cursor position."""
        if CustomTooltip._active_tooltip and CustomTooltip._active_tooltip is not self:
            CustomTooltip._active_tooltip.hide()

        CustomTooltip._active_tooltip = self

        if isinstance(self.target_widget, QWidget):
            current_window = self.target_widget.window()
            if current_window and self._tracked_window != current_window:
                if self._tracked_window:
                    self._tracked_window.removeEventFilter(self)
                self._tracked_window = current_window
                self._tracked_window.installEventFilter(self)

        pos = QCursor.pos()
        self.move(pos.x() + 2, pos.y() + 2)
        self.show()

    def hideEvent(self, event):
        """Clears the active tooltip tracking upon hiding."""
        if CustomTooltip._active_tooltip is self:
            CustomTooltip._active_tooltip = None

        super().hideEvent(event)


def set_custom_tooltip(target, title=None, text=None, hotkey=None, activity_type=None):
    """
    Binds a custom tooltip to a widget, QAction, or list/table items.
    """
    if isinstance(target, (QListWidgetItem, QTableWidgetItem, QTreeWidgetItem)):
        if not (title or text or hotkey or activity_type):
            target.setData(CUSTOM_TOOLTIP_ROLE, None)
            target.setToolTip("")
            return

        tooltip_data = {
            "title": title,
            "text": text,
            "hotkey": hotkey,
            "activity_type": activity_type
        }
        target.setData(CUSTOM_TOOLTIP_ROLE, tooltip_data)
        target.setToolTip(" ")
        GlobalTooltipFilter.install()
        return

    if hasattr(target, '_custom_tooltip') and target._custom_tooltip is not None:
        if not (title or text or hotkey or activity_type):
            if isinstance(target, QWidget):
                target.removeEventFilter(target._custom_tooltip)
            target._custom_tooltip.hide()
            target._custom_tooltip.deleteLater()
            target._custom_tooltip = None
            if isinstance(target, QAction):
                target.setToolTip("")
            return

        target._custom_tooltip.update_content(title, text, hotkey, activity_type)

        if isinstance(target, QWidget) and target.underMouse():
            tooltip = target._custom_tooltip
            if not tooltip.isVisible() and not tooltip._timer.isActive():
                tooltip._timer.start()

        return

    if not (title or text or hotkey or activity_type):
        if isinstance(target, QAction):
            target.setToolTip("")
        return

    if isinstance(target, QAction):
        GlobalTooltipFilter.install()
        native_text = " ".join(filter(None, [title, text, f"({hotkey})" if hotkey else None]))
        target.setToolTip(native_text or " ")

    tooltip = CustomTooltip(
        target_widget = target,
        title = title,
        text = text,
        hotkey = hotkey,
        activity_type = activity_type
    )
    target._custom_tooltip = tooltip


class DropDownList(QWidget):
    """
    A translucent frameless popup widget containing a StyledListWidget,
    typically used as a dropdown menu for custom combo boxes.
    """
    itemClicked = pyqtSignal(int)

    def __init__(self, parent = None):
        """Initializes the popup container, shadow margins, and the internal list widget."""
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self.layout = QVBoxLayout(self)

        self.layout.setContentsMargins(
            SHADOW_SIZE,
            SHADOW_SIZE - SHADOW_SHIFT_Y,
            SHADOW_SIZE,
            SHADOW_SIZE + SHADOW_SHIFT_Y
        )
        self.layout.setSpacing(0)

        self.list_widget = StyledListWidget()
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)

        self.list_widget.setStyleSheet("background: transparent; border: none;")

        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


        self.layout.addWidget(self.list_widget)
        self.list_widget.itemClicked.connect(self._on_click)
        self.list_widget.setProperty("class", "listWidget")

    def paintEvent(self, event):
        """
        Replicates the drawing logic from TranslucentMenu to ensure
        visual consistency across shadow and background rendering.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        bg_rect = rect.marginsRemoved(self.layout.contentsMargins())

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
            radius = 6 + i
            painter.drawRoundedRect(shadow_rect, radius, radius)

        base_color = QColor(theme.get_qcolor(theme.COLORS["SECONDARY"]))

        draw_rect = QRectF(bg_rect)

        draw_rect.adjust(-0.5, -0.5, 0.5, 0.5)

        painter.setBrush(base_color)

        border_color = QColor(theme.get_qcolor(theme.COLORS["INPUT_BRD_HOVER"]))
        painter.setPen(QPen(border_color, 1))

        painter.drawRoundedRect(draw_rect, 6, 6)

        painter.end()

    def mousePressEvent(self, event):
        """Closes the popup if a mouse press occurs outside the list widget."""
        if not self.list_widget.geometry().contains(event.pos()):
            self.close()
        else:
            super().mousePressEvent(event)

    def _on_click(self, item):
        """Emits the index of the clicked list item and closes the popup."""
        row = self.list_widget.row(item)
        self.itemClicked.emit(row)
        self.close()


class TranslucentCombo(QComboBox):
    """
    A QComboBox subclass that implements a custom DropDownList
    to provide a stylized, translucent popup menu.
    """
    def __init__(self, parent = None):
        """Initializes the combo box and variables for popup management."""
        super().__init__(parent)
        self._popup = None
        self._popup_closed_time = 0

    def mousePressEvent(self, event):
        """Prevents reopening the popup immediately after it was closed."""
        if time.time() - self._popup_closed_time < 0.2:
            return

        super().mousePressEvent(event)

    def showPopup(self):
        """Generates and displays the custom DropDownList popup with current items."""
        if self.count() == 0:
            return

        self._popup = DropDownList(self)
        self._popup.installEventFilter(self)

        for i in range(self.count()):
            item = QListWidgetItem(self.itemIcon(i), self.itemText(i))
            self._popup.list_widget.addItem(item)

        self._popup.list_widget.setCurrentRow(self.currentIndex())
        self._popup.itemClicked.connect(self.setCurrentIndex)

        self._popup.list_widget.ensurePolished()

        row_height = self._popup.list_widget.sizeHintForRow(0)
        if row_height < 0:
            row_height = 32

        content_height = row_height * self.count()

        margins = self._popup.list_widget.contentsMargins()
        css_padding_top = margins.top()
        css_padding_bottom = margins.bottom()

        final_list_height = content_height + css_padding_top + css_padding_bottom

        max_h = row_height * 8 + css_padding_top + css_padding_bottom
        if final_list_height > max_h:
            final_list_height = max_h

        margins = self._popup.layout.contentsMargins()
        full_width = self.width() + margins.left() + margins.right()

        full_height = final_list_height + margins.top() + margins.bottom()

        self._popup.setFixedSize(full_width, full_height)
        self._popup.list_widget.setFixedHeight(final_list_height)

        global_pos = self.mapToGlobal(QPoint(0, self.height()))

        target_x = global_pos.x() - margins.left()
        target_y = global_pos.y() - margins.top() + OFFSET_Y

        screen = self.screen()
        if screen:
            avail_geo = screen.availableGeometry()
            if target_y + full_height > avail_geo.bottom():
                target_y = global_pos.y() - self.height() - full_height + margins.bottom() - OFFSET_Y

        self._popup.show()
        self._popup.move(target_x, target_y)

    def eventFilter(self, obj, event):
        """Records the time when the popup closes to handle reopening restrictions."""
        if obj == self._popup and event.type() == QEvent.Type.Hide:
            self._popup_closed_time = time.time()
            self._popup = None

        return super().eventFilter(obj, event)

    def hidePopup(self):
        """Programmatically closes the custom popup if it is open."""
        if self._popup:
            self._popup.close()


class TranslucentMenu(QMenu):
    """
    A custom QMenu subclass featuring a translucent background,
    rounded corners, and custom shadow rendering.
    """
    def __init__(self, *args, **kwargs):
        """Initializes the menu window flags, transparency, and shadow margins."""
        super().__init__(*args, **kwargs)

        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)


        self.setContentsMargins(
            SHADOW_SIZE,
            SHADOW_SIZE - SHADOW_SHIFT_Y,
            SHADOW_SIZE,
            SHADOW_SIZE + SHADOW_SHIFT_Y
        )

        self.setStyleSheet(f"""
            QMenu {{
                background: transparent;
                border: none;
            }}
        """)

    def paintEvent(self, event):
        """Draws the custom shadows and rounded translucent background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

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
            radius = 6 + i
            painter.drawRoundedRect(shadow_rect, radius, radius)


        base_color = QColor(theme.get_qcolor(theme.COLORS["SECONDARY"]))

        draw_rect = QRectF(bg_rect)

        draw_rect.adjust(-0.5, -0.5, 0.5, 0.5)

        painter.setBrush(base_color)

        border_color = QColor(theme.get_qcolor(theme.COLORS["INPUT_BRD_HOVER"]))
        painter.setPen(QPen(border_color, 1))

        painter.drawRoundedRect(draw_rect, 6, 6)

        painter.end()

        super().paintEvent(event)

    def showEvent(self, event):
        """Captures the intended display position before applying margin compensations."""
        self._intended_pos = self.pos()
        super().showEvent(event)

        QTimer.singleShot(0, self._apply_mac_position_fix)

    def _apply_mac_position_fix(self):
        """Adjusts the menu coordinates to properly account for shadow margins and screen edges."""
        if not hasattr(self, '_intended_pos'):
            return

        current_pos = self._intended_pos
        new_x = current_pos.x() - SHADOW_SIZE
        top_margin = self.contentsMargins().top()
        new_y = current_pos.y() - top_margin + OFFSET_Y

        screen = self.screen()
        if screen:
            avail_geo = screen.availableGeometry()
            if new_y < avail_geo.top():
                new_y = avail_geo.top()
            elif new_y + self.height() > avail_geo.bottom():
                new_y = avail_geo.bottom() - self.height()

            if new_x < avail_geo.left():
                new_x = avail_geo.left()
            elif new_x + self.width() > avail_geo.right():
                new_x = avail_geo.right() - self.width()

        self.move(new_x, new_y)

    def addMenu(self, *args):
        """Overrides addMenu to ensure newly added submenus are also TranslucentMenu instances."""
        if len(args) == 1:
            if isinstance(args[0], str):
                return self._create_and_add_menu(title = args[0])
            elif isinstance(args[0], QMenu):
                return self._wrap_and_add_menu(args[0])
        elif len(args) == 2:
            if isinstance(args[0], QIcon) and isinstance(args[1], str):
                return self._create_and_add_menu(icon = args[0], title = args[1])
        return super().addMenu(*args)

    def _create_and_add_menu(self, title = "", icon = None):
        """Helper to create and return a new nested TranslucentMenu."""
        submenu = TranslucentMenu(title, self)
        if icon:
            submenu.setIcon(icon)
        super().addMenu(submenu)
        return submenu

    def _wrap_and_add_menu(self, menu):
        """Wraps a standard QMenu into a TranslucentMenu structure."""
        if isinstance(menu, TranslucentMenu):
            return super().addMenu(menu)

        new_menu = TranslucentMenu(menu.title(), self)
        new_menu.setIcon(menu.icon())

        for action in menu.actions():
            if action.menu():
                wrapped_submenu = self._wrap_and_add_menu(action.menu())
                action = QAction(action.icon(), action.text(), self)
                action.setMenu(wrapped_submenu)
            new_menu.addAction(action)

        return super().addMenu(new_menu)


class StyledToolButton(QToolButton):
    """
    A QToolButton subclass supporting TranslucentMenu integration.
    Recursively creates a fresh menu structure upon clicking to ensure
    correct shadow rendering.
    """

    def __init__(self, parent = None):
        """Initializes the tool button and configures its instant popup behavior."""
        super().__init__(parent)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._logic_menu = QMenu(self)
        self._menu_closed_time = 0
        super().setMenu(self._logic_menu)

    def menu(self):
        """Returns the logical backend menu used by the button."""
        return self._logic_menu

    def setMenu(self, menu):
        """Sets the logical menu to be used and displayed by the button."""
        self._logic_menu = menu
        super().setMenu(menu)

    def mousePressEvent(self, event):
        """Triggers the custom menu display upon a left mouse button click."""
        if event.button() == Qt.MouseButton.LeftButton:
            if time.time() - self._menu_closed_time < 0.2:
                return
            self.setDown(True)
            self.show_custom_menu()
            self.setDown(False)
        else:
            super().mousePressEvent(event)

    def show_custom_menu(self):
        """Generates the visual translucent menu and executes it at the appropriate global position."""
        if not self._logic_menu or not self._logic_menu.actions():
            return

        visual_menu = self._create_recursive_menu(self._logic_menu, self)

        global_pos = self.mapToGlobal(QPoint(0, self.height()))
        visual_menu.exec(global_pos)

        self._menu_closed_time = time.time()

    def _create_recursive_menu(self, source_menu, parent_widget):
        """
        Creates a fresh copy of the source menu and all its submenus.
        """
        visual_menu = TranslucentMenu(parent_widget)
        visual_menu.setProperty("class", "popMenu")

        for action in source_menu.actions():
            if action.isSeparator():
                visual_menu.addSeparator()
                continue

            vis_action = QAction(action.icon(), action.text(), visual_menu)
            vis_action.setData(action.data())
            vis_action.setCheckable(action.isCheckable())
            vis_action.setChecked(action.isChecked())
            vis_action.setEnabled(action.isEnabled())

            if action.menu():
                fresh_submenu = self._create_recursive_menu(action.menu(), visual_menu)
                vis_action.setMenu(fresh_submenu)
            else:
                vis_action.triggered.connect(partial(action.trigger))

            visual_menu.addAction(vis_action)

        return visual_menu


class IconSpaceButton(QPushButton):
    """
    A custom QPushButton consisting of an icon and text with customizable
    spacing and alignment, completely managed via nested QLabels.
    """
    def __init__(self, text="", icon_path=None, spacing=8, parent=None):
        """Initializes the composite button, laying out its icon and text labels."""
        super().__init__(parent)
        self.setText("")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 0, 12, 0)
        self._layout.setSpacing(spacing)

        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label = QLabel()
        self._text_label = QLabel(text)

        self._text_label.setProperty("class", "textPrimary")

        self._icon_label.setContentsMargins(0, 0, 0, 0)
        self._text_label.setContentsMargins(0, 0, 0, 0)

        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._text_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._layout.addWidget(self._icon_label)
        self._layout.addWidget(self._text_label)

    def sizeHint(self):
        """Calculates and returns the appropriate bounding size for the internal elements."""
        icon_width = (
            self._icon_label.pixmap().width() if self._icon_label.pixmap() else 0
        )

        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self._text_label.text()) + 4

        margins = self._layout.contentsMargins()
        spacing = self._layout.spacing() if icon_width > 0 and text_width > 0 else 0

        width = icon_width + spacing + text_width + margins.left() + margins.right()

        text_height = fm.height()
        icon_height = (
            self._icon_label.pixmap().height() if self._icon_label.pixmap() else 0
        )
        height = max(text_height, icon_height) + margins.top() + margins.bottom()

        return QSize(width, height)

    def setCustomIcon(self, pixmap):
        """Sets a scaled custom pixmap as the button's internal icon."""
        if not pixmap.isNull():
            dpr = pixmap.devicePixelRatio()
            logical_w = int(pixmap.width() / dpr)
            logical_h = int(pixmap.height() / dpr)

            self._icon_label.setPixmap(pixmap)
            self._icon_label.setFixedSize(logical_w, logical_h)
            self._icon_label.show()
        else:
            self._icon_label.hide()

    def setText(self, text):
        """Sets the string representation inside the nested text label."""
        if hasattr(self, "_text_label"):
            self._text_label.setText(text)
            self._text_label.adjustSize()
            self.updateGeometry()
        else:
            super().setText("")

    def setSpacing(self, spacing):
        """Adjusts the layout spacing between the inner icon and text."""
        self._layout.setSpacing(spacing)

    def setTextColorClass(self, class_name):
        """
        Applies a CSS class to the internal text QLabel to change the text color
        (e.g., 'textColorPrimary', 'textColorWhite').
        """
        self._text_label.setProperty("class", class_name)
        self._text_label.style().unpolish(self._text_label)
        self._text_label.style().polish(self._text_label)
