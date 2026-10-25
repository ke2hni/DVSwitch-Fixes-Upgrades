#!/usr/bin/env python3
"""Check that the private STFU target is safely exposed to the dashboard."""

from pathlib import Path
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (ROOT / "dvswitch-mode-targets").read_text(encoding="utf-8")
INSTALLER = (ROOT / "install-mode-target-persistence.sh").read_text(encoding="utf-8")

assert "if mode == 'STFU':" in TARGETS
assert "prefix='.stfu-target.'" in TARGETS
assert "os.chmod(public_tmp, 0o644)" in TARGETS
assert "os.replace(public_tmp, os.path.join(os.path.dirname(path), 'stfu-target'))" in TARGETS
assert "os.chmod(tmp,0o600)" in TARGETS, "canonical per-mode JSON must remain private"
assert '"$TARGET_HELPER" get STFU' in INSTALLER
assert '"$STATE_DIR/stfu-target"' in INSTALLER
assert 'chmod 644 "$stfu_tmp"' in INSTALLER

# Reproduce an STFU target save followed by a DMR target save. Both stores must
# remain mode-specific, and Apache's snapshot must contain a real newline.
with tempfile.TemporaryDirectory(prefix="dvswitch-stfu-target-test-") as directory:
    root = Path(directory)
    state_dir = root / "state"
    helper = root / "dvswitch-mode-targets"
    helper_source = TARGETS.replace(
        "STATE_DIR=/var/lib/dvswitch-mode-buttons", f"STATE_DIR={state_dir}"
    ).replace("[[ $EUID -eq 0 ]] || die 'run with sudo'", ":")
    helper.write_text(helper_source, encoding="utf-8")
    helper.chmod(0o755)
    mock_bin = root / "bin"
    mock_bin.mkdir()
    mock_chown = mock_bin / "chown"
    mock_chown.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    mock_chown.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(mock_bin) + os.pathsep + env["PATH"]
    subprocess.run(["bash", str(helper), "save", "STFU", "3166"], env=env, check=True, capture_output=True, text=True)
    subprocess.run(["bash", str(helper), "save", "TGIF", "51598"], env=env, check=True, capture_output=True, text=True)
    state = json.loads((state_dir / "mode-targets.json").read_text(encoding="utf-8"))
    assert state["STFU"]["target"] == "3166", "DMR target save changed the saved STFU target"
    assert state["TGIF"]["target"] == "51598", "DMR target was not saved independently"
    assert (state_dir / "stfu-target").read_text(encoding="utf-8") == "3166\n", "STFU snapshot is malformed or changed by DMR save"

print("PASS: STFU target snapshot is valid and remains unchanged by DMR target saves")
