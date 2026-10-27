#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Test the ASL Net card patch in the dashboard's left status column."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("asl3_dashboard_layout", ROOT / "lib" / "patch_asl3_dashboard_layout.py")
assert SPEC and SPEC.loader
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)

DSTAR_CARD = b'echo "<tr><th colspan=\\"2\\">D-Star Net</th></tr>\\n";'
END = b"?>\n</fieldset>"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


for ending in (b"</tr>\n", b"STFU Net</th></tr>\n"):
    source = b"<?php\nif ($testMMDVModeDSTAR == 1) {\n " + DSTAR_CARD + b"\n" + ending + END
    result = PATCHER.patch_text(source)
    require(result.count(PATCHER.MARKER) == 1, "ASL card marker is missing")
    require(result.count(PATCHER.CARD_CALL) == 1, "ASL card call is missing")
    require(result.index(DSTAR_CARD) < result.index(PATCHER.MARKER), "ASL Net card is not after D-Star Net")
    require(PATCHER.patch_text(result) == result, "ASL card patch is not idempotent")
    require(PATCHER.unpatch_text(result) == source, "ASL card removal did not restore the original")

crlf = b"<?php\r\n " + DSTAR_CARD + b"\r\n?>\r\n</fieldset>"
require(PATCHER.unpatch_text(PATCHER.patch_text(crlf)) == crlf, "CRLF dashboard restore failed")
for source in (b"missing anchors", b"<?php\n" + DSTAR_CARD + DSTAR_CARD + END):
    try:
        PATCHER.patch_text(source)
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported or ambiguous dashboard structure was accepted")

legacy = (
    b"// DVSwitch-ASL3-Mod-Support: ASL Net status cell v1\n"
    b"if (!function_exists('dvswitchASL3ShowNetStatus')) {\n"
    b"    function dvswitchASL3ShowNetStatus() {\n"
    b'        echo "<td id=\\"dvswitch-asl3-net-status\\" style=\\"background:#b00;color:#f9f9f9;width:8%;\\">&nbsp;ASL Net&nbsp;</td>\\n";\n'
    b"    }\n}\n"
    b"<?php dvswitchASL3ShowNetStatus();?>"
)
cleaned = PATCHER.remove_legacy_cell(legacy)
require(b"dvswitchASL3ShowNetStatus" not in cleaned and cleaned == b"", "old summary-strip cell was not removed")

js = (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8")
card = (ROOT / "dvswitch-asl3-net-card.php").read_text(encoding="utf-8")
require("setTargetLabel" in js and "dvswitch-asl3-net-status" not in js, "dashboard JS must retain Node label only, not the misplaced cell")
require("dvswitch-asl3-node-links" in card and "astdb.txt" in card and "ASL Net" in card and
        "Status unavailable" in card,
        "ASL Net card must render live connection state and ASTDB friendly names")
print("PASS: ASL Net card installs after D-Star in the left status column and removes the obsolete summary cell")
