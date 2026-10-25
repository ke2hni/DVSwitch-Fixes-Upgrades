"""Verify fresh installs get sample favorites without replacing user data."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text()
STARTER = ROOT / "favorites.json"


class FavoritesStarterTests(unittest.TestCase):
    def test_starter_has_examples_for_each_supported_mode(self):
        data = json.loads(STARTER.read_text())
        self.assertEqual(set(data), {"BM", "TGIF", "STFU", "YSF", "P25", "NXDN", "DSTAR"})
        self.assertTrue(all(data.values()))
        self.assertTrue(all(set(item) == {"name", "target"} for items in data.values() for item in items))
        for items in data.values():
            keys = [(item["name"].casefold(), item["target"].casefold()) for item in items]
            self.assertEqual(keys, sorted(keys), "starter favorites must be alphabetized within each mode")

    def test_install_copies_starter_once_and_preserves_existing_favorites(self):
        match = re.search(r"(?ms)^install_favorites_starter\(\)\{\n.*?^\}", INSTALLER)
        self.assertIsNotNone(match, "installer must define the favorites starter operation")
        install_stub = r'''
install() {
  if [[ $1 == -d ]]; then mkdir -p "${@: -1}"; return; fi
  local source=${@: -2:1} destination=${@: -1}
  mkdir -p "$(dirname "$destination")"
  cp "$source" "$destination"
}
'''
        script = install_stub + match.group(0) + "\ninstall_favorites_starter\n"
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "etc/dvswitch-mode-buttons/favorites.json"
            env = dict(os.environ, FAVORITES_FILE=str(destination), FAVORITES_STARTER=str(STARTER))
            first = subprocess.run(["bash", "-c", script], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(destination.read_text()), json.loads(STARTER.read_text()))

            user_data = {"BM": [{"name": "My favorite", "target": "12345"}]}
            destination.write_text(json.dumps(user_data))
            upgrade = subprocess.run(["bash", "-c", script], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(upgrade.returncode, 0, upgrade.stderr)
            self.assertEqual(json.loads(destination.read_text()), user_data)
            self.assertIn("existing favorites preserved", upgrade.stdout)

    def test_check_exits_before_starter_is_copied(self):
        check_start = INSTALLER.index("if [[ $mode == check ]]; then")
        check_exit = INSTALLER.index("  exit 0", check_start)
        install_call = INSTALLER.rindex("install_favorites_starter")
        self.assertLess(check_exit, install_call)


if __name__ == "__main__":
    unittest.main()
