#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Ensure STFU target saves cannot replace the saved BM/TGIF card state."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = (ROOT / "dvswitch-mode-buttons").read_text()
TARGET_HELPER = (ROOT / "dvswitch-mode-targets").read_text()
INSTALLER = (ROOT / "dvswitch-mode-buttons.sh").read_text()
state_block = HELPER.split('if [[ "$mode" == BM || "$mode" == TGIF ]]; then', 1)[1].split("\nfi", 1)[0]
assert '"$DMR_NETWORK_FILE"' in state_block
assert '"$DMR_CARD_MODE_FILE"' in state_block
assert 'elif [[ "$mode" == STFU' not in HELPER
assert 'BM > "$DMR_NETWORK_FILE"' not in HELPER
assert 'STFU > "$DMR_CARD_MODE_FILE"' not in HELPER
save_dmr_state = TARGET_HELPER.split('if [[ "$1" == save &&', 1)[1].split('then', 1)[0]
assert '"$mode" == BM || "$mode" == TGIF' in save_dmr_state
assert 'STFU' not in save_dmr_state
assert 'current_mode_target=' in INSTALLER and 'saved_mode_target=' in INSTALLER
assert 'existing_dmr_target" == "$current_mode_target"' in INSTALLER
assert 'restored saved DMR card target' in INSTALLER

# Run the installer’s exact state-migration block against temporary state.
start = INSTALLER.index("saved_dmr_card_mode=''\n")
end = INSTALLER.index("\nif [[ ! -e /var/lib/dvswitch-mode-buttons/last-dmr-talkgroup ]]; then", start)
migration = INSTALLER[start:end]

def run_recovery(existing: str, card_mode: str = "BM") -> str:
    with tempfile.TemporaryDirectory(prefix="dvswitch-dmr-state-test-") as directory:
        root = Path(directory)
        (root / "current-mode").write_text("STFU\n")
        (root / "last-dmr-network").write_text("BM\n")
        (root / "last-dmr-card-mode").write_text(card_mode + "\n")
        (root / "last-dmr-talkgroup").write_text(existing + "\n")
        target_helper = root / "targets"
        target_helper.write_text("#!/bin/bash\ncase \"$2\" in STFU) echo 3100;; BM) echo 91;; esac\n")
        target_helper.chmod(0o755)
        snippet = migration
        for name in ("current-mode", "last-dmr-network", "last-dmr-card-mode", "last-dmr-talkgroup"):
            snippet = snippet.replace(
                f"/var/lib/dvswitch-mode-buttons/{name}", str(root / name)
            )
        snippet = snippet.replace("/usr/local/sbin/dvswitch-mode-targets", str(target_helper))
        result = subprocess.run(
            ["bash", "-c", snippet + "\nprintf '%s %s %s\\n' \"$repair_saved_dmr_target\" \"$repair_saved_dmr_card_mode\" \"$saved_dmr_card_mode\"\n"],
            env=os.environ.copy(), check=True, text=True, capture_output=True,
        )
        return result.stdout.strip()

assert run_recovery("3100") == "1 0 BM", "matching STFU target was not repaired to saved BM target"
assert run_recovery("91") == "0 0 BM", "valid DMR card state was unnecessarily changed"
assert run_recovery("3100", "STFU") == "1 1 BM", "legacy STFU card-mode state was not restored to BM"
print("PASS: STFU preserves BM/TGIF card state and upgrade repairs recognized stale target and mode copies")
