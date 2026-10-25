#!/usr/bin/env python3
"""Regression coverage for the bundled responsive dashboard layout."""

from __future__ import annotations

import importlib.util
import importlib.machinery
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / 'dvswitch-mode-buttons.sh').read_text()
LAYOUT = (ROOT / 'dvswitch-display-layout.sh').read_text()
LOADER = importlib.machinery.SourceFileLoader('mode_layout_state', str(ROOT / 'dvswitch-mode-layout-state'))
SPEC = importlib.util.spec_from_loader('mode_layout_state', LOADER)
assert SPEC and SPEC.loader
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


class DisplayLayoutTests(unittest.TestCase):
    def test_installer_checks_applies_and_restores_bundled_layout(self):
        self.assertIn('bash ./dvswitch-display-layout.sh check', INSTALLER)
        self.assertIn('python3 ./dvswitch-mode-layout-state capture "$LAYOUT_STATE"', INSTALLER)
        self.assertIn('bash ./dvswitch-display-layout.sh apply', INSTALLER)
        self.assertIn('python3 ./dvswitch-mode-layout-state check-restore "$LAYOUT_STATE"', INSTALLER)
        self.assertIn('python3 ./dvswitch-mode-layout-state restore "$LAYOUT_STATE"', INSTALLER)
        self.assertIn('check)', LAYOUT)
        for source, old, new in (
            ('$INDEX_FILE', '<td valign="top" style="border:none; height: 480px; background-color:#fafafa;">', '<td valign="top" style="border:none; height: 480px; background-color:#fafafa; width:100%;">'),
            ('$CSS_FILE', 'width: 900px;', 'width: min(96vw, 1200px);'),
            ('$CSS_FILE', 'white-space: nowrap;', 'white-space: normal;'),
            ('$LH_FILE', 'width:640px;', 'width:min(95%,1400px);'),
            ('$LOCALTX_FILE', 'width:640px;', 'width:min(95%,1400px);'),
            ('$SYSTEM_FILE', 'width:855px', 'width:min(95%,1400px)'),
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

    def test_preexisting_responsive_layout_is_not_claimed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dashboard.php'
            path.write_text('ALREADY RESPONSIVE')
            STATE.PAIRS = {path: [('stock width', 'responsive width')]}
            state = path.parent / 'owned.json'
            STATE.capture(state)
            self.assertEqual(__import__('json').loads(state.read_text())['operations'], [])
            STATE.restore(state)
            self.assertEqual(path.read_text(), 'ALREADY RESPONSIVE')


if __name__ == '__main__':
    unittest.main()
