<div align="center">
<img src="docs/assets/vinyller_logo_header_en.png" width="480" alt="Vinyller Logo">

`PYTHON 3.13+` `PYQT6` `GPL-3.0+`

**[English](README.en.md) | [Русский](README.ru.md)**

</div>

---

# Vinyller


Vinyller is a modern cross-platform player for local music collections with support for all major audio formats and the ability to read monolithic FLAC+CUE albums by tracks. 
The player allows you to flexibly customize the interface and easily organize your music library using the built-in tag editor and creating your own music encyclopedia. 


|                                          Themes                                           |                                                Encyclopedia Article                                                 |                           Window Modes                                                        |
|:-----------------------------------------------------------------------------------------:|:-------------------------------------------------------------------------------------------------------------------:|:---------------------------------------------------------------------------------------------:|
| [![Vinyller](docs/assets/vinyller_main_themes.png)](docs/assets/vinyller_main_themes.png) | [![Vinyller](docs/assets/vinyller_encyclopedia_lyrics_view.png)](docs/assets/vinyller_encyclopedia_lyrics_view.png) | [![Vinyller](docs/assets/vinyller_compact_modes.png)](docs/assets/vinyller_compact_modes.png) | 


## Main Features

<details>
<summary><b>Library Management and Tag Editor</b></summary>

Vinyller allows you to edit track and album metadata without leaving the program, keeping your music library organized. For convenient management, we offer search, sorting, article handling in artist and album names, the ability to group genres case-insensitively, and much more!

</details>

<details>
<summary><b>Favorites and Blacklist</b></summary>

Add tracks, albums, artists, composers, genres, playlists, and folders to your favorites — just like in streaming services, but locally on your device. You can also blacklist music you don't want to see in your library but can't bring yourself to delete.

</details>

<details>
<summary><b>Music Encyclopedia</b></summary>

Write reviews, add concert photos, link articles about musicians, and add links to external resources — whether it's an official website or a record store.

</details>

<details>
<summary><b>Ratings and Charts</b></summary>

You probably know what you listened to most this month, but what about the whole year? Or conversely — which album is gathering dust? Turn on the charts and collect your own statistics! 

**Important:** Statistics are generated [locally](docs/MANUAL.en.md#user-data-storage) and stored only on your device!

</details>

<details>
<summary><b>Player Window Modes</b></summary>

- Normal — for full control over the library and playback; 
- Vinyl — a compact mode styled as a record player; 
- Mini — an ultra-compact player in "Always on top" mode.

</details>

<details>
<summary><b>Themes and Styling</b></summary>

Style your album covers to look like vintage record sleeves and add a characteristic vinyl crackle to the playback. Prefer dark themes? Vinyller supports various themes, along with the ability to fine-tune the accent color.

</details>

<details>
<summary><b>Mixtape Creation</b></summary>

Create song compilations in a couple of clicks — automatic export to a separate folder to share your music with friends. No more manual file copying one by one!

</details>

<details>
<summary><b>And Also...</b></summary>

- Playback history and restoring the playback position of the last listened track upon restart;
- Quick access to external resources from the context menu of tracks, albums, artists, composers, and genres, plus the ability to add your own search sources;
- Search and view song lyrics, as well as search for tracks by lyrics;
- Drag and drop music into the player and quickly export tracks from the playback queue;
- Different display views for album cards;
- And much more! A detailed list is available in the [User Manual](docs/MANUAL.en.md).

</details>


**Supported formats:** .mp3, .flac, .ogg, .wav, .m4a, .mp4, .wma, .aac, as well as virtual splitting of FLAC+CUE albums into tracks.

Vinyller is available in 18 languages and supports easy [addition of new localizations](docs/MANUAL.en.md#adding-new-localizations).

---

## User Manual
The documentation details the player's features, interaction methods, descriptions of the encyclopedia and metadata editor functions, as well as the logic behind chart generation and instructions for adding new translation files:
[User Manual](docs/MANUAL.en.md).

## Privacy and Network Activity
Vinyller is an application focused on local operation and respecting privacy. The player **does not collect telemetry, does not require account creation, and does not send your library data or listening history to third-party servers**. 
Learn more in the [User Manual](docs/MANUAL.en.md#privacy-and-network-activity).

---

## Download Latest Releases

| Platform    | Format    | Link                                                                                                                                                                                                                                                  |
|-------------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **macOS**   | `.dmg`    | [Download for Apple Silicon](https://github.com/maxcreations/vinyller/releases/latest/download/Vinyller_macOS_Apple_Silicon.dmg)<br/>[Download for Intel](https://github.com/maxcreations/vinyller/releases/latest/download/Vinyller_macOS_Intel.dmg) |
| **Windows** | `.exe`    | [Download Installer](https://github.com/maxcreations/vinyller/releases/latest/download/Vinyller_Windows_Setup.exe)<br/>[Portable Version](https://github.com/maxcreations/vinyller/releases/latest/download/Vinyller_Portable.exe)                    |
| **Linux**   | `.tar.gz` | [Standard Version](https://github.com/maxcreations/vinyller/releases/latest/download/Vinyller_Linux.tar.gz)                                                                                                                                           |

**Minimum system requirements:** Dual-core processor, 4 GB RAM. 
**Supported OS:** Windows 10/11, macOS 14+, Ubuntu 22.04+

---

## Quick Start
<details>
<summary><b>Running the project from source code</b></summary>

1. Clone the repository:
    ```bash
    git clone https://github.com/maxcreations/vinyller.git
    cd vinyller
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run Vinyller:
    ```bash
    python vinyller.py
    ```

</details>

## PyInstaller Quick Build

<details>
<summary><b>macOS</b></summary>

```
pyinstaller --noconfirm --name Vinyller --onedir --windowed --icon="assets/logo/app_icon.png" --add-data "assets:assets" --add-data "translations:translations" --add-data "LICENSE:." --osx-bundle-identifier "ru.maxcreations.vinyller" vinyller.py
```

</details>

<details>
<summary><b>Windows</b></summary>

#### A. For standard mode:
```
pyinstaller --noconfirm --name Vinyller --onedir --noconsole --version-file="version_info.txt" --add-data "assets;assets" --icon="assets/logo/app_icon_win.ico" --add-data "translations;translations" --add-data "LICENSE;." vinyller.py
```
#### B. For portable mode:
```
pyinstaller --noconfirm --onefile --noconsole --version-file="version_info.txt" --add-data "assets;assets" --icon="assets/logo/app_icon_win.ico" --add-data "translations;translations" --add-data "LICENSE;." --name Vinyller_Portable vinyller.py
```
</details>

<details>
<summary><b>Linux</b></summary>

```
pyinstaller --noconfirm --name Vinyller --onedir --noconsole --add-data "assets:assets" --icon="assets/logo/app_icon.png" --add-data "translations:translations" --add-data "LICENSE:." vinyller.py
```
</details>

-----

## Roadmap

- [ ] **Linux Improvements:** Fix potential font size issues.
- [ ] **Metadata Handling:** Add search and auto-completion of metadata based on the MusicBrainz database.
- [ ] **Theme Unification:** Refactor styles to create convenient tools for generating custom themes.
- [ ] **Magic Numbers:** Refactor and move all non-design-related hardcoded numbers into a separate file.
- [ ] **General Refactoring:** Perform general code optimization to comply with MVC.

-----

## Acknowledgments

### Open Source Libraries

- [PyQt6](https://pypi.org/project/PyQt6) — Python Bindings for Qt;
- [Mutagen](https://github.com/quodlibet/mutagen) — for handling audio metadata;
- [Pillow](https://github.com/python-pillow/Pillow) — image processing library;
- [Requests](https://github.com/psf/requests) — for downloading lyrics and encyclopedia article descriptions;
- [Send2Trash](https://github.com/arsenetar/send2trash) — for sending files to the trash bin instead of instant deletion;
- [urllib3](https://github.com/urllib3/urllib3) — for processing external links and Wikipedia data;
- [PyObjC](https://pyobjc.readthedocs.io/) — for integration with native media keys on macOS and MPRemoteCommandCenter.

### External Services

- [Apple Music](https://music.apple.com) — metadata and cover art search;
- [LRCLIB](https://lrclib.net) — lyrics search;
- [Wikipedia](https://www.wikipedia.org/) — short descriptions search for encyclopedia articles.

### Special thanks to the early testers

**TuneLow** and **StarSwarschik**, and everyone who asked questions that made Vinyller better.

### AI Usage

Complex functions, methods, and translations into different languages were implemented with AI support.

-----

## Legal Information

**Vinyller** — © 2026 [Maxim Moshkin](mailto:hellomaxcreations@gmail.com).

This software is distributed under the **GNU General Public License v3.0 or later**.
The full text of the license is available in the [LICENSE](LICENSE) file.

**Disclaimer:**
The software is provided "AS IS", without any express or implied warranties. The developer is not liable for data loss (including deletion of library files, incorrect overwriting of audio file metadata), business interruption, or any other damages arising from the use or inability to use this software. It is highly recommended to backup your music library and encyclopedia files before mass metadata editing.

