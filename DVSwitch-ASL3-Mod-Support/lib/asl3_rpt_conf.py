#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Find the USRP-backed ASL node and safely install link event hooks."""

from __future__ import annotations

import argparse
import os
import re
import stat
import tempfile
from pathlib import Path

NODE_HEADER = re.compile(rb"\[\s*(\d{1,8})\s*\]\s*(?:\([^)]*\))?\s*$")
ANY_HEADER = re.compile(rb"\[.*\]")
CHANNEL = re.compile(rb"^\s*rxchannel\s*=\s*usrp(?:/|\s|$)", re.I)
MARKER = b"; DVSwitch-ASL3-Mod-Support: activity hooks v1"


def clean_line(raw: bytes) -> bytes:
    return raw.split(b";", 1)[0].split(b"#", 1)[0].strip()


def node_sections(data: bytes) -> list[tuple[str, int, int, bytes]]:
    lines = data.splitlines(keepends=True)
    sections: list[tuple[str, int, int]] = []
    current_node: str | None = None
    start: int | None = None
    for index, raw in enumerate(lines):
        content = clean_line(raw)
        if not ANY_HEADER.match(content):
            continue
        if current_node is not None and start is not None:
            sections.append((current_node, start, index))
        header = NODE_HEADER.fullmatch(content)
        current_node = header.group(1).decode("ascii") if header else None
        start = index
    if current_node is not None and start is not None:
        sections.append((current_node, start, len(lines)))
    result = []
    for node, first, last in sections:
        block = b"".join(lines[first:last])
        if any(CHANNEL.match(clean_line(line)) for line in lines[first:last]):
            result.append((node, first, last, block))
    return result


def find_local_node(data: bytes) -> str:
    matches = node_sections(data)
    if len(matches) != 1:
        raise ValueError(f"expected one numeric node stanza with rxchannel=USRP; found {len(matches)}")
    return matches[0][0]


def install_hooks(path: Path, helper: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"rpt.conf is not a regular file: {path}")
    original = path.read_bytes()
    node = find_local_node(original)
    rows = node_sections(original)
    _, first, last, block = next(item for item in rows if item[0] == node)
    conn = f"connpgm = {helper} CONNECTED".encode()
    disc = f"discpgm = {helper} DISCONNECTED".encode()
    if MARKER in block:
        if block.count(MARKER) != 1 or block.count(conn) != 1 or block.count(disc) != 1:
            raise ValueError("partial or duplicate ASL activity hooks")
        return node
    active = [line for line in block.splitlines() if re.match(rb"^\s*(?:connpgm|discpgm)\s*=", clean_line(line), re.I)]
    if active:
        raise ValueError("ASL node already defines connpgm/discpgm; refusing to overwrite existing hooks")

    newline = b"\r\n" if b"\r\n" in original else b"\n"
    lines = original.splitlines(keepends=True)
    insertion = last
    while insertion > first and not lines[insertion - 1].strip():
        insertion -= 1
    block_lines = [MARKER + newline, conn + newline, disc + newline]
    if insertion < len(lines) or (insertion and not lines[insertion - 1].endswith((b"\n", b"\r"))):
        block_lines.append(newline)
    lines[insertion:insertion] = block_lines
    updated = b"".join(lines)
    info = path.stat()
    fd, temporary = tempfile.mkstemp(prefix=".rpt.conf.asl3-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
        os.chown(temporary, info.st_uid, info.st_gid)
        os.chmod(temporary, stat.S_IMODE(info.st_mode))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return node


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "node"))
    parser.add_argument("rpt_conf", type=Path)
    parser.add_argument("helper", nargs="?")
    args = parser.parse_args()
    try:
        if args.action == "node":
            print(find_local_node(args.rpt_conf.read_bytes()))
        elif args.action == "check":
            print(f"ASL local DVSwitch bridge node: {find_local_node(args.rpt_conf.read_bytes())}")
        else:
            if not args.helper:
                raise ValueError("--install requires the installed link-event helper path")
            print(f"ASL link activity hooks installed for node {install_hooks(args.rpt_conf, args.helper)}")
    except (OSError, ValueError, StopIteration) as error:
        raise SystemExit(f"ERROR: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
