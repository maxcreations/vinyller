# Copyright (c) 2026
# Licensed under the MIT License.

import os

# --- SETTINGS ---
SOURCE_DIR = "../src"
ASSETS_DIR = "../assets"

# Если False, ищет только имя файла (например, 'settings_icon').
# Если True, ищет полное имя с расширением (например, 'settings_icon.png')
CHECK_WITH_EXTENSION = False

# Папки внутри assets, которые нужно пропустить (включая все их вложенные папки).
# Указывайте просто названия папок, например: ["drafts", "macos_only", "old_icons"]
IGNORE_ICON_DIRS = ["drafts", "unused", "animation"]

ICON_EXTENSIONS = {".png", ".svg", ".ico", ".jpg", ".jpeg"}

# Форматы файлов, в которых будем искать упоминания иконок
SOURCE_EXTENSIONS = {".py", ".qml", ".ui", ".json"}

# Папки внутри src, которые нужно пропустить
IGNORE_SOURCE_DIRS = ["venv", ".git", "__pycache__"]


# ----------------


def get_all_icons(assets_dir):
    """Собирает все файлы иконок из папки assets, игнорируя заданные директории."""
    icons = []
    if not os.path.exists(assets_dir):
        print(f"❌ Директория {assets_dir} не найдена!")
        return icons

    for root, dirs, files in os.walk(assets_dir):
        # Исключаем заданные папки иконок из дальнейшего обхода.
        # Модификация dirs[:] влияет на то, куда os.walk пойдет дальше.
        dirs[:] = [d for d in dirs if d not in IGNORE_ICON_DIRS]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in ICON_EXTENSIONS:
                icons.append(os.path.join(root, file))
    return icons


def get_combined_source_text(source_dir):
    """Считывает весь код из исходников в одну большую строку для быстрого поиска."""
    combined_text = []
    if not os.path.exists(source_dir):
        print(f"❌ Директория {source_dir} не найдена!")
        return ""

    for root, dirs, files in os.walk(source_dir):
        # Исключаем ненужные директории исходного кода
        dirs[:] = [d for d in dirs if d not in IGNORE_SOURCE_DIRS]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in SOURCE_EXTENSIONS:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding = "utf-8") as f:
                        combined_text.append(f.read())
                except Exception as e:
                    print(f"⚠️ Ошибка чтения {filepath}: {e}")

    return "\n".join(combined_text)


def main():
    print(f"🔍 Сканируем иконки в: {os.path.abspath(ASSETS_DIR)}")
    if IGNORE_ICON_DIRS:
        print(f"   (Игнорируем папки: {', '.join(IGNORE_ICON_DIRS)})")

    icons = get_all_icons(ASSETS_DIR)

    if not icons:
        print("⚠️ Иконки не найдены. Проверьте путь и расширения.")
        return

    print(f"✅ Найдено файлов иконок для проверки: {len(icons)}")
    print(f"🔍 Считываем исходный код из: {os.path.abspath(SOURCE_DIR)}")

    source_text = get_combined_source_text(SOURCE_DIR)
    if not source_text:
        print("⚠️ Исходный код не найден или пуст.")
        return

    unused_icons = []

    for icon_path in icons:
        filename = os.path.basename(icon_path)
        basename, _ = os.path.splitext(filename)

        # Выбираем, что именно будем искать в коде
        search_term = filename if CHECK_WITH_EXTENSION else basename

        # Простой поиск подстроки в объединенном тексте исходников
        if search_term not in source_text:
            unused_icons.append(icon_path)

    # Вывод результатов
    print("-" * 40)
    if not unused_icons:
        print("🎉 Отлично! Все проверяемые иконки используются в коде.")
    else:
        print(f"🗑️ Найдено {len(unused_icons)} неиспользуемых иконок:")
        for icon in unused_icons:
            # Выводим относительный путь для удобства чтения
            rel_path = os.path.relpath(icon, ASSETS_DIR)
            print(f"  - {rel_path}")

    print("-" * 40)


if __name__ == "__main__":
    main()