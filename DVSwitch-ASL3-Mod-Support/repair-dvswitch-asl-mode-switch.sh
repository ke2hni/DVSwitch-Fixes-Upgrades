#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

# Repair ASL-to-digital mode changes when Analog_Bridge's TLV listener and
# ABInfo report different ports. This changes only the installed dvswitch.sh.

set -Eeuo pipefail
umask 077

readonly SCRIPT_VERSION="1.0.1"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PATCHER="$SCRIPT_DIR/lib/patch_dvswitch_asl_mode_switch.py"
readonly TARGET="/opt/MMDVM_Bridge/dvswitch.sh"
readonly BACKUP_ROOT="/var/backups/dvswitch-mods/asl-mode-switch"

WORK_DIR=""
INSTALL_ACTIVE=0
ACTIVE_BACKUP=""

die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
usage() { printf 'DVSwitch ASL mode-switch repair %s\nUsage: sudo %s {--check|--install|--restore BACKUP-NAME}\n' "$SCRIPT_VERSION" "$(basename "$0")"; }
cleanup() { [[ -z "$WORK_DIR" || ! -d "$WORK_DIR" ]] || rm -rf -- "$WORK_DIR"; }
require_root() { [[ ${EUID:-$(id -u)} -eq 0 ]] || die "Run this repair with sudo."; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"; }
require_regular_file() { [[ -f "$1" && ! -L "$1" ]] || die "Required regular non-symlink file not found: $1"; }
restore_file() { local source=$1 temporary; temporary=$(mktemp --tmpdir="$(dirname "$TARGET")" .dvswitch-asl-mode-restore.XXXXXX); cp -a -- "$source" "$temporary"; mv -fT -- "$temporary" "$TARGET"; }
begin_backup() { local timestamp candidate counter=0; [[ ! -L "$BACKUP_ROOT" ]] || die "Refusing symbolic-link backup directory: $BACKUP_ROOT"; install -d -o root -g root -m 0700 "$BACKUP_ROOT"; timestamp=$(date +%Y%m%d-%H%M%S); candidate="$BACKUP_ROOT/install-$timestamp"; while [[ -e "$candidate" ]]; do counter=$((counter + 1)); candidate="$BACKUP_ROOT/install-$timestamp-$counter"; done; install -d -o root -g root -m 0700 "$candidate"; cp -a -- "$TARGET" "$candidate/dvswitch.sh"; ACTIVE_BACKUP="$candidate"; }
install_candidate() { local temporary; temporary=$(mktemp --tmpdir="$(dirname "$TARGET")" .dvswitch-asl-mode.XXXXXX); cp -- "$WORK_DIR/dvswitch.sh" "$temporary"; chown --reference="$TARGET" "$temporary"; chmod --reference="$TARGET" "$temporary"; mv -fT -- "$temporary" "$TARGET"; }
on_error() { local line=$1 status=$2; trap - ERR; set +e; printf 'ERROR: failed near line %s (status %s).\n' "$line" "$status" >&2; if [[ $INSTALL_ACTIVE -eq 1 && -n "$ACTIVE_BACKUP" ]]; then restore_file "$ACTIVE_BACKUP/dvswitch.sh" && printf 'Automatic rollback completed from %s.\n' "$ACTIVE_BACKUP" >&2 || printf 'ERROR: automatic rollback failed; restore %s/dvswitch.sh manually.\n' "$ACTIVE_BACKUP" >&2; fi; cleanup; exit "$status"; }
trap 'on_error $LINENO $?' ERR
trap cleanup EXIT

preflight() {
    require_root
    for command in bash chmod chown cmp cp date grep install mktemp mv python3 sha256sum ss; do require_command "$command"; done
    require_regular_file "$PATCHER"
    require_regular_file "$TARGET"
    bash -n "$TARGET"
    python3 "$PATCHER" --help >/dev/null
}

prepare_candidate() {
    WORK_DIR=$(mktemp -d /tmp/dvswitch-asl-mode.XXXXXX)
    cp -- "$TARGET" "$WORK_DIR/dvswitch.sh"
    python3 "$PATCHER" --dvswitch "$WORK_DIR/dvswitch.sh"
    bash -n "$WORK_DIR/dvswitch.sh"
    local first_hash
    first_hash=$(sha256sum "$WORK_DIR/dvswitch.sh")
    python3 "$PATCHER" --dvswitch "$WORK_DIR/dvswitch.sh"
    [[ "$first_hash" == "$(sha256sum "$WORK_DIR/dvswitch.sh")" ]] || die "ASL mode-switch patch is not idempotent."
}

show_result() {
    if cmp -s "$TARGET" "$WORK_DIR/dvswitch.sh"; then
        printf 'ALREADY REPAIRED: %s\n' "$TARGET"
    else
        printf 'REPAIR READY: %s\nBefore: ' "$TARGET"
        sha256sum "$TARGET"
        printf 'After:  '
        sha256sum "$WORK_DIR/dvswitch.sh"
    fi
}

run_check() {
    preflight
    prepare_candidate
    show_result
    printf 'PASS: supported dvswitch.sh structure. No files or services changed.\n'
}

run_install() {
    preflight
    prepare_candidate
    show_result
    if cmp -s "$TARGET" "$WORK_DIR/dvswitch.sh"; then
        printf 'PASS: ASL mode-switch repair is already installed.\n'
        return
    fi

    begin_backup
    INSTALL_ACTIVE=1
    install_candidate
    cmp -s "$WORK_DIR/dvswitch.sh" "$TARGET"
    bash -n "$TARGET"
    python3 "$PATCHER" --dvswitch "$TARGET"
    cmp -s "$WORK_DIR/dvswitch.sh" "$TARGET"
    INSTALL_ACTIVE=0
    printf 'PASS: ASL mode-switch repair installed atomically.\nBackup: %s\n' "$ACTIVE_BACKUP"
    printf 'No service restart is required; dvswitch.sh is read when each command runs.\n'
}

run_restore() {
    local name=$1
    preflight
    [[ "$name" =~ ^install-[0-9]{8}-[0-9]{6}(-[0-9]+)?$ ]] || die "Invalid backup name: $name"
    require_regular_file "$BACKUP_ROOT/$name/dvswitch.sh"
    bash -n "$BACKUP_ROOT/$name/dvswitch.sh"
    restore_file "$BACKUP_ROOT/$name/dvswitch.sh"
    bash -n "$TARGET"
    printf 'PASS: dvswitch.sh restored from %s.\n' "$name"
}

main() {
    case "${1:-}" in
        --check) [[ $# -eq 1 ]] || die "Unexpected arguments."; run_check ;;
        --install) [[ $# -eq 1 ]] || die "Unexpected arguments."; run_install ;;
        --restore) [[ $# -eq 2 ]] || die "--restore requires one backup name."; run_restore "$2" ;;
        --help|-h) usage ;;
        "") usage; exit 2 ;;
        *) die "Unknown option: $1" ;;
    esac
}

main "$@"
