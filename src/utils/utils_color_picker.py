"""
Vinyller — Color picker class
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

import json
import re
from pathlib import Path

from PyQt6.QtCore import (
    QSize, Qt, pyqtSignal, QRectF, QPointF
)
from PyQt6.QtGui import (
    QColor, QPainter, QLinearGradient, QPen, QPainterPath,
    QRadialGradient, QPixmap, QBrush, QTransform
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton,
    QWidget, QVBoxLayout, QFrame
)

from src.ui.custom_base_widgets import StyledLineEdit, StyledScrollArea, ShadowPopup, set_custom_tooltip
from src.ui.custom_classes import apply_button_opacity_effect, FlowLayout
from src.utils import theme
from src.utils.constants import VINYLLER_FOLDER
from src.utils.utils import create_svg_icon
from src.utils.utils_translator import translate


def get_colors_file_path() -> Path:
    """Returns the path to the saved colors JSON file."""
    return Path.home() / VINYLLER_FOLDER / "saved_colors.json"


def load_saved_colors() -> list:
    """Loads the list of saved hex codes from disk."""
    path = get_colors_file_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def add_saved_color_to_storage(hex_color: str):
    """
    Adds a color to storage.
    If the color already exists, it moves it to the beginning of the list.
    """
    colors = load_saved_colors()

    if hex_color in colors:
        colors.remove(hex_color)

    colors.insert(0, hex_color)

    try:
        path = get_colors_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(colors, f, ensure_ascii=False, indent=4)
    except IOError:
        pass


def remove_saved_color_from_storage(hex_color: str):
    """Removes a specific color from the storage JSON file."""
    colors = load_saved_colors()
    if hex_color in colors:
        colors.remove(hex_color)
        try:
            path = get_colors_file_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(colors, f, ensure_ascii=False, indent=4)
        except IOError:
            pass


def get_relative_luminance(color: QColor) -> float:
    """Calculates relative luminance according to WCAG 2.0 standards."""
    def adjust(c):
        """
        Applies gamma correction to a color channel value (sRGB to linear RGB)
        as required by the WCAG relative luminance formula.
        """
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r = adjust(color.red())
    g = adjust(color.green())
    b = adjust(color.blue())
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def get_contrast_ratio(c1: QColor, c2: QColor) -> float:
    """Calculates the contrast ratio between two colors (ranging from 1.0 to 21.0)."""
    l1 = get_relative_luminance(c1)
    l2 = get_relative_luminance(c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class SavedColorSwatch(QPushButton):
    """
    A 24x24 rounded rectangle representing a saved color.
    Left click: Select the color.
    Right click: Delete the color from storage.
    """
    colorSelected = pyqtSignal(str)
    colorDeleted = pyqtSignal(str)

    def __init__(self, hex_color, parent=None):
        """Initializes the swatch with a specific hex color and tooltip."""
        super().__init__(parent)
        self.hex_color = hex_color
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            self,
            title = hex_color,
            text = translate("Right-click to delete the color"),
        )
        self.setProperty("class", "btnColorSwatch")
        self.setStyleSheet(f"""QPushButton{{background-color: {hex_color};}}""")

    def mousePressEvent(self, event):
        """Emits deletion signal on right click or selection signal on left click."""
        if event.button() == Qt.MouseButton.RightButton:
            self.colorDeleted.emit(self.hex_color)
        else:
            self.colorSelected.emit(self.hex_color)
            super().mousePressEvent(event)


class ColorPickerPopup(ShadowPopup):
    """
    A popup widget for selecting colors using HSV (Hue, Saturation, Value).
    Includes a contrast checker against the theme background.
    """
    colorChanged = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, initial_color="#FFFFFF", parent=None):
        """Initializes the UI, layouts, and initial color values."""
        super().__init__(parent)

        margins = self.layout.contentsMargins()
        self.setFixedWidth(256 + margins.left() + margins.right())

        self.initial_hex = initial_color
        c = QColor(initial_color)
        if not c.isValid():
            c = QColor("#FFFFFF")

        self.hue = c.hueF() if c.hue() != -1 else 0.0
        self.sat = c.saturationF()
        self.val = c.valueF()

        self.bg = QWidget()
        self.bg.setProperty("class", "backgroundTransparent")

        bg_layout = QVBoxLayout(self.bg)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.setSpacing(12)

        header_widget = QWidget()
        header_widget.setProperty("class", "borderBottom")

        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 6, 6, 6)
        header_layout.setSpacing(8)

        cpicker_title = QLabel()
        cpicker_title.setText(translate("Pick a color"))
        cpicker_title.setProperty("class", "textPrimary")
        header_layout.addWidget(cpicker_title)

        header_layout.addStretch()

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.btn_contrast = QPushButton()
        self.btn_contrast.setFixedSize(24, 24)
        self.btn_contrast.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_contrast.setIcon(
            create_svg_icon("assets/control/contrast.svg", theme.COLORS["PRIMARY"], QSize(20, 20)))
        self.btn_contrast.setIconSize(QSize(20, 20))
        self.btn_contrast.setProperty("class", "btnTool")
        self.btn_contrast.setCheckable(True)
        self.btn_contrast.setChecked(True)
        set_custom_tooltip(
            self.btn_contrast,
            title = translate("Contrast Areas"),
            text = translate("You can toggle the visibility of low-contrast areas, which will be marked with a dots."),
        )
        apply_button_opacity_effect(self.btn_contrast)
        actions_layout.addWidget(self.btn_contrast)

        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setIcon(create_svg_icon("assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(20, 20)))
        self.btn_close.setIconSize(QSize(20, 20))
        self.btn_close.setProperty("class", "btnTool")
        apply_button_opacity_effect(self.btn_close)
        set_custom_tooltip(
            self.btn_close,
            title = translate("Close"),
        )
        self.btn_close.clicked.connect(self._on_close_clicked)

        actions_layout.addWidget(self.btn_close)
        header_layout.addLayout(actions_layout)
        bg_layout.addWidget(header_widget)

        pick_layout = QVBoxLayout()
        pick_layout.setContentsMargins(6, 0, 6, 0)
        pick_layout.setSpacing(0)

        self.sv_area = SVAreaWidget(self.hue, self.sat, self.val)
        self.sv_area.colorChanged.connect(self._update_from_sv)
        pick_layout.addWidget(self.sv_area)

        self.hue_slider = HueSliderWidget(self.hue)
        self.hue_slider.hueChanged.connect(self._update_from_hue)
        pick_layout.addWidget(self.hue_slider)

        bg_layout.addLayout(pick_layout)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(16, 0, 16, 0)
        input_layout.setSpacing(0)

        self.preview_box = QLabel()
        self.preview_box.setFixedSize(36, 36)
        self.preview_box.setStyleSheet(f"background-color: {c.name()};")
        self.preview_box.setProperty("class", "inputBorderMultiLeft")

        self.hex_input = StyledLineEdit(c.name().upper())
        self.hex_input.setFixedHeight(36)
        self.hex_input.setPlaceholderText("#RRGGBB")
        self.hex_input.textChanged.connect(self._on_hex_input)
        self.hex_input.setProperty("class", "inputBorderMultiMiddle inputBorderPaddingTextEdit bold")

        self.btn_save = QPushButton()
        self.btn_save.setFixedSize(36, 36)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setIcon(create_svg_icon("assets/control/add.svg", theme.COLORS["PRIMARY"], QSize(20, 20)))
        self.btn_save.setIconSize(QSize(20, 20))
        self.btn_save.setProperty("class", "inputBorderMultiRight")
        set_custom_tooltip(
            self.btn_save,
            title = translate("Save current color"),
        )
        apply_button_opacity_effect(self.btn_save)
        self.btn_save.clicked.connect(self._on_save_clicked)

        input_layout.addWidget(self.preview_box)
        input_layout.addWidget(self.hex_input)
        input_layout.addWidget(self.btn_save)
        bg_layout.addLayout(input_layout)
        bg_layout.addSpacing(8)

        self.saved_area = StyledScrollArea()
        self.saved_area.setContentsMargins(0, 0, 0, 0)
        self.saved_area.setFixedHeight(108)
        self.saved_area.setWidgetResizable(True)
        self.saved_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.saved_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.saved_area.setFrameShape(QFrame.Shape.NoFrame)
        self.saved_area.setProperty("class", "borderTop backgroundTransparent")

        self.saved_container = QWidget()
        self.saved_container.setContentsMargins(16, 16, 8, 16)
        self.saved_container.setProperty("class", "backgroundTransparent")
        self.saved_layout = FlowLayout(self.saved_container)
        self.saved_layout.setSpacing(8)
        self.saved_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.saved_area.setWidget(self.saved_container)
        bg_layout.addWidget(self.saved_area)

        self._populate_saved_colors()

        hint_container = QWidget()
        hint_container.setContentsMargins(16, 16, 16, 16)
        hint_container.setProperty("class", "borderTop")

        hint_layout = QHBoxLayout(hint_container)
        hint_layout.setContentsMargins(0, 0, 0, 0)
        hint_layout.setSpacing(0)

        self.lbl_contrast_value = QLabel()
        self.lbl_contrast_value.setProperty("class", "textSecondary")
        hint_layout.addWidget(self.lbl_contrast_value)

        hint_layout.addStretch()

        self.lbl_contrast_desc = QLabel()
        self.lbl_contrast_desc.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hint_layout.addWidget(self.lbl_contrast_desc)

        bg_layout.addWidget(hint_container)

        self.btn_contrast.toggled.connect(self.sv_area.set_mask_visible)
        self.layout.addWidget(self.bg)

        self._update_contrast_stats(c)

    def _update_contrast_stats(self, color: QColor):
        """
        Calculates WCAG contrast against the current theme's SECONDARY color.
        Updates the labels with value and status (Critically Low/Low/Normal/Good).
        """
        bg_color = theme.get_qcolor(theme.COLORS.get("SECONDARY", "#FFFFFF"))

        ratio = get_contrast_ratio(color, bg_color)
        self.lbl_contrast_value.setText(f"<b>{translate('Contrast Ratio')}</b>: {ratio:.2f}:1")

        # WCAG AA requires 4.5:1 for normal text and 3:1 for large text.
        if ratio < 1.5:
            status_text = translate("Critically Low")
        elif ratio < 3.0:
            status_text = translate("Low")
        elif ratio < 4.5:
            status_text = translate("Normal")
        else:
            status_text = translate("Good")

        self.lbl_contrast_desc.setText(status_text)

        hex_color = color.name()

        self.lbl_contrast_desc.setStyleSheet(f"""QLabel{{color: {hex_color}; font-weight: bold;}}""")

        labels = [self.lbl_contrast_value, self.lbl_contrast_desc]

        for label in labels:
            set_custom_tooltip(
                label,
                title = translate("Color Contrast"),
                text = translate("To maintain the readability of interactive elements, you should avoid choosing colors that are too light for a light theme or too dark for a dark theme. For example, the WCAG AA standard requires a contrast ratio of 4.5:1 for normal text and 3:1 for large text to ensure high readability."),
            )
            label.setCursor(Qt.CursorShape.WhatsThisCursor)

    def _update_from_sv(self, s, v):
        """Internal handler for Saturation/Value changes."""
        self.sat = s
        self.val = v
        self._finalize_color()

    def _update_from_hue(self, h):
        """Internal handler for Hue slider changes."""
        self.hue = h
        self.sv_area.set_hue(h)
        self._finalize_color()

    def _on_hex_input(self, text):
        """Validates and applies color changes from the HEX line edit."""
        clean_text = re.sub(r'[^0-9A-F]', '', text.upper())
        if len(clean_text) > 6:
            clean_text = clean_text[:6]
        formatted_text = "#" + clean_text

        if self.hex_input.text() != formatted_text:
            self.hex_input.blockSignals(True)
            self.hex_input.setText(formatted_text)
            self.hex_input.setCursorPosition(len(formatted_text))
            self.hex_input.blockSignals(False)

        if len(clean_text) == 3 or len(clean_text) == 6:
            c = QColor(formatted_text)
            if c.isValid():
                self.hue = c.hueF() if c.hue() != -1 else 0.0
                self.sat = c.saturationF()
                self.val = c.valueF()

                self.sv_area.update_pos(self.sat, self.val)
                self.hue_slider.update_pos(self.hue)
                self.sv_area.set_hue(self.hue)

                self.preview_box.setStyleSheet(f"background-color: {c.name()};")
                self.preview_box.setProperty("class", "inputBorderMultiLeft")

                self._update_contrast_stats(c)

                self.colorChanged.emit(c.name().upper())

    def _finalize_color(self):
        """
        Called whenever SV area or Hue slider changes.
        Calculates color, updates UI inputs AND contrast stats instantly.
        """
        c = QColor.fromHsvF(self.hue, self.sat, self.val)
        hex_code = c.name().upper()

        self.preview_box.setStyleSheet(f"background-color: {hex_code};")
        self.preview_box.setProperty("class", "inputBorderMultiLeft")

        self.hex_input.blockSignals(True)
        self.hex_input.setText(hex_code)
        self.hex_input.blockSignals(False)

        self._update_contrast_stats(c)

        self.colorChanged.emit(hex_code)

    def _on_save_clicked(self):
        """Saves current color via standalone function and updates the saved colors list."""
        current_hex = self.hex_input.text()
        if QColor(current_hex).isValid():
            add_saved_color_to_storage(current_hex)
            self._populate_saved_colors()

    def _on_swatch_deleted(self, hex_color):
        """Handles deletion request from a SavedColorSwatch."""
        remove_saved_color_from_storage(hex_color)
        self._populate_saved_colors()

    def _on_swatch_selected(self, hex_color):
        """Handles selection request from a SavedColorSwatch."""
        self._on_hex_input(hex_color)

    def _populate_saved_colors(self):
        """Re-renders the saved colors layout by fetching data from storage."""
        while self.saved_layout.count():
            item = self.saved_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        saved_colors = load_saved_colors()
        if not saved_colors:
            self.saved_area.hide()
            return

        self.saved_area.show()

        for color_hex in saved_colors:
            swatch = SavedColorSwatch(color_hex)
            swatch.colorSelected.connect(self._on_swatch_selected)
            swatch.colorDeleted.connect(self._on_swatch_deleted)
            self.saved_layout.addWidget(swatch)

    def _on_close_clicked(self):
        """Triggers the popup closure."""
        self.close()

    def closeEvent(self, event):
        """Emits 'closed' signal when the widget is hidden/closed."""
        self.closed.emit()
        super().closeEvent(event)


class SVAreaWidget(QWidget):
    """Square area for Saturation (X) and Value (Y) selection with low-contrast masking."""
    colorChanged = pyqtSignal(float, float)

    def __init__(self, h, s, v, parent=None):
        """Initializes the SV selection area and calculates the initial contrast mask."""
        super().__init__(parent)
        self.setFixedHeight(200)
        self.hue = h
        self.sat = s
        self.val = v
        self.margin = 10
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.mask_visible = True
        self.bg_color_ref = theme.get_qcolor(theme.COLORS.get("SECONDARY", "#FFFFFF"))
        self.fill_path = QPainterPath()
        self.border_path = QPainterPath()
        self._recalc_contrast_mask()

    def set_mask_visible(self, visible: bool):
        """Toggles the visibility of the low-contrast dotted mask."""
        self.mask_visible = visible
        self.update()

    def set_hue(self, h):
        """Updates the hue and recalculates the mask for the new hue plane."""
        self.hue = h
        self._recalc_contrast_mask()
        self.update()

    def update_pos(self, s, v):
        """Manually updates the Saturation and Value cursor position."""
        self.sat = s
        self.val = v
        self.update()

    def _create_dot_brush(self, color):
        """Creates a tiled pixmap brush for the low-contrast area overlay."""
        tile_size = 9
        dot_size = 3

        pixmap = QPixmap(tile_size, tile_size)
        pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)

        center = tile_size / 2
        radius = dot_size / 2
        p.drawEllipse(QPointF(center, center), radius, radius)
        p.end()

        return QBrush(pixmap)

    def _recalc_contrast_mask(self):
        """
        Calculates areas on the SV plane that have a contrast ratio below 1.5:1
        relative to the background. Generates paths for filling and bordering.
        """
        self.fill_path = QPainterPath()
        self.border_path = QPainterPath()

        calc_w, calc_h = 200.0, 200.0
        step_x = 4
        threshold = 1.5

        bg_color = theme.get_qcolor(theme.COLORS.get("SECONDARY", "#FFFFFF"))
        bg_lum = get_relative_luminance(bg_color)

        l_bad_min = (bg_lum + 0.05) / threshold - 0.05
        l_bad_max = threshold * (bg_lum + 0.05) - 0.05

        top_points = []
        bottom_points = []
        was_inside = False

        for x_i in range(0, int(calc_w) + 1, step_x):
            x = min(float(x_i), calc_w)
            s = x / calc_w

            c_black = QColor.fromHsvF(self.hue, s, 0.0)
            c_white = QColor.fromHsvF(self.hue, s, 1.0)
            l_at_0 = get_relative_luminance(c_black)
            l_at_1 = get_relative_luminance(c_white)

            col_min = min(l_at_0, l_at_1)
            col_max = max(l_at_0, l_at_1)

            intersect_min = max(col_min, l_bad_min)
            intersect_max = min(col_max, l_bad_max)

            if intersect_min > intersect_max:
                if was_inside:
                    self._close_polygon_segment(top_points, bottom_points)
                    top_points = []
                    bottom_points = []
                    was_inside = False
                continue

            was_inside = True

            def get_v_for_l(target_l):
                """
                Uses binary search to approximate the required HSV Value (V)
                that results in the target relative luminance for the current Hue and Saturation.
                """
                if target_l <= col_min: return 0.0
                if target_l >= col_max: return 1.0

                low, high = 0.0, 1.0
                for _ in range(8):
                    mid = (low + high) / 2
                    if get_relative_luminance(QColor.fromHsvF(self.hue, s, mid)) < target_l:
                        low = mid
                    else:
                        high = mid
                return (low + high) / 2

            v_start = get_v_for_l(intersect_min)
            v_end = get_v_for_l(intersect_max)

            y_top = (1.0 - v_end) * calc_h
            y_bot = (1.0 - v_start) * calc_h

            top_points.append(QPointF(x, y_top))
            bottom_points.append(QPointF(x, y_bot))

            epsilon = 0.5
            if v_end < 1.0 - epsilon / calc_h:
                if len(top_points) >= 2:
                    self.border_path.moveTo(top_points[-2])
                    self.border_path.lineTo(top_points[-1])

            if v_start > 0.0 + epsilon / calc_h:
                if len(bottom_points) >= 2:
                    self.border_path.moveTo(bottom_points[-2])
                    self.border_path.lineTo(bottom_points[-1])

        if was_inside:
            self._close_polygon_segment(top_points, bottom_points)

    def _close_polygon_segment(self, top, bottom):
        """Closes the detected low-contrast area into a polygon path."""
        if not top or not bottom: return

        poly = QPainterPath()
        poly.moveTo(top[0])
        for p in top[1:]:
            poly.lineTo(p)

        for p in reversed(bottom):
            poly.lineTo(p)

        poly.closeSubpath()
        self.fill_path.addPath(poly)

    def paintEvent(self, event):
        """Renders the HSV gradient, the contrast mask, and the selection cursor."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(self.margin, self.margin, -self.margin, -self.margin)

        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 4, 4)

        painter.save()
        painter.setClipPath(path)

        base_color = QColor.fromHsvF(self.hue, 1.0, 1.0)
        h_grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
        h_grad.setColorAt(0, Qt.GlobalColor.white)
        h_grad.setColorAt(1, base_color)
        painter.fillRect(rect, h_grad)

        v_grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        v_grad.setColorAt(0, QColor(0, 0, 0, 0))
        v_grad.setColorAt(1, Qt.GlobalColor.black)
        painter.fillRect(rect, v_grad)

        if self.mask_visible and not self.fill_path.isEmpty():
            painter.save()
            scale_x = rect.width() / 200.0
            scale_y = rect.height() / 200.0

            transform = QTransform()
            transform.translate(rect.left(), rect.top())
            transform.scale(scale_x, scale_y)

            final_fill = transform.map(self.fill_path)
            final_border = transform.map(self.border_path)

            is_dark_bg = theme.get_relative_luminance(self.bg_color_ref) < 0.5
            overlay_color = QColor(255, 255, 255, 88) if is_dark_bg else QColor(0, 0, 0, 72)

            dot_brush = self._create_dot_brush(overlay_color)
            painter.fillPath(final_fill, dot_brush)

            if not final_border.isEmpty():
                pen = QPen(overlay_color, 2)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(final_border)

            painter.restore()

        painter.restore()

        border_color = QColor(theme.COLORS.get("WIDGET_BRD_PRIMARY"))
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawPath(path)

        x = rect.left() + (self.sat * rect.width())
        y = rect.top() + ((1 - self.val) * rect.height())
        center = QPointF(x, y)
        shadow_center = QPointF(x + 1, y + 1)

        shadow_grad = QRadialGradient(shadow_center, 10)
        shadow_grad.setColorAt(0.5, QColor(0, 0, 0, 127))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(shadow_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 10, 10)

        current_color = QColor.fromHsvF(self.hue, self.sat, self.val)
        painter.setBrush(current_color)
        painter.setPen(QPen(Qt.GlobalColor.white, 2.5))
        painter.drawEllipse(center, 7, 7)

    def mousePressEvent(self, event):
        """Triggers color selection on click."""
        self._handle_mouse(event.pos())

    def mouseMoveEvent(self, event):
        """Triggers color selection on drag."""
        self._handle_mouse(event.pos())

    def _handle_mouse(self, pos):
        """Calculates Saturation and Value based on mouse position within the widget."""
        rect = self.rect().adjusted(self.margin, self.margin, -self.margin, -self.margin)
        s = (pos.x() - rect.left()) / rect.width()
        v = 1.0 - ((pos.y() - rect.top()) / rect.height())
        self.sat = max(0.0, min(1.0, s))
        self.val = max(0.0, min(1.0, v))
        self.update()
        self.colorChanged.emit(self.sat, self.val)


class HueSliderWidget(QWidget):
    """A horizontal rainbow slider for selecting the color Hue."""
    hueChanged = pyqtSignal(float)

    def __init__(self, h, parent=None):
        """Initializes the hue slider with a specific initial hue."""
        super().__init__(parent)
        self.setFixedHeight(22)
        self.hue = h
        self.margin = 10
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_pos(self, h):
        """Updates the hue value and repaints the cursor position."""
        self.hue = h
        self.update()

    def paintEvent(self, event):
        """Renders the rainbow gradient track and the hue selection handle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_height = 16
        track_y = (self.height() - track_height) // 2
        rect = QRectF(self.margin, track_y, self.width() - 2 * self.margin, track_height)

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        painter.save()
        painter.setClipPath(path)
        gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        for i, color in enumerate([
            (0.0, 255, 0, 0), (0.16, 255, 255, 0), (0.33, 0, 255, 0),
            (0.5, 0, 255, 255), (0.66, 0, 0, 255), (0.83, 255, 0, 255), (1.0, 255, 0, 0)
        ]):
            gradient.setColorAt(color[0], QColor(color[1], color[2], color[3]))
        painter.fillRect(rect, gradient)
        painter.restore()

        border_color = QColor(theme.COLORS.get("WIDGET_BRD_PRIMARY"))
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.GlobalColor.transparent)

        x = rect.left() + (self.hue * rect.width())
        y = rect.center().y()
        center = QPointF(x, y)
        shadow_center = QPointF(x + 1, y + 1)

        shadow_radius = 10
        shadow_grad = QRadialGradient(shadow_center, shadow_radius)
        shadow_grad.setColorAt(0.5, QColor(0, 0, 0, 127))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setBrush(shadow_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(shadow_center, shadow_radius, shadow_radius)

        current_hue_color = QColor.fromHsvF(self.hue, 1.0, 1.0)

        painter.setBrush(current_hue_color)
        painter.setPen(QPen(Qt.GlobalColor.white, 2.5))
        painter.drawEllipse(center, 7, 7)

    def mousePressEvent(self, event):
        """Triggers hue selection on click."""
        self._handle_mouse(event.pos())

    def mouseMoveEvent(self, event):
        """Triggers hue selection on drag."""
        self._handle_mouse(event.pos())

    def _handle_mouse(self, pos):
        """Calculates Hue value based on mouse position within the slider track."""
        h = max(0.0, min(1.0, (pos.x() - self.margin) / (self.width() - 2 * self.margin)))
        self.hue = h
        self.update()
        self.hueChanged.emit(h)