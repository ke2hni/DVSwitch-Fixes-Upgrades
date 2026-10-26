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
    assert TOOL.find_public_node(SAMPLE) == "446901"
    assert TOOL.configured_nodes(SAMPLE) == ["446901", "1970"]
    old_private_hooks = SAMPLE.replace(
        b"[1970](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n",
        b"[1970](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n" + TOOL.MARKER + b"\nconnpgm = /usr/local/sbin/dvswitch-asl3-link-event CONNECTED\ndiscpgm = /usr/local/sbin/dvswitch-asl3-link-event DISCONNECTED\n",
        1,
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "rpt.conf"
        path.write_bytes(old_private_hooks)
        assert TOOL.install_hooks(path, "/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-link-event") == "446901"
        migrated = path.read_bytes()
        private_block = next(item[3] for item in TOOL.numeric_sections(migrated) if item[0] == "1970")
        public_block = next(item[3] for item in TOOL.numeric_sections(migrated) if item[0] == "446901")
        assert TOOL.MARKER not in private_block
        assert TOOL.MARKER in public_block
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "rpt.conf"
        path.write_bytes(SAMPLE)
        node = TOOL.install_hooks(path, "/usr/local/sbin/dvswitch-asl3-link-event")
        installed = path.read_bytes()
        assert node == "446901"
        assert installed.count(TOOL.MARKER) == 1
        assert b"connpgm = /usr/local/sbin/dvswitch-asl3-link-event CONNECTED" in installed
        assert b"discpgm = /usr/local/sbin/dvswitch-asl3-link-event DISCONNECTED" in installed
        assert b"[node-main](!)\nrxchannel = Local/pseudo\nconnpgm = template-hook" in installed
        private_block = next(item[3] for item in TOOL.numeric_sections(installed) if item[0] == "1970")
        assert b"connpgm =" not in private_block and b"discpgm =" not in private_block and TOOL.MARKER not in private_block
        assert TOOL.install_hooks(path, "/usr/local/sbin/dvswitch-asl3-link-event") == "446901"
        assert path.read_bytes() == installed
        # Upgrade the hook command format in place without changing node IDs.
        assert TOOL.install_hooks(path, "/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-link-event") == "446901"
        migrated = path.read_bytes()
        assert b"connpgm = /usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-link-event CONNECTED" in migrated
        assert b"discpgm = /usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-link-event DISCONNECTED" in migrated
        assert TOOL.install_hooks(path, "/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-link-event") == "446901"
        assert path.read_bytes() == migrated
        custom = SAMPLE.replace(b"[446901](node-main)\nrxchannel = Local/pseudo\n", b"[446901](node-main)\nrxchannel = Local/pseudo\nconnpgm = custom-hook\n", 1)
        path.write_bytes(custom)
        try:
            TOOL.install_hooks(path, "/usr/local/sbin/dvswitch-asl3-link-event")
        except ValueError as error:
            assert "refusing to overwrite" in str(error) or "custom activity hooks" in str(error)
        else:
            raise AssertionError("existing node hooks were overwritten")
        assert path.read_bytes() == custom
    print("PASS: node IDs are discovered from rpt.conf and activity hooks are placed on the local public node")


if __name__ == "__main__":
    main()
