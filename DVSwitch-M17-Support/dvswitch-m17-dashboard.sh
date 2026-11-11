#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI
# Version: 1.0.5
# Created: 2026-11-09T23:19:00-05:00 by KE2HNI
# Updated: 2026-11-10T15:20:00-05:00 by KE2HNI — insert M17 card without requiring the ASL add-on.
# Updated: 2026-11-10T16:40:00-05:00 by KE2HNI — make dashboard state directory searchable by Apache so the M17 button condition works.
# Updated: 2026-11-10T19:16:00-05:00 by KE2HNI — display the active M17 mode and reflector in Analog Bridge status rows.
# Updated: 2026-11-10T21:35:00-05:00 by KE2HNI — place eight network cards around Gateway Activity and alphabetize mode buttons.
# Updated: 2026-11-10T22:25:00-05:00 by KE2HNI — prevent duplicate card buildup and match the Analog Bridge panel outline.
set -Eeuo pipefail
umask 077

readonly DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly DASH=/usr/share/dvswitch/include
readonly FUNCTIONS=$DASH/functions.php
readonly STATUS=$DASH/status.php
readonly LOCALTX=$DASH/localtx.php
readonly INDEX=/usr/share/dvswitch/index.php
readonly LAYOUT="$DIR/dashboard/dvswitch-m17-layout.js"
readonly LAYOUT_TARGET=/usr/share/dvswitch/dvswitch-m17-layout.js
readonly SELECT=/usr/local/sbin/dvswitch-m17-select
readonly CATALOG_UPDATE=/usr/local/sbin/dvswitch-m17-catalog-update
readonly STATE=/var/lib/dvswitch-m17-dashboard/install-state.json
readonly BACKUPS=/var/backups/dvswitch-mods/m17-dashboard
action=${1:---install}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] || die 'Run this installer with sudo.'
for command in install php python3 systemctl; do command -v "$command" >/dev/null 2>&1 || die "Required command not found: $command"; done
for path in "$FUNCTIONS" "$STATUS" "$LOCALTX" "$INDEX"; do [[ -f "$path" && ! -L "$path" ]] || die "Dashboard file unavailable or unsafe: $path"; done
if [[ "$action" == --uninstall ]]; then
  [[ -f "$STATE" ]] || die 'No M17 dashboard installation record exists.'
else
  [[ -f /etc/USRP2M17.ini ]] || die 'Install USRP2M17 through manager option 8 first.'
  [[ -f /usr/share/dvswitch/dvswitch-mode-buttons.php ]] || die 'Install DVSwitch Mode Buttons through manager option 2 first.'
  [[ -f "$DIR/dashboard/dvswitch-m17-activity.php" && -f "$DIR/dashboard/dvswitch-m17-net-card.php" && -f "$DIR/dashboard/dvswitch-m17-layout.js" && -f "$DIR/dashboard/dvswitch-m17-select.py" && -f "$DIR/dashboard/dvswitch-m17-catalog-update.py" ]] || die 'M17 dashboard support files are incomplete.'
fi

if [[ "$action" == --check ]]; then
  php -l "$FUNCTIONS" >/dev/null && php -l "$STATUS" >/dev/null && php -l "$LOCALTX" >/dev/null && php -l "$INDEX" >/dev/null
  php -l "$DIR/dashboard/dvswitch-m17-activity.php" >/dev/null && php -l "$DIR/dashboard/dvswitch-m17-net-card.php" >/dev/null
  printf 'PASS: M17 dashboard prerequisites and PHP syntax are ready; --check made no changes.\n'
  exit 0
fi
[[ "$action" == --install || "$action" == --uninstall ]] || die "Usage: $0 [--check|--install|--uninstall]"

if [[ "$action" == --uninstall ]]; then
  [[ -f "$STATE" ]] || die 'No M17 dashboard installation record exists.'
  python3 - "$FUNCTIONS" "$STATUS" "$LOCALTX" "$INDEX" <<'PY_UNINSTALL'
import os, re, stat, sys, tempfile
from pathlib import Path
for path in map(Path,sys.argv[1:]):
    text=path.read_text(encoding='utf-8')
    if path.name=='functions.php':
        text=re.sub(r"(?m)^// DVSwitch-M17-Dashboard: merge activity v1\ninclude_once dirname\(__FILE__\)\.'/dvswitch-m17-activity\.php';\n\$lastHeard = dvsM17MergeActivity\(\$lastHeard\);\n",'',text)
    elif path.name=='status.php':
        text=re.sub(r"(?m)^// DVSwitch-M17-Dashboard: M17 Net card v1\ninclude_once dirname\(__FILE__\)\.'/dvswitch-m17-net-card\.php'; dvsM17ShowNetCard\(\);\n",'',text)
        text=re.sub(r"(?ms)^// DVSwitch-M17-Dashboard: Analog Bridge mode display v1\n.*?^    if \(is_array\(\$m17Display\)\) \{.*\}\n",'',text,count=1)
        text=text.replace('$displayMode', "$abinfo['tlv']['ambe_mode']")
        text=text.replace('$displayTarget', '$txValue')
    elif path.name=='localtx.php':
        marker='// DVSwitch-M17-Dashboard: Local Activity includes M17 v1\n'
        if marker in text:
            text=text.replace(marker,'',1)
            addition=' || $listElem[1] == "M17"'
            if text.count(addition)!=1: raise SystemExit('ERROR: M17 Local Activity filter is ambiguous; no files were changed.')
            text=text.replace(addition,'',1)
    else:
        tag='<script src="/dvswitch/dvswitch-m17-layout.js"></script>'
        text=text.replace(tag+'\n','',1)
    st=path.stat(); fd,tmp=tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd,'w',encoding='utf-8',newline='') as output: output.write(text)
    os.chown(tmp,st.st_uid,st.st_gid); os.chmod(tmp,stat.S_IMODE(st.st_mode)); os.replace(tmp,path)
PY_UNINSTALL
  systemctl disable --now dvswitch-m17-catalog-update.timer >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/dvswitch-m17-catalog-update.service /etc/systemd/system/dvswitch-m17-catalog-update.timer "$SELECT" "$CATALOG_UPDATE" "$DASH/dvswitch-m17-activity.php" "$DASH/dvswitch-m17-net-card.php" "$LAYOUT_TARGET" "$STATE"
  systemctl daemon-reload
  printf 'PASS: M17 dashboard integration removed; favorites, bridge config, and reflector catalog were preserved.\n'
  exit 0
fi

install -d -o root -g root -m 0755 "$DASH" /usr/local/sbin /etc/systemd/system /var/lib/mmdvm
install -o root -g root -m 0644 "$DIR/dashboard/dvswitch-m17-activity.php" "$DASH/dvswitch-m17-activity.php"
install -o root -g root -m 0644 "$DIR/dashboard/dvswitch-m17-net-card.php" "$DASH/dvswitch-m17-net-card.php"
install -o root -g root -m 0644 "$LAYOUT" "$LAYOUT_TARGET"
install -o root -g root -m 0755 "$DIR/dashboard/dvswitch-m17-select.py" "$SELECT"
install -o root -g root -m 0755 "$DIR/dashboard/dvswitch-m17-catalog-update.py" "$CATALOG_UPDATE"
install -o root -g root -m 0644 "$DIR/dashboard/dvswitch-m17-catalog-update.service" /etc/systemd/system/dvswitch-m17-catalog-update.service
install -o root -g root -m 0644 "$DIR/dashboard/dvswitch-m17-catalog-update.timer" /etc/systemd/system/dvswitch-m17-catalog-update.timer

python3 - "$FUNCTIONS" "$STATUS" "$LOCALTX" "$INDEX" "$STATE" "$BACKUPS" <<'PY_INSTALL'
import json, os, re, stat, sys, tempfile
from datetime import datetime
from pathlib import Path
functions,status,localtx,index,state_path,backup_root=map(Path,sys.argv[1:])
if not state_path.exists():
    backup_root.mkdir(mode=0o700,parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); backup=backup_root/('install-'+stamp)
    suffix=0
    while backup.exists(): suffix+=1; backup=backup_root/(f'install-{stamp}-{suffix}')
    backup.mkdir(mode=0o700)
    for path in (functions,status,localtx,index):
        import shutil; shutil.copy2(path,backup/path.name)
    state_path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
    state_path.write_text(json.dumps({'version':'1.0.0','backup':str(backup)},indent=2)+'\n',encoding='utf-8'); state_path.chmod(0o600)
# umask 077 would otherwise create this directory as 0700, hiding the M17 button
# from Apache's is_file() check. Keep the JSON file private; only allow traversal.
state_path.parent.chmod(0o755)
changes=[]
backup=Path(json.loads(state_path.read_text(encoding='utf-8'))['backup'])
if backup.is_dir() and not (backup/index.name).exists():
    import shutil; shutil.copy2(index,backup/index.name)
for path in (functions,status,localtx,index):
    text=path.read_text(encoding='utf-8')
    if path.name=='functions.php':
        marker='// DVSwitch-M17-Dashboard: merge activity v1'
        block=marker+"\ninclude_once dirname(__FILE__).'/dvswitch-m17-activity.php';\n$lastHeard = dvsM17MergeActivity($lastHeard);"
        if marker not in text:
            anchor='$lastHeard = dvsModsStfuMergeActivity($lastHeard);'
            if text.count(anchor)!=1: raise SystemExit('ERROR: functions.php activity anchor missing or ambiguous.')
            text=text.replace(anchor,anchor+'\n'+block,1)
        elif text.count(marker)!=1: raise SystemExit('ERROR: duplicate M17 activity integration markers.')
    elif path.name=='status.php':
        marker='// DVSwitch-M17-Dashboard: M17 Net card v1'
        block=marker+"\ninclude_once dirname(__FILE__).'/dvswitch-m17-net-card.php'; dvsM17ShowNetCard();"
        if marker not in text:
            # Insert at the end of the status include so M17 does not depend on the optional ASL card.
            marker_pos=text.rfind('?>')
            if marker_pos < 0: raise SystemExit('ERROR: status.php PHP closing tag is missing.')
            text=text[:marker_pos]+block+'\n'+text[marker_pos:]
        elif text.count(marker)!=1: raise SystemExit('ERROR: duplicate M17 Net card markers.')
        display_marker='// DVSwitch-M17-Dashboard: Analog Bridge mode display v1'
        if display_marker not in text:
            anchor=re.search(r'(?m)^\s*echo .*<table.*margin-top:4px.*$',text)
            block=(display_marker+"\n    $displayMode = $abinfo['tlv']['ambe_mode'];\n"
                   "    $displayTarget = $txValue;\n"
                   "    include_once dirname(__FILE__).'/dvswitch-m17-net-card.php';\n"
                   "    $m17Display = dvsM17CurrentDisplayTarget();\n"
                   "    if (is_array($m17Display)) { $displayMode = $m17Display['mode']; $displayTarget = htmlspecialchars($m17Display['target'], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }\n")
            if not anchor: raise SystemExit('ERROR: Analog Bridge display anchor missing or ambiguous.')
            text=text[:anchor.start()]+block+text[anchor.start():]
            mode_rows=re.findall(r"(?m)^.*<th width=50%>Mode</th>.*\$abinfo\[['\"]tlv['\"]\]\[['\"]ambe_mode['\"]\].*$",text)
            target_rows=re.findall(r"(?m)^.*<th width=50%>Tx TG/Ref</th>.*\$txValue.*$",text)
            if len(mode_rows)!=2 or len(target_rows)!=2: raise SystemExit('ERROR: Analog Bridge display rows are missing or ambiguous.')
            text=re.sub(r"(?m)(^.*<th width=50%>Mode</th>.*)\$abinfo\[['\"]tlv['\"]\]\[['\"]ambe_mode['\"]\](.*$)",r"\1$displayMode\2",text)
            text=re.sub(r"(?m)(^.*<th width=50%>Tx TG/Ref</th>.*)\$txValue(.*$)",r"\1$displayTarget\2",text)
        elif text.count(display_marker)!=1: raise SystemExit('ERROR: duplicate M17 Analog Bridge display markers.')
    elif path.name=='localtx.php':
        marker='// DVSwitch-M17-Dashboard: Local Activity includes M17 v1'
        if marker not in text:
            anchor='$listElem[1] == "STFU")) {'
            if text.count(anchor)!=1: raise SystemExit('ERROR: Local Activity mode filter anchor missing or ambiguous.')
            text=text.replace(anchor,'$listElem[1] == "STFU" || $listElem[1] == "M17")) {',1)
            text=text.replace('$counter = 0;',marker+'\n$counter = 0;',1)
        elif text.count(marker)!=1: raise SystemExit('ERROR: duplicate M17 Local Activity markers.')
    else:
        tag='<script src="/dvswitch/dvswitch-m17-layout.js"></script>'
        if tag not in text:
            if text.count('</body>')!=1: raise SystemExit('ERROR: index.php body ending is missing or ambiguous.')
            text=text.replace('</body>',tag+'\n</body>',1)
        elif text.count(tag)!=1: raise SystemExit('ERROR: duplicate M17 layout script tags.')
    changes.append((path,text))
for path,text in changes:
    st=path.stat(); fd,tmp=tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd,'w',encoding='utf-8',newline='') as output: output.write(text)
    os.chown(tmp,st.st_uid,st.st_gid); os.chmod(tmp,stat.S_IMODE(st.st_mode)); os.replace(tmp,path)
PY_INSTALL

python3 "$CATALOG_UPDATE"
python3 - /var/lib/mmdvm/M17Hosts.json /etc/USRP2M17.ini /var/lib/dvswitch-m17-dashboard/reflector-history.tsv <<'PY_CURRENT'
import configparser, json, re, sys, time
from pathlib import Path
catalog_path, config_path, history_path = map(Path, sys.argv[1:])
if not history_path.exists() or not history_path.stat().st_size:
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    parser=configparser.ConfigParser(interpolation=None); parser.read(config_path,encoding='utf-8')
    name=parser.get('M17 Network','Name',fallback='').strip()
    pieces=name.rsplit(' ',1)
    if len(pieces)==2:
        designator,desired_module=pieces[0],pieces[1].upper()
        for row in catalog.get('reflectors',[]):
            if not isinstance(row,dict) or row.get('designator')!=designator: continue
            enabled={str(value).upper() for value in row.get('enabled_modes',[]) if isinstance(value,str)} if isinstance(row.get('enabled_modes'),list) else set()
            modules=[]
            for item in row.get('modules',[]) if isinstance(row.get('modules'),list) else []:
                if isinstance(item,str):
                    module=item.upper()
                    if enabled and 'M17' not in enabled: continue
                elif isinstance(item,dict) and isinstance(item.get('module'),str):
                    module=item['module'].upper(); mode=str(item.get('mode','')).upper()
                    if mode!='M17' and not (mode=='ALL' and 'M17' in enabled): continue
                else: continue
                if re.fullmatch(r'[A-Z0-9]',module) and module not in modules: modules.append(module)
            if desired_module not in modules: break
            friendly=row.get('name') if isinstance(row.get('name'),str) else designator
            history_path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
            with history_path.open('a',encoding='utf-8') as history:
                history.write(f"{int(time.time())}\t{designator}-{desired_module}\t{friendly.strip()} {desired_module}\n")
            break
PY_CURRENT
python3 - /var/lib/mmdvm/M17Hosts.json /etc/dvswitch-mode-buttons/favorites.json /var/lib/dvswitch-m17-dashboard/m17-favorites-seeded <<'PY_SEED'
import json, os, re, sys, tempfile
import ipaddress
from pathlib import Path
catalog,favorites,marker=map(Path,sys.argv[1:])
if not marker.exists():
    data=json.loads(catalog.read_text(encoding='utf-8'))
    saved=json.loads(favorites.read_text(encoding='utf-8'))
    if not isinstance(saved,dict): raise SystemExit('ERROR: existing dashboard favorites are not a JSON object.')
    if not isinstance(saved.get('M17'),list) or not saved['M17']:
        items=[]
        for row in data.get('reflectors',[]):
            if not isinstance(row,dict): continue
            designator=row.get('designator'); modules=row.get('modules')
            if not isinstance(designator,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,30}',designator) or not isinstance(modules,list): continue
            try: ipaddress.IPv4Address(str(row.get('ipv4') or row.get('dns') or ''))
            except ipaddress.AddressValueError: continue
            enabled={str(value).upper() for value in row.get('enabled_modes',[]) if isinstance(value,str)} if isinstance(row.get('enabled_modes'),list) else set()
            supported=[]
            for item in modules:
                if isinstance(item,str):
                    module=item.upper()
                    if enabled and 'M17' not in enabled: continue
                elif isinstance(item,dict) and isinstance(item.get('module'),str):
                    module=item['module'].upper(); mode=str(item.get('mode','')).upper()
                    if mode!='M17' and not (mode=='ALL' and 'M17' in enabled): continue
                else: continue
                if re.fullmatch(r'[A-Z0-9]',module) and module not in supported: supported.append(module)
            modules=supported
            if not modules: continue
            module='A' if 'A' in modules else modules[0]
            name=row.get('name') if isinstance(row.get('name'),str) and row['name'].strip() else designator
            items.append({'name':(name.strip()+' '+module)[:35],'target':designator+'-'+module})
        saved['M17']=sorted(items,key=lambda item:(item['name'].casefold(),item['target'].casefold()))[:250]
    fd,tmp=tempfile.mkstemp(dir=favorites.parent)
    with os.fdopen(fd,'w',encoding='utf-8') as output: json.dump(saved,output,ensure_ascii=False,indent=2); output.write('\n')
    if os.geteuid()==0: os.chown(tmp,0,0)
    os.chmod(tmp,0o644); os.replace(tmp,favorites)
    marker.parent.mkdir(mode=0o755,parents=True,exist_ok=True); marker.write_text('M17 starter favorites seeded once.\n',encoding='utf-8'); marker.chmod(0o644)
    print(f"PASS: seeded {len(saved.get('M17',[]))} M17 favorites; future edits and deletions are preserved.")
else:
    print('PASS: existing M17 favorites preserved.')
PY_SEED

php -l "$FUNCTIONS" >/dev/null && php -l "$STATUS" >/dev/null && php -l "$LOCALTX" >/dev/null && php -l "$INDEX" >/dev/null
php -l "$DIR/dashboard/dvswitch-m17-activity.php" >/dev/null && php -l "$DIR/dashboard/dvswitch-m17-net-card.php" >/dev/null
systemctl daemon-reload
systemctl enable --now dvswitch-m17-catalog-update.timer >/dev/null
printf 'PASS: M17 dashboard integration installed.\n'
