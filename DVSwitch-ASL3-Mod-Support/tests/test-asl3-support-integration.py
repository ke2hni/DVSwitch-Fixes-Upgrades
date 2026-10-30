#!/usr/bin/env python3
# Version: 1.0.5
# SPDX-License-Identifier: MIT

"""Check ASL support is self-contained and leaves Mode Buttons independent."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = (ROOT / 'dvswitch-asl3-mod-support.sh').read_text()
CONTROL = (ROOT / 'dvswitch-asl3-control.php').read_text()
FAVORITES = (ROOT / 'dvswitch-asl3-favorites.py').read_text()
LINK = (ROOT / 'dvswitch-asl3-node-link').read_text()
DASHBOARD = (ROOT / 'dvswitch-asl3-dashboard.js').read_text()
ACTIVITY = (ROOT / 'dvswitch-asl3-activity.php').read_text()
PATCHER = (ROOT / 'lib' / 'patch_dvswitch_asl_mode_switch.py').read_text()
BUTTONS = (ROOT.parent / 'DVSwitch-Mode-Buttons' / 'dvswitch-mode-buttons.sh').read_text()
BUTTON_JS = (ROOT.parent / 'DVSwitch-Mode-Buttons' / 'dvswitch-mode-favorites.js').read_text()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


for entrypoint in ('run_check()', 'run_install()'):
    body = SUPPORT.split(entrypoint, 1)[1].split('\n}\n', 1)[0]
    require(body.index('if ! detect_asl3') < body.index('preflight'),
            entrypoint + ' must detect ASL before preflight')
require('SKIP: ASL 3 is not installed' in SUPPORT and 'DVSwitch remains usable without ASL' in SUPPORT,
        'ASL must remain optional')
require('BUTTONS_DIR' not in SUPPORT and 'BUTTONS_INSTALLER' not in SUPPORT and '--refresh-asl' not in SUPPORT,
        'ASL installation must not invoke or require Mode Buttons')
require('CONTROL_ENDPOINT_TARGET' in SUPPORT and 'FAVORITES_HELPER_TARGET' in SUPPORT and
        'install_index_script' in SUPPORT and 'dvswitch-asl3-dashboard.js' in SUPPORT,
        'ASL install must own and install its dashboard controls')
require("'action' => 'mode'" not in CONTROL and "'mode'" in CONTROL and
        "'/opt/MMDVM_Bridge/dvswitch.sh', 'mode', 'ASL'" in CONTROL and
        'ENSURE_BRIDGE' in CONTROL and "'saveFavorites'" in CONTROL,
        'ASL endpoint must select mode, establish the local bridge, and save favorites')
require("'/usr/local/sbin/dvswitch-asl3-node-link'" in CONTROL and
        "'/usr/local/sbin/dvswitch-asl3-favorites'" in CONTROL and
        'DISCONNECT_BEFORE_CONNECT' in CONTROL,
        'ASL endpoint must call only its own link and favorites helpers')
require('astdb.txt' in CONTROL and 'Disconnect before Connect' in DASHBOARD and
        "button.dataset.mode = 'ASL'" in DASHBOARD and "body: JSON.stringify({ action: 'mode' })" in DASHBOARD and
        "getElementById('dvs-target-input')" in DASHBOARD and "'Enter Node #'" in DASHBOARD and
        "'Enter TG / Ref'" in DASHBOARD and 'dvs-target-tuner' in DASHBOARD,
        'ASL dashboard must own its mode button and reuse the shared target form')
require("linkAction: action" in DASHBOARD and "action: 'link'" in DASHBOARD and
        "action: 'saveFavorites'" in DASHBOARD and "controlEndpoint + '?nodeNames=1'" in DASHBOARD,
        'ASL Tune and Favorites must use the ASL-owned link and ASTDB endpoints')
require("window.setInterval(refreshActivity, 5000)" in DASHBOARD and
        "setInterval(refresh," not in DASHBOARD and "dvswitch-mode-buttons.php?status=1" not in DASHBOARD and
        'digitalModePending' in DASHBOARD and "if (activeMode === 'ASL') setTargetLabel('ASL')" in DASHBOARD,
        'ASL mode selection must not poll stale digital-button state or let it hide the shared tuner')
require("'/etc/dvswitch-asl3-support/favorites.json'" in ACTIVITY and
        "$names[(string)$favorite['node']] = trim($favorite['name'])" in ACTIVITY,
        'user-defined ASL favorite names must override long ASTDB labels in activity rows')
require('ASL_NODE_HELPER' not in BUTTONS and 'mode ASL' not in BUTTONS and
        'ASL' not in BUTTON_JS and 'legacy_asl_button' in BUTTONS and '--install will remove it' in BUTTONS,
        'Mode Buttons must have no ASL behavior and must identify the old embedded button for migration')
require('DISCONNECT_ALL' in LINK and '$1 != keep { print $1 }' in LINK and
        'for attempt in {1..21}; do' in LINK and 'at most five seconds' in LINK,
        'ASL external link cleanup must preserve the private bridge and verify disconnects within five seconds')
require('wait_for_connection "$target"' in LINK and 'did not reach ESTABLISHED state' in LINK and
        'external node %s is established on local public ASL node %s' in LINK,
        'Connect must confirm the remote node on the public node instead of treating CLI acceptance as success')
require('disconnect external links before leaving ASL' in PATCHER and
        'dvswitch-asl3-node-link || return 1' in PATCHER,
        'ASL-owned dvswitch.sh repair must remove external links on every ASL exit')
match = re.search(r"python3 - \"\$FAVORITES_FILE\" <<'PY_ASL_FAVORITES_MIGRATE'\n(.*?)^PY_ASL_FAVORITES_MIGRATE$", SUPPORT, re.M | re.S)
require(match is not None, 'ASL installer must migrate prior user-saved ASL favorites')
with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    legacy = folder / 'legacy.json'
    destination = folder / 'favorites.json'
    legacy.write_text(json.dumps({'ASL': [{'name': 'Parrot test', 'target': '55553'}, {'name': 'Invalid', 'target': '0'}]}))
    migration = match.group(1).replace('/etc/dvswitch-mode-buttons/favorites.json', str(legacy))
    result = subprocess.run([sys.executable, '-c', migration, str(destination)], capture_output=True, text=True)
    require(result.returncode == 0, 'ASL favorite migration failed: ' + result.stderr)
    require(json.loads(destination.read_text()) == [{'name': 'Parrot test', 'node': '55553'}],
            'migration must preserve valid old favorites and reject invalid node numbers')
print('PASS: ASL dashboard, mode transition repair, link controls, and favorites are ASL-owned; Mode Buttons has no ASL runtime dependency.')
