#!/usr/bin/env python3
# Version: 1.0.0
# SPDX-License-Identifier: MIT

"""Validate and atomically save ASL node favorites."""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

PATH = Path('/etc/dvswitch-asl3-support/favorites.json')


def main():
    if os.geteuid() != 0:
        raise SystemExit('ERROR: run through the dashboard sudo rule')
    try:
        data = json.load(sys.stdin)
        items = data.get('favorites') if isinstance(data, dict) else None
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError('invalid favorites list')
        clean = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError('invalid favorite entry')
            name, node = item.get('name'), item.get('node')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64 or any(ord(ch) < 32 for ch in name):
                raise ValueError('favorite names must contain 1 to 64 printable characters')
            if not isinstance(node, str) or not re.fullmatch(r'[0-9]{1,8}', node) or not node.strip('0'):
                raise ValueError('favorite nodes must be non-zero numeric node numbers')
            clean.append({'name': name.strip(), 'node': node})
        clean.sort(key=lambda item: (item['name'].casefold(), item['node']))
        PATH.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.favorites.', dir=PATH.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(clean, output, ensure_ascii=False, indent=2)
                output.write('\n')
            os.chmod(temporary, 0o644)
            os.replace(temporary, PATH)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print('PASS: saved %d ASL favorite(s).' % len(clean))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit('ERROR: %s' % error)


if __name__ == '__main__':
    main()
