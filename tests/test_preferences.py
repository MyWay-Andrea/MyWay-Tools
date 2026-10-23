import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operational_preferences import Favorites, DEFAULT_FAVORITES


class PreferencesTests(unittest.TestCase):
    def test_defaults_toggle_reload_unknown_and_renamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preferences.json"
            store = Favorites(DEFAULT_FAVORITES + ["extra"], path)
            self.assertEqual(store.ids, DEFAULT_FAVORITES)
            store.toggle("extra")
            store.toggle(DEFAULT_FAVORITES[0])
            loaded = Favorites(DEFAULT_FAVORITES + ["extra"], path)
            self.assertEqual(loaded.ids, DEFAULT_FAVORITES[1:] + ["extra"])
            # Display names are deliberately absent from the persistence contract.
            narrowed = Favorites(["extra"], path)
            self.assertEqual(narrowed.ids, ["extra"])
            self.assertIn(DEFAULT_FAVORITES[1], json.loads(path.read_text())["favorites"])
            for key in loaded.ids:
                loaded.toggle(key)
            self.assertEqual(Favorites(DEFAULT_FAVORITES, path).ids, [])

    def test_corrupt_document_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preferences.json"
            for content in ("{bad", '[]', '{"schema_version":1,"favorites":[{}]}'):
                path.write_text(content)
                self.assertEqual(Favorites(DEFAULT_FAVORITES, path).ids, DEFAULT_FAVORITES)
                self.assertTrue(any(p.read_text() == content for p in path.parent.glob("*.invalid-*.json")))
