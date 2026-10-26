#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Discover local ASL nodes and safely install gateway link event hooks."""

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


def numeric_sections(data: bytes) -> list[tuple[str, int, int, bytes]]:
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
    return [(node, first, last, b"".join(lines[first:last]))
            for node, first, last in sections if node is not None]


def node_sections(data: bytes) -> list[tuple[str, int, int, bytes]]:
    return [item for item in numeric_sections(data)
            if any(CHANNEL.match(clean_line(line)) for line in item[3].splitlines())]


def find_local_node(data: bytes) -> str:
    matches = node_sections(data)
    if len(matches) != 1:
        raise ValueError(f"expected one numeric node stanza with rxchannel=USRP; found {len(matches)}")
    return matches[0][0]


def configured_nodes(data: bytes) -> list[str]:
    """Return node IDs with numeric rpt.conf stanzas, without fixed IDs."""
    return [item[0] for item in numeric_sections(data)]


def find_public_node(data: bytes) -> str:
    private_node = find_local_node(data)
    candidates = [node for node in configured_nodes(data) if node != private_node]
    if len(candidates) != 1:
        raise ValueError(f"expected one local public node stanza paired with USRP node {private_node}; found {len(candidates)} candidates")
    return candidates[0]


def install_hooks(path: Path, helper: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"rpt.conf is not a regular file: {path}")
    original = path.read_bytes()
    private_node = find_local_node(original)
    node = find_public_node(original)
    lines = original.splitlines(keepends=True)
    sections = {item[0]: item[1:3] for item in numeric_sections(original)}
    pfirst, plast = sections[private_node]
    first, last = sections[node]
    conn = f"connpgm = {helper} CONNECTED".encode()
    disc = f"discpgm = {helper} DISCONNECTED".encode()
    private_block = b"".join(lines[pfirst:plast])
    private_changed = False
    if MARKER in private_block:
        private_hooks = [clean_line(line) for line in lines[pfirst:plast]
                         if b"dvswitch-asl3-link-event" in clean_line(line)]
        if private_block.count(MARKER) != 1 or len(private_hooks) != 2:
            raise ValueError("partial or customized private-node ASL activity hooks")
        for index in range(pfirst, plast):
            content = clean_line(lines[index])
            if lines[index].strip() == MARKER or (b"dvswitch-asl3-link-event" in content and
                                      (content.startswith(b"connpgm =") or content.startswith(b"discpgm ="))):
                lines[index] = b""
                private_changed = True
    elif any(re.match(rb"^\s*(?:connpgm|discpgm)\s*=", clean_line(line), re.I)
             for line in lines[pfirst:plast]):
        raise ValueError("private ASL node has custom activity hooks; refusing to change them")
    block = b"".join(lines[first:last])
    if MARKER in block:
        if block.count(MARKER) != 1:
            raise ValueError("partial or duplicate ASL activity hooks")
        if block.count(conn) == 1 and block.count(disc) == 1:
            if private_changed:
                write_updated(path, lines)
            return node
        old_conn = [clean_line(line) for line in lines[first:last]
                    if b"dvswitch-asl3-link-event" in clean_line(line) and clean_line(line).startswith(b"connpgm =")]
        old_disc = [clean_line(line) for line in lines[first:last]
                    if b"dvswitch-asl3-link-event" in clean_line(line) and clean_line(line).startswith(b"discpgm =")]
        if len(old_conn) != 1 or len(old_disc) != 1:
            raise ValueError("partial or customized ASL activity hooks; refusing to replace them")
        for index in range(first, last):
            content = clean_line(lines[index])
            if content == old_conn[0]:
                lines[index] = lines[index].replace(content, conn, 1)
            elif content == old_disc[0]:
                lines[index] = lines[index].replace(content, disc, 1)
        write_updated(path, lines)
        return node
    active = [line for line in block.splitlines() if re.match(rb"^\s*(?:connpgm|discpgm)\s*=", clean_line(line), re.I)]
    if active:
        raise ValueError("ASL node already defines connpgm/discpgm; refusing to overwrite existing hooks")

    newline = b"\r\n" if b"\r\n" in original else b"\n"
    insertion = last
    while insertion > first and not lines[insertion - 1].strip():
        insertion -= 1
    block_lines = [MARKER + newline, conn + newline, disc + newline]
    if insertion < len(lines) or (insertion and not lines[insertion - 1].endswith((b"\n", b"\r"))):
        block_lines.append(newline)
    lines[insertion:insertion] = block_lines
    write_updated(path, lines)
    return node


def write_updated(path: Path, lines: list[bytes]) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "node", "nodes"))
    parser.add_argument("rpt_conf", type=Path)
    parser.add_argument("helper", nargs="?")
    args = parser.parse_args()
    try:
        if args.action == "node":
            print(find_local_node(args.rpt_conf.read_bytes()))
        elif args.action == "nodes":
            print("\n".join(configured_nodes(args.rpt_conf.read_bytes())))
        elif args.action == "check":
            data = args.rpt_conf.read_bytes()
            print(f"ASL private DVSwitch bridge node: {find_local_node(data)}")
            print(f"ASL local public node: {find_public_node(data)}")
        else:
            if not args.helper:
                raise ValueError("--install requires the installed link-event helper path")
            print(f"ASL link activity hooks installed for node {install_hooks(args.rpt_conf, args.helper)}")
    except (OSError, ValueError, StopIteration) as error:
        raise SystemExit(f"ERROR: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
