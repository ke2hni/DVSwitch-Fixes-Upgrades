#!/usr/bin/env python3
# Version: 1.0.1
# Created: 2026-11-17T09:38:00-05:00 by KE2HNI
# Updated: 2026-11-17T11:00:53-05:00 by KE2HNI — catch generated PHP quoting regression.
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


# Protect the PHP statement that caused the node's unexpected-identifier parse error.
php_echo_source = next(line for line in source.splitlines() if 'br' + chr(34) * 3 in line and 'echo' in line)
if r'style=\"background:' not in php_echo_source or r'nowrap;\">' not in php_echo_source:
    raise SystemExit('FAIL: generated PHP echo does not escape its HTML attribute quotes')

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

clean_system = b'''<?php
$rawuptime = shell_exec('cat /proc/uptime');
<fieldset><table style="margin-top:2px;">
<tr><th>Modes</th>
    <?php showMode("D-Star", $mmdvmconfigs);?></tr>
<tr><th>Networks</th>
  <?php showMode("D-Star Network", $mmdvmconfigs);?></tr>
</table></fieldset>
?>
'''

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    fake_bin = root / 'bin'
    fake_bin.mkdir()
    fake_php = fake_bin / 'php'
    # Guard the exact emitted PHP statement here; pi4test --check runs real php -l.
    fake_php.write_text("""#!/usr/bin/env python3
from pathlib import Path
import sys
if len(sys.argv) != 3 or sys.argv[1] != '-l':
    raise SystemExit(2)
content = Path(sys.argv[2]).read_bytes()
if b'dvsModsEmitNetworkStatus' not in content:
    raise SystemExit(0)
php_line = next((line for line in content.splitlines() if b'echo ' in line and b'background:' in line), b'')
if not php_line or php_line.count(bytes([92])) != 3 or b'&nbsp;' not in php_line:
    print('Generated PHP echo escaping regression')
    raise SystemExit(1)
print('Generated PHP echo escaping verified')
""", encoding='utf-8')
    fake_php.chmod(0o755)

    def run(action, target, backup_root, backup_name=''):
        environment = os.environ.copy()
        environment.update({
            'PATH': str(fake_bin) + os.pathsep + environment.get('PATH', ''),
            'STFU_ACTION': action,
            'STFU_TARGET': str(target),
            'STFU_BACKUP_ROOT': str(backup_root),
            'STFU_BACKUP_NAME': backup_name,
        })
        return subprocess.run([sys.executable, '-c', match.group(1)], env=environment,
                              text=True, capture_output=True)

    # Upgrade the previous v1 state and verify check, already-applied, and restore paths.
    target = root / 'upgrade' / 'system.php'
    target.parent.mkdir()
    target.write_bytes(old_system)
    backup_root = root / 'upgrade-backups'
    result = run('check', target, backup_root)
    if result.returncode or 'READY:' not in result.stdout or target.read_bytes() != old_system:
        raise SystemExit('FAIL: upgrade --check changed files or did not report READY: ' + result.stdout + result.stderr)
    result = run('install', target, backup_root)
    if result.returncode:
        raise SystemExit('FAIL: v1 upgrade failed: ' + result.stderr + result.stdout)
    installed = target.read_bytes()
    if installed.count(b'id="dvs-mods-mode-network-strip"') != 1:
        raise SystemExit('FAIL: strip table did not receive its scoped sizing rules')
    if installed.count(b'<col style="width:5.75%;">') != 16:
        raise SystemExit('FAIL: strip does not have 16 equal status columns')
    expected_features = (b'dvsModsShowASLM17Status("ASL", "ASL")',
                         b'dvsModsShowASLM17Status("M17", "M17")',
                         b'dvswitch-asl3-node-links', b"isProcessRunning('USRP2M17')")
    if any(item not in installed for item in expected_features):
        raise SystemExit('FAIL: ASL/M17 status behavior is missing')
    if installed.count(b'dvsModsShowASLM17Status("ASL"') != 2 or installed.count(b'dvsModsShowASLM17Status("M17"') != 2:
        raise SystemExit('FAIL: ASL/M17 mode and network cells were not both installed')
    result = run('check', target, backup_root)
    if result.returncode or 'ALREADY MODIFIED' not in result.stdout:
        raise SystemExit('FAIL: repeat --check did not recognize the installed state')
    backups = list(backup_root.glob('install-*'))
    if len(backups) != 1:
        raise SystemExit('FAIL: upgrade did not create exactly one backup')
    result = run('uninstall', target, backup_root, backups[0].name)
    if result.returncode or target.read_bytes() != old_system:
        raise SystemExit('FAIL: upgrade uninstall did not restore the v1 file')

    # Exercise fresh install from an unmodified dashboard and exact uninstall recovery.
    fresh_target = root / 'fresh' / 'system.php'
    fresh_target.parent.mkdir()
    fresh_target.write_bytes(clean_system)
    fresh_backups = root / 'fresh-backups'
    result = run('check', fresh_target, fresh_backups)
    if result.returncode or 'READY:' not in result.stdout or fresh_target.read_bytes() != clean_system:
        raise SystemExit('FAIL: fresh-install --check changed files or did not report READY')
    result = run('install', fresh_target, fresh_backups)
    if result.returncode:
        raise SystemExit('FAIL: fresh install failed: ' + result.stderr + result.stdout)
    result = run('check', fresh_target, fresh_backups)
    if result.returncode or 'ALREADY MODIFIED' not in result.stdout:
        raise SystemExit('FAIL: fresh install is not recognized as already applied')
    fresh_backup = next(iter(fresh_backups.glob('install-*')), None)
    if fresh_backup is None:
        raise SystemExit('FAIL: fresh install did not create a backup')
    result = run('uninstall', fresh_target, fresh_backups, fresh_backup.name)
    if result.returncode or fresh_target.read_bytes() != clean_system:
        raise SystemExit('FAIL: fresh-install uninstall did not restore the original file')

print('PASS: status strip fresh install, v1 upgrade, --check, already-applied, uninstall recovery, and layout')
