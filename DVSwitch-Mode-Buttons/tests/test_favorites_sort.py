"""Version: 1.0.4. Cover M17's larger list and existing per-mode limits."""

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
    def test_save_trims_legacy_favorite_names_to_35_character_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'favorites.json'
            favorites.save_favorites('P25', [
                {'name': "America's Kansas City Wide Digital Network", 'target': '31313'},
            ], target)
            self.assertEqual(json.loads(target.read_text())['P25'], [
                {'name': "America's Kansas City Wide Digital", 'target': '31313'},
            ])

    def test_save_accepts_favorite_names_up_to_35_characters(self):
        name = 'N' * 35
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'favorites.json'
            favorites.save_favorites('DSTAR', [{'name': name, 'target': 'REF001C'}], target)
            self.assertEqual(json.loads(target.read_text())['DSTAR'][0]['name'], name)

    def test_save_accepts_target_ids_up_to_35_characters(self):
        target_id = 'A' * 35
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'favorites.json'
            favorites.save_favorites('DSTAR', [{'name': 'Long ID', 'target': target_id}], target)
            self.assertEqual(json.loads(target.read_text())['DSTAR'][0]['target'], target_id)

    def test_save_accepts_100_favorites_and_rejects_101(self):
        favorites_100 = [{'name': f'Favorite {index:03}', 'target': str(index)} for index in range(100)]
        favorites_101 = favorites_100 + [{'name': 'Favorite 100', 'target': '100'}]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'favorites.json'
            self.assertEqual(favorites.save_favorites('YSF', favorites_100, target), 100)
            self.assertEqual(len(json.loads(target.read_text())['YSF']), 100)
            with self.assertRaisesRegex(ValueError, 'invalid mode or favorites list'):
                favorites.save_favorites('YSF', favorites_101, target)

    def test_m17_allows_250_favorites_but_rejects_251(self):
        items = [{'name': f'Reflector {index:03}', 'target': f'M17-{index:03}-A'} for index in range(250)]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'favorites.json'
            self.assertEqual(favorites.save_favorites('M17', items, target), 250)
            with self.assertRaisesRegex(ValueError, 'invalid mode or favorites list'):
                favorites.save_favorites('M17', items + [{'name': 'Overflow', 'target': 'M17-999-A'}], target)

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
