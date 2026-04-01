"""
Vinyller — Search services tools and dialogs
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

import urllib.parse
from functools import partial

from PyQt6.QtCore import (
    QSize, Qt,
    QUrl
)
from PyQt6.QtGui import (
    QAction, QDesktopServices
)
from PyQt6.QtWidgets import (
    QCheckBox, QDialogButtonBox,
    QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget, QSizePolicy
)

from src.ui.custom_base_dialogs import StyledDialog
from src.ui.custom_base_widgets import (
    StyledLineEdit, StyledToolButton, set_custom_tooltip
)
from src.utils import theme
from src.utils.utils import (
    create_svg_icon
)
from src.utils.utils_translator import translate


class SearchToolButton(StyledToolButton):
    """
    A custom tool button that reveals a drop-down menu with various external search services.
    It can dynamically generate search URLs based on context.
    """
    def __init__(self, main_window = None, parent = None):
        """
        Initialize the search tool button.

        :param main_window: Main application window reference.
        :param parent: Parent widget.
        """
        super().__init__(parent)
        self.mw = main_window

        self.setText(translate("Search..."))
        self.setFixedHeight(36)
        self.setProperty("class", "btnToolMenuBorder")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        set_custom_tooltip(
            self,
            title = translate("Search Online..."),
            text = translate("Select a service to search information online"),
            activity_type="external"
        )
        self._data_getter = None
        self.lyrics_mode = False

    def set_main_window(self, mw):
        """
        Assign or update the main window reference.

        :param mw: Main application window.
        """
        self.mw = mw

    def set_lyrics_mode(self, enabled: bool):
        """
        Toggle the mode to filter search links specifically for lyrics finding.

        :param enabled: True if lyrics mode should be enabled.
        """
        self.lyrics_mode = enabled
        if enabled:
            set_custom_tooltip(
                self,
                title = translate("Search lyrics online"),
                text = translate("Select a service to search information online"),
                activity_type="external"
            )
        else:
            set_custom_tooltip(
                self,
                title = translate("Search Online..."),
                text = translate("Select a service to search information online"),
                activity_type="external"
            )

    def set_data_getter(self, getter_func):
        """
        Register a callback function that returns the search context/parameters when triggered.

        :param getter_func: Function returning a list of strings representing search parts.
        """
        self._data_getter = getter_func

    def show_custom_menu(self):
        """
        Override the parent method. Rebuilds the search menu options before showing it.
        """
        self._rebuild_logic_menu()
        super().show_custom_menu()

    def _rebuild_logic_menu(self):
        """
        Populate the QMenu logically with loaded external search link templates.
        """
        m = self.menu()
        m.clear()

        if not self.mw:
            links = [
                {
                    "name": "Google",
                    "url": "https://www.google.com/search?q={query}",
                    "is_custom": False,
                    "lyrics": True,
                }
            ]
        else:
            links = self.mw.library_manager.load_search_links()

        for link in links:
            name = link["name"]
            url_tmpl = link["url"]
            is_suitable_for_lyrics = link.get("lyrics", False)

            if self.lyrics_mode and not is_suitable_for_lyrics:
                continue

            action = QAction(name, m)
            action.triggered.connect(partial(self._perform_search, url_tmpl))
            m.addAction(action)

        m.addSeparator()

        add_action = QAction(
            create_svg_icon(
                "assets/control/add.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            ),
            translate("Add Custom..."),
            m,
        )
        add_action.triggered.connect(self._open_add_dialog)
        m.addAction(add_action)

    def _open_add_dialog(self):
        """
        Open the wizard dialog to create and add a custom search template.
        """
        dlg = AddSearchLinkDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if data and self.mw:
                self.mw.library_manager.add_custom_search_link(
                    data["name"], data["url"], is_lyrics_suitable = data["lyrics"]
                )

    def _perform_search(self, url_pattern):
        """
        Execute the web search by filling the template and opening it in the system browser.

        :param url_pattern: The URL template string to format and open.
        """
        if not self._data_getter:
            return

        parts = self._data_getter()
        if not parts:
            return

        query = " ".join([str(p).strip() for p in parts if p]).strip()
        if not query:
            return

        if self.lyrics_mode and (
                "google" in url_pattern or "duckduckgo" in url_pattern
        ):
            if "lyrics" not in query.lower():
                query = f"Lyrics {query}"

        safe_query = urllib.parse.quote(query)

        if "{query}" in url_pattern:
            url = url_pattern.replace("{query}", safe_query)
        elif "{}" in url_pattern:
            url = url_pattern.replace("{}", safe_query)
        else:
            url = url_pattern + safe_query

        QDesktopServices.openUrl(QUrl(url))


class AddSearchLinkDialog(StyledDialog):
    """
    Dialog for creating or editing a search template (2-step Wizard).
    """

    def __init__(self, parent = None, edit_name = None, edit_url = None, edit_lyrics = False, title=""):
        """
        Initialize the wizard dialog.

        :param parent: Parent widget.
        :param edit_name: Name of the existing link if editing, else None.
        :param edit_url: URL template of the existing link if editing, else None.
        :param edit_lyrics: Boolean flag indicating if it's currently marked suitable for lyrics.
        """
        super().__init__(parent, title=title)
        self.is_edit_mode = edit_name is not None

        title_text = translate("Search Service Editor")
        self.setWindowTitle(title_text)
        self.setMinimumWidth(720)
        self.setProperty("class", "backgroundPrimary")

        self.result_data = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stacked_widget = QStackedWidget()

        step1_widget = QWidget()
        step1_layout = QVBoxLayout(step1_widget)
        step1_layout.setContentsMargins(24, 24, 24, 24)
        step1_layout.setSpacing(16)

        header_text = (
            translate("Edit Search Service")
            if self.is_edit_mode
            else translate("New Search Service")
        )
        header = QLabel(header_text)
        header.setProperty("class", "textHeaderSecondary textColorPrimary")
        step1_layout.addWidget(header)

        info_lbl = QLabel(
            translate("Search Service description text...")
        )
        info_lbl.setWordWrap(True)
        info_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        info_lbl.setProperty("class", "textSecondary textColorPrimary")
        step1_layout.addWidget(info_lbl)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(16)

        def make_label(text):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl.setProperty("class", "textSecondary textColorPrimary")
            return lbl

        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)
        title_layout.addWidget(make_label(translate("Service Title:")))

        self.name_edit = StyledLineEdit()
        self.name_edit.setFixedHeight(36)
        self.name_edit.setPlaceholderText(translate("e.g. My Favorite Wiki"))
        self.name_edit.setProperty("class", "inputBorderSinglePadding")
        if edit_name:
            self.name_edit.setText(edit_name)
        title_layout.addWidget(self.name_edit)
        form_layout.addLayout(title_layout)

        url_layout = QVBoxLayout()
        url_layout.setSpacing(8)
        url_layout.addWidget(make_label(translate("Sample URL:")))

        self.url_edit = StyledLineEdit()
        self.url_edit.setFixedHeight(36)
        self.url_edit.setPlaceholderText("https://google.com/search?q=Level+42")
        self.url_edit.setProperty("class", "inputBorderSinglePadding")
        if edit_url:
            self.url_edit.setText(edit_url)
        url_layout.addWidget(self.url_edit)
        form_layout.addLayout(url_layout)

        query_layout = QVBoxLayout()
        query_layout.setSpacing(8)
        query_layout.addWidget(make_label(translate("Query word of the URL:")))

        self.query_edit = StyledLineEdit()
        self.query_edit.setFixedHeight(36)
        self.query_edit.setPlaceholderText(translate("e.g. Level 42"))
        self.query_edit.setProperty("class", "inputBorderSinglePadding")
        if self.is_edit_mode and edit_url and "{query}" in edit_url:
            self.query_edit.setPlaceholderText(
                translate("Optional if 'query' is already in URL field")
            )
        query_layout.addWidget(self.query_edit)
        form_layout.addLayout(query_layout)

        self.lyrics_checkbox = QCheckBox(translate("Suitable for lyrics search"))
        self.lyrics_checkbox.setMinimumHeight(18)
        self.lyrics_checkbox.setProperty("class", "textColorPrimary")
        self.lyrics_checkbox.setCursor(Qt.CursorShape.WhatsThisCursor)
        set_custom_tooltip(
            self.lyrics_checkbox,
            title = translate("Suitable for lyrics search"),
            text = translate("If checked, this search service will appear in the metadata editor."),
        )
        if edit_lyrics:
            self.lyrics_checkbox.setChecked(True)
        form_layout.addWidget(self.lyrics_checkbox)

        step1_layout.addLayout(form_layout)
        step1_layout.addStretch()
        self.stacked_widget.addWidget(step1_widget)

        step2_widget = QWidget()
        step2_layout = QVBoxLayout(step2_widget)
        step2_layout.setContentsMargins(24, 24, 24, 24)
        step2_layout.setSpacing(16)

        step2_header = QLabel(translate("Review Generated URL"))
        step2_header.setProperty("class", "textHeaderSecondary textColorPrimary")
        step2_layout.addWidget(step2_header)

        step2_info = QLabel(
            translate(
                "Verify that the search query was correctly replaced with the {{query}} variable, and save the new search service.")
        )
        step2_info.setWordWrap(True)
        step2_info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        step2_info.setProperty("class", "textSecondary textColorPrimary")
        step2_layout.addWidget(step2_info)

        self.final_url_edit = StyledLineEdit()
        self.final_url_edit.setFixedHeight(36)
        self.final_url_edit.setProperty("class", "inputBorderSinglePadding")
        step2_layout.addWidget(self.final_url_edit)
        step2_layout.addStretch()

        self.stacked_widget.addWidget(step2_widget)
        layout.addWidget(self.stacked_widget, 1)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.error_label = QLabel("")
        self.error_label.setProperty("class", "textPrimary textColorAccent")
        self.error_label.setWordWrap(True)
        self.error_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.error_label.hide()
        bottom_layout.addWidget(self.error_label, 1)

        bottom_layout.addStretch()

        self.btn_box = QDialogButtonBox(self)

        self.btn_back = QPushButton(translate("Back"))
        self.btn_cancel = QPushButton(translate("Cancel"))

        next_btn_text = translate("Save") if self.is_edit_mode else translate("Next")
        self.btn_next = QPushButton(next_btn_text)

        self.btn_box.addButton(self.btn_back, QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_box.addButton(self.btn_cancel, QDialogButtonBox.ButtonRole.RejectRole)
        self.btn_box.addButton(self.btn_next, QDialogButtonBox.ButtonRole.AcceptRole)

        self.btn_back.hide()

        if self.btn_box.layout():
            self.btn_box.layout().setSpacing(16)

        for btn in self.btn_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_box.rejected.connect(self.reject)
        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)

        bottom_layout.addWidget(self.btn_box)
        layout.addWidget(bottom_panel)

        self.name_edit.textChanged.connect(self.error_label.hide)
        self.url_edit.textChanged.connect(self.error_label.hide)
        self.query_edit.textChanged.connect(self.error_label.hide)

    def _show_error(self, message):
        """
        Display an inline error message in the wizard.

        :param message: The error string to display.
        """
        self.error_label.setText(message)
        self.error_label.show()

    def _go_back(self):
        """
        Return to the first step of the wizard from the second step.
        """
        self.stacked_widget.setCurrentIndex(0)
        self.btn_back.hide()
        next_btn_text = translate("Save") if self.is_edit_mode else translate("Next")
        self.btn_next.setText(next_btn_text)
        self.error_label.hide()

    def _go_next(self):
        """
        Proceed to the next wizard step or finalize the wizard if complete.
        Validates URL templates and query matching.
        """
        if self.stacked_widget.currentIndex() == 0:
            name = self.name_edit.text().strip()
            url = self.url_edit.text().strip()
            query = self.query_edit.text().strip()

            if not name or not url:
                self._show_error(translate("Title and URL are required!"))
                return

            if "{query}" in url or "{}" in url:
                self.result_data = {
                    "name": name,
                    "url": url,
                    "lyrics": self.lyrics_checkbox.isChecked(),
                }
                self.accept()
                return

            if query:
                variants = [
                    urllib.parse.quote_plus(query),
                    urllib.parse.quote(query),
                    query
                ]

                last_idx = -1
                match_len = 0
                url_lower = url.lower()

                for variant in variants:
                    var_lower = variant.lower()
                    idx = url_lower.rfind(var_lower)
                    if idx > last_idx:
                        last_idx = idx
                        match_len = len(variant)

                if last_idx != -1:
                    template = url[:last_idx] + "{query}" + url[last_idx + match_len:]

                    self.error_label.hide()
                    self.final_url_edit.setText(template)
                    self.stacked_widget.setCurrentIndex(1)
                    self.btn_back.show()

                    final_btn_text = translate("Save")
                    self.btn_next.setText(final_btn_text)
                else:
                    self._show_error(translate("Text not found in URL!"))
                    return
            else:
                self._show_error(translate("Query text required!"))
                return

        elif self.stacked_widget.currentIndex() == 1:
            name = self.name_edit.text().strip()
            final_url = self.final_url_edit.text().strip()

            if not final_url:
                return

            self.result_data = {
                "name": name,
                "url": final_url,
                "lyrics": self.lyrics_checkbox.isChecked(),
            }
            self.accept()

    def get_data(self):
        """
        Get the final created or modified template dictionary.

        :return: A dictionary containing the 'name', 'url', and 'lyrics' flag.
        """
        return self.result_data

