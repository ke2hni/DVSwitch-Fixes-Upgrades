#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Add the ASL Net card to the dashboard's left status column."""

from __future__ import annotations

import argparse
import os
import re
import stat
import tempfile
from pathlib import Path

MARKER = b"// DVSwitch-ASL3-Mod-Support: ASL Net card v1"
CARD_CALL = b"include_once dirname(__FILE__).'/dvswitch-asl3-net-card.php'; dvswitchASL3ShowNetCard();"
LEGACY_MARKER = b"// DVSwitch-ASL3-Mod-Support: ASL Net status cell v1"
LEGACY_CELL = b'<?php dvswitchASL3ShowNetStatus();?>'


def patch_text(data: bytes) -> bytes:
    if data.count(MARKER) == 1 and data.count(CARD_CALL) == 1:
        return data
    if MARKER in data or CARD_CALL in data:
        raise ValueError("partial or ambiguous ASL Net card patch found")
    if data.count(b'echo "<tr><th colspan=\\"2\\">D-Star Net</th></tr>\\n";') != 1:
        raise ValueError("expected the dashboard status-card section ending after D-Star Net")
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    anchor = b"?>" + newline + b"</fieldset>"
    marker = MARKER + newline
    call = CARD_CALL + newline
    if data.count(anchor) != 1:
        raise ValueError("expected one dashboard status-card section ending")
    result = data.replace(anchor, marker + call + anchor, 1)
    if result.count(MARKER) != 1 or result.count(CARD_CALL) != 1:
        raise ValueError("ASL Net card patch verification failed")
    return result


def unpatch_text(data: bytes) -> bytes:
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    block = MARKER + newline + CARD_CALL + newline
    if data.count(MARKER) == 0 and data.count(CARD_CALL) == 0:
        return data
    if data.count(block) != 1:
        raise ValueError("partial or ambiguous ASL Net card patch found")
    return data.replace(block, b"", 1)


def remove_legacy_cell(data: bytes) -> bytes:
    if LEGACY_MARKER not in data and LEGACY_CELL not in data:
        return data
    if data.count(LEGACY_MARKER) != 1 or data.count(LEGACY_CELL) != 1:
        raise ValueError("partial or ambiguous legacy ASL Net status cell found")
    pattern = re.compile(
        rb"// DVSwitch-ASL3-Mod-Support: ASL Net status cell v1\r?\n"
        rb"if \(!function_exists\('dvswitchASL3ShowNetStatus'\)\) \{\r?\n"
        rb"    function dvswitchASL3ShowNetStatus\(\) \{\r?\n"
        rb"        echo \"<td id=\\\"dvswitch-asl3-net-status\\\" style=\\\"background:#b00;color:#f9f9f9;width:8%;\\\">&nbsp;ASL Net&nbsp;</td>\\n\";\r?\n"
        rb"    \}\r?\n\}\r?\n"
    )
    result, count = pattern.subn(b"", data)
    if count != 1:
        raise ValueError("legacy ASL Net function changed; refusing to remove it")
    result = result.replace(LEGACY_CELL, b"", 1)
    return result


def atomic_write(path: Path, data: bytes) -> None:
    info = path.stat()
    fd, raw = tempfile.mkstemp(prefix="." + path.name + ".asl3-", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chown(temporary, info.st_uid, info.st_gid)
        os.chmod(temporary, stat.S_IMODE(info.st_mode))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "uninstall"))
    parser.add_argument("target", type=Path, help="dashboard include/status.php")
    args = parser.parse_args()
    if args.target.is_symlink() or not args.target.is_file():
        raise SystemExit(f"ERROR: dashboard target is not a regular file: {args.target}")
    system_file = args.target.with_name("system.php")
    if system_file.is_symlink() or not system_file.is_file():
        raise SystemExit(f"ERROR: dashboard system include is not a regular file: {system_file}")
    status_before = args.target.read_bytes()
    system_before = system_file.read_bytes()
    try:
        status_after = unpatch_text(status_before) if args.action == "uninstall" else patch_text(status_before)
        system_after = remove_legacy_cell(system_before)
    except ValueError as error:
        raise SystemExit(f"ERROR: {error}") from error
    if args.action == "check":
        print("ALREADY INSTALLED" if status_after == status_before and MARKER in status_before and system_after == system_before else "READY")
        print("PASS: ASL Net card layout is supported; no files changed.")
    else:
        if status_after != status_before:
            atomic_write(args.target, status_after)
        if system_after != system_before:
            atomic_write(system_file, system_after)
        if args.action == "install":
            print("PASS: ASL Net card installed in the left dashboard status column.")
        else:
            print("PASS: ASL Net card removed and legacy status cell cleaned up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
