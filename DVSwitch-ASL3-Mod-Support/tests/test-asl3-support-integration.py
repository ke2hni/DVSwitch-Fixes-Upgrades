#!/usr/bin/env python3
# Version: 1.0.9
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
        'dvs-asl-node' in DASHBOARD and 'dvs-asl-favorites' in DASHBOARD and
        "dataset.mode = 'ASL'" in DASHBOARD,
        'ASL dashboard must own the button, numeric tuner, and database-backed favorites')
# The ASL poller must not overwrite standard mode highlights with raw values such as YSFN.
set_mode = re.search(r'function setMode\(mode\) \{(.*?)\n  \}', DASHBOARD, re.S)
require(set_mode is not None and "document.querySelectorAll('#dvs-mode-buttons [data-mode], #dvs-asl-mode-buttons [data-mode]')" not in set_mode.group(1) and
        "activeMode = mode;" in set_mode.group(1) and
        "#dvs-mode-buttons [data-mode=\"ASL\"], #dvs-asl-mode-buttons [data-mode=\"ASL\"]" in set_mode.group(1) and
        "button.dataset.mode !== 'ASL'" in set_mode.group(1) and
        "#dvs-mode-buttons [data-mode=\"ASL\"].selected" in DASHBOARD,
        'ASL highlighting must survive digital-button clearing and be styled in the shared mode row')
require("setControlMessage(linkSuccessMessage(selected.value, node))" in DASHBOARD and
        "return action === 'DISCONNECT_ALL' ? 'Disconnected all nodes' : (messages[action] || 'ASL link updated') + node;" in DASHBOARD and
        "status.textContent = result.message" not in DASHBOARD and
        DASHBOARD.count("sendControl({ action:'saveFavorites', favorites:next })") == 1,
        'successful ASL actions must show concise action and node text instead of raw helper diagnostics')
require('function placeRxMonitor(mode)' in DASHBOARD and
        "document.getElementById('dvs-target-tuner')" in DASHBOARD and
        "aslTuner.closest('.dvs-favorites-control-line, #dvs-asl-fallback-line')" in DASHBOARD and
        "document.getElementById('dvs-asl-controls-row')" not in DASHBOARD and
        "document.addEventListener('submit', function (event)" in DASHBOARD and
        "event.target !== aslTuner" in DASHBOARD and
        "root.append(actions, replaceLabel)" in DASHBOARD and
        "tunerRow.insertBefore(rxButton, tunerRow.firstChild)" in DASHBOARD and
        "favoritesRow.insertBefore(rxButton, favoritesRow.firstChild)" in DASHBOARD and
        "document.addEventListener('dvswitch-mode-buttons-mode'" in DASHBOARD and
        "aslNodeInput.placeholder = mode === 'ASL' ? 'Enter Node #' : 'Enter TG / Ref';" in DASHBOARD and
        "#dvs-target-input{box-sizing:border-box;width:min(18ch,55vw)}" in DASHBOARD,
        'ASL must reuse one Mode Buttons tuner line, preserve RX Monitor placement, switch the placeholder, and keep the target label readable')
transition = re.search(r'function beginModeTransition\(mode\) \{(.*?)\n  \}', DASHBOARD, re.S)
mode_event = re.search(r'function acceptModeUpdate\(mode\) \{(.*?)\n  \}', DASHBOARD, re.S)
require(transition is not None and
        'pendingMode = mode;' in transition.group(1) and
        'staleModeDuringTransition = activeMode;' in transition.group(1) and
        'setMode(mode)' not in transition.group(1) and
        mode_event is not None and
        "if (pendingMode && mode !== pendingMode) { setMode(activeMode); return; }" in mode_event.group(1) and
        "if (confirmedMode && mode === staleModeDuringTransition) { setMode(confirmedMode); return; }" in mode_event.group(1) and
        'confirmedMode = mode;' in mode_event.group(1) and
        'pendingModeTimer' not in DASHBOARD and
        "document.addEventListener('dvswitch-mode-buttons-mode', function (event)" in DASHBOARD,
        'Mode Buttons success events must control mode changes, ignore late stale status, and avoid timed rollbacks')
require("beginModeTransition('ASL');" in DASHBOARD and
        "acceptModeUpdate('ASL');" in DASHBOARD and
        "if (document.getElementById('dvs-mode-buttons')) {" in DASHBOARD and
        "if (activeMode) setTargetLabel(activeMode);" in DASHBOARD and
        "if (mode === 'ASL' && favoritesRoot) favoritesRoot.hidden = false;" in DASHBOARD,
        'ASL selection must guard against delayed old-mode events, reapply Node after live card refresh, and show the shared line')
require("if (document.getElementById('dvs-mode-buttons')) return;" in DASHBOARD and
        "function refreshStandaloneMode()" in DASHBOARD and
        "fetch('/dvswitch/dvswitch-mode-buttons.php?status=1'" not in DASHBOARD,
        'ASL must follow Mode Buttons events when present and use the dashboard row only in standalone mode')
require("'/etc/dvswitch-asl3-support/favorites.json'" in ACTIVITY and
        "$names[(string)$favorite['node']] = trim($favorite['name'])" in ACTIVITY,
        'user-defined ASL favorite names must override long ASTDB labels in activity rows')
require('ASL_NODE_HELPER' not in BUTTONS and 'mode ASL' not in BUTTONS and
        'ASL' not in BUTTON_JS and 'legacy_asl_button' in BUTTONS and '--install will remove it' in BUTTONS,
        'Mode Buttons must have no ASL behavior and must identify the old embedded button for migration')
require('DISCONNECT_ALL' in LINK and '$1 != keep { print $1 }' in LINK,
        'ASL external link cleanup must preserve the private bridge')
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
