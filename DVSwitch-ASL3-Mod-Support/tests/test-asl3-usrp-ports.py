#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Verify ASL USRP ports are derived and repaired without losing comments."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "lib" / "asl3_usrp_ports.py"
RPT = b"""[446901](node-main)
rxchannel = Local/pseudo
[1970](node-main)
rxchannel = USRP/127.0.0.1:34001:32001
"""
INI = b"""[GENERAL]
pcmPort = 2222
[USRP]
txPort = 31001 ; send to the private Asterisk USRP port
rxPort = 31001 ; receive from the private Asterisk USRP port
"""


def run(action: str, rpt: Path, ini: Path) -> str:
    result = subprocess.run(
        ["python3", str(TOOL), action, str(rpt), str(ini)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        rpt = Path(directory) / "rpt.conf"
        ini = Path(directory) / "Analog_Bridge.ini"
        rpt.write_bytes(RPT)
        ini.write_bytes(INI)

        output = run("check", rpt, ini)
        assert "NEEDS REPAIR: Analog_Bridge USRP ports should be txPort=32001, rxPort=34001." in output
        assert ini.read_bytes() == INI, "--check changed Analog_Bridge.ini"

        output = run("install", rpt, ini)
        assert "CHANGED=1" in output
        installed = ini.read_bytes()
        assert b"txPort = 32001 ; send to the private Asterisk USRP port" in installed
        assert b"rxPort = 34001 ; receive from the private Asterisk USRP port" in installed
        assert b"pcmPort = 2222" in installed

        assert "PASS: Analog_Bridge USRP ports match the private ASL node." in run("check", rpt, ini)
        assert run("install", rpt, ini).find("CHANGED=1") == -1

    print("PASS: ASL USRP port pairs are discovered from rpt.conf and repaired atomically")


if __name__ == "__main__":
    main()
