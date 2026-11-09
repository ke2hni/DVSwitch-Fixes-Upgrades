#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI
# Version: 1.0.1
# Created: 2026-10-26T13:45:14-04:00 by KE2HNI

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
USRP_CHANNEL = re.compile(rb"^\s*rxchannel\s*=\s*usrp/[^:\s]+:(\d{1,5}):(\d{1,5})\s*$", re.I)
MARKER = b"; DVSwitch-ASL3-Mod-Support: activity hooks v1"


def private_nodes(data: bytes) -> list[str]:
    """Return every numeric node stanza using a USRP channel."""
    return [item[0] for item in node_sections(data)]


def analog_bridge_ports(data: bytes) -> tuple[str, str]:
    """Read the active Analog_Bridge [USRP] txPort/rxPort pair."""
    lines = data.splitlines()
    in_usrp = False
    values: dict[str, str] = {}
    for raw in lines:
        content = raw.split(b";", 1)[0].split(b"#", 1)[0].strip()
        header = re.fullmatch(rb"\[([^]]+)\]", content)
        if header:
            in_usrp = header.group(1).strip().lower() == b"usrp"
            continue
        if not in_usrp:
            continue
        match = re.fullmatch(rb"(txPort|rxPort)\s*=\s*(\d{1,5})", content, re.I)
        if match:
            key = match.group(1).decode("ascii").lower()
            if key in values:
                raise ValueError(f"Analog_Bridge [USRP] has duplicate {key} settings")
            port = match.group(2).decode("ascii")
            if not 1 <= int(port) <= 65535:
                raise ValueError(f"Analog_Bridge {key} must be between 1 and 65535")
            values[key] = port
    if set(values) != {"txport", "rxport"}:
        raise ValueError("Analog_Bridge [USRP] must define exactly one txPort and rxPort")
    return values["txport"], values["rxport"]


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


def find_local_node(data: bytes, analog_bridge_data: bytes | None = None) -> str:
    matches = node_sections(data)
    if not matches:
        raise ValueError("expected at least one numeric node stanza with rxchannel=USRP; found 0")
    if len(matches) == 1:
        return matches[0][0]
    if analog_bridge_data is None:
        raise ValueError(f"found {len(matches)} private USRP nodes; Analog_Bridge ports are required to identify the DVSwitch node")
    tx_port, rx_port = analog_bridge_ports(analog_bridge_data)
    candidates = []
    for node, _, _, block in matches:
        channels = [USRP_CHANNEL.fullmatch(clean_line(line)) for line in block.splitlines()
                    if CHANNEL.match(clean_line(line))]
        if len(channels) != 1 or channels[0] is None:
            raise ValueError(f"private USRP node {node} has an unsupported or ambiguous rxchannel")
        remote_port, local_port = (value.decode("ascii") for value in channels[0].groups())
        # Asterisk sends to Analog_Bridge rxPort and listens on Analog_Bridge txPort.
        if (local_port, remote_port) == (tx_port, rx_port):
            candidates.append(node)
    if len(candidates) != 1:
        raise ValueError(f"Analog_Bridge ports match {len(candidates)} of {len(matches)} private USRP nodes; expected exactly one")
    return candidates[0]


def configured_nodes(data: bytes) -> list[str]:
    """Return node IDs with numeric rpt.conf stanzas, without fixed IDs."""
    return [item[0] for item in numeric_sections(data)]


def find_public_node(data: bytes) -> str:
    """Find the sole configured numeric node that is not a private USRP endpoint."""
    private = set(private_nodes(data))
    candidates = [node for node in configured_nodes(data) if node not in private]
    if len(candidates) != 1:
        raise ValueError(f"expected one local public node stanza after excluding {len(private)} private USRP nodes; found {len(candidates)} candidates")
    return candidates[0]


def install_hooks(path: Path, helper: str, analog_bridge_data: bytes | None = None) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"rpt.conf is not a regular file: {path}")
    original = path.read_bytes()
    # Select the Analog_Bridge-backed private node before removing legacy private-node hooks.
    private_node = find_local_node(original, analog_bridge_data)
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
    parser.add_argument("action", choices=("check", "install", "node", "nodes", "private-nodes", "public-node"))
    parser.add_argument("rpt_conf", type=Path)
    parser.add_argument("helper", nargs="?")
    parser.add_argument("--analog-bridge", type=Path, default=Path("/opt/Analog_Bridge/Analog_Bridge.ini"))
    args = parser.parse_args()
    try:
        analog_data = args.analog_bridge.read_bytes() if args.analog_bridge.is_file() else None
        if args.action == "node":
            print(find_local_node(args.rpt_conf.read_bytes(), analog_data))
        elif args.action == "nodes":
            print("\n".join(configured_nodes(args.rpt_conf.read_bytes())))
        elif args.action == "private-nodes":
            print("\n".join(private_nodes(args.rpt_conf.read_bytes())))
        elif args.action == "public-node":
            print(find_public_node(args.rpt_conf.read_bytes()))
        elif args.action == "check":
            data = args.rpt_conf.read_bytes()
            print(f"ASL private USRP nodes: {', '.join(private_nodes(data))}")
            print(f"ASL private DVSwitch bridge node: {find_local_node(data, analog_data)}")
            print(f"ASL local public node: {find_public_node(data)}")
        else:
            if not args.helper:
                raise ValueError("--install requires the installed link-event helper path")
            print(f"ASL link activity hooks installed for node {install_hooks(args.rpt_conf, args.helper, analog_data)}")
    except (OSError, ValueError, StopIteration) as error:
        raise SystemExit(f"ERROR: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
