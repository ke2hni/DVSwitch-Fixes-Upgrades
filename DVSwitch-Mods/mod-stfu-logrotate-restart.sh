#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

# Keep logrotate from leaving STFU stopped after its successful SIGINT exit.

set -Eeuo pipefail
umask 077

readonly SCRIPT_VERSION="1.0.0"
readonly TARGET="${DVS_STFU_LOGROTATE_TARGET:-/etc/logrotate.d/STFU}"
readonly BACKUP_ROOT="${DVS_STFU_LOGROTATE_BACKUP_ROOT:-/var/backups/dvswitch-mods/stfu-logrotate-restart}"

die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
usage() { printf 'STFU logrotate restart %s\nUsage: sudo %s {--check|--install|--uninstall BACKUP-NAME}\n' "$SCRIPT_VERSION" "$(basename "$0")"; }
require_root() { [[ ${EUID:-$(id -u)} -eq 0 ]] || die "Run this script with sudo."; }

main() {
    local action=${1:-} backup_name=${2:-}
    case "$action" in
        --check|--install) [[ $# -eq 1 ]] || die "$action takes no extra arguments." ;;
        --uninstall) [[ $# -eq 2 ]] || die "--uninstall requires one backup name." ;;
        --help|-h) usage; return 0 ;;
        *) usage >&2; return 2 ;;
    esac
    require_root
    command -v python3 >/dev/null 2>&1 || die "Required command not found: python3"
    command -v logrotate >/dev/null 2>&1 || die "Required command not found: logrotate"
    STFU_LOGROTATE_ACTION="$action" \
        STFU_LOGROTATE_TARGET="$TARGET" \
        STFU_LOGROTATE_BACKUP_ROOT="$BACKUP_ROOT" \
        STFU_LOGROTATE_BACKUP_NAME="$backup_name" \
        python3 - <<'PY_STFU_LOGROTATE'
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

action = os.environ["STFU_LOGROTATE_ACTION"]
target = Path(os.environ["STFU_LOGROTATE_TARGET"])
backup_root = Path(os.environ["STFU_LOGROTATE_BACKUP_ROOT"])
backup_name = os.environ["STFU_LOGROTATE_BACKUP_NAME"]
backup_pattern = re.compile(r"install-[0-9]{8}-[0-9]{6}(?:-[0-9]+)?\Z")
stanza_pattern = re.compile(rb"(?ms)^[ \t]*/var/log/dvswitch/STFU\.log[ \t]*\{.*?^[ \t]*\}")
postrotate_pattern = re.compile(rb"(?ms)^[ \t]*postrotate[ \t]*\r?\n(.*?)^[ \t]*endscript[ \t]*\r?$")
command_pattern = re.compile(rb"(?m)^([ \t]*)systemctl[ \t]+(reload|restart)[ \t]+stfu[ \t]*\r?$")


def fail(message):
    raise RuntimeError(message)


def read_regular(path):
    if path.is_symlink() or not path.is_file():
        fail(f"expected an existing regular, non-symlink file: {path}")
    return path.read_bytes()


def inspect(data):
    stanzas = list(stanza_pattern.finditer(data))
    if len(stanzas) != 1:
        fail(f"expected exactly one STFU.log stanza; found {len(stanzas)}")
    stanza = stanzas[0]
    blocks = list(postrotate_pattern.finditer(stanza.group(0)))
    if len(blocks) != 1:
        fail(f"expected exactly one complete STFU postrotate block; found {len(blocks)}")
    block = blocks[0]
    commands = list(command_pattern.finditer(block.group(1)))
    if len(commands) != 1:
        fail(f"expected exactly one 'systemctl reload/restart stfu' command; found {len(commands)}")
    command = commands[0]
    start = stanza.start() + block.start(1) + command.start()
    end = stanza.start() + block.start(1) + command.end()
    return command.group(2).decode("ascii"), start, end


def replace_command(data, expected, replacement):
    state, start, end = inspect(data)
    if state != expected:
        fail(f"expected 'systemctl {expected} stfu'; found 'systemctl {state} stfu'")
    return data[:start] + data[start:end].replace(expected.encode(), replacement.encode(), 1) + data[end:]


def validate_logrotate():
    result = subprocess.run(["logrotate", "-d", "-s", "/dev/null", str(target)], text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        fail("logrotate syntax check failed" + (f": {detail}" if detail else ""))


def atomic_write(content, metadata_path):
    metadata = metadata_path.stat()
    fd, raw_path = tempfile.mkstemp(prefix=f".{target.name}.dvswitch-mods-", dir=target.parent)
    temporary = Path(raw_path)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, metadata.st_uid, metadata.st_gid)
        os.chmod(temporary, stat.S_IMODE(metadata.st_mode))
        os.replace(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate():
    current = read_regular(target)
    state, _, _ = inspect(current)
    validate_logrotate()
    return current, state


try:
    if action in ("--check", "--install"):
        current, state = validate()
        if action == "--check":
            if state == "restart":
                print("ALREADY MODIFIED: STFU log rotation restarts the service. No files changed.")
            else:
                print("READY: STFU log rotation uses reload and can be safely changed to restart. No files changed.")
        elif state == "restart":
            print("PASS: STFU log rotation already restarts the service; no files changed.")
        else:
            replacement = replace_command(current, "reload", "restart")
            if backup_root.exists() and (backup_root.is_symlink() or not backup_root.is_dir()):
                fail(f"refusing unsafe backup path: {backup_root}")
            backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(backup_root, 0o700)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_dir = backup_root / f"install-{stamp}"
            suffix = 0
            while backup_dir.exists():
                suffix += 1
                backup_dir = backup_root / f"install-{stamp}-{suffix}"
            backup_dir.mkdir(mode=0o700)
            backup_file = backup_dir / target.name
            shutil.copy2(target, backup_file)
            try:
                atomic_write(replacement, target)
                if inspect(read_regular(target))[0] != "restart":
                    fail("post-install verification failed")
                validate_logrotate()
            except Exception:
                atomic_write(current, backup_file)
                raise
            print("PASS: STFU log rotation now restarts the service after rotation.")
            print(f"Backup: {backup_dir}")
            print("STFU was not restarted during installation.")
    else:
        if not backup_pattern.fullmatch(backup_name):
            fail(f"invalid backup name: {backup_name}")
        backup_dir = backup_root / backup_name
        if backup_dir.is_symlink() or not backup_dir.is_dir():
            fail(f"protected backup not found: {backup_name}")
        baseline = read_regular(backup_dir / target.name)
        current = read_regular(target)
        if inspect(baseline)[0] != "reload" or inspect(current)[0] != "restart":
            fail("backup or current STFU logrotate state is unexpected; refusing uninstall")
        replacement = replace_command(current, "restart", "reload")
        validate_logrotate()
        try:
            atomic_write(replacement, target)
            if inspect(read_regular(target))[0] != "reload":
                fail("post-uninstall verification failed")
            validate_logrotate()
        except Exception:
            atomic_write(current, backup_dir / target.name)
            raise
        print("PASS: restored the STFU logrotate command to reload; other file edits were preserved.")
        print(f"Protected backup retained: {backup_dir}")
except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(1)
PY_STFU_LOGROTATE
}

main "$@"
