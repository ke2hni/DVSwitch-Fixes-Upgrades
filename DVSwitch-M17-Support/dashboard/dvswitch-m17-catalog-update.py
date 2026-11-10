#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Version: 1.0.0
# Created: 2026-11-09T23:19:00-05:00 by KE2HNI
"""Refresh the public M17 reflector catalog without touching user favorites."""

import json
import os
import tempfile
import urllib.request
from pathlib import Path

URL = 'https://m17-project.github.io/hostfiles/M17Hosts.json'
DEST = Path('/var/lib/mmdvm/M17Hosts.json')


def valid(data):
    rows = data.get('reflectors') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('the catalog has no reflectors')
    accepted = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        designator = row.get('designator')
        modules = row.get('modules')
        if (isinstance(designator, str) and designator and len(designator) <= 30
                and isinstance(modules, list)):
            accepted += 1
    if not accepted:
        raise ValueError('the catalog contains no usable reflector records')
    return accepted


def main():
    request = urllib.request.Request(URL, headers={'User-Agent': 'DVSwitch-M17-Dashboard/1.0'})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read(8 * 1024 * 1024 + 1)
    if len(payload) > 8 * 1024 * 1024:
        raise ValueError('catalog is larger than the 8 MiB safety limit')
    data = json.loads(payload.decode('utf-8'))
    count = valid(data)
    DEST.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.M17Hosts.', dir=DEST.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(data, output, ensure_ascii=False, separators=(',', ':'))
            output.write('\n')
        os.chown(temporary, 0, 0)
        os.chmod(temporary, 0o644)
        os.replace(temporary, DEST)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f'PASS: refreshed {count} M17 reflector records at {DEST}; favorites were untouched.')


if __name__ == '__main__':
    main()
