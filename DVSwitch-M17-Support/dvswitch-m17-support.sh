#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI
# Version: 1.0.4
# Created: 2026-11-09T00:41:12-05:00 by KE2HNI
# Updated: 2026-11-10T15:20:00-05:00 by KE2HNI — own both node choices and exclusive switching helper.
# Updated: 2026-11-12T12:20:00-05:00 by KE2HNI — migrate pre-helper backups safely when restoring M17 switch support.

set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly CONFIG=/etc/dvswitch-m17-support.conf
readonly TARGET_DIR=/usr/local/lib/dvswitch-m17-support
readonly M17_LINK=/usr/local/bin/m17
readonly DVS_LINK=/usr/local/bin/dvs-dvswitch
readonly LINK_HELPER=/usr/local/sbin/dvswitch-m17-node-link
readonly BACKUP_ROOT=/var/backups/dvswitch-mods/m17-private-node-switch

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

preflight() {
    [[ ${EUID:-$(id -u)} -eq 0 ]] || die 'Run this installer with sudo.'
    for command in bash cat chown chmod cmp cp date grep head install ln mkdir mktemp mv readlink rm sed wc awk sort sleep; do command -v "$command" >/dev/null 2>&1 || die "Required command not found: $command"; done
    [[ -f "$SCRIPT_DIR/m17" && -f "$SCRIPT_DIR/dvs-dvswitch" && -f "$SCRIPT_DIR/dvswitch-m17-node-link" ]] || die 'M17 switching commands are missing from this folder.'
    bash -n "$SCRIPT_DIR/m17" "$SCRIPT_DIR/dvs-dvswitch" "$SCRIPT_DIR/dvswitch-m17-node-link" || die 'M17 command syntax validation failed.'
    if [[ -e "$CONFIG" || -L "$CONFIG" ]]; then [[ -f "$CONFIG" && ! -L "$CONFIG" ]] && grep -q '^# DVSwitch-M17-Support: ' "$CONFIG" || die "Refusing to use an unowned config file: $CONFIG"; fi
    if [[ -e "$M17_LINK" || -L "$M17_LINK" ]]; then [[ -L "$M17_LINK" && "$(readlink "$M17_LINK")" == "$TARGET_DIR/m17" ]] || { [[ -f "$M17_LINK" ]] && grep -q '^# DVSwitch-M17-Support:' "$M17_LINK"; } || die "Refusing to replace an unrelated command: $M17_LINK"; fi
    if [[ -e "$LINK_HELPER" || -L "$LINK_HELPER" ]]; then [[ -f "$LINK_HELPER" && ! -L "$LINK_HELPER" ]] && grep -q '^# DVSwitch-M17-Support:' "$LINK_HELPER" || die "Refusing to replace an unrelated helper: $LINK_HELPER"; fi
    if [[ -e "$DVS_LINK" || -L "$DVS_LINK" ]]; then [[ -L "$DVS_LINK" && "$(readlink "$DVS_LINK")" == "$TARGET_DIR/dvs-dvswitch" ]] || { [[ -f "$DVS_LINK" ]] && grep -q '^# DVSwitch-M17-Support:' "$DVS_LINK"; } || die "Refusing to replace an unrelated command: $DVS_LINK"; fi
    for path in "$TARGET_DIR/m17" "$TARGET_DIR/dvs-dvswitch"; do
        if [[ -e "$path" || -L "$path" ]]; then [[ -f "$path" && ! -L "$path" ]] && grep -q '^# DVSwitch-M17-Support:' "$path" || die "Refusing to replace an unowned support command: $path"; fi
    done
}

run_check() {
    preflight
    printf 'PASS: M17-owned exclusive private-node switch helper and commands are ready; --check made no changes.\n'
}

run_install() {
    local m17_node dv_node default_node default_dv_node stamp backup_dir temp path suffix backup_name
    preflight
    default_node=1972
    if [[ -f "$CONFIG" && ! -L "$CONFIG" ]]; then
        m17_node=$(sed -n 's/^M17_PRIVATE_NODE=\([0-9][0-9]*\)$/\1/p' "$CONFIG" | head -n 1)
        dv_node=$(sed -n 's/^DVSWITCH_PRIVATE_NODE=\([0-9][0-9]*\)$/\1/p' "$CONFIG" | head -n 1)
        default_node=${m17_node:-1972}
    fi
    default_dv_node=${dv_node:-}
    # Ask the installing operator for both private nodes; M17 owns these selections.
    if [[ $# -ge 2 ]]; then m17_node=$2; fi
    if [[ $# -ge 3 ]]; then dv_node=$3; fi
    if [[ $# -lt 2 && -t 0 ]]; then
        read -r -p "M17 private node number [$default_node]: " m17_node
        m17_node=${m17_node:-$default_node}
    else
        m17_node=${m17_node:-$default_node}
    fi
    [[ "$m17_node" =~ ^[0-9]{1,8}$ ]] && ((10#$m17_node > 0)) || die 'Enter a non-zero numeric M17 private node number.'
    if [[ $# -lt 3 && -t 0 ]]; then read -r -p "DVSwitch private node number [${default_dv_node}]: " dv_node; dv_node=${dv_node:-$default_dv_node}; fi
    [[ "${dv_node:-}" =~ ^[0-9]{1,8}$ ]] && ((10#$dv_node > 0)) || die 'Enter a non-zero numeric DVSwitch private node number.'
    [[ "$dv_node" != "$m17_node" ]] || die 'DVSwitch and M17 must use different private node numbers.'

    if [[ -f "$CONFIG" && -L "$M17_LINK" && -L "$DVS_LINK" && "$(readlink "$M17_LINK")" == "$TARGET_DIR/m17" && "$(readlink "$DVS_LINK")" == "$TARGET_DIR/dvs-dvswitch" && "$(sed -n 's/^M17_PRIVATE_NODE=//p' "$CONFIG")" == "$m17_node" && "$(sed -n 's/^DVSWITCH_PRIVATE_NODE=//p' "$CONFIG")" == "$dv_node" && -f "$TARGET_DIR/m17" && -f "$TARGET_DIR/dvs-dvswitch" && -f "$LINK_HELPER" ]] && cmp -s "$SCRIPT_DIR/m17" "$TARGET_DIR/m17" && cmp -s "$SCRIPT_DIR/dvs-dvswitch" "$TARGET_DIR/dvs-dvswitch" && cmp -s "$SCRIPT_DIR/dvswitch-m17-node-link" "$LINK_HELPER"; then
        printf 'ALREADY INSTALLED: M17 private-node switch commands are current for node %s.\n' "$m17_node"
        return 0
    fi

    # Refuse collisions with files not owned by this component before taking a backup.
    for path in "$CONFIG" "$M17_LINK" "$DVS_LINK" "$LINK_HELPER"; do
        if [[ -e "$path" || -L "$path" ]]; then
            [[ -f "$path" || -L "$path" ]] || die "Refusing to replace a non-file target: $path"
            if [[ "$path" == "$CONFIG" || "$path" == "$LINK_HELPER" ]]; then
                grep -q '^# DVSwitch-M17-Support: ' "$path" || die "Refusing to replace an unowned config file: $path"
            elif [[ -L "$path" ]]; then
                case "$path" in
                    "$M17_LINK") [[ "$(readlink "$path")" == "$TARGET_DIR/m17" ]] || die "Refusing to replace an unrelated symlink: $path" ;;
                    "$DVS_LINK") [[ "$(readlink "$path")" == "$TARGET_DIR/dvs-dvswitch" ]] || die "Refusing to replace an unrelated symlink: $path" ;;
                esac
            else
                grep -q '^# DVSwitch-M17-Support:' "$path" || die "Refusing to replace an unowned command: $path"
            fi
        fi
    done

    # Keep a timestamped copy of every current config, command link, and installed wrapper.
    stamp=$(date +%Y%m%d-%H%M%S)
    install -d -o root -g root -m 0700 "$BACKUP_ROOT"
    backup_dir="$BACKUP_ROOT/install-$stamp"
    local suffix=0
    while [[ -e "$backup_dir" ]]; do suffix=$((suffix + 1)); backup_dir="$BACKUP_ROOT/install-$stamp-$suffix"; done
    install -d -o root -g root -m 0700 "$backup_dir"
    for path in "$CONFIG" "$M17_LINK" "$DVS_LINK" "$LINK_HELPER" "$TARGET_DIR/m17" "$TARGET_DIR/dvs-dvswitch"; do
        backup_name=$(printf '%s' "$path" | sed 's#^/##; s#/#__#g')
        if [[ -e "$path" || -L "$path" ]]; then cp -a -- "$path" "$backup_dir/$backup_name"; printf 'present\n' > "$backup_dir/$backup_name.state"; else printf 'absent\n' > "$backup_dir/$backup_name.state"; fi
    done

    install -d -o root -g root -m 0755 "$TARGET_DIR" /usr/local/bin /etc
    install -o root -g root -m 0755 "$SCRIPT_DIR/m17" "$TARGET_DIR/m17"
    install -o root -g root -m 0755 "$SCRIPT_DIR/dvs-dvswitch" "$TARGET_DIR/dvs-dvswitch"
    install -d -o root -g root -m 0755 /usr/local/sbin
    install -o root -g root -m 0755 "$SCRIPT_DIR/dvswitch-m17-node-link" "$LINK_HELPER"
    # Replace the node selection atomically, then publish the two command symlinks.
    temp=$(mktemp /etc/.dvswitch-m17-support.XXXXXX)
    { printf '# DVSwitch-M17-Support: node selection v2\n'; printf 'M17_PRIVATE_NODE=%s\nDVSWITCH_PRIVATE_NODE=%s\n' "$m17_node" "$dv_node"; } > "$temp"
    chown root:root "$temp"
    chmod 0644 "$temp"
    mv -fT "$temp" "$CONFIG"
    ln -sfn "$TARGET_DIR/m17" "$M17_LINK"
    ln -sfn "$TARGET_DIR/dvs-dvswitch" "$DVS_LINK"
    printf 'PASS: M17 and DVSwitch private-node commands installed. M17 node: %s; DVSwitch node: %s. Backup: %s\n' "$m17_node" "$dv_node" "$backup_dir"
    printf 'NOTICE: The M17 Asterisk USRP stanza and M17 gateway software must be configured separately before running m17.\n'
}

run_restore() {
    local backup_dir=$1 path backup_name state source stamp recovery_dir
    [[ ${EUID:-$(id -u)} -eq 0 ]] || die 'Run this restore with sudo.'
    [[ ! -L "$BACKUP_ROOT" ]] || die "Refusing symbolic-link backup root: $BACKUP_ROOT"
    [[ "$backup_dir" != */* && "$backup_dir" != . && "$backup_dir" != .. ]] || die 'Pass only the backup directory name, not a path.'
    backup_dir="$BACKUP_ROOT/$backup_dir"
    [[ -d "$backup_dir" && ! -L "$backup_dir" ]] || die "Backup directory is unavailable: $backup_dir"
    local -a targets=("$CONFIG" "$M17_LINK" "$DVS_LINK" "$LINK_HELPER" "$TARGET_DIR/m17" "$TARGET_DIR/dvs-dvswitch")
    # Validate every saved state before creating a recovery point or restoring any target.
    for path in "${targets[@]}"; do
        backup_name=$(printf '%s' "$path" | sed 's#^/##; s#/#__#g')
        if [[ ! -f "$backup_dir/$backup_name.state" || -L "$backup_dir/$backup_name.state" ]]; then
            if [[ "$path" == "$LINK_HELPER" ]]; then
                if [[ ! -e "$path" && ! -L "$path" ]] || { [[ -f "$path" && ! -L "$path" ]] && grep -q '^# DVSwitch-M17-Support:' "$path"; }; then
                    printf 'NOTICE: treating missing legacy helper state as absent: %s\n' "$backup_name"
                    continue
                fi
            fi
            die "Backup state is missing: $backup_name.state"
        fi
        state=$(cat "$backup_dir/$backup_name.state")
        case "$state" in
            absent) ;;
            present)
                source="$backup_dir/$backup_name"
                [[ -f "$source" || -L "$source" ]] || die "Saved target is missing: $backup_name"
                if [[ -L "$source" ]]; then
                    case "$path" in
                        "$M17_LINK") [[ "$(readlink "$source")" == "$TARGET_DIR/m17" ]] || die "Saved M17 link target is unexpected: $backup_name" ;;
                        "$DVS_LINK") [[ "$(readlink "$source")" == "$TARGET_DIR/dvs-dvswitch" ]] || die "Saved DVSwitch link target is unexpected: $backup_name" ;;
                        *) die "Unexpected symbolic link in backup: $backup_name" ;;
                    esac
                elif [[ "$path" == "$CONFIG" || "$path" == "$LINK_HELPER" ]]; then
                    grep -q '^# DVSwitch-M17-Support: ' "$source" || die "Saved config is not owned by this component: $backup_name"
                elif [[ "$path" == "$TARGET_DIR/m17" || "$path" == "$TARGET_DIR/dvs-dvswitch" || "$path" == "$LINK_HELPER" || "$path" == "$M17_LINK" || "$path" == "$DVS_LINK" ]]; then
                    grep -q '^# DVSwitch-M17-Support:' "$source" || die "Saved command is not owned by this component: $backup_name"
                fi
                ;;
            *) die "Invalid saved state for $backup_name: $state" ;;
        esac
    done

    stamp=$(date +%Y%m%d-%H%M%S)
    recovery_dir="$BACKUP_ROOT/pre-restore-$stamp"
    local suffix=0
    while [[ -e "$recovery_dir" ]]; do suffix=$((suffix + 1)); recovery_dir="$BACKUP_ROOT/pre-restore-$stamp-$suffix"; done
    install -d -o root -g root -m 0700 "$recovery_dir"
    for path in "${targets[@]}"; do
        backup_name=$(printf '%s' "$path" | sed 's#^/##; s#/#__#g')
        if [[ -e "$path" || -L "$path" ]]; then cp -a -- "$path" "$recovery_dir/$backup_name"; printf 'present\n' > "$recovery_dir/$backup_name.state"; else printf 'absent\n' > "$recovery_dir/$backup_name.state"; fi
    done
    for path in "${targets[@]}"; do
        backup_name=$(printf '%s' "$path" | sed 's#^/##; s#/#__#g')
        if [[ "$path" == "$LINK_HELPER" && ! -f "$backup_dir/$backup_name.state" && ! -L "$backup_dir/$backup_name.state" ]]; then
            state=absent
        else
            state=$(cat "$backup_dir/$backup_name.state")
        fi
        if [[ "$state" == present ]]; then
            install -d -o root -g root -m 0755 "$(dirname "$path")"
            rm -f -- "$path"
            cp -a -- "$backup_dir/$backup_name" "$path"
        else
            rm -f -- "$path"
        fi
    done
    printf 'PASS: Restored M17 switch files from %s. Recovery snapshot: %s\n' "$backup_dir" "$recovery_dir"
}

case "${1:-}" in
    --check) [[ $# -eq 1 ]] || die '--check takes no extra arguments.'; run_check ;;
    --install) [[ $# -le 3 ]] || die '--install accepts M17 and DVSwitch private-node numbers.'; run_install "$@" ;;
    --restore) [[ $# -eq 2 ]] || die '--restore requires one backup directory name.'; run_restore "$2" ;;
    --help|-h) printf 'DVSwitch M17 private-node switching support\nUsage: sudo %s {--check|--install [M17-NODE DVSWITCH-NODE]|--restore BACKUP-DIR}\n' "$(basename "$0")" ;;
    *) die "Usage: sudo $(basename "$0") {--check|--install|--restore BACKUP-DIR}" ;;
esac
