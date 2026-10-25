"""Check the mode-scoped Favorites path is wired into the dashboard installer."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / 'dvswitch-mode-buttons.sh').read_text()
SCRIPT = (ROOT / 'dvswitch-mode-favorites.js').read_text()
HELPER = (ROOT / 'dvswitch-mode-favorites').read_text()
ENDPOINT = INSTALLER.split('install -o root -g root -m 644 /dev/stdin "$ENDPOINT" <<\'PHP\'\n', 1)[1].split('\nPHP\n', 1)[0]


class FavoritesDashboardTests(unittest.TestCase):
    def test_dashboard_loads_favorites_for_active_mode_and_provides_mode_editor(self):
        self.assertIn("load(activeMode)", SCRIPT)
        self.assertIn("selector.addEventListener('change', loadEditorMode)", SCRIPT)
        self.assertIn('editor.showModal()', SCRIPT)
        self.assertIn("editor.addEventListener('close'", SCRIPT)
        self.assertIn('editor.close()', SCRIPT)
        self.assertIn('A mode can have up to 100 favorites.', SCRIPT)
        self.assertIn('editing.length >= 100', SCRIPT)
        self.assertIn('rows.children.length < 100', SCRIPT)
        self.assertIn("selector.innerHTML", SCRIPT)
        for mode in ('BM', 'TGIF', 'STFU', 'YSF', 'P25', 'NXDN', 'DSTAR'):
            self.assertIn("value=\"%s\"" % mode, SCRIPT)
        self.assertIn("favoriteSelect.appendChild(option)", SCRIPT)
        self.assertIn("input.value = favoriteSelect.value", SCRIPT)
        self.assertIn("tuner.requestSubmit()", SCRIPT)
        self.assertIn("addCurrentTargetToFavorites", SCRIPT)
        self.assertIn("selector.value = activeMode", SCRIPT)
        self.assertIn("makeRow({ name: friendlyName, target: target })", SCRIPT)
        self.assertIn('loadTargetNames(activeMode)', SCRIPT)
        self.assertIn("names[target] || ''", SCRIPT)

    def test_target_name_endpoint_uses_the_matching_bm_or_tgif_talkgroup_list(self):
        self.assertIn("isset($_GET['targetNames'])", ENDPOINT)
        self.assertIn("'/var/lib/mmdvm/TGList_BM.txt'", ENDPOINT)
        self.assertIn("'/var/lib/mmdvm/TGList_TGIF.txt'", ENDPOINT)
        self.assertIn("trim($fields[1]) !== '0'", ENDPOINT)
        self.assertIn("str_replace('_', ' ', trim($fields[2]))", ENDPOINT)
        self.assertIn("'/var/lib/mmdvm/YSFHosts.txt'", ENDPOINT)
        self.assertIn("trim($fields[1])", ENDPOINT)
        self.assertIn("$mode.'Hosts.json'", ENDPOINT)
        self.assertIn("array('name', 'sponsor')", ENDPOINT)
        stfu_branch = ENDPOINT.split("} elseif ($mode === 'STFU') {", 1)[1].split("} else {", 1)[0]
        self.assertIn("$file = '/var/lib/mmdvm/TGList_BM.txt';", stfu_branch)
        self.assertNotIn('TGList_TGIF.txt', stfu_branch)
        self.assertNotIn('DSTARHosts', ENDPOINT)

    def test_editor_save_is_server_validated_and_uses_root_helper(self):
        self.assertIn("'application/json') === 0", INSTALLER)
        self.assertIn("/usr/local/sbin/dvswitch-mode-favorites", INSTALLER)
        self.assertIn("www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-favorites", INSTALLER)
        self.assertIn("re.fullmatch(r'[A-Za-z0-9_-]{1,32}', target)", HELPER)
        self.assertIn('os.replace(temporary, path)', HELPER)
        self.assertIn('len(items) > 100', HELPER)
        self.assertIn('clean.sort(key=favorite_sort_key)', HELPER)
        self.assertIn('favorites.sort(function (left, right)', SCRIPT)

    def test_favorites_editor_explains_cancel_and_close_clearly(self):
        self.assertIn('<strong>Cancel or Esc</strong> closes this editor and discards unsaved changes.', INSTALLER)
        self.assertIn('class="button link dvs-favorites-cancel">Cancel / Close</button>', INSTALLER)
        self.assertIn('Select <strong>Save</strong> to keep your changes.', INSTALLER)

    def test_test23_upgrade_and_uninstall_cover_the_favorites_script(self):
        self.assertIn('VERSION="1.0.0-test48"', INSTALLER)
        self.assertIn('|17|18|19|20|21|22|23', INSTALLER)
        self.assertIn('dvswitch-mode-favorites.js', INSTALLER)
        self.assertIn('./dvswitch-mode-favorites "$FAVORITES_HELPER"', INSTALLER)
        self.assertIn('id="dvs-target-tuner"', INSTALLER)
        self.assertIn('id="dvs-favorites"', INSTALLER)
        self.assertIn('<dialog class="dvs-favorites-editor"', INSTALLER)
        self.assertIn("marker='<!-- DVSwitch-Mode-Buttons 1.0.0-test48 -->'", INSTALLER)
        self.assertIn('max-height:45vh', INSTALLER)
        self.assertIn('dvs-favorites-editor', INSTALLER)
        self.assertIn('class="dvs-favorites-control-line"><div class="dvs-favorites-heading">Favorites</div>', INSTALLER)
        self.assertIn('id="dvs-favorites-select" class="dvs-favorites-select"', INSTALLER)
        self.assertIn('</select><button type="button" class="button link dvs-favorites-edit"', INSTALLER)
        self.assertIn('</button>\n<form id="dvs-target-tuner"', INSTALLER)
        self.assertIn('display:inline-flex;vertical-align:middle', INSTALLER)
        self.assertIn("includes('RX Monitor')", SCRIPT)
        self.assertIn("controlLine.insertBefore(rxButton, controlLine.firstChild)", SCRIPT)
        self.assertIn('dvs-rx-monitor-inline', INSTALLER)
        self.assertIn('class="button link dvs-favorites-add-current"', INSTALLER)
        self.assertIn('width:12ch', INSTALLER)

    def test_test18_upgrade_restores_static_tune_and_favorites_markup(self):
        source = (
            '<div class="content"><center>\n'
            '<!-- DVSwitch-Mode-Buttons 1.0.0-test18 -->\n'
            '<div id="dvs-mode-buttons">old controls</div>\n'
            '<script src="/dvswitch/dvswitch-mode-favorites.js"></script>\n'
            '</center><div style="margin-top:8px;">RX Monitor</div></div>\n'
        )
        import tempfile
        import subprocess
        import re
        installer = (ROOT / 'dvswitch-mode-buttons.sh').read_text()
        patcher = re.search(r"python3 - \"\$TARGET\" <<'PY'\n(.*?)^PY$", installer, re.M | re.S)
        self.assertIsNotNone(patcher)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'index.php'
            target.write_text(source)
            result = subprocess.run(['python3', '-c', patcher.group(1), str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = target.read_text()
        self.assertIn('id="dvs-target-tuner"', installed)
        self.assertIn('id="dvs-favorites"', installed)
        self.assertEqual(installed.count('id="dvs-target-tuner"'), 1)


if __name__ == '__main__':
    unittest.main()
