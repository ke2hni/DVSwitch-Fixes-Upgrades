#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Ensure STFU survives status polling when Analog_Bridge reports DMR."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text(encoding="utf-8")
match = re.search(r'install -o root -g root -m 644 /dev/stdin "\$ENDPOINT" <<\'PHP\'\n(.*?)\nPHP', INSTALLER, re.S)
assert match, "generated dashboard endpoint was not found"
endpoint = match.group(1)
start = endpoint.index("if (isset($_GET['status'])) {")
end = endpoint.index("\n}\n$mode = strtoupper", start)
status = endpoint[start:end]
assert "$mode === 'DMR'" in status
assert "'/var/lib/dvswitch-mode-buttons/current-mode'" in status
assert "$selectedMode === 'STFU'" in status
assert "$mode = 'STFU'" in status
assert status.index("if ($mode === 'DMR' && $selectedMode === 'STFU')") < status.index("echo json_encode(array('ok' => $mode !== ''")
print("PASS: dashboard status refresh retains selected STFU mode over generic DMR ABInfo")
