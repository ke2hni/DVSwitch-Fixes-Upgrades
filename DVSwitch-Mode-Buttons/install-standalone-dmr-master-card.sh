#!/usr/bin/env bash
set -Eeuo pipefail

STATUS=/usr/share/dvswitch/include/status.php
BACKUP_DIR=/var/backups/dvswitch-mode-buttons
MARKER='// DVSwitch-Mode-Buttons: standalone DMR Master display v1'

die(){ echo "ERROR: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die 'run with sudo'
[[ -f "$STATUS" ]] || die "missing $STATUS"

python3 - "$STATUS" "$BACKUP_DIR" "$MARKER" <<'PY'
import os, re, shutil, sys, tempfile, time
from pathlib import Path

path = Path(sys.argv[1]); backup_dir = Path(sys.argv[2]); marker = sys.argv[3]
raw = path.read_bytes(); nl = b'\r\n' if b'\r\n' in raw else b'\n'
text = raw.replace(b'\r\n', b'\n').decode('utf-8')

if text.count(marker) == 1:
    print('ALREADY INSTALLED: standalone DMR Master display v1 is present.')
    raise SystemExit(0)
if text.count(marker) > 1:
    raise SystemExit('ERROR: duplicate standalone DMR Master markers found')

helper = r'''// DVSwitch-Mode-Buttons: standalone DMR Master display v1
function dvsButtonsDmrNetwork($master) {
        $master = strtoupper(str_replace('_', ' ', (string)$master));
        return (strpos($master, 'TGIF') !== false) ? 'TGIF' : 'BM';
}

function dvsButtonsDmrTalkgroup($abinfo) {
        $values = array();
        if (isset($abinfo['last_tune'])) { $values[] = trim((string)$abinfo['last_tune']); }
        if (isset($abinfo['digital']['tg'])) { $values[] = trim((string)$abinfo['digital']['tg']); }
        foreach ($values as $value) {
                if (preg_match('/^(?:TG\s*)?([0-9]+)$/i', $value, $match) && $match[1] !== '0') { return $match[1]; }
        }
        return '';
}

function dvsButtonsDmrName($network, $talkgroup) {
        $file = ($network === 'TGIF') ? '/var/lib/mmdvm/TGList_TGIF.txt' : '/var/lib/mmdvm/TGList_BM.txt';
        if (!is_readable($file)) { return ''; }
        $lines = file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if (!is_array($lines)) { return ''; }
        foreach ($lines as $line) {
                if ($line === '' || strpos($line, '#') === 0) { continue; }
                $fields = explode(';', $line, 4);
                if (count($fields) === 4 && trim($fields[0]) === (string)$talkgroup && trim($fields[1]) === '0') {
                        $name = preg_replace('/\s+/u', ' ', str_replace('_', ' ', trim($fields[2])));
                        return is_string($name) ? $name : '';
                }
        }
        return '';
}

function dvsButtonsDmrMasterHeading($master, $abinfo) {
        return 'DMR '.dvsButtonsDmrNetwork($master).' Master';
}

function dvsButtonsDmrMasterDisplay($master, $abinfo) {
        $network = dvsButtonsDmrNetwork($master);
        $talkgroup = dvsButtonsDmrTalkgroup($abinfo);
        if ($talkgroup === '') { return '<span class="dvs-dmr-room-label" style="color:#000000;font-weight:normal;">Room</span><br/><span style="color:#b5651d;font-weight:bold;">'.htmlspecialchars((string)$master, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8').'</span>'; }
        $name = dvsButtonsDmrName($network, $talkgroup);
        $display = ($name !== '') ? $name : 'TG '.$talkgroup;
        $numberLine = ($name !== '') ? '<br/><span style="color:#b5651d;font-weight:bold;">(TG '.htmlspecialchars($talkgroup, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8').')</span>' : '';
        return '<span class="dvs-dmr-room-label" style="color:#000000;font-weight:normal;">Room</span><br/><span style="color:#b5651d;font-weight:bold;">'.htmlspecialchars($display, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8').'</span>'.$numberLine;
}

'''

include_anchor = "include_once dirname(dirname(__FILE__)).'/include/functions.php';\n"
if text.count(include_anchor) != 1:
    raise SystemExit('ERROR: expected exactly one dashboard functions include anchor')

heading_factory = 'echo "<tr><th colspan=\\"2\\">DMR Master</th></tr>\\n";'
heading_dvmods = 'echo "<tr><th colspan=\\"2\\">".dvsModsDmrMasterHeading($dmrMasterHost, $abinfo)."</th></tr>\\n";'
heading_buttons = 'echo "<tr><th colspan=\\"2\\">".dvsButtonsDmrMasterHeading($dmrMasterHost, $abinfo)."</th></tr>\\n";'

output_patterns = [
    re.compile(r'''echo "<tr><td  style=\\"background: #ffffed;\\" colspan=\\"2\\"><span style=\\"color:#b5651d;font-weight: bold\\">"\.\$dmrMasterHost\."</span></td></tr>\\n";\}'''),
    re.compile(r'''echo "<tr><td  style=\\"background: #ffffed;\\" colspan=\\"2\\"><span style=\\"color:#b5651d;font-weight:bold;white-space:normal;word-break:normal;overflow-wrap:anywhere;text-align:center;\\">"\.dvsModsDmrMasterDisplay\(\$dmrMasterHost, \$abinfo\)\."</span></td></tr>\\n";\}'''),
]
output_buttons = 'echo "<tr><td  style=\\"background: #ffffed;\\" colspan=\\"2\\"><span style=\\"color:#b5651d;font-weight: bold;white-space:normal;word-break:normal;overflow-wrap:anywhere;text-align:center;\\">".dvsButtonsDmrMasterDisplay($dmrMasterHost, $abinfo)."</span></td></tr>\\n";}'

heading_matches = [h for h in (heading_factory, heading_dvmods) if text.count(h) == 1]
if text.count(heading_buttons) == 1:
    print('ALREADY INSTALLED: standalone DMR Master card is present; manager will apply state-aware updates.')
    raise SystemExit(0)
if len(heading_matches) != 1:
    raise SystemExit(f'ERROR: expected one active supported DMR Master heading; found {len(heading_matches)}')
found = []
for pattern in output_patterns:
    found.extend(pattern.finditer(text))
if len(found) != 1:
    raise SystemExit(f'ERROR: expected exactly one supported DMR Master display output; found {len(found)}')

text = text.replace(include_anchor, include_anchor + helper, 1)
text = text.replace(heading_matches[0], heading_buttons, 1)
found = []
for pattern in output_patterns:
    found.extend(pattern.finditer(text))
if len(found) != 1:
    raise SystemExit('ERROR: DMR Master display output changed unexpectedly')
start, end = found[0].span()
text = text[:start] + output_buttons + text[end:]

backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
backup = backup_dir / ('status.php.' + time.strftime('%Y%m%d-%H%M%S'))
shutil.copy2(path, backup)
stat = path.stat(); fd, temporary = tempfile.mkstemp(dir=path.parent)
try:
    with os.fdopen(fd, 'wb') as stream:
        stream.write(text.replace('\n', nl.decode()).encode('utf-8'))
    os.chown(temporary, stat.st_uid, stat.st_gid)
    os.chmod(temporary, stat.st_mode & 0o7777)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary): os.unlink(temporary)
print(f'PASS: standalone DMR Master display installed. Backup: {backup}')
PY

php -l "$STATUS"
echo 'PASS: BM/TGIF DMR Master card is self-contained.'
