#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI
# Version: 1.0.6
# Created: 2026-11-12T15:45:00Z by KE2HNI
# Updated: 2026-11-12T16:10:00-05:00 by KE2HNI — stop DVSwitch units before removing binaries and reload restored ASL link configuration.
# Updated: 2026-11-12T16:20:00-05:00 by KE2HNI — include M17 monitor state and logs in the retained recovery archive.
# Updated: 2026-11-12T11:40:00-05:00 by KE2HNI — allow removal of the DVSwitch Quantar_Bridge package reported by APT.
# Updated: 2026-11-12T11:50:00-05:00 by KE2HNI — allow installed DVSwitch protocol parrot packages in the purge simulation.
# Updated: 2026-11-12T12:05:00-05:00 by KE2HNI — purge packages before archiving and removing residual /opt application trees.
# Updated: 2026-11-12T12:30:00-05:00 by KE2HNI — include the M17 support command directory in the final application cleanup.
# Updated: 2026-11-12T17:15:00-05:00 by KE2HNI — archive and remove the residual DVSwitch dashboard tree after package purge.
# Updated: 2026-11-12T17:30:00-05:00 by KE2HNI — remove Buttons helpers without mutating shared dashboard or bridge files.
# Test-node teardown for this repository; preserves Debian and ASL 3.
set -Eeuo pipefail
umask 077
readonly ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly MODS="$ROOT/DVSwitch-Mods/manage-dvswitch-mods.sh"
readonly BUTTONS="$ROOT/DVSwitch-Mode-Buttons/dvswitch-mode-buttons.sh"
readonly M17="$ROOT/DVSwitch-M17-Support"
readonly ASL_BACKUPS=/var/backups/dvswitch-mods/asl3-support
readonly ASL_REPAIR_BACKUPS=/var/backups/dvswitch-mods/asl-mode-switch
readonly M17_SUPPORT_BACKUPS=/var/backups/dvswitch-mods/m17-private-node-switch
readonly RECOVERY_ROOT=/var/backups/dvswitch-mods/repo-uninstall
readonly CORE_PACKAGES=(dvswitch-server dvswitch-dashboard mmdvm-bridge analog-bridge quantar-bridge ysfgateway p25gateway nxdngateway ircddbgateway stfu nxdnparrot p25parrot ysfparrot)
readonly CORE_DIRS=(/opt/MMDVM_Bridge /opt/Analog_Bridge /opt/YSFClients /opt/P25Clients /opt/NXDNClients /opt/STFU /opt/dvswitch-m17 /usr/local/lib/dvswitch-m17-support /usr/share/dvswitch)
readonly REPO_DATA=(/etc/dvswitch-mode-buttons /var/lib/dvswitch-mode-buttons /etc/dvswitch-asl3-support /var/lib/dvswitch-m17-dashboard /var/lib/dvswitch-m17-bridge /var/lib/dvswitch-mods /etc/dvswitch-m17-dashboard /var/lib/mmdvm/M17Hosts.json /var/log/usrp2m17)
die(){ printf 'ERROR: %s\n' "$*" >&2; exit 1; }
has_pkg(){ dpkg-query -W -f='${db:Status-Status}' "$1" 2>/dev/null | grep -qx installed; }
latest_install_backup(){ find "$1" -mindepth 1 -maxdepth 1 -type d -name 'install-*' -printf '%f\n' 2>/dev/null | sort | tail -n 1; }
plan(){
  printf 'Host: %s\n' "$(hostname -s)"
  has_pkg asl3-asterisk || die 'ASL 3 package asl3-asterisk is not installed; refusing cleanup.'
  [[ -f /etc/asterisk/rpt.conf ]] || die 'ASL rpt.conf is missing; refusing cleanup.'
  awk '/^\[[0-9]+\]/{gsub(/[\[\]]/,""); if ($0==68425) found=1} END{exit !found}' /etc/asterisk/rpt.conf && die 'Public node 68425 is protected.'
  printf '\nWill remove: M17 dashboard, USRP2M17, private-node tools, Mode Buttons, ASL dashboard add-on, and recorded DVSwitch-Mods.\n'
  local b p n=0; local -a installed=()
  b=$(latest_install_backup "$ASL_BACKUPS"); printf 'ASL add-on restore snapshot: %s\n' "${b:-NOT FOUND}"
  printf 'Installed DVSwitch package allowlist:\n'
  for p in "${CORE_PACKAGES[@]}"; do if has_pkg "$p"; then printf '  %s\n' "$p"; installed+=("$p"); n=1; fi; done
  ((n)) || printf '  (none)\n'
  if (( ${#installed[@]} )); then
    local simulated removed base allowed
    simulated=$(apt-get -s purge "${installed[@]}") || die 'APT could not simulate the allowlisted purge; no changes made.'
    printf '\nAPT simulation removals:\n'
    while read -r _ removed _; do
      [[ -n $removed ]] || continue
      printf '  %s\n' "$removed"
      base=${removed%%:*}; allowed=0
      for p in "${CORE_PACKAGES[@]}"; do [[ $base == "$p" ]] && allowed=1; done
      (( allowed )) || die "APT simulation would remove unapproved package $removed; no changes made."
      [[ $base != asterisk && $base != asl3-asterisk ]] || die "APT simulation would remove protected ASL/Asterisk package $removed."
    done < <(printf '%s\n' "$simulated" | awk '$1=="Remv" || $1=="Purg"')
  fi
  printf 'Existing DVSwitch application directories (will be archived, then removed):\n'
  for p in "${CORE_DIRS[@]}"; do [[ ! -e $p ]] || printf '  %s\n' "$p"; done
  printf 'Repository-owned state/favorites/catalog paths will also be archived, then removed.\n'
  printf 'Will not autoremove dependencies or remove Debian, ASL 3/Asterisk, Allmon3, user data, or backups.\n'
}
restore_asl(){
  local b name state target recovery stamp
  b=$(latest_install_backup "$ASL_BACKUPS")
  [[ -n $b ]] || { printf 'NOTICE: no ASL support snapshot; skipped.\n'; return; }
  b="$ASL_BACKUPS/$b"
  local -a targets=(
    /usr/share/dvswitch/include/system.php /usr/share/dvswitch/include/status.php
    /usr/share/dvswitch/include/dvswitch-asl3-net-card.php /etc/apache2/conf-available/dvswitch-asl3-webproxy.conf
    /usr/share/dvswitch/index.php /usr/local/sbin/dvswitch-asl3-node-link
    /usr/local/sbin/dvswitch-asl3-node-links /usr/local/sbin/dvswitch-asl3-link-event
    /usr/local/sbin/dvswitch-asl3-ami-status /usr/local/sbin/dvswitch-asl3-favorites
    /etc/dvswitch-asl3-support/favorites.json /etc/dvswitch-asl3-support/private-node
    /usr/local/lib/dvswitch-asl3-support/asl3_rpt_conf.py /usr/share/dvswitch/dvswitch-asl3-dashboard.js
    /usr/share/dvswitch/dvswitch-asl3-activity.php /usr/share/dvswitch/dvswitch-asl3-control.php
    /etc/sudoers.d/dvswitch-asl3-support /etc/sudoers.d/dvswitch-asl3-activity
    /etc/asterisk/rpt.conf /opt/Analog_Bridge/Analog_Bridge.ini
  )
  for target in "${targets[@]}"; do name=$(printf '%s' "$target" | sed 's#^/##;s#/#__#g'); [[ -f "$b/$name.state" ]] || die "ASL snapshot incomplete at $name.state; stopped."; done
  stamp=$(date +%Y%m%d-%H%M%S); recovery="$RECOVERY_ROOT/pre-asl-restore-$stamp"; install -d -o root -g root -m 0700 "$recovery"
  for target in "${targets[@]}"; do
    name=$(printf '%s' "$target" | sed 's#^/##;s#/#__#g')
    if [[ -e $target || -L $target ]]; then cp -a -- "$target" "$recovery/$name"; printf 'present\n' > "$recovery/$name.state"; else printf 'absent\n' > "$recovery/$name.state"; fi
  done
  a2disconf dvswitch-asl3-webproxy >/dev/null 2>&1 || true
  for target in "${targets[@]}"; do
    name=$(printf '%s' "$target" | sed 's#^/##;s#/#__#g'); state=$(cat "$b/$name.state")
    case "$state" in
      present) [[ -f "$b/$name" && ! -L "$b/$name" ]] || die "Snapshot payload missing: $name"; install -d -o root -g root -m 0755 "$(dirname "$target")"; cp -a -- "$b/$name" "$target" ;;
      absent) rm -f -- "$target" ;;
      *) die "Invalid snapshot state for $target" ;;
    esac
  done
  printf 'PASS: restored ASL add-on snapshot %s; ASL 3 retained.\n' "$(basename "$b")"
  printf 'Recovery copy of pre-restore files: %s\n' "$recovery"
}
remove_addons(){
  [[ ! -f /var/lib/dvswitch-m17-dashboard/install-state.json ]] || bash "$M17/dvswitch-m17-dashboard.sh" --uninstall
  [[ ! -f /var/lib/dvswitch-m17-bridge/install-state.json ]] || printf 'y\ny\n' | python3 "$M17/dvswitch-m17-bridge.py" --uninstall
  local b
  b=$(find "$M17_SUPPORT_BACKUPS" -mindepth 1 -maxdepth 1 -type d -name 'install-*' -printf '%f\n' 2>/dev/null | sort | head -n 1 || true)
  [[ -z $b ]] || bash "$M17/dvswitch-m17-support.sh" --restore "$b"
  [[ ! -f "$BUTTONS" ]] || (cd "$(dirname "$BUTTONS")" && bash ./dvswitch-mode-buttons.sh --uninstall-for-final-removal)
  restore_asl
  if [[ -f /opt/MMDVM_Bridge/dvswitch.sh ]]; then
    b=$(find "$ASL_REPAIR_BACKUPS" -mindepth 1 -maxdepth 1 -type d -name 'install-*' -printf '%f\n' 2>/dev/null | sort | head -n 1 || true)
    [[ -z $b ]] || bash "$ROOT/DVSwitch-ASL3-Mod-Support/repair-dvswitch-asl-mode-switch.sh" --restore "$b"
  fi
  if [[ -s /var/lib/dvswitch-mods/manager/active-installs.tsv ]]; then bash "$MODS" --uninstall all; fi
  [[ ! -d /usr/share/dvswitch/.dvs-dashboard-theme-original ]] || bash "$ROOT/DVSwitch-Mods/dvswitch-dark-mode.sh" restore-original
  [[ ! -d /usr/share/dvswitch/.dvs-dashboard-display-original ]] || bash "$ROOT/DVSwitch-Mode-Buttons/dvswitch-display-layout.sh" restore-original
  systemctl daemon-reload
  apache2ctl configtest >/dev/null 2>&1 && systemctl reload apache2 >/dev/null 2>&1 || true
}
remove_core_directories(){
  local d archive stamp
  stamp=$(date +%Y%m%d-%H%M%S); install -d -o root -g root -m 0700 "$RECOVERY_ROOT"; archive="$RECOVERY_ROOT/dvswitch-apps-$stamp.tar.gz"
  local -a existing=()
  for d in "${CORE_DIRS[@]}"; do [[ ! -e $d && ! -L $d ]] || existing+=("$d"); done
  if (( ${#existing[@]} )); then tar -czpf "$archive" -- "${existing[@]}"; for d in "${existing[@]}"; do rm -rf -- "$d"; done; printf 'Archived and removed DVSwitch application directories: %s\n' "$archive"; fi
}
stop_dvswitch_services(){
  local unit
  for unit in mmdvm_bridge.service analog_bridge.service ysfgateway.service p25gateway.service nxdngateway.service ircddbgateway.service stfu.service usrp2m17.service; do systemctl stop "$unit" >/dev/null 2>&1 || true; done
}
remove_repo_data(){
  local p archive stamp
  stamp=$(date +%Y%m%d-%H%M%S); install -d -o root -g root -m 0700 "$RECOVERY_ROOT"; archive="$RECOVERY_ROOT/repo-data-$stamp.tar.gz"
  local -a existing=()
  for p in "${REPO_DATA[@]}"; do [[ ! -e $p && ! -L $p ]] || existing+=("$p"); done
  if (( ${#existing[@]} )); then tar -czpf "$archive" -- "${existing[@]}"; for p in "${existing[@]}"; do rm -rf -- "$p"; done; printf 'Archived and removed repository data/state: %s\n' "$archive"; fi
}
remove_packages(){
  local -a installed=(); local p
  for p in "${CORE_PACKAGES[@]}"; do has_pkg "$p" && installed+=("$p"); done
  if (( ${#installed[@]} )); then apt-get purge "${installed[@]}"; fi
}
if [[ ${1:-} == --help || ${1:-} == -h ]]; then printf 'DVSwitch test-node uninstaller 1.0.6\nUsage: sudo %s --plan|--remove\n' "$0"; exit 0; fi
[[ $# -eq 1 && ( $1 == --plan || $1 == --remove ) ]] || die "Usage: sudo $0 --plan|--remove"
[[ $EUID -eq 0 ]] || die 'Run with sudo.'
plan
[[ $1 == --plan ]] && exit 0
printf '\nType %s to confirm permanent removal on this test node: ' "$(hostname -s)"
read -r confirmation
[[ $confirmation == "$(hostname -s)" ]] || die 'Confirmation mismatch; no changes made.'
remove_addons
remove_repo_data
stop_dvswitch_services
remove_packages
remove_core_directories
if command -v asterisk >/dev/null 2>&1; then asterisk -rx 'module reload app_rpt.so' >/dev/null 2>&1 || printf 'NOTICE: reload app_rpt.so manually to apply restored ASL node configuration.\n'; fi
printf '\nPASS: add-ons and allowlisted DVSwitch packages removed. No autoremove was run; Debian and ASL 3 remain.\n'
