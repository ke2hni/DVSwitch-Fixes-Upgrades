#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=/opt/MMDVM_Bridge
SCRIPT=$ROOT/dvswitch.sh
MODE_HELPER=/usr/local/sbin/dvswitch-mode-buttons
DMR_HELPER=/usr/local/sbin/dvswitch-dmr-network
TARGET_HELPER=/usr/local/sbin/dvswitch-mode-targets
STATE_DIR=/var/lib/dvswitch-mode-buttons
BACKUP_DIR=/var/backups/dvswitch-mode-buttons
MARKER='# DVSwitch-Mode-Buttons: per-mode target persistence v1'

die(){ echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die 'run with sudo'
[[ -f $SCRIPT ]] || die "missing $SCRIPT"
[[ -f dvswitch-mode-targets ]] || die 'run from the repository directory'
[[ -f dvswitch-mode-buttons ]] || die 'missing repository dvswitch-mode-buttons'

install -d "$STATE_DIR"
chown root:root "$STATE_DIR"
chmod 755 "$STATE_DIR"
install -d -m 700 -o root -g root "$BACKUP_DIR"
stamp=$(date +%Y%m%d-%H%M%S)
if ! grep -qF 'ABINFO_MODE_PY' "$SCRIPT"; then
  cp -a "$SCRIPT" "$BACKUP_DIR/dvswitch.sh.$stamp"
fi
cp -a "$MODE_HELPER" "$BACKUP_DIR/dvswitch-mode-buttons.$stamp" 2>/dev/null || true
cp -a "$DMR_HELPER" "$BACKUP_DIR/dvswitch-dmr-network.$stamp" 2>/dev/null || true
install -o root -g root -m 755 dvswitch-mode-targets "$TARGET_HELPER"
install -o root -g root -m 755 dvswitch-mode-buttons "$MODE_HELPER"
# Publish the retained STFU target for the independent dashboard card. The
# canonical per-mode JSON remains root-only; this one value is read-only to PHP.
saved_stfu_target=$("$TARGET_HELPER" get STFU)
[[ "$saved_stfu_target" =~ ^[A-Za-z0-9_-]{1,32}$ ]] || saved_stfu_target=''
stfu_tmp=$(mktemp "$STATE_DIR/.stfu-target.XXXXXX")
printf '%s\n' "$saved_stfu_target" > "$stfu_tmp"
chown root:root "$stfu_tmp"
chmod 644 "$stfu_tmp"
mv -f "$stfu_tmp" "$STATE_DIR/stfu-target"
# Keep the historical command path as a compatibility symlink to the unified mode helper.
link_tmp="${DMR_HELPER}.tmp.$$"
rm -f "$link_tmp"
ln -s "$MODE_HELPER" "$link_tmp"
mv -Tf "$link_tmp" "$DMR_HELPER"

python3 - "$SCRIPT" "$MARKER" <<'PY'
import os, sys, tempfile

path, marker = sys.argv[1:]
with open(path, 'rb') as f:
    raw = f.read()
newline = b'\r\n' if b'\r\n' in raw else b'\n'
newline = newline.decode()
text = raw.replace(b'\r\n', b'\n').decode()
block = '''    if [ "${#}" -eq 0 ]; then
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
if b'ABINFO_MODE_PY' in raw:
    raise SystemExit(0)
old_persisted = '''    if [ $# -eq 0 ]; then
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
old_test13 = '''    if [ $# -eq 0 ]; then
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
old = '''    if [ $# -eq 0 ]; then
        getABInfoValue last_tune
    else
        remoteControlCommand "txTg=$1"
    fi'''
new = block.replace('    if [ "${#}" -eq 0 ]; then', '    if [ $# -eq 0 ]; then')
if marker in text:
    if text.count(old_test13) == 1:
        text = text.replace(old_test13, new, 1)
    elif text.count(old_persisted) == 1:
        text = text.replace(old_persisted, new, 1)
    else:
        raise SystemExit('existing target-persistence block is unsupported; no files changed')
else:
    if text.count(old) != 1:
        raise SystemExit(f'expected one original tune block; found {text.count(old)}')
    text = text.replace(old, new, 1)
st = os.stat(path)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
try:
    with os.fdopen(fd, 'wb') as f:
        f.write(text.replace('\n', newline).encode())
    os.chown(tmp, st.st_uid, st.st_gid)
    os.chmod(tmp, st.st_mode & 0o7777)
    os.replace(tmp, path)
finally:
    if os.path.exists(tmp): os.unlink(tmp)
PY

python3 - "$MODE_HELPER" <<'PY'
import os, sys, tempfile

for path in sys.argv[1:]:
    with open(path, 'rb') as f: raw = f.read()
    if b'per-mode target persistence v1' in raw: continue
    nl = b'\r\n' if b'\r\n' in raw else b'\n'
    nl = nl.decode()
    text = raw.replace(b'\r\n', b'\n').decode()
    if path.endswith('dvswitch-mode-buttons'):
        if (b'dvswitch-mode-targets get "$mode"' in raw
                or b'TARGET_HELPER get "$mode"' in raw):
            continue
        old = "printf '%s\\n' \"$mode\" > \"$STATE_FILE\"\nchown root:root \"$STATE_FILE\"\nchmod 600 \"$STATE_FILE\"\necho \"PASS: DVSwitch mode selected: $mode\""
        new = old + '''
if [ -x /usr/local/sbin/dvswitch-mode-targets ]; then
  target=$(/usr/local/sbin/dvswitch-mode-targets get "$mode" 2>/dev/null || true)
  [ -n "$target" ] && "$MODE_CMD" tune "$target"
fi'''
    if text.count(old) != 1: raise SystemExit(f'expected one patch target in {path}; found {text.count(old)}')
    text = text.replace(old, new, 1)
    st = os.stat(path); fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'wb') as f: f.write(text.replace('\n', nl).encode())
        os.chown(tmp, st.st_uid, st.st_gid); os.chmod(tmp, st.st_mode & 0o7777); os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
PY

php -l /usr/share/dvswitch/include/status.php >/dev/null || die 'dashboard PHP validation failed'
bash -n "$SCRIPT" "$MODE_HELPER" "$TARGET_HELPER"
echo "PASS: per-mode target persistence installed. Backup: $BACKUP_DIR (timestamp $stamp)"
