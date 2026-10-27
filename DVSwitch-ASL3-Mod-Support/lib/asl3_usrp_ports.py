#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Keep Analog_Bridge USRP ports paired with the private ASL node."""

from __future__ import annotations

import argparse
import os
import re
import stat
import tempfile
from pathlib import Path

import asl3_rpt_conf


def expected_ports(rpt_data: bytes) -> tuple[str, str]:
    """Return Analog_Bridge txPort/rxPort from the private node's USRP channel."""
    matches = asl3_rpt_conf.node_sections(rpt_data)
    if len(matches) != 1:
        raise ValueError(f"expected one private USRP node; found {len(matches)}")
    channel = [
        asl3_rpt_conf.clean_line(line).decode("ascii", "strict")
        for line in matches[0][3].splitlines()
        if asl3_rpt_conf.CHANNEL.match(asl3_rpt_conf.clean_line(line))
    ]
    if len(channel) != 1:
        raise ValueError("private node USRP channel is ambiguous")
    match = re.fullmatch(r"\s*rxchannel\s*=\s*usrp/[^:\s]+:(\d{1,5}):(\d{1,5})\s*", channel[0], re.I)
    if not match:
        raise ValueError("private node USRP channel must use USRP/address:remote-port:local-port")
    remote_port, local_port = match.groups()
    if any(not 1 <= int(port) <= 65535 for port in (remote_port, local_port)):
        raise ValueError("private node USRP ports must be between 1 and 65535")
    # Asterisk sends to the remote port and listens on its local port.
    return local_port, remote_port


def config_values(data: bytes) -> tuple[bytes, list[tuple[int, re.Match[bytes]]]]:
    """Locate exactly one active USRP section and its active port settings."""
    lines = data.splitlines(keepends=True)
    sections: list[tuple[int, int]] = []
    start = None
    for index, raw in enumerate(lines):
        content = raw.split(b";", 1)[0].split(b"#", 1)[0].strip()
        header = re.fullmatch(rb"\[([^]]+)\]", content)
        if header:
            if start is not None:
                sections.append((start, index))
            start = index if header.group(1).strip().lower() == b"usrp" else None
    if start is not None:
        sections.append((start, len(lines)))
    if len(sections) != 1:
        raise ValueError(f"expected one [USRP] section in Analog_Bridge.ini; found {len(sections)}")

    port_lines: list[tuple[int, re.Match[bytes]]] = []
    for index in range(sections[0][0] + 1, sections[0][1]):
        content = lines[index].split(b";", 1)[0].split(b"#", 1)[0]
        match = re.match(rb"^(\s*)(txPort|rxPort)(\s*=\s*)(\d+)(.*)$", lines[index], re.I)
        if match:
            port_lines.append((index, match))
    for name in (b"txport", b"rxport"):
        if sum(1 for _, match in port_lines if match.group(2).lower() == name) != 1:
            raise ValueError(f"expected exactly one {name.decode()} setting in [USRP]")
    return b"".join(lines), port_lines


def apply_ports(rpt_path: Path, ini_path: Path, install: bool) -> bool:
    """Check or atomically update USRP ports; return whether bytes changed."""
    if rpt_path.is_symlink() or not rpt_path.is_file():
        raise ValueError(f"rpt.conf is not a regular file: {rpt_path}")
    if ini_path.is_symlink() or not ini_path.is_file():
        raise ValueError(f"Analog_Bridge.ini is not a regular file: {ini_path}")
    tx_port, rx_port = expected_ports(rpt_path.read_bytes())
    original = ini_path.read_bytes()
    _, port_lines = config_values(original)
    lines = original.splitlines(keepends=True)
    updated = False
    for index, match in port_lines:
        key = match.group(2).lower()
        value = tx_port if key == b"txport" else rx_port
        if match.group(4).decode("ascii") != value:
            updated = True
            newline = b"\r\n" if lines[index].endswith(b"\r\n") else b"\n" if lines[index].endswith(b"\n") else b""
            lines[index] = match.group(1) + match.group(2) + match.group(3) + value.encode("ascii") + match.group(5).removesuffix(newline) + newline
    if not updated or not install:
        return updated

    info = ini_path.stat()
    fd, temporary = tempfile.mkstemp(prefix=".Analog_Bridge.ini.asl3-", dir=ini_path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(b"".join(lines))
            output.flush()
            os.fsync(output.fileno())
        os.chown(temporary, info.st_uid, info.st_gid)
        os.chmod(temporary, stat.S_IMODE(info.st_mode))
        os.replace(temporary, ini_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install"))
    parser.add_argument("rpt_conf", type=Path)
    parser.add_argument("analog_bridge_ini", type=Path)
    args = parser.parse_args()
    try:
        changed = apply_ports(args.rpt_conf, args.analog_bridge_ini, args.action == "install")
        if changed and args.action == "check":
            tx_port, rx_port = expected_ports(args.rpt_conf.read_bytes())
            print(f"NEEDS REPAIR: Analog_Bridge USRP ports should be txPort={tx_port}, rxPort={rx_port}.")
        elif changed:
            tx_port, rx_port = expected_ports(args.rpt_conf.read_bytes())
            print(f"CHANGED: Analog_Bridge USRP ports set to txPort={tx_port}, rxPort={rx_port}.")
            print("CHANGED=1")
        else:
            print("PASS: Analog_Bridge USRP ports match the private ASL node.")
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
