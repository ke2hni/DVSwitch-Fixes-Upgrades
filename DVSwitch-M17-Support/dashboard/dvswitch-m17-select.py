#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Version: 1.0.0
# Created: 2026-11-09T23:19:00-05:00 by KE2HNI
"""Select an M17 reflector by updating USRP2M17's INI and restarting its service."""

import configparser
import datetime
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

CONFIG = Path('/etc/USRP2M17.ini')
CATALOG = Path('/var/lib/mmdvm/M17Hosts.json')
BACKUP_DIR = Path('/var/backups/dvswitch-mods/m17-dashboard')
STATE_DIR = Path('/var/lib/dvswitch-m17-dashboard')


def fail(message):
    print('ERROR: ' + message, file=sys.stderr)
    raise SystemExit(1)


def reflector_modules(row):
    enabled = row.get('enabled_modes')
    enabled = {str(value).upper() for value in enabled if isinstance(value, str)} if isinstance(enabled, list) else set()
    result = []
    for item in row.get('modules', []) if isinstance(row.get('modules'), list) else []:
        if isinstance(item, str):
            module = item
            if enabled and 'M17' not in enabled:
                continue
        elif isinstance(item, dict) and isinstance(item.get('module'), str):
            module = item['module']
            mode = str(item.get('mode', '')).upper()
            if mode != 'M17' and not (mode == 'ALL' and 'M17' in enabled):
                continue
        else:
            continue
        module = module.upper()
        if re.fullmatch(r'[A-Z0-9]', module) and module not in result:
            result.append(module)
    return result


def read_catalog_target(target):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,35}', target):
        raise ValueError('Enter a valid M17 reflector-module target.')
    try:
        designator, module = target.rsplit('-', 1)
        data = json.loads(CATALOG.read_text(encoding='utf-8'))
    except (ValueError, OSError, json.JSONDecodeError) as error:
        raise ValueError('M17 reflector catalog is unavailable; refresh it and retry.') from error
    for row in data.get('reflectors', []):
        if not isinstance(row, dict) or row.get('designator') != designator:
            continue
        modules = reflector_modules(row)
        if module not in modules:
            continue
        address = row.get('ipv4') or row.get('dns')
        try:
            address = str(ipaddress.IPv4Address(str(address)))
        except ipaddress.AddressValueError as error:
            raise ValueError(f'{designator} has no numeric IPv4 address accepted by USRP2M17.') from error
        port = row.get('port')
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f'{designator} has an invalid reflector UDP port.')
        friendly = row.get('name') if isinstance(row.get('name'), str) else designator
        return designator, module, address, port, f'{friendly.strip()} {module}'.strip()
    raise ValueError(f'{target} is not listed as an active M17 reflector module in the local catalog.')


def replace_network_values(text, updates):
    lines = text.splitlines(keepends=True)
    start = None
    end = len(lines)
    for index, line in enumerate(lines):
        section = re.match(r'^\s*\[([^]]+)\]', line)
        if section:
            if start is not None:
                end = index
                break
            if section.group(1).strip().lower() == 'm17 network':
                start = index
    if start is None:
        raise ValueError('USRP2M17 config does not contain an [M17 Network] section.')
    seen = set()
    for index in range(start + 1, end):
        line = lines[index]
        content = line.rstrip('\r\n')
        newline = line[len(content):]
        match = re.match(r'^(\s*)(Address|Name|DstPort)(\s*=\s*)([^;#]*)(.*)$', content, re.I)
        if match:
            key = match.group(2).lower()
            if key in updates:
                lines[index] = f'{match.group(1)}{match.group(2)}{match.group(3)}{updates[key]}{match.group(5)}{newline}'
                seen.add(key)
    missing = [key for key in updates if key not in seen]
    if missing:
        addition = ''.join(f'{key.title()}={updates[key]}\n' for key in missing)
        lines.insert(end, addition)
    return ''.join(lines)


def atomic_write(path, data, mode, uid, gid):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as output:
            output.write(data)
        os.chown(temporary, uid, gid)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    if os.geteuid() != 0:
        fail('run through the dashboard sudo rule')
    if not CONFIG.is_file() or CONFIG.is_symlink():
        fail('USRP2M17 config is missing or is not a regular file.')
    target = sys.stdin.readline(128).strip()
    try:
        designator, module, address, port, friendly = read_catalog_target(target)
        original = CONFIG.read_text(encoding='utf-8')
        updates = {'address': address, 'name': f'{designator} {module}', 'dstport': str(port)}
        updated = replace_network_values(original, updates)
    except (OSError, UnicodeError, ValueError) as error:
        fail(str(error))

    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read_string(original)
    current = parser['M17 Network'] if parser.has_section('M17 Network') else {}
    if all(str(current.get(key, '')).strip() == value for key, value in updates.items()):
        print(f'PASS: {friendly} is already selected; no restart was needed.')
        raise SystemExit(0)

    status = CONFIG.stat()
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = BACKUP_DIR / f'USRP2M17.ini.{stamp}'
    suffix = 1
    while backup.exists():
        backup = BACKUP_DIR / f'USRP2M17.ini.{stamp}-{suffix}'
        suffix += 1
    shutil.copy2(CONFIG, backup)
    try:
        atomic_write(CONFIG, updated, status.st_mode & 0o7777, status.st_uid, status.st_gid)
        subprocess.run(['systemctl', 'restart', 'usrp2m17.service'], check=True, timeout=20)
        subprocess.run(['systemctl', 'is-active', '--quiet', 'usrp2m17.service'], check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as error:
        shutil.copy2(backup, CONFIG)
        subprocess.run(['systemctl', 'restart', 'usrp2m17.service'], check=False, timeout=20)
        fail(f'could not activate {friendly}; the previous config was restored ({error}).')

    STATE_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
    with (STATE_DIR / 'reflector-history.tsv').open('a', encoding='utf-8') as history:
        history.write(f'{int(datetime.datetime.now().timestamp())}\t{target}\t{friendly.replace(chr(9), " ")}\n')
    print(f'PASS: selected {friendly}; USRP2M17 restarted. Backup: {backup}')


if __name__ == '__main__':
    main()
