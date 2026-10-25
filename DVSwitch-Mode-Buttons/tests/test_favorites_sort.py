"""Favorites are stored alphabetically by name within each mode."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'dvswitch-mode-favorites'
loader = importlib.machinery.SourceFileLoader('dvswitch_mode_favorites', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
favorites = importlib.util.module_from_spec(spec)
loader.exec_module(favorites)


class FavoritesSortTests(unittest.TestCase):
    def test_save_accepts_100_favorites_and_rejects_101(self):
        favorites_100 = [{'name': f'Favorite {index:03}', 'target': str(index)} for index in range(100)]
        favorites_101 = favorites_100 + [{'name': 'Favorite 100', 'target': '100'}]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'favorites.json'
            self.assertEqual(favorites.save_favorites('YSF', favorites_100, target), 100)
            self.assertEqual(len(json.loads(target.read_text())['YSF']), 100)
            with self.assertRaisesRegex(ValueError, 'invalid mode or favorites list'):
                favorites.save_favorites('YSF', favorites_101, target)

    def test_save_sorts_names_per_mode_and_keeps_targets_attached(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'favorites.json'
            target.write_text(json.dumps({
                'BM': [{'name': 'Zulu', 'target': '91'}],
                'TGIF': [
                    {'name': 'World Wide', 'target': '65000'},
                    {'name': 'Alpha', 'target': '123'},
                ],
            }))
            count = favorites.save_favorites('BM', [
                {'name': 'zulu', 'target': '93'},
                {'name': 'Alpha', 'target': '91'},
            ], target)
            self.assertEqual(count, 2)
            saved = json.loads(target.read_text())
            self.assertEqual(saved['BM'], [
                {'name': 'Alpha', 'target': '91'},
                {'name': 'zulu', 'target': '93'},
            ])
            self.assertEqual(saved['TGIF'], [
                {'name': 'Alpha', 'target': '123'},
                {'name': 'World Wide', 'target': '65000'},
            ])


if __name__ == '__main__':
    unittest.main()
