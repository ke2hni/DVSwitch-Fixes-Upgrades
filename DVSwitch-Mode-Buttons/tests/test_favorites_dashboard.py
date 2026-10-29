"""Check standard-mode Favorites and clean ownership of ASL controls."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / 'dvswitch-mode-buttons.sh').read_text()
SCRIPT = (ROOT / 'dvswitch-mode-favorites.js').read_text()
HELPER = (ROOT / 'dvswitch-mode-favorites').read_text()
ENDPOINT = INSTALLER.split('install -o root -g root -m 644 /dev/stdin "$ENDPOINT" <<\'PHP\'\n', 1)[1].split('\nPHP\n', 1)[0]


class FavoritesDashboardTests(unittest.TestCase):
    def test_dashboard_loads_favorites_for_supported_modes(self):
        self.assertIn('load(activeMode)', SCRIPT)
        self.assertIn("selector.addEventListener('change', loadEditorMode)", SCRIPT)
        self.assertIn('editor.showModal()', SCRIPT)
        self.assertIn('addCurrentTargetToFavorites', SCRIPT)
        self.assertIn('loadTargetNames(activeMode)', SCRIPT)
        for mode in ('BM', 'TGIF', 'STFU', 'YSF', 'P25', 'NXDN', 'DSTAR'):
            self.assertIn('value="%s"' % mode, SCRIPT)
        self.assertNotIn('ASL', SCRIPT)

    def test_target_name_endpoint_uses_network_databases(self):
        self.assertIn("'/var/lib/mmdvm/TGList_BM.txt'", ENDPOINT)
        self.assertIn("'/var/lib/mmdvm/TGList_TGIF.txt'", ENDPOINT)
        self.assertIn("'/var/lib/mmdvm/YSFHosts.txt'", ENDPOINT)
        self.assertIn("$mode.'Hosts.json'", ENDPOINT)
        self.assertNotIn('astdb', ENDPOINT)

    def test_button_mod_has_no_asl_runtime_dependency(self):
        self.assertNotIn('ASL_NODE_HELPER', INSTALLER)
        self.assertNotIn('mode ASL', INSTALLER)
        self.assertIn("'/usr/local/sbin/dvswitch-asl3-node-link'", INSTALLER)
        self.assertNotIn('ASL_NODE_HELPER=', INSTALLER)
        self.assertNotIn('ASL', HELPER)
        self.assertNotIn('ASL_NODE_HELPER', (ROOT / 'dvswitch-mode-buttons').read_text())
        self.assertNotIn('--refresh-asl', INSTALLER)
        self.assertIn('VERSION="1.0.0-test74"', INSTALLER)

    def test_upgrade_replaces_embedded_legacy_asl_button(self):
        match = re.search(r"python3 - \"\$TARGET\" <<'PY'\n(.*?)^PY$", INSTALLER, re.M | re.S)
        self.assertIsNotNone(match)
        source = ('<div class="content"><center>\n'
                  '<!-- DVSwitch-Mode-Buttons 1.0.0-test73 -->\n'
                  '<div id="dvs-mode-buttons"><button data-mode="ASL">ASL</button></div>\n'
                  '<script src="/dvswitch/dvswitch-mode-favorites.js"></script>\n'
                  '<div style="margin-top:8px;">RX Monitor</div>\n</center></div>')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'index.php'
            target.write_text(source)
            result = subprocess.run(['python3', '-c', match.group(1), str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = target.read_text()
        self.assertEqual(installed.count('<!-- DVSwitch-Mode-Buttons 1.0.0-test74 -->'), 1)
        self.assertNotIn('data-mode="ASL"', installed)

    def test_check_reports_legacy_button_without_changing_dashboard(self):
        match = re.search(r"python3 - \"\$TARGET\" <<'PY_BUTTONS_CHECK'\n(.*?)^PY_BUTTONS_CHECK$", INSTALLER, re.M | re.S)
        self.assertIsNotNone(match)
        original = ('<div class="content"><center>\n'
                    '<!-- DVSwitch-Mode-Buttons 1.0.0-test73 -->\n'
                    '<div id="dvs-mode-buttons"><button data-mode="ASL">ASL</button></div>\n'
                    '<script src="/dvswitch/dvswitch-mode-favorites.js"></script>\n'
                    '<div style="margin-top:8px;">RX Monitor</div>\n</center></div>')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'index.php'
            target.write_text(original)
            result = subprocess.run(['python3', '-c', match.group(1), str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_text(), original)
        self.assertIn('legacy ASL button', result.stdout)

    def test_check_recognizes_the_full_asl_support_installation(self):
        match = re.search(r"python3 - \"\$TARGET\" <<'PY_BUTTONS_CHECK'\n(.*?)^PY_BUTTONS_CHECK$", INSTALLER, re.M | re.S)
        source = ('<div class="content"><center>\n'
                  '<!-- DVSwitch-Mode-Buttons 1.0.0-test73 -->\n'
                  '<div id="dvs-mode-buttons"><button data-mode="ASL">ASL</button></div>\n'
                  '<script src="/dvswitch/dvswitch-mode-favorites.js"></script>\n'
                  '<div style="margin-top:8px;">RX Monitor</div>\n</center></div>')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'index.php'
            target.write_text(source)
            prelude = "import os; os.path.isfile=lambda _path: True; exec(compile(%r, '<checker>', 'exec'))" % match.group(1)
            result = subprocess.run(['python3', '-c', prelude, str(target)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('full ASL Support is installed', result.stdout)

    def test_favorites_editor_and_upgrade_markup_remain(self):
        self.assertIn('<strong>Cancel or Esc</strong> closes this editor and discards unsaved changes.', INSTALLER)
        self.assertIn('dvswitch-mode-favorites.js', INSTALLER)
        self.assertIn('id="dvs-target-tuner"', INSTALLER)
        self.assertIn('id="dvs-favorites"', INSTALLER)
        self.assertIn('max-height:45vh', INSTALLER)
        self.assertIn('VERSION="1.0.0-test74"', INSTALLER)


if __name__ == '__main__':
    unittest.main()
