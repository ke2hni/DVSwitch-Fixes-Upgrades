#!/usr/bin/env python3
# Version: 1.0.2
# Created: 2026-11-09T00:41:12-05:00 by KE2HNI

"""Verify private-node switching disconnects before connecting another mode."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_SOURCE = (ROOT / "dvswitch-asl3-node-link").read_text(encoding="utf-8")
RPT_SAMPLE = """[446901](node-main)
rxchannel = SimpleUSB/446901
[1970](node-main)
rxchannel = USRP/127.0.0.1:34001:32001
[1972](node-main)
rxchannel = USRP/127.0.0.1:34003:32003
[1973](node-main)
rxchannel = USRP/127.0.0.1:34005:32005
"""
AB_SAMPLE = """[USRP]
txPort = 32001
rxPort = 34001
"""


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run this test as root to exercise the link helper safely in its temporary fixture.")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rpt_conf = root / "rpt.conf"
        analog_conf = root / "Analog_Bridge.ini"
        state = root / "links.txt"
        log = root / "calls.log"
        rpt_conf.write_text(RPT_SAMPLE, encoding="utf-8")
        analog_conf.write_text(AB_SAMPLE, encoding="utf-8")
        state.write_text(
            "NODE PEER RECONNECTS DIRECTION CONNECT TIME CONNECT STATE\n"
            "1970 127.0.0.1 0 OUT 00:00 ESTABLISHED\n",
            encoding="utf-8",
        )
        mock_asterisk = root / "asterisk"
        mock_asterisk.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            "from pathlib import Path\n"
            "command = sys.argv[2].split()\n"
            "state = Path(os.environ['ASL_TEST_LINKS'])\n"
            "log = Path(os.environ['ASL_TEST_CALLS'])\n"
            "if command[:2] == ['rpt', 'lstats']:\n"
            "    print(state.read_text(), end='')\n"
            "elif command[:3] == ['rpt', 'cmd', '446901'] and command[3:5] == ['ilink', '1']:\n"
            "    peer = command[5]\n"
            "    with log.open('a') as output: output.write('DISCONNECT ' + peer + '\\n')\n"
            "    state.write_text(''.join(line for line in state.read_text().splitlines(keepends=True) if not line.split() or line.split()[0] != peer))\n"
            "    print('Disconnected', peer)\n"
            "elif command[:3] == ['rpt', 'cmd', '446901'] and command[3:5] == ['ilink', '3']:\n"
            "    node = command[5]\n"
            "    with log.open('a') as output: output.write('CONNECT ' + node + '\\n')\n"
            "    with state.open('a') as output: output.write(node + ' 127.0.0.1 0 OUT 00:00 ESTABLISHED\\n')\n"
            "    print('Connected', node)\n"
            "else:\n"
            "    raise SystemExit('unexpected Asterisk request: ' + ' '.join(command))\n",
            encoding="utf-8",
        )
        mock_asterisk.chmod(0o755)
        helper_source = (
            LINK_SOURCE.replace('readonly RPT_CONF="/etc/asterisk/rpt.conf"', f'readonly RPT_CONF="{rpt_conf}"')
            .replace('readonly ANALOG_BRIDGE_CONF="/opt/Analog_Bridge/Analog_Bridge.ini"', f'readonly ANALOG_BRIDGE_CONF="{analog_conf}"')
            .replace('readonly ASTERISK="/usr/sbin/asterisk"', f'readonly ASTERISK="{mock_asterisk}"')
            .replace('readonly RPT_CONF_TOOL="/usr/local/lib/dvswitch-asl3-support/asl3_rpt_conf.py"', f'readonly RPT_CONF_TOOL="{ROOT / "lib" / "asl3_rpt_conf.py"}"')
            .replace('sleep 0.25', 'sleep 0.01')
        )
        helper = root / "dvswitch-asl3-node-link"
        helper.write_text(helper_source, encoding="utf-8")
        helper.chmod(0o755)
        env = dict(os.environ, ASL_TEST_LINKS=str(state), ASL_TEST_CALLS=str(log))

        switched = subprocess.run([str(helper)], input="SWITCH_PRIVATE\t1972\n", text=True, capture_output=True, env=env)
        assert switched.returncode == 0, switched.stderr
        assert log.read_text(encoding="utf-8").splitlines() == ["DISCONNECT 1970", "CONNECT 1972"]
        assert "1972 127.0.0.1" in state.read_text(encoding="utf-8")
        assert "1970 127.0.0.1" not in state.read_text(encoding="utf-8")

        log.write_text("", encoding="utf-8")
        preserved = subprocess.run([str(helper)], input="ENSURE_BRIDGE\n", text=True, capture_output=True, env=env)
        assert preserved.returncode == 0, preserved.stderr
        assert "preserving the exclusive link" in preserved.stdout
        assert log.read_text(encoding="utf-8") == ""
        assert "1970 127.0.0.1" not in state.read_text(encoding="utf-8")

        with state.open("a", encoding="utf-8") as output:
            output.write("1973 127.0.0.1 0 OUT 00:00 ESTABLISHED\n")
        ambiguous = subprocess.run([str(helper)], input="ENSURE_BRIDGE\n", text=True, capture_output=True, env=env)
        assert ambiguous.returncode != 0 and "Multiple alternate private nodes" in ambiguous.stderr, (ambiguous.stdout, ambiguous.stderr)
        assert log.read_text(encoding="utf-8") == ""
        state.write_text("".join(line for line in state.read_text(encoding="utf-8").splitlines(keepends=True) if not line.startswith("1973 ")), encoding="utf-8")

        log.write_text("", encoding="utf-8")
        switched = subprocess.run([str(helper)], input="SWITCH_DVSWITCH\n", text=True, capture_output=True, env=env)
        assert switched.returncode == 0, switched.stderr
        assert log.read_text(encoding="utf-8").splitlines() == ["DISCONNECT 1972", "CONNECT 1970"]
        assert "1970 127.0.0.1" in state.read_text(encoding="utf-8")
        assert "1972 127.0.0.1" not in state.read_text(encoding="utf-8")

    print("PASS: M17 and DVSwitch private links are switched exclusively, disconnecting before connecting")


if __name__ == "__main__":
    main()
