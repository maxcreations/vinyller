"""
Vinyller — Encyclopedia article editor dialog
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
import os
import re
from functools import partial
from urllib.parse import urlparse

from PyQt6.QtCore import (
    QRect, QSize, Qt, QTimer
)
from PyQt6.QtGui import (
    QAction, QColor, QIcon, QPainter, QPen, QPixmap
)
from PyQt6.QtWidgets import (
    QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget, QSizePolicy
)

from src.encyclopedia.encyclopedia_components import (
    BlockListItemWidget, BlockWidget, CleanRichTextEdit, DiscographyItemWidget,
    GalleryImageItem, LinkWidget, RelationsItemWidget
)
from src.encyclopedia.encyclopedia_dialogs import (
    EncyclopediaConflictDialog, RelationsSyncDialog, EncyclopediaSearchDialog
)
from src.encyclopedia.encyclopedia_manager import FetchWorker
from src.ui.custom_base_dialogs import StyledDialog
from src.ui.custom_base_widgets import (
    StyledLineEdit, StyledListWidget, StyledScrollArea,
    TranslucentCombo, TranslucentMenu, StyledToolButton, set_custom_tooltip
)
from src.ui.custom_classes import (
    apply_button_opacity_effect,
    ElidedLabel, FlowLayout, GapCompleter,
    MetadataMergeControl, RoundedCoverLabel
)
from src.ui.custom_dialogs import (
    CustomConfirmDialog, DeleteWithCheckboxDialog
)
from src.ui.search_services_tools import SearchToolButton
from src.utils import theme
from src.utils.utils import (
    create_svg_icon, resource_path
)
from src.utils.utils_translator import translate


def create_missing_placeholder_pixmap(size, text="Image\nnot found"):
    """Creates a Pixmap placeholder with text."""
    pixmap = QPixmap(size)
    pixmap.fill(QColor(theme.COLORS["WIDGET_BRD_PRIMARY"]))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(theme.COLORS["ACCENT"]))
    pen.setWidth(4)
    painter.setPen(pen)
    painter.drawRect(0, 0, size.width(), size.height())

    painter.setPen(QColor(theme.COLORS["PRIMARY"]))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(10)
    painter.setFont(font)

    painter.drawText(
        QRect(0, 0, size.width(), size.height()),
        Qt.AlignmentFlag.AlignCenter,
        translate(text),
    )
    painter.end()
    return pixmap


class GalleryTab(QWidget):
    """Tab widget for managing the image gallery of an encyclopedia article."""

    def __init__(self, gallery_data, parent=None):
        """Initializes the gallery tab with existing image data."""
        super().__init__(parent)
        self.gallery_data = list(gallery_data)
        self.thumbs = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.scroll_area = StyledScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setProperty("class", "backgroundPrimary")

        self.container = QWidget()
        self.container.setProperty("class", "backgroundPrimary")
        self.grid_layout = FlowLayout(self.container)
        self.grid_layout.setSpacing(16)
        self.scroll_area.setWidget(self.container)

        layout.addWidget(self.scroll_area)

        self._refresh_grid()

    def add_header_buttons(self, header_layout):
        """Moves buttons to the page header."""
        self.add_btn = QPushButton(translate("Add Images"))
        self.add_btn.setFixedHeight(36)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setIcon(
            create_svg_icon(
                "assets/control/add.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
            )
        )
        self.add_btn.setIconSize(QSize(20, 20))
        self.add_btn.setProperty("class", "btnText textAlignLeft")
        self.add_btn.clicked.connect(self._add_images)
        header_layout.addWidget(self.add_btn)

        self.clear_missing_btn = QPushButton(translate("Clear inaccessible files"))
        self.clear_missing_btn.setFixedHeight(36)
        self.clear_missing_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_missing_btn.setProperty("class", "btnText")
        self.clear_missing_btn.setStyleSheet(f"color: {theme.COLORS['ACCENT']};")
        self.clear_missing_btn.clicked.connect(self._clear_missing)
        header_layout.addWidget(self.clear_missing_btn)

        self._update_clear_visibility()

    def _update_clear_visibility(self, count=None):
        """Safely updates button visibility."""
        if not hasattr(self, "clear_missing_btn"):
            return

        if count is None:
            count = 0
            for item in self.gallery_data:
                path = item.get("path") if isinstance(item, dict) else item
                if not os.path.exists(path):
                    count += 1

        if count > 0:
            self.clear_missing_btn.setText(
                translate("Clear inaccessible ({count})", count=count)
            )
            self.clear_missing_btn.show()
        else:
            self.clear_missing_btn.hide()

    def _add_images(self):
        """Opens a file dialog to select and add new images to the gallery."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            translate("Select Images"),
            "",
            translate("Images (*.png *.jpg *.jpeg)"),
        )
        if files:
            for f in files:
                self.gallery_data.append({"path": f, "caption": ""})
            self._refresh_grid()

    def _remove_image_by_ref(self, item_to_remove):
        """Removes a specific image item from the gallery data and refreshes the UI."""
        if item_to_remove in self.gallery_data:
            self.gallery_data.remove(item_to_remove)
            self._refresh_grid()

    def _clear_missing(self):
        """Removes all paths that do not exist on disk."""
        new_data = []
        for item in self.gallery_data:
            path = item.get("path") if isinstance(item, dict) else item
            if os.path.exists(path):
                new_data.append(item)
        self.gallery_data = new_data
        self._refresh_grid()

    def _refresh_grid(self):
        """Rebuilds the gallery grid layout with the current image data."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.thumbs.clear()
        missing_files_count = 0

        for item in self.gallery_data:
            if isinstance(item, dict):
                path = item.get("path", "")
                caption = item.get("caption", "")
            else:
                path = str(item)
                caption = ""

            data_dict = {"path": path, "caption": caption}

            pixmap = None
            is_missing = False
            tooltip = ""

            if not path or not os.path.exists(path):
                is_missing = True
                missing_files_count += 1
                pixmap = create_missing_placeholder_pixmap(QSize(128, 128))
                tooltip = translate("File not found: {path}", path = path)
            else:
                folder, filename = os.path.split(path)
                name, ext = os.path.splitext(filename)
                thumb_path = os.path.join(folder, f"{name}_thumb{ext}")
                pixmap = QPixmap(thumb_path) if os.path.exists(thumb_path) else QPixmap(path)

            item_widget = GalleryImageItem(
                pixmap,
                data_dict,
                radius = 6,
                is_missing = is_missing,
                tooltip = tooltip
            )

            item_widget.removeRequested.connect(partial(self._remove_image_by_ref, item))

            self.grid_layout.addWidget(item_widget)

        self._update_clear_visibility(count = missing_files_count)

    def _update_caption(self, index, text):
        """Updates the caption for a specific image by index."""
        if 0 <= index < len(self.gallery_data):
            item = self.gallery_data[index]
            if isinstance(item, dict):
                item["caption"] = text
            else:
                self.gallery_data[index] = {"path": item, "caption": text}

    def get_data(self):
        """Returns the cleaned image data from the grid items."""
        clean_data = []
        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            if isinstance(widget, GalleryImageItem):
                clean_data.append(widget.get_data())
        return clean_data

class RelationsTab(QWidget):
    """Tab for managing relations (Search left, Selected right)."""

    def __init__(
        self,
        current_item_key,
        current_item_type,
        existing_relations,
        main_window,
        parent=None,
    ):
        """Initializes the relations tab and populates available connection items."""
        super().__init__(parent)
        self.mw = main_window
        self.current_key = current_item_key
        self.current_type = current_item_type

        self.selected_items = []
        self.all_items_cache = []
        self.filtered_search_cache = []
        self.search_loaded_count = 0
        self.BATCH_SIZE = 50

        self._init_data(existing_relations)
        self._setup_ui()

    def _normalize_tuple(self, key):
        """
        Converts any list/tuple key to strict (Artist, Album, Year) format.
        Trims excess (path), adds missing (0).
        """
        if not isinstance(key, (list, tuple)):
            return key

        lst = list(key)

        if len(lst) > 3:
            lst = lst[:3]

        while len(lst) < 3:
            lst.append(0)

        return tuple(lst)

    def _init_data(self, existing_relations):
        """
        Loads items. Excludes current item via strict normalization.
        """
        self.all_items_cache = []
        dm = self.mw.data_manager
        em = self.mw.encyclopedia_manager
        enc_data = em.load_data()

        processed_keys = set()

        my_key_norm = self.current_key
        if self.current_type == "album":
            my_key_norm = self._normalize_tuple(self.current_key)

        def add_item(key, typ, name, subtitle="", in_lib=False):
            cand_key_norm = key
            if typ == "album":
                cand_key_norm = self._normalize_tuple(key)

            if typ == self.current_type and cand_key_norm == my_key_norm:
                return

            uniq_key_str = (
                json.dumps(list(cand_key_norm))
                if isinstance(cand_key_norm, (list, tuple))
                else str(cand_key_norm)
            )

            if (typ, uniq_key_str) in processed_keys:
                return

            self.all_items_cache.append(
                {
                    "key": cand_key_norm,
                    "type": typ,
                    "name": name,
                    "subtitle": subtitle,
                    "in_library": in_lib,
                }
            )
            processed_keys.add((typ, uniq_key_str))

        for artist in dm.artists_data.keys():
            add_item(artist, "artist", artist, in_lib=True)

        for album_key in dm.albums_data.keys():
            name = album_key[1]
            subtitle = album_key[0]
            year = album_key[2] if len(album_key) > 2 else 0
            if year > 0:
                subtitle += f" ({year})"
            add_item(album_key, "album", name, subtitle=subtitle, in_lib=True)

        for genre in dm.genres_data.keys():
            add_item(genre, "genre", genre, in_lib=True)

        for comp in dm.composers_data.keys():
            add_item(comp, "composer", comp, in_lib=True)

        for cat, items in enc_data.items():
            if cat not in ["artist", "album", "genre", "composer"]:
                continue

            for key_str, entry in items.items():
                real_key = key_str
                name = entry.get("title")
                subtitle = ""

                if cat == "album":
                    try:
                        real_key_list = json.loads(key_str)
                        real_key = tuple(real_key_list)
                        if len(real_key) >= 2:
                            if not name:
                                name = real_key[1]
                            subtitle = real_key[0]
                            if len(real_key) >= 3 and real_key[2]:
                                subtitle += f" ({real_key[2]})"
                        else:
                            if not name:
                                name = str(real_key)
                    except:
                        if not name:
                            name = str(key_str)
                else:
                    if not name:
                        name = key_str

                add_item(real_key, cat, name, subtitle=subtitle, in_lib=False)

        sort_func = self.mw.data_manager.get_sort_key
        self.all_items_cache.sort(key=lambda x: sort_func(x["name"]))

        cache_map = {}
        for item in self.all_items_cache:
            k_str = self._get_canonical_key_str(item["key"])
            cache_map[(item["type"], k_str)] = item

        self.selected_items = []
        for rel in existing_relations:
            rel_type = rel["type"]
            rel_key = rel["key"]

            if rel_type == "album":
                rel_key = self._normalize_tuple(rel_key)

            k_search_str = self._get_canonical_key_str(rel_key)
            full_data = cache_map.get((rel_type, k_search_str))

            if full_data:
                self.selected_items.append(full_data)
            else:
                self.selected_items.append(
                    {
                        "key": rel_key,
                        "type": rel_type,
                        "name": rel.get("name", str(rel_key)),
                        "subtitle": rel.get("subtitle", ""),
                        "in_library": False,
                    }
                )

    def add_header_buttons(self, header_layout):
        """Moves buttons to the page header."""
        self.btn_auto = QPushButton(translate("Auto Find"))
        self.btn_auto.setFixedHeight(36)
        self.btn_auto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto.setProperty("class", "btnText")
        self.btn_auto.clicked.connect(self._on_auto_find_clicked)
        header_layout.addWidget(self.btn_auto)

        self.relations_tools_btn = StyledToolButton()
        self.relations_tools_btn.setProperty("class", "btnToolMenuBorder")
        self.relations_tools_btn.setText(translate("Relations"))
        self.relations_tools_btn.setFixedHeight(36)
        self.relations_tools_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.relations_tools_btn.setPopupMode(
            StyledToolButton.ToolButtonPopupMode.InstantPopup
        )

        rel_menu = TranslucentMenu(self.relations_tools_btn)
        self.relations_tools_btn.setMenu(rel_menu)

        icn_link = QIcon(
            create_svg_icon(
                "assets/control/link.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        self.act_interlink = QAction(icn_link, translate("Interlink All"), rel_menu)
        self.act_interlink.triggered.connect(self._on_interlink_clicked)
        rel_menu.addAction(self.act_interlink)

        icn_unlink = QIcon(
            create_svg_icon(
                "assets/control/link_break.svg", theme.COLORS["PRIMARY"], QSize(16, 16)
            )
        )
        self.act_unlink = QAction(icn_unlink, translate("Break Interlinks"), rel_menu)
        self.act_unlink.triggered.connect(self._on_break_links_clicked)
        rel_menu.addAction(self.act_unlink)

        header_layout.addWidget(self.relations_tools_btn)

    def _setup_ui(self):
        """Sets up the layout and widgets for the RelationsTab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(24)

        search_col = QVBoxLayout()
        search_col.setSpacing(8)

        search_lbl = QLabel(translate("Search"))
        search_lbl.setProperty("class", "textTertiary textColorTertiary")
        search_col.addWidget(search_lbl)

        self.search_input = StyledLineEdit()
        self.search_input.setFixedHeight(36)
        self.search_input.setPlaceholderText(translate("Search articles..."))
        self.search_input.setProperty("class", "inputBorderSinglePadding")
        self.search_input.setClearButtonEnabled(True)
        clear_action = self.search_input.findChild(QAction)
        if clear_action:
            clear_action.setIcon(
                create_svg_icon(
                    "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
                )
            )
        self.search_input.textChanged.connect(self._update_search_results)
        search_col.addWidget(self.search_input)

        self.search_list = StyledListWidget()
        self.search_list.setProperty("class", "listWidget")
        self.search_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.search_list.uniformItemSizes = True

        self.search_list.verticalScrollBar().valueChanged.connect(self._check_scroll)

        search_col.addWidget(self.search_list)

        columns_layout.addLayout(search_col, 1)

        rels_col = QVBoxLayout()
        rels_col.setSpacing(8)

        rels_header = QHBoxLayout()
        rels_lbl = QLabel(translate("Relations List"))
        rels_lbl.setProperty("class", "textTertiary textColorTertiary")
        rels_header.addWidget(rels_lbl)
        rels_header.addStretch()
        rels_col.addLayout(rels_header)

        self.rels_list = StyledListWidget()
        self.rels_list.setProperty("class", "listWidget")
        self.rels_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        rels_col.addWidget(self.rels_list)

        columns_layout.addLayout(rels_col, 1)
        layout.addLayout(columns_layout, 1)

        self._populate_relations_list()
        self._update_search_results("")

    def _on_auto_find_clicked(self):
        """
        Analyzes the library AND encyclopedia. Searches data, ignoring key length (path) and inaccuracies.
        """
        dm = self.mw.data_manager
        em = self.mw.encyclopedia_manager
        enc_data = em.load_data()
        candidates = []

        if self.current_type == "album":
            album_data = None
            search_key_3 = self._normalize_tuple(self.current_key)

            for k, v in dm.albums_data.items():
                if self._normalize_tuple(k) == search_key_3:
                    album_data = v
                    break

            if not album_data and len(search_key_3) >= 2:
                target_artist = str(search_key_3[0]).lower().strip()
                target_album = str(search_key_3[1]).lower().strip()

                for k, v in dm.albums_data.items():
                    k_norm = self._normalize_tuple(k)
                    if len(k_norm) >= 2:
                        curr_artist = str(k_norm[0]).lower().strip()
                        curr_album = str(k_norm[1]).lower().strip()

                        if curr_artist == target_artist and curr_album == target_album:
                            album_data = v
                            break

            if album_data:
                if artist := album_data.get("album_artist"):
                    candidates.append((artist, "artist"))
                for genre in album_data.get("genre", []):
                    candidates.append((genre, "genre"))

                composers = set()
                for track in album_data.get("tracks", []):
                    if comp_raw := track.get("composer"):
                        comps = [c.strip() for c in re.split(r"[;/]", comp_raw) if c.strip()]
                        composers.update(comps)
                for comp in composers:
                    candidates.append((comp, "composer"))

            if len(search_key_3) >= 1 and search_key_3[0]:
                candidates.append((search_key_3[0], "artist"))

            enc_entry = em.get_entry(search_key_3, "album")
            if enc_entry:
                if artist := enc_entry.get("artist"):
                    candidates.append((artist, "artist"))
                if album_artist := enc_entry.get("album_artist"):
                    candidates.append((album_artist, "artist"))
                if genres := enc_entry.get("genre"):
                    for g in [g.strip() for g in re.split(r"[,;]", genres) if g.strip()]:
                        candidates.append((g, "genre"))
                if composers := enc_entry.get("composer"):
                    for c in [c.strip() for c in re.split(r"[,;]", composers) if c.strip()]:
                        candidates.append((c, "composer"))

        elif self.current_type == "artist":
            artist_name = self.current_key

            if artist_name in dm.artists_data:
                artist_data = dm.artists_data[artist_name]
                for album_key in artist_data.get("albums", []):
                    k_norm = self._normalize_tuple(album_key)
                    real_album_data = dm.albums_data.get(tuple(album_key))

                    if real_album_data:
                        candidates.append((k_norm, "album"))
                        for genre in real_album_data.get("genre", []):
                            candidates.append((genre, "genre"))
                        for track in real_album_data.get("tracks", []):
                            if comp_raw := track.get("composer"):
                                comps = [c.strip() for c in re.split(r"[;/]", comp_raw) if c.strip()]
                                for c in comps:
                                    candidates.append((c, "composer"))

            enc_albums = enc_data.get("album", {})
            for k_str, alb_data in enc_albums.items():
                try:
                    k_list = json.loads(k_str)
                    if len(k_list) >= 1 and k_list[0] == artist_name:
                        candidates.append((self._normalize_tuple(k_list), "album"))
                except:
                    pass

        elif self.current_type == "composer":
            comp_name = self.current_key

            if comp_name in dm.composers_data:
                comp_data = dm.composers_data[comp_name]
                for album_key in comp_data.get("albums", []):
                    real_k = tuple(album_key)
                    if real_k in dm.albums_data:
                        k_norm = self._normalize_tuple(real_k)
                        candidates.append((k_norm, "album"))
                        alb_data = dm.albums_data[real_k]
                        if artist := alb_data.get("album_artist"):
                            candidates.append((artist, "artist"))
                        for genre in alb_data.get("genre", []):
                            candidates.append((genre, "genre"))

            enc_albums = enc_data.get("album", {})
            for k_str, alb_data in enc_albums.items():
                try:
                    k_list = json.loads(k_str)
                    enc_comp = alb_data.get("composer", "")
                    comps = [c.strip() for c in re.split(r"[,;]", enc_comp) if c.strip()]
                    if comp_name in comps:
                        candidates.append((self._normalize_tuple(k_list), "album"))
                except:
                    pass

        elif self.current_type == "genre":
            genre_name = self.current_key

            if genre_name in dm.genres_data:
                g_data = dm.genres_data[genre_name]
                for album_key in g_data.get("albums", []):
                    real_k = tuple(album_key)
                    if real_k in dm.albums_data:
                        k_norm = self._normalize_tuple(real_k)
                        candidates.append((k_norm, "album"))
                        alb_data = dm.albums_data[real_k]
                        if artist := alb_data.get("album_artist"):
                            candidates.append((artist, "artist"))
                        for track in alb_data.get("tracks", []):
                            if comp_raw := track.get("composer"):
                                comps = [c.strip() for c in re.split(r"[;/]", comp_raw) if c.strip()]
                                for c in comps:
                                    candidates.append((c, "composer"))

            enc_albums = enc_data.get("album", {})
            for k_str, alb_data in enc_albums.items():
                try:
                    k_list = json.loads(k_str)
                    enc_genre = alb_data.get("genre", "")
                    genres = [g.strip() for g in re.split(r"[,;]", enc_genre) if g.strip()]
                    if genre_name in genres:
                        candidates.append((self._normalize_tuple(k_list), "album"))
                except:
                    pass

        cache_map = {}
        for item in self.all_items_cache:
            k_str = self._get_canonical_key_str(item["key"])
            cache_map[(item["type"], k_str)] = item

        supported_keys_ids = set()
        existing_ui_keys_ids = set()

        for item in self.selected_items:
            k_str = self._get_canonical_key_str(item["key"])
            existing_ui_keys_ids.add((item["type"], k_str))

        current_canon_key = self._get_canonical_key_str(self.current_key)
        supported_keys_ids.add((self.current_type, current_canon_key))

        added_count = 0
        for cand_key, cand_type in candidates:
            c_key_str = self._get_canonical_key_str(cand_key)
            supported_keys_ids.add((cand_type, c_key_str))

            if (cand_type, c_key_str) not in existing_ui_keys_ids:
                found_item = cache_map.get((cand_type, c_key_str))
                if found_item:
                    self.selected_items.append(found_item)
                    existing_ui_keys_ids.add((cand_type, c_key_str))
                    added_count += 1

        orphan_data = []
        type_map = {
            "artist": translate("Artist"),
            "album": translate("Album"),
            "genre": translate("Genre"),
            "composer": translate("Composer"),
        }

        for i, item in enumerate(self.selected_items):
            k_str = self._get_canonical_key_str(item["key"])
            if (item["type"], k_str) not in supported_keys_ids:
                display_type = type_map.get(item["type"], item["type"].capitalize())
                display_text = f"{display_type}: {item['name']}"
                if item.get("subtitle"):
                    display_text += f" ({item['subtitle']})"
                orphan_data.append((i, display_text))

        if added_count > 0 or orphan_data:
            dialog = RelationsSyncDialog(added_count, orphan_data, self)
            if dialog.exec():
                indices_to_remove = dialog.get_indices_to_remove()
                if indices_to_remove:
                    for idx in sorted(indices_to_remove, reverse = True):
                        self.selected_items.pop(idx)
                    print(f"Removed {len(indices_to_remove)} relations.")

            self._populate_relations_list()
            self._update_search_results(self.search_input.text())
        else:
            CustomConfirmDialog.confirm(
                self,
                translate("Sync Relations"),
                translate("No new or outdated relations found."),
                ok_text = translate("OK"),
                cancel_text = None,
            )

    def _check_scroll(self, value):
        """Checks scroll and loads items if necessary."""
        scroll_bar = self.search_list.verticalScrollBar()
        if value >= scroll_bar.maximum() - 200:
            if self.search_loaded_count < len(self.filtered_search_cache):
                self._load_search_batch()

    def _update_search_results(self, text):
        """Filters the search results based on user input and loads the new batch."""
        v_scroll = self.search_list.verticalScrollBar()
        scroll_pos = v_scroll.value()

        self.search_list.setUpdatesEnabled(False)
        self.search_list.clear()
        self.filtered_search_cache = []
        self.search_loaded_count = 0

        text = text.lower().strip()

        selected_keys = set()
        for item in self.selected_items:
            k = tuple(item["key"]) if isinstance(item["key"], list) else item["key"]
            selected_keys.add((item["type"], k))

        for item in self.all_items_cache:
            if (item["type"], item["key"]) in selected_keys:
                continue

            if (
                not text
                or text in item["name"].lower()
                or (item.get("subtitle") and text in item["subtitle"].lower())
            ):
                self.filtered_search_cache.append(item)

        self._load_search_batch()
        self.search_list.setUpdatesEnabled(True)

        QTimer.singleShot(0, lambda: v_scroll.setValue(scroll_pos))

    def _load_search_batch(self):
        """Adds a batch of widgets to the search list."""
        start = self.search_loaded_count
        end = min(start + self.BATCH_SIZE, len(self.filtered_search_cache))

        self.search_list.setUpdatesEnabled(False)

        for i in range(start, end):
            item_data = self.filtered_search_cache[i]
            list_item = QListWidgetItem(self.search_list)
            widget = RelationsItemWidget(item_data, is_selected_list=False)
            widget.addRequested.connect(partial(self._add_relation, item_data))

            list_item.setSizeHint(widget.sizeHint())
            self.search_list.setItemWidget(list_item, widget)

        self.search_list.setUpdatesEnabled(True)
        self.search_loaded_count = end

    def _populate_relations_list(self):
        """Populates the right panel with currently selected relation items."""
        v_scroll = self.rels_list.verticalScrollBar()
        scroll_pos = v_scroll.value()

        self.rels_list.setUpdatesEnabled(False)
        self.rels_list.clear()
        for i, item_data in enumerate(self.selected_items):
            list_item = QListWidgetItem(self.rels_list)
            widget = RelationsItemWidget(item_data, is_selected_list=True)
            widget.removeRequested.connect(partial(self._remove_relation, i))
            list_item.setSizeHint(widget.sizeHint())
            self.rels_list.setItemWidget(list_item, widget)
        self.rels_list.setUpdatesEnabled(True)

        QTimer.singleShot(0, lambda: v_scroll.setValue(scroll_pos))

    def _add_relation(self, item_data):
        """Adds an item to the selected relations and updates the UI."""
        self.selected_items.append(item_data)
        self._populate_relations_list()
        self._update_search_results(self.search_input.text())

    def _remove_relation(self, index):
        """Removes an item from the selected relations by its index."""
        if 0 <= index < len(self.selected_items):
            self.selected_items.pop(index)
            self._populate_relations_list()
            self._update_search_results(self.search_input.text())

    def _get_canonical_key_str(self, key, type_str=None):
        """
        Helper to get standardized key string.
        Always normalizes album key to 3 elements.
        """
        if isinstance(key, (list, tuple)):
            return json.dumps(list(self._normalize_tuple(key)))
        return str(key)

    def _on_interlink_clicked(self):
        """Initiates a bulk interlinking operation among all selected relations."""
        if len(self.selected_items) < 2:
            return

        if not CustomConfirmDialog.confirm(
            self,
            translate("Interlink Articles"),
            translate(
                "{count} articles need to be updated to link to each other. Do you want to proceed?", count = len(self.selected_items)
            ),
            ok_text=translate("Interlink"),
            cancel_text=translate("Cancel"),
        ):
            return

        self.mw.encyclopedia_manager.bulk_update_relations(
            self.selected_items, action="link"
        )
        print("Interlinking complete (Optimized).")

    def _on_break_links_clicked(self):
        """Initiates a bulk unlink operation among all selected relations."""
        if len(self.selected_items) < 2:
            return

        if not CustomConfirmDialog.confirm(
            self,
            translate("Break Interlinks"),
            translate("This action will remove links between the {count} selected items. Continue?", count = len(self.selected_items)),
            ok_text=translate("Break Links"),
            cancel_text=translate("Cancel"),
        ):
            return

        self.mw.encyclopedia_manager.bulk_update_relations(
            self.selected_items, action="break"
        )
        print("Group links broken (Optimized).")

    def get_relations_data(self):
        """Returns a cleaned list for saving."""
        clean_data = []
        for item in self.selected_items:
            clean_data.append(
                {
                    "key": item["key"],
                    "type": item["type"],
                    "name": item["name"],
                    "subtitle": item.get("subtitle", ""),
                }
            )

        return clean_data, False


class DiscographyTab(QWidget):
    """Tab widget for managing the discography section for an artist or composer."""

    def __init__(self, item_name, item_type, existing_data, main_window, parent=None):
        """Initializes the DiscographyTab with context and existing records."""
        super().__init__(parent)
        self.item_name = item_name
        self.item_type = item_type
        self.existing_disco = existing_data.get("discography", [])
        self.mw = main_window
        self.items = []

        self._init_data()
        self._setup_ui()

    def _init_data(self):
        """Loads data. For linked albums, takes data from DataManager."""
        self.items = []
        dm = self.mw.data_manager

        for item in self.existing_disco:
            display_item = item.copy()
            lib_key = display_item.get("library_key")

            if lib_key:
                k_tuple = tuple(lib_key)
                found_data = None
                if k_tuple in dm.albums_data:
                    found_data = dm.albums_data[k_tuple]
                elif len(k_tuple) == 3:
                    for real_k, real_v in dm.albums_data.items():
                        if real_k[:3] == k_tuple:
                            found_data = real_v
                            break

                if found_data:
                    display_item.update(
                        {
                            "title": k_tuple[1],
                            "year": (
                                k_tuple[2]
                                if len(k_tuple) > 2
                                else found_data.get("year", 0)
                            ),
                            "genre": ", ".join(found_data.get("genre", [])[:2]),
                            "artist": found_data.get("album_artist")
                            or found_data.get("artist", ""),
                            "in_library": True,
                            "is_manual": False,
                        }
                    )
                else:
                    display_item.update(
                        {
                            "title": (
                                str(lib_key[1])
                                if len(lib_key) > 1
                                else translate("Unknown Album")
                            ),
                            "year": int(lib_key[2]) if len(lib_key) > 2 else 0,
                            "artist": str(lib_key[0]) if len(lib_key) > 0 else "",
                            "in_library": False,
                            "is_manual": False,
                        }
                    )
            else:
                display_item["in_library"] = False
                display_item["is_manual"] = True

                t = display_item.get("title", "")
                y = display_item.get("year", 0)
                a = display_item.get("artist") or (
                    self.item_name if self.item_type == "artist" else ""
                )
                display_item["_original_key"] = (a, t, y)

            self.items.append(display_item)

        self.items.sort(key=lambda x: (int(x.get("year", 0) or 0), x.get("title", "")))

    def add_header_buttons(self, header_layout):
        """Moves buttons to the page header."""
        self.btn_auto = QPushButton(translate("Auto Find"))
        self.btn_auto.setFixedHeight(36)
        self.btn_auto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto.setProperty("class", "btnText")
        self.btn_auto.clicked.connect(self._on_auto_find_clicked)
        header_layout.addWidget(self.btn_auto)

        self.add_btn = QPushButton(translate("Add Album"))
        self.add_btn.setFixedHeight(36)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setIcon(
            create_svg_icon(
                "assets/control/add.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
            )
        )
        self.add_btn.setIconSize(QSize(20, 20))
        self.add_btn.setProperty("class", "btnText textAlignLeft")
        self.add_btn.clicked.connect(self._add_manual_album)
        header_layout.addWidget(self.add_btn)

    def _setup_ui(self):
        """Builds the user interface structure for the DiscographyTab."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        header_lbl = QLabel(translate("Albums List"))
        header_lbl.setProperty("class", "textTertiary textColorTertiary")
        left_layout.addWidget(header_lbl)

        self.list_widget = StyledListWidget()
        self.list_widget.setProperty("class", "listWidget")
        self.list_widget.currentRowChanged.connect(self._on_item_selected)
        left_layout.addWidget(self.list_widget)

        hint_text = translate("Note: Adding an album here creates a list item only...")
        self.hint_label = QLabel(hint_text)
        self.hint_label.setWordWrap(True)
        self.hint_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.hint_label.setProperty("class", "textTertiary textColorTertiary")
        left_layout.addWidget(self.hint_label)

        self.form_container = QWidget()
        self.form_container.setContentsMargins(0, 0, 0, 0)

        self.right_layout = QVBoxLayout(self.form_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)

        bh_lay = QHBoxLayout()
        bh_lay.setContentsMargins(0, 0, 0, 0)
        bh_lay.setSpacing(8)

        self.link_combo_label = QLabel(translate("Autofill from Library"))
        self.link_combo_label.setProperty("class", "textTertiary textColorTertiary")
        bh_lay.addWidget(self.link_combo_label)

        self.right_layout.addLayout(bh_lay)

        self.link_combo = TranslucentCombo()
        self.link_combo.currentIndexChanged.connect(self._on_link_changed)
        self.right_layout.addWidget(self.link_combo)
        self.right_layout.addSpacing(8)

        self.title_label = QLabel(translate("Title"))
        self.title_label.setProperty("class", "textTertiary textColorTertiary")
        self.right_layout.addWidget(self.title_label)

        self.title_edit = StyledLineEdit()
        self.title_edit.setFixedHeight(36)
        self.title_edit.setProperty("class", "inputBorderSinglePadding")
        self.title_edit.textChanged.connect(self._update_current_data)
        self.right_layout.addWidget(self.title_edit)
        self.right_layout.addSpacing(8)

        self.artist_label = QLabel(translate("Artist"))
        self.artist_label.setProperty("class", "textTertiary textColorTertiary")
        self.right_layout.addWidget(self.artist_label)

        all_artists = (
            sorted(list(self.mw.data_manager.artists_data.keys()))
            if self.mw.data_manager.artists_data
            else []
        )
        self.artist_edit = StyledLineEdit()
        self.artist_edit.setFixedHeight(36)
        self.artist_edit.setProperty("class", "inputBorderSinglePadding")

        completer_art = GapCompleter(all_artists, self.artist_edit, gap=4)
        completer_art.popup().setProperty("class", "listWidget")
        completer_art.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer_art.setFilterMode(Qt.MatchFlag.MatchContains)
        self.artist_edit.setCompleter(completer_art)

        self.artist_edit.textChanged.connect(self._update_current_data)
        self.right_layout.addWidget(self.artist_edit)
        self.right_layout.addSpacing(8)

        self.album_artist_label = QLabel(translate("Album Artist"))
        self.album_artist_label.setProperty("class", "textTertiary textColorTertiary")
        self.right_layout.addWidget(self.album_artist_label)

        self.album_artist_edit = StyledLineEdit()
        self.album_artist_edit.setFixedHeight(36)
        self.album_artist_edit.setProperty("class", "inputBorderSinglePadding")

        completer_aa = GapCompleter(all_artists, self.album_artist_edit, gap=4)
        completer_aa.popup().setProperty("class", "listWidget")
        completer_aa.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer_aa.setFilterMode(Qt.MatchFlag.MatchContains)
        self.album_artist_edit.setCompleter(completer_aa)

        self.album_artist_edit.textChanged.connect(self._update_current_data)
        self.right_layout.addWidget(self.album_artist_edit)
        self.right_layout.addSpacing(8)

        self.composer_label = QLabel(translate("Composer"))
        self.composer_label.setProperty("class", "textTertiary textColorTertiary")
        self.right_layout.addWidget(self.composer_label)

        all_composers = (
            sorted(list(self.mw.data_manager.composers_data.keys()))
            if self.mw.data_manager.composers_data
            else []
        )
        self.composer_edit = StyledLineEdit()
        self.composer_edit.setFixedHeight(36)
        self.composer_edit.setProperty("class", "inputBorderSinglePadding")

        completer_comp = GapCompleter(all_composers, self.composer_edit, gap=4)
        completer_comp.popup().setProperty("class", "listWidget")
        completer_comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer_comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.composer_edit.setCompleter(completer_comp)

        self.composer_edit.textChanged.connect(self._update_current_data)
        self.right_layout.addWidget(self.composer_edit)
        self.right_layout.addSpacing(8)

        self.year_label = QLabel(translate("Year"))
        self.year_label.setProperty("class", "textTertiary textColorTertiary")
        self.right_layout.addWidget(self.year_label)

        self.year_edit = StyledLineEdit()
        self.year_edit.setFixedHeight(36)
        self.year_edit.setPlaceholderText("1877")
        self.year_edit.setProperty("class", "inputBorderSinglePadding")
        self.year_edit.setMaxLength(4)
        self.year_edit.textChanged.connect(self._update_current_data)
        self.right_layout.addWidget(self.year_edit)
        self.right_layout.addSpacing(8)

        self.genre_label = QLabel(translate("Genre"))
        self.genre_label.setProperty("class", "textTertiary textColorTertiary")
        self.right_layout.addWidget(self.genre_label)

        all_genres = (
            sorted(list(self.mw.data_manager.genres_data.keys()))
            if self.mw.data_manager.genres_data
            else []
        )
        self.genre_edit = StyledLineEdit()
        self.genre_edit.setFixedHeight(36)
        self.genre_edit.setProperty("class", "inputBorderSinglePadding")

        completer_gen = GapCompleter(all_genres, self.genre_edit, gap=4)
        completer_gen.popup().setProperty("class", "listWidget")
        completer_gen.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer_gen.setFilterMode(Qt.MatchFlag.MatchContains)
        self.genre_edit.setCompleter(completer_gen)

        self.genre_edit.textChanged.connect(self._update_current_data)
        self.right_layout.addWidget(self.genre_edit)
        self.right_layout.addStretch()

        layout.addLayout(left_layout, 1)
        layout.addWidget(self.form_container, 1)

        self._populate_list()
        self._populate_link_combo()
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        else:
            self.form_container.setEnabled(False)

    def _populate_list(self):
        """Rebuilds the list with updates disabled for smoothness."""
        self.list_widget.setUpdatesEnabled(False)
        self.list_widget.clear()
        for i, item in enumerate(self.items):
            list_item = QListWidgetItem(self.list_widget)
            widget = DiscographyItemWidget(item)
            widget.removeRequested.connect(partial(self._remove_album_at, i))
            list_item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(list_item, widget)
        self.list_widget.setUpdatesEnabled(True)

    def _populate_link_combo(self):
        """Fills the combo box with available albums from the local library."""
        self.link_combo.blockSignals(True)
        self.link_combo.clear()
        self.link_combo.addItem(translate("No Link"), None)
        dm = self.mw.data_manager
        candidates = []
        for key in dm.albums_data.keys():
            if key[0] == self.item_name:
                candidates.append((f"{key[1]} ({key[2]})", list(key)))
        candidates.sort(key=lambda x: x[0])
        for disp, k_list in candidates:
            self.link_combo.addItem(disp, k_list)
        self.link_combo.blockSignals(False)

    def _on_item_selected(self, row):
        """Loads data into form fields when an album is selected from the list."""
        if row < 0:
            self.form_container.setEnabled(False)
            return
        self.form_container.setEnabled(True)
        item = self.items[row]

        self.title_edit.blockSignals(True)
        self.artist_edit.blockSignals(True)
        self.album_artist_edit.blockSignals(True)
        self.composer_edit.blockSignals(True)
        self.year_edit.blockSignals(True)
        self.genre_edit.blockSignals(True)
        self.link_combo.blockSignals(True)

        self.title_edit.setText(item.get("title", ""))

        self.artist_edit.setText(self.item_name)
        item["artist"] = self.item_name

        self.album_artist_edit.setText(item.get("album_artist", ""))
        self.composer_edit.setText(item.get("composer", ""))
        self.year_edit.setText(str(item.get("year", "")) if item.get("year") else "")
        self.genre_edit.setText(item.get("genre", ""))

        lib_key = item.get("library_key")
        idx = 0
        if lib_key:
            for i in range(1, self.link_combo.count()):
                if self.link_combo.itemData(i)[:3] == lib_key[:3]:
                    idx = i
                    break
        self.link_combo.setCurrentIndex(idx)

        self.title_edit.blockSignals(False)
        self.artist_edit.blockSignals(False)
        self.album_artist_edit.blockSignals(False)
        self.composer_edit.blockSignals(False)
        self.year_edit.blockSignals(False)
        self.genre_edit.blockSignals(False)
        self.link_combo.blockSignals(False)

        self._update_inputs_state()

    def _on_link_changed(self, index):
        """Handles binding an album to a local library entry."""
        row = self.list_widget.currentRow()
        if row < 0:
            return
        item = self.items[row]
        data = self.link_combo.itemData(index)

        self.title_edit.blockSignals(True)
        self.year_edit.blockSignals(True)
        self.album_artist_edit.blockSignals(True)
        self.genre_edit.blockSignals(True)
        self.composer_edit.blockSignals(True)

        if data:
            item["library_key"] = data
            item["in_library"] = True

            self.title_edit.setText(data[1])
            self.year_edit.setText(str(data[2]) if data[2] != 0 else "")

            dm = self.mw.data_manager
            lib_data = dm.albums_data.get(tuple(data))
            if not lib_data and len(data) >= 3:
                target_3 = tuple(data[:3])
                for k, v in dm.albums_data.items():
                    if k[:3] == target_3:
                        lib_data = v
                        break

            if lib_data:
                self._smart_merge_album_data(lib_data)
        else:
            item["library_key"] = None
            item["in_library"] = False

        self.title_edit.blockSignals(False)
        self.year_edit.blockSignals(False)
        self.album_artist_edit.blockSignals(False)
        self.genre_edit.blockSignals(False)
        self.composer_edit.blockSignals(False)

        self._update_current_data()
        self._update_list_item_visuals(row)
        self._update_inputs_state()

    def _smart_merge_album_data(self, lib_data):
        """Intelligently merges album metadata from library into the text inputs."""
        def merge_text_field(edit_widget, new_values_list):
            current_text = edit_widget.text().strip()
            is_placeholder = current_text == translate("New Album")

            if not current_text or is_placeholder:
                clean_values = [
                    str(v).strip() for v in new_values_list if str(v).strip()
                ]
                if clean_values:
                    edit_widget.setText(", ".join(clean_values))
                return

            current_tags = [
                t.strip() for t in re.split(r"[,;]", current_text) if t.strip()
            ]
            final_tags = list(current_tags)
            for val in new_values_list:
                val_s = str(val).strip()
                if val_s and val_s not in final_tags:
                    final_tags.append(val_s)
            edit_widget.setText(", ".join(final_tags))

        aa = lib_data.get("album_artist")
        if not aa and lib_data.get("tracks"):
            aa = lib_data["tracks"][0].get("album_artist")
        if aa:
            merge_text_field(self.album_artist_edit, [aa])

        merge_text_field(self.genre_edit, lib_data.get("genre", []))

        comp_set = []
        for t in lib_data.get("tracks", []):
            if c_raw := t.get("composer"):
                parts = [p.strip() for p in re.split(r"[;/]", c_raw) if p.strip()]
                for p in parts:
                    if p not in comp_set:
                        comp_set.append(p)
        if comp_set:
            merge_text_field(self.composer_edit, comp_set)

    def _update_current_data(self):
        """Updates internal item dictionary from the form inputs."""
        row = self.list_widget.currentRow()
        if row < 0:
            return
        item = self.items[row]

        item["title"] = self.title_edit.text()
        item["artist"] = self.artist_edit.text()
        item["album_artist"] = self.album_artist_edit.text()
        item["composer"] = self.composer_edit.text()

        try:
            val = self.year_edit.text()
            item["year"] = int(val) if val.isdigit() else 1877
        except:
            item["year"] = 1877

        item["genre"] = self.genre_edit.text()

        self._update_list_item_visuals(row)

    def _update_list_item_visuals(self, row):
        """Refreshes the visual representation of an album in the list widget."""
        list_item = self.list_widget.item(row)
        if list_item:
            new_widget = DiscographyItemWidget(self.items[row])
            new_widget.removeRequested.connect(partial(self._remove_album_at, row))
            self.list_widget.setItemWidget(list_item, new_widget)

    def _on_auto_find_clicked(self):
        """Finds and adds library albums associated with this artist or composer."""
        v_scroll = self.list_widget.verticalScrollBar()
        scroll_pos = v_scroll.value()

        dm = self.mw.data_manager

        current_keys = set()
        for i in self.items:
            if i.get("library_key"):
                current_keys.add(tuple(i["library_key"]))
            elif i.get("is_manual"):
                k = dm.make_album_key(i.get("artist"), i.get("title"), i.get("year"))
                current_keys.add(k)

        added_count = 0
        source_data = (
            dm.artists_data if self.item_type == "artist" else dm.composers_data
        )
        info = source_data.get(self.item_name)

        if info:
            for key in info.get("albums", []):
                real_key_tuple = tuple(key)

                candidate_key = real_key_tuple[:3]

                if (
                    real_key_tuple in dm.albums_data
                    and candidate_key not in current_keys
                ):
                    alb_data = dm.albums_data[real_key_tuple]

                    comp_list = []
                    for t in alb_data.get("tracks", []):
                        if c_raw := t.get("composer"):
                            parts = [
                                p.strip() for p in re.split(r"[;/]", c_raw) if p.strip()
                            ]
                            for p in parts:
                                if p not in comp_list:
                                    comp_list.append(p)

                    self.items.append(
                        {
                            "title": candidate_key[1],
                            "year": candidate_key[2],
                            "genre": ", ".join(alb_data.get("genre", [])[:2]),
                            "artist": alb_data.get("album_artist")
                            or alb_data.get("artist", ""),
                            "album_artist": alb_data.get("album_artist", ""),
                            "composer": ", ".join(comp_list),
                            "in_library": True,
                            "library_key": list(candidate_key),
                            "is_manual": False,
                        }
                    )
                    added_count += 1

        if added_count > 0:
            self.items.sort(
                key=lambda x: (int(x.get("year", 0) or 0), x.get("title", ""))
            )
            self._populate_list()
            QTimer.singleShot(0, lambda: v_scroll.setValue(scroll_pos))

    def _add_manual_album(self):
        """Appends a new blank album to the list for manual editing."""
        default_artist = self.item_name
        default_composer = self.item_name if self.item_type == "composer" else ""

        new_item = {
            "title": translate("New Album"),
            "year": 1877,
            "genre": "",
            "artist": default_artist,
            "album_artist": default_artist,
            "composer": default_composer,
            "in_library": False,
            "library_key": None,
            "is_manual": True,
        }

        new_item["_original_key"] = (
            new_item["artist"],
            new_item["title"],
            new_item["year"],
        )

        self.items.append(new_item)
        self._populate_list()

        self.list_widget.setCurrentRow(len(self.items) - 1)
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def _remove_album_at(self, index):
        """Removes an album from the list by its index."""
        if 0 <= index < len(self.items):
            v_scroll = self.list_widget.verticalScrollBar()
            scroll_pos = v_scroll.value()

            self.items.pop(index)
            self._populate_list()

            new_row = min(index, len(self.items) - 1)
            if new_row >= 0:
                self.list_widget.setCurrentRow(new_row)
            else:
                self.form_container.setEnabled(False)

            QTimer.singleShot(0, lambda: v_scroll.setValue(scroll_pos))

    def get_data(self):
        """Fetches final discography array data ready to be saved."""
        clean_disco = []
        for i in self.items:
            if i.get("in_library") and i.get("library_key"):
                clean_disco.append({"library_key": i["library_key"]})
            else:
                clean_disco.append(
                    {
                        "title": i.get("title", ""),
                        "year": i.get("year", 0),
                        "genre": i.get("genre", ""),
                        "artist": i.get("artist", ""),
                        "album_artist": i.get("album_artist", ""),
                        "composer": i.get("composer", ""),
                        "is_manual": True,
                    }
                )
        return clean_disco

    def process_migrations(self):
        """Detects if albums linked to the encyclopedia have been renamed and prompts for migration."""
        em = self.mw.encyclopedia_manager
        migrations_to_run = []

        for item in self.items:
            if item.get("is_manual") and "_original_key" in item:
                old_key = item["_original_key"]

                new_artist = item.get("artist") or (
                    self.item_name if self.item_type == "artist" else ""
                )
                new_title = item.get("title", "")
                new_year = item.get("year", 0)
                new_key = (new_artist, new_title, new_year)

                if new_key != old_key:
                    entry_data = em.get_entry(old_key, "album")
                    if entry_data:
                        migrations_to_run.append(
                            {
                                "item": item,
                                "old_key": old_key,
                                "new_key": new_key,
                                "entry_data": entry_data,
                            }
                        )

        if not migrations_to_run:
            return

        msg = translate(
            "You have renamed {count} album(s) that have linked encyclopedia articles...",
            count=len(migrations_to_run),
        )

        if CustomConfirmDialog.confirm(
            self,
            translate("Migrate Articles"),
            msg,
            ok_text=translate("Migrate"),
            cancel_text=translate("Keep old"),
        ):
            for m in migrations_to_run:
                if m["entry_data"].get("blocks"):
                    m["entry_data"]["blocks"][0]["title"] = m["new_key"][1]

                em.save_entry(m["new_key"], "album", m["entry_data"])
                em.save_entry(m["old_key"], "album", None)
                m["item"]["_original_key"] = m["new_key"]

    def _update_inputs_state(self):
        """Adjusts enabling/disabling of text inputs based on binding logic."""
        self.title_edit.setEnabled(True)
        self.year_edit.setEnabled(True)
        self.genre_edit.setEnabled(True)

        self.artist_edit.setEnabled(False)
        set_custom_tooltip(
            self.artist_edit,
            title = translate("Synced to current encyclopedia article"),
        )
        self.album_artist_edit.setEnabled(True)
        self.composer_edit.setEnabled(True)


class EncyclopediaEditorDialog(StyledDialog):
    """Main dialog for editing an encyclopedia article, handling general info, content blocks, gallery, discography, and links."""

    def __init__(
        self,
        item_name,
        default_image_path,
        item_type="item",
        existing_data=None,
        parent=None,
        secondary_query=None,
        main_window=None,
        full_item_key=None,
        initial_meta=None,
    ):
        """Initializes the encyclopedia editor dialog with necessary context."""
        super().__init__(parent)
        self.item_name = item_name
        self.item_type = item_type
        self.secondary_query = secondary_query
        self.main_app_window = main_window if main_window else parent

        self.full_item_key = full_item_key
        self.initial_meta = initial_meta or {}
        self.original_key = full_item_key if full_item_key else item_name
        self.original_type = item_type
        self.current_binding_key = self.original_key
        self.current_binding_type = self.original_type

        self.setWindowTitle(translate("Edit Article"))
        self.setMinimumSize(1024, 600)
        self.setProperty("class", "backgroundPrimary")

        self.image_path = existing_data.get("image_path") if existing_data else None
        self.default_image_path = default_image_path
        self.existing_data = existing_data or {}
        self._delete_requested = False
        self.unlink_on_delete = False
        self.is_main_cover_missing = False

        self.new_cover_path = None
        self.cached_new_cover_path = None
        self.original_cover_pixmap = None
        self.meta_inputs = {}

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Constructs the base layouts, sidebar navigation, and bottom control panel."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        body_container = QWidget()
        self.body_layout = QHBoxLayout(body_container)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        nav_widget = QWidget()
        nav_widget.setProperty("class", "navBar borderRight")
        nav_widget.setFixedWidth(240)
        nav_vbox = QVBoxLayout(nav_widget)
        nav_vbox.setContentsMargins(16, 16, 16, 16)
        self.nav_list = StyledListWidget()
        self.nav_list.setProperty("class", "listWidgetNav")
        self.nav_list.setSpacing(2)
        nav_vbox.addWidget(self.nav_list)
        self.body_layout.addWidget(nav_widget)

        self.stacked_widget = QStackedWidget()
        self.body_layout.addWidget(self.stacked_widget, 1)
        self.main_layout.addWidget(body_container, 1)

        self._init_pages()
        self.nav_list.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

        bottom_panel = QWidget()
        bottom_panel.setProperty("class", "controlPanel")
        bottom_layout = QHBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(24, 16, 24, 16)
        bottom_layout.setSpacing(16)

        self.delete_btn = QPushButton(translate("Delete Entry"))
        self.delete_btn.setFixedHeight(36)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setProperty("class", "btnText")
        self.delete_btn.setStyleSheet(f"color: {theme.COLORS['ACCENT']};")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        if not self.existing_data:
            self.delete_btn.hide()

        self.status_label = QLabel("")
        self.status_label.setProperty("class", "textSecondary")

        bottom_layout.addWidget(self.delete_btn)
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        if btn_box.layout():
            btn_box.layout().setSpacing(16)

        for btn in btn_box.buttons():
            btn.setProperty("class", "btnText")
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        bottom_layout.addWidget(btn_box)
        self.main_layout.addWidget(bottom_panel)

    def _create_page_wrapper(self, title, description, scrollable=True):
        """Generates a standard header, background, and optionally a scroll area for a specific tab."""
        page_container = QWidget()
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setProperty("class", "headerBackground headerBorder")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(24, 16, 24, 16)
        header_layout.setSpacing(20)

        title_block = QVBoxLayout()
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(4)

        lbl_title = ElidedLabel(title)
        lbl_title.setProperty("class", "textHeaderSecondary textColorPrimary")
        lbl_desc = QLabel(description)
        lbl_desc.setWordWrap(True)
        lbl_desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lbl_desc.setProperty("class", "textSecondary textColorTertiary")
        title_block.addWidget(lbl_title)
        title_block.addWidget(lbl_desc)
        header_layout.addLayout(title_block, 1)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        header_layout.addLayout(actions_layout)

        page_layout.addWidget(header_widget)

        content_area = QWidget()
        content_area.setProperty("class", "backgroundPrimary")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)

        if scrollable:
            scroll = StyledScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setProperty("class", "backgroundPrimary")
            scroll.setWidget(content_area)
            page_layout.addWidget(scroll, 1)
        else:
            page_layout.addWidget(content_area, 1)

        return page_container, content_layout, actions_layout

    def _add_page(self, widget, name, icon_name=None):
        """Adds a widget page to the StackedWidget and its title to the Navigation list."""
        self.stacked_widget.addWidget(widget)
        item = QListWidgetItem(name)
        item.setSizeHint(QSize(0, 44))
        self.nav_list.addItem(item)

    def _init_pages(self):
        """Initializes all editor tabs (General, Content, Gallery, Discography, Relations, Links)."""
        type_map = {
            "artist": translate("Artist"),
            "album": translate("Album"),
            "genre": translate("Genre"),
            "composer": translate("Composer"),
        }
        item_type_str = type_map.get(self.item_type, self.item_type)

        page_gen, layout_gen, header_gen = self._create_page_wrapper(
            self.item_name, item_type_str, scrollable=True
        )
        self._setup_general_content(layout_gen, header_gen)
        self._add_page(page_gen, translate("General"))

        page_add, layout_add, header_add = self._create_page_wrapper(
            self.item_name,
            translate("Add additional sections of the article..."),
            scrollable=True,
        )
        self._setup_additional_content(layout_add, header_add)
        self._add_page(page_add, translate("Content"))

        page_gal, layout_gal, header_gal = self._create_page_wrapper(
            self.item_name,
            translate("Add additional images, booklet scans or digital artwork."),
            scrollable=False,
        )
        self.gallery_tab = GalleryTab(self.existing_data.get("gallery", []), self)
        self.gallery_tab.add_header_buttons(header_gal)
        layout_gal.addWidget(self.gallery_tab)
        self._add_page(page_gal, translate("Gallery"))

        if self.item_type == "artist":
            page_disco, layout_disco, header_disco = self._create_page_wrapper(
                self.item_name,
                translate("Manage the list of albums..."),
                scrollable=True,
            )
            self.discography_tab = DiscographyTab(
                self.item_name,
                self.item_type,
                self.existing_data,
                self.main_app_window,
                self,
            )
            self.discography_tab.add_header_buttons(header_disco)
            layout_disco.addWidget(self.discography_tab)
            self._add_page(page_disco, translate("Discography"))

        page_rel, layout_rel, header_rel = self._create_page_wrapper(
            self.item_name,
            translate(
                "Connect this entry with other articles in your encyclopedia for cross-navigation."
            ),
            scrollable=False,
        )
        current_key = (
            self.full_item_key if self.full_item_key is not None else self.item_name
        )
        self.relations_tab = RelationsTab(
            current_key,
            self.item_type,
            self.existing_data.get("relations", []),
            self.main_app_window,
            self,
        )
        self.relations_tab.add_header_buttons(header_rel)
        layout_rel.addWidget(self.relations_tab)
        self._add_page(page_rel, translate("Relations"))

        self.links_page_widget, layout_links, header_links = self._create_page_wrapper(
            self.item_name,
            translate(
                "Attach URLs to external websites, streaming services or database pages."
            ),
            scrollable = True,
        )
        self._setup_links_content(layout_links, header_links)
        self._add_page(self.links_page_widget, translate("Links"))

    def _setup_general_content(self, layout, header_layout):
        """Constructs the General tab elements like title, summary text area, and cover changing."""
        self.search_btn = SearchToolButton(main_window=self.main_app_window)
        self.search_btn.set_lyrics_mode(False)
        self.search_btn.set_data_getter(lambda: (self.secondary_query, self.item_name))
        header_layout.addWidget(self.search_btn)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(24)

        cover_col = QVBoxLayout()
        cover_col.setContentsMargins(0, 0, 0, 0)
        cover_col.setSpacing(8)

        artwork_label = QLabel(translate("Article Artwork"))
        artwork_label.setProperty("class", "textTertiary textColorTertiary")
        cover_col.addWidget(artwork_label)

        self.cover_label = RoundedCoverLabel(QPixmap(), 6)
        self.cover_label.setFixedSize(228, 228)

        cover_btns_layout = QHBoxLayout()
        cover_btns_layout.setContentsMargins(0, 0, 0, 0)
        cover_btns_layout.setSpacing(0)

        change_cover_btn = QPushButton(translate("Change..."))
        change_cover_btn.setProperty("class", "btnText inputBorderMultiLeft")
        change_cover_btn.setFixedHeight(36)
        change_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_cover_btn.clicked.connect(self._change_cover_manual)

        self.reset_cover_btn = QPushButton()
        self.reset_cover_btn.setFixedSize(36, 36)
        self.reset_cover_btn.setProperty("class", "inputBorderMultiMiddle")
        self.reset_cover_btn.setIcon(
            QIcon(
                create_svg_icon(
                    "assets/control/undo.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
                )
            )
        )
        self.reset_cover_btn.setIconSize(QSize(20, 20))
        self.reset_cover_btn.clicked.connect(self._reset_cover)
        self.reset_cover_btn.setEnabled(False)

        self.redo_cover_btn = QPushButton()
        self.redo_cover_btn.setFixedSize(36, 36)
        self.redo_cover_btn.setProperty("class", "inputBorderMultiRight")
        self.redo_cover_btn.setIcon(
            QIcon(
                create_svg_icon(
                    "assets/control/redo.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
                )
            )
        )
        self.redo_cover_btn.setIconSize(QSize(20, 20))
        self.redo_cover_btn.clicked.connect(self._restore_new_cover)
        self.redo_cover_btn.setEnabled(False)

        cover_btns_layout.addWidget(change_cover_btn, 1)
        cover_btns_layout.addWidget(self.reset_cover_btn)
        cover_btns_layout.addWidget(self.redo_cover_btn)

        cover_col.addWidget(self.cover_label)
        cover_col.addLayout(cover_btns_layout)

        artwork_hint = QLabel(
            translate("By the way, the image added to the description for the artist")
        )
        artwork_hint.setWordWrap(True)
        artwork_hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        artwork_hint.setProperty("class", "textTertiary textColorTertiary")
        cover_col.addWidget(artwork_hint)

        cover_col.addStretch()

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(8)

        bind_group = QFrame()
        bind_group.setContentsMargins(0, 0, 0, 0)

        bind_lay = QVBoxLayout(bind_group)
        bind_lay.setContentsMargins(0, 0, 0, 0)
        bind_lay.setSpacing(8)

        bh_lay = QHBoxLayout()
        bh_lay.setContentsMargins(0, 0, 0, 0)
        bh_lay.setSpacing(8)

        library_binding_label = QLabel(translate("Library Binding"))
        library_binding_label.setProperty("class", "textTertiary textColorTertiary")
        bh_lay.addWidget(library_binding_label)

        bh_lay.addStretch()

        self.binding_info = QLabel()
        self.binding_info.setProperty("class", "textTertiary textColorTertiary")
        bh_lay.addWidget(self.binding_info)
        bind_lay.addLayout(bh_lay)

        sel_lay = QHBoxLayout()
        sel_lay.setContentsMargins(0, 0, 0, 0)
        sel_lay.setSpacing(0)

        self.object_selector = MetadataMergeControl(
            "", border_style="inputBorderMultiLeft inputBorderPaddingTextEdit"
        )

        self.clear_binding_btn = QPushButton()
        self.clear_binding_btn.setFixedSize(36, 36)
        self.clear_binding_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_binding_btn.setIcon(
            create_svg_icon(
                "assets/control/clear.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
            )
        )
        self.clear_binding_btn.setIconSize(QSize(20, 20))
        set_custom_tooltip(
            self.clear_binding_btn,
            title = translate("Unlink"),
        )
        self.clear_binding_btn.setProperty(
            "class", "inputBorderMultiRight"
        )
        apply_button_opacity_effect(self.clear_binding_btn)

        self.clear_binding_btn.clicked.connect(self._on_clear_binding_clicked)

        sel_lay.addWidget(self.object_selector)
        sel_lay.addWidget(self.clear_binding_btn)
        bind_lay.addLayout(sel_lay)

        right_col.addWidget(bind_group)
        right_col.addSpacing(16)

        main_title_label = QLabel(translate("Article Title"))
        main_title_label.setProperty("class", "textTertiary textColorTertiary")
        right_col.addWidget(main_title_label)

        btn_title_lay = QHBoxLayout()
        btn_title_lay.setContentsMargins(0, 0, 0, 0)
        btn_title_lay.setSpacing(0)

        self.main_title_edit = StyledLineEdit()
        self.main_title_edit.setFixedHeight(36)
        self.main_title_edit.setPlaceholderText(translate("Article Title"))
        self.main_title_edit.setProperty(
            "class", "inputBorderMultiLeft inputBorderPaddingTextEdit"
        )

        self.wiki_fetch_btn = QPushButton()
        set_custom_tooltip(
            self.wiki_fetch_btn,
            title = translate("Fetch description from Wikipedia"),
            text = translate("Get summary and cover for the article from Wikipedia"),
            activity_type="network_activity"
        )
        self.wiki_fetch_btn.setFixedSize(36, 36)
        self.wiki_fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wiki_fetch_btn.setIcon(
            create_svg_icon(
                "assets/control/search_web.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
            )
        )
        self.wiki_fetch_btn.setIconSize(QSize(20, 20))
        self.wiki_fetch_btn.setProperty("class", "inputBorderMultiRight")
        self.wiki_fetch_btn.clicked.connect(self._on_wiki_fetch_clicked)

        btn_title_lay.addWidget(self.main_title_edit)
        btn_title_lay.addWidget(self.wiki_fetch_btn)
        right_col.addLayout(btn_title_lay)

        right_col.addSpacing(8)

        main_desc_label = QLabel(translate("Summary Description"))
        main_desc_label.setProperty("class", "textTertiary textColorTertiary")
        right_col.addWidget(main_desc_label)

        self.main_content_edit = CleanRichTextEdit()
        self.main_content_edit.setProperty("class", "inputBorderSingle")
        self.main_content_edit.setPlaceholderText(translate("Summary description..."))
        self.main_content_edit.textChanged.connect(self._update_char_count)
        right_col.addWidget(self.main_content_edit, 1)

        self.chars_counter_lbl = QLabel(translate("0 / 800 (recommended)"))
        self.chars_counter_lbl.setContentsMargins(0, 0, 0, 0)
        self.chars_counter_lbl.setProperty("class", "textTertiary textColorTertiary")
        self.chars_counter_lbl.setCursor(Qt.CursorShape.WhatsThisCursor)
        set_custom_tooltip(
            self.chars_counter_lbl,
            title = translate("Why the limit?"),
            text = translate("The limit is for recommendation only. This text will be displayed on a compact encyclopedia card."),
        )
        self.chars_counter_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        right_col.addWidget(self.chars_counter_lbl)

        main_source_layout = QHBoxLayout()
        main_source_layout.setContentsMargins(0, 0, 0, 0)
        main_source_layout.setSpacing(16)

        source_title_layout = QVBoxLayout()
        source_title_layout.setContentsMargins(0, 0, 0, 0)
        source_title_layout.setSpacing(8)

        source_title_label = QLabel(translate("Source Title"))
        source_title_label.setProperty("class", "textTertiary textColorTertiary")
        source_title_layout.addWidget(source_title_label)

        self.main_source_name_edit = StyledLineEdit()
        self.main_source_name_edit.setFixedHeight(36)
        self.main_source_name_edit.setPlaceholderText(translate("Optional"))
        self.main_source_name_edit.setProperty("class", "inputBorderSinglePadding")
        source_title_layout.addWidget(self.main_source_name_edit)

        source_link_layout = QVBoxLayout()
        source_link_layout.setContentsMargins(0, 0, 0, 0)
        source_link_layout.setSpacing(8)

        source_link_label = QLabel(translate("Source URL"))
        source_link_label.setProperty("class", "textTertiary textColorTertiary")
        source_link_layout.addWidget(source_link_label)

        self.main_source_url_edit = StyledLineEdit()
        self.main_source_url_edit.setFixedHeight(36)
        self.main_source_url_edit.setPlaceholderText(translate("Optional"))
        self.main_source_url_edit.setProperty("class", "inputBorderSinglePadding")
        source_link_layout.addWidget(self.main_source_url_edit)

        main_source_layout.addLayout(source_title_layout, 1)
        main_source_layout.addLayout(source_link_layout, 2)
        right_col.addLayout(main_source_layout)

        if self.item_type == "album":
            right_col.addSpacing(16)
            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setProperty("class", "separator")
            right_col.addWidget(sep)

            right_col.addSpacing(16)
            album_desc_lay = QVBoxLayout()
            album_desc_lay.setContentsMargins(0, 0, 0, 0)
            album_desc_lay.setSpacing(4)

            meta_header = QLabel(translate("Album Specific Details"))
            meta_header.setProperty("class", "textHeaderSecondary textColorPrimary")
            album_desc_lay.addWidget(meta_header)

            meta_desc = QLabel(translate("Information based on a library bind object"))
            meta_desc.setWordWrap(True)
            meta_desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            meta_desc.setProperty("class", "textSecondary textColorPrimary")
            album_desc_lay.addWidget(meta_desc)

            right_col.addLayout(album_desc_lay)
            right_col.addSpacing(8)

            all_artists = sorted(
                list(self.main_app_window.data_manager.artists_data.keys())
            )
            all_genres = sorted(
                list(self.main_app_window.data_manager.genres_data.keys())
            )

            def add_meta_field(key, label_text, placeholder, suggestions=None):
                lbl = QLabel(label_text)
                lbl.setProperty("class", "textTertiary textColorTertiary")
                right_col.addWidget(lbl)

                inp = MetadataMergeControl("", border_style="inputBorderSinglePadding")

                if inp.lineEdit():
                    line_edit = inp.lineEdit()
                    line_edit.setPlaceholderText(placeholder)

                    if suggestions:
                        completer = GapCompleter(suggestions, inp, gap=4)
                        popup = completer.popup()
                        popup.setProperty("class", "listWidget")
                        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                        completer.setFilterMode(Qt.MatchFlag.MatchContains)
                        if inp.lineEdit():
                            inp.lineEdit().setCompleter(completer)

                self.meta_inputs[key] = inp
                right_col.addWidget(inp)
                right_col.addSpacing(12)

            add_meta_field("title", translate("Album Title"), translate("Album Title"))
            add_meta_field(
                "artist", translate("Artist"), translate("Artist Name"), all_artists
            )
            add_meta_field(
                "album_artist",
                translate("Album Artist"),
                translate("Album Artist"),
                all_artists,
            )
            add_meta_field(
                "composer", translate("Composer"), translate("Composer"), all_artists
            )
            add_meta_field("genre", translate("Genre"), translate("Genre"), all_genres)
            add_meta_field("year", translate("Year"), "1877")

        top_layout.addLayout(cover_col)
        top_layout.addLayout(right_col, 1)
        layout.addLayout(top_layout)
        layout.addStretch()

        self.object_selector.currentIndexChanged.connect(
            self._on_binding_object_changed
        )

    def _setup_additional_content(self, layout, header_layout):
        """Constructs the Content tab for adding sub-sections to the article."""
        actions_lay = QHBoxLayout()
        actions_lay.setSpacing(8)

        add_btn = QPushButton(translate("Add Section"))
        add_btn.setFixedHeight(36)
        add_btn.setIcon(
            create_svg_icon(
                "assets/control/add.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
            )
        )
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setProperty("class", "btnText textAlignLeft")
        add_btn.clicked.connect(lambda: self._add_block(give_focus = True))
        actions_lay.addWidget(add_btn)

        header_layout.addLayout(actions_lay)

        container = QWidget()
        split_lay = QHBoxLayout(container)
        split_lay.setContentsMargins(0, 0, 0, 0)
        split_lay.setSpacing(24)

        list_col = QVBoxLayout()
        list_col.setSpacing(8)

        list_label = QLabel(translate("Content"))
        list_label.setProperty("class", "textTertiary textColorTertiary")
        list_col.addWidget(list_label)

        self.blocks_list_widget = StyledListWidget()
        self.blocks_list_widget.setProperty("class", "listWidget")
        self.blocks_list_widget.currentRowChanged.connect(self._on_block_selected)

        self.blocks_list_widget.setVerticalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel
        )

        list_col.addWidget(self.blocks_list_widget)

        self.blocks_stack = QStackedWidget()
        self.empty_placeholder = QLabel(
            translate("Select a section to edit or add a new one.")
        )
        self.empty_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_placeholder.setProperty("class", "textSecondary textColorPrimary")
        self.blocks_stack.addWidget(self.empty_placeholder)

        split_lay.addLayout(list_col, 1)
        split_lay.addWidget(self.blocks_stack, 3)

        layout.addWidget(container)

    def _move_block_up(self):
        """Moves the currently selected block up."""
        self._move_block(-1)

    def _move_block_down(self):
        """Moves the currently selected block down."""
        self._move_block(1)

    def _move_block(self, direction):
        """
        Swaps the block at current row with the block at current row + direction.
        Syncs both the ListWidget (visuals) and StackedWidget (data).
        """
        row = self.blocks_list_widget.currentRow()
        target_row = row + direction

        if row < 0 or target_row < 0 or target_row >= self.blocks_list_widget.count():
            return

        current_stack_idx = row + 1
        target_stack_idx = target_row + 1

        editor_widget = self.blocks_stack.widget(current_stack_idx)
        self.blocks_stack.removeWidget(editor_widget)
        self.blocks_stack.insertWidget(target_stack_idx, editor_widget)

        title = editor_widget.title_edit.text() if hasattr(editor_widget, "title_edit") else ""
        item = self.blocks_list_widget.takeItem(row)

        self.blocks_list_widget.insertItem(target_row, item)

        new_list_item_widget = BlockListItemWidget(title)

        editor_widget.titleChanged.connect(new_list_item_widget.set_title)

        new_list_item_widget.removeRequested.connect(
            partial(self._remove_block, item, editor_widget)
        )

        self.blocks_list_widget.setItemWidget(item, new_list_item_widget)

        self.blocks_list_widget.setCurrentRow(target_row)

    def _setup_links_content(self, layout, header_layout):
        """Sets up the UI elements on the Links tab."""
        add_btn = QPushButton(translate("Add Link"))
        add_btn.setFixedHeight(36)
        add_btn.setIcon(
            create_svg_icon(
                "assets/control/add.svg", theme.COLORS["PRIMARY"], QSize(20, 20)
            )
        )
        add_btn.setIconSize(QSize(20, 20))
        add_btn.setProperty("class", "btnText textAlignLeft")
        add_btn.clicked.connect(lambda: self._add_link())
        header_layout.addWidget(add_btn)

        self.links_container = QWidget()
        self.links_container.setContentsMargins(0, 0, 0, 0)
        self.links_container.setProperty("class", "backgroundPrimary")

        self.links_layout = QVBoxLayout(self.links_container)
        self.links_layout.setContentsMargins(0, 0, 0, 0)
        self.links_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.links_layout.setSpacing(8)

        layout.addWidget(self.links_container)

    def _on_binding_object_changed(self, index):
        """Handles the logic when the bound library object is changed by the user."""
        def process_change():
            self._update_binding_status()

            if index <= 0:
                self._update_main_inputs_state()
                return

            selected_data = self.object_selector.currentData()
            if isinstance(selected_data, (list, tuple)):
                for inp in self.meta_inputs.values():
                    inp.blockSignals(True)

                self.meta_inputs["title"].update_current_value(selected_data[1])
                self.meta_inputs["artist"].update_current_value(selected_data[0])
                self.meta_inputs["year"].update_current_value(
                    str(selected_data[2]) if selected_data[2] != 0 else ""
                )

                dm = self.main_app_window.data_manager
                lib_data = dm.albums_data.get(tuple(selected_data))
                if lib_data:
                    self._smart_merge_metadata(lib_data)

                for inp in self.meta_inputs.values():
                    inp.blockSignals(False)

            self._update_main_inputs_state()

        QTimer.singleShot(0, process_change)

    def _smart_merge_metadata(self, lib_data):
        """Merges specific library metadata (like genre and composer) into current article metadata inputs."""
        def merge_field(field_key, new_values_list):
            control = self.meta_inputs[field_key]
            current_text = control.get_final_value().strip()

            if not current_text:
                clean_values = [
                    str(v).strip() for v in new_values_list if str(v).strip()
                ]
                if clean_values:
                    control.update_current_value(", ".join(clean_values))
                return

            current_tags = [
                t.strip() for t in re.split(r"[,;]", current_text) if t.strip()
            ]
            final_tags = list(current_tags)
            for val in new_values_list:
                val_s = str(val).strip()
                if val_s and val_s not in final_tags:
                    final_tags.append(val_s)

            control.update_current_value(", ".join(final_tags))

        merge_field("genre", lib_data.get("genre", []))

        aa = lib_data.get("album_artist")
        if not aa and lib_data.get("tracks"):
            aa = lib_data["tracks"][0].get("album_artist")
        if aa:
            merge_field("album_artist", [aa])

        comp_set = []
        for t in lib_data.get("tracks", []):
            if c_raw := t.get("composer"):
                parts = [p.strip() for p in re.split(r"[;/]", c_raw) if p.strip()]
                for p in parts:
                    if p not in comp_set:
                        comp_set.append(p)
        if comp_set:
            merge_field("composer", comp_set)

    def _fill_album_fields_from_library(self, album_key):
        """Silently queries library to overwrite empty or generic metadata with library metadata."""
        dm = self.main_app_window.data_manager
        target_key_3 = tuple(album_key[:3])
        album_data = None

        for k, v in dm.albums_data.items():
            if tuple(k[:3]) == target_key_3:
                album_data = v
                break

        if album_data and self.meta_inputs:
            for inp in self.meta_inputs.values():
                inp.blockSignals(True)
            self.meta_inputs["title"].update_current_value(album_key[1])
            self.meta_inputs["artist"].update_current_value(album_key[0])
            self.meta_inputs["album_artist"].update_current_value(
                album_data.get("album_artist", album_key[0])
            )
            self.meta_inputs["year"].update_current_value(
                str(album_key[2]) if album_key[2] != 0 else ""
            )
            self.meta_inputs["genre"].update_current_value(
                ", ".join(album_data.get("genre", [])[:2])
            )

            composers = set()
            for track in album_data.get("tracks", []):
                if comp_raw := track.get("composer"):
                    comps = [
                        c.strip() for c in re.split(r"[;/]", comp_raw) if c.strip()
                    ]
                    composers.update(comps)
            self.meta_inputs["composer"].update_current_value(
                ", ".join(list(composers)[:2])
            )

            for inp in self.meta_inputs.values():
                inp.blockSignals(False)

    def _on_clear_binding_clicked(self):
        """Removes the current library binding when the cross icon is clicked."""
        if self.object_selector.currentIndex() == 0:
            return
        self.object_selector.setCurrentIndex(0)

    def _update_binding_status(self):
        """Updates the text describing whether this article is bound to the local library."""
        current_data = self.object_selector.currentData()

        linked = current_data is not None

        if linked:
            self.binding_info.setText(translate("Linked to library object"))
            self.binding_info.setStyleSheet(f"color: {theme.COLORS['ACCENT']};")
        else:
            self.binding_info.setText(
                translate("Virtual entry (not linked to library)")
            )
            self.binding_info.setStyleSheet(f"color: {theme.COLORS['TERTIARY']};")

    def _populate_binding_ui(self):
        """Initiates the population of the selector dropdown used for library binding."""
        self._populate_object_list(self.item_type)

    def _populate_object_list(self, target_type):
        """Populates the object selector combo box with available data of target_type."""
        self.object_selector.blockSignals(True)
        self.object_selector.clear()

        self.object_selector.addItem(translate("No Link"), None)

        dm = self.main_app_window.data_manager
        items = []

        if target_type == "artist":
            items = [(n, n) for n in sorted(dm.artists_data.keys())]
        elif target_type == "composer":
            items = [(n, n) for n in sorted(dm.composers_data.keys())]
        elif target_type == "genre":
            items = [(n, n) for n in sorted(dm.genres_data.keys())]
        elif target_type == "album":
            seen_albums = set()
            for k in dm.albums_data.keys():
                short_key = tuple(k[:3])

                if short_key not in seen_albums:
                    display_text = f"{short_key[1]} ({short_key[0]})"
                    items.append((display_text, short_key))
                    seen_albums.add(short_key)

            items.sort(key=lambda x: x[0])

        for text, key in items:
            self.object_selector.addItem(text, key)

        model = [
            self.object_selector.itemText(i)
            for i in range(self.object_selector.count())
        ]
        completer = GapCompleter(model, self.object_selector, gap=4)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)

        if self.object_selector.lineEdit():
            self.object_selector.lineEdit().setCompleter(completer)
            completer.popup().setProperty("class", "listWidget")

        search_key = self.full_item_key
        if target_type == "album" and search_key:
            em = self.main_app_window.encyclopedia_manager
            search_key = em.normalize_album_key(search_key)

        if isinstance(search_key, list):
            search_key = tuple(search_key)

        idx = -1
        for i in range(1, self.object_selector.count()):
            if self.object_selector.itemData(i) == search_key:
                idx = i
                break

        if idx == -1:
            idx = 0

        self.object_selector.setCurrentIndex(idx)

        base_text = self.object_selector.itemText(idx)
        self.object_selector.set_reset_value(base_text)

        self.object_selector.blockSignals(False)
        self._update_binding_status()

    def _on_block_selected(self, row):
        """Switches the visible content editor in the StackedWidget when a block is selected from the list."""
        self.blocks_stack.setCurrentIndex(row + 1 if row >= 0 else 0)

    def _add_block(self, title="", content="", source_name="", source_url="", give_focus=False):
        """Creates a new text block section in the Content tab and updates the layout."""
        editor = BlockWidget(title=title, content=content, source_name=source_name, source_url=source_url)
        self.blocks_stack.addWidget(editor)

        list_item = QListWidgetItem(self.blocks_list_widget)
        item_widget = BlockListItemWidget(title)
        list_item.setSizeHint(item_widget.sizeHint())

        self.blocks_list_widget.setItemWidget(list_item, item_widget)

        editor.titleChanged.connect(item_widget.set_title)

        item_widget.removeRequested.connect(
            lambda: self._remove_block(list_item, editor)
        )

        item_widget.moveUpRequested.connect(
            lambda: self._move_block_from_item(list_item, -1)
        )
        item_widget.moveDownRequested.connect(
            lambda: self._move_block_from_item(list_item, 1)
        )

        self.blocks_list_widget.setCurrentRow(self.blocks_list_widget.count() - 1)

        if give_focus:
            editor.title_edit.setFocus()
            editor.title_edit.setCursorPosition(len(editor.title_edit.text()))

    def _move_block_from_item(self, item, direction):
        """
        Moves the specific item up or down.
        Reconstructs the widget and ensures signals are re-connected.
        """
        row = self.blocks_list_widget.row(item)
        target_row = row + direction

        if row < 0 or target_row < 0 or target_row >= self.blocks_list_widget.count():
            return

        current_stack_idx = row + 1
        target_stack_idx = target_row + 1

        editor_widget = self.blocks_stack.widget(current_stack_idx)
        self.blocks_stack.removeWidget(editor_widget)
        self.blocks_stack.insertWidget(target_stack_idx, editor_widget)

        title = editor_widget.title_edit.text() if hasattr(editor_widget, "title_edit") else ""

        taken_item = self.blocks_list_widget.takeItem(row)

        self.blocks_list_widget.insertItem(target_row, taken_item)

        new_list_item_widget = BlockListItemWidget(title)

        editor_widget.titleChanged.disconnect()
        editor_widget.titleChanged.connect(new_list_item_widget.set_title)

        new_list_item_widget.removeRequested.connect(
            partial(self._remove_block, taken_item, editor_widget)
        )

        new_list_item_widget.moveUpRequested.connect(
            lambda: self._move_block_from_item(taken_item, -1)
        )
        new_list_item_widget.moveDownRequested.connect(
            lambda: self._move_block_from_item(taken_item, 1)
        )

        self.blocks_list_widget.setItemWidget(taken_item, new_list_item_widget)

        self.blocks_list_widget.setCurrentRow(target_row)

    def _remove_block(self, item, widget):
        """Removes a content block from both the UI list and underlying stack widget."""
        row = self.blocks_list_widget.row(item)
        if row < 0:
            return

        self.blocks_stack.removeWidget(widget)
        widget.deleteLater()

        self.blocks_list_widget.takeItem(row)

        if self.blocks_list_widget.count() == 0:
            self.blocks_stack.setCurrentIndex(0)

    def _add_link(self, title = "", url = ""):
        """Adds a new LinkWidget to the Links tab layout."""
        w = LinkWidget(self.links_container, title, url)

        if hasattr(w, "url_edit") and hasattr(w, "title_edit"):
            w.url_edit.textChanged.connect(lambda: self._auto_fill_link_title(w))

        self.links_layout.addWidget(w)

    def _auto_fill_link_title(self, link_widget):
        """
        [NEW] Parses the URL and sets the title if the title is currently empty.
        """
        if link_widget.title_edit.text().strip():
            return

        url = link_widget.url_edit.text().strip()
        if not url:
            return

        candidate_title = translate("New Link")

        try:
            parsed = urlparse(url if "://" in url else "http://" + url)
            if parsed.netloc:
                domain = parsed.netloc
                if domain.startswith("www."):
                    domain = domain[4:]
                candidate_title = domain.capitalize()
        except Exception:
            pass

        link_widget.title_edit.blockSignals(True)
        link_widget.title_edit.setText(candidate_title)
        link_widget.title_edit.blockSignals(False)

    def _load_data(self):
        """Populates the entire dialog with existing article and library data."""
        em = self.main_app_window.encyclopedia_manager
        entry = em.get_entry(self.original_key, self.item_type)

        self._populate_binding_ui()

        if self.object_selector.currentIndex() > 0:
            self._on_binding_object_changed(self.object_selector.currentIndex())

        if entry:
            blocks = entry.get("blocks", [])
            if blocks:
                first_block = blocks[0]
                self.main_title_edit.setText(first_block.get("title", ""))
                self.main_content_edit.setHtml(first_block.get("content", ""))

                if hasattr(self, "main_source_name_edit"):
                    self.main_source_name_edit.setText(first_block.get("source_name", ""))
                if hasattr(self, "main_source_url_edit"):
                    self.main_source_url_edit.setText(first_block.get("source_url", ""))

                if len(blocks) > 1:
                    for b in blocks[1:]:
                        self._add_block(
                            title = b.get("title", ""),
                            content = b.get("content", ""),
                            source_name = b.get("source_name", ""),
                            source_url = b.get("source_url", "")
                        )
                else:
                    self._add_block()

            if self.item_type == "album" and self.meta_inputs:
                for inp in self.meta_inputs.values():
                    inp.blockSignals(True)

                self.meta_inputs["artist"].update_current_value(entry.get("artist", ""))
                self.meta_inputs["album_artist"].update_current_value(entry.get("album_artist", ""))
                self.meta_inputs["composer"].update_current_value(entry.get("composer", ""))
                self.meta_inputs["genre"].update_current_value(entry.get("genre", ""))

                self.meta_inputs["title"].update_current_value(
                    entry.get("title") or (blocks[0].get("title") if blocks else ""))

                yr = entry.get("year", 0)
                self.meta_inputs["year"].update_current_value(str(yr) if yr and yr != 0 else "")

                for inp in self.meta_inputs.values():
                    inp.blockSignals(False)

            for link in entry.get("links", []):
                self._add_link(title = link.get("title", ""), url = link.get("url", ""))

        else:
            self.main_title_edit.setText(self.item_name)
            self._add_block()
            if self.initial_meta and self.item_type == "album":
                for k, v in self.initial_meta.items():
                    if k in self.meta_inputs:
                        val_str = "" if v is None else str(v)
                        self.meta_inputs[k].update_current_value(val_str)

        self._update_cover_display()

        self._update_main_inputs_state()
        self._update_binding_status()

    def _update_char_count(self):
        """Counts the characters in the summary rich text field and updates the label label."""
        plain_text = self.main_content_edit.toPlainText()
        count = len(plain_text)
        limit = 800

        self.chars_counter_lbl.setText(
            f"{count} / {limit}" + " " + translate("(recommended)")
        )

    def _update_cover_display(self):
        """Renders the main article artwork, fallback image, or missing placeholder on screen."""
        path_to_show = None
        self.is_main_cover_missing = False
        if self.image_path:
            if os.path.exists(self.image_path):
                path_to_show = self.image_path
            else:
                self.is_main_cover_missing = True
        if not path_to_show and not self.is_main_cover_missing:
            if self.default_image_path and os.path.exists(self.default_image_path):
                path_to_show = self.default_image_path

        if self.is_main_cover_missing:
            pixmap = create_missing_placeholder_pixmap(QSize(250, 250))
        elif path_to_show:
            pixmap = QPixmap(path_to_show)
        else:
            pixmap = QIcon(resource_path("assets/view/encyclopedia_entry.svg")).pixmap(
                240, 240
            )

        self.cover_label.setPixmap(pixmap)
        if self.original_cover_pixmap is None:
            self.original_cover_pixmap = pixmap
        self._update_cover_buttons()

    def _change_cover_manual(self):
        """Allows the user to select a new cover image via file dialog."""
        f, _ = QFileDialog.getOpenFileName(
            self, translate("Select Cover"), "", "Images (*.png *.jpg *.jpeg)"
        )
        if f:
            self._apply_new_cover(f)

    def _apply_new_cover(self, path):
        """Assigns the newly selected cover path and updates visual representation."""
        self.new_cover_path = path
        self.cached_new_cover_path = path
        pix = QPixmap(path)
        if not pix.isNull():
            self.cover_label.setPixmap(pix)
        self._update_cover_buttons()

    def _reset_cover(self):
        """Restores the original cover image if the user had changed it or marks it fixed if missing."""
        if self.is_main_cover_missing:
            self.image_path = None
            self.is_main_cover_missing = False
            self.new_cover_path = None
            self._update_cover_display()
        else:
            if self.original_cover_pixmap:
                self.cover_label.setPixmap(self.original_cover_pixmap)
                self.new_cover_path = None
                self._update_cover_buttons()

    def _restore_new_cover(self):
        """Re-applies the user-selected new cover if the user accidentally pressed reset."""
        if self.cached_new_cover_path and os.path.exists(self.cached_new_cover_path):
            self._apply_new_cover(self.cached_new_cover_path)

    def _update_cover_buttons(self):
        """Enables or disables undo/redo buttons depending on current image path state."""
        can_reset = (self.new_cover_path is not None) or self.is_main_cover_missing
        self.reset_cover_btn.setEnabled(can_reset)
        can_redo = (
            (self.new_cover_path is None)
            and (self.cached_new_cover_path is not None)
            and not self.is_main_cover_missing
        )
        self.redo_cover_btn.setEnabled(can_redo)

    def _on_wiki_fetch_clicked(self):
        """Initiates a Wikipedia search for pulling article content dynamically."""
        app_lang = getattr(self.main_app_window, "current_language", "en")
        search_dlg = EncyclopediaSearchDialog(self.item_name, app_lang, self)

        if search_dlg.exec():
            title, selected_lang = search_dlg.get_result()

            if title:
                self.wiki_fetch_btn.setEnabled(False)
                self.worker = FetchWorker(
                    self.main_app_window.encyclopedia_manager, title, selected_lang
                )
                self.worker.finished.connect(self._on_fetch_finished)
                self.worker.start()

    def _on_fetch_finished(self, result):
        """Receives completed Wikipedia data request result, inserting into fields on success."""
        self.wiki_fetch_btn.setEnabled(True)
        if result:
            if result.get("content"):
                self.main_content_edit.setHtml(result["content"])

            if result.get("source_url"):
                self.main_source_name_edit.setText("Wikipedia")
                self.main_source_url_edit.setText(result["source_url"])

            if result.get("local_image_path"):
                self._apply_new_cover(result["local_image_path"])

            self.status_label.setText(translate("Wikipedia data imported."))
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))
        else:
            self.status_label.setText(translate("No data found or error occurred."))

    def _on_delete_clicked(self):
        """Asks for confirmation before deleting the currently opened article."""
        res, unlink = DeleteWithCheckboxDialog.confirm(
            self,
            translate("Delete Entry"),
            translate("Delete article?"),
            translate("Unlink references"),
            ok_text = translate("Delete"),
            cancel_text = translate("Cancel"),
        )
        if res:
            self._delete_requested = True
            self.unlink_on_delete = unlink
            self.accept()

    def get_data(self):
        """Generates the comprehensive data dictionary representing the finished encyclopedia article."""
        if self._delete_requested:
            return None
        if hasattr(self, "_merged_final_data"):
            return self._merged_final_data

        m_title = self.main_title_edit.text().strip()
        raw_html = self.main_content_edit.toHtml()
        match = re.search(r"<body[^>]*>(.*?)</body>", raw_html, re.DOTALL | re.IGNORECASE)
        clean_html = match.group(1).strip() if match else raw_html
        clean_html = re.sub(r"margin-top:\d+px;", "margin-top:0px;", clean_html)
        clean_html = re.sub(r"margin-bottom:\d+px;", "margin-bottom:0px;", clean_html)

        main_s_name = self.main_source_name_edit.text().strip() if hasattr(self, "main_source_name_edit") else ""
        main_s_url = self.main_source_url_edit.text().strip() if hasattr(self, "main_source_url_edit") else ""

        blocks = [{
            "title": m_title,
            "content": clean_html,
            "source_name": main_s_name,
            "source_url": main_s_url
        }]

        for i in range(1, self.blocks_stack.count()):
            w = self.blocks_stack.widget(i)
            if hasattr(w, "get_data"):
                d = w.get_data()
                if d:
                    blocks.append(d)

        links = []
        for w in self.links_container.findChildren(QWidget):
            if hasattr(w, "get_data"):
                d = w.get_data()
                if d:
                    links.append(d)

        rels, inter = self.relations_tab.get_relations_data()

        raw_gallery = self.gallery_tab.get_data()
        final_gallery = []
        for item in raw_gallery:
            if isinstance(item, dict):
                final_gallery.append(item)
            else:
                final_gallery.append({"path": str(item), "caption": ""})

        data = {
            "image_path": self.new_cover_path or self.image_path or self.default_image_path,
            "gallery": final_gallery,
            "blocks": [b for b in blocks if b],
            "links": links,
            "relations": rels,
            "interlink_all": inter,
        }

        if self.item_type == "album" and self.meta_inputs:
            bind_idx = self.object_selector.currentIndex()

            if bind_idx > 0:
                lib_key = self.object_selector.currentData()
                data["artist"] = lib_key[0]
                data["title"] = lib_key[1]
                data["year"] = lib_key[2]
            else:
                data["artist"] = self.meta_inputs["artist"].get_final_value()
                data["title"] = self.meta_inputs["title"].get_final_value()
                try:
                    year_val = self.meta_inputs["year"].get_final_value()
                    data["year"] = int(year_val) if year_val.isdigit() else 0
                except:
                    data["year"] = 0

            data["album_artist"] = self.meta_inputs["album_artist"].get_final_value()
            data["composer"] = self.meta_inputs["composer"].get_final_value()
            data["genre"] = self.meta_inputs["genre"].get_final_value()

        if hasattr(self, "discography_tab"):
            data["discography"] = self.discography_tab.get_data()

        return data

    def _update_main_inputs_state(self):
        """Enables or disables editability of key album metadata depending on binding status."""
        if self.item_type != "album":
            return

        is_linked = self.object_selector.currentIndex() > 0

        self.main_title_edit.setEnabled(True)

        identity_fields = ["title", "artist", "year"]

        for key, input_control in self.meta_inputs.items():
            if key in identity_fields:
                input_control.setEnabled(not is_linked)
                if is_linked:
                    set_custom_tooltip(
                        input_control,
                        title = translate("Linked to library object identification"),
                        text = translate("While the article is linked to a music library object, this field will be auto-filled"),
                    )
                else:
                    set_custom_tooltip(input_control)
            else:
                input_control.setEnabled(True)


    def accept(self):
        """Handles final validation, conflict resolution, and saves the dialog prior to closing."""
        for i in range(self.links_layout.count()):
            item = self.links_layout.itemAt(i)
            widget = item.widget()

            if widget and hasattr(widget, "title_edit"):
                title_text = widget.title_edit.text().strip()
                if not title_text:
                    CustomConfirmDialog.confirm(
                        self,
                        translate("Oops! Unnamed link detected."),
                        translate(
                            "To save the article, please fill in all 'Link Title' fields on the corresponding tab."),
                        ok_text = translate("OK"),
                        cancel_text = None
                    )

                    if hasattr(self, "links_page_widget"):
                        self.stacked_widget.setCurrentWidget(self.links_page_widget)
                        for row in range(self.nav_list.count()):
                            if self.nav_list.item(row).text() == translate("Links"):
                                self.nav_list.setCurrentRow(row)
                                break

                    widget.title_edit.setFocus()
                    return

        em = self.main_app_window.encyclopedia_manager
        new_type = self.item_type
        idx = self.object_selector.currentIndex()

        if new_type == "album":
            if idx > 0:
                raw_data = self.object_selector.itemData(idx)
                new_key = tuple(raw_data) if isinstance(raw_data, list) else raw_data
            else:
                f_artist = self.meta_inputs["artist"].get_final_value().strip()
                f_title = self.meta_inputs["title"].get_final_value().strip()
                f_year_str = self.meta_inputs["year"].get_final_value().strip()

                final_title = f_title or self.main_title_edit.text().strip()
                final_artist = f_artist or (
                    self.original_key[0] if isinstance(self.original_key, tuple) else translate("Unknown Artist"))

                try:
                    final_year = int(f_year_str) if f_year_str.isdigit() else (
                        self.original_key[2] if isinstance(self.original_key, tuple) else 0)
                except:
                    final_year = 0

                new_key = (final_artist, final_title, final_year)

            new_key = em.normalize_album_key(new_key)
        else:
            text = self.object_selector.currentText().strip()
            new_key = text if idx > 0 else self.main_title_edit.text().strip()

        orig_key_norm = em.normalize_album_key(
            self.original_key) if self.original_type == "album" else self.original_key

        k1 = tuple(new_key) if isinstance(new_key, (list, tuple)) else new_key
        k2 = tuple(orig_key_norm) if isinstance(orig_key_norm, (list, tuple)) else orig_key_norm

        if k1 != k2:
            existing = em.get_entry(new_key, new_type)
            if existing:
                cur_data = self.get_data()
                conflict = EncyclopediaConflictDialog(
                    new_key, new_type, existing, cur_data, str(em.images_dir), parent = self, is_import = False
                )
                result = conflict.exec()

                if result == EncyclopediaConflictDialog.ResultKeepCurrent:
                    self.object_selector.setCurrentIndex(0)

                    if self.original_type == "album":
                        orig = self.original_key
                        if isinstance(orig, (list, tuple)) and len(orig) >= 3:
                            self.meta_inputs["artist"].update_current_value(str(orig[0]))
                            self.meta_inputs["title"].update_current_value(str(orig[1]))
                            self.meta_inputs["year"].update_current_value(str(orig[2]) if orig[2] != 0 else "")
                            self.main_title_edit.setText(str(orig[1]))

                        orig_album_artist = ""
                        orig_composer = ""
                        orig_genre = ""

                        if self.existing_data:
                            orig_album_artist = self.existing_data.get("album_artist", "")
                            orig_composer = self.existing_data.get("composer", "")
                            orig_genre = self.existing_data.get("genre", "")
                        elif self.initial_meta:
                            orig_album_artist = self.initial_meta.get("album_artist", "")
                            orig_composer = self.initial_meta.get("composer", "")
                            orig_genre = self.initial_meta.get("genre", "")

                        self.meta_inputs["album_artist"].update_current_value(str(orig_album_artist))
                        self.meta_inputs["composer"].update_current_value(str(orig_composer))
                        self.meta_inputs["genre"].update_current_value(str(orig_genre))

                    else:
                        self.main_title_edit.setText(str(self.original_key))

                    return

                elif result == EncyclopediaConflictDialog.ResultMerge:
                    self._merged_final_data = em.merge_entry_data(existing.copy(), cur_data)
                    self.full_item_key = new_key

                elif result in (EncyclopediaConflictDialog.ResultOverwrite,
                                EncyclopediaConflictDialog.ResultOverwriteAll):
                    self._merged_final_data = cur_data
                    self.full_item_key = new_key
                else:
                    return
            else:
                self.full_item_key = new_key
        else:
            self.full_item_key = k2

        if hasattr(self, "discography_tab"):
            self.discography_tab.process_migrations()

        super().accept()