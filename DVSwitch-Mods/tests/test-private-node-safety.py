#!/usr/bin/env python3
# Version: 1.0.0
# Created: 2026-11-15T12:00:00+00:00 by KE2HNI
# SPDX-License-Identifier: MIT

"""Validate private-node duplex checks and manager installation gating."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "check-private-node-safety.py"
SPEC = importlib.util.spec_from_file_location("private_node_safety", CHECKER)
assert SPEC and SPEC.loader
SAFETY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SAFETY
SPEC.loader.exec_module(SAFETY)


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rpt = root / "rpt.conf"
        support = root / "dvswitch-m17-support.conf"
        support.write_text("M17_PRIVATE_NODE=1974\nDVSWITCH_PRIVATE_NODE=1973\n", encoding="utf-8")
        rpt.write_text(
            "[node-main](!)\nduplex = 0\n"
            "[nodes]\n1973 = radio@127.0.0.1/1973,NONE\n"
            "[1973](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n"
            "[1974](node-main)\nrxchannel = USRP/127.0.0.1:34008:32008\n"
            "[1500](node-main)\nrxchannel = SimpleUSB/1500\n"
            "[2000](node-main)\nrxchannel = USRP/127.0.0.1:34000:32000\n",
            encoding="utf-8")
        assert SAFETY.inspect(rpt, support) == []

        rpt.write_text(rpt.read_text(encoding="utf-8").replace(
            "[node-main](!)\nduplex = 0", "[node-main](!)\nduplex = 2"), encoding="utf-8")
        errors = SAFETY.inspect(rpt, support)
        assert any("Private USRP node 1974" in error and "duplex='2'" in error for error in errors)
        assert any("M17_PRIVATE_NODE=1974" in error for error in errors)

        rpt.write_text(
            "[node-main](!)\n[1999](node-main)\nrxchannel = SimpleUSB/1999\n",
            encoding="utf-8")
        assert any("Private node 1999 has no active duplex" in error
                   for error in SAFETY.inspect(rpt, None))
        rpt.write_text(
            "[1999]\nduplex = 5\nrxchannel = SimpleUSB/1999\n",
            encoding="utf-8")
        assert any("unsupported duplex='5'" in error for error in SAFETY.inspect(rpt, None))
        rpt.write_text(
            "[1999]\nduplex = 0\n[1999](node-main)\nduplex = 0\n",
            encoding="utf-8")
        assert any("defines private node stanza [1999] more than once" in error
                   for error in SAFETY.inspect(rpt, None))

    manager = (ROOT / "manage-dvswitch-mods.sh").read_text(encoding="utf-8")
    menu = manager[manager.index("show_menu() {"):manager.index("usage() {")]
    assert menu.index("run_private_node_safety_check") < menu.index("DVSwitch-Mods installer menu")
    assert "5) Uninstall all manager-recorded standard components" in menu
    assert "--install) [[ $# -eq 2 ]] || die" in manager
    install_case = manager[manager.index("--install)"):manager.index("--uninstall)")]
    assert install_case.index("run_private_node_safety_check") < install_case.index("initialize_state")
    assert "Private USRP node" in CHECKER.read_text(encoding="utf-8")
    print("PASS: private-node safety check and manager gate")


if __name__ == "__main__":
    main()
