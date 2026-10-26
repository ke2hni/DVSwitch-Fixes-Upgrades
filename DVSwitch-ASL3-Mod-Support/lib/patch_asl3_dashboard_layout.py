#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Safely add the ASL Net status cell after the dashboard's D-Star Network cell."""

from __future__ import annotations

import argparse
import os
import stat
import tempfile
from pathlib import Path

MARKER = b"// DVSwitch-ASL3-Mod-Support: ASL Net status cell v1"
ANCHOR = b'<?php showMode("D-Star Network", $mmdvmconfigs);?>'
FUNCTION_ANCHOR = b"$rawuptime = shell_exec('cat /proc/uptime');"


def function_block(newline: bytes) -> bytes:
    lines = [
        MARKER,
        b"if (!function_exists('dvswitchASL3ShowNetStatus')) {",
        b"    function dvswitchASL3ShowNetStatus() {",
        b'        echo "<td id=\\"dvswitch-asl3-net-status\\" style=\\"background:#b00;color:#f9f9f9;width:8%;\\">&nbsp;ASL Net&nbsp;</td>\\n";',
        b"    }",
        b"}",
    ]
    return newline.join(lines)


def cell_block() -> bytes:
    return b"<?php dvswitchASL3ShowNetStatus();?>"


def patch_text(data: bytes) -> bytes:
    cell = cell_block()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    function = function_block(newline)
    if data.count(MARKER) == 1 and data.count(cell) == 1 and data.count(function) == 1:
        return data
    if MARKER in data or cell in data:
        raise ValueError("partial or ambiguous ASL dashboard layout patch found")
    if data.count(FUNCTION_ANCHOR) != 1 or data.count(ANCHOR) != 1:
        raise ValueError("expected exactly one system uptime anchor and one D-Star Network cell")
    candidate = data.replace(FUNCTION_ANCHOR, function + newline + FUNCTION_ANCHOR, 1)
    candidate = candidate.replace(ANCHOR, ANCHOR + cell, 1)
    if candidate.count(MARKER) != 1 or candidate.count(cell) != 1:
        raise ValueError("ASL dashboard layout verification failed")
    return candidate


def unpatch_text(data: bytes) -> bytes:
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    function = function_block(newline)
    cell = cell_block()
    if data.count(MARKER) == 0 and data.count(cell) == 0:
        return data
    if data.count(MARKER) != 1 or data.count(cell) != 1:
        raise ValueError("partial or ambiguous ASL dashboard layout patch found")
    if data.count(function) != 1 or data.count(ANCHOR + cell) != 1:
        raise ValueError("ASL dashboard layout changed after installation; refusing removal")
    candidate = data.replace(ANCHOR + cell, ANCHOR, 1)
    candidate = candidate.replace(function + newline, b"", 1)
    return candidate


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
    parser.add_argument("action", choices=("--check", "--install", "--uninstall"))
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    if args.target.is_symlink() or not args.target.is_file():
        raise SystemExit(f"ERROR: dashboard target is not a regular file: {args.target}")
    original = args.target.read_bytes()
    try:
        candidate = unpatch_text(original) if args.action == "--uninstall" else patch_text(original)
    except ValueError as error:
        raise SystemExit(f"ERROR: {error}") from error
    if args.action == "--check":
        print("ALREADY INSTALLED" if candidate == original and MARKER in original else "READY")
        print("PASS: ASL Net layout structure is supported; no files changed.")
    elif candidate != original:
        atomic_write(args.target, candidate)
        print("PASS: ASL Net status cell installed after D-Star Network.")
    else:
        print("PASS: ASL Net dashboard layout is already in the requested state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
