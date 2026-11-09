#!/usr/bin/env python3
# Version: 1.1.0
# Created: 2026-11-09T00:41:12-05:00 by KE2HNI

"""Check ASL discovery with several private USRP nodes."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("asl3_rpt_conf", ROOT / "lib" / "asl3_rpt_conf.py")
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

RPT = b"""[446901](node-main)
rxchannel = SimpleUSB/446901
[1970](node-main)
rxchannel = USRP/127.0.0.1:34001:32001
[1972](node-main)
rxchannel = USRP/127.0.0.1:34003:32003
[1973](node-main)
rxchannel = USRP/127.0.0.1:34005:32005
"""
ANALOG = b"""[USRP]
txPort = 32001
rxPort = 34001
"""


def main() -> None:
    assert TOOL.private_nodes(RPT) == ["1970", "1972", "1973"]
    assert TOOL.find_public_node(RPT) == "446901"
    assert TOOL.find_local_node(RPT, ANALOG, "1970") == "1970"
    assert TOOL.find_local_node(RPT, ANALOG, "1972") == "1972"
    try:
        TOOL.find_local_node(RPT)
    except ValueError as error:
        assert "explicitly select" in str(error)
    else:
        raise AssertionError("multiple private nodes were accepted without explicit user selection")

    # Before M17 is configured, its stanza can share the default port pair.
    # The explicit selection, not stanza order or ports, determines the bridge.
    duplicate_pair = RPT.replace(
        b"[1972](node-main)\nrxchannel = USRP/127.0.0.1:34003:32003",
        b"[1972](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001",
    )
    assert TOOL.private_nodes(duplicate_pair) == ["1970", "1972", "1973"]
    assert TOOL.find_local_node(duplicate_pair, ANALOG, "1972") == "1972"

    with tempfile.TemporaryDirectory() as directory:
        rpt_path = Path(directory) / "rpt.conf"
        analog_path = Path(directory) / "Analog_Bridge.ini"
        rpt_path.write_bytes(RPT)
        analog_path.write_bytes(ANALOG)
        check = subprocess.run(
            ["python3", str(ROOT / "lib" / "asl3_rpt_conf.py"), "check", str(rpt_path), "--analog-bridge", str(analog_path), "--private-node", "1970"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "ASL private USRP nodes: 1970, 1972, 1973" in check.stdout
        assert "ASL private DVSwitch bridge node: 1970" in check.stdout
        assert "ASL local public node: 446901" in check.stdout

    ports_tool = ROOT / "lib" / "asl3_usrp_ports.py"
    with tempfile.TemporaryDirectory() as directory:
        rpt_path = Path(directory) / "rpt.conf"
        ini_path = Path(directory) / "Analog_Bridge.ini"
        rpt_path.write_bytes(RPT)
        ini_path.write_bytes(ANALOG)
        ports = subprocess.run(
            ["python3", str(ports_tool), "check", str(rpt_path), str(ini_path), "--private-node", "1970"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "PASS: Analog_Bridge USRP ports match the private ASL node." in ports.stdout
        before = ini_path.read_bytes()
        mismatched = ANALOG.replace(b"32001", b"32009").replace(b"34001", b"34009")
        ini_path.write_bytes(mismatched)
        ports = subprocess.run(
            ["python3", str(ports_tool), "check", str(rpt_path), str(ini_path), "--private-node", "1970"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "NEEDS REPAIR: Analog_Bridge USRP ports should be txPort=32001, rxPort=34001." in ports.stdout
        assert ini_path.read_bytes() == mismatched
        ports = subprocess.run(
            ["python3", str(ports_tool), "install", str(rpt_path), str(ini_path), "--private-node", "1970"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "CHANGED=1" in ports.stdout
        assert ini_path.read_bytes() == before

    hook = "/usr/local/sbin/dvswitch-asl3-link-event"
    with tempfile.TemporaryDirectory() as directory:
        rpt_path = Path(directory) / "rpt.conf"
        rpt_path.write_bytes(RPT)
        assert TOOL.install_hooks(rpt_path, hook, ANALOG, "1970") == "446901"
        installed = rpt_path.read_bytes()
        assert installed.count(TOOL.MARKER) == 1
        assert b"[1970](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n" in installed
        assert b"[1972](node-main)\nrxchannel = USRP/127.0.0.1:34003:32003\n" in installed
        assert TOOL.install_hooks(rpt_path, hook, ANALOG, "1970") == "446901"

        # Installation remains deterministic by using the selected node when
        # an unconfigured private node has the same default ports.
        rpt_path.write_bytes(duplicate_pair)
        assert TOOL.install_hooks(rpt_path, hook, ANALOG, "1972") == "446901"
        installed = rpt_path.read_bytes()
        assert installed.count(TOOL.MARKER) == 1
        assert b"[1972](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n" in installed

    helper = ROOT / "dvswitch-asl3-ami-status.py"
    status_spec = importlib.util.spec_from_file_location("asl3_ami_status", helper)
    assert status_spec and status_spec.loader
    status = importlib.util.module_from_spec(status_spec)
    status_spec.loader.exec_module(status)
    xstat = [
        "Conn: 1970 local local local ESTABLISHED",
        "Conn: 1972 local local local ESTABLISHED",
        "Conn: 700001 external external external ESTABLISHED",
    ]
    assert status._connected_nodes(xstat, TOOL.private_nodes(RPT)) == ["700001"]

    print("PASS: multiple private USRP nodes require explicit DVSwitch selection; chosen node and public-peer filtering are honored")


if __name__ == "__main__":
    main()
