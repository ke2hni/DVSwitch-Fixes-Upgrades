#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Check ASL support stays optional and links through Mode Buttons safely."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = (ROOT / "dvswitch-asl3-mod-support.sh").read_text(encoding="utf-8")
LINK = (ROOT / "dvswitch-asl3-node-link").read_text(encoding="utf-8")
ACTIVITY_HOOK = (ROOT / "dvswitch-asl3-link-event").read_text(encoding="utf-8")
ACTIVITY_ENDPOINT = (ROOT / "dvswitch-asl3-activity.php").read_text(encoding="utf-8")
RPT_CONF_TOOL = (ROOT / "lib" / "asl3_rpt_conf.py").read_text(encoding="utf-8")
MANAGER = (ROOT.parent / "DVSwitch-Mods" / "manage-dvswitch-mods.sh").read_text(encoding="utf-8")
BUTTON_INSTALLER = (ROOT.parent / "DVSwitch-Mode-Buttons" / "dvswitch-mode-buttons.sh").read_text(encoding="utf-8")
BUTTON_HELPER = (ROOT.parent / "DVSwitch-Mode-Buttons" / "dvswitch-mode-buttons").read_text(encoding="utf-8")


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
require('"$LAYOUT_PATCHER" check "$DASHBOARD_SYSTEM"' in SUPPORT and '"$LAYOUT_PATCHER" install "$DASHBOARD_SYSTEM"' in SUPPORT,
        "ASL layout patcher calls must use its positional action interface")
require("--check" in SUPPORT and "--install" in SUPPORT and "BACKUP_ROOT=\"/var/backups/dvswitch-mods/asl3-support\"" in SUPPORT,
        "support installer check/install flow or protected backup location is missing")
require("--refresh-asl" in SUPPORT and "--refresh-asl) mode=\"refresh_asl\"" in BUTTON_INSTALLER,
        "existing Mode Buttons must refresh without starting the interactive DMR preset setup")
require('for target in "$TARGET" "$ENDPOINT" "$FAVORITES_JS" "$SUDOERS" "$TUNE_HELPER" "$FAVORITES_HELPER" "$MODE_HELPER"; do backup "$target"; done' in BUTTON_INSTALLER and
        'install -o root -g root -m 755 ./dvswitch-mode-buttons "$MODE_HELPER"' in BUTTON_INSTALLER and
        '"$MODE_CMD" mode ASL' in BUTTON_HELPER,
        "ASL refresh must back up and update the dispatcher so its button runs dvswitch.sh mode ASL")
require('"$BUTTONS_HELPER" "$BUTTONS_ENDPOINT"' in SUPPORT and '"$BUTTONS_HELPER" "$BUTTONS_ENDPOINT"' in SUPPORT.split('rollback_install()', 1)[1],
        "ASL installer must snapshot and restore the shared mode dispatcher on failure")
require("dvswitch-asl3-node-link" in BUTTON_INSTALLER and "is_executable('/usr/local/sbin/dvswitch-asl3-node-link')" in BUTTON_INSTALLER,
        "ASL button and tuning endpoint are not gated by the installed helper")
require('"$ASTERISK" -rx "rpt cmd $local_node ilink $ilink $target"' in LINK and "rxchannel" in RPT_CONF_TOOL and "USRP" in RPT_CONF_TOOL,
        "node linking must use the detected local USRP bridge and ASL link command")
require("$target" in LINK and "dvswitch-mode-targets save ASL" in LINK,
        "successful ASL links must persist their node for Favorites and mode switching")
for action, code in (("CONNECT", "3"), ("DISCONNECT", "1"), ("MONITOR", "2"), ("LOCAL_MONITOR", "8"), ("DISCONNECT_ALL", "6")):
    require(action in LINK and f"{action}) ilink={code}" in LINK,
            f"ASL link action {action} must map to documented ilink {code}")
require("aslAction" in BUTTON_INSTALLER and "dvs-asl-links" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8"),
        "ASL checkbox link controls are not connected to the dashboard endpoint")
require("connpgm = {helper} CONNECTED" in RPT_CONF_TOOL and "discpgm = {helper} DISCONNECTED" in RPT_CONF_TOOL,
        "ASL activity hooks are not configured for the selected local node")
require('"$RPT_CONF_TOOL" install "$RPT_CONF" "/usr/bin/sudo -n $EVENT_HELPER_TARGET"' in SUPPORT and
        "asterisk ALL=(root) NOPASSWD:" in SUPPORT and "[[ ${EUID:-$(id -u)} -eq 0 ]]" in ACTIVITY_HOOK,
        "ASL activity events must use the root-owned logger through a constrained Asterisk sudo rule")
require("(?:\\([^)]*\\))?" in RPT_CONF_TOOL and '"$RPT_CONF_TOOL" check "$RPT_CONF"' in SUPPORT,
        "inherited numeric rpt.conf node stanzas are not handled during preflight")
require("$remote_node" in ACTIVITY_HOOK and "CONNECTED)" in ACTIVITY_HOOK and "DISCONNECTED)" in ACTIVITY_HOOK and "asl3-link-activity.tsv" in ACTIVITY_HOOK,
        "ASL connection event hook must record bounded local link events")
require("ASL Gateway Activity" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and "astdb.txt" in ACTIVITY_ENDPOINT,
        "ASL Gateway Activity view must use ASTDB node names")
dashboard_js = (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8")
require("function normalizeHeader(value)" in dashboard_js and "clean(cell.textContent)" not in dashboard_js,
        "ASL target-label updates must not depend on an undefined global cleaner")
require("document.getElementById('modeInfo')" in dashboard_js and "watchGatewayActivity()" in dashboard_js and
        "normalizeHeader(cells[5].textContent) === ''" in dashboard_js and "cells[5].textContent = 'Src'" in dashboard_js,
        "ASL dashboard must scope the target label and restore the missing Src heading in the supported activity table")
require("if [[ \"$mode\" != BM && \"$mode\" != TGIF ]]" in BUTTON_HELPER,
        "ASL selection must clear DMR pending-target state")
print("PASS: ASL support is optional, menu-connected, backed up, and integrated with Mode Buttons node tuning")
