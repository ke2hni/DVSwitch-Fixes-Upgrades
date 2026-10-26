#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Check ASL support stays optional and links through Mode Buttons safely."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = (ROOT / "dvswitch-asl3-mod-support.sh").read_text(encoding="utf-8")
LINK = (ROOT / "dvswitch-asl3-node-link").read_text(encoding="utf-8")
ACTIVITY_HOOK = (ROOT / "dvswitch-asl3-link-event").read_text(encoding="utf-8")
ACTIVITY_ENDPOINT = (ROOT / "dvswitch-asl3-activity.php").read_text(encoding="utf-8")
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
require("--check" in SUPPORT and "--install" in SUPPORT and "BACKUP_ROOT=\"/var/backups/dvswitch-mods/asl3-support\"" in SUPPORT,
        "support installer check/install flow or protected backup location is missing")
require("--refresh-asl" in SUPPORT and "--refresh-asl) mode=\"refresh_asl\"" in BUTTON_INSTALLER,
        "existing Mode Buttons must refresh without starting the interactive DMR preset setup")
require("dvswitch-asl3-node-link" in BUTTON_INSTALLER and "is_executable('/usr/local/sbin/dvswitch-asl3-node-link')" in BUTTON_INSTALLER,
        "ASL button and tuning endpoint are not gated by the installed helper")
require('"$ASTERISK" -rx "rpt cmd $local_node ilink $ilink $target"' in LINK and "rxchannel\\s*=\\s*usrp" in LINK,
        "node linking must use the detected local USRP bridge and ASL link command")
require("$target" in LINK and "dvswitch-mode-targets save ASL" in LINK,
        "successful ASL links must persist their node for Favorites and mode switching")
for action, code in (("CONNECT", "3"), ("DISCONNECT", "1"), ("MONITOR", "2"), ("LOCAL_MONITOR", "8"), ("DISCONNECT_ALL", "6")):
    require(action in LINK and f"{action}) ilink={code}" in LINK,
            f"ASL link action {action} must map to documented ilink {code}")
require("aslAction" in BUTTON_INSTALLER and "dvs-asl-links" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8"),
        "ASL checkbox link controls are not connected to the dashboard endpoint")
require("connpgm = /usr/local/sbin/dvswitch-asl3-link-event CONNECTED" in SUPPORT and "discpgm = /usr/local/sbin/dvswitch-asl3-link-event DISCONNECTED" in SUPPORT,
        "ASL activity hooks are not configured for the selected local node")
require("$remote_node" in ACTIVITY_HOOK and "CONNECTED)" in ACTIVITY_HOOK and "DISCONNECTED)" in ACTIVITY_HOOK and "asl3-link-activity.tsv" in ACTIVITY_HOOK,
        "ASL connection event hook must record bounded local link events")
require("ASL Gateway Activity" in (ROOT / "dvswitch-asl3-dashboard.js").read_text(encoding="utf-8") and "astdb.txt" in ACTIVITY_ENDPOINT,
        "ASL Gateway Activity view must use ASTDB node names")
require("if [[ \"$mode\" != BM && \"$mode\" != TGIF ]]" in BUTTON_HELPER,
        "ASL selection must clear DMR pending-target state")
print("PASS: ASL support is optional, menu-connected, backed up, and integrated with Mode Buttons node tuning")
