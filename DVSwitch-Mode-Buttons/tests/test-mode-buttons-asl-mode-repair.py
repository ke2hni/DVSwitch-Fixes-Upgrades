#!/usr/bin/env python3
# Version: 1.0.0
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Test the self-contained Mode Buttons ASL repair patcher and installer checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "lib" / "patch_dvswitch_mode_buttons_asl_mode.py"
spec = importlib.util.spec_from_file_location("patch_dvswitch_mode_buttons_asl_mode", PATCHER)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load ASL mode-switch patcher")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(version: str) -> str:
    return f'''#!/bin/bash
SCRIPT_VERSION="{version}"
function remoteControlCommand() {{
    if [ ! -z "${{DEBUG}}" ]; then
        echo "remoteControlCommand $1"
    else
PYTHON_ARG="$1" python3 - <<END
END
    fi
}}
function setMode() {{
            ${{DEBUG}} setTLVRxPort 30000  # cause AB to stop listening
            _MBTX=`parseIniFile "$DVSWITCH_INI" "$_MODE" "TXPort"`
}}
'''


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_rejected(text: str, reason: str) -> None:
    try:
        module.patch_text(text)
    except module.PatchError:
        return
    raise AssertionError(f"unsafe input accepted: {reason}")


for version in ("1.6.2", "1.6.3"):
    stock = fixture(version)
    repaired = module.patch_text(stock)
    require(repaired.count(module.REMOTE_MARKER) == 1, f"remote marker missing for {version}")
    require(repaired.count(module.REMOTE_BLOCK) == 1, f"live-port routing missing for {version}")
    require(repaired.count(module.MODE_MARKER) == 1, f"ASL transition marker missing for {version}")
    require(repaired.count(module.MODE_BLOCK) == 1, f"ASL listener selection missing for {version}")
    require(module.patch_text(repaired) == repaired, f"patch is not idempotent for {version}")
    with tempfile.NamedTemporaryFile("w", suffix=".sh", encoding="utf-8") as candidate:
        candidate.write(repaired)
        candidate.flush()
        subprocess.run(["bash", "-n", candidate.name], check=True)

legacy = fixture("1.6.2").replace(
    '    else\nPYTHON_ARG="$1" python3 - <<END',
    f'    else\n{module.REMOTE_BLOCK}\nPYTHON_ARG="$1" python3 - <<END',
).replace(module.MODE_ANCHOR, f'{module.MODE_BLOCK}\n{module.MODE_ANCHOR}')
adopted = module.patch_text(legacy)
require(adopted.count(module.REMOTE_MARKER) == 1, "existing unmarked live-port patch was not adopted")
require(adopted.count(module.MODE_MARKER) == 1, "existing unmarked ASL patch was not adopted")
require(module.patch_text(adopted) == adopted, "adopted patch is not idempotent")

require_rejected(fixture("1.6.4"), "unknown DVSwitch script version")
require_rejected(fixture("1.6.2").replace(module.MODE_ANCHOR, "", 1), "missing transition anchor")
duplicate = fixture("1.6.2").replace(
    '    else\nPYTHON_ARG="$1" python3 - <<END',
    f'    else\n{module.REMOTE_BLOCK}\n{module.REMOTE_BLOCK}\nPYTHON_ARG="$1" python3 - <<END',
)
require_rejected(duplicate, "duplicate routing code")

BUTTON_INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text(encoding="utf-8")
BUTTON_REPAIR = (ROOT / "dvswitch-mode-buttons-asl-mode-switch-repair.sh").read_text(encoding="utf-8")
assert 'ASL_MODE_REPAIR="$SCRIPT_DIR/dvswitch-mode-buttons-asl-mode-switch-repair.sh"' in BUTTON_INSTALLER
assert 'if [[ ! -x "$ASL_NODE_HELPER" ]]' in BUTTON_INSTALLER
assert 'SKIP: ASL 3 support is not installed; no ASL mode-switch repair is needed.' in BUTTON_INSTALLER
assert 'apply_asl_mode_repair --check' in BUTTON_INSTALLER
assert 'apply_asl_mode_repair --install' in BUTTON_INSTALLER
assert "../DVSwitch-ASL3-Mod-Support" not in BUTTON_INSTALLER
assert 'patch_dvswitch_mode_buttons_asl_mode.py' in BUTTON_REPAIR
assert 'BACKUP_ROOT="/var/backups/dvswitch-mode-buttons/asl-mode-switch"' in BUTTON_REPAIR
print("PASS: self-contained Mode Buttons ASL repair supports 1.6.2/1.6.3, checks idempotently, adopts tested patches, and rejects unsupported structures")
