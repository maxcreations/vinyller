import unittest
import importlib.util
import os
import re
import sys

# --- PATH SETUP ---
# Assuming this script is located in the 'tools' directory,
# we determine the absolute path to the project root (one level up).
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Add project root to sys.path to allow imports from the 'src' directory
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Now we can safely import from src.utils
from src.utils.utils_translator import get_expected_plural_count
# ------------------


class TestTranslations(unittest.TestCase):
    # --- CHECK SETTINGS ---
    TRANSLATIONS_DIR = os.path.join(PROJECT_ROOT, "translations")
    CHECK_AGAINST_REFERENCE = False
    REFERENCE_LANG = "en"
    MARKERS_TO_CHECK = ['\n', '\\n', '<br>', '<br/>', '<br />']
    # ----------------------

    def _get_markers_in_value(self, value):
        """Finds all line break/tag markers in the value."""
        found_markers = set()
        for marker in self.MARKERS_TO_CHECK:
            if isinstance(value, str):
                if marker in value:
                    found_markers.add(marker)
            elif isinstance(value, list):
                if any(isinstance(v, str) and marker in v for v in value):
                    found_markers.add(marker)
        return found_markers

    def _get_format_vars(self, text):
        """Extracts all formatting variable names (e.g., {count}) from a string."""
        if not isinstance(text, str):
            return set()
        return set(re.findall(r'\{([^{}]+)\}', text))

    def _get_all_format_vars_in_value(self, value):
        """Collects all unique formatting variables from a string or list of strings."""
        if isinstance(value, str):
            return self._get_format_vars(value)
        elif isinstance(value, list):
            vars_set = set()
            for v in value:
                if isinstance(v, str):
                    vars_set.update(self._get_format_vars(v))
            return vars_set
        return set()

    def test_dictionary_structures_and_formatting(self):
        if not os.path.exists(self.TRANSLATIONS_DIR):
            self.skipTest(f"Directory '{self.TRANSLATIONS_DIR}' not found.")

        languages = [
            f[:-3] for f in os.listdir(self.TRANSLATIONS_DIR)
            if f.endswith(".py") and f != "__init__.py"
        ]

        loaded_translations = {}
        for lang in languages:
            filepath = os.path.join(self.TRANSLATIONS_DIR, f"{lang}.py")
            spec = importlib.util.spec_from_file_location(f"translations_{lang}", filepath)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
                loaded_translations[lang] = getattr(module, "TRANSLATIONS", None)
            except Exception as e:
                self.fail(f"Could not load {filepath}: {e}")

            self.assertIsNotNone(loaded_translations[lang], f"TRANSLATIONS dict missing in {lang}.py")
            self.assertIsInstance(loaded_translations[lang], dict, f"TRANSLATIONS in {lang}.py must be a dictionary.")

        # --- STAGE 1: Basic structure, pluralization, tags, and variables check ---
        for lang, translations in loaded_translations.items():
            with self.subTest(lang=lang, stage="basic_checks"):
                expected_forms = get_expected_plural_count(lang)

                for key, value in translations.items():
                    self.assertTrue(
                        isinstance(value, (str, list)),
                        f"Key '{key}' in {lang}.py must be a string or a list of strings."
                    )

                    expected_markers_from_key = [m for m in self.MARKERS_TO_CHECK if m in key]
                    expected_vars_from_key = self._get_format_vars(key)
                    actual_vars_in_value = self._get_all_format_vars_in_value(value)

                    missing_vars = expected_vars_from_key - actual_vars_in_value
                    if missing_vars:
                        self.fail(
                            f"Missing format variables {missing_vars} in translation for key '{key}' in {lang}.py")

                    if isinstance(value, list):
                        self.assertEqual(
                            len(value),
                            expected_forms,
                            f"Plural key '{key}' in {lang}.py has {len(value)} forms, but requires {expected_forms}."
                        )
                        for idx, form in enumerate(value):
                            self.assertIsInstance(
                                form, str,
                                f"Form at index {idx} in plural key '{key}' ({lang}.py) is not a string."
                            )
                            for marker in expected_markers_from_key:
                                self.assertIn(
                                    marker, form,
                                    f"Missing formatting marker '{marker}' in plural form index {idx} for key '{key}' in {lang}.py"
                                )
                    else:
                        for marker in expected_markers_from_key:
                            self.assertIn(
                                marker, value,
                                f"Missing formatting marker '{marker}' in translation for key '{key}' in {lang}.py"
                            )

        # --- STAGE 2: Optional reference language check ---
        if self.CHECK_AGAINST_REFERENCE and self.REFERENCE_LANG in loaded_translations:
            ref_translations = loaded_translations[self.REFERENCE_LANG]

            for lang, target_translations in loaded_translations.items():
                if lang == self.REFERENCE_LANG:
                    continue

                with self.subTest(lang=lang, stage="reference_checks"):
                    for key, target_value in target_translations.items():
                        if key in ref_translations:
                            ref_value = ref_translations[key]

                            expected_markers_from_ref = self._get_markers_in_value(ref_value)
                            for marker in expected_markers_from_ref:
                                if isinstance(target_value, list):
                                    marker_found = any(isinstance(v, str) and marker in v for v in target_value)
                                    self.assertTrue(
                                        marker_found,
                                        f"Missing reference marker '{marker}' in plural forms for key '{key}' in {lang}.py (expected from {self.REFERENCE_LANG}.py)"
                                    )
                                else:
                                    self.assertIn(
                                        marker, target_value,
                                        f"Missing reference marker '{marker}' in translation for key '{key}' in {lang}.py (expected from {self.REFERENCE_LANG}.py)"
                                    )

                            expected_vars_from_ref = self._get_all_format_vars_in_value(ref_value)
                            actual_vars_in_target = self._get_all_format_vars_in_value(target_value)
                            missing_vars_ref = expected_vars_from_ref - actual_vars_in_target

                            if missing_vars_ref:
                                self.fail(
                                    f"Missing reference variables {missing_vars_ref} in translation for key '{key}' in {lang}.py (expected from {self.REFERENCE_LANG}.py)")


if __name__ == '__main__':
    unittest.main()