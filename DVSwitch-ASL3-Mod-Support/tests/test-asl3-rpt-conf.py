#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Cover inherited ASL node sections and safe link-hook placement."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("asl3_rpt_conf", ROOT / "lib" / "asl3_rpt_conf.py")
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)

SAMPLE = b"""[nodes]
1970 = radio@127.0.0.1:4571/1970,NONE
[node-main](!)
rxchannel = Local/pseudo
connpgm = template-hook
[446901](node-main)
rxchannel = Local/pseudo
[1970](node-main)
rxchannel = USRP/127.0.0.1:34001:32001
[other-template](!)
rxchannel = USRP/127.0.0.1:34001:32001
"""


def main() -> None:
    assert TOOL.find_local_node(SAMPLE) == "1970"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "rpt.conf"
        path.write_bytes(SAMPLE)
        node = TOOL.install_hooks(path, "/usr/local/sbin/dvswitch-asl3-link-event")
        installed = path.read_bytes()
        assert node == "1970"
        assert installed.count(TOOL.MARKER) == 1
        assert b"connpgm = /usr/local/sbin/dvswitch-asl3-link-event CONNECTED" in installed
        assert b"discpgm = /usr/local/sbin/dvswitch-asl3-link-event DISCONNECTED" in installed
        assert b"[node-main](!)\nrxchannel = Local/pseudo\nconnpgm = template-hook" in installed
        assert TOOL.install_hooks(path, "/usr/local/sbin/dvswitch-asl3-link-event") == "1970"
        assert path.read_bytes() == installed
        custom = SAMPLE.replace(b"rxchannel = USRP/127.0.0.1:34001:32001\n", b"rxchannel = USRP/127.0.0.1:34001:32001\nconnpgm = custom-hook\n", 1)
        path.write_bytes(custom)
        try:
            TOOL.install_hooks(path, "/usr/local/sbin/dvswitch-asl3-link-event")
        except ValueError as error:
            assert "refusing to overwrite" in str(error)
        else:
            raise AssertionError("existing node hooks were overwritten")
        assert path.read_bytes() == custom
    print("PASS: inherited numeric node headers resolve correctly and hooks stay inside the USRP node stanza")


if __name__ == "__main__":
    main()
