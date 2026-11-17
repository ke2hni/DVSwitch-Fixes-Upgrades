#!/usr/bin/env python3
# Version: 1.0.0
# Created: 2026-11-17T09:38:00-05:00 by KE2HNI
# SPDX-License-Identifier: MIT
"""Verify the Modes and Networks strip upgrade and proportional cell layout."""

from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'mod-dashboard-stfu-status.sh'
source = INSTALLER.read_text(encoding='utf-8')
match = re.search(r"<<'PY_STFU_MOD'\n(.*?)\nPY_STFU_MOD", source, re.S)
if not match:
    raise SystemExit('FAIL: status installer Python block was not found')

old_system = b'''<?php
// DVSwitch-Mods: STFU Modes and Networks status v1
if (!function_exists('dvsModsShowSTFUStatus')) {
    function dvsModsShowSTFUStatus($label) {
        if (isProcessRunning("STFU")) { echo "<td>".$label."</td>"; }
    }
}
$rawuptime = shell_exec('cat /proc/uptime');
<fieldset><table style="margin-top:2px;">
<tr><th>Modes</th>
    <?php showMode("D-Star", $mmdvmconfigs);?><?php dvsModsShowSTFUStatus("STFU"); ?><?php dvsModsShowASLM17Status("ASL", "ASL"); ?><?php dvsModsShowASLM17Status("M17", "M17"); ?>
    <th>Networks</th>
  <?php showMode("D-Star Network", $mmdvmconfigs);?><?php dvsModsShowSTFUStatus("STFU Net"); ?><?php dvsModsShowASLM17Status("ASL", "ASL Net"); ?><?php dvsModsShowASLM17Status("M17", "M17 Net"); ?></tr>
</table></fieldset>
?>
'''

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    target = root / 'system.php'
    target.write_bytes(old_system)
    fake_bin = root / 'bin'
    fake_bin.mkdir()
    fake_php = fake_bin / 'php'
    fake_php.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
    fake_php.chmod(0o755)
    environment = os.environ.copy()
    environment.update({
        'PATH': str(fake_bin) + os.pathsep + environment.get('PATH', ''),
        'STFU_ACTION': 'install',
        'STFU_TARGET': str(target),
        'STFU_BACKUP_ROOT': str(root / 'backups'),
        'STFU_BACKUP_NAME': '',
    })
    result = subprocess.run([sys.executable, '-c', match.group(1)], env=environment,
                            text=True, capture_output=True)
    if result.returncode:
        raise SystemExit('FAIL: status-strip upgrade failed: ' + result.stderr + result.stdout)
    installed = target.read_bytes()
    if installed.count(b'id="dvs-mods-mode-network-strip"') != 1:
        raise SystemExit('FAIL: strip table did not receive its scoped sizing rules')
    if installed.count(b'<col style="width:5.75%;">') != 16:
        raise SystemExit('FAIL: strip does not have 16 equal status columns')
    for expected in (b'dvsModsShowASLM17Status("ASL", "ASL")',
                     b'dvsModsShowASLM17Status("M17", "M17")',
                     b'dvswitch-asl3-node-links', b'isProcessRunning(\'USRP2M17\')'):
        if expected not in installed:
            raise SystemExit('FAIL: missing ASL/M17 status behavior: ' + expected.decode())
    if installed.count(b'dvsModsShowASLM17Status("ASL"') != 2:
        raise SystemExit('FAIL: ASL mode and network cells were not both installed')
    if installed.count(b'dvsModsShowASLM17Status("M17"') != 2:
        raise SystemExit('FAIL: M17 mode and network cells were not both installed')

    environment['STFU_ACTION'] = 'check'
    result = subprocess.run([sys.executable, '-c', match.group(1)], env=environment,
                            text=True, capture_output=True)
    if result.returncode or 'ALREADY MODIFIED' not in result.stdout:
        raise SystemExit('FAIL: status-strip upgrade is not idempotent: ' + result.stderr + result.stdout)

print('PASS: ASL/M17 status strip migration, connection states, and fixed column sizing')
