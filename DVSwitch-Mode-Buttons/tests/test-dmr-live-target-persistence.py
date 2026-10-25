#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Exercise the installer upgrade from a v7 DMR card with varied helper formatting."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text()


def embedded_python() -> str:
    install_call = INSTALLER.index("\n./install-standalone-dmr-master-card.sh\n")
    start = INSTALLER.index("python3 - <<'PY'\n", install_call)
    end = INSTALLER.index("\nPY\n", start)
    code = INSTALLER[start + len("python3 - <<'PY'\n"):end]
    return code.replace(
        "path = Path('/usr/share/dvswitch/include/status.php')",
        "path = Path(os.environ['STATUS_CANDIDATE'])",
    )


def literal_assignment(tree: ast.Module, wanted: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == wanted for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing installer template: {wanted}")


def main() -> None:
    code = embedded_python()
    tree = ast.parse(code)
    not_connected_row = literal_assignment(tree, "not_connected_row")
    helpers = (
        "dvsButtonsDmrNetwork", "dvsButtonsDmrTalkgroup", "dvsButtonsDmrName",
        "dvsButtonsDmrSavedCardMode", "dvsButtonsDmrSavedNetwork",
        "dvsButtonsDmrCurrentMode", "dvsButtonsDmrSavedTalkgroup",
        "dvsButtonsDmrRememberTalkgroup",
    )
    with tempfile.TemporaryDirectory() as directory:
        for index, display in enumerate((
            """function dvsButtonsDmrMasterDisplay($master, $abinfo) {
        $mode = 'STFU';
        $network = ($mode === 'STFU') ? 'BM' : dvsButtonsDmrNetwork($master);
        $talkgroup = dvsButtonsDmrTalkgroup($abinfo);
        $name = dvsButtonsDmrName($network, $talkgroup);
        $display = ($name !== '') ? $name : 'TG '.$talkgroup;
        return htmlspecialchars($display, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}""",
            """function dvsButtonsDmrMasterDisplay($master, $abinfo) {
        $liveMode = dvsButtonsDmrCurrentMode($abinfo);
        $isDmrMode = in_array($liveMode, array('DMR', 'BM', 'TGIF', 'STFU'), true);
        $network = ($liveMode === 'STFU') ? 'BM' : dvsButtonsDmrNetwork($master);
        $talkgroup = $isDmrMode ? dvsButtonsDmrTalkgroup($abinfo) : dvsButtonsDmrSavedTalkgroup();
        if ($isDmrMode && $talkgroup !== '') { dvsButtonsDmrRememberTalkgroup($talkgroup); }
        $name = dvsButtonsDmrName($network, $talkgroup);
        $display = ($name !== '') ? $name : 'TG '.$talkgroup;
        return htmlspecialchars($display, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}""",
        )):
            fixture = "<?php\ninclude_once dirname(dirname(__FILE__)).'/include/functions.php';\n"
            fixture += "// DVSwitch-Mode-Buttons: standalone DMR Master display v7\n"
            fixture += "".join(f"function {name}($value) {{ return ''; }}\n" for name in helpers)
            fixture += "function dvsButtonsDmrMasterHeading($master, $abinfo) {\n"
            fixture += "        $saved = dvsButtonsDmrSavedCardMode();\n"
            fixture += "        if ($saved === 'STFU') { return 'DMR STFU Master'; }\n"
            fixture += "        return 'DMR '.dvsButtonsDmrNetwork($master).' Master';\n}\n"
            fixture += display + "\n?>\n"
            fixture += "if (strpos($dmrstat, 'Logged') !== false) { echo 'logged'; }\n"
            fixture += "else if (strpos($dmrstat, 'Opening') !== false || strpos($dmrstatus, 'Closing') !== false || strpos($dmrstatus, 'Connection') !== false) {\n"
            fixture += "    " + not_connected_row + "\n}\n"

            candidate = Path(directory) / f"status-{index}.php"
            candidate.write_text(fixture)
            environment = os.environ.copy()
            environment["STATUS_CANDIDATE"] = str(candidate)
            subprocess.run([sys.executable, "-c", code], env=environment, check=True, capture_output=True, text=True)
            upgraded = candidate.read_text()
            assert "standalone DMR Master display v9" in upgraded
            assert "function dvsButtonsDmrRememberTalkgroup(" in upgraded
            assert "function dvsButtonsDmrPendingTarget(" in upgraded
            assert "dvsButtonsDmrPendingTarget()" in upgraded
            assert "dvsButtonsDmrMasterDisplay($master, $abinfo, $connecting = false)" in upgraded
            assert "in_array($liveMode, array('DMR', 'BM', 'TGIF'), true)" in upgraded
            current_mode = upgraded.split("function dvsButtonsDmrCurrentMode(", 1)[1].split("\n}", 1)[0]
            assert "selectedModeFile" in current_mode
            assert current_mode.index("$mode === 'DMR'") > current_mode.index("$selectedMode =")
            assert "in_array($selectedMode, array('BM', 'TGIF', 'STFU'), true)" in current_mode
            assert "DMR STFU Master" not in upgraded
            assert "array('DMR', 'BM', 'TGIF', 'STFU')" not in upgraded
            assert "dvs-dmr-connection-state" in upgraded
            assert "dvsButtonsDmrMasterDisplay($dmrMasterHost, $abinfo, true)" in upgraded
            assert "(TG '.htmlspecialchars($talkgroup" in upgraded
            assert "strpos($dmrstatus" not in upgraded
            assert ">Not Connected</span>" not in upgraded
            subprocess.run([sys.executable, "-c", code], env=environment, check=True, capture_output=True, text=True)
            assert candidate.read_text() == upgraded, "v7-to-current DMR card upgrade is not idempotent"

            if shutil.which("php"):
                helper_region = upgraded[upgraded.index("// DVSwitch-Mode-Buttons: standalone DMR Master display v9"):]
                helper_region = helper_region.split("?>", 1)[0]
                state_file = Path(directory) / f"current-mode-{index}"
                state_file.write_text("STFU\n", encoding="utf-8")
                php_program = "<?php\n" + helper_region + f"\necho dvsButtonsDmrCurrentMode(array('tlv' => array('ambe_mode' => 'DMR')), {str(state_file)!r});\n?>"
                result = subprocess.run(["php"], input=php_program, text=True, capture_output=True, check=True)
                assert result.stdout.endswith("STFU"), f"DMR ABInfo overrode selected STFU mode: {result.stdout!r}"

                pending_file = Path(directory) / f"pending-target-{index}"
                saved_file = Path(directory) / f"saved-target-{index}"
                pending_region = helper_region.replace(
                    "/var/lib/dvswitch-mode-buttons/current-mode", str(state_file)
                ).replace(
                    "/var/lib/dvswitch-mode-buttons/dmr-tune-pending", str(pending_file)
                ).replace(
                    "/var/lib/dvswitch-mode-buttons/last-dmr-talkgroup", str(saved_file)
                )
                pending_program = "<?php\n" + pending_region + f"\nfile_put_contents({str(state_file)!r}, 'P25');\nfile_put_contents({str(saved_file)!r}, '7941');\nfile_put_contents({str(pending_file)!r}, 'TGIF 12345 '.time());\necho dvsButtonsDmrMasterDisplay('tgif.network', array('tlv' => array('ambe_mode' => 'DMR'), 'last_tune' => '7941', 'digital' => array('tg' => '7941')));\n?>"
                result = subprocess.run(["php"], input=pending_program, text=True, capture_output=True, check=True)
                assert "TG 12345" in result.stdout and "7941" not in result.stdout, (
                    f"DMR card rejected pending TGIF target while saved mode was still P25: {result.stdout!r}"
                )

    print("PASS: DMR card upgrades to v9, preserves BM/TGIF state during STFU, and stays idempotent")


if __name__ == "__main__":
    main()
