#!/usr/bin/env python3
# Version: 1.0.0
# Created: 2026-11-19T14:45:00-05:00 by KE2HNI
# SPDX-License-Identifier: MIT
"""Verify ASL network status is registration-based, independent of peer links."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "dvswitch-asl3-node-links"
RPT_TOOL = ROOT / "lib" / "asl3_rpt_conf.py"
INSTALLER = ROOT / "dvswitch-asl3-mod-support.sh"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    config = root / "rpt.conf"
    config.write_text("[1970]\nrxchannel=USRP/127.0.0.1:32001:34001\n[446901]\nrxchannel=SimpleUSB\n", encoding="utf-8")
    tool = root / "rpt-conf.py"
    tool.write_bytes(RPT_TOOL.read_bytes())
    asterisk = root / "asterisk"
    asterisk.write_text("""#!/usr/bin/env bash
case "$*" in
  *"rpt lstats"*) printf 'NODE PEER\n';;
  *"rpt show registrations"*)
    printf 'Host Username Perceived Refresh State\\n'
    [[ ${HTTP_REGISTERED:-0} == 1 ]] && printf 'server 446901 192.0.2.1 179 Registered\\n'
    [[ ${HTTP_OTHER:-0} == 1 ]] && printf 'server 55555 192.0.2.1 179 Registered\\n'
    ;;
  *"iax2 show registry"*)
    printf 'Host Username Perceived Refresh State\\n'
    [[ ${IAX_REGISTERED:-0} == 1 ]] && printf 'server 446901 192.0.2.1 179 Registered\\n'
    ;;
esac
exit 0
""", encoding="utf-8")
    asterisk.chmod(0o755)

    source = HELPER.read_text(encoding="utf-8")
    source = source.replace('[[ ${EUID:-$(id -u)} -eq 0 ]] || exit 2', 'true')
    source = source.replace('readonly RPT_CONF=/etc/asterisk/rpt.conf', f'readonly RPT_CONF={config}')
    source = source.replace('readonly ASTERISK=/usr/sbin/asterisk', f'readonly ASTERISK={asterisk}')
    source = source.replace('readonly RPT_CONF_TOOL=/usr/local/lib/dvswitch-asl3-support/asl3_rpt_conf.py', f'readonly RPT_CONF_TOOL={tool}')
    runnable = root / "node-links"
    runnable.write_text(source, encoding="utf-8")

    installer = INSTALLER.read_text(encoding="utf-8")
    require("/usr/local/sbin/dvswitch-asl3-node-links --network-status" in installer,
            "ASL support installer must authorize the registration-status helper invocation")

    def run(*args: str, **environment: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(environment)
        return subprocess.run(["bash", str(runnable), *args], text=True, capture_output=True, env=env)

    # Existing peer listing remains valid without a connected external node.
    require(run().returncode == 0, "existing peer-list mode should succeed with an available local ASL node")
    result = run("--network-status", HTTP_REGISTERED="1")
    require(result.returncode == 0, f"registered HTTP ASL node should be available without an external peer: {result.stdout} {result.stderr}")
    require(run("--network-status", IAX_REGISTERED="1").returncode == 0,
            "registered legacy IAX ASL node should be available")
    require(run("--network-status", HTTP_OTHER="1").returncode != 0,
            "a different registered node must not satisfy the local public node check")
    require(run("--network-status").returncode != 0,
            "unregistered public ASL node must report unavailable")
    require(run("--invalid").returncode == 2, "unknown helper arguments must be rejected")

print("PASS: ASL registration status uses the configured public node, supports HTTP/IAX, and does not require external peers")
