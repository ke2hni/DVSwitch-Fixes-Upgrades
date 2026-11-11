#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Version: 1.0.0
# Created: 2026-11-11T11:30:00-05:00 by KE2HNI
"""Validate and atomically save favorites for the standalone M17 dashboard."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

DEST = Path('/etc/dvswitch-m17-dashboard/favorites.json')

def main():
    if os.geteuid() != 0:
        raise SystemExit('ERROR: run through the dashboard sudo rule.')
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise SystemExit(f'ERROR: invalid favorites JSON: {error}')
    if not isinstance(data, list) or len(data) > 250:
        raise SystemExit('ERROR: favorites must be a list containing at most 250 entries.')
    cleaned, targets = [], set()
    for item in data:
        if not isinstance(item, dict):
            raise SystemExit('ERROR: each favorite must contain a name and target.')
        name, target = item.get('name'), item.get('target')
        if not isinstance(name, str) or not isinstance(target, str):
            raise SystemExit('ERROR: each favorite must contain a name and target.')
        name, target = name.strip(), target.strip().upper()
        if not 1 <= len(name) <= 35 or not re.fullmatch(r'[A-Za-z0-9_-]{1,35}', target):
            raise SystemExit('ERROR: favorite name or M17 target is invalid.')
        if target in targets:
            raise SystemExit(f'ERROR: duplicate M17 target: {target}')
        targets.add(target)
        cleaned.append({'name': name, 'target': target})
    DEST.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.favorites.', dir=DEST.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(cleaned, output, ensure_ascii=False, indent=2)
            output.write('\n')
        os.chown(temporary, 0, 0)
        os.chmod(temporary, 0o644)
        os.replace(temporary, DEST)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f'PASS: saved {len(cleaned)} standalone M17 favorites.')

if __name__ == '__main__':
    main()
