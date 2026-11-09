#!/usr/bin/env python3
# Version: 1.0.4
# Created: 2026-11-09T00:53:07-05:00 by KE2HNI

"""Exercise M17 support installer check, fresh, upgrade, resume, restore, and collision paths in a temporary tree."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dvswitch-m17-support.sh"


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run this test as root because the installer requires root privileges.")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project = root / "project"
        project.mkdir()
        shutil.copy2(ROOT / "m17", project / "m17")
        shutil.copy2(ROOT / "dvs-dvswitch", project / "dvs-dvswitch")
        target = project / "installer.sh"
        source = SOURCE.read_text(encoding="utf-8")

        replacements = {
            "readonly CONFIG=/etc/dvswitch-m17-support.conf": f"readonly CONFIG={root}/etc/dvswitch-m17-support.conf\nreadonly CONFIG_DIR={root}/etc",
            "readonly TARGET_DIR=/usr/local/lib/dvswitch-m17-support": f"readonly TARGET_DIR={root}/usr/local/lib/dvswitch-m17-support",
            "readonly M17_LINK=/usr/local/bin/m17": f"readonly M17_LINK={root}/usr/local/bin/m17",
            "readonly DVS_LINK=/usr/local/bin/dvs-dvswitch": f"readonly DVS_LINK={root}/usr/local/bin/dvs-dvswitch",
            "readonly LINK_HELPER=/usr/local/sbin/dvswitch-asl3-node-link": f"readonly LINK_HELPER={root}/usr/local/sbin/dvswitch-asl3-node-link",
            "readonly BACKUP_ROOT=/var/backups/dvswitch-mods/m17-private-node-switch": f"readonly BACKUP_ROOT={root}/var/backups/m17",
            "install -d -o root -g root -m 0755 \"$TARGET_DIR\" /usr/local/bin /etc": "install -d -o root -g root -m 0755 \"$TARGET_DIR\" \"$(dirname \"$M17_LINK\")\" \"$CONFIG_DIR\"",
            "mktemp /etc/.dvswitch-m17-support.XXXXXX": "mktemp \"$CONFIG_DIR/.dvswitch-m17-support.XXXXXX\"",
        }
        for old, new in replacements.items():
            if old not in source:
                raise AssertionError(f"installer test path anchor missing: {old}")
            source = source.replace(old, new)
        target.write_text(source, encoding="utf-8")
        target.chmod(0o755)

        helper = root / "usr/local/sbin/dvswitch-asl3-node-link"
        helper.parent.mkdir(parents=True)
        helper.write_text("#!/bin/sh\n# SWITCH_PRIVATE SWITCH_DVSWITCH\nexit 0\n", encoding="utf-8")
        helper.chmod(0o755)

        def run(action: str, *arguments: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run([str(target), action, *arguments], capture_output=True, text=True, check=False)

        check = run("--check")
        assert check.returncode == 0, check.stderr
        assert not (root / "etc/dvswitch-m17-support.conf").exists()
        assert not (root / "var/backups/m17").exists()

        fresh = run("--install")
        assert fresh.returncode == 0, fresh.stderr
        assert "M17 node: 1972" in fresh.stdout
        config = root / "etc/dvswitch-m17-support.conf"
        assert "M17_PRIVATE_NODE=1972" in config.read_text(encoding="utf-8")
        m17_link = root / "usr/local/bin/m17"
        dvs_link = root / "usr/local/bin/dvs-dvswitch"
        assert m17_link.is_symlink() and m17_link.resolve() == (root / "usr/local/lib/dvswitch-m17-support/m17")
        assert dvs_link.is_symlink() and dvs_link.resolve() == (root / "usr/local/lib/dvswitch-m17-support/dvs-dvswitch")

        fake_sudo = root / "fake-sudo"
        fake_sudo.write_text("#!/bin/sh\ncat\n", encoding="utf-8")
        fake_sudo.chmod(0o755)
        m17_wrapper = root / "m17-wrapper"
        m17_source = (ROOT / "m17").read_text(encoding="utf-8")
        m17_source = m17_source.replace("readonly CONFIG=/etc/dvswitch-m17-support.conf", f"readonly CONFIG={config}")
        m17_source = m17_source.replace("readonly LINK_HELPER=/usr/local/sbin/dvswitch-asl3-node-link", f"readonly LINK_HELPER={helper}")
        m17_source = m17_source.replace("readonly SUDO=/usr/bin/sudo", f"readonly SUDO={fake_sudo}")
        m17_wrapper.write_text(m17_source, encoding="utf-8")
        m17_wrapper.chmod(0o755)
        assert subprocess.run([str(m17_wrapper)], capture_output=True, text=True, check=True).stdout == "SWITCH_PRIVATE\t1972\n"

        dvs_wrapper = root / "dvs-wrapper"
        dvs_source = (ROOT / "dvs-dvswitch").read_text(encoding="utf-8")
        dvs_source = dvs_source.replace("readonly LINK_HELPER=/usr/local/sbin/dvswitch-asl3-node-link", f"readonly LINK_HELPER={helper}")
        dvs_source = dvs_source.replace("readonly SUDO=/usr/bin/sudo", f"readonly SUDO={fake_sudo}")
        dvs_wrapper.write_text(dvs_source, encoding="utf-8")
        dvs_wrapper.chmod(0o755)
        assert subprocess.run([str(dvs_wrapper)], capture_output=True, text=True, check=True).stdout == "SWITCH_DVSWITCH\n"

        already = run("--install")
        assert already.returncode == 0 and "ALREADY INSTALLED" in already.stdout
        backup_root = root / "var/backups/m17"
        assert len(list(backup_root.glob("install-*"))) == 1

        source_command = project / "m17"
        source_command.write_text(source_command.read_text(encoding="utf-8").replace("Version: 1.0.0", "Version: 1.0.1"), encoding="utf-8")
        upgraded = run("--install")
        assert upgraded.returncode == 0 and "PASS: M17 and DVSwitch private-node commands installed" in upgraded.stdout
        assert "Version: 1.0.1" in (root / "usr/local/lib/dvswitch-m17-support/m17").read_text(encoding="utf-8")
        assert len(list(backup_root.glob("install-*"))) == 2

        dvs_link.unlink()
        resumed = run("--install")
        assert resumed.returncode == 0 and dvs_link.is_symlink()
        assert len(list(backup_root.glob("install-*"))) == 3

        first_backup = sorted(backup_root.glob("install-*"))[0].name
        restored = run("--restore", first_backup)
        assert restored.returncode == 0, restored.stderr
        assert not config.exists() and not m17_link.exists() and not dvs_link.exists()
        assert not (root / "usr/local/lib/dvswitch-m17-support/m17").exists()
        assert list(backup_root.glob("pre-restore-*")), "restore must preserve a recovery snapshot of the current files"

        conflict = root / "usr/local/bin/m17"
        # The full bridge installer passes the selected node without prompting twice.
        explicit = run("--install", "246810")
        assert explicit.returncode == 0, explicit.stderr
        assert "M17_PRIVATE_NODE=246810" in config.read_text(encoding="utf-8")
        if conflict.is_symlink() or conflict.exists():
            conflict.unlink()
        conflict.write_text("user command\n", encoding="utf-8")
        blocked = run("--check")
        assert blocked.returncode != 0 and "Refusing to replace an unrelated command" in blocked.stderr

    print("PASS: M17 installer check, fresh install, upgrade, already-installed, partial-install resume, restore, and collision guard")


if __name__ == "__main__":
    main()
