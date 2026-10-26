#!/usr/bin/env bash
set -Eeuo pipefail
INDEX='/usr/share/dvswitch/index.php'
STATUS='/usr/share/dvswitch/include/status.php'
BACKUP_DIR='/var/backups/dvswitch-mode-buttons/refresh-cleanup'
[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'ERROR: run with sudo.' >&2; exit 1; }
[[ -f "$INDEX" && -f "$STATUS" ]] || { echo 'ERROR: required dashboard file missing.' >&2; exit 1; }
before_status=$(sha256sum "$STATUS" | awk '{print $1}')
grep -Fq 'DVSwitch-Mode-Buttons 1.0.0-test8' "$INDEX" || { echo 'ERROR: expected mode-button block not found.' >&2; exit 1; }
grep -Fq 'syncAttempts' "$INDEX" || { echo 'PASS: failed polling experiment already removed; no files changed.'; exit 0; }
install -d -o root -g root -m 0700 "$BACKUP_DIR"
backup="$BACKUP_DIR/index.php.$(date +%Y%m%d-%H%M%S)"
cp -a -- "$INDEX" "$backup"
python3 - "$INDEX" <<'PY'
from pathlib import Path
import os, sys, tempfile
path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
old = """<script>(function(){const box=document.getElementById('dvs-mode-buttons'),buttons=[...box.querySelectorAll('button')];let syncAttempts=0;function select(mode,network){buttons.forEach(b=>b.classList.toggle('selected',b.dataset.mode===(mode==='DMR'?(network||''):mode)))}async function refresh(){try{const r=await fetch('/dvswitch/dvswitch-mode-buttons.php?status=1',{cache:'no-store'}),j=await r.json();if(j.ok)select(j.mode,j.network)}catch(e){}if(syncAttempts++<4)setTimeout(refresh,1500)}buttons.forEach(b=>b.addEventListener('click',async()=>{buttons.forEach(x=>x.disabled=true);try{const r=await fetch('/dvswitch/dvswitch-mode-buttons.php?mode='+encodeURIComponent(b.dataset.mode)),j=await r.json();if(!j.ok)throw new Error(j.output||j.error||'switch failed');select(j.mode,j.network)}catch(e){alert('Mode switch failed: '+e.message)}finally{buttons.forEach(x=>x.disabled=false)}}));refresh()})();</script>"""
new = """<script>(function(){const box=document.getElementById('dvs-mode-buttons'),buttons=[...box.querySelectorAll('button')];function select(mode,network){buttons.forEach(b=>b.classList.toggle('selected',b.dataset.mode===(mode==='DMR'?(network||''):mode)))}async function refresh(){try{const r=await fetch('/dvswitch/dvswitch-mode-buttons.php?status=1',{cache:'no-store'}),j=await r.json();if(j.ok)select(j.mode,j.network)}catch(e){}}buttons.forEach(b=>b.addEventListener('click',async()=>{buttons.forEach(x=>x.disabled=true);try{const r=await fetch('/dvswitch/dvswitch-mode-buttons.php?mode='+encodeURIComponent(b.dataset.mode)),j=await r.json();if(!j.ok)throw new Error(j.output||j.error||'switch failed');select(j.mode,j.network)}catch(e){alert('Mode switch failed: '+e.message)}finally{buttons.forEach(x=>x.disabled=false)}}));refresh()})();</script>"""
if text.count(old) != 1:
    raise SystemExit(f'ERROR: expected one failed polling block; found {text.count(old)}')
text = text.replace(old, new, 1)
st = path.stat()
fd, tmp = tempfile.mkstemp(dir=path.parent)
with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
    stream.write(text)
os.chown(tmp, st.st_uid, st.st_gid)
os.chmod(tmp, st.st_mode & 0o7777)
os.replace(tmp, path)
PY
php -l "$INDEX" >/dev/null
after_status=$(sha256sum "$STATUS" | awk '{print $1}')
[[ "$before_status" == "$after_status" ]] || { echo 'ERROR: status.php changed unexpectedly.' >&2; exit 1; }
echo "PASS: failed button polling experiment removed from index.php. Backup: $backup"
echo "PASS: status.php unchanged ($after_status)."
