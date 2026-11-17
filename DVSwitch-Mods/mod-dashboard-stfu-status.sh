#!/usr/bin/env bash
# Version: 1.0.1
# Updated: 2026-11-16T23:18:42-05:00 by KE2HNI — add ASL and M17 status indicators.
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

# Add STFU, ASL, and M17 status cells to the existing dashboard Modes and Networks strip.
# This standalone installer intentionally modifies only include/system.php.

set -Eeuo pipefail
umask 077

readonly SCRIPT_VERSION="1.0.1"
readonly TARGET="${DVS_STFU_STATUS_TARGET:-/usr/share/dvswitch/include/system.php}"
readonly BACKUP_ROOT="${DVS_STFU_STATUS_BACKUP_ROOT:-/var/backups/dvswitch-mods/dashboard-stfu-status}"

die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
usage() {
    printf 'Dashboard mode status modification %s\n' "$SCRIPT_VERSION"
    printf 'Usage: sudo %s {--check|--install|--uninstall BACKUP-NAME}\n' "$(basename "$0")"
}
require_root() { [[ ${EUID:-$(id -u)} -eq 0 ]] || die "Run this script with sudo."; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"; }

run_python() {
    local action=${1:?action required} backup_name=${2:-}
    STFU_ACTION="$action" STFU_TARGET="$TARGET" STFU_BACKUP_ROOT="$BACKUP_ROOT" STFU_BACKUP_NAME="$backup_name" python3 - <<'PY_STFU_MOD'
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

action = os.environ["STFU_ACTION"]
target = Path(os.environ["STFU_TARGET"])
backup_root = Path(os.environ["STFU_BACKUP_ROOT"])
backup_name = os.environ["STFU_BACKUP_NAME"]
marker = b"// DVSwitch-Mods: STFU Modes and Networks status v1"
asl_m17_marker = b"// DVSwitch-Mods: ASL and M17 Modes and Networks status v1"
function_anchor = b"$rawuptime = shell_exec('cat /proc/uptime');"
mode_original = b'    <?php showMode("D-Star", $mmdvmconfigs);?>'
network_original = b'  <?php showMode("D-Star Network", $mmdvmconfigs);?></tr>'
mode_added = mode_original + b'<?php dvsModsShowSTFUStatus("STFU"); ?>'
network_added = b'  <?php showMode("D-Star Network", $mmdvmconfigs);?><?php dvsModsShowSTFUStatus("STFU Net");?></tr>'
function_signature = b"function dvsModsShowSTFUStatus($label)"
asl_m17_calls = (
    b'<?php dvsModsShowASLM17Status("ASL", "ASL"); ?>',
    b'<?php dvsModsShowASLM17Status("M17", "M17"); ?>',
    b'<?php dvsModsShowASLM17Status("ASL Net", "ASL"); ?>',
    b'<?php dvsModsShowASLM17Status("M17 Net", "M17"); ?>',
)
mode_with_extension = mode_added + asl_m17_calls[0] + asl_m17_calls[1]
network_with_extension = network_added[:-len(b'</tr>')] + asl_m17_calls[2] + asl_m17_calls[3] + b'</tr>'
asl_m17_function_signature = b"function dvsModsShowASLM17Status($label, $mode)"


def fail(message):
    raise RuntimeError(message)


def read_target(path):
    if not path.is_file() or path.is_symlink():
        fail(f"target must be an existing regular, non-symlink file: {path}")
    return path.read_bytes()


def installed_function(data):
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    lines = [
        marker,
        b"if (!function_exists('dvsModsShowSTFUStatus')) {",
        b"    function dvsModsShowSTFUStatus($label) {",
        b'        if (isProcessRunning("STFU")) {',
        b'            echo "<td style=\\"background:#12AD2A; color:#030; width:8%;\\">&nbsp;".$label."&nbsp;</td>\\n";',
        b"        } else {",
        b'            echo "<td style=\\"background:#b00; color:#f9f9f9; width:8%;\\">&nbsp;".$label."&nbsp;</td>\\n";',
        b"        }",
        b"    }",
        b"}",
    ]
    return newline.join(lines)


def installed_asl_m17_function(data):
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    lines = [
        asl_m17_marker,
        b"if (!function_exists('dvsModsShowASLM17Status')) {",
        b"    function dvsModsASLM17Connected($mode) {",
        b"        static $states = array();",
        b"        if (isset($states[$mode])) { return $states[$mode]; }",
        b"        if ($mode === 'M17') { $states[$mode] = isProcessRunning('USRP2M17'); return $states[$mode]; }",
        b"        if ($mode !== 'ASL' || !is_executable('/usr/local/sbin/dvswitch-asl3-node-links')) { $states[$mode] = false; return false; }",
        b"        $links = array(); $status = 1;",
        b"        exec('/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-node-links 2>/dev/null', $links, $status);",
        b"        if ($status !== 0) { $states[$mode] = false; return false; }",
        b"        foreach ($links as $node) { if (preg_match('/^[0-9]+$/', trim($node))) { $states[$mode] = true; return true; } }",
        b"        $states[$mode] = false; return false;",
        b"    }",
        b"    function dvsModsShowASLM17Status($label, $mode) {",
        b"        $connected = dvsModsASLM17Connected($mode);",
        b"        $color = $connected ? '#12AD2A' : '#b00'; $text = $connected ? '#030' : '#f9f9f9';",
        b"        echo '<td style=\"background:'.$color.'; color:'.$text.'; width:8%;\">&nbsp;'.htmlspecialchars($label, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8').'&nbsp;</td>'.PHP_EOL;",
        b"    }",
        b"}",
    ]
    return newline.join(lines)


def inspect(data):
    function = installed_function(data)
    markers = data.count(marker)
    mode_new = data.count(mode_added)
    network_new = data.count(network_added)
    function_count = data.count(function)
    network_present = network_new == 1 or data.count(network_with_extension) == 1
    legacy_stfu = markers == 1 and mode_new == 1 and network_present and function_count == 1
    if markers and not legacy_stfu:
        fail("partial or ambiguous STFU modification found; refusing to change system.php")
    if not markers and (mode_new or network_new or function_signature in data):
        fail("partial or ambiguous STFU modification found; refusing to change system.php")
    ext_present = asl_m17_marker in data or asl_m17_function_signature in data or any(call in data for call in asl_m17_calls)
    if ext_present:
        extension = installed_asl_m17_function(data)
        if (data.count(asl_m17_marker) != 1 or data.count(extension) != 1
                or any(data.count(call) != 1 for call in asl_m17_calls) or not legacy_stfu):
            fail("partial or ambiguous ASL/M17 status modification found; refusing to change system.php")
        return "installed"
    if legacy_stfu:
        return "legacy"
    counts = (data.count(function_anchor), data.count(mode_original), data.count(network_original))
    if counts != (1, 1, 1):
        fail(f"unsupported or ambiguous system.php sections; expected one each of the three matching anchors, found {counts}")
    return "ready"


def make_candidate(data):
    state = inspect(data)
    if state == "installed":
        return data
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    candidate = data
    if state == "ready":
        function = installed_function(data)
        candidate = candidate.replace(function_anchor, function + newline + function_anchor, 1)
        candidate = candidate.replace(mode_original, mode_added, 1)
        candidate = candidate.replace(network_original, network_added, 1)
    extension = installed_asl_m17_function(candidate)
    candidate = candidate.replace(function_anchor, extension + newline + function_anchor, 1)
    candidate = candidate.replace(mode_added, mode_added + asl_m17_calls[0] + asl_m17_calls[1], 1)
    candidate = candidate.replace(network_added, network_with_extension, 1)
    if inspect(candidate) != "installed":
        fail("candidate verification failed")
    return candidate


def lint(path):
    result = subprocess.run(["php", "-l", str(path)], text=True, capture_output=True)
    if result.returncode:
        fail("PHP syntax validation failed: " + (result.stderr or result.stdout).strip())


def atomic_write(destination, content, metadata_from):
    info = metadata_from.stat()
    fd, raw_temp = tempfile.mkstemp(prefix=f".{destination.name}.stfu-", dir=destination.parent)
    temporary = Path(raw_temp)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chown(temporary, info.st_uid, info.st_gid)
        os.chmod(temporary, stat.S_IMODE(info.st_mode))
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def new_backup_directory():
    if backup_root.exists() and backup_root.is_symlink():
        fail(f"refusing symbolic-link backup directory: {backup_root}")
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(backup_root, 0o700)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = backup_root / f"install-{stamp}"
    suffix = 0
    while candidate.exists():
        suffix += 1
        candidate = backup_root / f"install-{stamp}-{suffix}"
    candidate.mkdir(mode=0o700)
    return candidate


try:
    if action in ("check", "install"):
        original = read_target(target)
        state = inspect(original)
        lint(target)
        if action == "check":
            if state == "installed":
                print("ALREADY MODIFIED: STFU, ASL, and M17 status cells are installed. No files changed.")
            else:
                candidate = make_candidate(original)
                fd, raw_temp = tempfile.mkstemp(prefix="dvswitch-stfu-check-", suffix=".php")
                with os.fdopen(fd, "wb") as output:
                    output.write(candidate)
                try:
                    lint(Path(raw_temp))
                finally:
                    Path(raw_temp).unlink(missing_ok=True)
                print("READY: supported Modes and Networks sections found; STFU, ASL, and M17 cells can be installed. No files changed.")
        elif state == "installed":
            print("PASS: STFU, ASL, and M17 status cells are already installed; no new backup created.")
        else:
            candidate = make_candidate(original)
            fd, raw_temp = tempfile.mkstemp(prefix="dvswitch-stfu-install-", suffix=".php", dir=target.parent)
            with os.fdopen(fd, "wb") as output:
                output.write(candidate)
            temp_path = Path(raw_temp)
            try:
                lint(temp_path)
            finally:
                temp_path.unlink(missing_ok=True)
            backup = new_backup_directory()
            shutil.copy2(target, backup / target.name)
            try:
                atomic_write(target, candidate, target)
                lint(target)
                if inspect(read_target(target)) != "installed":
                    fail("post-install verification failed")
            except Exception:
                atomic_write(target, original, backup / target.name)
                raise
            print("PASS: STFU, ASL, and M17 status cells installed atomically.")
            print(f"Backup: {backup}")
    elif action == "uninstall":
        if not re.fullmatch(r"install-[0-9]{8}-[0-9]{6}(?:-[0-9]+)?", backup_name):
            fail(f"invalid backup name: {backup_name}")
        backup_dir = backup_root / backup_name
        if not backup_dir.is_dir() or backup_dir.is_symlink():
            fail(f"protected backup not found: {backup_name}")
        backup_file = backup_dir / target.name
        original = read_target(backup_file)
        lint(backup_file)
        current = read_target(target)
        if inspect(current) != "installed":
            fail("current system.php does not contain the complete STFU modification; refusing uninstall")
        lint(target)
        atomic_write(target, original, backup_file)
        lint(target)
        print(f"PASS: system.php restored from {backup_name}.")
    else:
        fail(f"unknown action: {action}")
except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(1)
PY_STFU_MOD
}

main() {
    require_root
    require_command python3
    require_command php
    case "${1:-}" in
        --check)
            [[ $# -eq 1 ]] || die "--check takes no extra arguments."
            run_python check
            ;;
        --install)
            [[ $# -eq 1 ]] || die "--install takes no extra arguments."
            run_python install
            ;;
        --uninstall|--restore)
            [[ $# -eq 2 ]] || die "--uninstall requires one backup name."
            run_python uninstall "$2"
            ;;
        --help|-h) usage ;;
        *) usage >&2; exit 2 ;;
    esac
}

main "$@"
