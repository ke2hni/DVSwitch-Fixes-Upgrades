#!/usr/bin/env python3
# Version: 1.0.0
# Created: 2026-11-11T12:08:00-05:00 by KE2HNI
"""Check that D-Star validation accepts the M17 dashboard's display wrapper."""

import importlib.util
from pathlib import Path

PATCHER = Path(__file__).resolve().parents[1] / 'lib' / 'patch_dashboard_dstar.py'
spec = importlib.util.spec_from_file_location('patch_dashboard_dstar', PATCHER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

base = module.INSERT_ANCHOR + module.TOOLTIP_OLD + module.ROW_OLD * 2
patched = module.patch_text(base)
assert module.patch_text(patched) == patched, 'D-Star patch must remain idempotent.'

m17_patched = patched.replace(module.ROW_NEW, module.ROW_M17)
assert m17_patched.count(module.ROW_M17) == 2
assert module.patch_text(m17_patched) == m17_patched, 'M17 Tx display wrapper must validate as installed.'

incomplete = m17_patched.replace(module.ROW_M17, module.ROW_NEW, 1)
assert module.patch_text(incomplete) == incomplete, 'Mixed valid D-Star/M17 rows must remain recognized.'

broken = m17_patched.replace(module.ROW_M17, '', 1)
try:
    module.patch_text(broken)
except module.PatchError:
    pass
else:
    raise AssertionError('Incomplete D-Star/M17 display must still be rejected.')

print('PASS: D-Star modification validation accepts the M17 Tx display and rejects incomplete edits.')
