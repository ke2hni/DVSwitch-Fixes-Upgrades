#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Verify BM/TGIF clicks skip copies and restarts only when both INIs match."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "dvswitch-mode-buttons").read_text(encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "etc/dvswitch-mode-buttons/dmr-presets").mkdir(parents=True)
        (root / "opt/MMDVM_Bridge").mkdir(parents=True)
        (root / "opt/Analog_Bridge").mkdir(parents=True)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        log = root / "calls.log"
        mode_cmd = root / "opt/MMDVM_Bridge/dvswitch.sh"
        mode_cmd.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = mode ]; then printf 'mode %s pending=' \"$*\" >> \"$CALL_LOG\"; "
            "cat \"$PENDING_STATE\" >> \"$CALL_LOG\" 2>/dev/null || printf 'MISSING\\n' >> \"$CALL_LOG\"; "
            "else printf 'mode %s\\n' \"$*\" >> \"$CALL_LOG\"; fi\n",
            encoding="utf-8",
        )
        mode_cmd.chmod(0o755)
        systemctl = bin_dir / "systemctl"
        systemctl.write_text("#!/bin/sh\nprintf 'systemctl %s\\n' \"$*\" >> \"$CALL_LOG\"\n", encoding="utf-8")
        systemctl.chmod(0o755)
        target_helper = root / "bin/dvswitch-mode-targets"
        target_helper.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = get ]; then cat \"$TARGET_STATE\" 2>/dev/null || true; "
            "else printf '%s\\n' \"$3\" > \"$TARGET_STATE\"; fi\n",
            encoding="utf-8",
        )
        target_helper.chmod(0o755)

        helper = root / "dvswitch-mode-buttons"
        helper.write_text(SOURCE.replace(
            "MODE_CMD=/opt/MMDVM_Bridge/dvswitch.sh", f"MODE_CMD={mode_cmd}"
        ).replace(
            "STATE_DIR=/var/lib/dvswitch-mode-buttons", f"STATE_DIR={root}/state"
        ).replace(
            "PRESET_DIR=/etc/dvswitch-mode-buttons/dmr-presets",
            f"PRESET_DIR={root}/etc/dvswitch-mode-buttons/dmr-presets",
        ).replace(
            "INI=/opt/MMDVM_Bridge/MMDVM_Bridge.ini", f"INI={root}/opt/MMDVM_Bridge/MMDVM_Bridge.ini"
        ).replace(
            "ANALOG_INI=/opt/Analog_Bridge/Analog_Bridge.ini", f"ANALOG_INI={root}/opt/Analog_Bridge/Analog_Bridge.ini"
        ).replace(
            "DMR_HISTORY_WRITER=/usr/local/sbin/dvswitch-mods-record-dmr-network",
            f"DMR_HISTORY_WRITER={root}/missing-history-writer",
        ).replace(
            "TARGET_HELPER=/usr/local/sbin/dvswitch-mode-targets",
            f"TARGET_HELPER={target_helper}",
        ), encoding="utf-8")
        helper.chmod(0o755)

        env = os.environ.copy()
        target_state = root / "target-state"
        env.update(
            PATH=f"{bin_dir}:{env['PATH']}", CALL_LOG=str(log), TARGET_STATE=str(target_state),
            PENDING_STATE=str(root / "state/dmr-tune-pending"),
        )
        preset_dir = root / "etc/dvswitch-mode-buttons/dmr-presets"
        mmdvm = "[DMR Network]\nAddress=tgif.network\nPort=62030\nPassword=secret\n"
        analog = "[AMBE_AUDIO]\ntxTg=12345\n"
        live_mmdvm = root / "opt/MMDVM_Bridge/MMDVM_Bridge.ini"
        live_analog = root / "opt/Analog_Bridge/Analog_Bridge.ini"
        (preset_dir / "MMDVM_Bridge.TGIF.ini").write_text(mmdvm, encoding="utf-8")
        (preset_dir / "Analog_Bridge.TGIF.ini").write_text(analog, encoding="utf-8")

        # Same network and matching companion INI: mode only, no copy or restart.
        live_mmdvm.write_text(mmdvm, encoding="utf-8")
        live_analog.write_text(analog, encoding="utf-8")
        result = subprocess.run([str(helper), "TGIF"], env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        calls = log.read_text(encoding="utf-8").splitlines()
        assert len(calls) == 3 and calls[0].startswith("mode mode DMR pending=TGIF 12345 "), calls
        assert calls[1:] == [
            "systemctl is-active --quiet analog_bridge mmdvm_bridge",
            "mode tune 12345",
        ], calls
        assert "skipped preset copies and service restart" in result.stdout
        assert target_state.read_text(encoding="utf-8").strip() == "12345"

        # A subsequent non-DMR selection clears the short-lived DMR marker.
        result = subprocess.run([str(helper), "P25"], env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert not (root / "state/dmr-tune-pending").exists()

        # With a saved TGIF target, preserve it instead of using the preset default.
        log.write_text("", encoding="utf-8")
        target_state.write_text("98765\n", encoding="utf-8")
        result = subprocess.run([str(helper), "TGIF"], env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert "mode tune 98765" in log.read_text(encoding="utf-8").splitlines()

        # A differing Analog_Bridge file still takes the established full path.
        log.write_text("", encoding="utf-8")
        live_analog.write_text("[AMBE_AUDIO]\ntxTg=99999\n", encoding="utf-8")
        result = subprocess.run([str(helper), "TGIF"], env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        calls = log.read_text(encoding="utf-8").splitlines()
        assert "systemctl restart analog_bridge mmdvm_bridge" in calls, calls
        assert live_analog.read_text(encoding="utf-8") == analog

    print("PASS: matching BM/TGIF presets skip recopy/restart; mismatches use the full switch path")


if __name__ == "__main__":
    main()
