#!/usr/bin/env python3
"""Regression coverage for the bundled responsive dashboard layout."""
# Version: 1.1.12

from __future__ import annotations

import importlib.util
import importlib.machinery
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / 'dvswitch-mode-buttons.sh').read_text()
LAYOUT = (ROOT / 'dvswitch-display-layout.sh').read_text()
MODS_LAYOUT = (ROOT.parent / 'DVSwitch-Mods' / 'dvswitch-display-layout.sh').read_text()
LOADER = importlib.machinery.SourceFileLoader('mode_layout_state', str(ROOT / 'dvswitch-mode-layout-state'))
SPEC = importlib.util.spec_from_loader('mode_layout_state', LOADER)
assert SPEC and SPEC.loader
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


class DisplayLayoutTests(unittest.TestCase):
    # Keep the standalone and bundled installers on the same width rules.
    def test_both_installers_share_fluid_width_logic(self):
        function = r'(?ms)^replace_layout_variants\(\)\{.*?^}'
        bundled = re.search(function, LAYOUT)
        standalone = re.search(function, MODS_LAYOUT)
        self.assertIsNotNone(bundled)
        self.assertIsNotNone(standalone)
        self.assertEqual(bundled.group(0), standalone.group(0))
        for marker in (
            'replace_layout_variants "$CSS_FILE" "width: 96vw;"',
            'replace_layout_variants "$LH_FILE" "width:95%;"',
            'replace_layout_variants "$LOCALTX_FILE" "width:95%;"',
            'replace_layout_variants "$SYSTEM_FILE" "width:95%"',
        ):
            self.assertIn(marker, LAYOUT)
            self.assertIn(marker, MODS_LAYOUT)

    # Both original and previously capped widths must migrate to the fluid layout.
    def test_installer_checks_applies_and_restores_bundled_layout(self):
        self.assertIn('bash ./dvswitch-display-layout.sh check', INSTALLER)
        self.assertIn('python3 ./dvswitch-mode-layout-state capture "$LAYOUT_STATE"', INSTALLER)
        self.assertIn('bash ./dvswitch-display-layout.sh apply', INSTALLER)
        self.assertIn('python3 ./dvswitch-mode-layout-state check-restore "$LAYOUT_STATE"', INSTALLER)
        self.assertIn('python3 ./dvswitch-mode-layout-state restore "$LAYOUT_STATE"', INSTALLER)
        self.assertIn('check|--check)', LAYOUT)
        self.assertIn('check|--check)', MODS_LAYOUT)
        self.assertIn('margin-top:8px !important;', MODS_LAYOUT)
        self.assertIn('#modeInfo > span:first-child { position:relative; top:-1px; }', MODS_LAYOUT)
        self.assertIn('#dvs-asl-activity { position:relative; top:-1px; }', MODS_LAYOUT)
        active_overlay = re.search(r"(?m)^CSS_LAYOUT_OVERLAY='([^']*)'", MODS_LAYOUT)
        self.assertIsNotNone(active_overlay)
        self.assertIn('#dvs-asl-activity { position:relative; top:-1px; }', active_overlay.group(1))
        self.assertIn('#dvs-asl-activity > span { position:relative; top:-1px; }', active_overlay.group(1))
        self.assertIn('#lastHerd > span:first-child { position:relative; top:1px; }', active_overlay.group(1))
        self.assertIn('#dvs-asl-activity > span { position:relative; top:-1px; }', active_overlay.group(1))
        self.assertIn('body:has(#dvs-asl-activity:not([hidden]))', MODS_LAYOUT)
        self.assertIn('PASS: display-layout targets are present', MODS_LAYOUT)
        self.assertIn('VERSION="1.0.0-test89"', INSTALLER)
        for source, old, new in (
            ('$INDEX_FILE', 'background-color:#fafafa; width:100%; table-layout:fixed;', 'table-layout:fixed;'),
            ('$INDEX_FILE', 'width:100%;">', 'background-color:#fafafa;">'),
            ('$CSS_FILE', 'DVSwitch-Mods: responsive column alignment and compact header v1.3.7', 'margin-top:15px !important;'),
            ('$CSS_FILE', '.header h2 { margin:8px 0; }', 'padding:0;'),
            ('$CSS_FILE', 'width: 900px;', 'width: 96vw;'),
            ('$CSS_FILE', 'width: min(96vw, 1200px);', 'width: 96vw;'),
            ('$CSS_FILE', 'white-space: nowrap;', 'white-space: normal;'),
            ('$LH_FILE', 'width:640px;', 'width:95%;'),
            ('$LH_FILE', 'width:min(95%,1400px);', 'width:95%;'),
            ('$LOCALTX_FILE', 'width:640px;', 'width:95%;'),
            ('$LOCALTX_FILE', 'width:min(95%,1400px);', 'width:95%;'),
            ('$SYSTEM_FILE', 'width:855px', 'width:95%'),
            ('$SYSTEM_FILE', 'width:min(95%,1400px)', 'width:95%'),
            ('$SYSTEM_FILE', 'margin-left:6px;margin-right:0px', 'margin-left:auto;margin-right:auto'),
        ):
            self.assertIn(source, LAYOUT)
            self.assertIn(old, LAYOUT)
            self.assertIn(new, LAYOUT)

    def test_restore_reverses_only_substitutions_recorded_at_install(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = [base / f'dashboard-{index}.php' for index in range(5)]
            old = [b'OLD_INDEX', b'OLD_WIDTH OLD_SPACE', b'OLD_LH', b'OLD_LOCAL', b'OLD_SYSTEM OLD_MARGIN']
            new = [b'NEW_INDEX', b'NEW_WIDTH NEW_SPACE', b'NEW_LH', b'NEW_LOCAL', b'NEW_SYSTEM NEW_MARGIN']
            for path, content in zip(paths, old):
                path.write_bytes(content + b'\nkeep local customization\n')
            STATE.PAIRS = {
                path: [(o.decode(), n.decode())]
                for path, o, n in zip(paths, old, new)
            }
            state = base / 'state' / 'owned.json'
            STATE.capture(state)
            for path, o, n in zip(paths, old, new):
                path.write_bytes(path.read_bytes().replace(o, n) + b'later unrelated mod\n')
            STATE.restore(state)
            for path, o in zip(paths, old):
                self.assertIn(o, path.read_bytes())
                self.assertIn(b'keep local customization', path.read_bytes())
                self.assertIn(b'later unrelated mod', path.read_bytes())
            self.assertFalse(state.exists())

    # Capture of CSS and table edits remains idempotent even when the new selector contains its old anchor.
    def test_layout_ownership_capture_is_repeatable_and_restores_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            index = base / 'index.php'
            css = base / 'css.php'
            table_old = 'style="border:none; background-color:#fafafa;"'
            table_new = 'style="border:none; background-color:#fafafa; width:100%; table-layout:fixed;"'
            cell_old = '<td style="background-color:#fafafa; width:100%;">'
            cell_new = '<td style="background-color:#fafafa;">'
            overlay = '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.7 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } .nav #modeInfo > span:first-child { position:relative; top:-1px; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity { position:relative; top:-1px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity > span { position:relative; top:-1px; } body:not(:has(#dvs-asl-activity:not([hidden]))) #lastHerd > span:first-child { position:relative; top:1px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {'
            original_index = table_old + '\n' + cell_old + '\n'
            original_css = '.container { width: 96vw; }\n'
            index.write_text(original_index)
            css.write_text(original_css)
            state = base / 'owned.json'
            original_pairs = STATE.PAIRS
            STATE.PAIRS = {index: [(table_old, table_new), (cell_old, cell_new)], css: [('.container {', overlay)]}
            try:
                STATE.capture(state)
                index.write_text(original_index.replace(table_old, table_new).replace(cell_old, cell_new))
                css.write_text(original_css.replace('.container {', overlay))
                STATE.capture(state)
                first_capture = state.read_text()
                STATE.capture(state)
                self.assertEqual(state.read_text(), first_capture)
                self.assertEqual(len(json.loads(first_capture)['operations']), 3)
                STATE.restore(state)
                self.assertEqual(index.read_text(), original_index)
                self.assertEqual(css.read_text(), original_css)
            finally:
                STATE.PAIRS = original_pairs

    # Existing ownership records must follow the new replacement after an upgrade.
    def test_capture_migrates_previous_width_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            css = base / 'css.php'
            css.write_text('width: min(96vw, 1200px);\n')
            state = base / 'owned.json'
            state.write_text(json.dumps({
                'format': 1,
                'operations': [{
                    'path': str(css),
                    'old': 'width: 900px;',
                    'new': 'width: min(96vw, 1200px);',
                    'count': 1,
                }],
            }, indent=2) + '\n')
            original_pairs = STATE.PAIRS
            STATE.PAIRS = {css: [
                ('width: 900px;', 'width: 96vw;'),
                ('width: min(96vw, 1200px);', 'width: 96vw;'),
            ]}
            try:
                STATE.capture(state)
                css.write_text('width: 96vw;\n')
                STATE.capture(state)
                operation = json.loads(state.read_text())['operations'][0]
                self.assertEqual(operation['new'], 'width: 96vw;')
                STATE.restore(state)
                self.assertEqual(css.read_text(), 'width: 900px;\n')
            finally:
                STATE.PAIRS = original_pairs

    # Previously recorded overlay ownership must advance without adding duplicate CSS edits.
    def test_capture_migrates_previous_alignment_overlay_ownership(self):
        old_overlays = (
            '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.0 */ .nav #modeInfo > fieldset { margin-top:15px !important; } .header { padding:0; } .header h2 { margin:8px 0; } .container {',
            '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.1 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } .header { padding:0; } .header h2 { margin:8px 0; } .container {',
            '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.2 */ .nav #modeInfo > fieldset { margin-top:1px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:6px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity > span { position:relative; top:6px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {',
            '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.4 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } .nav #modeInfo > span:first-child { position:relative; top:-1px; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity { position:relative; top:-1px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {',
            '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.6 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } .nav #modeInfo > span:first-child { position:relative; top:-1px; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity { position:relative; top:-1px; } body:not(:has(#dvs-asl-activity:not([hidden]))) #lastHerd > span:first-child { position:relative; top:1px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {',
            '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.5 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } .nav #modeInfo > span:first-child { position:relative; top:-1px; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity > span { position:relative; top:-1px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {',
            '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.3 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {',
        )
        dashboard_css = Path('/usr/share/dvswitch/css/css.php')
        new_overlay = next(new for old, new in STATE.PAIRS[dashboard_css] if old == '.container {')
        for old_overlay in old_overlays:
            with self.subTest(previous=old_overlay.split('*/')[0]):
                with tempfile.TemporaryDirectory() as directory:
                    base = Path(directory)
                    css = base / 'css.php'
                    css.write_text(new_overlay + '\n')
                    state = base / 'owned.json'
                    state.write_text(json.dumps({
                        'format': 1,
                        'operations': [{
                            'path': str(css),
                            'old': '.container {',
                            'new': old_overlay,
                            'count': 1,
                        }],
                    }, indent=2) + '\n')
                    original_pairs = STATE.PAIRS
                    STATE.PAIRS = {css: [('.container {', new_overlay)]}
                    try:
                        STATE.capture(state)
                        result = json.loads(state.read_text())
                        self.assertEqual(len(result['operations']), 1)
                        self.assertEqual(result['operations'][0]['new'], new_overlay)
                    finally:
                        STATE.PAIRS = original_pairs

    # An upgrade removes the v58 forced-width cell and keeps the saved uninstall state reversible.
    def test_capture_migrates_old_main_cell_width_for_safe_uninstall(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / 'index.php'
            index.write_text('table-layout:fixed;\n<td valign="top" style="border:none; height: 480px; background-color:#fafafa;">\n')
            state = Path(directory) / 'owned.json'
            state.write_text(json.dumps({
                'format': 1,
                'operations': [{
                    'path': str(index),
                    'old': '<td valign="top" style="border:none; height: 480px; background-color:#fafafa;">',
                    'new': '<td valign="top" style="border:none; height: 480px; background-color:#fafafa; width:100%;">',
                    'count': 1,
                }],
            }, indent=2) + '\n')
            original_pairs = STATE.PAIRS
            STATE.PAIRS = {index: [
                ('<td valign="top" style="border:none; height: 480px; background-color:#fafafa; width:100%;">',
                 '<td valign="top" style="border:none; height: 480px; background-color:#fafafa;">'),
            ]}
            try:
                STATE.capture(state)
                operation = json.loads(state.read_text())['operations'][0]
                self.assertNotIn('width:100%;', operation['old'])
                self.assertNotIn('width:100%;', operation['new'])
                STATE.restore(state)
                self.assertNotIn('width:100%;', index.read_text())
            finally:
                STATE.PAIRS = original_pairs

    # Exercise the shell migration against both stock and prior capped values.
    def test_layout_width_replacements_upgrade_and_rerun_cleanly(self):
        match = re.search(r'(?ms)^replace_layout_variants\(\)\{.*?^}', LAYOUT)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as directory:
            dashboard = Path(directory) / 'css.php'
            for previous in ('width: 900px;', 'width: min(96vw, 1200px);'):
                dashboard.write_text(previous + '\n')
                harness = Path(directory) / 'replace.sh'
                harness.write_text(
                    'log(){ :; }\ndie(){ echo "$1" >&2; exit 1; }\n'
                    + match.group(0) + '\n'
                    + f'replace_layout_variants "{dashboard}" "width: 96vw;" "test fluid width" '
                    + '"width: 900px;" "width: min(96vw, 1200px);"\n',
                    encoding='utf-8',
                )
                subprocess.run(['bash', '-e', str(harness)], check=True, capture_output=True)
                self.assertEqual(dashboard.read_text(), 'width: 96vw;\n')
                subprocess.run(['bash', '-e', str(harness)], check=True, capture_output=True)
                self.assertEqual(dashboard.read_text(), 'width: 96vw;\n')

    def test_preexisting_responsive_layout_is_not_claimed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dashboard.php'
            path.write_text('ALREADY RESPONSIVE')
            STATE.PAIRS = {path: [('stock width', 'responsive width')]}
            state = path.parent / 'owned.json'
            STATE.capture(state)
            self.assertEqual(json.loads(state.read_text())['operations'], [])
            STATE.restore(state)
            self.assertEqual(path.read_text(), 'ALREADY RESPONSIVE')


if __name__ == '__main__':
    unittest.main()
