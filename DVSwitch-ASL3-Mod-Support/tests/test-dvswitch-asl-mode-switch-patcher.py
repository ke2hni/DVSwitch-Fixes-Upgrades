#!/usr/bin/env python3
# Version: 1.0.2
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

require(module.REMOTE_BLOCK.count('python3 - "$DVSWITCH_INI"') == 1, "mode port candidates are not loaded in one config parse")
require("parseIniFile" not in module.REMOTE_BLOCK, "listener lookup starts separate INI parser processes")
require(module.REMOTE_BLOCK.count("ss -H -lunp ") == 1, "Analog_Bridge-owned listener sockets are not read from one snapshot")
require('index($0, "Analog_Bridge")' in module.REMOTE_BLOCK, "listener lookup does not exclude sockets owned by other processes")
require("grep" not in module.REMOTE_BLOCK, "listener lookup still starts a grep process per candidate")
require("unset _ASL_TLV_LISTENERS_VALID" in module.REMOTE_BLOCK, "listener cache is not invalidated after an rxport change")

# A configured candidate may also be bound by MMDVM_Bridge; only the
# Analog_Bridge-owned socket is a valid command destination.
listener_fixture = (
    'UNCONN 0 0 0.0.0.0:31103 0.0.0.0:* users:(("MMDVM_Bridge",pid=1,fd=1))\n'
    'UNCONN 0 0 0.0.0.0:33100 0.0.0.0:* users:(("Analog_Bridge",pid=2,fd=2))\n'
)
listener_filter = 'index($0, "Analog_Bridge") {port=$4; sub(/^.*:/, "", port); if (port ~ /^[0-9]+$/) printf " %s ", port}'
selected_listeners = subprocess.run(
    ["awk", listener_filter], input=listener_fixture, text=True, capture_output=True, check=True
).stdout
require("33100" in selected_listeners and "31103" not in selected_listeners,
        "listener selection accepted an MMDVM_Bridge socket as Analog_Bridge")

legacy = fixture("1.6.2").replace(
    '    else\nPYTHON_ARG="$1" python3 - <<END',
    f'    else\n{module.REMOTE_BLOCK}\nPYTHON_ARG="$1" python3 - <<END',
).replace(module.MODE_ANCHOR, f'{module.MODE_BLOCK}\n{module.MODE_ANCHOR}')
adopted = module.patch_text(legacy)
require(adopted.count(module.REMOTE_MARKER) == 1, "existing unmarked live-port patch was not adopted")
require(adopted.count(module.MODE_MARKER) == 1, "existing unmarked ASL patch was not adopted")
require(module.patch_text(adopted) == adopted, "adopted patch is not idempotent")

old_repair = fixture("1.6.3").replace(
    '    else\nPYTHON_ARG="$1" python3 - <<END',
    f'    else\n{module.REMOTE_MARKER}\n{module.LEGACY_REMOTE_BLOCK}\nPYTHON_ARG="$1" python3 - <<END',
).replace(module.MODE_ANCHOR, f'{module.MODE_MARKER}\n{module.MODE_BLOCK}\n{module.MODE_ANCHOR}')
upgraded = module.patch_text(old_repair)
require(upgraded.count(module.REMOTE_BLOCK) == 1, "slow marked routing block was not upgraded")
require(module.LEGACY_REMOTE_BLOCK not in upgraded, "slow marked routing block remains after upgrade")
require(module.patch_text(upgraded) == upgraded, "upgraded repair is not idempotent")

v67_repair = fixture("1.6.3").replace(
    '    else\nPYTHON_ARG="$1" python3 - <<END',
    f'    else\n{module.REMOTE_MARKER}\n{module.PREVIOUS_REMOTE_BLOCK}\nPYTHON_ARG="$1" python3 - <<END',
).replace(module.MODE_ANCHOR, f'{module.MODE_MARKER}\n{module.MODE_BLOCK}\n{module.MODE_ANCHOR}')
v68_repair = module.patch_text(v67_repair)
require(v68_repair.count(module.REMOTE_BLOCK) == 1, "v67 cached listener block was not upgraded")
require(module.PREVIOUS_REMOTE_BLOCK not in v68_repair, "unfiltered v67 listener block remains")
require(module.patch_text(v68_repair) == v68_repair, "v67 upgrade is not idempotent")

require_rejected(fixture("1.6.4"), "unknown DVSwitch script version")
require_rejected(fixture("1.6.2").replace(module.MODE_ANCHOR, "", 1), "missing transition anchor")
duplicate = fixture("1.6.2").replace(
    '    else\nPYTHON_ARG="$1" python3 - <<END',
    f'    else\n{module.REMOTE_BLOCK}\n{module.REMOTE_BLOCK}\nPYTHON_ARG="$1" python3 - <<END',
)
require_rejected(duplicate, "duplicate routing code")

print("PASS: ASL mode-switch patch supports 1.6.2/1.6.3, is idempotent, adopts the tested markerless patch, and rejects unsupported structures")
