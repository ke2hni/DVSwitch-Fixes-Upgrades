#!/usr/bin/env python3
# Version: 1.0.0
# SPDX-License-Identifier: MIT

"""Test STFU logrotate validation, install, idempotency, and uninstall."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "mod-stfu-logrotate-restart.sh"
ORIGINAL = (
    b"/var/log/dvswitch/STFU.log {\n"
    b"        rotate 7\n"
    b"        daily\n"
    b"        compress\n"
    b"        size 100k\n"
    b"        nocreate\n"
    b"        missingok\n"
    b"        postrotate\n"
    b"                systemctl reload stfu\n"
    b"        endscript\n"
    b"}\n"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def invoke(target: Path, backup_root: Path, fake_bin: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "DVS_STFU_LOGROTATE_TARGET": str(target),
            "DVS_STFU_LOGROTATE_BACKUP_ROOT": str(backup_root),
            "PATH": str(fake_bin) + os.pathsep + env.get("PATH", ""),
        }
    )
    return subprocess.run(
        ["/bin/bash", str(INSTALLER), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo: sudo env PYTHONDONTWRITEBYTECODE=1 python3 tests/test-stfu-logrotate-restart.py")

    with tempfile.TemporaryDirectory(prefix="test-stfu-logrotate-") as raw:
        root = Path(raw)
        target = root / "STFU"
        backup_root = root / "backups" / "stfu-logrotate-restart"
        fake_bin = root / "bin"
        fake_bin.mkdir()
        fake_logrotate = fake_bin / "logrotate"
        fake_logrotate.write_text("#!/bin/sh\nexit 0\n")
        fake_logrotate.chmod(0o755)
        target.write_bytes(ORIGINAL)
        target.chmod(0o640)

        checked = invoke(target, backup_root, fake_bin, "--check")
        require(checked.returncode == 0 and "READY:" in checked.stdout, "check did not report ready")
        require(target.read_bytes() == ORIGINAL and not backup_root.exists(), "check changed files")

        installed = invoke(target, backup_root, fake_bin, "--install")
        expected = ORIGINAL.replace(b"systemctl reload stfu", b"systemctl restart stfu")
        require(installed.returncode == 0, f"install failed: {installed.stderr}{installed.stdout}")
        require(target.read_bytes() == expected, "install changed more than the STFU command")
        require(target.stat().st_mode & 0o777 == 0o640, "install did not preserve mode")
        backups = sorted(backup_root.glob("install-*"))
        require(len(backups) == 1 and (backups[0] / "STFU").read_bytes() == ORIGINAL,
                "install did not create the protected original backup")

        checked_again = invoke(target, backup_root, fake_bin, "--check")
        require(checked_again.returncode == 0 and "ALREADY MODIFIED:" in checked_again.stdout,
                "check rejected installed state")
        repeated = invoke(target, backup_root, fake_bin, "--install")
        require(repeated.returncode == 0 and len(list(backup_root.glob("install-*"))) == 1,
                "repeat install was not idempotent")

        note = b"# unrelated user note\n"
        target.write_bytes(target.read_bytes() + note)
        removed = invoke(target, backup_root, fake_bin, "--uninstall", backups[0].name)
        require(removed.returncode == 0, f"uninstall failed: {removed.stderr}{removed.stdout}")
        require(target.read_bytes() == ORIGINAL + note, "uninstall failed to preserve unrelated edits")
        rejected = invoke(target, backup_root, fake_bin, "--uninstall", backups[0].name)
        require(rejected.returncode != 0 and target.read_bytes() == ORIGINAL + note,
                "repeat uninstall did not fail safely")

        malformed = root / "malformed-STFU"
        malformed.write_bytes(ORIGINAL.replace(b"systemctl reload stfu", b"systemctl restart other"))
        bad = invoke(malformed, root / "bad-backups", fake_bin, "--check")
        require(bad.returncode != 0, "check accepted an unsupported command")

    print("PASS: STFU logrotate validation, install, idempotency, and uninstall")


if __name__ == "__main__":
    main()
