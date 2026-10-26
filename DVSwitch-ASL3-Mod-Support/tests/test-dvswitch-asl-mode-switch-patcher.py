#!/usr/bin/env python3
# Version: 1.0.0
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Test ASL mode-switch patching, idempotency, legacy adoption, and guards."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "lib" / "patch_dvswitch_asl_mode_switch.py"
spec = importlib.util.spec_from_file_location("patch_dvswitch_asl_mode_switch", PATCHER)
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

print("PASS: ASL mode-switch patch supports 1.6.2/1.6.3, is idempotent, adopts the tested markerless patch, and rejects unsupported structures")
