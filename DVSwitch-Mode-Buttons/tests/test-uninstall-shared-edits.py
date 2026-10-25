#!/usr/bin/env python3
"""Verify uninstall removes only recognized Mode Buttons shared-file edits."""

from __future__ import annotations

import re
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "dvswitch-mode-buttons.sh"
MANAGER_TEXT = MANAGER.read_text()
MATCH = re.search(
    r"<<'PY_BUTTONS_UNINSTALL'[^\n]*\n(.*?)^PY_BUTTONS_UNINSTALL$",
    MANAGER_TEXT,
    re.MULTILINE | re.DOTALL,
)
assert MATCH, "embedded uninstall program is missing"
PATCH = types.ModuleType("buttons_uninstall_test")
exec(compile(MATCH.group(1), str(MANAGER), "exec"), PATCH.__dict__)


def php_function(name: str) -> str:
    return f"function {name}($value) {{\n        return $value;\n}}\n"


def status_fixture(with_mods: bool = True) -> str:
    names = (
        "dvsButtonsDmrNetwork",
        "dvsButtonsDmrTalkgroup",
        "dvsButtonsDmrName",
        "dvsButtonsDmrMasterHeading",
        "dvsButtonsDmrMasterDisplay",
        "dvsButtonsDmrSavedCardMode",
        "dvsButtonsDmrSavedNetwork",
        "dvsButtonsDmrCurrentMode",
        "dvsButtonsDmrSavedTalkgroup",
    )
    helper = "\n".join(php_function(name) for name in names)
    mods = ""
    if with_mods:
        mods = php_function("dvsModsDmrMasterHeading") + php_function("dvsModsDmrMasterDisplay")
    return (
        "<?php\ninclude_once dirname(dirname(__FILE__)).'/include/functions.php';\n"
        + "// DVSwitch-Mode-Buttons: standalone DMR Master display v8\n"
        + "\n"
        + helper
        + "// DVSwitch-Mods: P25/NXDN friendly names remain present\n"
        + mods
        + "?>\n"
        + PATCH.BUTTONS_HEADING
        + "\n"
        + PATCH.BUTTONS_OUTPUT
        + "\n"
        + PATCH.BUTTONS_CONNECTING_CONDITION
        + " {\n"
        + PATCH.BUTTONS_CONNECTING_OUTPUT
        + "\n}\n"
    )


class SharedFileUninstallTests(unittest.TestCase):
    def test_manager_uninstall_uses_structural_cleanup_without_snapshot_restore(self) -> None:
        manager = (ROOT / "dvswitch-mode-buttons.sh").read_text()

        cleanup_at = manager.index("PY_BUTTONS_UNINSTALL")
        delete_at = manager.index('rm -f "$MODE_HELPER"')
        self.assertLess(cleanup_at, delete_at)
        self.assertIn('backup "$STATUS_TARGET"', manager)
        self.assertIn('backup /opt/MMDVM_Bridge/dvswitch.sh', manager)
        self.assertNotIn("latest_status", manager)
        self.assertNotIn("latest_bridge", manager)

    def test_removes_buttons_helpers_and_restores_mods_rows(self) -> None:
        original = status_fixture()
        cleaned, changed = PATCH.patch_status(original)

        self.assertTrue(changed)
        self.assertNotIn("standalone DMR Master display v8", cleaned)
        self.assertNotIn("dvsButtonsDmrMasterHeading(", cleaned)
        self.assertNotIn("dvsButtonsDmrMasterDisplay($dmrMasterHost, $abinfo, true)", cleaned)
        self.assertIn(PATCH.NOT_CONNECTED_ROW, cleaned)
        self.assertIn(PATCH.LEGACY_CONNECTING_CONDITION, cleaned)
        self.assertIn("DVSwitch-Mods: P25/NXDN friendly names remain present", cleaned)
        self.assertIn("function dvsModsDmrMasterHeading(", cleaned)
        self.assertIn("function dvsModsDmrMasterDisplay(", cleaned)
        self.assertIn(PATCH.MODS_HEADING, cleaned)
        self.assertIn(PATCH.MODS_OUTPUT, cleaned)
        self.assertEqual(PATCH.patch_status(cleaned), (cleaned, False))

    def test_restores_factory_rows_when_no_mods_dmr_helper_exists(self) -> None:
        cleaned, changed = PATCH.patch_status(status_fixture(with_mods=False))

        self.assertTrue(changed)
        self.assertIn(PATCH.FACTORY_HEADING, cleaned)
        self.assertIn(PATCH.FACTORY_OUTPUT, cleaned)

    def test_removes_only_the_marked_bridge_block(self) -> None:
        bridge = "# DVSwitch-Mods: updater remains\n" + PATCH.BRIDGE_BLOCK + "\n# local customization\n"
        cleaned, changed = PATCH.patch_bridge(bridge)

        self.assertTrue(changed)
        self.assertEqual(
            cleaned,
            "# DVSwitch-Mods: updater remains\n" + PATCH.BRIDGE_ORIGINAL + "\n# local customization\n",
        )

    def test_removes_test13_bridge_block_during_upgrade_or_uninstall(self) -> None:
        bridge = "# DVSwitch-Mods: updater remains\n" + PATCH.BRIDGE_BLOCK_TEST13 + "\n# local customization\n"
        cleaned, changed = PATCH.patch_bridge(bridge)

        self.assertTrue(changed)
        self.assertEqual(
            cleaned,
            "# DVSwitch-Mods: updater remains\n" + PATCH.BRIDGE_ORIGINAL + "\n# local customization\n",
        )

    def test_removes_only_the_mode_button_index_script(self) -> None:
        index = (
            "<html><body>keep this<!-- DVSwitch-Mode-Buttons 1.0.0-test8 -->"
            "<script>buttons()</script>keep this too</body></html>"
        )

        cleaned, changed = PATCH.patch_index(index)

        self.assertTrue(changed)
        self.assertEqual(cleaned, "<html><body>keep thiskeep this too</body></html>")

    def test_duplicate_index_markers_are_refused(self) -> None:
        index = PATCH.INDEX_MARKER + "<script>x</script>" + PATCH.INDEX_MARKER + "<script>x</script>"

        with self.assertRaises(PATCH.UnsafeStructure):
            PATCH.patch_index(index)

    def test_ambiguous_status_state_is_refused_without_mutation(self) -> None:
        ambiguous = status_fixture().replace(PATCH.BUTTONS_HEADING, "unsupported heading", 1)

        with self.assertRaises(PATCH.UnsafeStructure):
            PATCH.patch_status(ambiguous)


if __name__ == "__main__":
    unittest.main()
