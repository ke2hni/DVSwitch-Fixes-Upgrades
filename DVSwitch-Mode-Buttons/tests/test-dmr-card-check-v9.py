#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Verify --check accepts the current v9 DMR card and still rejects bad rows."""

from pathlib import Path
import ast
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text(encoding="utf-8")
start = INSTALLER.index('python3 - "$STATUS_TARGET" <<\'PY_DMR_CARD_CHECK\'\n')
end = INSTALLER.index("\nPY_DMR_CARD_CHECK", start)
CHECK = INSTALLER[start:].split("\n", 1)[1][:end - start - len("python3 - \"$STATUS_TARGET\" <<'PY_DMR_CARD_CHECK'\n")]

CONNECTING = r'''echo "<tr><td  style=\"background: #ffffed;\" colspan=\"2\"><span style=\"color:#b5651d;font-weight: bold;white-space:normal;word-break:normal;overflow-wrap:anywhere;text-align:center;\">".dvsButtonsDmrMasterDisplay($dmrMasterHost, $abinfo, true)."</span></td></tr>\n";'''
NOT_CONNECTED = r'''echo "<tr><td  style=\"background: #ffffed;\" colspan=\"2\"><span style=\"color:#b0b0b0;font-weight: bold\">Not Connected</span></td></tr>\n";'''
tree = ast.parse(CHECK)
rows = {
    node.targets[0].id: ast.literal_eval(node.value)
    for node in ast.walk(tree)
    if isinstance(node, ast.Assign)
    and len(node.targets) == 1
    and isinstance(node.targets[0], ast.Name)
    and node.targets[0].id in {"connecting_row", "not_connected_row"}
}
CONNECTING = rows["connecting_row"]
NOT_CONNECTED = rows["not_connected_row"]
STATUS = """<?php
// DVSwitch-Mode-Buttons: standalone DMR Master display v{version}
strpos($dmrstat, 'Opening') !== false;
strpos($dmrstat, 'Closing') !== false;
strpos($dmrstat, 'Connection') !== false;
{row}
{extras}
?>
"""

with tempfile.TemporaryDirectory() as directory:
    status = Path(directory) / "status.php"
    for version, row, extras in (
        ("1", NOT_CONNECTED, ""),
        ("9", CONNECTING, "dvs-dmr-connection-state"),
    ):
        status.write_text(STATUS.format(version=version, row=row, extras=extras), encoding="utf-8")
        result = subprocess.run([sys.executable, "-c", CHECK, str(status)], text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert "PASS: DMR card can be upgraded safely" in result.stdout

    status.write_text(STATUS.format(version="9", row=NOT_CONNECTED, extras=""), encoding="utf-8")
    result = subprocess.run([sys.executable, "-c", CHECK, str(status)], text=True, capture_output=True)
    assert result.returncode != 0, "v9 card with the wrong connection row was accepted"
    assert "state-aware DMR connecting card structure is incomplete" in result.stderr

    status.write_text(
        STATUS.format(version="9", row=CONNECTING, extras="dvs-dmr-connection-state").replace(
            "dvs-dmr-connection-state", "missing-connection-state"
        ),
        encoding="utf-8",
    )
    result = subprocess.run([sys.executable, "-c", CHECK, str(status)], text=True, capture_output=True)
    assert result.returncode != 0, "v9 card without its Connecting state class was accepted"
    assert "state-aware DMR connecting card structure is incomplete" in result.stderr

print("PASS: DMR card check accepts stock v1 and current v9 rows, and rejects mismatched v9 structure")
