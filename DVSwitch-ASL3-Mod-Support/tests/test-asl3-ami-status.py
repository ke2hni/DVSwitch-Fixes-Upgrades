#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Exercise the Allmon3-compatible ASL AMI activity reader with a local fixture."""

from __future__ import annotations

import importlib.util
import socket
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("asl3_ami_status", ROOT / "dvswitch-asl3-ami-status.py")
assert SPEC and SPEC.loader
STATUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATUS)

RPT = b"""[446901](node-main)
rxchannel = Local/pseudo
[1970](node-main)
rxchannel = USRP/127.0.0.1:34001:32001
"""


def fake_ami(listener: socket.socket) -> None:
    connection, _ = listener.accept()
    with connection:
        connection.sendall(b"Asterisk Call Manager/5.0.0\r\n")
        stream = connection.makefile("rwb")
        while True:
            lines = []
            while True:
                line = stream.readline()
                if not line or line in (b"\r\n", b"\n"):
                    break
                lines.append(line.decode().strip())
            if not lines:
                return
            values = dict(line.split(": ", 1) for line in lines if ": " in line)
            action = values.get("Action", "").lower()
            if action == "login":
                response = "Response: Success\r\nMessage: Authentication accepted\r\n\r\n"
            elif action == "rptstatus" and values.get("Command") == "XStat":
                response = (
                    "Response: Success\r\nNode: 446901\r\n"
                    "Conn: 1970 127.0.0.1 0 OUT 00:19:00 ESTABLISHED\r\n"
                    "Conn: 55553 44.27.139.130 0 OUT 00:00:13 ESTABLISHED\r\n"
                    "Var: RPT_RXKEYED=0\r\nVar: RPT_TXKEYED=1\r\nVar: RPT_TXEKEYED=0\r\n\r\n"
                )
            elif action == "rptstatus" and values.get("Command") == "SawStat":
                response = "Response: Success\r\nConn: 55553 1 11 -1\r\n\r\n"
            else:
                response = "Response: Success\r\nMessage: Goodbye\r\n\r\n"
            stream.write(response.encode())
            stream.flush()
            if action == "logoff":
                return


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / "allmon3.ini"
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        config.write_text(f"[446900]\nhost=127.0.0.1\nport={port}\nuser=monitor\npass=fixture-secret\nmultinodes=446900,446901\n", encoding="utf-8")
        server = threading.Thread(target=fake_ami, args=(listener,), daemon=True)
        server.start()
        result = STATUS.query_status(RPT, config)
        listener.close()
        server.join(timeout=2)

    assert result["public_node"] == "446901"
    assert result["connected_nodes"] == ["55553"]
    assert result["tx_keyed"] is True and result["rx_keyed"] is False
    assert result["link_keying"]["55553"] == {"ptt": True, "seconds_since_key": 11}
    assert STATUS._keyed_values(["Var: RPT_TXEKEYED=1"])["txe_keyed"] is True
    print("PASS: ASL AMI status follows Allmon3 XStat/SawStat and excludes the private bridge peer")


if __name__ == "__main__":
    main()
