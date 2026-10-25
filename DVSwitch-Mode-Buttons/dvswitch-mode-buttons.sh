#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="1.0.0-test48"
INI="/opt/MMDVM_Bridge/MMDVM_Bridge.ini"
ANALOG_INI="/opt/Analog_Bridge/Analog_Bridge.ini"
VAR="/var/lib/dvswitch/dvs/var.txt"
TARGET="/usr/share/dvswitch/index.php"
STATUS_TARGET="/usr/share/dvswitch/include/status.php"
MODE_HELPER="/usr/local/sbin/dvswitch-mode-buttons"
DMR_HELPER="/usr/local/sbin/dvswitch-dmr-network"
TARGET_HELPER="/usr/local/sbin/dvswitch-mode-targets"
ENDPOINT="/usr/share/dvswitch/dvswitch-mode-buttons.php"
TUNE_HELPER="/usr/local/sbin/dvswitch-mode-tune"
FAVORITES_HELPER="/usr/local/sbin/dvswitch-mode-favorites"
FAVORITES_JS="/usr/share/dvswitch/dvswitch-mode-favorites.js"
FAVORITES_FILE="/etc/dvswitch-mode-buttons/favorites.json"
FAVORITES_STARTER="./favorites.json"
SUDOERS="/etc/sudoers.d/dvswitch-mode-buttons"
LAYOUT_STATE="/var/lib/dvswitch-mode-buttons/display-layout-owned.json"
PRESET_DIR="/etc/dvswitch-mode-buttons/dmr-presets"
LEGACY_PRESET_DIR="/etc/dvswitch-mode-buttons"

die(){ echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run with sudo"
[[ -f "$INI" ]] || die "missing $INI"
[[ -f "$TARGET" ]] || die "missing $TARGET"
[[ -f ./dvswitch-mode-buttons ]] || die 'missing unified mode helper source'
[[ -f ./dvswitch-mode-targets ]] || die 'missing target-state helper source'
[[ -f ./dvswitch-mode-tune ]] || die 'missing target-tuning helper source'
[[ -f ./dvswitch-mode-favorites ]] || die 'missing favorites helper source'
[[ -f ./dvswitch-mode-favorites.js ]] || die 'missing dashboard favorites source'
[[ -f "$FAVORITES_STARTER" ]] || die 'missing favorites starter file'
[[ -f ./install-mode-target-persistence.sh ]] || die 'missing target-persistence installer'
[[ -f ./install-standalone-dmr-master-card.sh ]] || die 'missing standalone DMR-card installer'
[[ -f ./dvswitch-display-layout.sh ]] || die 'missing bundled display-layout installer'
[[ -f ./dvswitch-mode-layout-state ]] || die 'missing display-layout ownership helper'
grep -q '^switch_dmr_network(){' ./dvswitch-mode-buttons || die 'unified DMR switch function is missing'
bash -n ./dvswitch-mode-buttons ./dvswitch-mode-targets ./dvswitch-mode-tune ./install-mode-target-persistence.sh ./install-standalone-dmr-master-card.sh ./dvswitch-display-layout.sh || die 'installer source syntax validation failed'
python3 -c 'from pathlib import Path; compile(Path("dvswitch-mode-favorites").read_text(), "dvswitch-mode-favorites", "exec")' || die 'favorites helper syntax validation failed'
python3 -c 'import json; from pathlib import Path; data=json.loads(Path("favorites.json").read_text()); expected={"BM","TGIF","STFU","YSF","P25","NXDN","DSTAR"}; assert set(data)==expected; assert all(isinstance(items,list) and all(isinstance(item,dict) and set(item)=={"name","target"} for item in items) for items in data.values())' || die 'favorites starter file validation failed'
python3 -c 'from pathlib import Path; compile(Path("dvswitch-mode-layout-state").read_text(), "dvswitch-mode-layout-state", "exec")' || die 'display-layout ownership helper syntax validation failed'

BACKUP_DIR=/var/backups/dvswitch-mode-buttons
backup(){
  install -d -m 700 -o root -g root "$BACKUP_DIR"
  local source=$1 stamp candidate counter=0
  [[ -e "$source" ]] || return 0
  stamp=$(date +%Y%m%d-%H%M%S)
  candidate="$BACKUP_DIR/$(basename "$source").$stamp"
  while [[ -e "$candidate" ]]; do
    counter=$((counter + 1))
    candidate="$BACKUP_DIR/$(basename "$source").$stamp-$counter"
  done
  cp -a "$source" "$candidate"
}

uninstall(){
  install -d -m 700 -o root -g root "$BACKUP_DIR"
  # Capture the last pre-uninstall rollback copies before backing up current files.
  latest_dmr_helper=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'dvswitch-dmr-network.*' -printf '%T@ %p\n' 2>/dev/null | sort -nr | sed -n '1s/^[^ ]* //p')
  backup "$TARGET"
  backup "$ENDPOINT"
  backup "$FAVORITES_JS"
  backup "$SUDOERS"
  backup "$TUNE_HELPER"
  backup "$FAVORITES_HELPER"
  backup "$STATUS_TARGET"
  backup "$LAYOUT_STATE"
  backup /opt/MMDVM_Bridge/dvswitch.sh
  backup /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup
  backup /var/lib/dvswitch-mode-buttons/dmr-tune-pending
  backup "$DMR_HELPER"
  python3 ./dvswitch-mode-layout-state check-restore "$LAYOUT_STATE"
  python3 - "$STATUS_TARGET" /opt/MMDVM_Bridge/dvswitch.sh "$TARGET" <<'PY_BUTTONS_UNINSTALL' || die 'uninstall structure was unsupported; installed controls and helpers were left in place'
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Remove only structurally recognized Mode Buttons edits from shared files."""

from __future__ import annotations

import os
import re
import stat
import sys
import tempfile
from pathlib import Path

STATUS_MARKER = re.compile(
    r"^// DVSwitch-Mode-Buttons: standalone DMR Master display v[1-9]$", re.MULTILINE
)
BUTTONS_HEADING = (
    'echo "<tr><th colspan=\\"2\\">".dvsButtonsDmrMasterHeading($dmrMasterHost, $abinfo).'
    '"</th></tr>\\n";'
)
MODS_HEADING = (
    'echo "<tr><th colspan=\\"2\\">".dvsModsDmrMasterHeading($dmrMasterHost, $abinfo).'
    '"</th></tr>\\n";'
)
FACTORY_HEADING = 'echo "<tr><th colspan=\\"2\\">DMR Master</th></tr>\\n";'

BUTTONS_OUTPUT = (
    'echo "<tr><td  style=\\"background: #ffffed;\\" colspan=\\"2\\"><span '
    'style=\\"color:#b5651d;font-weight: bold;white-space:normal;word-break:normal;'
    'overflow-wrap:anywhere;text-align:center;\\">".dvsButtonsDmrMasterDisplay($dmrMasterHost, '
    '$abinfo)."</span></td></tr>\\n";}'
)
MODS_OUTPUT = (
    'echo "<tr><td  style=\\"background: #ffffed;\\" colspan=\\"2\\"><span '
    'style=\\"color:#b5651d;font-weight:bold;white-space:normal;word-break:normal;'
    'overflow-wrap:anywhere;text-align:center;\\">".dvsModsDmrMasterDisplay($dmrMasterHost, '
    '$abinfo)."</span></td></tr>\\n";}'
)
FACTORY_OUTPUT = (
    'echo "<tr><td  style=\\"background: #ffffed;\\" colspan=\\"2\\"><span '
    'style=\\"color:#b5651d;font-weight: bold\\">".$dmrMasterHost.'
    '"</span></td></tr>\\n";}'
)
NOT_CONNECTED_ROW = (
    'echo "<tr><td  style=\\"background: #ffffed;\\" colspan=\\"2\\"><span '
    'style=\\"color:#b0b0b0;font-weight: bold\\">Not Connected</span></td></tr>\\n";'
)
BUTTONS_CONNECTING_OUTPUT = (
    'echo "<tr><td  style=\\"background: #ffffed;\\" colspan=\\"2\\"><span '
    'style=\\"color:#b5651d;font-weight: bold;white-space:normal;word-break:normal;'
    'overflow-wrap:anywhere;text-align:center;\\">".dvsButtonsDmrMasterDisplay($dmrMasterHost, '
    '$abinfo, true)."</span></td></tr>\\n";'
)
BUTTONS_CONNECTING_CONDITION = (
    "else if (strpos($dmrstat, 'Opening') !== false || strpos($dmrstat, 'Closing') !== false "
    "|| strpos($dmrstat, 'Connection') !== false)"
)
LEGACY_CONNECTING_CONDITION = (
    "else if (strpos($dmrstat, 'Opening') !== false || strpos($dmrstatus, 'Closing') !== false "
    "|| strpos($dmrstatus, 'Connection') !== false)"
)

BRIDGE_MARKER = "# DVSwitch-Mode-Buttons: per-mode target persistence v1"
BRIDGE_BLOCK_OLD = '''    if [ $# -eq 0 ]; then
        getABInfoValue last_tune
    else
        remoteControlCommand "txTg=$1"
        # DVSwitch-Mode-Buttons: per-mode target persistence v1
        if [ -r /var/lib/dvswitch-mode-buttons/current-mode ]; then
            mode=$(tr -d '[:space:]' < /var/lib/dvswitch-mode-buttons/current-mode)
            case "$mode" in
                BM|TGIF|STFU|YSF|P25|NXDN|DSTAR)
                    /usr/local/sbin/dvswitch-mode-targets save "$mode" "$1" >/dev/null || true
                    ;;
            esac
        fi
    fi'''
BRIDGE_BLOCK_TEST13 = '''    if [ $# -eq 0 ]; then
        getABInfoValue last_tune
    else
        remoteControlCommand "txTg=$1"
        # DVSwitch-Mode-Buttons: per-mode target persistence v1
        mode=$(/opt/MMDVM_Bridge/dvswitch.sh mode 2>/dev/null | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')
        case "$mode" in YSFN|YSFW) mode=YSF ;; esac
        case "$mode" in DSTAR|YSF|P25|NXDN) ;; *)
            if [ -r /var/lib/dvswitch-mode-buttons/current-mode ]; then
                mode=$(tr -d '[:space:]' < /var/lib/dvswitch-mode-buttons/current-mode)
            fi
            ;;
        esac
        case "$mode" in
            BM|TGIF|STFU|YSF|P25|NXDN|DSTAR)
                /usr/local/sbin/dvswitch-mode-targets save "$mode" "$1" >/dev/null || true
                ;;
        esac
    fi'''
BRIDGE_BLOCK = '''    if [ $# -eq 0 ]; then
        getABInfoValue last_tune
    else
        remoteControlCommand "txTg=$1"
        # DVSwitch-Mode-Buttons: per-mode target persistence v1
        mode=$(python3 - <<'ABINFO_MODE_PY'
import glob, json, os
files = glob.glob('/tmp/ABInfo_*.json')
files.sort(key=os.path.getmtime, reverse=True)
if files:
    try:
        with open(files[0], encoding='utf-8') as stream:
            data = json.load(stream)
        for value in (data.get('tlv', {}).get('ambe_mode', ''), data.get('ambe_mode', '')):
            value = str(value).strip().upper()
            if value in ('YSFN', 'YSFW'):
                value = 'YSF'
            if value in ('DSTAR', 'YSF', 'P25', 'NXDN'):
                print(value)
                break
    except (OSError, ValueError, TypeError):
        pass
ABINFO_MODE_PY
        )
        case "$mode" in
            DSTAR|YSF|P25|NXDN) ;;
            *)
                if [ -r /var/lib/dvswitch-mode-buttons/current-mode ]; then
                    mode=$(tr -d '[:space:]' < /var/lib/dvswitch-mode-buttons/current-mode)
                fi
                ;;
        esac
        case "$mode" in
            BM|TGIF|STFU|YSF|P25|NXDN|DSTAR)
                /usr/local/sbin/dvswitch-mode-targets save "$mode" "$1" >/dev/null || true
                ;;
        esac
    fi'''
BRIDGE_ORIGINAL = '''    if [ $# -eq 0 ]; then
        getABInfoValue last_tune
    else
        remoteControlCommand "txTg=$1"
    fi'''
INDEX_MARKER = '<!-- DVSwitch-Mode-Buttons 1.0.0-test48 -->'
INDEX_MARKERS = re.compile(r'<!-- DVSwitch-Mode-Buttons 1\.0\.0-test(?:8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|32|33|34|35|36|37|38|39|40|41|42|43|44|45|46|47|48) -->')


class UnsafeStructure(RuntimeError):
    pass


def patch_status(text: str) -> tuple[str, bool]:
    marker_matches = list(STATUS_MARKER.finditer(text))
    heading_count = text.count(".dvsButtonsDmrMasterHeading(")
    display_count = text.count(".dvsButtonsDmrMasterDisplay(")
    helpers_present = bool(marker_matches)
    marker_version = int(re.search(r"v(\d+)$", marker_matches[0].group(0)).group(1)) if marker_matches else 0

    if not helpers_present and heading_count == 0 and display_count == 0:
        return text, False
    expected_displays = 2 if marker_version >= 7 else 1
    if len(marker_matches) != 1 or heading_count != 1 or display_count != expected_displays:
        raise UnsafeStructure("status.php contains incomplete or duplicate Buttons DMR markers")

    required_helpers = [
        "dvsButtonsDmrNetwork",
        "dvsButtonsDmrTalkgroup",
        "dvsButtonsDmrName",
        "dvsButtonsDmrMasterHeading",
        "dvsButtonsDmrMasterDisplay",
    ]
    if re.search(r"standalone DMR Master display v[6789]", text):
        required_helpers.extend(("dvsButtonsDmrSavedCardMode", "dvsButtonsDmrSavedNetwork", "dvsButtonsDmrCurrentMode", "dvsButtonsDmrSavedTalkgroup"))
    for name in required_helpers:
        if len(re.findall(r"^function " + re.escape(name) + r"\(", text, re.MULTILINE)) != 1:
            raise UnsafeStructure(f"status.php has an unsupported {name} helper structure")
    for name in ("dvsButtonsDmrSavedCardMode", "dvsButtonsDmrSavedNetwork", "dvsButtonsDmrCurrentMode", "dvsButtonsDmrSavedTalkgroup"):
        if len(re.findall(r"^function " + re.escape(name) + r"\(", text, re.MULTILINE)) > 1:
            raise UnsafeStructure(f"status.php has duplicate {name} helpers")

    marker = marker_matches[0]
    close_tag = text.find("?>", marker.end())
    if close_tag < 0:
        raise UnsafeStructure("status.php is missing the PHP close tag after Buttons helpers")
    helper_region = text[marker.start():close_tag]
    connecting_rows = text.count(BUTTONS_CONNECTING_OUTPUT)
    if marker_version >= 7:
        if connecting_rows != 1:
            raise UnsafeStructure("status.php is missing the supported DMR connecting row")
        text = text.replace(BUTTONS_CONNECTING_OUTPUT, NOT_CONNECTED_ROW, 1)
        if text.count(BUTTONS_CONNECTING_CONDITION) == 1:
            text = text.replace(BUTTONS_CONNECTING_CONDITION, LEGACY_CONNECTING_CONDITION, 1)
        elif text.count(LEGACY_CONNECTING_CONDITION) != 1:
            raise UnsafeStructure("status.php DMR connection-state condition is unsupported")
    elif connecting_rows > 0:
        raise UnsafeStructure("status.php has a connecting row without its matching marker version")
    function_pattern = re.compile(
        r"(?ms)^function (dvsButtonsDmr[A-Za-z0-9_]*)\([^\n]*\) \{\n.*?^\}\n?"
    )
    stripped_helpers, removed = function_pattern.subn("", helper_region)
    stripped_helpers = STATUS_MARKER.sub("", stripped_helpers, count=1)
    if removed < len(required_helpers) or re.search(r"\bdvsButtonsDmr[A-Za-z0-9_]*\s*\(", stripped_helpers):
        raise UnsafeStructure("status.php contains incomplete or unrecognized Buttons helper code; left unchanged")

    mods_helpers = (
        text.count("function dvsModsDmrMasterHeading(") == 1
        and text.count("function dvsModsDmrMasterDisplay(") == 1
    )
    heading_replacement = MODS_HEADING if mods_helpers else FACTORY_HEADING
    output_replacement = MODS_OUTPUT if mods_helpers else FACTORY_OUTPUT
    if text.count(BUTTONS_HEADING) != 1 or text.count(BUTTONS_OUTPUT) != 1:
        raise UnsafeStructure("status.php active DMR rows do not match the supported Buttons structure")

    result = text.replace(BUTTONS_HEADING, heading_replacement, 1)
    result = result.replace(BUTTONS_OUTPUT, output_replacement, 1)
    # Remove only the Buttons marker and helper functions. Keep adjacent
    # helpers owned by DVSwitch-Mods or local dashboard customizations intact.
    result = result[:marker.start()] + stripped_helpers + result[close_tag:]
    return result, result != text


def patch_bridge(text: str) -> tuple[str, bool]:
    marker_count = text.count(BRIDGE_MARKER)
    if marker_count == 0:
        return text, False
    if marker_count != 1:
        raise UnsafeStructure("dvswitch.sh target-persistence block is incomplete or ambiguous")
    if text.count(BRIDGE_BLOCK) == 1:
        return text.replace(BRIDGE_BLOCK, BRIDGE_ORIGINAL, 1), True
    if text.count(BRIDGE_BLOCK_TEST13) == 1:
        return text.replace(BRIDGE_BLOCK_TEST13, BRIDGE_ORIGINAL, 1), True
    if text.count(BRIDGE_BLOCK_OLD) == 1:
        return text.replace(BRIDGE_BLOCK_OLD, BRIDGE_ORIGINAL, 1), True
    raise UnsafeStructure("dvswitch.sh target-persistence block is incomplete or ambiguous")


def patch_index(text: str) -> tuple[str, bool]:
    markers = list(INDEX_MARKERS.finditer(text))
    if not markers:
        return text, False
    if len(markers) != 1:
        raise UnsafeStructure("index.php has duplicate Mode Buttons markers")
    start = markers[0].start()
    end = text.lower().find("</script>", start)
    if end < 0:
        raise UnsafeStructure("index.php is missing the Mode Buttons script end anchor")
    end += len("</script>")
    return text[:start] + text[end:], True


def read_target(path: Path) -> tuple[str, bytes, os.stat_result]:
    if path.is_symlink() or not path.is_file():
        raise UnsafeStructure(f"shared target is not a regular file: {path}")
    raw = path.read_bytes()
    crlf_count = raw.count(b"\r\n")
    bare_cr_count = raw.count(b"\r") - crlf_count
    bare_lf_count = raw.replace(b"\r\n", b"").count(b"\n")
    if bare_cr_count or (crlf_count and bare_lf_count):
        raise UnsafeStructure(f"mixed or unsupported line endings in {path}; file was left unchanged")
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    return raw.replace(b"\r\n", b"\n").decode("utf-8"), newline, path.stat()


def atomic_write(path: Path, text: str, newline: bytes, original_stat: os.stat_result) -> None:
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".buttons-uninstall.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(text.replace("\n", newline.decode()).encode("utf-8"))
        os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        os.chmod(temporary, stat.S_IMODE(original_stat.st_mode))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: embedded uninstall program STATUS.PHP DVSWITCH.SH INDEX.PHP")
    status_path, bridge_path, index_path = map(Path, sys.argv[1:])
    status_text, status_nl, status_stat = read_target(status_path)
    bridge_text, bridge_nl, bridge_stat = read_target(bridge_path)
    index_text, index_nl, index_stat = read_target(index_path)

    # Prepare and validate every output before replacing any target.
    status_result, status_changed = patch_status(status_text)
    bridge_result, bridge_changed = patch_bridge(bridge_text)
    index_result, index_changed = patch_index(index_text)
    if status_changed:
        atomic_write(status_path, status_result, status_nl, status_stat)
    if bridge_changed:
        atomic_write(bridge_path, bridge_result, bridge_nl, bridge_stat)
    if index_changed:
        atomic_write(index_path, index_result, index_nl, index_stat)
    print(
        "PASS: removed Buttons-owned shared-file edits; preserved all other content."
        if status_changed or bridge_changed or index_changed
        else "PASS: no recognized Buttons shared-file edits required removal."
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeError, UnsafeStructure) as error:
        raise SystemExit(f"ERROR: {error}; shared files were left unchanged")
PY_BUTTONS_UNINSTALL
  rm -f "$MODE_HELPER" "$DMR_HELPER" "$TARGET_HELPER" "$TUNE_HELPER" "$FAVORITES_HELPER" "$FAVORITES_JS" "$ENDPOINT" "$SUDOERS" "$DMR_HELPER".tmp.*
  python3 ./dvswitch-mode-layout-state restore "$LAYOUT_STATE"
  rm -rf "$PRESET_DIR" /var/lib/dvswitch-mode-buttons
  # Restore an older standalone helper when one was present before consolidation.
  [[ -z "$latest_dmr_helper" ]] || cp -a "$latest_dmr_helper" "$DMR_HELPER"
  php -l "$STATUS_TARGET" >/dev/null || die 'status.php validation failed after uninstall'
  systemctl restart apache2 || die 'Apache restart failed after uninstall'
  echo 'PASS: DVSwitch Mode Buttons removed; backups saved under /var/backups/dvswitch-mode-buttons.'
  echo 'PASS: Buttons-owned dashboard and bridge changes removed; other installed changes were preserved.'
}

if [[ ${1:-} == "--uninstall" ]]; then
  uninstall
  exit 0
fi

case ${1:-} in
  --check) mode="check" ;;
  --install) mode="install" ;;
  "")
    echo "DVSwitch Mode Buttons $VERSION"
    echo "1) Install / upgrade"
    echo "2) Uninstall"
    echo "3) Exit"
    read -r -p "Choose an option [1/2/3]: " choice
    case "$choice" in
      1) mode="install" ;;
      2) uninstall; exit 0 ;;
      3) echo "Exit."; exit 0 ;;
      *) die "invalid menu choice" ;;
    esac
    ;;
  *) die "usage: $0 [--check|--install|--uninstall]" ;;
esac

install_dashboard_components(){
  install -d -o root -g root -m 755 "$(dirname "$ENDPOINT")" /etc/sudoers.d
  install -o root -g root -m 755 ./dvswitch-mode-tune "$TUNE_HELPER"
  install -o root -g root -m 755 ./dvswitch-mode-favorites "$FAVORITES_HELPER"
  install -o root -g root -m 644 ./dvswitch-mode-favorites.js "$FAVORITES_JS"
  install -o root -g root -m 644 /dev/stdin "$ENDPOINT" <<'PHP'
<?php
declare(strict_types=1);
$allowed = array('BM', 'TGIF', 'STFU', 'YSF', 'P25', 'NXDN', 'DSTAR');
if (isset($_GET['favorites'])) {
    $mode = strtoupper(trim((string)$_GET['favorites']));
    if (!in_array($mode, $allowed, true)) { http_response_code(400); header('Content-Type: application/json'); echo json_encode(array('ok' => false, 'error' => 'Unsupported mode')); exit; }
    $saved = is_readable('/etc/dvswitch-mode-buttons/favorites.json') ? json_decode((string)file_get_contents('/etc/dvswitch-mode-buttons/favorites.json'), true) : array();
    $items = is_array($saved) && isset($saved[$mode]) && is_array($saved[$mode]) ? $saved[$mode] : array();
    header('Content-Type: application/json'); echo json_encode(array('ok' => true, 'mode' => $mode, 'favorites' => $items)); exit;
}
if (isset($_GET['targetNames'])) {
    $mode = strtoupper(trim((string)$_GET['targetNames']));
    if (!in_array($mode, $allowed, true)) { http_response_code(400); header('Content-Type: application/json'); echo json_encode(array('ok' => false, 'error' => 'Unsupported mode')); exit; }
    $names = array();
    if ($mode === 'BM' || $mode === 'TGIF') {
        $file = ($mode === 'TGIF') ? '/var/lib/mmdvm/TGList_TGIF.txt' : '/var/lib/mmdvm/TGList_BM.txt';
    } elseif ($mode === 'STFU') {
        $file = '/var/lib/mmdvm/TGList_BM.txt';
    } else {
        $file = '';
    }
    if ($file !== '' && is_readable($file)) {
        foreach (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: array() as $line) {
            if ($line === '' || $line[0] === '#') continue;
            $fields = explode(';', $line, 4);
            if (count($fields) !== 4 || trim($fields[1]) !== '0') continue;
            $target = trim($fields[0]);
            $name = preg_replace('/\s+/u', ' ', str_replace('_', ' ', trim($fields[2])));
            if (preg_match('/^[A-Za-z0-9_-]{1,32}$/', $target) && is_string($name) && $name !== '') $names[$target] = $name;
        }
    }
    if ($mode === 'YSF' && is_readable('/var/lib/mmdvm/YSFHosts.txt')) {
        foreach (file('/var/lib/mmdvm/YSFHosts.txt', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: array() as $line) {
            if ($line === '' || $line[0] === '#') continue;
            $fields = explode(';', $line);
            if (count($fields) < 2) continue;
            $target = trim($fields[0]);
            $name = preg_replace('/\s+/u', ' ', str_replace('_', ' ', trim($fields[1])));
            if (preg_match('/^[A-Za-z0-9_-]{1,32}$/', $target) && is_string($name) && $name !== '') $names[$target] = $name;
        }
    } elseif (($mode === 'P25' || $mode === 'NXDN') && is_readable('/var/lib/mmdvm/'.$mode.'Hosts.json')) {
        $database = json_decode((string)file_get_contents('/var/lib/mmdvm/'.$mode.'Hosts.json'), true);
        if (isset($database['reflectors']) && is_array($database['reflectors'])) {
            foreach ($database['reflectors'] as $row) {
                if (!is_array($row) || !isset($row['designator'])) continue;
                $target = trim((string)$row['designator']);
                $name = '';
                foreach (array('name', 'sponsor') as $field) {
                    if (!isset($row[$field]) || !is_string($row[$field])) continue;
                    $candidate = preg_replace('/\s+/u', ' ', str_replace('_', ' ', trim($row[$field])));
                    if (is_string($candidate) && $candidate !== '' && strcasecmp($candidate, 'Place holder') !== 0) { $name = $candidate; break; }
                }
                if (preg_match('/^[A-Za-z0-9_-]{1,32}$/', $target) && $name !== '') $names[$target] = $name;
            }
        }
    }
    header('Content-Type: application/json'); echo json_encode(array('ok' => true, 'mode' => $mode, 'names' => $names)); exit;
}
if ($_SERVER['REQUEST_METHOD'] === 'POST' && stripos((string)($_SERVER['CONTENT_TYPE'] ?? ''), 'application/json') === 0) {
    $payload = json_decode((string)file_get_contents('php://input'), true);
    if (!is_array($payload) || !isset($payload['mode'], $payload['favorites']) || !in_array($payload['mode'], $allowed, true) || !is_array($payload['favorites'])) {
        http_response_code(400); header('Content-Type: application/json'); echo json_encode(array('ok' => false, 'error' => 'Invalid favorites request.')); exit;
    }
    $pipes = array();
    $process = proc_open(array('/usr/bin/sudo', '/usr/local/sbin/dvswitch-mode-favorites'),
        array(0 => array('pipe', 'r'), 1 => array('pipe', 'w'), 2 => array('pipe', 'w')), $pipes);
    if (!is_resource($process)) { http_response_code(500); header('Content-Type: application/json'); echo json_encode(array('ok' => false, 'error' => 'Unable to start favorites save.')); exit; }
    fwrite($pipes[0], json_encode($payload)); fclose($pipes[0]);
    $output = stream_get_contents($pipes[1]); fclose($pipes[1]);
    $error = stream_get_contents($pipes[2]); fclose($pipes[2]);
    $status = proc_close($process);
    header('Content-Type: application/json');
    if ($status !== 0) http_response_code(400);
    echo json_encode(array('ok' => $status === 0, 'message' => trim((string)$output), 'error' => trim((string)$error))); exit;
}
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['target'])) {
    $target = trim((string)$_POST['target']);
    if (!preg_match('/^[A-Za-z0-9_-]{1,32}$/D', $target)) {
        http_response_code(400); header('Content-Type: application/json');
        echo json_encode(array('ok' => false, 'error' => 'Enter a valid talkgroup or reflector ID.')); exit;
    }
    $modeFile = '/var/lib/dvswitch-mode-buttons/current-mode';
    $mode = is_readable($modeFile) ? strtoupper(trim((string)file_get_contents($modeFile))) : '';
    $infoFiles = glob('/tmp/ABInfo_*.json');
    if (is_array($infoFiles) && count($infoFiles) > 0) {
        usort($infoFiles, static function ($a, $b) { return filemtime($b) <=> filemtime($a); });
        $liveInfo = json_decode((string)file_get_contents($infoFiles[0]), true);
        if (is_array($liveInfo)) foreach (array($liveInfo['tlv']['ambe_mode'] ?? '', $liveInfo['ambe_mode'] ?? '') as $liveValue) {
            $liveValue = strtoupper(trim((string)$liveValue));
            if ($liveValue === 'YSFN' || $liveValue === 'YSFW') $liveValue = 'YSF';
            if (in_array($liveValue, array('YSF', 'P25', 'NXDN', 'DSTAR'), true)) { $mode = $liveValue; break; }
        }
    }
    if (!in_array($mode, $allowed, true)) {
        http_response_code(409); header('Content-Type: application/json');
        echo json_encode(array('ok' => false, 'error' => 'Current mode is unavailable. Select a mode with the dashboard buttons first.')); exit;
    }
    $pipes = array();
    $process = proc_open(array('/usr/bin/sudo', '/usr/local/sbin/dvswitch-mode-tune'),
        array(0 => array('pipe', 'r'), 1 => array('pipe', 'w'), 2 => array('pipe', 'w')), $pipes);
    if (!is_resource($process)) {
        http_response_code(500); header('Content-Type: application/json');
        echo json_encode(array('ok' => false, 'error' => 'Unable to start tuning command.')); exit;
    }
    fwrite($pipes[0], $target . "\n"); fclose($pipes[0]);
    $output = stream_get_contents($pipes[1]); fclose($pipes[1]);
    $error = stream_get_contents($pipes[2]); fclose($pipes[2]);
    $status = proc_close($process);
    header('Content-Type: application/json');
    echo json_encode(array('ok' => $status === 0, 'mode' => $mode,
        'message' => trim((string)$output), 'error' => trim((string)$error), 'status' => $status)); exit;
}
if (isset($_GET['status'])) {
    $mode = '';
    $files = glob('/tmp/ABInfo_*.json');
    if (is_array($files) && count($files) > 0) {
        usort($files, static function ($a, $b) { return filemtime($b) <=> filemtime($a); });
        $data = json_decode((string)file_get_contents($files[0]), true);
        if (is_array($data)) foreach (array($data['tlv']['ambe_mode'] ?? '', $data['ambe_mode'] ?? '') as $value) {
            $value = strtoupper(trim((string)$value));
            if ($value === 'YSFN' || $value === 'YSFW') $value = 'YSF';
            if ($value !== '') { $mode = $value; break; }
        }
    }
    // STFU uses DMR internally. Keep the selected STFU button active instead
    // of mapping the generic DMR bridge mode back to the BM/TGIF network.
    $selectedModeFile = '/var/lib/dvswitch-mode-buttons/current-mode';
    $selectedMode = is_readable($selectedModeFile) ? strtoupper(trim((string)file_get_contents($selectedModeFile))) : '';
    if ($mode === 'DMR' && $selectedMode === 'STFU') { $mode = 'STFU'; }
    $address = '';
    $ini = '/opt/MMDVM_Bridge/MMDVM_Bridge.ini';
    if (is_readable($ini)) {
        $inNetwork = false;
        foreach (file($ini, FILE_IGNORE_NEW_LINES) ?: array() as $line) {
            if (trim($line) === '[DMR Network]') { $inNetwork = true; continue; }
            if ($inNetwork && preg_match('/^\s*\[/', $line)) break;
            if ($inNetwork && preg_match('/^\s*Address\s*=\s*(\S+)/i', $line, $match)) { $address = $match[1]; break; }
        }
    }
    $network = (stripos($address, 'tgif') !== false) ? 'TGIF' : ((stripos($address, 'brandmeister') !== false || stripos($address, 'repeater.net') !== false) ? 'BM' : '');
    header('Content-Type: application/json'); echo json_encode(array('ok' => $mode !== '', 'mode' => $mode, 'network' => $network)); exit;
}
$mode = strtoupper(trim((string)($_GET['mode'] ?? '')));
if (!in_array($mode, $allowed, true)) { http_response_code(400); header('Content-Type: application/json'); echo json_encode(array('ok' => false, 'error' => 'Unsupported mode')); exit; }
$output = array(); $status = 0;
exec('/usr/bin/sudo /usr/local/sbin/dvswitch-mode-buttons '.escapeshellarg($mode).' 2>&1', $output, $status);
header('Content-Type: application/json'); echo json_encode(array('ok' => $status === 0, 'mode' => $mode, 'output' => implode("\n", $output), 'status' => $status));
?>
PHP
  install -o root -g root -m 440 /dev/stdin "$SUDOERS" <<'SUDO'
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-buttons BM
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-buttons TGIF
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-buttons STFU
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-buttons YSF
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-buttons P25
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-buttons NXDN
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-buttons DSTAR
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-tune
www-data ALL=(root) NOPASSWD: /usr/local/sbin/dvswitch-mode-favorites
SUDO
  visudo -cf "$SUDOERS" >/dev/null || die 'sudoers validation failed'
  php -l "$ENDPOINT" >/dev/null || die 'endpoint PHP validation failed'
  python3 - "$TARGET" <<'PY'
import os, re, shutil, sys, tempfile
path=sys.argv[1]; text=open(path, encoding='utf-8').read()
marker='<!-- DVSwitch-Mode-Buttons 1.0.0-test48 -->'
owned_marker=re.compile(r'<!-- DVSwitch-Mode-Buttons 1\.0\.0-test(?:8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|32|33|34|35|36|37|38|39|40|41|42|43|44|45|46|47) -->')
owned_matches=list(owned_marker.finditer(text))
if len(owned_matches) > 1: raise SystemExit('ERROR: duplicate owned mode-button markers found')
if owned_matches:
    start=owned_matches[0].start()
    end=text.lower().find('</script>', start)
    if end < 0: raise SystemExit('ERROR: existing mode-button script end anchor not found')
    end += len('</script>')
    text=text[:start]+text[end:]
if marker not in text:
    block='''<!-- DVSwitch-Mode-Buttons 1.0.0-test48 -->
<div id="dvs-mode-buttons" aria-label="Select Mode"><div class="dvs-mode-buttons-title">Select Mode</div>
<button type="button" class="button link" data-mode="BM">BM</button><button type="button" class="button link" data-mode="TGIF">TGIF</button><button type="button" class="button link" data-mode="STFU">STFU</button><button type="button" class="button link" data-mode="YSF">YSF</button><button type="button" class="button link" data-mode="P25">P25</button><button type="button" class="button link" data-mode="NXDN">NXDN</button><button type="button" class="button link" data-mode="DSTAR">D-Star</button></div>
<section id="dvs-favorites" hidden aria-label="Mode favorites"><div class="dvs-favorites-control-line"><div class="dvs-favorites-heading">Favorites</div><label class="dvs-favorites-select-label" for="dvs-favorites-select" hidden>Favorite</label><select id="dvs-favorites-select" class="dvs-favorites-select" aria-label="Active mode favorite"><option value="">Select favorite</option></select><button type="button" class="button link dvs-favorites-edit">Edit</button>
<form id="dvs-target-tuner" aria-label="Tune talkgroup or reflector"><input id="dvs-target-input" name="target" type="text" inputmode="numeric" maxlength="32" autocomplete="off" placeholder="Enter TG / reflector ID" aria-label="Talkgroup or reflector ID"><button id="dvs-target-submit" type="submit" class="button link">Tune</button><button type="button" class="button link dvs-favorites-add-current" aria-label="Add tuned ID to favorites for the current mode">+ Favorite</button><span id="dvs-target-message" role="status" aria-live="polite"></span></form></div>
<div class="dvs-favorites-list-status" role="status" aria-live="polite"></div><dialog class="dvs-favorites-editor" aria-labelledby="dvs-favorites-editor-title"><div class="dvs-favorites-dialog-content"><h2 id="dvs-favorites-editor-title">Edit Favorites</h2><p class="dvs-favorites-help">Choose a mode, then edit the favorite name and talkgroup or reflector ID. Use <strong>Add Favorite</strong> for a new row or <strong>Delete</strong> to remove one. Select <strong>Save</strong> to keep your changes. <strong>Cancel or Esc</strong> closes this editor and discards unsaved changes. Changes apply only to the selected mode.</p><label class="dvs-favorites-mode-label">Mode <select class="dvs-favorites-mode"></select></label><div class="dvs-favorites-rows" aria-label="Favorite entries"></div><div class="dvs-favorites-dialog-actions"><button type="button" class="button link dvs-favorites-add">Add Favorite</button><button type="button" class="button link dvs-favorites-save">Save</button><button type="button" class="button link dvs-favorites-cancel">Cancel / Close</button></div><div class="dvs-favorites-status" role="status" aria-live="polite"></div></div></dialog></section>
<style>#dvs-mode-buttons{text-align:center;margin:4px auto 5px}#dvs-mode-buttons .dvs-mode-buttons-title{font-weight:bold;margin-bottom:2px}#dvs-mode-buttons button{min-width:72px;height:32px;padding:4px 10px}#dvs-mode-buttons button.selected{background-color:#008000}#dvs-mode-buttons button:disabled{opacity:.65}#dvs-favorites{text-align:center;margin:0 auto 8px;max-width:100%}#dvs-favorites .dvs-favorites-control-line{display:inline-flex;vertical-align:middle;align-items:center;justify-content:center;gap:8px;margin:0 0 8px;min-height:34px;white-space:nowrap}#dvs-favorites .dvs-favorites-heading{font-weight:bold;white-space:nowrap}#dvs-target-tuner{display:inline-flex;vertical-align:middle;align-items:center;justify-content:center;gap:6px;margin:0;min-height:34px;white-space:nowrap}#dvs-target-input{box-sizing:border-box;width:12ch;height:32px;padding:4px 8px}#dvs-target-submit,#dvs-favorites .dvs-favorites-add-current{min-width:64px;height:32px;padding:4px 10px}#dvs-target-message{min-width:0;font-size:12px;text-align:left}#dvs-target-message.error{color:#d9534f}#dvs-favorites-select{box-sizing:border-box;width:min(260px,25vw);height:32px;padding:4px 8px}#dvs-favorites .dvs-favorites-editor{box-sizing:border-box;width:min(720px,calc(100vw - 24px));max-width:none;max-height:88vh;margin:auto;padding:0;border:1px solid #8795a8;border-radius:8px;background:#111827;color:inherit;box-shadow:0 12px 40px #0009}#dvs-favorites .dvs-favorites-editor::backdrop{background:#0009}#dvs-favorites .dvs-favorites-dialog-content{display:flex;flex-direction:column;max-height:88vh;padding:18px}#dvs-favorites-editor-title{margin:0 0 8px;font-size:1.2em}#dvs-favorites .dvs-favorites-help{margin:0 auto 12px;max-width:620px;text-align:left;line-height:1.45;white-space:normal}#dvs-favorites .dvs-favorites-mode-label{margin-bottom:8px}#dvs-favorites .dvs-favorites-rows{overflow-y:auto;overscroll-behavior:contain;max-height:45vh;padding:2px}#dvs-favorites .dvs-favorites-dialog-actions{display:flex;flex-wrap:wrap;justify-content:center;gap:6px;margin-top:10px}#dvs-favorites .dvs-favorites-status{margin-top:8px}#dvs-favorites .dvs-favorites-list-status{font-size:12px;min-height:1em}.dvs-rx-monitor-inline{display:inline-flex;vertical-align:middle;align-items:center;justify-content:center;min-width:137px;height:34px;margin:0 8px 0 0;padding:4px 10px}.dvs-rx-monitor-inline img{vertical-align:middle}#dvs-favorites-mode{margin-left:5px;padding:4px}.dvs-favorite-edit-row{display:flex;gap:5px;justify-content:center;margin:4px}.dvs-favorite-edit-row input{box-sizing:border-box;width:min(220px,34vw);min-width:0;padding:4px}.dvs-favorites-status{font-size:12px;min-height:1em}@media(max-width:600px){#dvs-favorites .dvs-favorites-dialog-content{padding:12px}#dvs-favorites .dvs-favorites-rows{max-height:42vh}#dvs-favorites .dvs-favorites-control-line{gap:4px}#dvs-target-tuner{gap:4px}#dvs-favorites-select{width:22vw}#dvs-target-message{max-width:16vw;overflow-wrap:anywhere}.dvs-rx-monitor-inline{min-width:0;margin-right:4px;padding:4px}.dvs-favorite-edit-row input{width:38vw}.dvs-favorite-edit-row{gap:3px}}</style>
<script src="/dvswitch/dvswitch-mode-favorites.js"></script>'''
    rx_move_marker='// DVSwitch-Mods: RX Monitor left of status v1'
    if rx_move_marker in text:
        if text.count(rx_move_marker) != 1:
            raise SystemExit('ERROR: RX Monitor relocation marker is ambiguous')
        moved_rx=re.compile(r'// DVSwitch-Mods: RX Monitor left of status v1\s*\n\s*echo \'<div style="margin-top:8px;text-align:center;">\';\s*\n\s*if \( RXMONITOR == "YES" \)')
        if len(moved_rx.findall(text)) != 1:
            raise SystemExit('ERROR: RX Monitor relocation block is incomplete or unsupported')
        center=re.search(r'(<div class="content"><center>)(\s*)(</center>)', text, re.I)
        if not center or center.group(2).strip():
            raise SystemExit('ERROR: vacated centered RX Monitor area not found')
        insert_at=center.start(3)
        text=text[:insert_at]+block+'\n'+text[insert_at:]
    else:
        anchor=re.search(r'<div style="margin-top:8px;">', text, re.I)
        if not anchor: raise SystemExit('ERROR: RX Monitor anchor not found and Mods relocation was not detected')
        text=text[:anchor.start()]+block+'\n'+text[anchor.start():]
    st=os.stat(path); fd,tmp=tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd,'w',encoding='utf-8',newline='') as f: f.write(text)
    os.chown(tmp,st.st_uid,st.st_gid); os.chmod(tmp,st.st_mode & 0o7777); os.replace(tmp,path)
PY
  grep -qF '<!-- DVSwitch-Mode-Buttons 1.0.0-test48 -->' "$TARGET" || die 'dashboard controls block was not installed'
}

network="$(awk '
  /^\[DMR Network\]/{insec=1;next} /^\[/{insec=0}
  insec && /^[[:space:]]*Address[[:space:]]*=/{sub(/^[^=]*=/,""); gsub(/[[:space:]]/,""); print; exit}
' "$INI")"
case "$network" in
  *brandmeister*|*repeater.net|*3102*|*3104*) default_net=BM;;
  *tgif*) default_net=TGIF;;
  *) default_net=UNKNOWN;;
esac

getvar(){ awk -F= -v key="$1" '$1 == key {sub(/^[^=]*=/,""); sub(/\r$/,""); print; exit}' "$VAR"; }
password_state(){
  case "$1" in
    "") echo "missing";;
    passw0rd) echo "default password";;
    *) echo "configured";;
  esac
}

install_favorites_starter(){
  if [[ ! -e "$FAVORITES_FILE" && ! -L "$FAVORITES_FILE" ]]; then
    install -d -o root -g root -m 755 "$(dirname "$FAVORITES_FILE")"
    install -o root -g root -m 644 "$FAVORITES_STARTER" "$FAVORITES_FILE"
    echo "PASS: installed starter favorites at $FAVORITES_FILE."
  else
    echo "PASS: existing favorites preserved at $FAVORITES_FILE."
  fi
}

if [[ $mode == check ]]; then
  bash ./dvswitch-display-layout.sh check
  python3 - "$TARGET" <<'PY_BUTTONS_CHECK'
import re, sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
button_markers = list(re.finditer(r'<!-- DVSwitch-Mode-Buttons 1\.0\.0-test(?:8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|32|33|34|35|36|37|38|39|40|41|42|43|44|45|46|47) -->', text))
if len(button_markers) > 1:
    raise SystemExit('ERROR: duplicate Mode Buttons blocks found')
if button_markers:
    start = button_markers[0].start()
    end = text.lower().find('</script>', start)
    if end < 0:
        raise SystemExit('ERROR: existing Mode Buttons script end anchor not found')
    text = text[:start] + text[end + len('</script>'):]
rx_marker = '// DVSwitch-Mods: RX Monitor left of status v1'
if rx_marker in text:
    moved_rx = re.compile(r'// DVSwitch-Mods: RX Monitor left of status v1\s*\n\s*echo \'<div style="margin-top:8px;text-align:center;">\';\s*\n\s*if \( RXMONITOR == "YES" \)')
    center = re.search(r'(<div class="content"><center>)(\s*)(</center>)', text, re.I)
    if text.count(rx_marker) != 1 or len(moved_rx.findall(text)) != 1 or not center or center.group(2).strip():
        raise SystemExit('ERROR: relocated RX Monitor layout is incomplete or centered insertion area is occupied')
    print('PASS: relocated RX Monitor layout and vacated centered button area are supported.')
elif len(re.findall(r'<div style="margin-top:8px;">', text, re.I)) == 1:
    print('PASS: original RX Monitor button anchor is available.')
else:
    raise SystemExit('ERROR: supported RX Monitor button anchor or DVSwitch-Mods relocation was not found')
PY_BUTTONS_CHECK
  python3 - "$STATUS_TARGET" <<'PY_DMR_CARD_CHECK'
import re, sys
from pathlib import Path
path = Path(sys.argv[1])
if path.is_symlink() or not path.is_file():
    raise SystemExit('ERROR: status.php is missing or is not a regular file')
text = path.read_text(encoding='utf-8')
markers = re.findall(r'// DVSwitch-Mode-Buttons: standalone DMR Master display v([1-9])', text)
if len(markers) > 1:
    raise SystemExit('ERROR: duplicate standalone DMR Master markers found')
if "strpos($dmrstat, 'Opening') !== false" not in text:
    raise SystemExit('ERROR: supported DMR Opening status check not found')
for event in ('Closing', 'Connection'):
    old = "strpos($dmrstatus, '%s')" % event
    fixed = "strpos($dmrstat, '%s')" % event
    if text.count(old) + text.count(fixed) != 1:
        raise SystemExit('ERROR: unsupported or ambiguous DMR %s status check' % event)
if markers and int(markers[0]) >= 7:
    connecting_row = r'''echo "<tr><td  style=\"background: #ffffed;\" colspan=\"2\"><span style=\"color:#b5651d;font-weight: bold;white-space:normal;word-break:normal;overflow-wrap:anywhere;text-align:center;\">".dvsButtonsDmrMasterDisplay($dmrMasterHost, $abinfo, true)."</span></td></tr>\n";'''
    if text.count('dvsButtonsDmrMasterDisplay($dmrMasterHost, $abinfo, true)') != 1 or text.count('dvs-dmr-connection-state') < 1 or text.count(connecting_row) != 1:
        raise SystemExit('ERROR: state-aware DMR connecting card structure is incomplete')
else:
    not_connected_row = r'''echo "<tr><td  style=\"background: #ffffed;\" colspan=\"2\"><span style=\"color:#b0b0b0;font-weight: bold\">Not Connected</span></td></tr>\n";'''
    if text.count(not_connected_row) != 1:
        raise SystemExit('ERROR: expected one supported DMR Not Connected row')
print('PASS: DMR card can be upgraded safely; connection-state handling is supported.')
PY_DMR_CARD_CHECK
  echo "DVSwitch Mode Buttons $VERSION"
  echo "MMDVM_Bridge.ini: $INI"
  echo "Current DMR network: $default_net ($network)"
  [[ -f "$VAR" ]] && echo "DVSwitch var.txt: found" || echo "DVSwitch var.txt: not found"
  echo "Preset directory: $PRESET_DIR"
  if [[ -f "$VAR" ]]; then
    echo "BM password status: $(password_state "$(getvar bm_password)")"
    echo "TGIF password status: $(password_state "$(getvar tgif_password)")"
    echo "BM address: $(getvar bm_address)"
    echo "TGIF address: $(getvar tgif_address)"
  fi
  echo "PASS: installer prerequisites checked; no files changed."
  exit 0
fi

if [[ -e "$MODE_HELPER" || -e "$TARGET_HELPER" || -e "$FAVORITES_HELPER" || -e "$ENDPOINT" || -e "$SUDOERS" ]] || grep -Eq '<!-- DVSwitch-Mode-Buttons 1\.0\.0-test(8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|32|33|34|35|36|37|38|39|40|41|42|43|44) -->' "$TARGET"; then
  echo "Existing installation detected; applying the current upgrade."
else
  echo "No existing installation detected; starting installation."
fi

[[ -f "$VAR" ]] || die "missing $VAR"
[[ -f "$ANALOG_INI" ]] || die "missing $ANALOG_INI"
install -d -m 700 -o root -g root "$PRESET_DIR"
for preset in MMDVM_Bridge.BM.ini MMDVM_Bridge.TGIF.ini Analog_Bridge.BM.ini Analog_Bridge.TGIF.ini; do
  if [[ -f "$LEGACY_PRESET_DIR/$preset" && ! -f "$PRESET_DIR/$preset" ]]; then
    cp -p "$LEGACY_PRESET_DIR/$preset" "$PRESET_DIR/$preset"
  fi
done

bm_address="$(getvar bm_address)"; bm_port="$(getvar bm_port)"; bm_password="$(getvar bm_password)"
tgif_address="$(getvar tgif_address)"; tgif_port="$(getvar tgif_port)"; tgif_password="$(getvar tgif_password)"
[[ $default_net == BM || $default_net == TGIF ]] || die "current DMR address is not recognized as BM or TGIF"
cp -p "$INI" "$PRESET_DIR/MMDVM_Bridge.$default_net.ini"
alternate_net=TGIF; [[ $default_net == TGIF ]] && alternate_net=BM
current_tg="$(sed -nE '/^\[AMBE_AUDIO\][[:space:]]*$/,/^\[/ s/^[[:space:]]*txTg[[:space:]]*=[[:space:]]*([^;#[:space:]]+).*$/\1/ip' "$ANALOG_INI")"
[[ -n "$current_tg" ]] || die "current Analog_Bridge txTg is empty"
read -r -p "$alternate_net Analog_Bridge txTg for boot: " alternate_tg
[[ "$alternate_tg" =~ ^[0-9]+$ ]] || die 'Analog_Bridge txTg must be numeric'
if [[ $alternate_net == BM ]]; then
  [[ -n "$bm_address" ]] || read -r -p "BrandMeister address: " bm_address
  [[ -n "$bm_port" ]] || read -r -p "BrandMeister port: " bm_port
  if [[ -z "$bm_password" || "$bm_password" == "passw0rd" ]]; then
    read -r -s -p "BrandMeister password: " bm_password; echo
    [[ -n "$bm_password" && "$bm_password" != "passw0rd" ]] || die "BM password is blank or still the DVSwitch default; BM preset was not created."
  fi
else
  [[ -n "$tgif_address" ]] || read -r -p "TGIF address: " tgif_address
  [[ -n "$tgif_port" ]] || read -r -p "TGIF port: " tgif_port
  if [[ -z "$tgif_password" || "$tgif_password" == "passw0rd" ]]; then
    read -r -s -p "TGIF password: " tgif_password; echo
    [[ -n "$tgif_password" && "$tgif_password" != "passw0rd" ]] || die "TGIF password is blank or still the DVSwitch default; TGIF preset was not created."
  fi
fi

[[ -n "$bm_address" && -n "$bm_port" && -n "$bm_password" && "$bm_password" != "passw0rd" ]] && bm_ok=1 || bm_ok=0
[[ -n "$tgif_address" && -n "$tgif_port" && -n "$tgif_password" && "$tgif_password" != "passw0rd" ]] && tgif_ok=1 || tgif_ok=0
[[ $alternate_net == BM && $bm_ok == 1 ]] || [[ $alternate_net != BM ]] || die "required BM data is missing or its default password remains configured; no preset was installed."
[[ $alternate_net == TGIF && $tgif_ok == 1 ]] || [[ $alternate_net != TGIF ]] || die "required TGIF data is missing or its default password remains configured; no preset was installed."

export INI ANALOG_INI PRESET_DIR default_net alternate_net current_tg alternate_tg bm_address bm_port bm_password tgif_address tgif_port tgif_password bm_ok tgif_ok
python3 - <<'PY'
import os, re, shutil, tempfile
ini=os.environ['INI']; analog=os.environ['ANALOG_INI']; outdir=os.environ['PRESET_DIR']
text=open(ini, encoding='utf-8').read()
if not re.search(r'(?m)^\[DMR Network\]\s*$', text): raise SystemExit('missing [DMR Network] section')
def make(name, address, port, password):
    lines=text.splitlines(True); start=next(i for i,x in enumerate(lines) if re.match(r'^\[DMR Network\]\s*$',x)); end=next((i for i in range(start+1,len(lines)) if re.match(r'^\[.*\]\s*$',lines[i])),len(lines))
    replacement={'address':address,'port':port,'password':password}
    for i in range(start+1,end):
        m=re.match(r'^(Address|Port|Password)([ \t]*=[ \t]*)[^\r\n]*(\r?\n)?$',lines[i],re.I)
        if m:
            key=m.group(1).lower(); lines[i]=m.group(1)+m.group(2)+replacement[key]+(m.group(3) or '')
    data=''.join(lines)
    fd,tmp=tempfile.mkstemp(dir=outdir); os.close(fd); open(tmp,'w',encoding='utf-8',newline='').write(data); shutil.copystat(ini,tmp); os.chown(tmp,os.stat(ini).st_uid,os.stat(ini).st_gid); os.chmod(tmp,os.stat(ini).st_mode & 0o7777); os.replace(tmp,os.path.join(outdir,'MMDVM_Bridge.'+name+'.ini'))
if os.environ['alternate_net']=='BM' and os.environ['bm_ok']=='1': make('BM',os.environ['bm_address'],os.environ['bm_port'],os.environ['bm_password'])
if os.environ['alternate_net']=='TGIF' and os.environ['tgif_ok']=='1': make('TGIF',os.environ['tgif_address'],os.environ['tgif_port'],os.environ['tgif_password'])

analog_text=open(analog, encoding='utf-8', newline='').read()
section=re.search(r'(?ms)^\[AMBE_AUDIO\]\s*\n(.*?)(?=^\[|\Z)', analog_text)
line=re.compile(r'^(\s*txTg\s*=\s*)([^;#\r\n]+)(.*)$', re.I|re.M)
if not section or len(line.findall(section.group(1))) != 1: raise SystemExit('expected exactly one txTg in [AMBE_AUDIO]')
def analog_preset(name, value):
    def replace_tx_tg(match):
        prefix=match.group(1)
        suffix=match.group(3)
        padding=max(1, 40-len(prefix)-len(value))
        return prefix+value+(' '*padding)+suffix
    body=line.sub(replace_tx_tg, section.group(1), count=1)
    data=analog_text[:section.start(1)]+body+analog_text[section.end(1):]
    fd,tmp=tempfile.mkstemp(dir=outdir); os.close(fd)
    with open(tmp,'w',encoding='utf-8',newline='') as f: f.write(data)
    shutil.copystat(analog,tmp); st=os.stat(analog); os.chown(tmp,st.st_uid,st.st_gid); os.replace(tmp,os.path.join(outdir,'Analog_Bridge.'+name+'.ini'))
analog_preset(os.environ['default_net'], os.environ['current_tg'])
analog_preset(os.environ['alternate_net'], os.environ['alternate_tg'])
PY
chmod 700 "$PRESET_DIR"; chown -R root:root "$PRESET_DIR"
echo "PASS: created available BM/TGIF presets in $PRESET_DIR."

python3 ./dvswitch-mode-layout-state capture "$LAYOUT_STATE"
bash ./dvswitch-display-layout.sh apply
install_dashboard_components

./install-mode-target-persistence.sh
./install-standalone-dmr-master-card.sh
saved_dmr_card_mode=''
[[ -r /var/lib/dvswitch-mode-buttons/last-dmr-card-mode ]] && saved_dmr_card_mode=$(tr -d '[:space:]' < /var/lib/dvswitch-mode-buttons/last-dmr-card-mode)
saved_dmr_network=''
[[ -r /var/lib/dvswitch-mode-buttons/last-dmr-network ]] && saved_dmr_network=$(tr -d '[:space:]' < /var/lib/dvswitch-mode-buttons/last-dmr-network)
repair_saved_dmr_card_mode=0
case "$saved_dmr_card_mode" in
  BM|TGIF) ;;
  *)
    case "$saved_dmr_network" in
      BM|TGIF) saved_dmr_card_mode=$saved_dmr_network; repair_saved_dmr_card_mode=1 ;;
    esac
    ;;
esac
saved_dmr_target=''
existing_dmr_target=''
if [[ -r /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup ]]; then
  existing_dmr_target=$(tr -d '[:space:]' < /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup)
  [[ "$existing_dmr_target" =~ ^[0-9]+$ && "$existing_dmr_target" != 0 ]] && saved_dmr_target=$existing_dmr_target
fi
if [[ -z "$saved_dmr_target" ]]; then
  case "$saved_dmr_card_mode" in
    BM|TGIF) saved_dmr_target=$(/usr/local/sbin/dvswitch-mode-targets get "$saved_dmr_card_mode");;
    *) saved_dmr_target='';;
  esac
fi
# Earlier releases also copied STFU's active target into the DMR-only saved
# card field. If that exact mismatch is present, recover the DMR value from
# its own per-mode target while preserving valid saved values in other cases.
repair_saved_dmr_target=0
current_selected_mode=''
[[ -r /var/lib/dvswitch-mode-buttons/current-mode ]] && current_selected_mode=$(tr -d '[:space:]' < /var/lib/dvswitch-mode-buttons/current-mode)
case "$current_selected_mode" in
  BM|TGIF|DMR|'') ;;
  *)
    case "$saved_dmr_card_mode" in
      BM|TGIF)
        current_mode_target=$(/usr/local/sbin/dvswitch-mode-targets get "$current_selected_mode" 2>/dev/null || true)
        saved_mode_target=$(/usr/local/sbin/dvswitch-mode-targets get "$saved_dmr_card_mode" 2>/dev/null || true)
        if [[ "$existing_dmr_target" =~ ^[0-9]+$ && "$current_mode_target" =~ ^[0-9]+$ && "$saved_mode_target" =~ ^[0-9]+$ && "$existing_dmr_target" == "$current_mode_target" && "$existing_dmr_target" != "$saved_mode_target" ]]; then
          saved_dmr_target=$saved_mode_target
          repair_saved_dmr_target=1
        fi
        ;;
    esac
    ;;
esac
if [[ ! -e /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup ]]; then
  install -o root -g www-data -m 664 /dev/stdin /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup <<<"$saved_dmr_target"
fi
python3 - <<'PY'
from pathlib import Path
import os, re, tempfile

path = Path('/usr/share/dvswitch/include/status.php')
text = path.read_text(encoding='utf-8')
markers = re.findall(r'// DVSwitch-Mode-Buttons: standalone DMR Master display v[1-9]', text)
if len(markers) != 1:
    raise SystemExit('ERROR: expected one supported standalone DMR Master marker')
text = re.sub(r'// DVSwitch-Mode-Buttons: standalone DMR Master display v[1-9]', '// DVSwitch-Mode-Buttons: standalone DMR Master display v9', text, count=1)
saved = r'''function dvsButtonsDmrSavedCardMode() {
        $file = '/var/lib/dvswitch-mode-buttons/last-dmr-card-mode';
        if (!is_readable($file)) { return ''; }
        $mode = strtoupper(trim((string)file_get_contents($file)));
        return in_array($mode, array('BM', 'TGIF'), true) ? $mode : '';
}

function dvsButtonsDmrSavedNetwork() {
        $file = '/var/lib/dvswitch-mode-buttons/last-dmr-network';
        if (!is_readable($file)) { return ''; }
        $network = strtoupper(trim((string)file_get_contents($file)));
        return in_array($network, array('BM', 'TGIF'), true) ? $network : '';
}

'''
anchor='function dvsButtonsDmrName('
if 'function dvsButtonsDmrSavedCardMode(' not in text:
    text=text.replace(anchor, saved+anchor, 1)
new_current_mode_function = r'''function dvsButtonsDmrCurrentMode($abinfo, $selectedModeFile = null) {
        $mode = isset($abinfo['tlv']['ambe_mode']) ? strtoupper(trim((string)$abinfo['tlv']['ambe_mode'])) : '';
        if ($mode === 'YSFN' || $mode === 'YSFW') { $mode = 'YSF'; }
        // STFU is DMR-based internally, so its selected button mode must take
        // precedence over Analog_Bridge's generic DMR ambe_mode value.
        if (in_array($mode, array('STFU', 'YSF', 'P25', 'NXDN', 'DSTAR'), true)) { return $mode; }
        if ($selectedModeFile === null) { $selectedModeFile = '/var/lib/dvswitch-mode-buttons/current-mode'; }
        $selectedMode = is_readable($selectedModeFile) ? strtoupper(trim((string)file_get_contents($selectedModeFile))) : '';
        if ($mode === 'DMR') {
                if (in_array($selectedMode, array('BM', 'TGIF', 'STFU'), true)) { return $selectedMode; }
                return 'DMR';
        }
        return in_array($selectedMode, array('BM', 'TGIF', 'STFU', 'YSF', 'P25', 'NXDN', 'DSTAR'), true) ? $selectedMode : $mode;
}'''
current_mode_pattern = re.compile(r'(?ms)^function dvsButtonsDmrCurrentMode\([^\n]*\) \{\n.*?^\}')
current_mode_matches = list(current_mode_pattern.finditer(text))
if len(current_mode_matches) > 1:
    raise SystemExit('ERROR: duplicate DMR current-mode helpers found')
if current_mode_matches:
    text = text[:current_mode_matches[0].start()] + new_current_mode_function + text[current_mode_matches[0].end():]
else:
    anchor = 'function dvsButtonsDmrName('
    if text.count(anchor) != 1: raise SystemExit('ERROR: DMR name helper anchor is ambiguous during current-mode upgrade')
    text = text.replace(anchor, new_current_mode_function+'\n\n'+anchor, 1)
saved_talkgroup_function = r'''function dvsButtonsDmrSavedTalkgroup() {
        $file = '/var/lib/dvswitch-mode-buttons/last-dmr-talkgroup';
        if (!is_readable($file)) { return ''; }
        $value = trim((string)file_get_contents($file));
        if (preg_match('/^(?:TG\s*)?([0-9]+)$/i', $value, $match) && $match[1] !== '0') { return $match[1]; }
        return '';
}'''
saved_talkgroup_matches = list(re.finditer(r'(?ms)^function dvsButtonsDmrSavedTalkgroup\([^\n]*\) \{\n.*?^\}', text))
if len(saved_talkgroup_matches) > 1:
    raise SystemExit('ERROR: duplicate saved DMR talkgroup helpers found')
if saved_talkgroup_matches:
    text = text[:saved_talkgroup_matches[0].start()] + saved_talkgroup_function + text[saved_talkgroup_matches[0].end():]
else:
    anchor = 'function dvsButtonsDmrName('
    if text.count(anchor) != 1: raise SystemExit('ERROR: DMR name helper anchor is ambiguous during saved talkgroup upgrade')
    text = text.replace(anchor, saved_talkgroup_function+'\n\n'+anchor, 1)
pending_target_function = r'''function dvsButtonsDmrPendingTarget() {
        $pendingFile = '/var/lib/dvswitch-mode-buttons/dmr-tune-pending';
        if (!is_readable($pendingFile)) { return ''; }
        $parts = preg_split('/\s+/', trim((string)file_get_contents($pendingFile)));
        if (count($parts) !== 3 || !in_array(strtoupper($parts[0]), array('BM', 'TGIF'), true)) { return ''; }
        if (!preg_match('/^[0-9]+$/', $parts[1]) || !preg_match('/^[0-9]+$/', $parts[2])) { return ''; }
        $age = time() - (int)$parts[2];
        return ($age >= 0 && $age <= 12) ? $parts[1] : '';
}'''
pending_target_matches = list(re.finditer(r'(?ms)^function dvsButtonsDmrPendingTarget\([^\n]*\) \{\n.*?^\}', text))
if len(pending_target_matches) > 1:
    raise SystemExit('ERROR: duplicate pending DMR target helpers found')
if pending_target_matches:
    text = text[:pending_target_matches[0].start()] + pending_target_function + text[pending_target_matches[0].end():]
else:
    saved_anchor = 'function dvsButtonsDmrSavedTalkgroup() {'
    if text.count(saved_anchor) != 1: raise SystemExit('ERROR: saved DMR talkgroup helper anchor is ambiguous during pending-target upgrade')
    text = text.replace(saved_anchor, pending_target_function+'\n\n'+saved_anchor, 1)
remember_helper = r'''function dvsButtonsDmrRememberTalkgroup($talkgroup) {
        $file = '/var/lib/dvswitch-mode-buttons/last-dmr-talkgroup';
        $talkgroup = trim((string)$talkgroup);
        if (!preg_match('/^[0-9]+$/', $talkgroup) || $talkgroup === '0' || !is_file($file) || is_link($file) || !is_writable($file)) { return; }
        $saved = is_readable($file) ? trim((string)file_get_contents($file)) : '';
        if ($saved !== $talkgroup) { file_put_contents($file, $talkgroup."\n", LOCK_EX); }
}

'''
if 'function dvsButtonsDmrRememberTalkgroup(' not in text:
    saved_anchor = 'function dvsButtonsDmrSavedTalkgroup('
    if text.count(saved_anchor) != 1: raise SystemExit('ERROR: saved DMR talkgroup helper anchor is ambiguous')
    text=text.replace(saved_anchor, remember_helper+saved_anchor, 1)
new_heading_function = r'''function dvsButtonsDmrMasterHeading($master, $abinfo) {
        $liveMode = isset($abinfo['tlv']['ambe_mode']) ? strtoupper(trim((string)$abinfo['tlv']['ambe_mode'])) : '';
        if ($liveMode === 'DMR') { return 'DMR '.dvsButtonsDmrNetwork($master).' Master'; }
        $saved = dvsButtonsDmrSavedCardMode();
        if ($saved === 'BM' || $saved === 'TGIF') { return 'DMR '.$saved.' Master'; }
        return 'DMR '.dvsButtonsDmrNetwork($master).' Master';
}'''
heading_pattern = re.compile(r'(?ms)^function dvsButtonsDmrMasterHeading\([^\n]*\) \{\n.*?^\}')
heading_matches = list(heading_pattern.finditer(text))
if len(heading_matches) != 1 or 'dvsButtonsDmrNetwork' not in heading_matches[0].group(0):
    raise SystemExit(f'ERROR: expected one supported DMR Master heading function; found {len(heading_matches)}')
text = text[:heading_matches[0].start()] + new_heading_function + text[heading_matches[0].end():]
new_display_function = r'''function dvsButtonsDmrMasterDisplay($master, $abinfo, $connecting = false) {
        $liveMode = dvsButtonsDmrCurrentMode($abinfo);
        if ($liveMode === 'DMR') {
                $network = $connecting ? dvsButtonsDmrSavedNetwork() : '';
                if ($network !== 'BM' && $network !== 'TGIF') { $network = dvsButtonsDmrNetwork($master); }
        } elseif ($liveMode === 'BM' || $liveMode === 'TGIF') {
                $network = $liveMode;
        } else {
                $network = dvsButtonsDmrSavedNetwork();
                if ($network === '') { $network = dvsButtonsDmrNetwork($master); }
        }
        $isDmrMode = in_array($liveMode, array('DMR', 'BM', 'TGIF'), true);
        $observedTalkgroup = $isDmrMode ? dvsButtonsDmrTalkgroup($abinfo) : '';
        $pendingTarget = dvsButtonsDmrPendingTarget();
        $talkgroup = ($pendingTarget !== '') ? $pendingTarget : ($isDmrMode ? $observedTalkgroup : dvsButtonsDmrSavedTalkgroup());
        $numberLine = '';
        if ($connecting && $talkgroup === '') { $talkgroup = dvsButtonsDmrSavedTalkgroup(); }
        if (!$connecting && $isDmrMode && $talkgroup !== '' && ($pendingTarget === '' || $observedTalkgroup === $pendingTarget)) { dvsButtonsDmrRememberTalkgroup($talkgroup); }
        if ($talkgroup === '') {
                $display = (string)$master;
        } else {
                $name = dvsButtonsDmrName($network, $talkgroup);
                $display = ($name !== '') ? $name : 'TG '.$talkgroup;
                if ($name !== '') { $numberLine = '<br/><span style="color:#b5651d;font-weight:bold;">(TG '.htmlspecialchars($talkgroup, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8').')</span>'; }
        }
        return '<span class="dvs-dmr-room-label" style="color:#000000;font-weight:normal;">Room</span><br/><span style="color:#b5651d;font-weight:bold;">'.htmlspecialchars($display, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8').'</span>'.$numberLine.($connecting ? '<br/><span class="dvs-dmr-connection-state" style="color:#b0b0b0;font-weight:normal;">Connecting</span>' : '');
}'''
function_pattern = re.compile(r'(?ms)^function dvsButtonsDmrMasterDisplay\([^\n]*\) \{\n.*?^\}')
function_matches = list(function_pattern.finditer(text))
if len(function_matches) != 1:
    raise SystemExit(f'ERROR: expected exactly one DMR Master display function; found {len(function_matches)}')
existing_display_function = function_matches[0].group(0)
if 'dvsButtonsDmrTalkgroup' not in existing_display_function or 'dvsButtonsDmrNetwork' not in existing_display_function or 'dvsButtonsDmrName' not in existing_display_function:
    raise SystemExit('ERROR: DMR Master display function has an unsupported structure')
text = text[:function_matches[0].start()] + new_display_function + text[function_matches[0].end():]
legacy_conditions = ("strpos($dmrstatus, 'Closing')", "strpos($dmrstatus, 'Connection')")
for legacy in legacy_conditions:
    count = text.count(legacy)
    if count > 1: raise SystemExit('ERROR: DMR connection-state condition is ambiguous')
    if count == 1: text = text.replace(legacy, legacy.replace('$dmrstatus', '$dmrstat'), 1)
if text.count("strpos($dmrstat, 'Opening') !== false || strpos($dmrstat, 'Closing') !== false || strpos($dmrstat, 'Connection') !== false") != 1:
    raise SystemExit('ERROR: supported DMR connection-state condition was not found')
not_connected_row = r'''echo "<tr><td  style=\"background: #ffffed;\" colspan=\"2\"><span style=\"color:#b0b0b0;font-weight: bold\">Not Connected</span></td></tr>\n";'''
connecting_row = r'''echo "<tr><td  style=\"background: #ffffed;\" colspan=\"2\"><span style=\"color:#b5651d;font-weight: bold;white-space:normal;word-break:normal;overflow-wrap:anywhere;text-align:center;\">".dvsButtonsDmrMasterDisplay($dmrMasterHost, $abinfo, true)."</span></td></tr>\n";'''
if text.count(not_connected_row) == 1:
    text = text.replace(not_connected_row, connecting_row, 1)
elif text.count(connecting_row) != 1:
    raise SystemExit('ERROR: DMR Not Connected row is unsupported or ambiguous')

if 'standalone DMR Master display v9' not in text or 'dvsButtonsDmrSavedCardMode' not in text or 'dvsButtonsDmrSavedTalkgroup' not in text or 'dvsButtonsDmrRememberTalkgroup' not in text or 'dvsButtonsDmrPendingTarget' not in text or 'dvs-dmr-connection-state' not in text or 'selectedModeFile' not in text:
    raise SystemExit('ERROR: state-aware DMR card upgrade was not applied')
if "return 'DMR STFU Master';" in text or "$isDmrMode = in_array($liveMode, array('DMR', 'BM', 'TGIF', 'STFU'), true);" in text:
    raise SystemExit('ERROR: STFU is still included in the DMR Master card')
stat=path.stat(); fd,tmp=tempfile.mkstemp(dir=path.parent)
with os.fdopen(fd,'w',encoding='utf-8',newline='') as f: f.write(text)
os.chown(tmp,stat.st_uid,stat.st_gid); os.chmod(tmp,stat.st_mode & 0o7777); os.replace(tmp,path)
PY
php -l "$STATUS_TARGET" >/dev/null || die 'state-aware DMR card upgrade failed'
install -d /var/lib/dvswitch-mode-buttons
chown root:root /var/lib/dvswitch-mode-buttons
chmod 755 /var/lib/dvswitch-mode-buttons
for state_file in current-mode last-dmr-card-mode last-dmr-network; do
  if [[ -e "/var/lib/dvswitch-mode-buttons/$state_file" ]]; then
    chown root:root "/var/lib/dvswitch-mode-buttons/$state_file"
    chmod 644 "/var/lib/dvswitch-mode-buttons/$state_file"
  fi
done
if [[ -e /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup ]]; then
  [[ ! -L /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup ]] || die 'unsafe DMR talkgroup state symlink'
  chown root:www-data /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup
  chmod 664 /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup
else
  install -o root -g www-data -m 664 /dev/stdin /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup <<<"$saved_dmr_target"
fi
if ((repair_saved_dmr_target)); then
  saved_target_tmp=$(mktemp /var/lib/dvswitch-mode-buttons/.last-dmr-talkgroup.XXXXXX)
  printf '%s\n' "$saved_dmr_target" > "$saved_target_tmp"
  chown root:www-data "$saved_target_tmp"
  chmod 664 "$saved_target_tmp"
  mv -f "$saved_target_tmp" /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup
  echo "PASS: restored saved DMR card target to $saved_dmr_target from the $saved_dmr_card_mode target; STFU target remains mode-specific."
fi
if ((repair_saved_dmr_card_mode)); then
  saved_mode_tmp=$(mktemp /var/lib/dvswitch-mode-buttons/.last-dmr-card-mode.XXXXXX)
  printf '%s\n' "$saved_dmr_card_mode" > "$saved_mode_tmp"
  chown root:root "$saved_mode_tmp"
  chmod 644 "$saved_mode_tmp"
  mv -f "$saved_mode_tmp" /var/lib/dvswitch-mode-buttons/last-dmr-card-mode
  echo "PASS: restored saved BM/TGIF DMR card mode to $saved_dmr_card_mode."
fi
php -l "$STATUS_TARGET"
install_favorites_starter
systemctl restart apache2
echo "PASS: mode helpers, target persistence, standalone DMR card, and permissions installed."
echo '!!!!!!!!   NOTICE !!!!!!!!'
echo 'NOTICE: If the DVSwitch dashboard was already open, refresh that browser tab (press F5) to display the new buttons.'
