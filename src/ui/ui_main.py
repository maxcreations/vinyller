"""
Vinyller — Main window
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
import sys
import time
from collections import defaultdict

from PyQt6.QtCore import (
    pyqtSignal, QByteArray, QEvent, QLibraryInfo, QPoint, QProcess,
    QSize, Qt,
    QThread, QTimer, QTranslator, QUrl
)
from PyQt6.QtGui import (
    QIcon, QAction, QPainter, QPixmap, QDesktopServices
)
from PyQt6.QtMultimedia import QMediaDevices, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QScrollArea
)

from src.core.action_handler import ActionHandler
from src.core.hotkey_manager import HotkeyManager
from src.core.library_manager import (
    LibraryManager
)
from src.core.library_processor import (
    DataManager, LibraryProcessor, PlaylistIndexingWorker, LibraryChangeChecker
)
from src.core.state_manager import PlayerController
from src.core.update_checker import UpdateCheckerThread
from src.encyclopedia.encyclopedia_manager import EncyclopediaManager
from src.encyclopedia.encyclopedia_manager_window import EncyclopediaWindow
from src.player.player import Player, RepeatMode
from src.ui.custom_base_dialogs import StyledMainWindow
from src.ui.custom_base_widgets import SHADOW_SHIFT_Y, set_custom_tooltip
from src.ui.custom_classes import (
    AlphaJumpPopup, ChartsPeriod,
    SearchMode, SortMode,
    ViewMode
)
from src.ui.custom_dialogs import (
    ClearStatsConfirmDialog, CustomConfirmDialog,
    LanguageSelectionDialog
)
from src.ui.custom_lists import (
    QueueDelegate
)
from src.ui.managers.ui_manager import UIManager
from src.ui.mode_mini import MiniVinny
from src.ui.ui_components import ToastNotification, PendingUpdatesPopup
from src.ui.ui_settings import SettingsWindow
from src.utils import theme
from src.utils.constants import (ArtistSource,
                                 STATS_AWARD_CAP_S, STATS_AWARD_MIN_S, STATS_AWARD_PERCENTAGE, STATS_POLL_INTERVAL_S,
                                 STATS_SAVE_TRIGGER_INTERVAL_M, APP_VERSION
                                 )
from src.utils.constants_linux import IS_LINUX
from src.utils.utils import (
    create_svg_icon, resource_path, is_onefile_build
)
from src.utils.utils_translator import translate, set_current_language


class MainWindow(StyledMainWindow):
    """
    Main application window class handling the UI, player state, library management,
    and tying together various subsystems of Vinyller.
    """
    queueViewOptionsChanged = pyqtSignal()

    def __init__(self):
        """Initializes the main window and all core components."""
        super().__init__()

        self.right_panel = None
        self.vinyl_widget = None
        self.control_panel = None

        self.is_checking_library_changes = False

        self.qt_translator = None

        self.player = Player(self)
        self.library_manager = LibraryManager()
        self.data_manager = DataManager()
        self.startup_structure_snapshot = self.library_manager.load_library_structure()
        self.pending_external_changes_count = 0
        self.pending_added_modified_paths = []
        self.pending_removed_paths = []

        self.app_update_available = False
        self.app_update_version = ""
        self.app_update_url = ""
        self.update_ignored_this_session = False

        self.encyclopedia_manager = EncyclopediaManager(
            self.library_manager.app_data_dir
        )
        self.ui_manager = UIManager(self)
        self.player_controller = PlayerController(self)
        self.action_handler = ActionHandler(self)

        if sys.platform == "darwin":
            from src.core.mac_media_handler import MacMediaManager
            self.mac_media_manager = MacMediaManager.alloc().initWithWindow_(self)

        self.previous_stack_index = 0
        self.global_search_page_index = -1

        settings_path = self.library_manager.settings_path
        settings = self.library_manager.load_settings()

        if not os.path.exists(settings_path) or "language" not in settings:
            lang_dialog = LanguageSelectionDialog(self)
            if lang_dialog.exec():
                selected_lang = lang_dialog.selected_language_code()
                self.current_language = selected_lang if selected_lang else "en"
            else:
                self.current_language = "en"
            settings["language"] = self.current_language
            self.library_manager.save_settings(settings)
        else:
            self.current_language = settings.get("language", "en")

        set_current_language(self.current_language)
        self.load_qt_translations(self.current_language)

        self.setWindowTitle(translate("Vinyller"))
        self.setGeometry(100, 100, 1440, 960)
        self.setMinimumHeight(480)
        self.setWindowIcon(QIcon(resource_path("assets/logo/app_icon.png")))

        self.last_played_index = -1

        self.current_theme = settings.get("theme", "Light")
        self.current_accent = settings.get("accent_color", "Crimson")
        theme.select_theme(self.current_theme, self.current_accent)

        QApplication.instance().setStyleSheet(theme.get_compiled_stylesheet())

        self.pending_metadata_updates = set()
        self.pending_metadata_items_count = 0
        self.pending_settings_rescan = False
        pending_paths_on_startup = self.library_manager.load_pending_updates()
        if pending_paths_on_startup:
            self.pending_metadata_updates = set(pending_paths_on_startup)
            self.pending_metadata_items_count = len(self.pending_metadata_updates)


        self.favorites = {}
        self.artist_artworks = {}
        self.genre_artworks = {}
        self.current_ui_queue = []
        self.scan_thread = None
        self.processor = None
        self.is_processing_library = False

        self.current_search_results = []
        self.current_artists_display_list = []
        self.current_albums_display_list = []
        self.current_songs_display_list = []
        self.current_genres_display_list = []
        self.search_mode = SearchMode.EVERYWHERE
        self.search_view_mode = ViewMode.ALL_TRACKS
        self.current_artist_view = None
        self.current_genre_view = None
        self.current_favorites_context = None
        self.composers_loaded_count = 0
        self.is_loading_composers = False
        self.current_composers_display_list = []
        self.last_composer_letter = None
        self.current_composer_flow_layout = None
        self.current_composer_view = None
        self.current_composer_albums_list = []
        self.composer_albums_loaded_count = 0
        self.is_loading_composer_albums = False

        self.current_charts_context = None

        self.mini_window = None

        self.current_favorite_folder_path_nav = ""
        self.current_catalog_path = ""
        self.scroll_positions = {}
        self.last_splitter_sizes = []
        self.current_queue_name = translate("Playback Queue")
        self.current_queue_context_path = None
        self.current_queue_context_data = None
        self.current_open_playlist_path = None

        self.playlists_need_refresh = False

        self.last_right_panel_width = settings.get("lastRightPanelWidth", 300)

        self.current_playlists_display_list = []
        self.playlists_loaded_count = 0
        self.is_loading_playlists = False

        (
            self.artists_loaded_count,
            self.albums_loaded_count,
            self.songs_loaded_count,
            self.search_loaded_count,
            self.genres_loaded_count,
        ) = (0, 0, 0, 0, 0)

        self.charts_loaded_count = 0
        self.is_loading_charts = False
        self.current_charts_artist_album_list = []
        self.charts_artist_albums_loaded_count = 0
        self.is_loading_charts_artist_albums = False
        self.current_charts_genre_album_list = []
        self.charts_genre_albums_loaded_count = 0
        self.is_loading_charts_genre_albums = False

        self.current_charts_all_artists_list = []
        self.charts_all_artists_loaded_count = 0
        self.is_loading_charts_all_artists = False
        self.last_charts_all_artists_group = None
        self.current_charts_all_artists_flow_layout = None

        self.current_charts_all_albums_list = []
        self.charts_all_albums_loaded_count = 0
        self.is_loading_charts_all_albums = False
        self.last_charts_all_albums_group = None
        self.current_charts_all_albums_flow_layout = None

        self.current_charts_all_genres_list = []
        self.charts_all_genres_loaded_count = 0
        self.is_loading_charts_all_genres = False
        self.last_charts_all_genres_group = None
        self.current_charts_all_genres_flow_layout = None

        self.current_charts_all_composers_list = []
        self.charts_all_composers_loaded_count = 0
        self.is_loading_charts_all_composers = False
        self.last_charts_all_composers_group = None
        self.current_charts_all_composers_flow_layout = None

        self.current_charts_composer_album_list = []
        self.charts_composer_albums_loaded_count = 0
        self.is_loading_charts_composer_albums = False

        self.current_fav_all_artists_list = []
        self.fav_all_artists_loaded_count = 0
        self.is_loading_fav_all_artists = False
        self.last_fav_all_artists_group = None
        self.current_fav_all_artists_flow_layout = None

        self.current_fav_all_albums_list = []
        self.fav_all_albums_loaded_count = 0
        self.is_loading_fav_all_albums = False
        self.last_fav_all_albums_group = None
        self.current_fav_all_albums_flow_layout = None

        self.current_fav_all_genres_list = []
        self.fav_all_genres_loaded_count = 0
        self.is_loading_fav_all_genres = False
        self.last_fav_all_genres_group = None
        self.current_fav_all_genres_flow_layout = None

        self.current_fav_all_playlists_list = []
        self.fav_all_playlists_loaded_count = 0
        self.is_loading_fav_all_playlists = False

        self.current_fav_all_folders_list = []
        self.fav_all_folders_loaded_count = 0
        self.is_loading_fav_all_folders = False

        (
            self.is_loading_search,
            self.is_loading_artists,
            self.is_loading_genres,
            self.is_loading_albums,
            self.is_loading_songs,
        ) = (False, False, False, False, False)
        self.current_fav_artist_album_list = []
        self.fav_artist_albums_loaded_count = 0
        self.is_loading_fav_artist_albums = False
        self.current_fav_genre_album_list = []
        self.fav_genre_albums_loaded_count = 0
        self.is_loading_fav_genre_albums = False
        self.is_initial_cache_load = False
        self.rescan_initiated_from_dialog = False
        self.last_artist_letter, self.last_album_group = None, None
        (
            self.current_artist_flow_layout,
            self.current_album_flow_layout,
            self.current_genre_flow_layout,
        ) = (None, None, None)
        self.main_view_track_widgets = defaultdict(list)
        self.main_view_track_lists = []
        self.main_view_cover_widgets = defaultdict(list)
        self.main_view_card_widgets = defaultdict(list)
        self.main_view_header_play_buttons = {}
        self.pixmap_cache = {}
        self.remember_last_view = False
        self.window_geometry = None
        self.remember_window_size = True
        self.remember_vinyl_window_size = True
        self.saved_vinyl_size = [392, 592]
        self.stylize_vinyl_covers = False
        self.warm_sound = False
        self.mini_opacity = not IS_LINUX
        self.ignore_genre_case = True
        self.show_random_suggestions = True
        self.favorite_icon_name = "favorite_heart"
        self.splitter_sizes = None
        self.current_view_state = {}
        self.active_metadata_dialog = None
        self.queue_state_before_soft_reload = None
        self.current_artwork_path = None
        self.original_geometry = None
        self.queue_visible_before_vinyl = True
        self.is_scrubbing = False
        self.was_playing_before_scrub = False
        self.SCRUB_SENSITIVITY_MS_PER_DEGREE = 4000 / 360
        self.active_drop_zone = -1
        self.is_restoring_state = False
        self.queue_show_cover = False
        self.favorite_detail_scroll_area = None
        self.favorite_detail_separator_widgets = {}

        self.chart_detail_scroll_area = None
        self.chart_detail_separator_widgets = {}

        self.show_favorites_separators = False
        self.playback_history_mode = 0
        self.history_store_unique_only = True
        self.is_first_play_of_session = True
        self.is_restoring_queue = False
        self.treat_folders_as_unique = False
        self.scratch_sound = False
        self.collect_statistics = True

        self.encyclopedia_manager_window = None
        self.encyclopedia_manager.rotate_json_backups()

        self.conscious_choice_data = None

        self.STATS_AWARD_MIN_S = STATS_AWARD_MIN_S
        self.STATS_AWARD_PERCENTAGE = STATS_AWARD_PERCENTAGE
        self.STATS_AWARD_CAP_S = STATS_AWARD_CAP_S

        self.reload_timer = QTimer(self)
        self.reload_angle = 0
        self.settings_icon = create_svg_icon(
            "assets/control/options.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        self.reload_icon = create_svg_icon(
            "assets/control/scan.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
        )
        self.check_icon = QIcon(
            create_svg_icon(
                "assets/control/check.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.mixtape_icon = QIcon(
            create_svg_icon(
                "assets/control/mixtape.svg", theme.COLORS["PRIMARY"], QSize(24, 24)
            )
        )
        self.folder_pixmap = QPixmap(resource_path("assets/view/folder.png"))

        self.global_search_debounce_timer = QTimer(self)
        self.global_search_debounce_timer.setInterval(300)
        self.global_search_debounce_timer.setSingleShot(True)

        self.now_playing_animation_timer = QTimer(self)
        self.now_playing_animation_timer.setInterval(120)
        self.now_playing_animation_frame = 0

        self.last_track_change_time = time.time()
        self.charts_data_is_stale = False
        self.pending_stats_save = False

        self.stats_save_trigger_timer = QTimer(self)
        self.stats_save_trigger_timer.setInterval(
            STATS_SAVE_TRIGGER_INTERVAL_M * 60 * 1000
        )
        self.stats_save_trigger_timer.timeout.connect(
            self.on_stats_save_trigger_timeout
        )

        self.stats_poll_timer = QTimer(self)
        self.stats_poll_timer.setInterval(STATS_POLL_INTERVAL_S * 1000)
        self.stats_poll_timer.timeout.connect(self.on_stats_poll_timer_timeout)

        self.load_settings()
        self._update_favorite_icons()
        self.favorites = self.library_manager.load_favorites()
        self.artist_artworks = self.library_manager.load_artist_artworks()
        self.genre_artworks = self.library_manager.load_genre_artworks()
        self.composer_artworks = self.library_manager.load_composer_artworks()

        self.ui_manager.setup_ui()

        self.tab_history = {icon_name: [] for icon_name in self.nav_button_icon_names}

        self.toast = ToastNotification(self)
        if hasattr(self, "splitter") and self.splitter.count() > 0:
            self.splitter.widget(0).setMinimumWidth(300)
            self.splitter.setCollapsible(0, False)

        self.pending_updates_widget = PendingUpdatesPopup(
            parent = self,
            update_callback = self._process_pending_updates,
            hide_callback = self._on_pending_updates_hidden,
            postpone_callback = self._on_update_postponed
        )
        self.pending_updates_widget.hide()

        self._update_pending_updates_widget()
        self.hotkey_manager = HotkeyManager(
            self, self.player_controller, self.action_handler
        )
        self.setAcceptDrops(True)

        self.connect_signals()
        self.apply_player_settings()
        self.apply_ui_settings()

        self.right_panel.installEventFilter(self)
        self.splitter.splitterMoved.connect(self._sync_search_bar_width)

        if self.right_panel.isVisible():
            self._sync_search_bar_width()

        if self.collect_statistics:
            self.library_manager.process_stats_log()
            try:
                self.library_manager.archive_monthly_stats_if_needed()
            except Exception as e:
                print(f"Error while archiving monthly charts: {e}")

        self.media_devices = QMediaDevices(self)
        self.media_devices.audioOutputsChanged.connect(
            self._handle_audio_output_changed
        )

        has_paths = hasattr(self, "music_library_paths") and self.music_library_paths
        cache_path = (
            self.library_manager.get_cache_path(self.music_library_paths)
            if has_paths
            else None
        )

        if has_paths or (cache_path and cache_path.exists()):
            self.is_processing_library = True
        else:
            self.is_processing_library = False

        self.charts_tab_index = -1
        self.search_tab_index = -1
        self.ui_manager.populate_all_tabs()

        if has_paths:
            QTimer.singleShot(
                100,
                lambda: self.start_library_processing(
                    from_cache=True, user_initiated=False, is_startup=True
                ),
            )
        self.start_background_playlist_indexing()

        QTimer.singleShot(0, self._sync_search_bar_width)
        QTimer.singleShot(2000, self.start_library_change_detection)
        if getattr(self, "check_updates_at_startup", True):
            QTimer.singleShot(3000, self.check_for_updates)

    def check_for_updates(self):
        """Starts a background thread to check for new versions on GitHub."""
        self.update_checker = UpdateCheckerThread(current_version = APP_VERSION)
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.finished.connect(self.update_checker.deleteLater)
        self.update_checker.start()

    def on_update_available(self, latest_version, release_url):
        """Triggered when a new version is found on GitHub."""
        self.app_update_available = True
        self.app_update_version = latest_version
        self.app_update_url = release_url

        self._update_pending_updates_widget()

    def load_qt_translations(self, lang_code):
        """Loads and installs Qt standard translations for base interactions."""
        if self.qt_translator:
            QApplication.instance().removeTranslator(self.qt_translator)

        self.qt_translator = QTranslator(self)
        translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)

        if self.qt_translator.load(f"qt_{lang_code}", translations_path):
            QApplication.instance().installTranslator(self.qt_translator)
        else:
            print(
                f"Warning: Could not load Qt base translations for language '{lang_code}' from {translations_path}"
            )

    def _update_favorite_icons(self):
        """Creates or updates favorite icons based on current settings."""
        self.favorite_icon = QIcon(
            create_svg_icon(
                f"assets/control/{self.favorite_icon_name}.svg",
                theme.COLORS["PRIMARY"],
                QSize(24, 24),
            )
        )
        self.favorite_filled_icon = QIcon(
            create_svg_icon(
                f"assets/control/{self.favorite_icon_name}_filled.svg",
                theme.COLORS["ACCENT"],
                QSize(24, 24),
            )
        )

    def _update_pending_updates_widget(self):
        """
        Updates the state and visibility of the pending updates notification widget.

        Evaluates the current state of pending metadata changes, external file modifications,
        and available application updates. Based on the highest priority event, it configures
        the widget's title, message text, and button visibility (e.g., showing the 'Later'
        button for app updates). It also syncs the tooltip of the toggle button in the sidebar.
        """
        count = self.pending_metadata_items_count
        ext_count = getattr(self, "pending_external_changes_count", 0)

        msg = ""
        show_button = False
        has_file_changes = False
        show_later_btn = False
        is_app_update = False
        app_update_link = ""

        popup_title = translate("Library update required")
        tooltip_text = translate("Library update required")

        if count > 0:
            msg = translate(
                "You have changed metadata for {count} item(s). Refresh the library to apply changes.",
                count = count,
            )
            show_button = True

        elif ext_count > 0:
            msg = translate(
                "Detected {count} changes in your music folders (files added, removed or edited externally). Refresh required.",
                count = ext_count
            )
            show_button = True
            has_file_changes = True

        elif self.pending_settings_rescan:
            msg = translate(
                "You have changed settings or files changed externally. Refresh the library to apply changes."
            )
            show_button = True

        elif getattr(self, "app_update_available", False) and not self.update_ignored_this_session:
            msg = translate(
                "A new Vinyller version out now! Check the {version} release page on GitHub for the full changelog, including bug fixes and new features.",
                version = self.app_update_version
            )
            show_button = True
            has_file_changes = False
            show_later_btn = True

            is_app_update = True
            app_update_link = self.app_update_url

            popup_title = translate("A new version is available")
            tooltip_text = translate("A new version is available")

        if show_button:
            self.pending_updates_widget.set_title(popup_title)
            self.pending_updates_widget.set_message(msg)
            self.pending_updates_widget.set_changes_button_visible(has_file_changes)
            self.pending_updates_widget.set_later_button_visible(show_later_btn)

            self.pending_updates_widget.set_app_update_mode(is_app_update, app_update_link)

            set_custom_tooltip(self.notification_toggle_button, title = tooltip_text)

            self.notification_toggle_button.show()
        else:
            self.notification_toggle_button.hide()
            if self.notification_toggle_button.isChecked():
                self.notification_toggle_button.setChecked(False)
            else:
                self.pending_updates_widget.hide()

    def _on_update_postponed(self):
        """
        Callback invoked when the user clicks the 'Later' button on the update notification.

        Sets a session flag to ignore the application update prompt until the next
        application launch, and hides the notification UI elements.
        """
        self.update_ignored_this_session = True

        if hasattr(self, "notification_toggle_button") and self.notification_toggle_button.isChecked():
            self.notification_toggle_button.setChecked(False)

        self._update_pending_updates_widget()

    def _position_pending_updates_widget(self):
        """Positions the notification widget relative to the button (Global coords)."""
        if not hasattr(self, "pending_updates_widget") or not hasattr(
                self, "notification_toggle_button"
        ):
            return

        target_widget = self.notification_toggle_button
        global_button_pos = self.notification_toggle_button.mapToGlobal(QPoint(0, 0))
        global_pos = target_widget.mapToGlobal(QPoint(0, target_widget.height()))

        x = global_pos.x() + self.nav_bar.width()

        y = global_pos.y() - self.notification_toggle_button.height() - SHADOW_SHIFT_Y

        self.pending_updates_widget.move(x, y)

    def _on_pending_updates_hidden(self):
        """Callback invoked when the PendingUpdatesPopup is hidden (either automatically or via button click)."""
        if hasattr(self, "notification_toggle_button") and self.notification_toggle_button.isChecked():
            self.notification_toggle_button.setChecked(False)

    def _process_pending_updates(self):
        """Starts processing pending metadata updates, library changes, or app updates."""

        has_library_updates = (
                bool(self.pending_metadata_updates)
                or getattr(self, "pending_external_changes_count", 0) > 0
                or getattr(self, "pending_settings_rescan", False)
        )

        if has_library_updates:
            print("Processing pending library updates...")

            current_tracks = self.data_manager.all_tracks
            tracks_to_keep = []

            changed_paths_only = [item[1] for item in self.pending_added_modified_paths]

            paths_to_remove = set(self.pending_removed_paths) | set(changed_paths_only)

            for track in current_tracks:
                p = track.get("real_path", track.get("path"))
                p_norm = os.path.normpath(p)

                if p_norm not in paths_to_remove:
                    tracks_to_keep.append(track)

            paths_to_scan = list(changed_paths_only)

            self.pending_metadata_updates.clear()
            self.pending_metadata_items_count = 0
            self.pending_settings_rescan = False
            self.pending_external_changes_count = 0
            self.pending_added_modified_paths = []
            self.pending_removed_paths = []

            self.library_manager.clear_pending_updates()
            self._update_pending_updates_widget()

            self.action_handler.start_library_processing_with_restore(
                from_cache = False,
                user_initiated = True,
                tracks_to_reprocess = tracks_to_keep,
                partial_scan_paths = paths_to_scan
            )
            return

        if getattr(self, "app_update_available", False):
            QDesktopServices.openUrl(QUrl(self.app_update_url))

            self.app_update_available = False
            self._update_pending_updates_widget()
            self.pending_updates_widget.hide()
            return

    def _handle_deferred_rescan_request(self):
        """Called when 'Later' is selected in settings, sets a flag to rescan on next start."""
        self.pending_settings_rescan = True

        self.save_current_settings()

        self._update_pending_updates_widget()

    def _update_charts_button_visibility(self):
        """Shows or hides the 'Charts' button based on settings and handles active tab switching if hidden."""
        if not hasattr(self, "charts_button") or not self.charts_button:
            return

        is_visible = self.collect_statistics
        self.charts_button.setVisible(is_visible)

        if not is_visible and self.charts_button.isChecked():
            self.charts_button.setChecked(False)

            try:
                charts_idx = self.nav_button_icon_names.index("charts")
                if self.main_stack.currentIndex() == charts_idx:
                    self.main_stack.setCurrentIndex(0)
                    if self.nav_buttons:
                        self.nav_buttons[0].setChecked(True)
                    self.ui_manager.update_nav_button_icons()
            except (ValueError, AttributeError):
                pass

    def restart_app(self):
        """Restarts the entire application."""
        self.close()
        QProcess.startDetached(sys.executable, sys.argv)

    def _handle_audio_output_changed(self):
        """Handles audio output device changes and reconnects players to the new device."""
        new_default_device = QMediaDevices.defaultAudioOutput()
        self.player.audio_output.setDevice(new_default_device)
        self.player.crackle_audio_output.setDevice(new_default_device)
        self.player.scratch_forward_audio_output.setDevice(new_default_device)
        self.player.scratch_backward_audio_output.setDevice(new_default_device)

    def connect_signals(self):
        """Connects signals across various UI components and handlers."""
        self.ui_manager.alphaJumpRequested.connect(self._show_alpha_jump_popup)

        self.global_search_bar.textChanged.connect(
            self.global_search_debounce_timer.start
        )
        self.global_search_debounce_timer.timeout.connect(
            self.on_global_search_query_changed
        )

        self.vinyl_widget.controlPanelToggled.connect(self.toggle_vinyl_control_panel)
        self.control_panel.hide_panel_clicked.connect(self.toggle_vinyl_control_panel)

        self.vinyl_widget.play_pause_clicked.connect(self.player_controller.toggle_play_pause)
        self.vinyl_widget.next_clicked.connect(self.player.next)
        self.vinyl_widget.prev_clicked.connect(self.player.previous)

        self.player.missingTrackDetected.connect(self.handle_missing_track)

        self.player.player.playbackStateChanged.connect(self._update_vinyl_play_state)

        self.main_view_stack.currentChanged.connect(self._on_main_view_changed)

        self.settings_button.clicked.connect(self.open_settings)
        self.vinyl_toggle_button.clicked.connect(self.toggle_vinyl_widget)
        self.main_stack.currentChanged.connect(self.ui_manager.on_main_stack_changed)
        self.nav_buttons_group.buttonClicked.connect(
            self.ui_manager.on_nav_button_clicked
        )
        self.reload_timer.timeout.connect(self._update_reload_animation)
        self.vinyl_widget.backClicked.connect(self.return_from_vinyl_widget)
        self.notification_toggle_button.toggled.connect(
            self._toggle_pending_updates_widget
        )

        self.vinyl_widget.scrubbingStarted.connect(
            self.player_controller.handle_scrubbing_started
        )
        self.vinyl_widget.positionScrubbed.connect(
            self.player_controller.handle_position_scrubbed
        )
        self.vinyl_widget.scrubbingFinished.connect(
            self.player_controller.handle_scrubbing_finished
        )

        self.control_panel.play_pause_clicked.connect(
            self.player_controller.toggle_play_pause
        )
        self.control_panel.next_clicked.connect(self.player.next)
        self.control_panel.prev_clicked.connect(self.player.previous)
        self.control_panel.shuffle_clicked.connect(
            self.player_controller.toggle_shuffle
        )
        self.control_panel.repeat_clicked.connect(
            self.player_controller.cycle_repeat_mode
        )
        self.control_panel.position_seeked.connect(self.player_controller.seek_position)
        self.control_panel.volume_changed.connect(self.set_volume)
        self.control_panel.volume_toggle_clicked.connect(self.toggle_mute)
        self.control_panel.queue_toggle_clicked.connect(self.toggle_queue_view)
        self.control_panel.vinyl_queue_toggle_clicked.connect(
            self.toggle_vinyl_queue_view
        )
        self.control_panel.favorite_clicked.connect(
            self.action_handler.toggle_current_track_favorite
        )
        self.control_panel.artist_clicked.connect(self.handle_artist_click)
        self.control_panel.album_clicked.connect(self.handle_album_click)
        self.control_panel.genre_clicked.connect(self.handle_genre_click)
        self.control_panel.cover_zoom_requested.connect(
            lambda p: self.ui_manager.components.show_cover_viewer(
                p, use_global_context=True
            )
        )
        self.control_panel.year_clicked.connect(self.handle_year_click)
        self.player.player.playbackStateChanged.connect(
            self.player_controller.update_player_state
        )
        self.player.player.playbackStateChanged.connect(
            self._handle_playback_state_for_animation
        )
        self.player.player.playbackStateChanged.connect(
            self.action_handler._handle_playback_state_changed
        )
        self.player.currentTrackChanged.connect(
            self.action_handler._handle_track_changed
        )
        self.player.player.playbackStateChanged.connect(
            self.on_playback_state_changed_for_stats
        )
        self.player.currentTrackChanged.connect(self.on_track_changed_for_stats)
        self.player.player.playbackStateChanged.connect(self._handle_stats_timers_state)
        self.player.player.positionChanged.connect(
            self.player_controller.update_position
        )
        self.player.player.durationChanged.connect(
            self.player_controller.update_duration
        )
        self.player.currentTrackChanged.connect(
            self.player_controller.update_track_info
        )
        self.player.errorOccurred.connect(self.handle_player_error)
        self.player.queueChanged.connect(self.player_controller.on_queue_changed)

        self.right_panel.queuePopulated.connect(
            self.ui_manager.update_all_track_widgets
        )
        self.right_panel.itemDoubleClicked.connect(
            self.player_controller.play_from_queue_double_click
        )
        self.right_panel.playActionRequested.connect(
            self.player_controller.play_from_queue_action
        )
        self.right_panel.tracksDropped.connect(
            self.action_handler.handle_tracks_dropped
        )
        self.right_panel.orderChanged.connect(
            self.action_handler.handle_queue_reordered
        )
        self.right_panel.clearQueueRequested.connect(self.action_handler.clear_queue)
        self.right_panel.saveQueueRequested.connect(self.action_handler.save_playlist)
        self.right_panel.createMixtapeRequested.connect(
            lambda: self.action_handler.create_mixtape_from_data(
                self.player.get_current_queue(),
                getattr(self, "current_queue_name", "Mixtape")
            )
        )
        self.right_panel.shakeQueueRequested.connect(
            self.action_handler.handle_shake_queue
        )
        self.right_panel.deletePlaylistRequested.connect(
            self.action_handler.delete_playlist
        )
        self.right_panel.toggleCompactModeRequested.connect(self.toggle_compact_queue)
        self.right_panel.toggleShowCoverRequested.connect(self.toggle_queue_show_cover)
        self.right_panel.toggleHideArtistRequested.connect(
            self.toggle_hide_artist_in_compact_queue
        )
        self.right_panel.toggleAutoplayOnQueueRequested.connect(
            self.toggle_autoplay_on_queue
        )
        self.right_panel.artistClicked.connect(self.handle_artist_click)
        self.right_panel.queue_widget.trackContextMenuRequested.connect(
            lambda track, pos, ctx: self.action_handler.show_context_menu(
                track, pos, is_queue_item=True, context=ctx
            )
        )

        self.control_panel.lyrics_toggle_clicked.connect(self._on_lyrics_toggled)
        self.control_panel.always_on_top_toggled.connect(self.toggle_always_on_top)
        self.control_panel.mini_requested.connect(self.enter_mini_mode)

        self.right_panel.lyricsCloseRequested.connect(self._on_lyrics_closed)
        self.right_panel.vinylLyricsCloseRequested.connect(self._on_vinyl_lyrics_closed)
        self.right_panel.lyricsClicked.connect(self.action_handler.show_lyrics)

        self.queueViewOptionsChanged.connect(self.ui_manager.apply_queue_view_options)

        self.player.player.playbackStateChanged.connect(self._sync_mini_playback)
        self.player.queueChanged.connect(self._sync_mini_queue)
        self.player.currentTrackChanged.connect(self._sync_mini_track_index)

        self.artists_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.artists_scroll.verticalScrollBar(),
                self.ui_manager.load_more_artists,
            )
        )
        self.albums_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.albums_scroll.verticalScrollBar(),
                self.ui_manager.load_more_albums,
            )
        )
        self.songs_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.songs_scroll.verticalScrollBar(),
                self.ui_manager.load_more_songs,
            )
        )
        self.genres_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.genres_scroll.verticalScrollBar(),
                self.ui_manager.load_more_genres,
            )
        )

        self.composers_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.composers_scroll.verticalScrollBar(),
                self.ui_manager.load_more_composers,
            )
        )

        self.search_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.search_scroll.verticalScrollBar(),
                self.ui_manager.search_ui_manager.load_more_search_results,
            )
        )

        self.history_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.history_scroll.verticalScrollBar(),
                self.ui_manager.load_more_history,
            )
        )

        self.catalog_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.catalog_scroll.verticalScrollBar(),
                self.ui_manager.load_more_catalog,
            )
        )

        self.playlists_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self.ui_manager.check_scroll_and_load(
                v,
                self.playlists_scroll.verticalScrollBar(),
                self.ui_manager.load_more_playlists,
            )
        )

        self.search_mode_button.menu().triggered.connect(
            self.set_search_mode_from_action
        )
        self.search_view_button.menu().triggered.connect(self.set_search_view_mode)

        self.artist_sort_button.menu().triggered.connect(self.set_artist_sort_mode)
        self.artist_view_button.menu().triggered.connect(self.set_artist_view_mode)
        self.album_sort_button.menu().triggered.connect(self.set_album_sort_mode)
        self.album_view_button.menu().triggered.connect(self.set_album_view_mode)
        self.song_sort_button.menu().triggered.connect(self.set_song_sort_mode)
        self.genre_sort_button.menu().triggered.connect(self.set_genre_sort_mode)
        self.genre_view_button.menu().triggered.connect(self.set_genre_view_mode)
        self.playlist_sort_button.menu().triggered.connect(self.set_playlist_sort_mode)
        self.playlist_view_button.menu().triggered.connect(self.set_playlist_view_mode)
        self.chart_view_button.menu().triggered.connect(self.set_chart_view_mode)
        self.catalog_sort_button.menu().triggered.connect(self.set_catalog_sort_mode)
        self.catalog_view_button.menu().triggered.connect(self.set_catalog_view_mode)
        self.composer_sort_button.menu().triggered.connect(self.set_composer_sort_mode)
        self.composer_view_button.menu().triggered.connect(self.set_composer_view_mode)

        self.now_playing_animation_timer.timeout.connect(
            self._update_now_playing_animation
        )

    def _update_vinyl_play_state(self, state):
        """Updates the icon in the mini-player based on the playback state."""
        if self.vinyl_widget:
            self.vinyl_widget.update_play_state(state == QMediaPlayer.PlaybackState.PlayingState)

    def _on_main_view_changed(self, index):
        """
        Checks if the current view is NOT the vinyl widget.
        If so, ensures the control panel is restored.
        """
        current_widget = self.main_view_stack.widget(index)
        if current_widget != self.vinyl_widget:
            self._restore_controls_defaults()

    def _restore_controls_defaults(self):
        """
        Restores the control panel visibility when exiting Vinyl/Mini-player mode.
        """
        if not self.control_panel.isVisible():
            self.control_panel.show()

        self._set_adjusted_min_size(392, 592)

        if self.vinyl_widget:
            self.vinyl_widget.set_mini_mode(False)

        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().activate()

    def toggle_vinyl_control_panel(self):
        """
        Toggles the visibility of the control panel in Vinyl mode.
        Updates the main layout and forces a geometry recalculation for VinylWidget.
        """
        should_show = not self.control_panel.isVisible()
        self.control_panel.setVisible(should_show)

        if self.right_panel:
            self.right_panel.update_vinyl_margins(should_show)

        if self.vinyl_widget:
            self.vinyl_widget.set_mini_mode(not should_show)

        if should_show:
            self._set_adjusted_min_size(392, 592)
        else:
            self._set_adjusted_min_size(392, 392)
            self.resize(self.width(), min(self.width(), self.minimumHeight()))

        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().activate()

        QTimer.singleShot(10, lambda: self.vinyl_widget.resizeEvent(None))

    def on_global_search_query_changed(self):
        """
        Slot for processing changes in global search text.
        Executes search across the library based on the query.
        """
        text = self.global_search_bar.text().strip()

        if hasattr(self, "search_stack") and self.search_stack.count() > 0:
            if self.search_stack.currentIndex() > 0:
                self.search_stack.setCurrentIndex(0)

        if (
            hasattr(self, "search_header_stack")
            and self.search_header_stack.count() > 0
        ):
            if self.search_header_stack.currentIndex() > 0:
                self.search_header_stack.setCurrentIndex(0)

        if not text:
            if self.main_stack.currentIndex() == self.global_search_page_index:
                self.main_stack.setCurrentIndex(self.previous_stack_index)

                if 0 <= self.previous_stack_index < len(self.nav_buttons):
                    self.nav_buttons[self.previous_stack_index].setChecked(True)

                self.ui_manager.update_nav_button_icons()
                self.header_stack.setCurrentIndex(self.previous_stack_index)
            return

        if self.main_stack.currentIndex() != self.global_search_page_index:
            current_idx = self.main_stack.currentIndex()
            if current_idx != self.global_search_page_index:
                self.previous_stack_index = current_idx

            self.main_stack.setCurrentIndex(self.global_search_page_index)

            for btn in self.nav_buttons:
                btn.setChecked(False)
            self.ui_manager.update_nav_button_icons()

        self.player_controller.perform_search(text)

    def _handle_stats_timers_state(self, state):
        """Starts or stops the statistics timers depending on the player state."""
        if not self.collect_statistics:
            return

        if state == QMediaPlayer.PlaybackState.PlayingState:
            if not self.stats_save_trigger_timer.isActive():
                self.stats_save_trigger_timer.start()
            if not self.stats_poll_timer.isActive():
                self.stats_poll_timer.start()
        else:
            if self.stats_save_trigger_timer.isActive():
                self.stats_save_trigger_timer.stop()
            if self.stats_poll_timer.isActive():
                self.stats_poll_timer.stop()

    def _sync_mini_position(self, position):
        """Synchronizes the player position with the Mini Vinny."""
        if getattr(self, "mini_window", None):
            self.mini_window.set_position(position)

    def _sync_mini_duration(self, duration):
        """Synchronizes the player duration with the Mini Vinny."""
        if getattr(self, "mini_window", None):
            self.mini_window.set_duration(duration)

    def _sync_mini_playback(self, state, *args, **kwargs):
        """Synchronizes the playback state with the Mini Vinny."""
        if getattr(self, "mini_window", None):
            is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
            self.mini_window.set_playback_state(is_playing)

    def _sync_mini_queue(self, *args, **kwargs):
        """Synchronizes the queue data with the Mini Vinny."""
        if getattr(self, "mini_window", None):
            self.mini_window.set_queue(
                self.player.get_current_queue(),
                self.player.get_current_index()
            )

    def _sync_mini_track_index(self, *args, **kwargs):
        """Synchronizes the current track index with the Mini Vinny."""
        if getattr(self, "mini_window", None):
            self.mini_window.set_current_index(self.player.get_current_index())

    def _update_now_playing_animation(self):
        """Updates the animation frames for the currently playing item."""
        self.now_playing_animation_frame = (self.now_playing_animation_frame + 1) % 8

        delegate = self.right_panel.queue_widget.itemDelegate()
        if isinstance(delegate, QueueDelegate):
            delegate.set_animation_frame(self.now_playing_animation_frame)

        vinyl_delegate = self.right_panel.vinyl_queue_widget.itemDelegate()
        if isinstance(vinyl_delegate, QueueDelegate):
            vinyl_delegate.set_animation_frame(self.now_playing_animation_frame)

        if getattr(self, "mini_window", None):
            self.mini_window.set_animation_frame(self.now_playing_animation_frame)

        if self.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState:
            self.right_panel.queue_widget.viewport().update()
            self.right_panel.vinyl_queue_widget.viewport().update()

            if hasattr(self, "my_wave_btn") and self.my_wave_btn:
                if self.current_queue_name == translate("My Wave"):
                    frame_pix = self.ui_manager.components.my_wave_animation_frames[
                        self.now_playing_animation_frame
                    ]
                    self.my_wave_btn.setCustomIcon(frame_pix)
                else:
                    self.my_wave_btn.setCustomIcon(self.my_wave_static_pixmap)

    def _handle_playback_state_for_animation(self, state):
        """Handles state changes to control the now playing animation timer."""

        if hasattr(self, "mac_media_manager"):
            is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
            current_idx = self.player.get_current_index()
            queue = self.player.get_current_queue()
            if 0 <= current_idx < len(queue):
                current_time = self.player.player.position()
                self.mac_media_manager.update_now_playing_info(queue[current_idx], is_playing, current_time)

        if state == QMediaPlayer.PlaybackState.PlayingState:
            if not self.now_playing_animation_timer.isActive():
                self.now_playing_animation_timer.start()
        else:
            if self.now_playing_animation_timer.isActive():
                self.now_playing_animation_timer.stop()

            delegate = self.right_panel.queue_widget.itemDelegate()
            if isinstance(delegate, QueueDelegate):
                delegate.set_animation_frame(0)

            vinyl_delegate = self.right_panel.vinyl_queue_widget.itemDelegate()
            if isinstance(vinyl_delegate, QueueDelegate):
                vinyl_delegate.set_animation_frame(0)

            if hasattr(self, "my_wave_btn") and self.my_wave_btn:
                self.my_wave_btn.setCustomIcon(self.my_wave_static_pixmap)

            self.right_panel.queue_widget.viewport().update()
            self.right_panel.vinyl_queue_widget.viewport().update()

    def handle_artist_click(self, artist_data):
        """Handles navigation when an artist is clicked."""
        if self.vinyl_toggle_button.isChecked():
            self.return_from_vinyl_widget()
        self.ui_manager.navigate_to_artist(artist_data)

    def handle_album_click(self, album_data):
        """Handles navigation when an album is clicked."""
        if self.vinyl_toggle_button.isChecked():
            self.return_from_vinyl_widget()
        self.ui_manager.navigate_to_album(album_data)

    def handle_year_click(self, year):
        """Handles navigation when a release year is clicked."""
        if self.vinyl_toggle_button.isChecked():
            self.return_from_vinyl_widget()
        self.ui_manager.navigate_to_year(year)

    def handle_genre_click(self, genre_name):
        """Handles navigation when a genre is clicked."""
        if self.vinyl_toggle_button.isChecked():
            self.return_from_vinyl_widget()
        self.ui_manager.navigate_to_genre(genre_name)

    def handle_composer_click(self, composer_name):
        """Handler for clicking on a composer name."""
        if self.vinyl_toggle_button.isChecked():
            self.return_from_vinyl_widget()

        self.ui_manager.navigate_to_composer(composer_name)

    def select_folder_and_scan(self):
        """Opens a dialog to select a folder and adds it to the library paths."""
        directory = QFileDialog.getExistingDirectory(
            self, translate("Select music folder")
        )
        if directory:
            if directory in self.music_library_paths:
                print("This folder is already in the library.")
                return

            self.music_library_paths.append(directory)
            self.save_current_settings()
            self.start_library_processing(from_cache=False, user_initiated=True)

    def open_encyclopedia_manager(self, target_key=None, target_type=None):
        """Opens the encyclopedia manager dialog window."""
        if (
            not hasattr(self, "encyclopedia_manager_window")
            or self.encyclopedia_manager_window is None
        ):
            self.encyclopedia_manager_window = EncyclopediaWindow(self)
            self.encyclopedia_manager_window.setAttribute(
                Qt.WidgetAttribute.WA_DeleteOnClose
            )
            self.encyclopedia_manager_window.destroyed.connect(
                lambda: setattr(self, "encyclopedia_manager_window", None)
            )

        self.encyclopedia_manager_window.bring_to_front()

        if target_key is not None and target_type is not None:
            QTimer.singleShot(
                100,
                lambda: self.encyclopedia_manager_window.navigate_to_item(
                    target_key, target_type
                ),
            )

    def _get_core_settings_dict(self) -> dict:
        """
        Generates and returns a dictionary of the core configurable user settings.

        This method acts as the single source of truth for the application's configuration state,
        preventing code duplication when passing settings to the UI or saving them to disk.
        It strictly contains cross-session preferences and UI modes, excluding transient
        window geometries or temporary application states.

        Returns:
            dict: A dictionary containing key-value pairs of all core settings.
        """
        return {
            "musicLibraryPaths": self.music_library_paths,
            "nav_tab_order": getattr(self, "nav_tab_order", []),
            "theme": self.current_theme,
            "accent_color": self.current_accent,
            "artist_source_tag": self.artist_source_tag,
            "show_separators": getattr(self, "show_separators", True),
            "ignore_articles": getattr(self, "ignore_articles", True),
            "show_favorites_separators": getattr(self, "show_favorites_separators", False),
            "ignore_genre_case": getattr(self, "ignore_genre_case", True),
            "treat_folders_as_unique": getattr(self, "treat_folders_as_unique", False),
            "allow_drag_export": getattr(self, "allow_drag_export", False),
            "check_updates_at_startup": getattr(self, "check_updates_at_startup", True),
            "remember_queue_mode": getattr(self, "remember_queue_mode", 3),
            "playback_history_mode": getattr(self, "playback_history_mode", 2),
            "history_store_unique_only": getattr(self, "history_store_unique_only", True),
            "remember_last_view": getattr(self, "remember_last_view", False),
            "remember_window_size": getattr(self, "remember_window_size", True),
            "stylize_vinyl_covers": getattr(self, "stylize_vinyl_covers", False),
            "warm_sound": getattr(self, "warm_sound", False),
            "scratch_sound": getattr(self, "scratch_sound", False),
            "mini_opacity": getattr(self, "mini_opacity", True),
            "show_random_suggestions": getattr(self, "show_random_suggestions", True),
            "queueCompactMode": getattr(self, "queue_compact_mode", False),
            "queueCompactHideArtist": getattr(self, "queue_compact_hide_artist", False),
            "queueShowCover": getattr(self, "queue_show_cover", True),
            "collect_statistics": getattr(self, "collect_statistics", True),
            "language": getattr(self, "current_language", "en"),
            "favorite_icon_name": getattr(self, "favorite_icon_name", "favorite_heart"),
            "autoplay_on_queue": getattr(self, "autoplay_on_queue", False),
            "view_modes": {
                "artists": getattr(self, "artist_view_mode", ViewMode.GRID),
                "artist_albums": getattr(self, "artist_album_view_mode", ViewMode.GRID),
                "albums": getattr(self, "album_view_mode", ViewMode.GRID),
                "genres": getattr(self, "genre_view_mode", ViewMode.GRID),
                "catalog": getattr(self, "catalog_view_mode", ViewMode.TILE_SMALL),
                "playlists": getattr(self, "playlist_view_mode", ViewMode.TILE_BIG),
                "favorites": getattr(self, "favorite_view_mode", ViewMode.GRID),
                "composers": getattr(self, "composer_view_mode", ViewMode.GRID),
                "composer_albums": getattr(self, "composer_album_view_mode", ViewMode.GRID),

                "favorite_playlists": getattr(self, "favorite_playlists_view_mode", ViewMode.GRID),
                "favorite_albums": getattr(self, "favorite_albums_view_mode", ViewMode.GRID),
                "favorite_artists": getattr(self, "favorite_artists_view_mode", ViewMode.GRID),
                "favorite_composers": getattr(self, "favorite_composers_view_mode", ViewMode.GRID),
                "favorite_genres": getattr(self, "favorite_genres_view_mode", ViewMode.GRID),
                "favorite_folders": getattr(self, "favorite_folders_view_mode", ViewMode.GRID),
                "favorite_artist_albums": getattr(self, "favorite_artist_album_view_mode", ViewMode.GRID),
                "favorite_composer_albums": getattr(self, "favorite_composer_album_view_mode", ViewMode.GRID),
                "favorite_genre_albums": getattr(self, "favorite_genre_album_view_mode", ViewMode.GRID),

                "charts": getattr(self, "charts_view_mode", ViewMode.GRID),
                "charts_artist_albums": getattr(self, "charts_artist_album_view_mode", ViewMode.GRID),
                "charts_composer_albums": getattr(self, "charts_composer_album_view_mode", ViewMode.GRID),
                "charts_genre_albums": getattr(self, "charts_genre_album_view_mode", ViewMode.GRID),
            },
            "sort_modes": {
                "artists": getattr(self, "artist_sort_mode", SortMode.ALPHA_ASC),
                "albums": getattr(self, "album_sort_mode", SortMode.YEAR_DESC),
                "genres": getattr(self, "genre_sort_mode", SortMode.ALPHA_ASC),
                "artist_albums": getattr(self, "artist_album_sort_mode", SortMode.YEAR_DESC),
                "songs": getattr(self, "song_sort_mode", SortMode.ARTIST_ASC),
                "playlists": getattr(self, "playlist_sort_mode", SortMode.ALPHA_ASC),
                "catalog": getattr(self, "catalog_sort_mode", SortMode.ALPHA_ASC),
                "composers": getattr(self, "composer_sort_mode", SortMode.ALPHA_ASC),
                "composer_albums": getattr(self, "composer_album_sort_mode", SortMode.YEAR_DESC),

                "charts_albums": getattr(self, "charts_album_sort_mode", SortMode.DATE_ADDED_DESC),
                "charts_artists": getattr(self, "charts_artist_sort_mode", SortMode.DATE_ADDED_DESC),
                "charts_composers": getattr(self, "charts_composer_sort_mode", SortMode.DATE_ADDED_DESC),
                "charts_genres": getattr(self, "charts_genre_sort_mode", SortMode.DATE_ADDED_DESC),
                "charts_artist_albums": getattr(self, "charts_artist_album_sort_mode", SortMode.YEAR_DESC),
                "charts_composer_albums": getattr(self, "charts_composer_album_sort_mode", SortMode.YEAR_DESC),
                "charts_genre_albums": getattr(self, "charts_genre_album_sort_mode", SortMode.YEAR_DESC),

                "favorite_tracks": getattr(self, "favorite_tracks_sort_mode", SortMode.DATE_ADDED_DESC),
                "favorite_playlists": getattr(self, "favorite_playlists_sort_mode", SortMode.DATE_ADDED_DESC),
                "favorite_albums": getattr(self, "favorite_albums_sort_mode", SortMode.DATE_ADDED_DESC),
                "favorite_artists": getattr(self, "favorite_artists_sort_mode", SortMode.DATE_ADDED_DESC),
                "favorite_composers": getattr(self, "favorite_composers_sort_mode", SortMode.DATE_ADDED_DESC),
                "favorite_genres": getattr(self, "favorite_genres_sort_mode", SortMode.DATE_ADDED_DESC),
                "favorite_folders": getattr(self, "favorite_folders_sort_mode", SortMode.DATE_ADDED_DESC),
                "favorite_artist_albums": getattr(self, "favorite_artist_album_sort_mode", SortMode.YEAR_DESC),
                "favorite_composer_albums": getattr(self, "favorite_composer_album_sort_mode", SortMode.YEAR_DESC),
                "favorite_genre_albums": getattr(self, "favorite_genre_album_sort_mode", SortMode.YEAR_DESC),

            },
        }

    def open_settings(self, tab_index = 0):
        """
        Opens the settings window dialog.

        Fetches the core settings state, initializes the SettingsWindow, and handles
        custom signals emitted by the dialog (such as rescan, reset, or theme changes).

        Args:
            tab_index (int, optional): The index of the tab to be displayed initially. Defaults to 0.
        """
        current_settings = self._get_core_settings_dict()

        dialog = SettingsWindow(current_settings, self, start_tab_index = tab_index)
        dialog.settings_were_reset = False
        RESCAN_CODE = 2

        def handle_rescan_request():
            """
            Handles the signal from the settings dialog requesting a library rescan.
            Closes the dialog with a specific return code to trigger the rescan.
            """
            dialog.done(RESCAN_CODE)

        dialog.rescan_requested.connect(handle_rescan_request)
        dialog.reset_requested.connect(lambda: self.handle_settings_reset(dialog))
        dialog.clear_stats_requested.connect(lambda: self._handle_clear_stats_request(dialog))
        dialog.theme_change_requires_restart.connect(self._handle_theme_change_request)
        dialog.deferred_rescan_requested.connect(self._handle_deferred_rescan_request)

        result = dialog.exec()

        if dialog.settings_were_reset:
            return

        if result == RESCAN_CODE:
            new_settings = dialog.get_settings()
            new_paths = new_settings.get("musicLibraryPaths", [])
            self.music_library_paths = new_paths
            self.save_current_settings()
            print("Library update initiated with new paths...")
            self.start_library_processing(from_cache = False, user_initiated = True)

        elif result == 1:
            new_settings = dialog.get_settings()
            self.apply_new_settings(new_settings, current_settings)

    def save_current_settings(self):
        """
        Gathers both the core user settings and the transient window/application state,
        then writes them to the JSON settings file via the LibraryManager.

        This method computes current geometries, splitter sizes, and active volumes
        before appending them to the core settings dictionary.
        """
        current_geometry = None
        if self.remember_window_size:
            if self.vinyl_toggle_button.isChecked() and self.original_geometry:
                current_geometry = self.original_geometry.toHex().data().decode()
            else:
                current_geometry = self.saveGeometry().toHex().data().decode()

        if self.vinyl_toggle_button.isChecked():
            queue_is_visible = self.queue_visible_before_vinyl
        else:
            queue_is_visible = self.right_panel.isVisible()

        splitter_sizes = self.splitter.sizes() if self.remember_window_size else None

        if self.vinyl_toggle_button.isChecked():
            current_vinyl_w = self.width()
            current_vinyl_h = self.height()
            self.vinyl_window_geometry = self.saveGeometry().toHex().data().decode()
        else:
            current_vinyl_w = self.saved_vinyl_size[0]
            current_vinyl_h = self.saved_vinyl_size[1]

        final_vinyl_size = [current_vinyl_w, current_vinyl_h]

        if getattr(self, "mini_window", None) and self.mini_window.isVisible():
            self.mini_geometry = self.mini_window.saveGeometry().toHex().data().decode()
            self.mini_pos = self.mini_window.pos()

        mini_pos_list = [self.mini_pos.x(), self.mini_pos.y()] if getattr(self, "mini_pos", None) else None

        settings = self._get_core_settings_dict()

        settings.update({
            "dismissed_album_merge_warning": getattr(self, "dismissed_album_merge_warning", False),
            "dismissed_add_folder_hint": getattr(self, "dismissed_add_folder_hint", False),
            "volume": self.control_panel.volume_slider.value(),
            "shuffle": self.player.is_shuffled(),
            "repeatMode": self.player.get_repeat_mode().value,
            "queueVisible": queue_is_visible,
            "lastRightPanelWidth": self.last_right_panel_width,
            "windowGeometry": current_geometry,
            "vinyl_window_size": final_vinyl_size,
            "vinyl_window_geometry": getattr(self, "vinyl_window_geometry", None),
            "mini_geometry": getattr(self, "mini_geometry", None),
            "mini_pos": mini_pos_list,
            "splitterSizes": splitter_sizes,
            "charts_period": getattr(self, "charts_period", ChartsPeriod.MONTHLY),
            "pending_settings_rescan": getattr(self, "pending_settings_rescan", False),
            "encyclopedia_collapsed": getattr(self, "encyclopedia_collapsed", False),
        })

        self.library_manager.save_settings(settings)

    def apply_new_settings(self, new_settings, old_settings):
        """
        Applies changes generated by the SettingsWindow.

        Triggers library rescans, restarts, or UI updates depending on the severity
        and impact of the modified settings. Dynamic mappings are used to update simple flags.

        Args:
            new_settings (dict): The dictionary containing the newly modified user preferences.
            old_settings (dict): The dictionary containing the previous state to detect deltas.
        """
        reprocess_needed = False
        restart_required = False

        new_paths_norm = [os.path.normcase(os.path.abspath(p)) for p in new_settings["musicLibraryPaths"]]
        old_paths_norm = [os.path.normcase(os.path.abspath(p)) for p in old_settings["musicLibraryPaths"]]

        if set(new_paths_norm) != set(old_paths_norm):
            self.music_library_paths = new_settings["musicLibraryPaths"]
            reprocess_needed = True

        if old_settings["artist_source_tag"] != new_settings["artist_source_tag"]:
            self.artist_source_tag = new_settings["artist_source_tag"]
            reprocess_needed = True

        if old_settings["ignore_articles"] != new_settings["ignore_articles"]:
            self.ignore_articles = new_settings["ignore_articles"]
            self.data_manager.ignore_articles = self.ignore_articles
            reprocess_needed = True

        if old_settings.get("nav_tab_order") != new_settings.get("nav_tab_order"):
            self.nav_tab_order = new_settings.get("nav_tab_order")
            restart_required = True

        if old_settings["ignore_genre_case"] != new_settings["ignore_genre_case"]:
            self.ignore_genre_case = new_settings["ignore_genre_case"]
            reprocess_needed = True

        if old_settings.get("treat_folders_as_unique") != new_settings.get("treat_folders_as_unique"):
            new_val = new_settings.get("treat_folders_as_unique")
            if self.data_manager.all_tracks:
                self.library_manager.migrate_album_favorites_on_setting_change(
                    self.data_manager.all_tracks, to_unique_folders = new_val
                )
            self.treat_folders_as_unique = new_val
            reprocess_needed = True

        old_history_mode = old_settings.get("playback_history_mode", 2)
        self.playback_history_mode = new_settings.get("playback_history_mode", 2)

        if self.playback_history_mode == 0 and old_history_mode != 0:
            self.library_manager.save_playback_history([])
            if hasattr(self.ui_manager, "history_ui_manager"):
                self.ui_manager.history_ui_manager.populate_history_tab()

        if old_settings.get("collect_statistics") != new_settings.get("collect_statistics"):
            self.collect_statistics = new_settings.get("collect_statistics")
            if not self.collect_statistics:
                self.stats_save_trigger_timer.stop()
                self.stats_poll_timer.stop()
                self.library_manager.process_stats_log()
                self.data_manager.recalculate_ratings(self.charts_period, {})
            else:
                if self.player.get_current_state() == QMediaPlayer.PlaybackState.PlayingState:
                    self.stats_save_trigger_timer.start()
                    self.stats_poll_timer.start()
                current_stats = self.library_manager.load_play_stats()
                self.data_manager.recalculate_ratings(self.charts_period, current_stats)
            self.charts_data_is_stale = True

        simple_keys = [
            "show_separators", "show_favorites_separators", "allow_drag_export",
            "favorite_icon_name", "remember_queue_mode", "remember_last_view",
            "remember_window_size", "warm_sound", "scratch_sound", "mini_opacity",
            "show_random_suggestions", "check_updates_at_startup", "autoplay_on_queue",
            "history_store_unique_only", "stylize_vinyl_covers"
        ]

        for key in simple_keys:
            setattr(self, key, new_settings.get(key, getattr(self, key)))

        if self.vinyl_widget:
            self.vinyl_widget.set_stylize_covers(self.stylize_vinyl_covers)
        if getattr(self, "mini_window", None):
            self.mini_window._update_opacity()

        self.player.set_warm_sound(self.warm_sound)
        self.player.set_scratch_sound(self.scratch_sound)

        view_modes = new_settings.get("view_modes", {})
        self.artist_view_mode = view_modes.get("artists", getattr(self, "artist_view_mode", ViewMode.GRID))
        self.artist_album_view_mode = view_modes.get("artist_albums",
                                                     getattr(self, "artist_album_view_mode", ViewMode.GRID))
        self.album_view_mode = view_modes.get("albums", getattr(self, "album_view_mode", ViewMode.GRID))
        self.genre_view_mode = view_modes.get("genres", getattr(self, "genre_view_mode", ViewMode.GRID))
        self.catalog_view_mode = view_modes.get("catalog", getattr(self, "catalog_view_mode", ViewMode.TILE_SMALL))
        self.playlist_view_mode = view_modes.get("playlists", getattr(self, "playlist_view_mode", ViewMode.TILE_BIG))
        self.favorite_view_mode = view_modes.get("favorites", getattr(self, "favorite_view_mode", ViewMode.GRID))
        self.composer_view_mode = view_modes.get("composers", getattr(self, "composer_view_mode", ViewMode.GRID))
        self.composer_album_view_mode = view_modes.get("composer_albums",
                                                       getattr(self, "composer_album_view_mode", ViewMode.GRID))

        self.favorite_playlists_view_mode = view_modes.get("favorite_playlists",
                                                           getattr(self, "favorite_playlists_view_mode", ViewMode.GRID))
        self.favorite_albums_view_mode = view_modes.get("favorite_albums",
                                                        getattr(self, "favorite_albums_view_mode", ViewMode.GRID))
        self.favorite_artists_view_mode = view_modes.get("favorite_artists",
                                                         getattr(self, "favorite_artists_view_mode", ViewMode.GRID))
        self.favorite_composers_view_mode = view_modes.get("favorite_composers",
                                                           getattr(self, "favorite_composers_view_mode", ViewMode.GRID))
        self.favorite_genres_view_mode = view_modes.get("favorite_genres",
                                                        getattr(self, "favorite_genres_view_mode", ViewMode.GRID))
        self.favorite_folders_view_mode = view_modes.get("favorite_folders",
                                                         getattr(self, "favorite_folders_view_mode", ViewMode.GRID))
        self.favorite_artist_album_view_mode = view_modes.get("favorite_artist_albums",
                                                              getattr(self, "favorite_artist_album_view_mode",
                                                                      ViewMode.GRID))
        self.favorite_composer_album_view_mode = view_modes.get("favorite_composer_albums",
                                                                getattr(self, "favorite_composer_album_view_mode",
                                                                        ViewMode.GRID))
        self.favorite_genre_album_view_mode = view_modes.get("favorite_genre_albums",
                                                             getattr(self, "favorite_genre_album_view_mode",
                                                                     ViewMode.GRID))

        self.charts_view_mode = view_modes.get("charts", getattr(self, "charts_view_mode", ViewMode.GRID))
        self.charts_artist_album_view_mode = view_modes.get("charts_artist_albums",
                                                            getattr(self, "charts_artist_album_view_mode",
                                                                    ViewMode.GRID))
        self.charts_composer_album_view_mode = view_modes.get("charts_composer_albums",
                                                              getattr(self, "charts_composer_album_view_mode",
                                                                      ViewMode.GRID))
        self.charts_genre_album_view_mode = view_modes.get("charts_genre_albums",
                                                           getattr(self, "charts_genre_album_view_mode", ViewMode.GRID))

        sort_modes = new_settings.get("sort_modes", {})
        self.artist_sort_mode = sort_modes.get("artists", getattr(self, "artist_sort_mode", SortMode.ALPHA_ASC))
        self.album_sort_mode = sort_modes.get("albums", getattr(self, "album_sort_mode", SortMode.YEAR_DESC))
        self.song_sort_mode = sort_modes.get("songs", getattr(self, "song_sort_mode", SortMode.ARTIST_ASC))
        self.genre_sort_mode = sort_modes.get("genres", getattr(self, "genre_sort_mode", SortMode.ALPHA_ASC))
        self.composer_sort_mode = sort_modes.get("composers", getattr(self, "composer_sort_mode", SortMode.ALPHA_ASC))

        self.favorite_tracks_sort_mode = sort_modes.get("favorite_tracks", getattr(self, "favorite_tracks_sort_mode",
                                                                                   SortMode.DATE_ADDED_DESC))
        self.favorite_playlists_sort_mode = sort_modes.get("favorite_playlists",
                                                           getattr(self, "favorite_playlists_sort_mode",
                                                                   SortMode.DATE_ADDED_DESC))
        self.favorite_albums_sort_mode = sort_modes.get("favorite_albums", getattr(self, "favorite_albums_sort_mode",
                                                                                   SortMode.DATE_ADDED_DESC))
        self.favorite_artists_sort_mode = sort_modes.get("favorite_artists", getattr(self, "favorite_artists_sort_mode",
                                                                                     SortMode.DATE_ADDED_DESC))
        self.favorite_composers_sort_mode = sort_modes.get("favorite_composers",
                                                           getattr(self, "favorite_composers_sort_mode",
                                                                   SortMode.DATE_ADDED_DESC))
        self.favorite_genres_sort_mode = sort_modes.get("favorite_genres", getattr(self, "favorite_genres_sort_mode",
                                                                                   SortMode.DATE_ADDED_DESC))
        self.favorite_folders_sort_mode = sort_modes.get("favorite_folders", getattr(self, "favorite_folders_sort_mode",
                                                                                     SortMode.DATE_ADDED_DESC))
        self.favorite_artist_album_sort_mode = sort_modes.get("favorite_artist_albums",
                                                              getattr(self, "favorite_artist_album_sort_mode",
                                                                      SortMode.YEAR_DESC))
        self.favorite_composer_album_sort_mode = sort_modes.get("favorite_composer_albums",
                                                                getattr(self, "favorite_composer_album_sort_mode",
                                                                        SortMode.YEAR_DESC))
        self.favorite_genre_album_sort_mode = sort_modes.get("favorite_genre_albums",
                                                             getattr(self, "favorite_genre_album_sort_mode",
                                                                     SortMode.YEAR_DESC))

        self.charts_album_sort_mode = sort_modes.get("charts_albums",
                                                     getattr(self, "charts_album_sort_mode", SortMode.DATE_ADDED_DESC))
        self.charts_artist_sort_mode = sort_modes.get("charts_artists",
                                                      getattr(self, "charts_artist_sort_mode",
                                                              SortMode.DATE_ADDED_DESC))
        self.charts_composer_sort_mode = sort_modes.get("charts_composers",
                                                        getattr(self, "charts_composer_sort_mode",
                                                                SortMode.DATE_ADDED_DESC))
        self.charts_genre_sort_mode = sort_modes.get("charts_genres",
                                                     getattr(self, "charts_genre_sort_mode", SortMode.DATE_ADDED_DESC))

        self.charts_artist_album_sort_mode = sort_modes.get("charts_artist_albums",
                                                            getattr(self, "charts_artist_album_sort_mode",
                                                                    SortMode.YEAR_DESC))
        self.charts_composer_album_sort_mode = sort_modes.get("charts_composer_albums",
                                                              getattr(self, "charts_composer_album_sort_mode",
                                                                      SortMode.YEAR_DESC))
        self.charts_genre_album_sort_mode = sort_modes.get("charts_genre_albums",
                                                           getattr(self, "charts_genre_album_sort_mode",
                                                                   SortMode.YEAR_DESC))

        self._update_history_button_visibility()
        self._update_charts_button_visibility()
        self.save_current_settings()
        self._update_favorite_icons()
        self.player_controller.update_favorite_button_ui()
        self.ui_manager.update_nav_button_icons()
        self.update_ui_from_settings()
        self.ui_manager.apply_queue_view_options()

        if hasattr(self.ui_manager.components, "resize_filter"):
            self.ui_manager.components.resize_filter.recalc_layout()

        if reprocess_needed:
            if not self.music_library_paths:
                self.clear_library()
                self.ui_manager.populate_all_tabs()
            else:
                self.start_library_processing(from_cache = False, user_initiated = True)
        else:
            self.ui_manager.populate_all_tabs()

        if (
                self.current_language != new_settings.get("language")
                or self.current_theme != new_settings.get("theme")
                or self.current_accent != new_settings.get("accent_color")
                or restart_required
        ):
            self.current_language = new_settings.get("language")
            self.current_theme = new_settings.get("theme")
            self.current_accent = new_settings.get("accent_color")
            self._handle_theme_change_request()

    def _handle_theme_change_request(self):
        """Displays a dialog instructing the user to restart the application for theme changes."""
        msg_label = translate("The program needs to be restarted for the changes to take effect.")

        if is_onefile_build():
            msg_label += "\n\n" + translate("Please restart program.")
            ok_text = translate("OK")
            restart_text = None
        else:
            ok_text = translate("Later")
            restart_text = translate("Restart Now")

        result = CustomConfirmDialog.confirm(
            self,
            title=translate("Restart Required"),
            label=msg_label,
            ok_text=ok_text,
            cancel_text=None,
            restart_text=restart_text,
        )
        if result == CustomConfirmDialog.RestartCode:
            self.save_current_settings()
            self.restart_app()

    def _handle_clear_stats_request(self, settings_dialog):
        """Handles the user's request to clear play statistics and histories."""
        (accepted, delete_archive_checked) = (
            ClearStatsConfirmDialog.confirm_clear_stats(
                self,
                title=translate("Reset Playback Rating"),
                label=translate("Reset playback rating warning text..."),
                checkbox_text=translate("Also delete archived charts"),
                ok_text=translate("Reset"),
                cancel_text=translate("Cancel"),
            )
        )

        if accepted:
            print("User confirmed. Clearing play stats...")
            self.library_manager.clear_play_stats()

            if delete_archive_checked:
                print("User also requested to delete chart archives.")
                self.library_manager.clear_charts_archive()

            self.rescan_initiated_from_dialog = True
            self.start_library_processing(from_cache=True, user_initiated=True)
            settings_dialog.accept()

    def handle_settings_reset(self, settings_dialog):
        """Handles the procedure to reset application settings back to defaults."""
        confirmed = CustomConfirmDialog.confirm(
            self,
            title=translate("Settings Reset"),
            label=translate(
                "Are you sure you want to reset all settings to their defaults?"
            ),
            ok_text=translate("Reset"),
            cancel_text=translate("Cancel"),
        )

        if confirmed:
            settings_dialog.settings_were_reset = True
            old_artist_source = self.artist_source_tag
            old_ignore_articles = self.ignore_articles
            old_ignore_genre_case = self.ignore_genre_case
            old_favorite_icon_name = self.favorite_icon_name
            old_theme = self.current_theme
            old_accent = self.current_accent
            old_treat_folders_as_unique = self.treat_folders_as_unique
            old_collect_statistics = self.collect_statistics

            self.library_manager.reset_settings()
            self.load_settings()
            self._update_favorite_icons()
            settings_dialog.accept()
            self.apply_player_settings()
            self.apply_ui_settings()
            self.ui_manager.update_nav_button_icons()
            self._update_charts_button_visibility()

            rescan_needed = (
                old_artist_source != self.artist_source_tag
                or old_ignore_articles != self.ignore_articles
                or old_ignore_genre_case != self.ignore_genre_case
                or old_treat_folders_as_unique != self.treat_folders_as_unique
            )

            if not old_collect_statistics and self.collect_statistics:
                rescan_needed = True

            if old_theme != self.current_theme or old_accent != self.current_accent:
                self._handle_theme_change_request()
            elif rescan_needed:
                force_rescan = (
                    old_ignore_genre_case != self.ignore_genre_case
                    or old_treat_folders_as_unique != self.treat_folders_as_unique
                )
                self.start_library_processing(
                    from_cache=not force_rescan, user_initiated=True
                )
            else:
                if old_favorite_icon_name != self.favorite_icon_name:
                    self.ui_manager.populate_all_tabs()


    def handle_player_error(self, error_message):
        """Handles critical playback errors, such as missing files."""
        if "not found" in error_message.lower() or "resource" in error_message.lower():
            curr_idx = self.player.get_current_index()
            queue = self.player.get_current_queue()

            if 0 <= curr_idx < len(queue):
                track = queue[curr_idx]
                self.player_controller._handle_missing_file(track)

                if curr_idx < len(queue) - 1:
                    QTimer.singleShot(300, self.player.next)
            return

        print(f"Error: {error_message}")

    def handle_missing_track(self, track_info):
        """Synchronizes all widgets when a file access error occurs."""
        self.ui_manager.update_all_track_widgets()

        if hasattr(self, "start_library_change_detection"):
            self.start_library_change_detection()

    def load_settings(self):
        """Loads settings from the settings file into class variables."""
        settings = self.library_manager.load_settings()
        self.current_theme = settings.get("theme", "Light")
        self.current_accent = settings.get("accent_color", "Crimson")
        theme.select_theme(self.current_theme, self.current_accent)
        paths = settings.get("musicLibraryPaths", [])
        self.music_library_paths = [os.path.abspath(p) for p in paths]

        default_order = [
            "artist", "album", "genre", "composer",
            "track", "playlist", "folder", "charts"
        ]
        self.nav_tab_order = settings.get("nav_tab_order", default_order)
        for key in default_order:
            if key not in self.nav_tab_order:
                self.nav_tab_order.append(key)

        self.artist_source_tag = settings.get("artist_source_tag", ArtistSource.ARTIST)
        self.show_separators = settings.get("show_separators", True)
        self.show_favorites_separators = settings.get("show_favorites_separators", False)
        self.ignore_articles = settings.get("ignore_articles", True)
        self.data_manager.ignore_articles = self.ignore_articles
        self.ignore_genre_case = settings.get("ignore_genre_case", True)
        self.treat_folders_as_unique = settings.get("treat_folders_as_unique", False)
        self.allow_drag_export = settings.get("allow_drag_export", False)
        self.check_updates_at_startup = settings.get("check_updates_at_startup", True)
        self.dismissed_album_merge_warning = False
        self.dismissed_add_folder_hint = False
        self.remember_queue_mode = settings.get("remember_queue_mode", 3)
        self.playback_history_mode = settings.get("playback_history_mode", 2)
        self.history_store_unique_only = settings.get("history_store_unique_only", True)
        self.remember_last_view = settings.get("remember_last_view", False)

        self.remember_window_size = settings.get("remember_window_size", True)

        self.window_geometry = settings.get("windowGeometry", None)
        self.saved_vinyl_size = settings.get("vinyl_window_size", [392, 592])
        self.vinyl_window_geometry = settings.get("vinyl_window_geometry", None)
        self.mini_geometry = settings.get("mini_geometry", None)
        mini_pos_data = settings.get("mini_pos", None)
        self.mini_pos = QPoint(mini_pos_data[0], mini_pos_data[1]) if mini_pos_data else None
        self.stylize_vinyl_covers = settings.get("stylize_vinyl_covers", False)
        self.warm_sound = settings.get("warm_sound", False)
        self.scratch_sound = settings.get("scratch_sound", False)
        self.mini_opacity = False if IS_LINUX else settings.get("mini_opacity", True)
        self.show_random_suggestions = settings.get("show_random_suggestions", True)
        self.splitter_sizes = settings.get("splitterSizes", None)
        self.current_language = settings.get("language", "en")
        self.favorite_icon_name = settings.get("favorite_icon_name", "favorite_heart")
        self.autoplay_on_queue = settings.get("autoplay_on_queue", False)

        view_modes = settings.get("view_modes", {})
        self.artist_view_mode = view_modes.get("artists", ViewMode.GRID)
        self.artist_album_view_mode = view_modes.get("artist_albums", ViewMode.GRID)
        self.album_view_mode = view_modes.get("albums", ViewMode.GRID)
        self.catalog_view_mode = view_modes.get("catalog", ViewMode.TILE_SMALL)
        self.playlist_view_mode = view_modes.get("playlists", ViewMode.TILE_BIG)
        self.favorite_view_mode = view_modes.get("favorites", ViewMode.GRID)
        self.genre_view_mode = view_modes.get("genres", ViewMode.GRID)
        self.composer_view_mode = view_modes.get("composers", ViewMode.GRID)
        self.composer_album_view_mode = view_modes.get("composer_albums", ViewMode.GRID)

        self.favorite_playlists_view_mode = view_modes.get("favorite_playlists", ViewMode.GRID)
        self.favorite_albums_view_mode = view_modes.get("favorite_albums", ViewMode.GRID)
        self.favorite_artists_view_mode = view_modes.get("favorite_artists", ViewMode.GRID)
        self.favorite_composers_view_mode = view_modes.get("favorite_composers", ViewMode.GRID)
        self.favorite_genres_view_mode = view_modes.get("favorite_genres", ViewMode.GRID)
        self.favorite_folders_view_mode = view_modes.get("favorite_folders", ViewMode.GRID)
        self.favorite_artist_album_view_mode = view_modes.get("favorite_artist_albums", ViewMode.GRID)
        self.favorite_composer_album_view_mode = view_modes.get("favorite_composer_albums", ViewMode.GRID)
        self.favorite_genre_album_view_mode = view_modes.get("favorite_genre_albums", ViewMode.GRID)

        self.charts_view_mode = view_modes.get("charts", ViewMode.GRID)
        self.charts_artist_album_view_mode = view_modes.get("charts_artist_albums", ViewMode.GRID)
        self.charts_composer_album_view_mode = view_modes.get("charts_composer_albums", ViewMode.GRID)
        self.charts_genre_album_view_mode = view_modes.get("charts_genre_albums", ViewMode.GRID)

        sort_modes = settings.get("sort_modes", {})
        self.artist_sort_mode = sort_modes.get("artists", SortMode.ALPHA_ASC)
        self.album_sort_mode = sort_modes.get("albums", SortMode.YEAR_DESC)
        self.artist_album_sort_mode = sort_modes.get("artist_albums", SortMode.YEAR_DESC)
        self.song_sort_mode = sort_modes.get("songs", SortMode.ARTIST_ASC)
        self.playlist_sort_mode = sort_modes.get("playlists", SortMode.ALPHA_ASC)
        self.catalog_sort_mode = sort_modes.get("catalog", SortMode.ALPHA_ASC)
        self.genre_sort_mode = sort_modes.get("genres", SortMode.ALPHA_ASC)
        self.charts_album_sort_mode = sort_modes.get("charts_albums", SortMode.DATE_ADDED_DESC)
        self.charts_artist_sort_mode = sort_modes.get("charts_artists", SortMode.DATE_ADDED_DESC)
        self.charts_composer_sort_mode = sort_modes.get("charts_composers", SortMode.DATE_ADDED_DESC)
        self.charts_genre_sort_mode = sort_modes.get("charts_genres", SortMode.DATE_ADDED_DESC)
        self.composer_sort_mode = sort_modes.get("composers", SortMode.ALPHA_ASC)
        self.composer_album_sort_mode = sort_modes.get("composer_albums", SortMode.YEAR_DESC)

        self.favorite_tracks_sort_mode = sort_modes.get("favorite_tracks", SortMode.DATE_ADDED_DESC)
        self.favorite_playlists_sort_mode = sort_modes.get("favorite_playlists", SortMode.DATE_ADDED_DESC)
        self.favorite_albums_sort_mode = sort_modes.get("favorite_albums", SortMode.DATE_ADDED_DESC)
        self.favorite_artists_sort_mode = sort_modes.get("favorite_artists", SortMode.DATE_ADDED_DESC)
        self.favorite_composers_sort_mode = sort_modes.get("favorite_composers", SortMode.DATE_ADDED_DESC)
        self.favorite_genres_sort_mode = sort_modes.get("favorite_genres", SortMode.DATE_ADDED_DESC)
        self.favorite_folders_sort_mode = sort_modes.get("favorite_folders", SortMode.DATE_ADDED_DESC)
        self.favorite_artist_album_sort_mode = sort_modes.get("favorite_artist_albums", SortMode.YEAR_DESC)
        self.favorite_composer_album_sort_mode = sort_modes.get("favorite_composer_albums", SortMode.YEAR_DESC)
        self.favorite_genre_album_sort_mode = sort_modes.get("favorite_genre_albums", SortMode.YEAR_DESC)

        self.charts_artist_album_sort_mode = sort_modes.get("charts_artist_albums", SortMode.YEAR_DESC)
        self.charts_composer_album_sort_mode = sort_modes.get("charts_composer_albums", SortMode.YEAR_DESC)
        self.charts_genre_album_sort_mode = sort_modes.get("charts_genre_albums", SortMode.YEAR_DESC)

        self.queue_visible = settings.get("queueVisible", True)
        self.queue_compact_mode = settings.get("queueCompactMode", False)
        self.queue_compact_hide_artist = settings.get("queueCompactHideArtist", False)
        self.queue_show_cover = settings.get("queueShowCover", True)
        self.collect_statistics = settings.get("collect_statistics", True)
        self.charts_period = settings.get("charts_period", ChartsPeriod.MONTHLY)
        self.pending_settings_rescan = settings.get("pending_settings_rescan", False)
        self.encyclopedia_collapsed = settings.get("encyclopedia_collapsed", False)
        self.last_right_panel_width = settings.get("lastRightPanelWidth", 300)

        self.player_settings = {
            "volume": settings.get("volume", 50),
            "shuffle": settings.get("shuffle", False),
            "repeatMode": settings.get("repeatMode", 0),
            "warm_sound": settings.get("warm_sound", False),
            "scratch_sound": settings.get("scratch_sound", False),
        }

        if self.playback_history_mode in [0, 1]:
            self.library_manager.save_playback_history([])

    def apply_player_settings(self):
        """Applies the initial playback configuration loaded from settings."""
        saved_volume = self.player_settings.get("volume", 50)
        self.control_panel.volume_slider.setValue(saved_volume)
        self.player.set_volume(saved_volume)
        player_is_shuffled = self.player_settings.get("shuffle", False)
        if self.player.is_shuffled() != player_is_shuffled:
            self.player.toggle_shuffle()
        self.player_controller.update_shuffle_button_ui()
        initial_repeat_mode = RepeatMode(self.player_settings.get("repeatMode", 0))
        self.player.set_repeat_mode(initial_repeat_mode)
        self.control_panel.update_repeat_button(initial_repeat_mode)
        self.player.set_warm_sound(self.player_settings.get("warm_sound", False))
        self.player.set_scratch_sound(self.player_settings.get("scratch_sound", False))
        self.update_volume_ui()

    def _update_history_button_visibility(self):
        """Shows or hides the history button and redirects if necessary."""
        if hasattr(self, "history_button"):
            is_visible = self.playback_history_mode in [1, 2]
            self.history_button.setVisible(is_visible)

            if not is_visible and self.history_button.isChecked():
                self.history_button.setChecked(False)
                try:
                    history_tab_index = self.nav_button_icon_names.index("history")
                    if self.main_stack.currentIndex() == history_tab_index:
                        self.main_stack.setCurrentIndex(0)
                        if self.nav_buttons:
                            self.nav_buttons[0].setChecked(True)
                        self.ui_manager.update_nav_button_icons()
                except (ValueError, AttributeError):
                    pass

    def apply_ui_settings(self):
        """Applies visual states and geometry configuration on startup."""
        if self.remember_window_size and self.window_geometry:
            self.restoreGeometry(QByteArray.fromHex(self.window_geometry.encode()))
        if self.remember_window_size and self.splitter_sizes:
            self.splitter.setSizes(self.splitter_sizes)

        saved_geometry = self.saveGeometry()
        self.restoreGeometry(saved_geometry)

        if not self.queue_visible:
            self.right_panel.hide()
        else:
            self.right_panel.show()
        self.update_queue_toggle_button_ui()

        if self.vinyl_widget:
            self.vinyl_widget.set_stylize_covers(self.stylize_vinyl_covers)

        self.update_ui_from_settings()
        self._update_history_button_visibility()
        self._update_charts_button_visibility()
        self.ui_manager.update_queue_header()
        self.ui_manager.apply_queue_view_options()
        self.player_controller.update_favorite_button_ui()

        self._sync_search_bar_width()

    def update_ui_from_settings(self):
        """Updates internal UI elements based on current view/sort modes."""
        self.ui_manager.components.update_tool_button_icon(
            self.artist_view_button, self.artist_view_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.artist_sort_button, self.artist_sort_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.album_view_button, self.album_view_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.album_sort_button, self.album_sort_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.playlist_view_button, self.playlist_view_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.playlist_sort_button, self.playlist_sort_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.genre_sort_button, self.genre_sort_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.genre_view_button, self.genre_view_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.composer_sort_button, self.composer_sort_mode
        )
        self.ui_manager.components.update_tool_button_icon(
            self.composer_view_button, self.composer_view_mode
        )

        if hasattr(self, "chart_view_button"):
            self.ui_manager.components.update_tool_button_icon(
                self.chart_view_button, self.charts_view_mode
            )

    def set_volume(self, volume):
        """Sets the audio volume for playback."""
        self.player.set_volume(volume)
        if volume > 0 and self.player.audio_output.isMuted():
            self.player.audio_output.setMuted(False)
        self.update_volume_ui()

    def toggle_mute(self):
        """Toggles audio mute state across all players."""
        self.player.audio_output.setMuted(not self.player.audio_output.isMuted())
        self.player.crackle_audio_output.setMuted(
            not self.player.crackle_audio_output.isMuted()
        )
        self.player.scratch_forward_audio_output.setMuted(
            not self.player.scratch_forward_audio_output.isMuted()
        )
        self.player.scratch_backward_audio_output.setMuted(
            not self.player.scratch_backward_audio_output.isMuted()
        )
        self.update_volume_ui()

    def update_volume_ui(self):
        """Updates the visual volume indicator."""
        is_muted = self.player.audio_output.isMuted()
        volume = self.control_panel.volume_slider.value()
        self.control_panel.update_volume_ui(is_muted, volume)

        if getattr(self, "mini_window", None):
            self.mini_window.set_volume_state(volume, is_muted)

    def toggle_queue_view(self):
        """Toggles the visibility of the queue (right panel)."""
        if self.right_panel.isVisible():
            if self.right_panel.width() > 10:
                self.last_right_panel_width = self.right_panel.width()

            self.last_splitter_sizes = self.splitter.sizes()

            self.right_panel.hide()
            self.queue_visible = False
        else:
            self.right_panel.show()

            if self.last_splitter_sizes and sum(self.last_splitter_sizes) > 0:
                self.splitter.setSizes(self.last_splitter_sizes)

            elif self.last_right_panel_width > 0:
                total_width = self.splitter.width()
                target_right_width = self.last_right_panel_width + 1

                if target_right_width < total_width - 50:
                    target_left_width = total_width - target_right_width
                    self.splitter.setSizes([target_left_width, target_right_width])
                else:
                    self.splitter.setSizes(
                        [int(total_width * 0.7), int(total_width * 0.3)]
                    )

            else:
                self.splitter.setSizes(
                    [int(self.splitter.width() * 0.7), int(self.splitter.width() * 0.3)]
                )

            self.queue_visible = True

            QTimer.singleShot(0, self._sync_search_bar_width)

        self.update_queue_toggle_button_ui()

    def update_queue_toggle_button_ui(self):
        """Updates the button indicating if the queue is displayed."""
        self.control_panel.update_queue_toggle_button(self.queue_visible)

    def mousePressEvent(self, event):
        """
        Resets focus from input elements when clicking in an empty area of the window.
        """
        if hasattr(self, "global_search_bar") and self.global_search_bar.hasFocus():
            widget_under_mouse = self.childAt(event.position().toPoint())

            if widget_under_mouse != self.global_search_bar:
                self.global_search_bar.clearFocus()
                self.setFocus()

        super().mousePressEvent(event)

    def closeEvent(self, event):
        """Handles tasks prior to the main window closing (saving state, cleanups)."""
        if self.collect_statistics:
            self.library_manager.process_stats_log()

        self.library_manager.save_external_cache()

        if self.playback_history_mode in [0, 1]:
            self.library_manager.save_playback_history([])

        if self.remember_queue_mode > 0:
            context_data = self.current_queue_context_data
            if isinstance(context_data, tuple):
                context_data = list(context_data)
            queue_state = {
                "name": self.current_queue_name,
                "path": self.current_queue_context_path,
                "tracks": self.player.get_current_queue(),
                "context_data": context_data,
            }
            if self.remember_queue_mode >= 2:
                queue_state["current_track_index"] = self.player.get_current_index()
            if self.remember_queue_mode == 3:
                queue_state["playback_position"] = self.player.player.position()
            self.library_manager.save_last_queue(queue_state)
        else:
            self.library_manager.clear_last_queue()

        if self.remember_last_view:
            self.save_current_view_state()
        else:
            self.library_manager.clear_last_view_state()

        self.save_current_settings()
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.quit()
            self.scan_thread.wait()

        if getattr(self, "encyclopedia_manager_window", None):
            self.encyclopedia_manager_window.close()

        super().closeEvent(event)

    def save_scroll_positions(self):
        """Saves the current vertical scroll positions and loaded item counts for each tab."""
        self.scroll_positions["artists"] = (
            self.artists_scroll.verticalScrollBar().value(),
            self.artists_loaded_count,
        )
        self.scroll_positions["albums"] = (
            self.albums_scroll.verticalScrollBar().value(),
            self.albums_loaded_count,
        )
        self.scroll_positions["songs"] = (
            self.songs_scroll.verticalScrollBar().value(),
            self.songs_loaded_count,
        )
        self.scroll_positions["search"] = (
            self.search_scroll.verticalScrollBar().value(),
            self.search_loaded_count,
        )
        self.scroll_positions["genres"] = (
            self.genres_scroll.verticalScrollBar().value(),
            self.genres_loaded_count,
        )
        self.scroll_positions["composers"] = (
            self.composers_scroll.verticalScrollBar().value(),
            self.composers_loaded_count,
        )

        self.scroll_positions["charts"] = (
            self.charts_scroll.verticalScrollBar().value(),
            self.charts_loaded_count,
        )

        self.scroll_positions["history"] = (
            self.history_scroll.verticalScrollBar().value(),
            getattr(self, "history_loaded_count", 0),
        )

        if (
            self.catalog_stack.count() > 0
            and (current_page := self.catalog_stack.currentWidget())
            and (scroll_area := current_page.findChild(QScrollArea))
        ):
            self.scroll_positions["catalog_path"] = self.current_catalog_path
            self.scroll_positions["catalog_scroll"] = (
                scroll_area.verticalScrollBar().value()
            )

    def start_library_change_detection(self):
        """Starts a background process to check for file changes."""
        if not self.music_library_paths:
            return

        if getattr(self, "is_checking_library_changes", False):
            print("[LibraryChecker] Scan already in progress, skipping request.")
            return

        if self.is_processing_library:
            print("[Main] Library is busy. Retrying change detection in 2s...")
            QTimer.singleShot(2000, self.start_library_change_detection)
            return

        cached_structure = self.startup_structure_snapshot
        if not cached_structure:
            print("[Main] No startup snapshot available. Skipping check.")
            return

        self.is_checking_library_changes = True

        self.change_checker_thread = QThread()
        self.change_checker = LibraryChangeChecker(
            self.music_library_paths,
            cached_structure,
            self.library_manager.supported_formats
        )
        self.change_checker.moveToThread(self.change_checker_thread)

        self.change_checker_thread.started.connect(self.change_checker.run)
        self.change_checker.finished.connect(self.on_library_changes_detected)
        self.change_checker.finished.connect(self.change_checker_thread.quit)
        self.change_checker.finished.connect(self.change_checker.deleteLater)
        self.change_checker_thread.finished.connect(self.change_checker_thread.deleteLater)

        self.change_checker_thread.finished.connect(self._reset_check_flag)

        self.change_checker_thread.start()

    def _reset_check_flag(self):
        """Resets the state tracking library changes check."""
        self.is_checking_library_changes = False

    def on_library_changes_detected(self, has_changes, changed_files, removed_files):
        """Callback to handle detection of library file changes."""
        if has_changes:
            count = len(changed_files) + len(removed_files)
            print(f"Library monitor: Detected {count} external changes.")

            self.pending_added_modified_paths = changed_files
            self.pending_removed_paths = removed_files
            self.pending_external_changes_count = count

            self._update_pending_updates_widget()

    def start_library_processing(
            self,
            from_cache = True,
            user_initiated = True,
            tracks_to_reprocess = None,
            partial_scan_paths = None,
            is_startup = False,
    ):
        """Initiates the library scan or data load on a separate thread."""
        if (
                not is_startup
                and self.is_processing_library
                and not self.is_initial_cache_load
        ):
            return

        if not self.music_library_paths:
            print("Music folders are not selected. Go to Settings.")
            if hasattr(self, "ui_manager"):
                self.ui_manager.populate_all_tabs()
            return

        if user_initiated and not hasattr(self, "queue_state_before_soft_reload"):
            current_queue = self.player.get_current_queue()
            if current_queue:
                self.queue_state_before_soft_reload = {
                    "paths": [track["path"] for track in current_queue],
                    "current_path": (
                        current_queue[self.player.get_current_index()]["path"]
                        if 0 <= self.player.get_current_index() < len(current_queue)
                        else None
                    ),
                    "name": getattr(self, "current_queue_name", None),
                    "context": getattr(self, "current_queue_context_data", None),
                    "playlist_path": getattr(self, "current_queue_context_path", None),
                    "position": self.player.player.position(),
                    "is_playing": self.player.get_current_state()
                                  == self.player.get_current_state().PlayingState,
                }

        tracks_to_process = None

        if tracks_to_reprocess is not None:
            print("Reprocessing library data (Smart Update)...")
            tracks_to_process = tracks_to_reprocess
            self.is_initial_cache_load = False

        elif partial_scan_paths and tracks_to_reprocess is None:
            print("Adding new tracks to existing library...")
            tracks_to_process = self.data_manager.all_tracks
            self.is_initial_cache_load = False
            user_initiated = True

        elif from_cache and (
                cached_tracks := self.library_manager.load_cache(self.music_library_paths)
        ):
            print("Loading from cache...")
            tracks_to_process = cached_tracks
            self.is_initial_cache_load = is_startup

        else:
            print("Scanning library (Full Scan)...")
            self.is_initial_cache_load = False
            user_initiated = True

        self.is_processing_library = True

        if self.data_manager.is_empty():
            self.ui_manager.populate_all_tabs()

        if user_initiated:
            self.settings_button.setEnabled(False)
            self.settings_button.setIcon(self.reload_icon)
            self.reload_timer.start(30)
            self.settings_button.setProcessing(True)
            self.settings_button.setIndeterminate(True)
            set_custom_tooltip(
                self.settings_button,
                title = translate("Updating library..."),
                text = translate("Updating your media library. Please wait..."),
            )

        if not self.is_initial_cache_load and not partial_scan_paths:
            if self.pending_metadata_updates:
                print("Full scan initiated, clearing pending metadata updates.")
                self.pending_metadata_updates.clear()
                self.pending_metadata_items_count = 0
                self.library_manager.clear_pending_updates()
                self._update_pending_updates_widget()

        if from_cache and tracks_to_process and self.pending_metadata_updates:
            print(f"Found {len(self.pending_metadata_updates)} pending updates. Re-scanning changed files...")

            tracks_to_keep = [
                t for t in tracks_to_process
                if t["path"] not in self.pending_metadata_updates
            ]

            paths_to_rescan_meta = [
                t["path"] for t in tracks_to_process
                if t["path"] in self.pending_metadata_updates
            ]

            cached_paths = {t["path"] for t in tracks_to_process}
            for path in self.pending_metadata_updates:
                if path not in cached_paths:
                    paths_to_rescan_meta.append(path)

            tracks_to_process = tracks_to_keep

            if partial_scan_paths:
                partial_scan_paths.extend(paths_to_rescan_meta)
                partial_scan_paths = list(set(partial_scan_paths))
            else:
                partial_scan_paths = paths_to_rescan_meta

            self.is_initial_cache_load = False
            self.library_manager.clear_pending_updates()
            self.pending_metadata_updates.clear()
            self.pending_metadata_items_count = 0

        old_date_map = {}
        if not from_cache and not self.is_initial_cache_load:
            if old_cached_tracks := self.library_manager.load_cache(self.music_library_paths):
                old_date_map = {
                    track["path"]: track.get("date_added")
                    for track in old_cached_tracks
                    if track.get("date_added")
                }
                if old_date_map:
                    print(f"Preserving 'date_added' timestamps for {len(old_date_map)} cached tracks.")

        self.scan_thread = QThread()

        play_stats = {}
        if self.collect_statistics:
            play_stats = self.library_manager.load_play_stats()

        self.processor = LibraryProcessor(
            self.music_library_paths,
            self.artist_source_tag,
            self.ignore_genre_case,
            play_stats,
            tracks_to_process,
            artist_artworks = self.artist_artworks,
            composer_artworks = self.composer_artworks,
            genre_artworks = self.genre_artworks,
            partial_scan_paths = partial_scan_paths,
            blacklist = self.library_manager.load_blacklist(),
            treat_folders_as_unique = self.treat_folders_as_unique,
            charts_period = self.charts_period,
            old_date_map = old_date_map,
            encyclopedia_manager = self.encyclopedia_manager,
        )

        self.processor.user_initiated = user_initiated
        self.processor.moveToThread(self.scan_thread)
        self.processor.progressUpdated.connect(self._update_scan_progress)
        self.scan_thread.started.connect(self.processor.run)
        self.processor.finished.connect(self.on_library_processed)
        self.processor.finished.connect(self.scan_thread.quit)
        self.processor.finished.connect(self.processor.deleteLater)
        self.scan_thread.start()

    def on_library_processed(self, result_data):
        """Finalizes UI state after library processing is complete."""
        user_initiated = getattr(self.processor, "user_initiated", True)
        if not user_initiated:
            self.save_scroll_positions()

        self.data_manager.update_data(result_data)

        if user_initiated or not self.is_initial_cache_load:
            self.library_manager.save_library_structure(self.music_library_paths)
        else:
            print("[Main] Loaded from cache, skipping structure snapshot update to preserve diffs.")

        self.pending_external_changes_count = 0
        self.pixmap_cache.clear()

        if (
            hasattr(self, "queue_state_before_soft_reload")
            and self.queue_state_before_soft_reload
        ):
            self.action_handler.on_scan_finished_restore(
                result_data["all_tracks"], user_initiated
            )

        self.library_manager.playlists_metadata.clear()
        self.favorites = self.library_manager.load_favorites()

        self.is_processing_library = False
        self.ui_manager.populate_all_tabs()

        is_startup = self.is_initial_cache_load or (
            not user_initiated and not self.is_initial_cache_load
        )

        if self.is_initial_cache_load:
            print(
                translate(
                    "Loaded {count} tracks from cache.",
                    count=len(self.data_manager.all_tracks),
                )
            )
            self.is_initial_cache_load = False
        else:
            self.library_manager.clean_artwork_cache(self.data_manager.all_tracks)
            print(
                translate(
                    "Library updated. Found {count} tracks.",
                    count=len(self.data_manager.all_tracks),
                )
            )

            self.library_manager.save_cache(
                self.music_library_paths, self.data_manager.all_tracks
            )

        if is_startup:
            if not self.restore_last_view_state():
                print("No last view state found, defaulting to Artists tab.")
                self.main_stack.setCurrentIndex(0)
                self.nav_buttons[0].setChecked(True)
                self.ui_manager.update_nav_button_icons()
                self.update_current_view_state(main_tab_index=0, context_data={})

        else:
            self.refresh_current_view()

            current_index = self.player.get_current_index()
            queue = self.player.get_current_queue()
            if 0 <= current_index < len(queue):
                track = queue[current_index]
                self.player_controller.update_track_info(
                    track.get("artist", ""), track.get("title", ""), current_index
                )

                if self.right_panel.lyrics_page.isVisible():
                    self.right_panel.updateLyricsPage(track)

                if (
                    self.vinyl_widget.isVisible()
                    and self.vinyl_widget.is_lyrics_visible()
                ):
                    self.right_panel.updateVinylLyricsPage(track)

        self.settings_button.setEnabled(True)

        if user_initiated:
            self.reload_timer.stop()
            self.reload_angle = 0
            self.settings_button.setProcessing(False)

        self.settings_button.setIcon(self.settings_icon)
        set_custom_tooltip(
            self.settings_button,
            title = translate("Settings"),
        )

        def finalize_startup_restore():
            """
            Completes the startup restoration process after the UI has settled.
            Restores the playback queue, current track, and playback position if configured.
            """
            if self.remember_queue_mode > 0 and not self.player.get_current_queue():
                self.is_restoring_queue = True

                queue_state = self.library_manager.load_last_queue(
                    self.data_manager.path_to_track_map
                )
                if queue_state and (tracks := queue_state.get("tracks")):
                    self.player.set_queue(tracks)
                    self.current_queue_name = queue_state.get(
                        "name", translate("Playback Queue")
                    )
                    self.current_queue_context_path = queue_state.get("path")
                    context_data = queue_state.get("context_data")
                    if isinstance(context_data, list):
                        context_data = tuple(context_data)
                    self.current_queue_context_data = context_data
                    self.ui_manager.update_queue_header()
                    start_index = queue_state.get("current_track_index")
                    if start_index is None:
                        start_index = 0
                    start_position = queue_state.get("playback_position")
                    if start_position is None:
                        start_position = 0

                    if self.remember_queue_mode >= 2 and 0 <= start_index < len(tracks):
                        track_to_resume = tracks[start_index]
                        real_path = track_to_resume.get("path", "")
                        if "::" in real_path:
                            real_path = real_path.split("::")[0]

                        if os.path.exists(real_path):
                            saved_pos = (
                                (queue_state.get("playback_position") or 0)
                                if self.remember_queue_mode == 3
                                else 0
                            )
                            try:
                                self.player.play(start_index, pause = True, resume_pos_ms = saved_pos)
                            except Exception as e:
                                print(f"Error restoring playback: {e}")
                        else:
                            print(f"Startup: Last played track missing: {real_path}")
                            self.player_controller._handle_missing_file(track_to_resume)

                            self.player._current_index = start_index
                            self.player.stop()

                            self.player_controller.update_track_info(
                                track_to_resume.get("artist", ""),
                                track_to_resume.get("title", ""),
                                start_index
                            )
                    else:
                        if tracks:
                            self.player_controller.update_track_info("", "", 0)

                self.is_restoring_queue = False

            if self.active_metadata_dialog:
                self.active_metadata_dialog.force_close()

            self._update_pending_updates_widget()

        QTimer.singleShot(150, finalize_startup_restore)

    def _update_scan_progress(self, current, total):
        """Updates the settings button with progress tooltip during library scan."""
        if total > 0:
            self.settings_button.setIndeterminate(False)
            self.settings_button.setRange(0, total)
            self.settings_button.setValue(current)
            set_custom_tooltip(
                self.settings_button,
                title = translate("Updating library..."),
                text = translate("Processed {current}/{total}", current=current, total=total),
            )
        else:
            self.settings_button.setIndeterminate(True)
            set_custom_tooltip(
                self.settings_button,
                title = translate("Updating library..."),
                text = translate("Searching for new files..."),
            )

    def refresh_current_view(self):
        """Reloads the UI data for the currently visible tab state."""
        state = self.current_view_state
        if not state:
            self.ui_manager.populate_all_tabs()
            return

        main_tab_name = state.get("main_tab_name")
        if not main_tab_name:
            return

        try:
            main_tab_index = self.nav_button_icon_names.index(main_tab_name)
        except ValueError:
            if main_tab_name not in ["search", "encyclopedia_full"]:
                self.ui_manager.populate_all_tabs()
                return

        context_data = state.get("context_data", {})

        self.is_restoring_state = True
        try:
            self.ui_manager.populate_all_tabs()

            if main_tab_name == "artist":
                if "album_key" in context_data:
                    self.ui_manager.show_artist_albums(context_data["artist_name"])
                    self.ui_manager.show_album_tracks(
                        tuple(context_data["album_key"]), source_stack = self.artists_stack
                    )
                elif "artist_name" in context_data:
                    self.ui_manager.show_artist_albums(context_data["artist_name"])

            elif main_tab_name == "album":
                if "album_key" in context_data:
                    self.ui_manager.show_album_tracks(
                        tuple(context_data["album_key"]), source_stack = self.albums_stack
                    )

            elif main_tab_name == "genre":
                if "album_key" in context_data:
                    self.ui_manager.show_genre_albums(context_data["genre_name"])
                    self.ui_manager.show_album_tracks(
                        tuple(context_data["album_key"]), source_stack = self.genres_stack
                    )
                elif "genre_name" in context_data:
                    self.ui_manager.show_genre_albums(context_data["genre_name"])

            elif main_tab_name == "composer":
                if "album_key" in context_data:
                    self.ui_manager.show_composer_albums(context_data["composer_name"])
                    self.ui_manager.show_album_tracks(
                        tuple(context_data["album_key"]), source_stack = self.composers_stack
                    )
                elif "composer_name" in context_data:
                    self.ui_manager.show_composer_albums(context_data["composer_name"])

            elif main_tab_name == "folder":
                if path := context_data.get("path"):
                    self.ui_manager.navigate_to_directory(path)

            elif main_tab_name == "playlist":
                if path := context_data.get("path"):
                    self.ui_manager.show_playlist_tracks(path)

            elif main_tab_name == "favorite":
                context = context_data.get("context")
                data = context_data.get("data")

                if context == "tracks":
                    self.ui_manager.favorites_ui_manager.show_favorite_tracks_view()
                elif context == "all_artists":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_artists_view()
                elif context == "all_albums":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_albums_view()
                elif context == "all_genres":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_genres_view()
                elif context == "all_composers":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_composers_view()
                elif context == "all_playlists":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_playlists_view()
                elif context == "all_folders":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_folders_view()
                elif context == "artist" and data:
                    self.ui_manager.favorites_ui_manager.show_favorite_artist_albums_view(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.favorites_stack
                        )
                elif context == "genre" and data:
                    self.ui_manager.favorites_ui_manager.show_favorite_genre_albums_view(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.favorites_stack
                        )
                elif context == "composer" and data:
                    self.ui_manager.favorites_ui_manager.show_favorite_composer_albums_view(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.favorites_stack
                        )
                elif context == "album" and data:
                    self.ui_manager.show_album_tracks(
                        tuple(data), source_stack = self.favorites_stack
                    )
                elif context == "folder" and data:
                    self.ui_manager.favorites_ui_manager._navigate_in_favorite_folder(data)
                elif context == "playlist" and data:
                    self.ui_manager.favorites_ui_manager.show_favorite_playlist_view(data)

            elif main_tab_name == "charts":
                context = context_data.get("context")
                data = context_data.get("data")

                if context == "all_tracks":
                    self.ui_manager.charts_ui_manager.show_all_top_tracks_view()
                elif context == "all_artists":
                    self.ui_manager.charts_ui_manager.show_all_top_artists_view()
                elif context == "all_albums":
                    self.ui_manager.charts_ui_manager.show_all_top_albums_view()
                elif context == "all_genres":
                    self.ui_manager.charts_ui_manager.show_all_top_genres_view()
                elif context == "all_composers":
                    self.ui_manager.charts_ui_manager.show_all_top_composers_view()
                elif context == "artist" and data:
                    self.ui_manager.charts_ui_manager.show_top_artist_albums_view(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.charts_stack
                        )
                elif context == "genre" and data:
                    self.ui_manager.charts_ui_manager.show_top_genre_albums_view(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.charts_stack
                        )
                elif context == "album" and data:
                    self.ui_manager.show_album_tracks(
                        tuple(data), source_stack = self.charts_stack
                    )
                elif context == "composer" and data:
                    self.ui_manager.charts_ui_manager.show_top_composer_albums_view(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.charts_stack
                        )

            elif main_tab_name == "history":
                self.ui_manager.populate_history_tab()

            elif main_tab_name == "encyclopedia_full":
                item_key = context_data.get("item_key")
                item_type = context_data.get("item_type")
                if item_type == "album" and isinstance(item_key, list):
                    item_key = tuple(item_key)

                self.ui_manager.open_encyclopedia_full_view(item_key, item_type)

            elif main_tab_name == "search":
                context = context_data.get("context")
                data = context_data.get("data")

                if context == "artist" and data:
                    self.ui_manager.search_ui_manager.show_search_artist_albums(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.search_stack
                        )
                elif context == "genre" and data:
                    self.ui_manager.search_ui_manager.show_search_genre_albums(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.search_stack
                        )
                elif context == "composer" and data:
                    self.ui_manager.search_ui_manager.show_search_composer_albums(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]), source_stack = self.search_stack
                        )
                elif context in ["album", "albums"] and data:
                    album_key = tuple(data) if isinstance(data, list) else data
                    self.ui_manager.show_album_tracks(album_key, source_stack = self.search_stack)
                elif context == "playlist" and data:
                    self.ui_manager.search_ui_manager.show_search_playlist_tracks(data)
                else:
                    query = self.global_search_bar.text().strip()
                    if query:
                        self.player_controller.perform_search(query)

        finally:
            self.is_restoring_state = False

    def _update_reload_animation(self):
        """Rotates the settings icon to represent active loading."""
        self.reload_angle = (self.reload_angle + 10) % 360
        target_size = QSize(24, 24)
        dpr = self.devicePixelRatio()
        original_pixmap = self.reload_icon.pixmap(target_size)
        canvas_pixmap = QPixmap(target_size * dpr)
        canvas_pixmap.setDevicePixelRatio(dpr)
        canvas_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(canvas_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = target_size.width() / 2
        cy = target_size.height() / 2

        painter.translate(cx, cy)
        painter.rotate(self.reload_angle)
        painter.translate(-cx, -cy)

        painter.drawPixmap(
            0, 0, target_size.width(), target_size.height(), original_pixmap
        )
        painter.end()
        self.settings_button.setIcon(QIcon(canvas_pixmap))

    def set_artist_view_mode(self, action):
        """Sets the artist view mode based on the user's action and repopulates the UI."""
        self.artist_view_mode = action.data()
        self.ui_manager.populate_artists_tab()

    def set_artist_album_view_mode(self, action):
        """Sets the artist album view mode based on the user's action and repopulates the UI."""
        self.artist_album_view_mode = action.data()
        if self.current_artist_view:
            self.ui_manager.show_artist_albums(self.current_artist_view)

    def set_artist_sort_mode(self, action):
        """Sets the artist sorting mode based on the user's action and repopulates the UI."""
        self.artist_sort_mode = action.data()
        self.ui_manager.populate_artists_tab()

    def set_genre_sort_mode(self, action):
        """Sets the genre sorting mode based on the user's action and repopulates the UI."""
        self.genre_sort_mode = action.data()
        self.ui_manager.populate_genres_tab()

    def set_genre_album_view_mode(self, action):
        """Sets the genre album view mode based on the user's action and repopulates the UI."""
        self.artist_album_view_mode = action.data()
        if self.current_genre_view:
            self.ui_manager.show_genre_albums(self.current_genre_view)

    def set_genre_view_mode(self, action):
        """Sets the genre view mode based on the user's action and repopulates the UI."""
        self.genre_view_mode = action.data()
        self.ui_manager.populate_genres_tab()

    def set_catalog_view_mode(self, action):
        """Sets the catalog view mode based on the user's action and repopulates the UI."""
        self.catalog_view_mode = action.data()
        if not self.current_catalog_path:
            self.ui_manager.populate_catalog_tab()
        else:
            self.ui_manager.navigate_to_directory(self.current_catalog_path)

    def set_catalog_sort_mode(self, action):
        """Sets the catalog sorting mode based on the user's action and repopulates the UI."""
        self.catalog_sort_mode = action.data()
        if self.current_catalog_path:
            self.ui_manager.navigate_to_directory(self.current_catalog_path)
        else:
            self.ui_manager.populate_catalog_tab()

    def set_album_view_mode(self, action):
        """Sets the album view mode based on the user's action and repopulates the UI."""
        self.album_view_mode = action.data()
        self.ui_manager.populate_albums_tab()

    def set_album_sort_mode(self, action):
        """Sets the album sorting mode based on the user's action and repopulates the UI."""
        self.album_sort_mode = action.data()
        self.ui_manager.populate_albums_tab()

    def set_song_sort_mode(self, action):
        """Sets the song sorting mode based on the user's action and repopulates the UI."""
        self.song_sort_mode = action.data()
        self.ui_manager.populate_songs_tab()

    def set_playlist_sort_mode(self, action):
        """Sets the playlist sorting mode based on the user's action and repopulates the UI."""
        self.playlist_sort_mode = action.data()
        self.ui_manager.populate_playlists_tab()

    def set_playlist_view_mode(self, action):
        """Sets the playlist view mode based on the user's action and repopulates the UI."""
        self.playlist_view_mode = action.data()
        self.ui_manager.populate_playlists_tab()

    def set_favorite_view_mode(self, action):
        """Sets the favorite view mode based on the user's action and repopulates the UI."""
        self.favorite_view_mode = action.data()
        self.ui_manager.favorites_ui_manager.populate_favorites_tab()

    def set_chart_view_mode(self, action):
        """Sets the chart view mode based on the user's action and repopulates the UI."""
        self.charts_view_mode = action.data()
        self.ui_manager.charts_ui_manager.populate_charts_tab()

    def set_favorite_tracks_sort_mode(self, action):
        """Sets the favorite tracks sorting mode based on the user's action and repopulates the UI."""
        self.favorite_tracks_sort_mode = action.data()
        self.ui_manager.favorites_ui_manager.show_favorite_tracks_view()

    def set_composer_view_mode(self, action):
        """Sets the composer view mode based on the user's action and repopulates the UI."""
        self.composer_view_mode = action.data()
        self.ui_manager.populate_composers_tab()

    def set_composer_sort_mode(self, action):
        """Sets the composer sorting mode based on the user's action and repopulates the UI."""
        self.composer_sort_mode = action.data()
        self.ui_manager.populate_composers_tab()

    def set_composer_album_sort_mode(self, action):
        """Sets the composer album sorting mode based on the user's action and repopulates the UI."""
        self.composer_album_sort_mode = action.data()
        if self.current_composer_view:
            self.ui_manager.show_composer_albums(self.current_composer_view)

    def set_composer_album_view_mode(self, action):
        """Switches the display mode for composer albums and updates the UI."""
        self.composer_album_view_mode = action.data()
        if self.current_composer_view:
            self.ui_manager.show_composer_albums(self.current_composer_view)

    def set_search_view_mode(self, action):
        """Sets the view mode for search results and repopulates."""
        self.search_view_mode = action.data()
        self.ui_manager.search_ui_manager.populate_search_results()

    def set_search_mode_from_action(self, action: QAction):
        """Sets the search mode from the menu action and updates the UI."""
        mode = action.data()
        if mode is not None and self.search_mode != mode:
            self.search_mode = mode
            self.ui_manager.search_ui_manager.update_search_view_options()
            self.ui_manager.components.update_tool_button_icon(
                self.search_mode_button, self.search_mode
            )
            if self.global_search_bar.text():
                self.player_controller.perform_search(self.global_search_bar.text())

    def update_current_view_state(self, main_tab_index, context_data = None):
        """Records current UI state to resume it on the next launch or view switch."""
        if getattr(self, "is_restoring_state", False):
            return

        if hasattr(self, 'current_view_state') and self.current_view_state:
            prev_tab_name = self.current_view_state.get("main_tab_name")
            if prev_tab_name:
                if prev_tab_name not in self.tab_history:
                    self.tab_history[prev_tab_name] = []

                if not self.tab_history[prev_tab_name] or self.tab_history[prev_tab_name][
                    -1] != self.current_view_state:
                    state_to_save = self.current_view_state.copy()

                    if hasattr(self, "ui_manager"):
                        attr_name, val = self.ui_manager._capture_current_scroll()
                        if attr_name:
                            state_to_save["scroll_positions"] = {attr_name: val}

                    self.tab_history[prev_tab_name].append(state_to_save)

                    if len(self.tab_history[prev_tab_name]) > 50:
                        self.tab_history[prev_tab_name] = self.tab_history[prev_tab_name][-50:]

        if isinstance(main_tab_index, str):
            self.current_view_state = {
                "main_tab_name": main_tab_index,
                "context_data": context_data or {},
            }
            return

        if 0 <= main_tab_index < len(self.nav_button_icon_names):
            icon_name = self.nav_button_icon_names[main_tab_index]
            self.current_view_state = {
                "main_tab_name": icon_name,
                "context_data": context_data or {},
            }
        elif hasattr(self, "global_search_page_index") and main_tab_index == self.global_search_page_index:
            self.current_view_state = {
                "main_tab_name": "search",
                "context_data": context_data or {},
            }

    def save_current_view_state(self):
        """Saves current UI state to the state dictionary."""
        if self.current_view_state:
            state_to_save = self.current_view_state.copy()
            ctx = state_to_save.get("context_data", {})

            if "item_key" in ctx and isinstance(ctx["item_key"], tuple):
                ctx["item_key"] = list(ctx["item_key"])

            state_to_save["tab_history"] = self.tab_history

            self.library_manager.save_last_view_state(state_to_save)

    def _apply_view_state(self, state):
        """
        Helper method for applying a specific UI state.
        """
        if not state:
            return

        main_tab_name = state.get("main_tab_name")

        redirect_needed = False
        if main_tab_name == "history" and self.playback_history_mode == 0:
            redirect_needed = True
        elif main_tab_name == "charts" and not self.collect_statistics:
            redirect_needed = True

        if redirect_needed:
            main_tab_name = "favorite"
            state["main_tab_name"] = "favorite"
            state["context_data"] = {}

        context_data = state.get("context_data", {})

        if main_tab_name == "encyclopedia_full":
            if prev_state := context_data.get("previous_state"):
                self._apply_view_state(prev_state)
            else:
                p_idx = context_data.get("prev_main", 0)
                self.main_stack.setCurrentIndex(p_idx)
                if p_idx < len(self.nav_buttons):
                    self.nav_buttons[p_idx].setChecked(True)
                self.ui_manager.update_nav_button_icons()

            item_key = context_data.get("item_key")
            item_type = context_data.get("item_type")
            if item_type == "album" and isinstance(item_key, list):
                item_key = tuple(item_key)

            self.ui_manager.open_encyclopedia_full_view(item_key, item_type)

            self.current_view_state = state
            return

        main_tab_index = -1
        if main_tab_name and main_tab_name in self.nav_button_icon_names:
            main_tab_index = self.nav_button_icon_names.index(main_tab_name)
        elif "main_tab_index" in state:
            main_tab_index = state.get("main_tab_index")

        if main_tab_index != -1:
            self.main_stack.setCurrentIndex(main_tab_index)
            if main_tab_index < len(self.nav_buttons):
                self.nav_buttons[main_tab_index].setChecked(True)
            self.ui_manager.update_nav_button_icons()

            self.update_current_view_state(main_tab_index, context_data)

        if main_tab_name == "history":
            self.ui_manager.populate_history_tab()

        elif context_data:
            if main_tab_name == "artist" and "artist_name" in context_data:
                self.ui_manager.show_artist_albums(context_data["artist_name"])
                if "album_key" in context_data:
                    self.ui_manager.show_album_tracks(
                        tuple(context_data["album_key"]),
                        source_stack=self.artists_stack,
                    )
            elif main_tab_name == "album" and "album_key" in context_data:
                self.ui_manager.show_album_tracks(
                    tuple(context_data["album_key"]), source_stack=self.albums_stack
                )
            elif main_tab_name == "genre" and "genre_name" in context_data:
                self.ui_manager.show_genre_albums(context_data["genre_name"])
                if "album_key" in context_data:
                    self.ui_manager.show_album_tracks(
                        tuple(context_data["album_key"]), source_stack=self.genres_stack
                    )
            elif main_tab_name == "composer" and "composer_name" in context_data:
                self.ui_manager.show_composer_albums(context_data["composer_name"])
                if "album_key" in context_data:
                    self.ui_manager.show_album_tracks(
                        tuple(context_data["album_key"]),
                        source_stack=self.composers_stack,
                    )
            elif main_tab_name == "folder" and "path" in context_data:
                self.ui_manager.navigate_to_directory(context_data["path"])
            elif main_tab_name == "playlist" and "path" in context_data:
                self.ui_manager.show_playlist_tracks(context_data["path"])
            elif main_tab_name == "favorite":
                context = context_data.get("context")
                data = context_data.get("data")

                if context == "tracks":
                    self.ui_manager.favorites_ui_manager.show_favorite_tracks_view()
                elif context == "all_artists":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_artists_view()
                elif context == "all_albums":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_albums_view()
                elif context == "all_genres":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_genres_view()
                elif context == "all_composers":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_composers_view()
                elif context == "all_playlists":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_playlists_view()
                elif context == "all_folders":
                    self.ui_manager.favorites_ui_manager.show_all_favorite_folders_view()
                elif context == "artist" and data:
                    self.ui_manager.favorites_ui_manager.show_favorite_artist_albums_view(
                        data
                    )
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]),
                            source_stack=self.favorites_stack,
                        )
                elif context == "genre" and data:
                    self.ui_manager.favorites_ui_manager.show_favorite_genre_albums_view(
                        data
                    )
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]),
                            source_stack=self.favorites_stack,
                        )
                elif context == "album" and data:
                    self.ui_manager.show_album_tracks(
                        tuple(data), source_stack=self.favorites_stack
                    )
                elif context == "folder" and data:
                    self.ui_manager.favorites_ui_manager._navigate_in_favorite_folder(
                        data
                    )
                elif context == "playlist" and data:
                    self.ui_manager.favorites_ui_manager.show_favorite_playlist_view(
                        data
                    )

            elif main_tab_name == "charts":
                context = context_data.get("context")
                data = context_data.get("data")

                if context == "all_tracks":
                    self.ui_manager.charts_ui_manager.show_all_top_tracks_view()
                elif context == "all_artists":
                    self.ui_manager.charts_ui_manager.show_all_top_artists_view()
                elif context == "all_albums":
                    self.ui_manager.charts_ui_manager.show_all_top_albums_view()
                elif context == "all_genres":
                    self.ui_manager.charts_ui_manager.show_all_top_genres_view()
                elif context == "artist" and data:
                    self.ui_manager.charts_ui_manager.show_top_artist_albums_view(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]),
                            source_stack=self.charts_stack,
                        )
                elif context == "genre" and data:
                    self.ui_manager.charts_ui_manager.show_top_genre_albums_view(data)
                    if "album_key" in context_data:
                        self.ui_manager.show_album_tracks(
                            tuple(context_data["album_key"]),
                            source_stack=self.charts_stack,
                        )
                elif context == "album" and data:
                    self.ui_manager.show_album_tracks(
                        tuple(data), source_stack=self.charts_stack
                    )

    def restore_last_view_state(self):
        """Main restoration method, called at startup."""
        if not self.remember_last_view:
            return False

        state = self.library_manager.load_last_view_state()
        if not state:
            return False

        self.is_restoring_state = True
        try:

            def deferred_restore():
                """
                Executes the actual restoration of the UI view state.
                Delayed to ensure all UI components are fully initialized before applying state.
                """
                try:
                    if "tab_history" in state:
                        self.tab_history = state.pop("tab_history")

                    self.current_view_state = state

                    self._apply_view_state(state)
                finally:
                    self.is_restoring_state = False

            QTimer.singleShot(150, deferred_restore)
            return True

        except Exception as e:
            print(f"Error restoring UI state: {e}")
            self.library_manager.clear_last_view_state()
            self.is_restoring_state = False
            return False

    def toggle_vinyl_widget(self):
        """Toggles between the standard view and the immersive vinyl widget view."""
        is_checked = self.vinyl_toggle_button.isChecked()
        self.control_panel.setViewMode(is_checked)

        is_fullscreen = self.isFullScreen()

        if is_checked:
            if not hasattr(self, '_original_cp_layout'):
                self._original_cp_layout = self.control_panel.parentWidget().layout() if self.control_panel.parentWidget() else self.centralWidget().layout()

            self.queue_visible_before_vinyl = self.right_panel.isVisible()

            if not is_fullscreen:
                self.original_geometry = self.saveGeometry()
            self.normal_is_maximized = self.isMaximized()

            self.vinyl_widget.attach_control_panel(self.control_panel)
            self.control_panel.show()

            if self.vinyl_widget:
                self.vinyl_widget.set_mini_mode(False)

            if self.right_panel.vinyl_queue_container.isVisible():
                self.toggle_vinyl_queue_view(False)
            self.control_panel.update_vinyl_queue_toggle_button(False)

            self.main_view_stack.setCurrentWidget(self.vinyl_widget)

            self.vinyl_toggle_button.setIcon(
                create_svg_icon("assets/control/view_vinny.svg", theme.COLORS["ACCENT"], QSize(24, 24))
            )

            self._set_adjusted_min_size(392, 592)
            min_size = self.minimumSize()

            if not is_fullscreen:
                if self.remember_window_size:
                    if getattr(self, "vinyl_window_geometry", None):
                        self.restoreGeometry(QByteArray.fromHex(self.vinyl_window_geometry.encode()))
                    elif getattr(self, "saved_vinyl_size", None):
                        w, h = self.saved_vinyl_size
                        self.resize(max(min_size.width(), w), max(min_size.height(), h))
                    else:
                        self.resize(min_size)
                else:
                    self.resize(min_size)
                    self.showNormal()
            else:
                self.showFullScreen()

        else:
            if self.remember_window_size and not is_fullscreen:
                self.vinyl_window_geometry = self.saveGeometry().toHex().data().decode()
                self.vinyl_is_maximized = self.isMaximized()
                self.saved_vinyl_size = [self.width(), self.height()]

            self._restore_controls_defaults()
            self.vinyl_widget.detach_control_panel(self.control_panel)
            if hasattr(self, '_original_cp_layout') and self._original_cp_layout:
                self._original_cp_layout.addWidget(self.control_panel)
            else:
                self.centralWidget().layout().addWidget(self.control_panel)

            self.control_panel.show()

            self.main_view_stack.setCurrentIndex(0)

            self.setFixedSize(QSize(16777215, 16777215))

            m = self.contentsMargins()
            self.setMinimumHeight(480 + m.top() + m.bottom())

            if not is_fullscreen:
                if getattr(self, "original_geometry", None):
                    self.restoreGeometry(self.original_geometry)
                else:
                    self.resize(1024, 768)
            else:
                self.showFullScreen()

            self.vinyl_toggle_button.setIcon(
                create_svg_icon("assets/control/view_vinny.svg", theme.COLORS["PRIMARY"], QSize(24, 24))
            )
            self.toggle_always_on_top(False)

    def cycle_window_mode(self):
        """Cyclically toggles modes: Standard -> Vinyl -> mini -> Standard."""
        is_mini = getattr(self, "mini_window", None) and self.mini_window.isVisible()
        is_vinyl = self.vinyl_toggle_button.isChecked()

        if is_mini:
            self.exit_mini_mode()
            if self.vinyl_toggle_button.isChecked():
                self.vinyl_toggle_button.setChecked(False)
                self.toggle_vinyl_widget()
        elif is_vinyl:
            self.enter_mini_mode()
        else:
            self.vinyl_toggle_button.setChecked(True)
            self.toggle_vinyl_widget()

    def _toggle_pending_updates_widget(self, checked):
        """Toggles the visibility of the widget showing pending metadata or library updates."""
        if checked:
            color = theme.COLORS["ACCENT"]
            self._position_pending_updates_widget()
            self.pending_updates_widget.show()
            self.pending_updates_widget.raise_()

        else:
            color = theme.COLORS["PRIMARY"]
            self.pending_updates_widget.hide()

        icon = create_svg_icon("assets/control/warning.svg", color, QSize(24, 24))
        self.notification_toggle_button.setIcon(icon)

    def return_from_vinyl_widget(self):
        """Returns to the standard window view from the vinyl widget."""
        if self.vinyl_toggle_button.isChecked():
            self.vinyl_toggle_button.setChecked(False)
            self.toggle_vinyl_widget()

    def _vinyl_queue_go_back(self):
        """Closes the vinyl queue view and returns to the cover view."""
        self.toggle_vinyl_queue_view(False)

    def toggle_vinyl_queue_view(self, show=None):
        """Toggles the visibility of the queue view while in vinyl mode."""
        if show is None:
            show = not self.vinyl_widget.is_queue_visible()
        if not self.vinyl_toggle_button.isChecked():
            return

        if show:
            self.vinyl_widget.toggle_lyrics_view(False)
            has_lyrics = False
            player_queue = self.player.get_current_queue()
            current_index = self.player.get_current_index()
            if 0 <= current_index < len(player_queue):
                track_data = player_queue[current_index]
                has_lyrics = bool(track_data and track_data.get("lyrics"))

            self.control_panel.update_lyrics_toggle_button(
                is_visible=has_lyrics, is_checked=False
            )

        self.vinyl_widget.toggle_stacked_view(show)
        self.control_panel.update_vinyl_queue_toggle_button(show)

    def eventFilter(self, source, event):
        """Custom event filter, e.g., to handle specific resize interactions."""
        if source == self.right_panel and event.type() == QEvent.Type.Resize:
            self._sync_search_bar_width()
        return super().eventFilter(source, event)

    def _sync_search_bar_width(self, pos=0, index=0):
        """
        Sets the search container width equal to the right panel width.
        Called when the splitter is moved or the window is resized.
        """
        if not hasattr(self, "search_container"):
            return

        if self.right_panel.isVisible() and self.right_panel.width() > 10:
            self.last_right_panel_width = self.right_panel.width()

        target_width = self.last_right_panel_width + 1
        self.search_container.setFixedWidth(target_width)

    def _set_adjusted_min_size(self, base_w, base_h):
        """Sets the minimum size, accounting for window shadow and title bar margins on Linux."""
        m = self.contentsMargins()

        title_bar_height = 0
        if hasattr(self, 'title_bar') and self.title_bar.isVisible():
            title_bar_height = self.title_bar.height()

        self.setMinimumSize(
            base_w + m.left() + m.right(),
            base_h + title_bar_height + m.top() + m.bottom()
        )

    def resizeEvent(self, event):
        """Handles resizing events for the window."""
        super().resizeEvent(event)
        self.ui_manager.drop_zone_manager.handle_resize_event(event)
        self._position_pending_updates_widget()
        if hasattr(self, 'toast') and self.toast.isVisible():
            self.toast.update_position()

    def showEvent(self, event):
        """Handles the show event for the window."""
        super().showEvent(event)

        if self.right_panel.isVisible():
            self._sync_search_bar_width()

        if hasattr(self, "global_search_bar"):
            self.global_search_bar.clearFocus()
            self.setFocus()

    def dragEnterEvent(self, event):
        """Handles drag-enter events."""
        if event.source() == self.right_panel.queue_widget:
            super().dragEnterEvent(event)
            return

        if hasattr(self.right_panel, "vinyl_queue_widget"):
            if event.source() == self.right_panel.vinyl_queue_widget:
                super().dragEnterEvent(event)
                return

        self.ui_manager.drop_zone_manager.handle_drag_enter_event(event)

    def dragMoveEvent(self, event):
        """Handles mouse drag movement events."""
        if event.source() == self.right_panel.queue_widget:
            super().dragMoveEvent(event)
            return

        if hasattr(self.right_panel, "vinyl_queue_widget"):
             if event.source() == self.right_panel.vinyl_queue_widget:
                super().dragMoveEvent(event)
                return

        self.ui_manager.drop_zone_manager.handle_drag_move_event(event)

    def dragLeaveEvent(self, event):
        """Handles drag-leave events."""
        self.ui_manager.drop_zone_manager.handle_drag_leave_event(event)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        """Handles drag-drop operations to the main window."""
        self.ui_manager.drop_zone_manager.handle_drop_event(event)

    def _show_alpha_jump_popup(self, source_view, letters, anchor_widget):
        """Shows the pop-up to fast scroll to a specific letter."""
        popup = AlphaJumpPopup(letters, self)
        popup.letterSelected.connect(
            lambda letter: self.scroll_to_letter(letter, source_view)
        )
        global_pos = anchor_widget.mapToGlobal(QPoint(0, 0))
        popup.move(global_pos.x() - 4, global_pos.y() - 4)
        popup.show()

    def scroll_to_letter(self, letter, source_view = "artists"):
        """
        Optimized Alpha Jump: Synchronously loads data, waits for Layout
        recalculation, and then performs scrolling.
        """
        view_config = {
            "artists": (
                self.artists_scroll,
                self.ui_manager.artists_ui_manager.artist_separator_widgets,
                self.ui_manager.load_more_artists,
                lambda: self.artists_loaded_count,
                lambda: self.current_artists_display_list
            ),
            "albums": (
                self.albums_scroll,
                self.ui_manager.albums_ui_manager.album_separator_widgets,
                self.ui_manager.load_more_albums,
                lambda: self.albums_loaded_count,
                lambda: self.current_albums_display_list
            ),
            "genres": (
                self.genres_scroll,
                self.ui_manager.genres_ui_manager.genre_separator_widgets,
                self.ui_manager.load_more_genres,
                lambda: self.genres_loaded_count,
                lambda: self.current_genres_display_list
            ),
            "composers": (
                self.composers_scroll,
                self.ui_manager.composers_ui_manager.composer_separator_widgets,
                self.ui_manager.load_more_composers,
                lambda: self.composers_loaded_count,
                lambda: self.current_composers_display_list
            ),
        }

        if source_view in [
            "favorite_artists", "favorite_albums", "favorite_genres",
            "charts_artists", "charts_albums", "charts_genres", "charts_composers"
        ]:
            if source_view.startswith("favorite_"):
                target_scroll = self.favorite_detail_scroll_area
                target_separators = self.favorite_detail_separator_widgets
            else:
                target_scroll = self.chart_detail_scroll_area
                target_separators = self.chart_detail_separator_widgets

            view_config[source_view] = (
                target_scroll,
                target_separators,
                None,
                lambda: 1,
                lambda: 1
            )

        config = view_config.get(source_view)
        if not config:
            print(f"AlphaJump: Unknown source view '{source_view}'")
            return

        scroll_area, separators, load_func, get_loaded, get_total = config

        if hasattr(self, 'toast'):
            self.toast.show_message(f"{translate('Searching for:')} {letter}...", duration = 1000)

        max_loops = 100
        loops = 0
        found = False

        while loops < max_loops:
            if letter in separators:
                found = True
                break

            if load_func and get_loaded() < len(get_total()):
                load_func()
                loops += 1
            else:
                break

        if found:
            def perform_scroll(attempts = 5):
                """
                Attempts to scroll the view to the target letter widget.
                Uses multiple attempts (retries) to wait for the layout to fully update
                and the scrollbar maximum to accommodate the target position.
                """
                target_widget = separators.get(letter)
                if not target_widget:
                    if hasattr(self, 'toast'): self.toast.hide()
                    return

                if scroll_area.widget():
                    scroll_area.widget().layout().activate()
                    QApplication.processEvents()

                val = target_widget.y()
                scrollbar = scroll_area.verticalScrollBar()

                if scrollbar.maximum() < val and attempts > 0:
                    QTimer.singleShot(20, lambda: perform_scroll(attempts - 1))
                    return

                scrollbar.setValue(val)

                if hasattr(self, 'toast'):
                    self.toast.hide()

            QTimer.singleShot(20, perform_scroll)

        else:
            if hasattr(self, 'toast'):
                self.toast.show_message(f"{translate('Not found:')} {letter}", duration = 1500)

    def clear_library(self):
        """Clears all metadata and track tracking state."""
        self.player.stop()
        self.player.set_queue([])
        self.data_manager.clear_data()
        self.pixmap_cache.clear()
        self.library_manager.save_cache(self.music_library_paths, [])
        print("Library cleared. Select folders in settings.")

    def toggle_compact_queue(self):
        """Toggles the compact rendering mode in the queue widget."""
        self.queue_compact_mode = not self.queue_compact_mode
        self.save_current_settings()
        self.queueViewOptionsChanged.emit()

    def toggle_queue_show_cover(self):
        """Toggles whether the album cover is shown in the queue list elements."""
        self.queue_show_cover = not self.queue_show_cover
        self.queueViewOptionsChanged.emit()
        self.save_current_settings()

    def toggle_hide_artist_in_compact_queue(self):
        """Toggles whether the artist label is visible in the compact queue view."""
        self.queue_compact_hide_artist = not self.queue_compact_hide_artist
        self.queueViewOptionsChanged.emit()
        self.save_current_settings()

    def _on_lyrics_toggled(self, is_checked):
        """Callback to handle toggling the lyrics view layout."""
        if self.vinyl_toggle_button.isChecked():
            self._toggle_vinyl_lyrics_view(is_checked)
        else:
            track_data = None
            if is_checked:
                player_queue = self.player.get_current_queue()
                current_index = self.player.get_current_index()
                if 0 <= current_index < len(player_queue):
                    track_data = player_queue[current_index]
                else:
                    is_checked = False
                    self.control_panel.update_lyrics_toggle_button(
                        is_visible=False, is_checked=False
                    )

                if is_checked and not self.right_panel.isVisible():
                    self.right_panel.show()
                    if self.last_splitter_sizes and sum(self.last_splitter_sizes) > 0:
                        self.splitter.setSizes(self.last_splitter_sizes)
                    else:
                        self.splitter.setSizes(
                            [
                                int(self.splitter.width() * 0.7),
                                int(self.splitter.width() * 0.3),
                            ]
                        )

                    self.queue_visible = True
                    self.update_queue_toggle_button_ui()

            self.right_panel.toggleLyricsView(is_checked, track_data)

    def toggle_always_on_top(self, state):
        """Toggles the 'Always on Top' flag for the main window."""
        flags = self.windowFlags()
        if state:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.show()

    def enter_mini_mode(self):
        """Activates the mini standalone controller and hides the main window."""
        QApplication.instance().setQuitOnLastWindowClosed(False)

        if self.isFullScreen():
            self.showNormal()
            QTimer.singleShot(800, self._execute_enter_mini)
            return

        if self.isMaximized():
            self.showNormal()
            QTimer.singleShot(100, self._execute_enter_mini)
            return

        self._execute_enter_mini()

    def _execute_enter_mini(self):
        """Internal method to execute mini transition after OS animations settle."""
        if not getattr(self, "mini_window", None):
            self.mini_window = MiniVinny(self)
            self.mini_window.restore_requested.connect(self.exit_mini_mode)

        cp = self.control_panel

        cover_pixmap = None
        try:
            if hasattr(cp.album_art_label, 'cover_label'):
                cover_pixmap = cp.album_art_label.cover_label._pixmap
            elif hasattr(cp.album_art_label, '_pixmap'):
                cover_pixmap = cp.album_art_label._pixmap
        except Exception:
            pass

        is_fav = bool(cp.favorite_button_ctrl.property("active"))

        self.mini_window.set_track_data(
            cp.current_track_data,
            cover_pixmap,
            is_fav,
            getattr(cp.artist_name_label, "data", None),
            getattr(cp.album_name_label, "data", None),
            getattr(cp.album_year_label, "data", None)
        )

        is_playing = (self.player.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        self.mini_window.set_playback_state(is_playing)

        self.mini_window.set_queue(self.player.get_current_queue(), self.player.get_current_index())
        self.mini_window.set_volume_state(cp.volume_slider.value(), self.player.audio_output.isMuted())
        self.mini_window.set_duration(cp.progress_slider.maximum())
        self.mini_window.set_position(cp.progress_slider.value())

        def get_centered_pos():
            """
            Calculates the position to center the mini-player window
            relative to the main application window.
            """
            center = self.geometry().center()
            return QPoint(int(center.x() - self.mini_window.width() / 2),
                          int(center.y() - self.mini_window.height() / 2))

        if getattr(self, "mini_pos", None):
            self.mini_window.move(self.mini_pos)
            mini_rect = self.mini_window.geometry()
            if not any(screen.availableGeometry().intersects(mini_rect) for screen in QApplication.screens()):
                self.mini_window.move(get_centered_pos())
        elif getattr(self, "mini_geometry", None):
            self.mini_window.restoreGeometry(QByteArray.fromHex(self.mini_geometry.encode()))
            mini_rect = self.mini_window.geometry()
            if not any(screen.availableGeometry().intersects(mini_rect) for screen in QApplication.screens()):
                self.mini_window.move(get_centered_pos())
        else:
            self.mini_window.move(get_centered_pos())

        self.mini_window.show()
        self.mini_window.raise_()
        self.mini_window.activateWindow()

        self.hide()

    def exit_mini_mode(self):
        """Restores the main window and hides the Mini Vinny."""
        if getattr(self, "mini_window", None):
            self.mini_pos = self.mini_window.pos()
            self.mini_geometry = self.mini_window.saveGeometry().toHex().data().decode()
            self.mini_window.hide()

        self.show()
        self.toggle_always_on_top(False)
        QApplication.instance().setQuitOnLastWindowClosed(True)

    def _get_current_track_has_lyrics(self):
        """Helper method to check if the current track has lyrics."""
        queue = self.player.get_current_queue()
        index = self.player.get_current_index()
        if 0 <= index < len(queue):
            return bool(queue[index].get("lyrics"))
        return False

    def _on_lyrics_closed(self):
        """Callback to handle closing the standard lyrics view."""
        has_lyrics = self._get_current_track_has_lyrics()

        self.control_panel.update_lyrics_toggle_button(
            is_visible=has_lyrics, is_checked=False
        )
        self.right_panel.toggleLyricsView(False)

    def _toggle_vinyl_lyrics_view(self, is_checked):
        """Toggles the lyrics layout specifically for the Vinyl view mode."""
        track_data = None
        if is_checked:
            player_queue = self.player.get_current_queue()
            current_index = self.player.get_current_index()
            if 0 <= current_index < len(player_queue):
                track_data = player_queue[current_index]
            else:
                is_checked = False
                self.control_panel.update_lyrics_toggle_button(
                    is_visible=False, is_checked=False
                )

        if is_checked:
            self.vinyl_widget.toggle_stacked_view(False)
            self.control_panel.update_vinyl_queue_toggle_button(False)

        self.right_panel.updateVinylLyricsPage(track_data)
        self.vinyl_widget.toggle_lyrics_view(is_checked)

    def _on_vinyl_lyrics_closed(self):
        """Callback to handle closing the vinyl view's lyrics pane."""
        has_lyrics = self._get_current_track_has_lyrics()

        self.control_panel.update_lyrics_toggle_button(
            is_visible=has_lyrics, is_checked=False
        )
        self.vinyl_widget.toggle_lyrics_view(False)

    def toggle_autoplay_on_queue(self):
        """Toggles whether items added to an empty queue start playing automatically."""
        self.autoplay_on_queue = not self.autoplay_on_queue
        self.save_current_settings()

    def on_stats_save_trigger_timeout(self):
        """Callback for the timer that signals play statistics should be saved."""
        if not self.collect_statistics:
            self.stats_save_trigger_timer.stop()
            return

        print(
            f"{STATS_SAVE_TRIGGER_INTERVAL_M}-minute stats trigger fired. Pending save."
        )
        self.pending_stats_save = True

    def on_stats_poll_timer_timeout(self):
        """Callback for polling user activity to perform the actual play stats save."""
        if not self.collect_statistics:
            self.stats_poll_timer.stop()
            return

        if not self.pending_stats_save:
            return

        if (time.time() - self.last_track_change_time) > STATS_POLL_INTERVAL_S:
            print("Stats poller: Inactivity detected. Saving stats.")
            work_done = self.library_manager.process_stats_log()

            if work_done:
                print("Stats poller: Statistics processed. Marking charts as stale.")
                try:
                    new_stats = self.library_manager.load_play_stats()
                    self.data_manager.update_stats_from_json(new_stats)
                    self.charts_data_is_stale = True
                except Exception as e:
                    print(f"Error during in-memory stats update: {e}")
            else:
                print("Stats poller: No new statistics to save.")

            self.pending_stats_save = False
        else:
            print("Stats poller: User is active. Will check again in 30s.")

    def on_track_changed_for_stats(self, artist, title, index):
        """Resets the statistics timeout counter whenever a track is changed manually."""
        self.last_track_change_time = time.time()

    def on_playback_state_changed_for_stats(self, state):
        """Resets the statistics timeout counter on playback start."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.last_track_change_time = time.time()

    def start_background_playlist_indexing(self):
        """Initializes a background thread to fetch data for stored playlists."""
        self.playlist_indexer_thread = QThread()
        self.playlist_worker = PlaylistIndexingWorker(
            self.library_manager.playlists_dir
        )
        self.playlist_worker.moveToThread(self.playlist_indexer_thread)

        self.playlist_indexer_thread.started.connect(self.playlist_worker.run)
        self.playlist_worker.playlist_indexed.connect(
            self.library_manager.update_index_entry
        )

        self.playlist_worker.finished.connect(self.playlist_indexer_thread.quit)
        self.playlist_worker.finished.connect(self.playlist_worker.deleteLater)
        self.playlist_indexer_thread.finished.connect(
            self.playlist_indexer_thread.deleteLater
        )

        self.playlist_indexer_thread.start()