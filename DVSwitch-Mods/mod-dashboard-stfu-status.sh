#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI
# Version: 1.0.7
# Updated: 2026-11-18T21:44:18-05:00 by KE2HNI — bold active green cells and center all status labels.

# Add STFU, ASL, and M17 status cells to the dashboard Modes and Networks strip.
# This standalone installer intentionally modifies only include/system.php.

set -Eeuo pipefail
umask 077

readonly SCRIPT_VERSION="1.0.7"
readonly TARGET="${DVS_STFU_STATUS_TARGET:-/usr/share/dvswitch/include/system.php}"
readonly BACKUP_ROOT="${DVS_STFU_STATUS_BACKUP_ROOT:-/var/backups/dvswitch-mods/dashboard-stfu-status}"

die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
usage() {
    printf 'Dashboard Modes and Networks status modification %s\n' "$SCRIPT_VERSION"
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
marker = b"// DVSwitch-Mods: Modes and Networks status v6"
previous_marker = b"// DVSwitch-Mods: Modes and Networks status v5"
older_marker = b"// DVSwitch-Mods: Modes and Networks status v4"
oldest_marker = b"// DVSwitch-Mods: Modes and Networks status v3"
ancient_marker = b"// DVSwitch-Mods: Modes and Networks status v2"
old_marker = b"// DVSwitch-Mods: STFU Modes and Networks status v1"
function_anchor = b"$rawuptime = shell_exec('cat /proc/uptime');"
mode_original = b'    <?php showMode("D-Star", $mmdvmconfigs);?>'
network_original = b'  <?php showMode("D-Star Network", $mmdvmconfigs);?></tr>'
mode_added = mode_original + b'<?php dvsModsShowSTFUStatus("STFU"); ?><?php dvsModsShowASLM17Status("ASL", "ASL"); ?><?php dvsModsShowASLM17Status("M17", "M17"); ?>'
network_added = b'  <?php showMode("D-Star Network", $mmdvmconfigs);?><?php dvsModsShowSTFUStatus("STFU Net"); ?><?php dvsModsShowASLM17Status("ASL", "ASL Net"); ?><?php dvsModsShowASLM17Status("M17", "M17 Net"); ?></tr>'
old_mode_added = mode_original + b'<?php dvsModsShowSTFUStatus("STFU"); ?>'
old_network_added = b'  <?php showMode("D-Star Network", $mmdvmconfigs);?><?php dvsModsShowSTFUStatus("STFU Net");?></tr>'
network_base = b'  <?php showMode("D-Star Network", $mmdvmconfigs);?>'
function_signature = b"function dvsModsShowSTFUStatus($label)"
table_marker = b'id="dvs-mods-mode-network-strip"'
style_marker = b'id="dvs-mods-mode-network-style"'
cell_style_marker = b'id="dvs-mods-mode-network-cell-style"'
style_block = (b'<style id="dvs-mods-mode-network-style">'
               b'/* Override upstream showMode inline widths only in this status strip. */'
               b'#dvs-mods-mode-network-strip{table-layout:fixed;width:100%}'
               b'#dvs-mods-mode-network-strip th{width:5%!important;white-space:nowrap}'
               b'#dvs-mods-mode-network-strip td{width:5.625%!important;white-space:nowrap}'
               b'</style>')
wide_style_block = (b'<style id="dvs-mods-mode-network-style">'
                      b'/* Override upstream showMode inline widths only in this status strip. */'
                      b'#dvs-mods-mode-network-strip{table-layout:fixed;width:100%}'
                      b'#dvs-mods-mode-network-strip th{width:7%!important;white-space:nowrap}'
                      b'#dvs-mods-mode-network-strip td{width:5.375%!important;white-space:nowrap}'
                      b'</style>')
legacy_style_block = (b'<style id="dvs-mods-mode-network-style">'
                      b'/* Override upstream showMode inline widths only in this status strip. */'
                      b'#dvs-mods-mode-network-strip{table-layout:fixed;width:100%}'
                      b'#dvs-mods-mode-network-strip th{width:4%!important;white-space:nowrap}'
                      b'#dvs-mods-mode-network-strip td{width:5.75%!important;white-space:nowrap}'
                      b'</style>')
cell_style_block = (b'<style id="dvs-mods-mode-network-cell-style">'
                    b'/* Keep labels centered and emphasize active green cells without changing their colors. */'
                    b'#dvs-mods-mode-network-strip td{text-align:center!important}'
                    b'#dvs-mods-mode-network-strip td[style*="#12AD2A"],#dvs-mods-mode-network-strip td[style*="#0b0"]{font-weight:bold!important}'
                    b'</style>')


def installed_function(data):
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    lines = [
        marker,
        b"if (!function_exists('dvsModsEmitNetworkStatus')) {",
        b"    function dvsModsEmitNetworkStatus($label, $connected) {",
        b'        $background = $connected ? "#12AD2A" : "#b00";',
        b'        $foreground = $connected ? "#000" : "#f9f9f9";',
        # Raw bytes preserve backslashes so PHP keeps the HTML attribute quotes inside its string.
        br"""        echo "<td style=\"background:".$background.";color:".$foreground.";white-space:nowrap;\">&nbsp;".$label."&nbsp;</td>\n";""",
        b"    }",
        b"}",
        b"if (!function_exists('dvsModsAslNetworkConnected')) {",
        b"    function dvsModsAslNetworkConnected() {",
        b"        if (!function_exists('exec') || !is_executable('/usr/local/sbin/dvswitch-asl3-node-links')) { return false; }",
        b"        $nodes = array(); $status = 1;",
        b"        exec('/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-node-links 2>/dev/null', $nodes, $status);",
        b"        if ($status !== 0) { return false; }",
        b"        foreach ($nodes as $node) { if (preg_match('/^[0-9]{1,8}$/D', trim((string)$node))) { return true; } }",
        b"        return false;",
        b"    }",
        b"}",
        b"if (!function_exists('dvsModsShowSTFUStatus')) {",
        b"    function dvsModsShowSTFUStatus($label) {",
        b'        dvsModsEmitNetworkStatus($label, isProcessRunning("STFU"));',
        b"    }",
        b"}",
        b"if (!function_exists('dvsModsShowASLM17Status')) {",
        b"    function dvsModsShowASLM17Status($mode, $label) {",
        b"        $connected = ($mode === 'ASL') ? dvsModsAslNetworkConnected() : isProcessRunning('USRP2M17');",
        b"        dvsModsEmitNetworkStatus($label, $connected);",
        b"    }",
        b"}",
    ]
    return newline.join(lines)


def fail(message):
    raise RuntimeError(message)


def read_target(path):
    if not path.is_file() or path.is_symlink():
        fail(f"target must be an existing regular, non-symlink file: {path}")
    return path.read_bytes()


def inspect(data):
    function = installed_function(data)
    markers = data.count(marker)
    if (markers == 1 and data.count(mode_added) == 1 and data.count(network_added) == 1
            and data.count(function) == 1 and data.count(table_marker) == 1
            and data.count(style_block) == 1 and data.count(style_marker) == 1
            and data.count(cell_style_block) == 1 and data.count(cell_style_marker) == 1):
        return "installed"
    known_v6_styles = (style_block, wide_style_block, legacy_style_block)
    if (markers == 1 and function_signature in data and data.count(mode_added) == 1
            and data.count(network_added) == 1 and data.count(table_marker) == 1
            and sum(data.count(item) for item in known_v6_styles) == 1 and data.count(style_marker) == 1
            and cell_style_marker not in data):
        return "upgrade_v6"
    if (data.count(previous_marker) == 1 and function_signature in data
            and data.count(mode_added) == 1 and data.count(network_added) == 1
            and data.count(table_marker) == 1 and data.count(wide_style_block) == 1
            and data.count(style_marker) == 1):
        return "upgrade_v5"
    if (data.count(older_marker) == 1 and function_signature in data
            and data.count(mode_added) == 1 and data.count(network_added) == 1
            and data.count(table_marker) == 1 and data.count(wide_style_block) == 1
            and (data.count(style_marker) == 1 or
                 (data.count(style_marker) == 2 and data.count(legacy_style_block) == 1))):
        return "upgrade_v4"
    if (data.count(oldest_marker) == 1 and function_signature in data
            and data.count(mode_added) == 1 and data.count(network_added) == 1
            and data.count(table_marker) == 1 and data.count(legacy_style_block) == 1
            and data.count(style_marker) == 1):
        return "upgrade_v3"
    if (data.count(ancient_marker) == 1 and function_signature in data
            and data.count(mode_added) == 1 and data.count(network_added) == 1
            and data.count(table_marker) == 1 and style_marker not in data):
        return "upgrade_v2"
    if data.count(old_marker) == 1 and function_signature in data:
        mode_count = data.count(mode_original)
        network_count = data.count(network_base)
        if mode_count == 1 and network_count == 1 and table_marker not in data:
            return "upgrade"
    if (markers or previous_marker in data or older_marker in data or oldest_marker in data
            or ancient_marker in data
            or old_marker in data or function_signature in data or style_marker in data
            or cell_style_marker in data):
        fail("partial or ambiguous Modes and Networks status modification found; refusing to change system.php")
    counts = (data.count(function_anchor), data.count(mode_original), data.count(network_original))
    if counts != (1, 1, 1):
        fail(f"unsupported or ambiguous system.php sections; expected one each of the three matching anchors, found {counts}")
    return "ready"


def make_candidate(data):
    state = inspect(data)
    if state == "installed":
        return data
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    function = installed_function(data)
    if state in ("upgrade", "upgrade_v2", "upgrade_v3", "upgrade_v4", "upgrade_v5"):
        source_marker = {"upgrade_v5": previous_marker,
                         "upgrade_v4": older_marker,
                         "upgrade_v3": oldest_marker,
                         "upgrade_v2": ancient_marker}.get(state, old_marker)
        start = data.index(source_marker)
        end = data.index(function_anchor, start)
        data = data[:start] + function + newline + data[end:]
    if state == "upgrade":
        mode_start = data.index(mode_original)
        networks_heading = re.search(rb'<th[^>]*>\s*(?:&nbsp;)?Networks(?:&nbsp;)?\s*</th>', data[mode_start:])
        if networks_heading is None:
            fail("Modes row separator is missing or ambiguous during upgrade")
        heading_start = mode_start + networks_heading.start()
        data = data[:mode_start] + mode_added + data[heading_start:]
        network_start = data.index(network_base)
        row_end = data.find(b"</tr>", network_start)
        if row_end < 0:
            fail("Networks row ending is missing or ambiguous during upgrade")
        row_end += len(b"</tr>")
        data = data[:network_start] + network_added + data[row_end:]
    elif state == "ready":
        data = data.replace(function_anchor, function + newline + function_anchor, 1)
        data = data.replace(mode_original, mode_added, 1)
        data = data.replace(network_original, network_added, 1)
    table_replacement = (b'<table id="dvs-mods-mode-network-strip" style="margin-top:2px;table-layout:fixed;width:100%;"><colgroup>'
                         + b'<col style="width:5%;">' + b'<col style="width:5.625%;">' * 8
                         + b'<col style="width:5%;">' + b'<col style="width:5.625%;">' * 8 + b'</colgroup>')
    replacement = style_block + b'\n' + table_replacement
    if state in ("upgrade_v2", "upgrade_v3", "upgrade_v4", "upgrade_v5"):
        previous_table = re.compile(rb'<table id="dvs-mods-mode-network-strip"[^>]*><colgroup>.*?</colgroup>', re.S)
        if len(previous_table.findall(data)) != 1:
            fail("previous Modes and Networks table sizing is missing or ambiguous during upgrade")
        data = previous_table.sub(replacement if state == "upgrade_v2" else table_replacement, data, count=1)
        if state == "upgrade_v3":
            if data.count(legacy_style_block) != 1:
                fail("previous Modes and Networks style block is missing or ambiguous during upgrade")
            data = data.replace(legacy_style_block, style_block, 1)
        elif state in ("upgrade_v4", "upgrade_v5"):
            if data.count(wide_style_block) != 1:
                fail("previous Modes and Networks style block is missing or ambiguous during upgrade")
            data = data.replace(wide_style_block, style_block, 1)
        if state == "upgrade_v4" and data.count(legacy_style_block) == 1:
            data = data.replace(legacy_style_block, b"", 1)
        elif state == "upgrade_v4" and data.count(style_marker) != 1:
            fail("duplicate Modes and Networks style blocks are not a recognized prior layout")
    elif table_marker not in data:
        table = b'<table style="margin-top:2px;">'
        if data.count(table) < 1:
            fail("Modes and Networks table anchor is missing")
        data = data.replace(table, replacement, 1)
    if cell_style_marker not in data:
        if data.count(style_marker) != 1:
            fail("Modes and Networks sizing style is missing or ambiguous while installing label alignment")
        style_start = data.index(style_marker)
        style_end = data.find(b"</style>", style_start)
        if style_end < 0:
            fail("Modes and Networks sizing style has no closing tag")
        style_end += len(b"</style>")
        data = data[:style_end] + newline + cell_style_block + data[style_end:]
    if inspect(data) != "installed":
        fail("candidate verification failed")
    return data


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
                print("ALREADY MODIFIED: the balanced Modes and Networks status strip is installed. No files changed.")
            else:
                candidate = make_candidate(original)
                fd, raw_temp = tempfile.mkstemp(prefix="dvswitch-stfu-check-", suffix=".php")
                with os.fdopen(fd, "wb") as output:
                    output.write(candidate)
                try:
                    lint(Path(raw_temp))
                finally:
                    Path(raw_temp).unlink(missing_ok=True)
                print("READY: exact Modes and Networks sections found; ASL/M17 cells and balanced columns can be installed. No files changed.")
        elif state == "installed":
            print("PASS: the balanced Modes and Networks status strip is already installed; no new backup created.")
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
            print("PASS: ASL/M17 cells and balanced Modes and Networks columns installed atomically.")
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
