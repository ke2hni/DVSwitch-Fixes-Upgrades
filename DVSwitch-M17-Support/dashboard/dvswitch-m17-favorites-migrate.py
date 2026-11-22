#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Version: 1.0.0
# Created: 2026-11-21T18:20:00-05:00 by KE2HNI
"""Move legacy M17 favorites out of the shared Mode Buttons JSON file."""

import json
import os
import re
import tempfile
from pathlib import Path

SHARED = Path('/etc/dvswitch-mode-buttons/favorites.json')
STANDALONE = Path('/etc/dvswitch-m17-dashboard/favorites.json')


def _read(path, default):
    if path.is_symlink():
        raise ValueError(f'{path} must not be a symbolic link')
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f'{path} is unreadable or invalid JSON; it was left unchanged') from error


def _clean(items, source):
    if not isinstance(items, list) or len(items) > 250:
        raise ValueError(f'{source} M17 favorites must be a list with at most 250 entries')
    cleaned = []
    targets = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not isinstance(item.get('target'), str):
            raise ValueError(f'{source} contains an invalid M17 favorite; it was left unchanged')
        name, target = item['name'].strip(), item['target'].strip().upper()
        if not 1 <= len(name) <= 35 or not re.fullmatch(r'[A-Za-z0-9_-]{1,35}', target):
            raise ValueError(f'{source} contains an invalid M17 favorite; it was left unchanged')
        if target in targets:
            raise ValueError(f'{source} contains duplicate M17 target {target}; it was left unchanged')
        targets.add(target)
        cleaned.append({'name': name, 'target': target})
    return cleaned


def _write(path, value):
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    old_mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix='.favorites-migrate.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        if os.geteuid() == 0:
            os.chown(temporary, 0, 0)
        os.chmod(temporary, old_mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def migrate(shared=SHARED, standalone=STANDALONE):
    old_shared = _read(shared, {})
    if not isinstance(old_shared, dict):
        raise ValueError(f'{shared} must contain a JSON object; it was left unchanged')
    separate = _read(standalone, [])
    # Earlier standalone-only installs stored an object with an M17 key.
    if isinstance(separate, dict):
        if not isinstance(separate.get('M17'), list):
            raise ValueError(f'{standalone} has an unsupported legacy format; it was left unchanged')
        separate = separate['M17']
    separate = _clean(separate, 'standalone file')
    legacy = _clean(old_shared.get('M17', []), 'shared file')

    merged = list(separate)
    seen = {item['target'].upper() for item in merged}
    for item in legacy:
        if item['target'].upper() not in seen:
            merged.append(item)
            seen.add(item['target'].upper())
    if len(merged) > 250:
        raise ValueError('combined M17 favorites exceed the 250-entry limit; source files were left unchanged')

    # Commit the standalone copy first. A later shared-file error leaves a safe duplicate, never lost favorites.
    if not standalone.exists() or separate != merged or isinstance(_read(standalone, []), dict):
        _write(standalone, merged)
    if 'M17' in old_shared:
        del old_shared['M17']
        _write(shared, old_shared)
    print(f'PASS: M17 favorites are separate; preserved {len(merged)} favorite(s) at {standalone}.')


if __name__ == '__main__':
    try:
        migrate()
    except (OSError, ValueError) as error:
        raise SystemExit(f'ERROR: {error}')
