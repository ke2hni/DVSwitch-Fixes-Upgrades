#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Verify the optional Mods history hook does not couple the repositories."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = (ROOT / "dvswitch-mode-buttons").read_text()
INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text()

assert 'DMR_HISTORY_WRITER=/usr/local/sbin/dvswitch-mods-record-dmr-network' in HELPER
assert 'if [[ -x "$DMR_HISTORY_WRITER" ]]; then' in HELPER
assert '"$DMR_HISTORY_WRITER" --record "$network" "$(date +%s%3N)"' in HELPER
assert HELPER.index('mv -f "$tmp" "$INI"') < HELPER.index('"$DMR_HISTORY_WRITER" --record')
assert HELPER.index('"$DMR_HISTORY_WRITER" --record') < HELPER.index('systemctl restart analog_bridge mmdvm_bridge')
assert 'dvswitch-mods-record-dmr-network' not in INSTALLER, "Buttons installer must not require or install Mods recorder"
assert 'bash -n ./dvswitch-mode-buttons' in INSTALLER, "installer must syntax-check the helper source that contains the optional hook"
print("PASS: optional Mods history hook records the network before bridge restart; Buttons installer remains independent")
