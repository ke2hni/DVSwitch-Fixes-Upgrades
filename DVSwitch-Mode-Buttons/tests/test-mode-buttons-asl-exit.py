#!/usr/bin/env python3
# Version: 1.0.0
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Verify Mode Buttons owns safe, dynamically discovered ASL exit cleanup."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "dvswitch-mode-buttons-asl-exit"
loader = importlib.machinery.SourceFileLoader("buttons_asl_exit", str(HELPER))
spec = importlib.util.spec_from_loader("buttons_asl_exit", loader)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load Mode Buttons ASL exit helper")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# Exercise the node discovery parser with different local IDs; no node number is fixed in code.
private_node, public_node = module.local_nodes(
    b"[123456]\nrxchannel = usrp/127.0.0.1:34001:32001\n[987654]\n"
)
require((private_node, public_node) == ("123456", "987654"), "local node discovery used fixed IDs or selected the wrong pair")

with tempfile.TemporaryDirectory(prefix="mode-buttons-asl-exit-") as directory:
    temp = Path(directory)
    rpt_conf = temp / "rpt.conf"
    rpt_conf.write_text("[123456]\nrxchannel = usrp/127.0.0.1:34001:32001\n[987654]\n", encoding="utf-8")
    fake_asterisk = temp / "asterisk"
    fake_asterisk.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys\n"
        "command = sys.argv[2]\n"
        "state = pathlib.Path(os.environ['LINK_STATE'])\n"
        "with open(os.environ['COMMAND_LOG'], 'a', encoding='utf-8') as log: log.write(command + '\\n')\n"
        "if command == 'rpt lstats 987654':\n"
        " print('NODE PEER RECONNECTS DIRECTION CONNECT TIME CONNECT STATE')\n"
        " print('123456 127.0.0.1 0 OUT 00:00:10 ESTABLISHED')\n"
        " if not state.exists(): print('55553 44.27.139.130 0 OUT 00:00:05 ESTABLISHED')\n"
        "elif command == 'rpt cmd 987654 ilink 1 55553': state.touch()\n"
        "else: raise SystemExit('unexpected Asterisk command: ' + command)\n",
        encoding="utf-8",
    )
    fake_asterisk.chmod(0o755)
    env = {
        **os.environ,
        "DVS_BUTTONS_TESTING": "1",
        "DVS_BUTTONS_RPT_CONF": str(rpt_conf),
        "DVS_BUTTONS_ASTERISK": str(fake_asterisk),
        "LINK_STATE": str(temp / "external-disconnected"),
        "COMMAND_LOG": str(temp / "commands.log"),
    }
    result = subprocess.run([str(HELPER)], env=env, text=True, capture_output=True, check=False)
    require(result.returncode == 0, f"mocked ASL disconnect failed: {result.stderr}")
    commands = (temp / "commands.log").read_text(encoding="utf-8").splitlines()
    require("rpt cmd 987654 ilink 1 55553" in commands, "external peer was not disconnected on discovered public node")
    require(not any("ilink 1 123456" in command for command in commands), "private bridge node was disconnected")
    require("private bridge 123456 on public node 987654 preserved" in result.stdout,
            "success output did not confirm that the private bridge was retained")

installer = (ROOT / "dvswitch-mode-buttons.sh").read_text(encoding="utf-8")
dispatcher = (ROOT / "dvswitch-mode-buttons").read_text(encoding="utf-8")
require('install -o root -g root -m 755 ./dvswitch-mode-buttons-asl-exit "$ASL_EXIT_HELPER"' in installer,
        "Mode Buttons installer does not install its own ASL exit helper")
require('"$ASL_EXIT_HELPER" || die' in dispatcher,
        "mode dispatcher does not use its repository-owned cleanup helper")
require("dvswitch-asl3-node-link DISCONNECT_ALL" not in dispatcher,
        "mode-exit cleanup still depends on ASL3 Support's polling implementation")
print("PASS: Mode Buttons discovers node IDs, preserves the private bridge, disconnects external peers, and owns the ASL exit helper.")
