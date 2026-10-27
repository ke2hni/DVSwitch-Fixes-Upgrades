#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Read Allmon3-compatible ASL keying status for the configured public node."""

from __future__ import annotations

import configparser
import ipaddress
import json
import re
import socket
import sys
from pathlib import Path

SUPPORT_LIB = Path("/usr/local/lib/dvswitch-asl3-support")
if SUPPORT_LIB.is_dir():
    sys.path.insert(0, str(SUPPORT_LIB))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import asl3_rpt_conf

RPT_CONF = Path("/etc/asterisk/rpt.conf")
ALLMON_CONFIG = Path("/etc/allmon3/allmon3.ini")


def _ami_frame(stream) -> list[str]:
    """Read one complete AMI response frame, as Allmon3 does."""
    lines: list[str] = []
    size = 0
    while True:
        raw = stream.readline(65537)
        if not raw:
            raise ValueError("Asterisk AMI closed the connection before completing a response")
        size += len(raw)
        if size > 262144:
            raise ValueError("Asterisk AMI response exceeded the safety limit")
        if raw in (b"\r\n", b"\n"):
            if lines:
                return [line.decode("utf-8", "replace").rstrip("\r\n") for line in lines]
            continue
        lines.append(raw)


def _ami_action(stream, action: str, **headers: str) -> list[str]:
    parts = [f"Action: {action}"]
    parts.extend(f"{key}: {value}" for key, value in headers.items())
    stream.write(("\r\n".join(parts) + "\r\n\r\n").encode("ascii"))
    stream.flush()
    return _ami_frame(stream)


def _local_manager_config(public_node: str, config_path: Path) -> tuple[str, int, str, str]:
    if config_path.is_symlink() or not config_path.is_file():
        raise ValueError("Allmon3 AMI configuration is unavailable")
    config = configparser.ConfigParser(interpolation=None)
    with config_path.open(encoding="utf-8") as source:
        config.read_file(source)
    section = config[public_node] if public_node in config else None
    if section is None:
        matches = [config[name] for name in config.sections()
                   if public_node in {value.strip() for value in config[name].get("multinodes", "").split(",")}]
        if len(matches) == 1:
            section = matches[0]
    if section is None:
        raise ValueError(f"Allmon3 has no AMI entry for public node {public_node}")
    entry = section
    host = entry.get("host", "127.0.0.1").strip()
    if host.lower() == "localhost":
        host = "127.0.0.1"
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError("Allmon3 AMI host must be local to this DVSwitch unit")
    except ValueError as error:
        raise ValueError("Allmon3 AMI host must be a local loopback address") from error
    try:
        port = entry.getint("port", fallback=5038)
    except ValueError as error:
        raise ValueError("Allmon3 AMI port is invalid") from error
    user = entry.get("user", "").strip()
    secret = entry.get("pass", "")
    if not 1 <= port <= 65535 or not user or not secret:
        raise ValueError("Allmon3 AMI entry is missing a valid port, user, or password")
    if any(character in user + secret for character in "\r\n"):
        raise ValueError("Allmon3 AMI credentials contain invalid line breaks")
    return host, port, user, secret


def _keyed_values(lines: list[str]) -> dict[str, bool]:
    values = {"rx_keyed": False, "tx_keyed": False, "txe_keyed": False}
    names = {"RPT_RXKEYED": "rx_keyed", "RPT_TXKEYED": "tx_keyed", "RPT_TXEKEYED": "txe_keyed"}
    for line in lines:
        match = re.fullmatch(r"Var:\s*(RPT_(?:RX|TXE?)KEYED)=([01])", line.strip())
        if match and match.group(1) in names:
            values[names[match.group(1)]] = match.group(2) == "1"
    return values


def _connected_nodes(xstat: list[str], private_node: str) -> list[str]:
    nodes: list[str] = []
    for line in xstat:
        fields = line.split()
        if len(fields) >= 6 and fields[0] == "Conn:" and fields[-1] == "ESTABLISHED":
            node = fields[1]
            if node != private_node and re.fullmatch(r"[0-9]{1,8}", node) and node not in nodes:
                nodes.append(node)
    return nodes


def _link_keying(sawstat: list[str], connected: list[str]) -> dict[str, dict[str, int | bool]]:
    states: dict[str, dict[str, int | bool]] = {}
    for line in sawstat:
        fields = line.split()
        if len(fields) != 5 or fields[0] != "Conn:" or fields[1] not in connected:
            continue
        try:
            ptt = int(fields[2]) == 1
            since_key = max(0, int(fields[3])) if ptt else 0
        except ValueError:
            continue
        states[fields[1]] = {"ptt": ptt, "seconds_since_key": since_key}
    return states


def query_status(rpt_data: bytes, config_path: Path = ALLMON_CONFIG) -> dict[str, object]:
    """Fetch XStat/SawStat for the discovered public node using local Allmon3 AMI settings."""
    public_node = asl3_rpt_conf.find_public_node(rpt_data)
    private_node = asl3_rpt_conf.find_local_node(rpt_data)
    host, port, user, secret = _local_manager_config(public_node, config_path)

    with socket.create_connection((host, port), timeout=2.0) as connection:
        connection.settimeout(2.0)
        stream = connection.makefile("rwb")
        try:
            banner = stream.readline(4096).decode("utf-8", "replace")
            if not banner.startswith("Asterisk Call Manager"):
                raise ValueError("The local Allmon3 port is not an Asterisk AMI service")
            login = _ami_action(stream, "Login", Username=user, Secret=secret, Events="off")
            if not any(line.lower() == "response: success" for line in login):
                raise ValueError("Allmon3 AMI login failed")
            # Query the same RptStatus actions Allmon3 uses for keying and link PTT.
            xstat = _ami_action(stream, "RptStatus", Command="XStat", Node=public_node)
            sawstat = _ami_action(stream, "RptStatus", Command="SawStat", Node=public_node)
            if not any(line.lower() == "response: success" for line in xstat + sawstat):
                raise ValueError("Asterisk did not return RptStatus for the public node")
        finally:
            try:
                _ami_action(stream, "Logoff")
            except (OSError, ValueError):
                pass
            stream.close()

    connected = _connected_nodes(xstat, private_node)
    return {
        "public_node": public_node,
        "connected_nodes": connected,
        **_keyed_values(xstat),
        "link_keying": _link_keying(sawstat, connected),
    }


def main() -> int:
    if len(sys.argv) != 1:
        print(json.dumps({"ok": False, "error": "This status command accepts no arguments"}, separators=(",", ":")))
        return 2
    public_node = ""
    try:
        data = RPT_CONF.read_bytes()
        public_node = asl3_rpt_conf.find_public_node(data)
        print(json.dumps({"ok": True, **query_status(data)}, separators=(",", ":")))
        return 0
    except (OSError, ValueError, configparser.Error, socket.error) as error:
        print(json.dumps({"ok": False, "public_node": public_node, "error": str(error)}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
