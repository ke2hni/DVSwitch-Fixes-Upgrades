#!/usr/bin/env python3
"""Verify Mode Buttons installs with RX Monitor in either supported location."""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "dvswitch-mode-buttons.sh"
SOURCE = INSTALLER.read_text()
MATCH = re.search(
    r"python3 - \"\$TARGET\" <<'PY'\n(.*?)^PY$",
    SOURCE,
    re.MULTILINE | re.DOTALL,
)
assert MATCH, "dashboard installer patch program is missing"
PATCHER = MATCH.group(1)
CHECK_MATCH = re.search(
    r"python3 - \"\$TARGET\" <<'PY_BUTTONS_CHECK'\n(.*?)^PY_BUTTONS_CHECK$",
    SOURCE,
    re.MULTILINE | re.DOTALL,
)
assert CHECK_MATCH, "dashboard --check layout validator is missing"
CHECKER = CHECK_MATCH.group(1)

RX_BUTTON = (
    'echo \'<button class="button link" onclick="playAudioToggle(8080, this)">'
    '<b>&nbsp;&nbsp;&nbsp;<img src=images/speaker.png alt="" '
    'style="vertical-align:middle">&nbsp;&nbsp;RX Monitor&nbsp;&nbsp;&nbsp;</b></button>\';'
)


def run_patcher(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "-c", PATCHER, str(path)],
        check=False,
        text=True,
        capture_output=True,
    )


def run_checker(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "-c", CHECKER, str(path)],
        check=False,
        text=True,
        capture_output=True,
    )


class RxMonitorAnchorTests(unittest.TestCase):
    def test_stock_layout_keeps_existing_rx_monitor_anchor_behavior(self) -> None:
        source = (
            '<div class="content"><center>\n'
            '<div style="margin-top:8px;">\n<?php\n'
            'if ( RXMONITOR == "YES" ) {\n'
            + RX_BUTTON
            + '}\n?>\n</div>\n</center></div>\n<?php\nfunction nextSection() {}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.php"
            target.write_text(source)
            result = run_patcher(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = target.read_text()
        self.assertIn("<!-- DVSwitch-Mode-Buttons 1.0.0-test48 -->", installed)
        self.assertIn('id="dvs-target-tuner"', installed)
        self.assertIn('id="dvs-favorites"', installed)
        self.assertLess(installed.index("dvs-mode-buttons"), installed.index('<div style="margin-top:8px;">'))

    def test_check_accepts_both_supported_layouts(self) -> None:
        fixtures = (
            '<div class="content"><center>\n<div style="margin-top:8px;">RX Monitor</div>\n</center></div>\n',
            '<div class="content"><center>\n\n</center></div>\n'
            '// DVSwitch-Mods: RX Monitor left of status v1\n'
            'echo \'<div style="margin-top:8px;text-align:center;">\';\n'
            'if ( RXMONITOR == "YES" ) {\n' + RX_BUTTON + '\n',
        )
        for source in fixtures:
            with self.subTest(source=source[:40]), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "index.php"
                target.write_text(source)
                result = run_checker(target)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_accepts_installed_test14_controls_in_moved_layout(self) -> None:
        source = (
            '<div class="content"><center>\n'
            '<!-- DVSwitch-Mode-Buttons 1.0.0-test14 -->\n'
            '<div id="dvs-mode-buttons">installed controls</div>\n'
            '<script>installed()</script>\n'
            '</center></div>\n'
            '// DVSwitch-Mods: RX Monitor left of status v1\n'
            'echo \'<div style="margin-top:8px;text-align:center;">\';\n'
            'if ( RXMONITOR == "YES" ) {\n' + RX_BUTTON + '\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.php"
            target.write_text(source)
            result = run_checker(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: relocated RX Monitor layout", result.stdout)

    def test_check_accepts_test45_through_test48_controls(self) -> None:
        for version in (45, 46, 47, 48):
            source = (
                '<div class="content"><center>\n'
                f'<!-- DVSwitch-Mode-Buttons 1.0.0-test{version} -->\n'
                '<div id="dvs-mode-buttons">installed controls</div>\n'
                '<script>installed()</script>\n'
                '<div style="margin-top:8px;">RX Monitor</div>\n'
                '</center></div>\n'
            )
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "index.php"
                target.write_text(source)
                result = run_checker(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS: original RX Monitor button anchor", result.stdout)

    def test_check_rejects_unknown_layout_without_changes(self) -> None:
        source = '<div class="content"><center>custom layout</center></div>\n'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.php"
            target.write_text(source)
            result = run_checker(target)
            after = target.read_text()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(after, source)

    def test_mods_moved_layout_uses_vacated_center_and_is_idempotent(self) -> None:
        source = (
            '<div class="content"><center>\n\n</center></div>\n<?php\n'
            '    // DVSwitch-Mods: RX Monitor left of status v1\n'
            '    echo \'<div style="margin-top:8px;text-align:center;">\';\n'
            '    if ( RXMONITOR == "YES" ) {\n    ' + RX_BUTTON + '\n'
            '    }\n    echo \'</div>\';\nfunction nextSection() {}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.php"
            target.write_text(source)
            first = run_patcher(target)
            self.assertEqual(first.returncode, 0, first.stderr)
            second = run_patcher(target)
            self.assertEqual(second.returncode, 0, second.stderr)
            installed = target.read_text()
        self.assertEqual(installed.count("<!-- DVSwitch-Mode-Buttons 1.0.0-test48 -->"), 1)
        self.assertEqual(installed.count("// DVSwitch-Mods: RX Monitor left of status v1"), 1)
        self.assertLess(installed.index("dvs-mode-buttons"), installed.index("</center>"))
        self.assertIn("playAudioToggle(8080, this)", installed)

    def test_incomplete_relocation_is_refused_without_changing_file(self) -> None:
        source = '<div class="content"><center>\n\n</center></div>\n<?php\n'
        source += "// DVSwitch-Mods: RX Monitor left of status v1\nfunction nextSection() {}\n"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.php"
            target.write_text(source)
            result = run_patcher(target)
            after = target.read_text()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("relocation block is incomplete", result.stderr)
        self.assertEqual(after, source)

    def test_test8_buttons_upgrade_in_place_when_rx_monitor_was_moved(self) -> None:
        source = (
            '<div class="content"><center>\n\n</center></div>\n'
            '<!-- DVSwitch-Mode-Buttons 1.0.0-test8 -->\n'
            '<div id="old-buttons">old</div><script>old()</script>\n<?php\n'
            '    // DVSwitch-Mods: RX Monitor left of status v1\n'
            '    echo \'<div style="margin-top:8px;text-align:center;">\';\n'
            '    if ( RXMONITOR == "YES" ) {\n    ' + RX_BUTTON + '\n'
            '    }\n    echo \'</div>\';\nfunction nextSection() {}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.php"
            target.write_text(source)
            result = run_patcher(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = target.read_text()
        self.assertNotIn("1.0.0-test8", installed)
        self.assertEqual(installed.count("1.0.0-test48"), 1)
        self.assertNotIn("old-buttons", installed)

    def test_test43_dashboard_marker_upgrades_to_test48(self) -> None:
        source = (
            '<div class="content"><center>\n'
            '<!-- DVSwitch-Mode-Buttons 1.0.0-test43 -->\n'
            '<div id="dvs-mode-buttons">old controls</div>\n'
            '<script src="/dvswitch/dvswitch-mode-favorites.js"></script>\n'
            '<div style="margin-top:8px;">RX Monitor</div>\n'
            '</center></div>\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.php"
            target.write_text(source)
            result = run_patcher(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = target.read_text()
        self.assertNotIn("1.0.0-test43", installed)
        self.assertEqual(installed.count("1.0.0-test48"), 1)
        self.assertEqual(installed.count('id="dvs-target-tuner"'), 1)

    def test_test44_dashboard_marker_upgrades_to_test48(self) -> None:
        source = (
            '<div class="content"><center>\n'
            '<!-- DVSwitch-Mode-Buttons 1.0.0-test44 -->\n'
            '<div id="dvs-mode-buttons">old controls</div>\n'
            '<script src="/dvswitch/dvswitch-mode-favorites.js"></script>\n'
            '<div style="margin-top:8px;">RX Monitor</div>\n'
            '</center></div>\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "index.php"
            target.write_text(source)
            result = run_patcher(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = target.read_text()
        self.assertNotIn("1.0.0-test44", installed)
        self.assertEqual(installed.count("1.0.0-test48"), 1)
        self.assertIn('<dialog class="dvs-favorites-editor"', installed)

    def test_test45_through_test47_markers_upgrade_in_place_to_test48(self) -> None:
        for old_version in (45, 46, 47):
            source = (
                '<div class="content"><center>\n'
                f'<!-- DVSwitch-Mode-Buttons 1.0.0-test{old_version} -->\n'
                '<div id="dvs-mode-buttons">old controls</div>\n'
                '<script src="/dvswitch/dvswitch-mode-favorites.js"></script>\n'
                '<div style="margin-top:8px;">RX Monitor</div>\n'
                '</center></div>\n'
            )
            with self.subTest(old_version=old_version), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "index.php"
                target.write_text(source)
                result = run_patcher(target)
                self.assertEqual(result.returncode, 0, result.stderr)
                installed = target.read_text()
            self.assertNotIn(f"1.0.0-test{old_version}", installed)
            self.assertEqual(installed.count("1.0.0-test48"), 1)
            self.assertIn('<strong>Cancel or Esc</strong>', installed)
            self.assertIn('Cancel / Close</button>', installed)

if __name__ == "__main__":
    unittest.main()
