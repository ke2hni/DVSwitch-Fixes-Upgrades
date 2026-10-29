#!/usr/bin/env python3
# Version: 1.0.1
# SPDX-License-Identifier: MIT

"""Verify default Connect replacement drops external links before connecting."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LINK_SOURCE = (ROOT / "dvswitch-asl3-node-link").read_text(encoding="utf-8")
RPT_SAMPLE = """[nodes]
1970 = radio@127.0.0.1:4571/1970,NONE
[node-main](!)
rxchannel = Local/pseudo
[446901](node-main)
rxchannel = Local/pseudo
[1970](node-main)
rxchannel = USRP/127.0.0.1:34001:32001
"""


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run this test as root to exercise the link helper safely in its temporary fixture.")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rpt_conf = root / "rpt.conf"
        rpt_conf.write_text(RPT_SAMPLE, encoding="utf-8")
        state = root / "links.txt"
        state.write_text(
            "NODE PEER RECONNECTS DIRECTION CONNECT TIME CONNECT STATE\n"
            "1970 127.0.0.1 0 OUT 00:00 ESTABLISHED\n"
            "55553 203.0.113.5 0 OUT 00:00 ESTABLISHED\n",
            encoding="utf-8",
        )
        log = root / "calls.log"
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
            "    if not os.environ.get('ASL_TEST_REJECT_CONNECT'):\n"
            "        with state.open('a') as output: output.write(node + ' 203.0.113.9 0 OUT 00:00 ESTABLISHED\\n')\n"
            "    print('Connected', node)\n"
            "else:\n"
            "    raise SystemExit('unexpected Asterisk request: ' + ' '.join(command))\n",
            encoding="utf-8",
        )
        mock_asterisk.chmod(0o755)
        helper_source = (
            LINK_SOURCE.replace('readonly RPT_CONF="/etc/asterisk/rpt.conf"', f'readonly RPT_CONF="{rpt_conf}"')
            .replace('readonly ASTERISK="/usr/sbin/asterisk"', f'readonly ASTERISK="{mock_asterisk}"')
            # Keep the timeout case short in this isolated fixture; production waits up to 30 seconds.
            .replace('for attempt in {1..120}; do', 'for attempt in {1..2}; do')
            .replace('sleep 0.25', 'sleep 0.01')
            .replace(
                'readonly RPT_CONF_TOOL="/usr/local/lib/dvswitch-asl3-support/asl3_rpt_conf.py"',
                f'readonly RPT_CONF_TOOL="{ROOT / "lib" / "asl3_rpt_conf.py"}"',
            )
        )
        helper = root / "dvswitch-asl3-node-link"
        helper.write_text(helper_source, encoding="utf-8")
        helper.chmod(0o755)
        env = dict(os.environ, ASL_TEST_LINKS=str(state), ASL_TEST_CALLS=str(log))

        replaced = subprocess.run(
            [str(helper)], input="CONNECT\t55553\tDISCONNECT_BEFORE_CONNECT\n",
            text=True, capture_output=True, env=env,
        )
        assert replaced.returncode == 0, replaced.stderr
        calls = log.read_text(encoding="utf-8").splitlines()
        assert calls == ["DISCONNECT 55553", "CONNECT 55553"], calls
        assert "1970 127.0.0.1" in state.read_text(encoding="utf-8")
        assert "55553 203.0.113.9" in state.read_text(encoding="utf-8")
        assert "external node 55553 is established on local public ASL node 446901" in replaced.stdout

        # Without the replacement flag, Connect leaves existing external peers alone.
        log.write_text("", encoding="utf-8")
        state.write_text(
            "1970 127.0.0.1 0 OUT 00:00 ESTABLISHED\n"
            "55553 203.0.113.5 0 OUT 00:00 ESTABLISHED\n",
            encoding="utf-8",
        )
        ordinary = subprocess.run(
            [str(helper)], input="CONNECT\t672000\n", text=True, capture_output=True, env=env,
        )
        assert ordinary.returncode == 0, ordinary.stderr
        assert log.read_text(encoding="utf-8").splitlines() == ["CONNECT 672000"]
        assert "1970 127.0.0.1" in state.read_text(encoding="utf-8")
        assert "55553 203.0.113.5" in state.read_text(encoding="utf-8")

        # A zero CLI exit status without a live peer must not be treated as a successful link.
        state.write_text("1970 127.0.0.1 0 OUT 00:00 ESTABLISHED\n", encoding="utf-8")
        env["ASL_TEST_REJECT_CONNECT"] = "1"
        failed = subprocess.run(
            [str(helper)], input="CONNECT\t55553\n", text=True, capture_output=True, env=env,
        )
        assert failed.returncode != 0, failed.stdout
        assert "node 55553 did not reach ESTABLISHED state" in failed.stderr, failed.stderr

    print("PASS: Connect targets public node 446901, verifies parrot 55553, and preserves private bridge 1970")


if __name__ == "__main__":
    main()
