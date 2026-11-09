#!/usr/bin/env python3
# Version: 1.0.0
# Created: 2026-11-09T01:54:26-05:00 by KE2HNI

"""Verify manager-facing private bridge node prompting and validation."""

from __future__ import annotations

import os
import pty
import select
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "dvswitch-asl3-mod-support.sh"
RPT = b"""[446901](node-main)
rxchannel = SimpleUSB/446901
[1970](node-main)
rxchannel = USRP/127.0.0.1:34001:32001
[1972](node-main)
rxchannel = USRP/127.0.0.1:34001:32001
"""


def run_with_tty(script: Path, answer: bytes) -> tuple[int, str]:
    pid, terminal = pty.fork()
    if pid == 0:
        os.execv("/bin/bash", ["bash", str(script), "--select-private-node"])
    output = bytearray()
    sent = False
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        readable, _, _ = select.select([terminal], [], [], 0.1)
        if readable:
            try:
                chunk = os.read(terminal, 4096)
            except OSError:
                break
            if not chunk:
                break
            output.extend(chunk)
            if not sent and b"Which private node number is used for DVSwitch" in output:
                os.write(terminal, answer)
                sent = True
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), output.decode("utf-8", "replace")


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        rpt = temp / "rpt.conf"
        config = temp / "private-node"
        script = temp / "dvswitch-asl3-mod-support.sh"
        rpt.write_bytes(RPT)
        source = INSTALLER.read_text(encoding="utf-8")
        source = source.replace('readonly RPT_CONF="/etc/asterisk/rpt.conf"', f'readonly RPT_CONF="{rpt}"')
        source = source.replace('readonly PRIVATE_NODE_CONFIG_TARGET="/etc/dvswitch-asl3-support/private-node"', f'readonly PRIVATE_NODE_CONFIG_TARGET="{config}"')
        source = source.replace('readonly RPT_CONF_TOOL="$SCRIPT_DIR/lib/asl3_rpt_conf.py"', f'readonly RPT_CONF_TOOL="{ROOT / "lib" / "asl3_rpt_conf.py"}"')
        script.write_text(source, encoding="utf-8")

        code, output = run_with_tty(script, b"1972\n")
        assert code == 0, output
        assert "Private USRP nodes: 1970 1972" in output
        assert "Which private node number is used for DVSwitch" in output
        assert output.rstrip().endswith("1972")
        assert not config.exists(), "selection-only command must not write configuration"

        config.write_text("1970\n", encoding="ascii")
        code, output = run_with_tty(script, b"\n")
        assert code == 0, output
        assert "Press Enter to keep 1970" in output
        assert output.rstrip().endswith("1970")

        code, output = run_with_tty(script, b"12345\n")
        assert code != 0 and "not one of the configured private USRP nodes" in output

    print("PASS: ASL installer asks for the DVSwitch private node and validates the selected number")


if __name__ == "__main__":
    main()
