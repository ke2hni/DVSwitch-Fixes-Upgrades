#!/usr/bin/env python3
# Version: 1.0.1
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
    assert TOOL.find_local_node(RPT, ANALOG) == "1970"
    assert TOOL.find_public_node(RPT) == "446901"
    try:
        TOOL.find_local_node(RPT)
    except ValueError as error:
        assert "Analog_Bridge ports are required" in str(error)
    else:
        raise AssertionError("multiple private nodes were accepted without a DVSwitch port map")

    mismatched = ANALOG.replace(b"32001", b"32009").replace(b"34001", b"34009")
    try:
        TOOL.find_local_node(RPT, mismatched)
    except ValueError as error:
        assert "match 0 of 3" in str(error)
    else:
        raise AssertionError("unmatched Analog_Bridge ports selected a private node")

    with tempfile.TemporaryDirectory() as directory:
        rpt_path = Path(directory) / "rpt.conf"
        analog_path = Path(directory) / "Analog_Bridge.ini"
        rpt_path.write_bytes(RPT)
        analog_path.write_bytes(ANALOG)
        check = subprocess.run(
            ["python3", str(ROOT / "lib" / "asl3_rpt_conf.py"), "check", str(rpt_path), "--analog-bridge", str(analog_path)],
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
            ["python3", str(ports_tool), "check", str(rpt_path), str(ini_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert "PASS: Analog_Bridge USRP ports match the private ASL node." in ports.stdout
        before = ini_path.read_bytes()
        ini_path.write_bytes(mismatched)
        ports = subprocess.run(
            ["python3", str(ports_tool), "check", str(rpt_path), str(ini_path)],
            capture_output=True,
            text=True,
        )
        assert ports.returncode != 0 and "match 0 of 3" in ports.stdout
        assert ini_path.read_bytes() == mismatched == before.replace(b"32001", b"32009").replace(b"34001", b"34009")

    hook = "/usr/local/sbin/dvswitch-asl3-link-event"
    with tempfile.TemporaryDirectory() as directory:
        rpt_path = Path(directory) / "rpt.conf"
        rpt_path.write_bytes(RPT)
        assert TOOL.install_hooks(rpt_path, hook, ANALOG) == "446901"
        installed = rpt_path.read_bytes()
        assert installed.count(TOOL.MARKER) == 1
        assert b"[1970](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n" in installed
        assert b"[1972](node-main)\nrxchannel = USRP/127.0.0.1:34003:32003\n" in installed
        assert TOOL.install_hooks(rpt_path, hook, ANALOG) == "446901"

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

    print("PASS: multiple private USRP nodes are recognized; Analog_Bridge selects DVSwitch; private peers stay hidden")


if __name__ == "__main__":
    main()
