#!/usr/bin/env python3
# Version: 1.1.1
# Created: 2026-11-10T19:00:00-05:00 by KE2HNI
# Updated: 2026-11-10T15:20:00-05:00 by KE2HNI — verify independent M17 installation paths.
# Updated: 2026-11-13T20:15:25-05:00 by KE2HNI — verify all affected upstream headers receive the fixed-width integer include.

"""Check the USRP2M17 installer config and reversible Asterisk node edits."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "dvswitch-m17-bridge.py"
SPEC = importlib.util.spec_from_file_location("dvswitch_m17_bridge", SOURCE)
assert SPEC is not None and SPEC.loader is not None
BRIDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRIDGE)


def main() -> None:
    sample = (
        "[nodes]\n446901 = radio@127.0.0.1:4571/446901,NONE\n"
        "[446901](node-main)\nrxchannel = SimpleUSB/446901\n"
        "[1970](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n"
    )
    private = BRIDGE.discover_private_nodes(sample)
    assert private == {"1970": "USRP/127.0.0.1:34001:32001"}
    assert BRIDGE.validate_node("1972", "M17 node") == "1972"
    assert BRIDGE.validate_port("34008", "USRP port") == 34008
    assert BRIDGE.node_channel_ports("USRP/127.0.0.1:34008:32008") == {34008, 32008}
    assert BRIDGE.node_channel_ports("SimpleUSB/446901") == set()

    with tempfile.TemporaryDirectory() as directory:
        # Upgrade must clean its prior untracked build binary before the cleanliness check.
        root = Path(directory) / "opt/dvswitch-m17"
        source = root / "MMDVM_CM"
        project = source / "USRP2M17"
        project.mkdir(parents=True)
        (project / "Makefile").write_text("all:\n", encoding="utf-8")
        (project / "Conf.h").write_text("#include <vector>\nuint16_t port;\n", encoding="utf-8")
        (project / "ModeConv.h").write_text(
            '#include "codec2/codec2.h"\nuint8_t tag;\n', encoding="utf-8")
        (project / "USRP2M17.cpp").write_text(
            'LogMessage("M17 received end of voice transmission, %.1f seconds", float(m_m17Frames) / 25.0F);\n'
            'LogMessage("USRP received end of voice transmission, %.1f seconds", float(m_usrpFrames) / 50.0F);\n',
            encoding="utf-8")
        binary = project / "USRP2M17"
        binary.write_text("old installer build\n", encoding="utf-8")
        old_source_root, old_install_root, old_run = (
            BRIDGE.SOURCE_ROOT, BRIDGE.INSTALL_ROOT, BRIDGE.run)
        calls = []
        patched_headers = []

        def fake_git_run(command, **kwargs):
            calls.append(command)
            if command[3:5] == ["remote", "get-url"]:
                return subprocess.CompletedProcess(command, 0, BRIDGE.REPOSITORY, "")
            if command[3:5] == ["status", "--porcelain"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[0] == "make" and len(command) > 1 and command[1] == "clean":
                binary.unlink(missing_ok=True)
            elif command[0] == "git" and "pull" in command:
                pass
            elif command[0] == "make":
                patched_headers.append({
                    name: (Path(kwargs["cwd"]) / name).read_text(encoding="utf-8")
                    for name in ("Conf.h", "ModeConv.h")})
                Path(kwargs["cwd"] / "USRP2M17").write_text("rebuilt executable\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        try:
            BRIDGE.SOURCE_ROOT, BRIDGE.INSTALL_ROOT = source, root
            BRIDGE.run = fake_git_run
            built = BRIDGE.ensure_source()
            assert built == b"rebuilt executable\n"
            assert not binary.exists(), "the clean upstream checkout must not retain the patched temporary build"
            assert any(call[:2] == ["make", "clean"] for call in calls)
            assert any("--untracked-files=all" in call for call in calls)
            assert patched_headers and all(
                "#include <cstdint>" in text for text in patched_headers[0].values())
            assert "#include <cstdint>" not in (project / "Conf.h").read_text(encoding="utf-8")
            assert "#include <cstdint>" not in (project / "ModeConv.h").read_text(encoding="utf-8")
            assert all(path.stat().st_mode & 0o777 == 0o755
                       for path in (root, source, project))
        finally:
            BRIDGE.SOURCE_ROOT, BRIDGE.INSTALL_ROOT, BRIDGE.run = (
                old_source_root, old_install_root, old_run)

    settings = {
        "callsign": "KE2HNI",
        "address": "107.191.121.105",
        "name": "M17-M17",
        "module": "C",
        "m17_local": 32011,
        "m17_remote": 17000,
        "m17_gain": "3",
        "asl_local": 32008,
        "usrp_local": 34008,
        "usrp_gain": "-6",
    }
    config = BRIDGE.make_config(settings)
    assert "Name=M17-M17 C\n" in config
    assert "DstPort=32008\nLocalPort=34008\n" in config
    assert "LocalPort=32011\nDstPort=17000\n" in config
    assert "FilePath=/var/log/usrp2m17\n" in config
    assert "ExecStart=/usr/local/bin/USRP2M17" in BRIDGE.service_text()

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "opt/dvswitch-m17"
        source = root / "MMDVM_CM"
        project = source / "USRP2M17"
        project.mkdir(parents=True, mode=0o700)
        # Simulate the manager's restrictive umask and confirm the service path is traversable.
        for path in (root, source, project):
            path.chmod(0o700)
        old_install_root, old_source_root = BRIDGE.INSTALL_ROOT, BRIDGE.SOURCE_ROOT
        try:
            BRIDGE.INSTALL_ROOT, BRIDGE.SOURCE_ROOT = root, source
            BRIDGE.ensure_service_directory_access()
            assert all((path.stat().st_mode & 0o777) == 0o755
                       for path in (root, source, project))
        finally:
            BRIDGE.INSTALL_ROOT, BRIDGE.SOURCE_ROOT = old_install_root, old_source_root

    with tempfile.TemporaryDirectory() as directory:
        temp_root = Path(directory)
        BRIDGE.CONFIG = temp_root / "USRP2M17.ini"
        BRIDGE.BINARY = temp_root / "usr-local-bin-USRP2M17"
        BRIDGE.STATE_FILE = temp_root / "install-state.json"
        BRIDGE.CONFIG.write_text(config, encoding="utf-8")
        BRIDGE.BINARY.write_text("existing executable\n", encoding="utf-8")
        assert BRIDGE.matching_imported_node(
            {"1970": "USRP/127.0.0.1:34001:32001",
             "1972": "USRP/127.0.0.1:34008:32008"}) == "1972"

        # Option 7 reserves the M17 node, while option 8 must update its rxchannel only.
        support_config = temp_root / "dvswitch-m17-support.conf"
        support_config.write_text(
            "M17_PRIVATE_NODE=1974\nDVSWITCH_PRIVATE_NODE=1973\n", encoding="utf-8")
        old_support_config = BRIDGE.SUPPORT_CONFIG
        BRIDGE.SUPPORT_CONFIG = support_config
        assert BRIDGE.configured_m17_node() == "1974"
        adopted_rpt = temp_root / "adopted-rpt.conf"
        adopted_rpt.write_text(
            "[nodes]\n1973 = radio@127.0.0.1:4571/1973,NONE\n"
            "1974 = radio@127.0.0.1:4571/1974,NONE\n"
            "[1973](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n"
            "[1974](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n"
            "idrecording = |iKE2HNI\n", encoding="utf-8")
        original_channel = []
        added_node, added_map = BRIDGE.edit_rpt_conf(
            adopted_rpt, "1974", 34008, 32008,
            adopt_existing_node=("1974" == BRIDGE.configured_m17_node()),
            original_channel_out=original_channel)
        assert not added_node and not added_map
        adopted_text = adopted_rpt.read_text(encoding="utf-8")
        assert "[1973](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001" in adopted_text
        assert "[1974](node-main)\nrxchannel = USRP/127.0.0.1:34008:32008\nidrecording = |iKE2HNI" in adopted_text
        BRIDGE.remove_managed_rpt(adopted_rpt, {
            "rpt_added_node": False, "rpt_added_map": False,
            "rpt_original_channel": original_channel[0],
            "settings": {"m17_node": "1974", "usrp_local": 34008, "asl_local": 32008}})
        restored_text = adopted_rpt.read_text(encoding="utf-8")
        assert "[1974](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\nidrecording = |iKE2HNI" in restored_text
        BRIDGE.SUPPORT_CONFIG = old_support_config

        rpt = Path(directory) / "rpt.conf"
        rpt.write_text(sample, encoding="utf-8")
        added_node, added_map = BRIDGE.edit_rpt_conf(rpt, "1972", 34008, 32008)
        installed = rpt.read_text(encoding="utf-8")
        assert added_node and added_map
        assert "[1972](node-main)\nrxchannel = USRP/127.0.0.1:34008:32008\n" in installed
        assert "1972 = radio@127.0.0.1:4571/1972,NONE ; DVSwitch-M17-Bridge v1" in installed
        state = {"rpt_added_node": added_node, "rpt_added_map": added_map}
        # Upgrade the managed port pair without taking ownership of unrelated node settings.
        upgraded_node, upgraded_map = BRIDGE.edit_rpt_conf(
            rpt, "1972", 34009, 32009, allow_managed_block=True)
        assert upgraded_node and not upgraded_map
        assert "rxchannel = USRP/127.0.0.1:34009:32009" in rpt.read_text(encoding="utf-8")
        assert "1972 = radio@127.0.0.1:4571/1972,NONE ; DVSwitch-M17-Bridge v1" in rpt.read_text(encoding="utf-8")
        rpt.write_text(installed + "; preserve this later user edit\n", encoding="utf-8")
        BRIDGE.remove_managed_rpt(rpt, state)
        restored = rpt.read_text(encoding="utf-8")
        assert "[1972](node-main)" not in restored
        assert "1972 = radio@127.0.0.1:4571/1972,NONE" not in restored
        assert "; preserve this later user edit" in restored
        assert "[1970](node-main)" in restored

    with tempfile.TemporaryDirectory() as directory:
        # Simulate fresh install, upgrade, and uninstall with isolated paths and mocked services.
        root = Path(directory)
        paths = {
            "INSTALL_ROOT": root / "opt/dvswitch-m17",
            "SOURCE_ROOT": root / "opt/dvswitch-m17/MMDVM_CM",
            "CONFIG": root / "etc/USRP2M17.ini",
            "BINARY": root / "usr/local/bin/USRP2M17",
            "SERVICE": root / "etc/systemd/system/usrp2m17.service",
            "LOG_DIR": root / "var/log/usrp2m17",
            "STATE_ROOT": root / "var/lib/dvswitch-m17-bridge",
            "STATE_FILE": root / "var/lib/dvswitch-m17-bridge/install-state.json",
            "BACKUP_ROOT": root / "var/backups/usrp2m17",
            "RPT_CONF": root / "etc/asterisk/rpt.conf",
            "SUPPORT_INSTALLER": root / "repo/dvswitch-m17-support.sh",
        }
        prior = {key: getattr(BRIDGE, key) for key in paths}
        for key, value in paths.items():
            setattr(BRIDGE, key, value)
        paths["RPT_CONF"].parent.mkdir(parents=True)
        paths["RPT_CONF"].write_text(
            "[nodes]\n446901 = radio@127.0.0.1:4571/446901,NONE\n"
            "[446901](node-main)\nrxchannel = SimpleUSB/446901\n"
            "[1970](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n",
            encoding="utf-8")
        paths["SUPPORT_INSTALLER"].parent.mkdir(parents=True)
        paths["SUPPORT_INSTALLER"].write_text("#!/bin/sh\n", encoding="utf-8")
        paths["SUPPORT_INSTALLER"].chmod(0o755)
        restored_switch = []
        service_started = False

        def fake_run(command, **kwargs):
            nonlocal service_started
            if command[:2] == ["pgrep", "-x"]:
                return subprocess.CompletedProcess(command, 1, "", "")
            if command[:2] == ["systemctl", "enable"]:
                service_started = True
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:2] == ["systemctl", "stop"] or command[:3] == ["systemctl", "disable", "--now"]:
                service_started = False
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:3] == ["bash", str(paths["SUPPORT_INSTALLER"]), "--restore"]:
                restored_switch.append(command[-1])
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:3] == ["bash", str(paths["SUPPORT_INSTALLER"]), "--install"]:
                return subprocess.CompletedProcess(
                    command, 0, "PASS: commands installed\nBackup: /var/backups/m17/install-first\n", "")
            if command[:2] == ["systemctl", "is-active"]:
                return subprocess.CompletedProcess(command, 0 if service_started else 1,
                                                   "active\n" if service_started else "inactive\n", "")
            if command[:2] == ["systemctl", "is-enabled"]:
                return subprocess.CompletedProcess(command, 1, "inactive\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        def fake_source():
            project = paths["SOURCE_ROOT"] / "USRP2M17"
            project.mkdir(parents=True, exist_ok=True)
            paths["BINARY"].parent.mkdir(parents=True, exist_ok=True)
            paths["SERVICE"].parent.mkdir(parents=True, exist_ok=True)
            return b"fake executable\n"

        old_run = BRIDGE.run
        old_source = BRIDGE.ensure_source
        old_check = BRIDGE.check_only
        old_platform = BRIDGE.check_platform
        old_private = BRIDGE.private_node_selection
        old_reflector = BRIDGE.select_reflector
        old_ports = BRIDGE.udp_port_free
        old_require_root = BRIDGE.require_root
        old_lookup = BRIDGE.pwd.getpwnam
        try:
            BRIDGE.run = fake_run
            BRIDGE.ensure_source = fake_source
            BRIDGE.check_only = lambda: None
            BRIDGE.check_platform = lambda **_kwargs: []
            BRIDGE.private_node_selection = lambda _private: "1970"
            BRIDGE.select_reflector = lambda _existing: ("M17-M17", "127.0.0.1", 17000, "C")
            BRIDGE.udp_port_free = lambda _port: True
            BRIDGE.require_root = lambda: None
            BRIDGE.pwd.getpwnam = lambda _name: SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
            answers = ["1972", "KE2HNI", "", "", "", "", "", "y", "n",
                       "", "", "", "", "", "", "", "y", "n", "y", "y"]
            with patch("builtins.input", side_effect=answers):
                BRIDGE.install()
                original_backup = __import__("json").loads(paths["STATE_FILE"].read_text())["backup"]
                BRIDGE.install()
                upgraded = __import__("json").loads(paths["STATE_FILE"].read_text())
                assert upgraded["backup"] == original_backup
                assert "rxchannel = USRP/127.0.0.1:34008:32008" in paths["RPT_CONF"].read_text()
                BRIDGE.uninstall()
            assert not paths["STATE_FILE"].exists()
            assert not paths["CONFIG"].exists()
            assert not paths["BINARY"].exists()
            assert not paths["SERVICE"].exists()
            assert "[1972](node-main)" not in paths["RPT_CONF"].read_text()
            assert "[1970](node-main)" in paths["RPT_CONF"].read_text()
            assert restored_switch == ["install-first"]
        finally:
            BRIDGE.run = old_run
            BRIDGE.ensure_source = old_source
            BRIDGE.check_only = old_check
            BRIDGE.check_platform = old_platform
            BRIDGE.private_node_selection = old_private
            BRIDGE.select_reflector = old_reflector
            BRIDGE.udp_port_free = old_ports
            BRIDGE.require_root = old_require_root
            BRIDGE.pwd.getpwnam = old_lookup
            for key, value in prior.items():
                setattr(BRIDGE, key, value)

    print("PASS: USRP2M17 configuration rendering, private-node detection, marked install, and selective cleanup")


if __name__ == "__main__":
    main()
