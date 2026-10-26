#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly ASL_REPAIR="$SCRIPT_DIR/repair-dvswitch-asl-mode-switch.sh"
readonly LAYOUT_PATCHER="$SCRIPT_DIR/lib/patch_asl3_dashboard_layout.py"
readonly RPT_CONF="/etc/asterisk/rpt.conf"
readonly ASTERISK="/usr/sbin/asterisk"
readonly BUTTONS_DIR="$SCRIPT_DIR/../DVSwitch-Mode-Buttons"
readonly BUTTONS_INSTALLER="$BUTTONS_DIR/dvswitch-mode-buttons.sh"
readonly BUTTONS_HELPER="/usr/local/sbin/dvswitch-mode-buttons"
readonly NODE_HELPER="$SCRIPT_DIR/dvswitch-asl3-node-link"
readonly EVENT_HELPER="$SCRIPT_DIR/dvswitch-asl3-link-event"
readonly ACTIVITY_ENDPOINT="$SCRIPT_DIR/dvswitch-asl3-activity.php"
readonly DASHBOARD_JS="$SCRIPT_DIR/dvswitch-asl3-dashboard.js"
readonly HELPER_TARGET="/usr/local/sbin/dvswitch-asl3-node-link"
readonly DASHBOARD_JS_TARGET="/usr/share/dvswitch/dvswitch-asl3-dashboard.js"
readonly ACTIVITY_ENDPOINT_TARGET="/usr/share/dvswitch/dvswitch-asl3-activity.php"
readonly EVENT_HELPER_TARGET="/usr/local/sbin/dvswitch-asl3-link-event"
readonly DASHBOARD_SYSTEM="/usr/share/dvswitch/include/system.php"
readonly DASHBOARD_INDEX="/usr/share/dvswitch/index.php"
readonly BUTTONS_ENDPOINT="/usr/share/dvswitch/dvswitch-mode-buttons.php"
readonly BUTTONS_JS="/usr/share/dvswitch/dvswitch-mode-favorites.js"
readonly BUTTONS_SUDOERS="/etc/sudoers.d/dvswitch-mode-buttons"
readonly BUTTONS_TUNE_HELPER="/usr/local/sbin/dvswitch-mode-tune"
readonly BUTTONS_FAVORITES_HELPER="/usr/local/sbin/dvswitch-mode-favorites"
readonly SUDOERS="/etc/sudoers.d/dvswitch-asl3-support"
readonly BACKUP_ROOT="/var/backups/dvswitch-mods/asl3-support"

BACKUP_DIR=""
REPAIR_BACKUP=""
INSTALL_ACTIVE=0

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

detect_asl3() {
    command -v dpkg-query >/dev/null 2>&1 || return 1
    dpkg-query -W -f='${db:Status-Status}' asl3-asterisk 2>/dev/null | grep -qx installed || return 1
    [[ -f "$RPT_CONF" && -x "$ASTERISK" ]]
}

require_file() { [[ -f "$1" && ! -L "$1" ]] || die "Required regular file is unavailable: $1"; }

preflight() {
    [[ ${EUID:-$(id -u)} -eq 0 ]] || die 'Run this command with sudo.'
    for command in bash cat chmod chown cp date grep install mktemp mv node php python3 rm sed systemctl visudo; do command -v "$command" >/dev/null 2>&1 || die "Required command not found: $command"; done
    require_file "$ASL_REPAIR"
    require_file "$LAYOUT_PATCHER"
    require_file "$NODE_HELPER"
    require_file "$EVENT_HELPER"
    require_file "$ACTIVITY_ENDPOINT"
    require_file "$DASHBOARD_JS"
    require_file "$DASHBOARD_SYSTEM"
    require_file "$DASHBOARD_INDEX"
    require_file "$RPT_CONF"
    bash -n "$ASL_REPAIR" "$NODE_HELPER" "$EVENT_HELPER" || die 'ASL support shell syntax validation failed.'
    python3 "$SCRIPT_DIR/lib/patch_dvswitch_asl_mode_switch.py" --help >/dev/null || die 'ASL mode-switch patcher validation failed.'
    python3 -c 'import sys; from pathlib import Path; compile(Path(sys.argv[1]).read_text(), sys.argv[1], "exec")' "$LAYOUT_PATCHER" || die 'ASL dashboard layout patcher syntax validation failed.'
    node --check "$DASHBOARD_JS" >/dev/null || die 'ASL dashboard script syntax validation failed.'
    php -l "$DASHBOARD_SYSTEM" >/dev/null || die 'system.php syntax validation failed.'
    php -l "$DASHBOARD_INDEX" >/dev/null || die 'index.php syntax validation failed.'
    php -l "$ACTIVITY_ENDPOINT" >/dev/null || die 'ASL activity endpoint syntax validation failed.'
    python3 "$LAYOUT_PATCHER" --check "$DASHBOARD_SYSTEM"
    python3 "$SCRIPT_DIR/lib/patch_dvswitch_asl_mode_switch.py" --help >/dev/null
    python3 - "$DASHBOARD_INDEX" <<'PY_ASL_INDEX_CHECK'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
if text.lower().count('</body>') != 1:
    raise SystemExit('ERROR: expected exactly one dashboard </body> script anchor')
tag = '<script src="/dvswitch/dvswitch-asl3-dashboard.js"></script>'
if text.count(tag) > 1:
    raise SystemExit('ERROR: duplicate ASL dashboard script references found')
PY_ASL_INDEX_CHECK
    python3 - "$RPT_CONF" <<'PY_ASL_CHECK'
import re, sys
section = None
matches = []
for raw in open(sys.argv[1], encoding='utf-8', errors='replace'):
    line = raw.split(';', 1)[0].split('#', 1)[0].strip()
    found = re.fullmatch(r'\[\s*(\d{1,8})\s*\]', line)
    if found:
        section = found.group(1)
    elif section and re.match(r'rxchannel\s*=\s*usrp(?:/|\s|$)', line, re.I):
        matches.append(section)
if len(set(matches)) != 1:
    raise SystemExit('ERROR: expected one ASL node with rxchannel=usrp in rpt.conf; found %d' % len(set(matches)))
print('ASL local DVSwitch bridge node: ' + matches[0])
PY_ASL_CHECK
}

snapshot_file() {
    local target=$1 name
    name=$(printf '%s' "$target" | sed 's#^/##; s#/#__#g')
    if [[ -e "$target" || -L "$target" ]]; then
        [[ -f "$target" && ! -L "$target" ]] || die "Refusing non-regular support target: $target"
        cp -a -- "$target" "$BACKUP_DIR/$name"
        printf 'present\n' > "$BACKUP_DIR/$name.state"
    else
        printf 'absent\n' > "$BACKUP_DIR/$name.state"
    fi
}

restore_snapshot() {
    local target=$1 name state
    name=$(printf '%s' "$target" | sed 's#^/##; s#/#__#g')
    [[ -f "$BACKUP_DIR/$name.state" ]] || return 0
    state=$(cat "$BACKUP_DIR/$name.state")
    if [[ "$state" == present ]]; then
        install -d -o root -g root -m 0755 "$(dirname "$target")"
        cp -a -- "$BACKUP_DIR/$name" "$target"
    else
        rm -f -- "$target"
    fi
}

rollback_install() {
    local status=$?
    trap - ERR
    if [[ $INSTALL_ACTIVE -eq 1 && -n "$BACKUP_DIR" ]]; then
        printf 'ERROR: ASL dashboard installation failed; restoring its saved files.\n' >&2
        for target in "$DASHBOARD_SYSTEM" "$DASHBOARD_INDEX" "$HELPER_TARGET" "$EVENT_HELPER_TARGET" "$DASHBOARD_JS_TARGET" "$ACTIVITY_ENDPOINT_TARGET" "$SUDOERS" "$BUTTONS_ENDPOINT" "$BUTTONS_JS" "$BUTTONS_SUDOERS" "$BUTTONS_TUNE_HELPER" "$BUTTONS_FAVORITES_HELPER" "$RPT_CONF"; do restore_snapshot "$target" || printf 'ERROR: rollback failed for %s.\n' "$target" >&2; done
        if [[ -n "$REPAIR_BACKUP" ]]; then "$ASL_REPAIR" --restore "$REPAIR_BACKUP" || printf 'ERROR: rollback of dvswitch.sh failed.\n' >&2; fi
        systemctl restart apache2 >/dev/null 2>&1 || true
    fi
    exit "$status"
}
trap rollback_install EXIT

install_index_script() {
    python3 - "$DASHBOARD_INDEX" <<'PY_ASL_INDEX_INSTALL'
import os, stat, sys, tempfile
path = sys.argv[1]
if os.path.islink(path) or not os.path.isfile(path): raise SystemExit('ERROR: dashboard index.php is not a regular file')
data = open(path, 'rb').read()
tag = b'<script src="/dvswitch/dvswitch-asl3-dashboard.js"></script>'
if tag not in data:
    pos = data.lower().rfind(b'</body>')
    if pos < 0 or data.lower().count(b'</body>') != 1: raise SystemExit('ERROR: dashboard script anchor is missing or ambiguous')
    info = os.stat(path)
    newline = b'\r\n' if b'\r\n' in data else b'\n'
    fd, tmp = tempfile.mkstemp(prefix='.index.php.asl3-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data[:pos] + tag + newline + data[pos:])
        os.chown(tmp, info.st_uid, info.st_gid)
        os.chmod(tmp, stat.S_IMODE(info.st_mode))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
PY_ASL_INDEX_INSTALL
}

install_sudoers() {
    local temporary
    install -d -o root -g root -m 0755 /etc/sudoers.d
    temporary=$(mktemp /etc/sudoers.d/.dvswitch-asl3-support.XXXXXX)
    printf '%s\n' 'www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-asl3-node-link' > "$temporary"
    chown root:root "$temporary"
    chmod 0440 "$temporary"
    visudo -cf "$temporary" >/dev/null || { rm -f "$temporary"; die 'ASL sudo rule validation failed.'; }
    mv -fT "$temporary" "$SUDOERS"
}

run_check() {
    if ! detect_asl3; then
        printf 'SKIP: ASL 3 is not installed. No files changed; DVSwitch remains usable without ASL.\n'
        return 0
    fi
    preflight
    if [[ -e "$BUTTONS_HELPER" ]]; then
        [[ -x "$BUTTONS_INSTALLER" ]] || die 'Mode Buttons is installed but its repository installer is unavailable; refusing a partial ASL update.'
        (cd "$BUTTONS_DIR" && ./dvswitch-mode-buttons.sh --check)
    fi
    "$ASL_REPAIR" --check
    printf 'PASS: ASL 3 dashboard support is ready; --check made no changes.\n'
}

run_install() {
    local target stamp
    if ! detect_asl3; then
        printf 'SKIP: ASL 3 is not installed. No files changed; DVSwitch remains usable without ASL.\n'
        return 0
    fi
    preflight
    if [[ -e "$BUTTONS_HELPER" ]]; then
        [[ -x "$BUTTONS_INSTALLER" ]] || die 'Mode Buttons is installed but its repository installer is unavailable; refusing a partial ASL update.'
        (cd "$BUTTONS_DIR" && ./dvswitch-mode-buttons.sh --check)
    fi
    "$ASL_REPAIR" --check
    stamp=$(date +%Y%m%d-%H%M%S)
    [[ ! -L "$BACKUP_ROOT" ]] || die "Refusing symbolic-link backup root: $BACKUP_ROOT"
    install -d -o root -g root -m 0700 "$BACKUP_ROOT"
    BACKUP_DIR="$BACKUP_ROOT/install-$stamp"
    local collision=0
    while [[ -e "$BACKUP_DIR" ]]; do collision=$((collision + 1)); BACKUP_DIR="$BACKUP_ROOT/install-$stamp-$collision"; done
    install -d -o root -g root -m 0700 "$BACKUP_DIR"
    for target in "$DASHBOARD_SYSTEM" "$DASHBOARD_INDEX" "$HELPER_TARGET" "$EVENT_HELPER_TARGET" "$DASHBOARD_JS_TARGET" "$ACTIVITY_ENDPOINT_TARGET" "$SUDOERS" "$BUTTONS_ENDPOINT" "$BUTTONS_JS" "$BUTTONS_SUDOERS" "$BUTTONS_TUNE_HELPER" "$BUTTONS_FAVORITES_HELPER" "$RPT_CONF"; do snapshot_file "$target"; done
    INSTALL_ACTIVE=1

    install -d -o root -g root -m 0755 /usr/local/sbin "$(dirname "$DASHBOARD_JS_TARGET")"
    install -o root -g root -m 0755 "$NODE_HELPER" "$HELPER_TARGET"
    install -o root -g root -m 0755 "$EVENT_HELPER" "$EVENT_HELPER_TARGET"
    install -o root -g root -m 0644 "$DASHBOARD_JS" "$DASHBOARD_JS_TARGET"
    install -o root -g root -m 0644 "$ACTIVITY_ENDPOINT" "$ACTIVITY_ENDPOINT_TARGET"
    python3 - "$RPT_CONF" <<'PY_ASL_HOOKS'
from pathlib import Path
import os, stat, sys, tempfile
path=Path(sys.argv[1])
raw=path.read_bytes()
if b"DVSwitch-ASL3-Mod-Support: activity hooks v1" in raw:
    if raw.count(b"DVSwitch-ASL3-Mod-Support: activity hooks v1") != 1 or raw.count(b"connpgm = /usr/local/sbin/dvswitch-asl3-link-event CONNECTED") != 1 or raw.count(b"discpgm = /usr/local/sbin/dvswitch-asl3-link-event DISCONNECTED") != 1: raise SystemExit("ERROR: partial or duplicate ASL activity hooks")
else:
    newline=b"\r\n" if b"\r\n" in raw else b"\n"
    lines=raw.splitlines(keepends=True); node=None; matches=[]; start=None
    import re
    for i,line in enumerate(lines):
        body=line.split(b";",1)[0].split(b"#",1)[0].strip()
        found=re.fullmatch(rb"\[\s*(\d{1,8})\s*\]",body)
        if found:
            if node and start is not None: matches.append((node,start,i))
            node=found.group(1).decode(); start=i; continue
        if re.fullmatch(rb"\[.*\]",body):
            if node and start is not None: matches.append((node,start,i))
            node=None; start=i; continue
    if node and start is not None: matches.append((node,start,len(lines)))
    valid=[]
    for item in matches:
        block=b"".join(lines[item[1]:item[2]])
        if re.search(rb"(?im)^\s*rxchannel\s*=\s*usrp(?:/|\s|$)",block): valid.append(item)
    if len(valid)!=1: raise SystemExit("ERROR: could not identify one USRP-backed ASL node stanza")
    local=valid[0]
    block=b"".join(lines[local[1]:local[2]])
    if re.search(rb"(?im)^\s*(?:connpgm|discpgm)\s*=",block): raise SystemExit("ERROR: ASL node already defines connpgm/discpgm; refusing to overwrite activity hooks")
    marker=b"; DVSwitch-ASL3-Mod-Support: activity hooks v1"+newline+b"connpgm = /usr/local/sbin/dvswitch-asl3-link-event CONNECTED"+newline+b"discpgm = /usr/local/sbin/dvswitch-asl3-link-event DISCONNECTED"+newline
    insertion=local[2]
    lines[insertion:insertion]=[marker]
    updated=b"".join(lines)
    info=path.stat(); fd,tmp=tempfile.mkstemp(prefix=".rpt.conf.asl3-",dir=str(path.parent))
    with os.fdopen(fd,"wb") as out: out.write(updated); out.flush(); os.fsync(out.fileno())
    os.chown(tmp,info.st_uid,info.st_gid); os.chmod(tmp,stat.S_IMODE(info.st_mode)); os.replace(tmp,path)
PY_ASL_HOOKS
    install -d -o root -g www-data -m 0750 /var/lib/dvswitch-mods
    python3 "$LAYOUT_PATCHER" --install "$DASHBOARD_SYSTEM"
    install_index_script
    install_sudoers
    if [[ -x "$BUTTONS_HELPER" ]]; then (cd "$BUTTONS_DIR" && ./dvswitch-mode-buttons.sh --refresh-asl); else printf 'NOTICE: install Mode Buttons with manager option 2 to show the ASL mode button and tuner.\n'; fi

    local repair_output
    repair_output=$("$ASL_REPAIR" --install)
    printf '%s\n' "$repair_output"
    REPAIR_BACKUP=$(printf '%s\n' "$repair_output" | sed -n 's#^Backup: .*/\(install-[0-9-]*\)$#\1#p' | tail -n 1)
    php -l "$BUTTONS_ENDPOINT" >/dev/null 2>&1 || [[ ! -e "$BUTTONS_ENDPOINT" ]]
    php -l "$DASHBOARD_SYSTEM" >/dev/null
    php -l "$DASHBOARD_INDEX" >/dev/null
    php -l "$ACTIVITY_ENDPOINT_TARGET" >/dev/null
    visudo -cf "$SUDOERS" >/dev/null
    systemctl restart apache2
    INSTALL_ACTIVE=0
    printf 'PASS: ASL 3 dashboard support installed. Backup: %s\n' "$BACKUP_DIR"
}

case "${1:-}" in
    --check) [[ $# -eq 1 ]] || die '--check takes no extra arguments.'; run_check ;;
    --install) [[ $# -eq 1 ]] || die '--install takes no extra arguments.'; run_install ;;
    --help|-h) printf 'DVSwitch ASL 3 Support\nUsage: sudo %s {--check|--install}\n' "$(basename "$0")" ;;
    *) die "Usage: sudo $(basename "$0") {--check|--install}" ;;
esac
