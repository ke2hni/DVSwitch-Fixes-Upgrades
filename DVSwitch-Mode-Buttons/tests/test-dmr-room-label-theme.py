#!/usr/bin/env python3
"""Check the DMR Room label markup and its safe upgrade path."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text()
CARD_INSTALLER = (ROOT / "install-standalone-dmr-master-card.sh").read_text()


class DmrRoomLabelThemeTest(unittest.TestCase):
    def test_installed_card_emits_semantic_label_for_named_and_fallback_rows(self):
        self.assertIn('class="dvs-dmr-room-label"', INSTALLER)
        self.assertIn('class="dvs-dmr-room-label"', CARD_INSTALLER)
        self.assertIn("if ($talkgroup === '')", CARD_INSTALLER)
        self.assertIn("function dvsButtonsDmrMasterDisplay($master, $abinfo, $connecting = false)", INSTALLER)

    def test_non_dmr_modes_use_the_saved_dmr_target(self):
        self.assertIn("dvsButtonsDmrSavedTalkgroup()", INSTALLER)
        self.assertIn("dvsButtonsDmrRememberTalkgroup($talkgroup)", INSTALLER)
        self.assertIn("dvsButtonsDmrCurrentMode($abinfo)", INSTALLER)
        self.assertIn("last-dmr-talkgroup", INSTALLER)
        self.assertIn("display v9", INSTALLER)
        self.assertIn("$isDmrMode = in_array($liveMode, array('DMR', 'BM', 'TGIF'), true);", INSTALLER)
        self.assertIn("if (!$connecting && $isDmrMode && $talkgroup !== '' && ($pendingTarget === '' || $observedTalkgroup === $pendingTarget)) { dvsButtonsDmrRememberTalkgroup($talkgroup); }", INSTALLER)
        heading = INSTALLER.split("new_heading_function = r'''", 1)[1].split("'''", 1)[0]
        self.assertNotIn("STFU", heading)
        display = INSTALLER.split("new_display_function = r'''", 1)[1].split("'''", 1)[0]
        self.assertNotIn("STFU", display)
        self.assertIn('data-mode="STFU"', INSTALLER)
        self.assertIn("return in_array($mode, array('BM', 'TGIF'), true) ? $mode : '';", INSTALLER)
        current_mode = INSTALLER.split("new_current_mode_function = r'''", 1)[1].split("'''", 1)[0]
        self.assertLess(current_mode.index("array('STFU', 'YSF', 'P25', 'NXDN', 'DSTAR')"), current_mode.index("if ($mode === 'DMR')"))
        self.assertIn("in_array($selectedMode, array('BM', 'TGIF', 'STFU'), true)", current_mode)
        self.assertIn("chown root:www-data /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup", INSTALLER)
        self.assertIn("chmod 664 /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup", INSTALLER)
        target_helper = (ROOT / "dvswitch-mode-targets").read_text()
        self.assertIn('"$STATE_DIR/last-dmr-talkgroup"', target_helper)
        self.assertIn('"$mode" == BM || "$mode" == TGIF', target_helper)
        self.assertNotIn('"$mode" == BM || "$mode" == TGIF || "$mode" == STFU', target_helper)
        self.assertIn('chown root:www-data "$last_dmr_tmp"', target_helper)
        self.assertIn('chmod 664 "$last_dmr_tmp"', target_helper)

    def test_upgrade_rewrites_marked_card_functions_structurally(self):
        self.assertIn("heading_pattern = re.compile", INSTALLER)
        self.assertIn("function_pattern = re.compile", INSTALLER)
        self.assertIn("expected exactly one DMR Master display function", INSTALLER)
        self.assertIn("expected one supported DMR Master heading function", INSTALLER)


if __name__ == "__main__":
    unittest.main()
