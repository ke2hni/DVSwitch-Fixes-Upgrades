#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Check ASL support stays optional and links through Mode Buttons safely."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = (ROOT / "dvswitch-asl3-mod-support.sh").read_text(encoding="utf-8")
LINK = (ROOT / "dvswitch-asl3-node-link").read_text(encoding="utf-8")
LIVE_LINKS = (ROOT / "dvswitch-asl3-node-links").read_text(encoding="utf-8")
ACTIVITY_HOOK = (ROOT / "dvswitch-asl3-link-event").read_text(encoding="utf-8")
ACTIVITY_ENDPOINT = (ROOT / "dvswitch-asl3-activity.php").read_text(encoding="utf-8")
APACHE_AUDIO_CONF = (ROOT / "apache" / "dvswitch-asl3-webproxy.conf.in").read_text(encoding="utf-8")
AMI_STATUS = (ROOT / "dvswitch-asl3-ami-status.py").read_text(encoding="utf-8")
RPT_CONF_TOOL = (ROOT / "lib" / "asl3_rpt_conf.py").read_text(encoding="utf-8")
USRP_PORT_TOOL = (ROOT / "lib" / "asl3_usrp_ports.py").read_text(encoding="utf-8")
MANAGER = (ROOT.parent / "DVSwitch-Mods" / "manage-dvswitch-mods.sh").read_text(encoding="utf-8")
BUTTON_INSTALLER = (ROOT.parent / "DVSwitch-Mode-Buttons" / "dvswitch-mode-buttons.sh").read_text(encoding="utf-8")
BUTTON_HELPER = (ROOT.parent / "DVSwitch-Mode-Buttons" / "dvswitch-mode-buttons").read_text(encoding="utf-8")
TARGET_HELPER = (ROOT.parent / "DVSwitch-Mode-Buttons" / "dvswitch-mode-targets").read_text(encoding="utf-8")
BUTTON_JS = (ROOT.parent / "DVSwitch-Mode-Buttons" / "dvswitch-mode-favorites.js").read_text(encoding="utf-8")
ASL_DASHBOARD_JS = (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8")
ASL_NET_CARD = (ROOT / "dvswitch-asl3-net-card.php").read_text(encoding="utf-8")


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


for entrypoint in ("run_check()", "run_install()"):
    body = SUPPORT.split(entrypoint, 1)[1].split("\n}\n", 1)[0]
    require(body.index("if ! detect_asl3") < body.index("preflight"),
            entrypoint + " must detect ASL before installer preflight")
require("SKIP: ASL 3 is not installed" in SUPPORT and "DVSwitch remains usable without ASL" in SUPPORT,
        "installer must skip cleanly when ASL is absent")
require('6) Install ASL 3 Support' in MANAGER and '6) run_asl3_support_installer ;;' in MANAGER,
        "manager option 6 is not connected to the optional ASL installer")
require('"$LAYOUT_PATCHER" check "$DASHBOARD_STATUS"' in SUPPORT and '"$LAYOUT_PATCHER" install "$DASHBOARD_STATUS"' in SUPPORT,
        "ASL layout patcher calls must use its positional action interface")
require("--check" in SUPPORT and "--install" in SUPPORT and "BACKUP_ROOT=\"/var/backups/dvswitch-mods/asl3-support\"" in SUPPORT,
        "support installer check/install flow or protected backup location is missing")
require("--refresh-asl" in SUPPORT and "--refresh-asl) mode=\"refresh_asl\"" in BUTTON_INSTALLER,
        "existing Mode Buttons must refresh without starting the interactive DMR preset setup")
require('for target in "$TARGET" "$ENDPOINT" "$FAVORITES_JS" "$SUDOERS" "$TUNE_HELPER" "$FAVORITES_HELPER" "$MODE_HELPER" "$TARGET_HELPER"; do backup "$target"; done' in BUTTON_INSTALLER and
        'install -o root -g root -m 755 ./dvswitch-mode-buttons "$MODE_HELPER"' in BUTTON_INSTALLER and
        'install -o root -g root -m 755 ./dvswitch-mode-targets "$TARGET_HELPER"' in BUTTON_INSTALLER and
        '"$MODE_CMD" mode ASL' in BUTTON_HELPER,
        "ASL refresh must back up and update the dispatcher so its button runs dvswitch.sh mode ASL")
require('"$BUTTONS_HELPER" "$BUTTONS_TARGET_HELPER" "$BUTTONS_ENDPOINT"' in SUPPORT and
        '"$BUTTONS_HELPER" "$BUTTONS_TARGET_HELPER" "$BUTTONS_ENDPOINT"' in SUPPORT.split('rollback_install()', 1)[1],
        "ASL installer must snapshot and restore shared Mode Buttons helpers on failure")
require("dvswitch-asl3-node-link" in BUTTON_INSTALLER and "is_executable('/usr/local/sbin/dvswitch-asl3-node-link')" in BUTTON_INSTALLER,
        "ASL button and tuning endpoint are not gated by the installed helper")
require('"$ASTERISK" -rx "rpt cmd $public_node ilink $ilink $target"' in LINK and
        '"$RPT_CONF_TOOL" public-node "$RPT_CONF"' in LINK and "find_public_node" in RPT_CONF_TOOL and
        "rxchannel" in RPT_CONF_TOOL and "USRP" in RPT_CONF_TOOL,
        "node linking must discover the public node from this unit's rpt.conf even when the bridge is down")
require("$target" in LINK and "dvswitch-mode-targets save ASL" in LINK and "save ASL \"$target\" >/dev/null || true" in LINK and
        "DSTAR|ASL" in TARGET_HELPER,
        "successful ASL links must persist their node for Favorites and mode switching")
for action, code in (("CONNECT", "3"), ("DISCONNECT", "1"), ("MONITOR", "2"), ("LOCAL_MONITOR", "8")):
    require(action in LINK and f"{action}) ilink={code}" in LINK,
            f"ASL link action {action} must map to documented ilink {code}")
require('rpt cmd $public_node ilink 1 $peer' in LINK and '$1 != keep { print $1 }' in LINK and
        'rpt lstats $public_node' in LINK and "ilink 6" not in LINK,
        "Disconnect All must individually remove public-node peers and preserve the private bridge")
require('printf \'DISCONNECT_ALL\\n\' | "$ASL_NODE_HELPER"' in BUTTON_HELPER and
        '"$(<"$STATE_FILE")" == ASL' in BUTTON_HELPER,
        "leaving ASL mode must disconnect external links before switching modes")
require("ENSURE_BRIDGE" in LINK and "rpt cmd $public_node ilink 3 $private_node" in LINK and
        'if [[ "$action" == CONNECT || "$action" == MONITOR || "$action" == LOCAL_MONITOR ]]; then ensure_bridge; fi' in LINK and
        "printf 'ENSURE_BRIDGE\\n' | \"$ASL_NODE_HELPER\"" in BUTTON_HELPER,
        "ASL selection and link actions must re-establish and verify the private-to-public bridge when it is down")
require("aslAction" in BUTTON_INSTALLER and "dvs-asl-links" in ASL_DASHBOARD_JS,
        "ASL checkbox link controls are not connected to the dashboard endpoint")
require("dvs-asl-disconnect-before-connect" in ASL_DASHBOARD_JS and "replaceCheckbox.checked = true" in ASL_DASHBOARD_JS and
        "disconnectBeforeConnect: disconnectBeforeConnect ? '1' : '0'" in BUTTON_JS and
        "$disconnectBeforeConnect = (string)($_POST['disconnectBeforeConnect'] ?? '1');" in BUTTON_INSTALLER and
        "if ($action === 'CONNECT' && $disconnectBeforeConnect === '1')" in BUTTON_INSTALLER,
        "Connect must default to disconnecting previous external ASL links")
replace_before_connect = LINK.index('if [[ "$action" == CONNECT && "${option:-}" == DISCONNECT_BEFORE_CONNECT ]]; then disconnect_external_links; fi')
connect_request = LINK.index('rpt cmd $public_node ilink $ilink $target')
require(replace_before_connect < connect_request and '[[ -z "${option:-}" || ( "$action" == CONNECT && "$option" == DISCONNECT_BEFORE_CONNECT ) ]]' in LINK and
        '$1 != keep { print $1 }' in LINK and
        'if ! awk -v keep="$private_node"' in LINK,
        "replace-connect must wait for external links to clear while retaining the private bridge")
require("Run ASL Link Action" not in ASL_DASHBOARD_JS and "dvs-asl-link-form" not in ASL_DASHBOARD_JS and
        "selectedAslAction" in BUTTON_JS and "aslAction: aslAction" in BUTTON_JS and
        "if (activeMode === 'ASL' && !selectedAslAction)" in BUTTON_JS,
        "ASL link actions must use the existing Tune button and require an explicitly checked action")
require("isset($_POST['target']) && !isset($_POST['aslAction'])" in BUTTON_INSTALLER and
        'fwrite($pipes[0], $request . "\\n"); fclose($pipes[0]);' in BUTTON_INSTALLER and
        "width:min(95%,600px)" in ASL_DASHBOARD_JS and "padding:0 8px 3px" in ASL_DASHBOARD_JS,
        "ASL action requests and saved targets must reach the node-link helper with an action")
require('if [[ -x "$TARGET_HELPER" && "$mode" != ASL ]]; then' in BUTTON_HELPER and
        'if [[ ( "$mode" == BM || "$mode" == TGIF ) && -x "$TARGET_HELPER" ]]; then' in BUTTON_HELPER and
        'printf \'CONNECT\\t%s\\n\' "$target" | "$ASL_NODE_HELPER"' not in BUTTON_HELPER,
        "selecting ASL must not automatically reconnect a saved node")
require("connpgm = {helper} CONNECTED" in RPT_CONF_TOOL and "discpgm = {helper} DISCONNECTED" in RPT_CONF_TOOL and
        "find_public_node" in RPT_CONF_TOOL and "ASL local public node:" in RPT_CONF_TOOL,
        "ASL activity hooks are not attached to the discovered local public node")
require('"$RPT_CONF_TOOL" install "$RPT_CONF" "/usr/bin/sudo -n $EVENT_HELPER_TARGET"' in SUPPORT and
        'install -o root -g root -m 0755 "$LINKS_HELPER" "$LINKS_HELPER_TARGET"' in SUPPORT and
        "/usr/local/sbin/dvswitch-asl3-node-links" in SUPPORT and
        "asterisk ALL=(root) NOPASSWD:" in SUPPORT and "[[ ${EUID:-$(id -u)} -eq 0 ]]" in ACTIVITY_HOOK,
        "ASL activity events must use the root-owned logger through a constrained Asterisk sudo rule")
require("(?:\\([^)]*\\))?" in RPT_CONF_TOOL and '"$RPT_CONF_TOOL" check "$RPT_CONF"' in SUPPORT,
        "inherited numeric rpt.conf node stanzas are not handled during preflight")
require("$remote_node" in ACTIVITY_HOOK and "CONNECTED)" in ACTIVITY_HOOK and "DISCONNECTED)" in ACTIVITY_HOOK and "asl3-link-activity.tsv" in ACTIVITY_HOOK,
        "ASL connection event hook must record bounded local link events")
require("$remote_node" != "$private_node" in ACTIVITY_HOOK and "asl3_rpt_conf.py node /etc/asterisk/rpt.conf" in ACTIVITY_HOOK,
        "ASL activity hook must omit the private-to-public bridge from external-link activity")
require("asl3_usrp_ports.py" in SUPPORT and 'readonly ANALOG_BRIDGE_CONF="/opt/Analog_Bridge/Analog_Bridge.ini"' in SUPPORT and
        '"$RPT_CONF" "$ANALOG_BRIDGE_CONF"; do snapshot_file' in SUPPORT and
        '"$RPT_CONF" "$ANALOG_BRIDGE_CONF"; do restore_snapshot' in SUPPORT and
        'if grep -qx \'CHANGED=1\' <<< "$usrp_port_output"; then' in SUPPORT and
        'systemctl restart analog_bridge' in SUPPORT and "USRP/address:remote-port:local-port" in USRP_PORT_TOOL and
        "CHANGED=1" in USRP_PORT_TOOL and "txPort" in USRP_PORT_TOOL and "rxPort" in USRP_PORT_TOOL,
        "ASL support must discover, back up, and align Analog_Bridge USRP ports with the private node")
require("ASL Gateway Activity" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and
        "dvswitch-asl3-node-links" in ACTIVITY_ENDPOINT and "asl3-link-activity.tsv" not in ACTIVITY_ENDPOINT and
        "astdb.txt" in ACTIVITY_ENDPOINT,
        "ASL Gateway Activity must list only live connected nodes with ASTDB names")
require("$time = date('H:i:s M d');" in ACTIVITY_ENDPOINT and "$timezone = date('T');" in ACTIVITY_ENDPOINT and
        "'timezone' => $timezone" in ACTIVITY_ENDPOINT and "Time (' + result.timezone + ')'" in ASL_DASHBOARD_JS,
        "ASL Gateway Activity must use the dashboard server's local time and matching timezone label")
require("connectedNodes" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and
        "updateAnalogBridgeNode" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and
        "box-shadow:0 0 10px #999" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and
        "width:min(95%,600px)" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and
        "new MutationObserver(function ()" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and
        "insertAdjacentElement('beforebegin', activity)" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and
        "name.setAttribute('style', 'display:block;color:#b5651d;font-weight:bold;white-space:normal;')" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and
        "updateAslNameColors" not in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8"),
        "ASL dashboard must show live linked node IDs, keep the Node label through status refreshes, and fit the link controls")
require('readonly DASHBOARD_STATUS="/usr/share/dvswitch/include/status.php"' in SUPPORT and
        'readonly DASHBOARD_CARD_TARGET="/usr/share/dvswitch/include/dvswitch-asl3-net-card.php"' in SUPPORT and
        '"$DASHBOARD_STATUS" "$DASHBOARD_CARD_TARGET"' in SUPPORT,
        "ASL Net card must be installed in the dashboard's left status-card renderer and included in backups")
require('readonly ACTIVITY_STATUS_HELPER_TARGET="/usr/local/sbin/dvswitch-asl3-ami-status"' in SUPPORT and
        '"$ACTIVITY_STATUS_HELPER_TARGET" "$RPT_CONF_TOOL_TARGET"' in SUPPORT and
        'install -o root -g root -m 0755 "$ACTIVITY_STATUS_HELPER" "$ACTIVITY_STATUS_HELPER_TARGET"' in SUPPORT and
        "RptStatus" in AMI_STATUS and 'Command="XStat"' in AMI_STATUS and 'Command="SawStat"' in AMI_STATUS and
        "find_public_node" in AMI_STATUS and "127.0.0.1" in AMI_STATUS,
        "dashboard activity must use local Allmon3-compatible public-node XStat/SawStat data")
require("dvswitch-asl3-ami-status" in ACTIVITY_ENDPOINT and "telemetry" in ACTIVITY_ENDPOINT and
        "Radio RX" in ACTIVITY_ENDPOINT and "System TX" in ACTIVITY_ENDPOINT and
        "'loss' => '0%'" in ACTIVITY_ENDPOINT and "'ber' => '0.0%'" in ACTIVITY_ENDPOINT and
        "['Time', 'Mode', 'Node', 'Name', 'Target', 'Src', 'Dur(s)', 'Loss', 'BER']" in ASL_DASHBOARD_JS and
        "No external ASL nodes connected" in ASL_DASHBOARD_JS and "activityStarted" in ASL_DASHBOARD_JS,
        "ASL activity must match Gateway Activity columns and display current keying and duration")
require("routeRxMonitorOverHttps" in ASL_DASHBOARD_JS and
        "wss://' + window.location.host + '/dvswitch-audio/'" in ASL_DASHBOARD_JS and
        "ProxyPass /dvswitch-audio/ ws://127.0.0.1:8080/" in APACHE_AUDIO_CONF and
        'readonly AUDIO_PROXY_CONF_TARGET="/etc/apache2/conf-available/dvswitch-asl3-webproxy.conf"' in SUPPORT and
        'a2disconf a2enconf a2enmod apache2ctl' in SUPPORT and
        'a2enmod proxy proxy_wstunnel' in SUPPORT and 'a2enconf dvswitch-asl3-webproxy' in SUPPORT,
        "RX Monitor must use a same-origin secure WebSocket proxy on HTTPS dashboards")
require('python3 "$ACTIVITY_STATUS_HELPER" >/dev/null 2>&1' in SUPPORT and
        'NOTICE: Allmon3 keying status is unavailable' in SUPPORT,
        "ASL check must report unavailable Allmon3 telemetry without blocking the support install")
require("dvswitch-asl3-node-links" in ASL_NET_CARD and "astdb.txt" in ASL_NET_CARD and
        "dvswitchASL3ShowNetCard" in ASL_NET_CARD and "Listening" in ASL_NET_CARD and
        "$NF" in LIVE_LINKS and "ESTABLISHED" in LIVE_LINKS,
        "ASL Net card must show live established remote nodes, ASTDB names, and current idle state")
dashboard_js = (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8")
require("name.setAttribute('style', 'display:block;color:#b5651d;font-weight:bold;white-space:normal;')" in dashboard_js and
        "updateAslNameColors" not in dashboard_js and "dvs-asl-node-name" not in dashboard_js,
        "ASL activity names must use the same inline color markup as other dashboard names and targets")
require("function normalizeHeader(value)" in dashboard_js and "clean(cell.textContent)" not in dashboard_js,
        "ASL target-label updates must not depend on an undefined global cleaner")
require("document.getElementById('modeInfo')" in dashboard_js and "watchGatewayActivity()" in dashboard_js and
        "normalizeHeader(cells[5].textContent) === ''" in dashboard_js and "cells[5].textContent = 'Src'" in dashboard_js,
        "ASL dashboard must scope the target label and restore the missing Src heading in the supported activity table")
require("if [[ \"$mode\" != BM && \"$mode\" != TGIF ]]" in BUTTON_HELPER,
        "ASL selection must clear DMR pending-target state")
print("PASS: ASL support is optional, menu-connected, backed up, and integrated with Mode Buttons node tuning")
