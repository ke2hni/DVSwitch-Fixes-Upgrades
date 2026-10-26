#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Test the ASL Net cell patch against stock and STFU-modified dashboard layouts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("asl3_dashboard_layout", ROOT / "lib" / "patch_asl3_dashboard_layout.py")
assert SPEC and SPEC.loader
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)

FUNCTION = b"$rawuptime = shell_exec('cat /proc/uptime');"
DSTAR = b'<?php showMode("D-Star Network", $mmdvmconfigs);?>'
STFU = b'<?php dvsModsShowSTFUStatus("STFU Net");?>'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


for ending in (b"</tr>", STFU + b"</tr>"):
    source = b"<?php\n" + FUNCTION + b"\n" + DSTAR + ending + b"\n?>\n"
    result = PATCHER.patch_text(source)
    require(result.count(PATCHER.MARKER) == 1, "ASL status function marker is missing")
    require(result.count(PATCHER.cell_block()) == 1, "ASL status cell is missing")
    require(result.index(DSTAR) < result.index(PATCHER.cell_block()), "ASL Net is not after D-Star Network")
    require(PATCHER.patch_text(result) == result, "ASL layout patch is not idempotent")
    require(PATCHER.unpatch_text(result) == source, "ASL layout restore did not recover the original")

crlf = b"<?php\r\n" + FUNCTION + b"\r\n" + DSTAR + b"</tr>\r\n?>\r\n"
require(PATCHER.unpatch_text(PATCHER.patch_text(crlf)) == crlf, "CRLF dashboard restore failed")
for source in (b"missing anchors", b"<?php\n" + FUNCTION + b"\n" + DSTAR + DSTAR + b"</tr>"):
    try:
        PATCHER.patch_text(source)
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported or ambiguous dashboard structure was accepted")

js = (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8")
require("dvswitch-asl3-net-status" in PATCHER.function_block(b"\n").decode(), "status cell ID is missing")
require("setTargetLabel" in js and "setAslNetworkState" in js, "dashboard label/state integration is missing")
print("PASS: ASL Net cell installs after D-Star with or without STFU, restores exactly, and rejects ambiguous layouts")
