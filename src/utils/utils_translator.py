"""
Vinyller — Translation tools
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

import importlib

# --- Global state management for translations ---

_current_language = "en"
_translation_data = {}
_fallback_translation_data = {}


def load_language_data(lang):
    """
    Dynamically loads translation data from the translations package.

    Args:
        lang (str): The language code to load.
    """
    global _translation_data, _fallback_translation_data

    # Normalize the language code for safe module imports (e.g., pt-br -> pt_br)
    safe_lang = lang.replace("-", "_").lower()

    if not _fallback_translation_data:
        try:
            fallback_module = importlib.import_module("translations.en")
            _fallback_translation_data = getattr(fallback_module, "TRANSLATIONS", {})
        except ImportError:
            print("FATAL: Could not load fallback translation module 'translations.en'.")
            _fallback_translation_data = {}

    if safe_lang == "en":
        _translation_data = _fallback_translation_data
        return

    try:
        module = importlib.import_module(f"translations.{safe_lang}")
        _translation_data = getattr(module, "TRANSLATIONS", {})
    except ImportError:
        print(f"Warning: Translation module for '{safe_lang}' not found. Falling back to default.")
        _translation_data = _fallback_translation_data
    except AttributeError:
        print(f"Warning: Module 'translations.{safe_lang}' found but 'TRANSLATIONS' dict is missing.")
        _translation_data = _fallback_translation_data


def set_current_language(lang):
    """
    Sets the current language and triggers the loading of corresponding data.

    Args:
        lang (str): The language code to set as active.
    """
    global _current_language
    _current_language = lang
    load_language_data(lang)


def get_expected_plural_count(lang):
    """
    Returns the expected number of plural forms for a given language code.
    Useful for unit tests to verify translation dictionaries.
    """
    # Normalize to IETF standard with a hyphen for logic checks
    lang = lang.lower().replace("_", "-")

    if lang in ["zh", "ja", "ko", "tr", "vi", "th", "ms", "id", "fa", "ka"]:
        return 1
    elif lang in ["ru", "uk", "be", "lt", "sr", "hr", "bs", "pl", "cs", "sk", "ro"]:
        return 3
    elif lang == "sl":
        return 4
    elif lang == "ar":
        return 6

    # Default for English, French, German, Spanish, Hindi, Portuguese, etc.
    return 2


def _get_plural_form(lang, n, forms):
    """
    Selects the correct plural form based on standard gettext/CLDR plural rules.

    Args:
        lang (str): ISO 639-1 Language code.
        n (int/float): The number used to determine the plural form.
        forms (list): A list of strings representing different plural forms.

    Returns:
        str: The selected plural form.
    """
    if not forms:
        return ""

    try:
        n = int(n) if n is not None else 0
    except (ValueError, TypeError):
        n = 0

    lang = lang.lower().replace("_", "-")

    # Safe getter: fallback to the last available form if the list is incomplete
    def get_form(idx):
        """
        Safely retrieves the plural form string at the specified index.
        Falls back to the last available form if the provided list is incomplete.
        """
        return forms[idx] if idx < len(forms) else forms[-1]

    # 1. No plurals (Asian, Turkic, Persian, etc.) - 1 form
    if lang in ["zh", "ja", "ko", "tr", "vi", "th", "ms", "id", "fa", "ka"]:
        return get_form(0)

    # 2. French & Brazilian Portuguese (0 and 1 are singular) - 2 forms
    if lang in ["fr", "pt-br", "wa"]:
        return get_form(0 if n <= 1 else 1)

    # 3. East Slavic, Baltic & Balkan - 3 forms
    if lang in ["ru", "uk", "be", "lt", "sr", "hr", "bs"]:
        if n % 10 == 1 and n % 100 != 11:
            return get_form(0)
        elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
            return get_form(1)
        else:
            return get_form(2)

    # 4. Polish - 3 forms
    if lang == "pl":
        if n == 1:
            return get_form(0)
        elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
            return get_form(1)
        else:
            return get_form(2)

    # 5. West Slavic (Czech, Slovak) - 3 forms
    if lang in ["cs", "sk"]:
        if n == 1:
            return get_form(0)
        elif 2 <= n <= 4:
            return get_form(1)
        else:
            return get_form(2)

    # 6. Romanian - 3 forms
    if lang == "ro":
        if n == 1:
            return get_form(0)
        elif n == 0 or (1 < n % 100 < 20):
            return get_form(1)
        else:
            return get_form(2)

    # 7. Slovenian - 4 forms
    if lang == "sl":
        if n % 100 == 1:
            return get_form(0)
        elif n % 100 == 2:
            return get_form(1)
        elif n % 100 == 3 or n % 100 == 4:
            return get_form(2)
        else:
            return get_form(3)

    # 8. Arabic - 6 forms
    if lang == "ar":
        if n == 0:
            return get_form(0)
        elif n == 1:
            return get_form(1)
        elif n == 2:
            return get_form(2)
        elif 3 <= n % 100 <= 10:
            return get_form(3)
        elif 11 <= n % 100 <= 99:
            return get_form(4)
        else:
            return get_form(5)

    # 9. Default Germanic/Romance - 2 forms
    return get_form(0 if n == 1 else 1)


def translate(key, count=None, **kwargs):
    """
    Translates a key using the current language data with a fallback to English.

    Args:
        key (str): The translation key.
        count (int, optional): Number for pluralization.
        **kwargs: Values for string formatting.

    Returns:
        str: The translated and formatted string, or an error message if missing.
    """
    if not isinstance(key, str):
        return str(key)

    lang = _current_language
    string_to_format = _translation_data.get(key)
    is_missing = False

    if string_to_format is None:
        string_to_format = _fallback_translation_data.get(key)
        if string_to_format is None:
            is_missing = True
            string_to_format = key

    if count is not None:
        kwargs["count"] = count
        if isinstance(string_to_format, list):
            string_to_format = _get_plural_form(lang, count, string_to_format)

    try:
        formatted_string = string_to_format.format(**kwargs)
    except (KeyError, IndexError):
        return f"<span style='color: red;'>[FMT_ERR] {string_to_format}</span>"

    if is_missing:
        return f"<span style='color: red;'>⚠️{formatted_string}⚠️</span>"
    else:
        return formatted_string