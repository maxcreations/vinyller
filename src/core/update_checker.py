"""
Vinyller — Update checker
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


import requests
from PyQt6.QtCore import QThread, pyqtSignal


class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str)  # latest_version, release_url
    error_occurred = pyqtSignal(str)  # error message (optional)

    def __init__(self, current_version, repo_owner="maxcreations", repo_name="vinyller"):
        super().__init__()
        self.current_version = current_version.lower().lstrip('v')
        self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"

    def run(self):
        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()

            data = response.json()
            latest_version_tag = data.get("tag_name", "").lower().lstrip('v')
            release_url = data.get("html_url", "")

            if self._parse_version(latest_version_tag) > self._parse_version(self.current_version):
                self.update_available.emit(latest_version_tag, release_url)

        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"Network error while checking for updates: {e}")
        except Exception as e:
            self.error_occurred.emit(f"Error parsing updates: {e}")

    def _parse_version(self, version_str):
        """Converts a version string like '1.2.10' into a tuple (1, 2, 10) for accurate mathematical comparison."""
        try:
            return tuple(map(int, version_str.split('.')))
        except ValueError:
            return (0, 0, 0)