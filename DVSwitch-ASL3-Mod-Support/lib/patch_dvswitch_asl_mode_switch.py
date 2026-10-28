#!/usr/bin/env python3
# Version: 1.0.1
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Jeff Milne, KE2HNI

"""Patch the installed DVSwitch mode command to route around stale TLV ports."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


REMOTE_MARKER = "        # DVSwitch-Mods: ASL-aware TLV command routing v1"
MODE_MARKER = "            # DVSwitch-Mods: ASL-aware mode transition routing v1"
REMOTE_BLOCK = '''        if [ -z "${_ASL_TLV_CANDIDATES+x}" ]; then
            _ASL_TLV_CANDIDATES=$(python3 - "$DVSWITCH_INI" <<'PY_ASL_PORTS'
import configparser, sys
from pathlib import Path

parser = configparser.RawConfigParser(inline_comment_prefixes=(";",))
parser.read_string("[dummy_section]\\n" + Path(sys.argv[1]).read_text())
print("30000", end=" ")
for section in ("ASL", "DMR", "DSTAR", "NXDN", "P25", "YSF", "STFU"):
    try:
        print(parser.get(section, "TXPort"), end=" ")
    except (configparser.Error, KeyError):
        pass
PY_ASL_PORTS
)
        fi
        if [ -z "${_ASL_TLV_LISTENERS_VALID:-}" ]; then
            _ASL_TLV_LISTENERS=$(ss -H -lun 2>/dev/null | awk '{port=$4; sub(/^.*:/, "", port); printf " %s ", port}')
            _ASL_TLV_LISTENERS_VALID=1
        fi
        for _candidate in $_ASL_TLV_CANDIDATES; do
            case "$_ASL_TLV_LISTENERS" in *" $_candidate "*) TLV_PORT=$_candidate; break;; esac
        done
        case "$1" in rxport=*) unset _ASL_TLV_LISTENERS_VALID;; esac'''
LEGACY_REMOTE_BLOCK = '''        for _candidate in 30000 $(parseIniFile "$DVSWITCH_INI" ASL TXPort) $(parseIniFile "$DVSWITCH_INI" DMR TXPort) $(parseIniFile "$DVSWITCH_INI" DSTAR TXPort) $(parseIniFile "$DVSWITCH_INI" NXDN TXPort) $(parseIniFile "$DVSWITCH_INI" P25 TXPort) $(parseIniFile "$DVSWITCH_INI" YSF TXPort) $(parseIniFile "$DVSWITCH_INI" STFU TXPort); do if ss -H -lun "sport = :${_candidate}" 2>/dev/null | grep -q .; then TLV_PORT=$_candidate; break; fi; done'''
MODE_BLOCK = '''            if [ "$(getABInfoValue tlv ambe_mode)" = "ASL" ]; then if ss -lunp "sport = :30000" 2>/dev/null | grep -q "Analog_Bridge"; then TLV_PORT=30000; else TLV_PORT=$(parseIniFile "$DVSWITCH_INI" "ASL" "TXPort"); fi; fi'''
REMOTE_ANCHOR = '    else\nPYTHON_ARG="$1" python3 - <<END'
MODE_ANCHOR = '            ${DEBUG} setTLVRxPort 30000  # cause AB to stop listening'


class PatchError(RuntimeError):
    """Raised when the installed script is outside the verified structure."""


def _replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PatchError(f"expected one {description}; found {count}")
    return text.replace(old, new, 1)


def patch_text(text: str) -> str:
    versions = re.findall(r'^SCRIPT_VERSION=["\']([^"\']+)["\']\s*$', text, re.MULTILINE)
    if len(versions) != 1 or versions[0] not in {"1.6.2", "1.6.3"}:
        raise PatchError("supported dvswitch.sh versions are 1.6.2 and 1.6.3")

    remote_markers = text.count(REMOTE_MARKER)
    mode_markers = text.count(MODE_MARKER)
    remote_blocks = text.count(REMOTE_BLOCK)
    legacy_remote_blocks = text.count(LEGACY_REMOTE_BLOCK)
    mode_blocks = text.count(MODE_BLOCK)
    if (remote_markers > 1 or mode_markers > 1 or remote_blocks > 1
            or legacy_remote_blocks > 1 or (remote_blocks and legacy_remote_blocks)
            or mode_blocks > 1):
        raise PatchError("duplicate ASL mode-switch marker or routing block")
    if (remote_markers and not (remote_blocks or legacy_remote_blocks)) or (mode_markers and not mode_blocks):
        raise PatchError("incomplete or modified ASL mode-switch repair")

    if legacy_remote_blocks:
        text = _replace_once(text, LEGACY_REMOTE_BLOCK, REMOTE_BLOCK, "legacy live-port routing block")
        if not remote_markers:
            text = _replace_once(text, REMOTE_BLOCK, f"{REMOTE_MARKER}\n{REMOTE_BLOCK}", "legacy routing block")
    elif not remote_blocks:
        text = _replace_once(
            text,
            REMOTE_ANCHOR,
            f"    else\n{REMOTE_MARKER}\n{REMOTE_BLOCK}\nPYTHON_ARG=\"$1\" python3 - <<END",
            "remoteControlCommand insertion point",
        )
    elif not remote_markers:
        text = _replace_once(text, REMOTE_BLOCK, f"{REMOTE_MARKER}\n{REMOTE_BLOCK}", "legacy routing block")

    if not mode_blocks:
        text = _replace_once(
            text,
            MODE_ANCHOR,
            f"{MODE_MARKER}\n{MODE_BLOCK}\n{MODE_ANCHOR}",
            "setMode insertion point",
        )
    elif not mode_markers:
        text = _replace_once(text, MODE_BLOCK, f"{MODE_MARKER}\n{MODE_BLOCK}", "legacy mode-routing block")

    if (text.count(REMOTE_MARKER) != 1 or text.count(REMOTE_BLOCK) != 1
            or LEGACY_REMOTE_BLOCK in text):
        raise PatchError("remote command routing repair did not validate")
    if text.count(MODE_MARKER) != 1 or text.count(MODE_BLOCK) != 1:
        raise PatchError("ASL mode transition repair did not validate")
    return text


def patch_file(path: Path) -> None:
    with path.open("r", encoding="utf-8", newline="") as source:
        original = source.read()
    newline = "\r\n" if "\r\n" in original else "\n"
    if "\r\n" in original and "\n" in original.replace("\r\n", ""):
        raise PatchError("mixed line endings are unsupported")
    normalized = original.replace("\r\n", "\n")
    patched = patch_text(normalized)
    if newline == "\r\n":
        patched = patched.replace("\n", "\r\n")
    path.write_text(patched, encoding="utf-8", newline="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dvswitch", required=True, type=Path, help="temporary or installed dvswitch.sh file")
    args = parser.parse_args()
    try:
        patch_file(args.dvswitch)
    except (OSError, UnicodeError, PatchError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
