#!/usr/bin/env python3
# Version: 1.0.4
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Test the self-contained Mode Buttons ASL repair patcher and installer checks."""

from __future__ import annotations

import importlib.util
import os
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

require(module.REMOTE_BLOCK.count('python3 - "$DVSWITCH_INI"') == 1, "mode port candidates are not loaded in one config parse")
require("parseIniFile" not in module.REMOTE_BLOCK, "listener lookup starts separate INI parser processes")
require(module.REMOTE_BLOCK.count("ss -H -lunp ") == 1, "Analog_Bridge-owned listener sockets are not read from one snapshot")
require('index($0, "Analog_Bridge")' in module.REMOTE_BLOCK, "listener lookup does not exclude sockets owned by other processes")
require("grep" not in module.REMOTE_BLOCK, "listener lookup still starts a grep process per candidate")
require("unset _ASL_TLV_LISTENERS_VALID" in module.REMOTE_BLOCK, "listener cache is not invalidated after an rxport change")

# The mode command must select the Analog_Bridge socket when another process
# is listening on a configured TLV candidate port.
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
require(module.PREVIOUS_REMOTE_BLOCK not in v68_repair, "unfiltered v67 listener block remains after upgrade")
require(module.patch_text(v68_repair) == v68_repair, "v67 repair upgrade is not idempotent")

require_rejected(fixture("1.6.4"), "unknown DVSwitch script version")
require_rejected(fixture("1.6.2").replace(module.MODE_ANCHOR, "", 1), "missing transition anchor")
duplicate = fixture("1.6.2").replace(
    '    else\nPYTHON_ARG="$1" python3 - <<END',
    f'    else\n{module.REMOTE_BLOCK}\n{module.REMOTE_BLOCK}\nPYTHON_ARG="$1" python3 - <<END',
)
require_rejected(duplicate, "duplicate routing code")

BUTTON_INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text(encoding="utf-8")
BUTTON_REPAIR = (ROOT / "dvswitch-mode-buttons-asl-mode-switch-repair.sh").read_text(encoding="utf-8")
MODE_HELPER = (ROOT / "dvswitch-mode-buttons").read_text(encoding="utf-8")
assert 'ASL_MODE_REPAIR="$SCRIPT_DIR/dvswitch-mode-buttons-asl-mode-switch-repair.sh"' in BUTTON_INSTALLER
assert 'if [[ ! -x "$ASL_NODE_HELPER" ]]' in BUTTON_INSTALLER
assert 'SKIP: ASL 3 support is not installed; no ASL mode-switch repair is needed.' in BUTTON_INSTALLER
assert 'apply_asl_mode_repair --check' in BUTTON_INSTALLER
assert 'apply_asl_mode_repair --install' in BUTTON_INSTALLER
assert "../DVSwitch-ASL3-Mod-Support" not in BUTTON_INSTALLER
assert 'patch_dvswitch_mode_buttons_asl_mode.py' in BUTTON_REPAIR
assert 'BACKUP_ROOT="/var/backups/dvswitch-mode-buttons/asl-mode-switch"' in BUTTON_REPAIR
assert '# Version: 1.0.0-test71' in MODE_HELPER
assert 'VERSION="1.0.0-test71"' in BUTTON_INSTALLER
assert 'Analog_Bridge did not confirm the mode change; ASL remains selected.' in MODE_HELPER
assert 'NOTICE: retrying the mode command after ASL link cleanup.' in MODE_HELPER
assert MODE_HELPER.index('Analog_Bridge did not confirm the mode change; ASL remains selected.') < MODE_HELPER.index('printf \'%s\\n\' "$mode" > "$STATE_FILE"')

# Exercise confirmation and one retry with a fake command: a delayed ASL
# transition must recover, while an unresponsive bridge must keep ASL saved.
guard_start = MODE_HELPER.index("# Do not record a mode change away from ASL")
guard_end = MODE_HELPER.index('printf \'%s\\n\' "$mode" > "$STATE_FILE"', guard_start)
mode_guard = MODE_HELPER[guard_start:guard_end]
with tempfile.TemporaryDirectory(prefix="mode-buttons-asl-retry-") as directory:
    temporary = Path(directory)
    fake_mode = temporary / "fake-mode"
    live_state = temporary / "live-mode"
    fake_mode.write_text(
        '#!/bin/bash\n'
        'if [[ "$1" == mode && $# -eq 2 && "${IGNORE_MODE_COMMAND:-0}" != 1 ]]; then printf \'{"tlv":{"ambe_mode":"%s"}}\\n\' "$2" > "$ABINFO_DIR/ABInfo_test.json"; fi\n'
    )
    fake_mode.chmod(0o755)
    prelude = (
        f'MODE_CMD={fake_mode}; export ABINFO_DIR={live_state}; previous_mode=ASL; mode=P25; '
        'die(){ echo "ERROR: $*" >&2; exit 1; }; sleep(){ :; }\n'
    )
    live_state.mkdir()
    (live_state / "ABInfo_test.json").write_text('{"tlv":{"ambe_mode":"ASL"}}\n')
    recovered = subprocess.run(
        ["bash", "-c", prelude + mode_guard + 'printf "STATE_WRITE\\n"'],
        text=True, capture_output=True, check=False,
    )
    require(recovered.returncode == 0 and "STATE_WRITE" in recovered.stdout,
            "one retry did not recover a delayed ASL-to-digital transition")
    require('"P25"' in (live_state / "ABInfo_test.json").read_text(), "retry did not issue the selected mode")
    (live_state / "ABInfo_test.json").write_text('{"tlv":{"ambe_mode":"ASL"}}\n')
    not_recovered = subprocess.run(
        ["bash", "-c", prelude + mode_guard + 'printf "STATE_WRITE\\n"'],
        env={**os.environ, "IGNORE_MODE_COMMAND": "1"}, text=True, capture_output=True, check=False,
    )
    require(not_recovered.returncode != 0 and "STATE_WRITE" not in not_recovered.stdout,
            "a failed retry incorrectly allowed the saved mode to leave ASL")
    require("ASL remains selected" in not_recovered.stderr,
            "a non-matching live mode incorrectly passed transition confirmation")
print("PASS: self-contained Mode Buttons ASL repair supports 1.6.2/1.6.3, checks idempotently, adopts tested patches, and rejects unsupported structures")
