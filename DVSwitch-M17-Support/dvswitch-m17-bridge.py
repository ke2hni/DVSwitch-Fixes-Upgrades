#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Version: 1.1.1
# Created: 2026-11-10T19:00:00-05:00 by KE2HNI
# Updated: 2026-11-13T20:38:48-05:00 by KE2HNI — preserve valid existing local node maps and avoid disabling a unit before systemd has loaded it.
# Updated: 2026-11-10T15:20:00-05:00 by KE2HNI — own node selection and switching; remove ASL-mod prerequisite.
# Updated: 2026-11-09T23:19:00-05:00 by KE2HNI — include source callsigns in M17 activity logs.
# Interactive USRP2M17 installer for an ASL3 node; see INSTALL-USRP2M17.md.

"""Build and configure nostar/MMDVM_CM's USRP2M17 bridge on ASL3."""

from __future__ import annotations

import configparser
import datetime as dt
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

VERSION = "1.1.1"
REPOSITORY = "https://github.com/nostar/MMDVM_CM.git"
HOSTFILE = "https://m17-project.github.io/hostfiles/M17Hosts.txt"
INSTALL_ROOT = Path("/opt/dvswitch-m17")
SOURCE_ROOT = INSTALL_ROOT / "MMDVM_CM"
CONFIG = Path("/etc/USRP2M17.ini")
BINARY = Path("/usr/local/bin/USRP2M17")
SERVICE = Path("/etc/systemd/system/usrp2m17.service")
LOG_DIR = Path("/var/log/usrp2m17")
STATE_ROOT = Path("/var/lib/dvswitch-m17-bridge")
STATE_FILE = STATE_ROOT / "install-state.json"
BACKUP_ROOT = Path("/var/backups/dvswitch-mods/usrp2m17")
RPT_CONF = Path("/etc/asterisk/rpt.conf")
SUPPORT_CONFIG = Path("/etc/dvswitch-m17-support.conf")
SUPPORT_INSTALLER = Path(__file__).with_name("dvswitch-m17-support.sh")
BEGIN = "; BEGIN DVSwitch-M17-Bridge managed private node v1"
END = "; END DVSwitch-M17-Bridge managed private node v1"
NODE_MAP_MARKER = "; DVSwitch-M17-Bridge v1"


class SetupError(Exception):
    """A safe, user-facing setup error."""


def run(command: list[str], *, cwd: Path | None = None, check: bool = True,
        capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, check=False,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if check and result.returncode:
        details = (result.stderr or result.stdout or "").strip() if capture else ""
        raise SetupError(f"Command failed ({result.returncode}): {' '.join(command)}"
                         + (f"\n{details}" if details else ""))
    return result


def prompt(label: str, default: str | None = None, *, allow_empty: bool = False) -> str:
    shown = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{shown}: ").strip()
        if not value and default is not None:
            return default
        if value or allow_empty:
            return value
        print("Please enter a value.")


def ask_yes_no(label: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{label} [{suffix}]: ").strip().lower()
    return default if not value else value in {"y", "yes"}


def require_root() -> None:
    if os.geteuid() != 0:
        raise SetupError("Run this installer with sudo from the repository folder.")


def check_platform(*, allow_package_install: bool = False) -> list[str]:
    if not RPT_CONF.is_file():
        raise SetupError(f"ASL/Asterisk configuration not found: {RPT_CONF}")
    try:
        os_release = Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError as error:
        raise SetupError(f"Cannot read /etc/os-release: {error}") from error
    if not any(line in os_release for line in ("ID=debian", 'ID="debian"', "ID=raspbian")):
        raise SetupError("This installer supports Debian-based ASL3 systems.")
    missing = [name for name in ("git", "make", "g++", "asterisk", "systemctl")
               if shutil.which(name) is None]
    if "asterisk" in missing:
        raise SetupError("Asterisk is not installed or is not in PATH; install ASL3 before using this bridge installer.")
    if missing:
        print("Missing required tools: " + ", ".join(missing))
        if not allow_package_install:
            return missing
        if not ask_yes_no("Install git and build-essential with APT?", True):
            raise SetupError("Install the required packages, then rerun this installer.")
        run(["apt-get", "update"])
        run(["apt-get", "install", "-y", "git", "build-essential"])
        missing = [name for name in ("git", "make", "g++", "asterisk", "systemctl")
                   if shutil.which(name) is None]
        if missing:
            raise SetupError("Required tools are still missing: " + ", ".join(missing))
    return missing


def parse_ini(path: Path) -> dict[str, dict[str, str]]:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    if path.is_file():
        parser.read(path, encoding="utf-8")
    return {section: dict(parser.items(section)) for section in parser.sections()}


def parse_node_sections(data: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    node: str | None = None
    for line in data.splitlines():
        clean = line.split(";", 1)[0].split("#", 1)[0].strip()
        match = re.fullmatch(r"\[\s*(\d{1,8})\s*\]\s*(?:\([^)]*\))?", clean)
        if match:
            node = match.group(1)
            result.setdefault(node, [])
        elif clean.startswith("["):
            node = None
        elif node is not None:
            result[node].append(clean)
    return result


def node_channel(section: list[str]) -> str | None:
    values = [match.group(1).strip() for line in section
              if (match := re.match(r"rxchannel\s*=\s*(.*?)\s*$", line, re.I))]
    if len(values) > 1:
        raise SetupError("A node stanza contains more than one active rxchannel setting.")
    return values[0] if values else None


def node_channel_ports(channel: str) -> set[int]:
    """Return the loopback UDP ports already reserved by a USRP rxchannel."""
    match = re.fullmatch(r"usrp/[^:]+:(\d+):(\d+)", channel.strip(), re.I)
    return {int(match.group(1)), int(match.group(2))} if match else set()


def discover_private_nodes(data: str) -> dict[str, str]:
    private: dict[str, str] = {}
    for node, section in parse_node_sections(data).items():
        channel = node_channel(section)
        if channel and channel.lower().startswith("usrp/"):
            private[node] = channel
    return private


def validate_node(value: str, label: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]{0,7}", value):
        raise SetupError(f"{label} must be a non-zero numeric AllStar node number.")
    return value


def validate_port(value: str, label: str) -> int:
    if not re.fullmatch(r"[0-9]{1,5}", value) or not 1 <= int(value) <= 65535:
        raise SetupError(f"{label} must be a UDP port from 1 to 65535.")
    return int(value)


def udp_port_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def next_free_port(start: int, excluded: set[int]) -> int:
    for port in range(start, min(start + 1000, 65536)):
        if port not in excluded and udp_port_free(port):
            return port
    raise SetupError(f"No unused UDP port found starting at {start}.")


def fetch_hosts() -> list[tuple[str, str, int]]:
    request = urllib.request.Request(HOSTFILE, headers={"User-Agent": "DVSwitch-M17-Bridge-Installer"})
    with urllib.request.urlopen(request, timeout=15) as response:
        text = response.read().decode("utf-8", "replace")
    hosts: list[tuple[str, str, int]] = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[2].isdigit():
            try:
                socket.inet_aton(fields[1])
            except OSError:
                continue
            hosts.append((fields[0], fields[1], int(fields[2])))
    return hosts


def select_reflector(existing: dict[str, dict[str, str]]) -> tuple[str, str, int, str]:
    old = existing.get("M17 Network", {})
    old_name = old.get("name", "")
    old_address = old.get("address", "")
    old_port = old.get("dstport", "17000")
    try:
        hosts = fetch_hosts()
    except (OSError, ValueError) as error:
        print(f"Could not download the official M17 host list ({error}); enter its IPv4 details manually.")
        name = prompt("Reflector name", old_name or "M17-M17")
        address = prompt("Reflector IPv4 address", old_address or "107.191.121.105")
        port = validate_port(prompt("Reflector UDP port", old_port), "Reflector UDP port")
    else:
        print(f"Loaded {len(hosts)} entries from the official M17 host list.")
        term = prompt("Filter by reflector name", old_name.split()[0] if old_name else "M17-M17",
                      allow_empty=True).lower()
        matches = [host for host in hosts if term in host[0].lower()] if term else hosts
        matches = matches[:60]
        for index, (host_name, host_address, host_port) in enumerate(matches, 1):
            print(f"  {index:2d}) {host_name:<24} {host_address}:{host_port}")
        choice = prompt("Choose a listed number, or press Enter for a custom reflector", allow_empty=True)
        if choice and choice.isdigit() and 1 <= int(choice) <= len(matches):
            name, address, port = matches[int(choice) - 1]
            port = validate_port(str(port), "Reflector UDP port")
        else:
            if choice:
                raise SetupError("Choose one of the displayed entries or press Enter for custom details.")
            name = prompt("Reflector name", old_name or "M17-M17")
            address = prompt("Reflector IPv4 address", old_address or "107.191.121.105")
            port = validate_port(prompt("Reflector UDP port", old_port), "Reflector UDP port")
    try:
        socket.inet_aton(address)
    except OSError as error:
        raise SetupError("USRP2M17 requires a numeric IPv4 address from the M17 host list.") from error
    module = prompt("Reflector module letter", "C").upper()
    if not re.fullmatch(r"[A-Z0-9]", module):
        raise SetupError("Use one letter or digit for the M17 module.")
    return name, address, port, module


def private_node_selection(private: dict[str, str]) -> str:
    saved_path = SUPPORT_CONFIG
    saved_match = re.search(r"(?m)^DVSWITCH_PRIVATE_NODE=([0-9]+)$", saved_path.read_text(encoding="utf-8")) if saved_path.is_file() else None
    saved = saved_match.group(1) if saved_match else ""
    m17_saved = configured_m17_node()
    if saved and saved not in private:
        raise SetupError(f"M17 Support records DVSwitch node {saved}, but it is not a private USRP node in rpt.conf.")
    print("Configured private USRP nodes:")
    for node, channel in private.items():
        # Distinguish both option 7 selections from unrelated private-node entries.
        label = ("DVSwitch (saved by M17 Support)" if node == saved else
                 "M17 (saved by M17 Support)" if node == m17_saved else
                 "available for another service")
        print(f"  {node}: {channel} — {label}")
    selected = validate_node(prompt("Which private node number is used for DVSwitch?", saved or None),
                             "DVSwitch private node")
    if selected not in private:
        raise SetupError(f"Node {selected} is not configured as a private USRP node in rpt.conf.")
    return selected


def configured_m17_node() -> str:
    """Read the M17 node reserved by option 7 so the bridge can adopt it."""
    if not SUPPORT_CONFIG.is_file():
        return ""
    match = re.search(r"(?m)^M17_PRIVATE_NODE=([0-9]+)$",
                      SUPPORT_CONFIG.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def matching_imported_node(private: dict[str, str]) -> str:
    """Recognize the manually configured USRP2M17 node so the installer can adopt it."""
    if STATE_FILE.is_file() or not CONFIG.is_file() or not BINARY.is_file():
        return ""
    usrp = parse_ini(CONFIG).get("USRP Network", {})
    local_port = usrp.get("localport", "")
    dst_port = usrp.get("dstport", "")
    if not local_port.isdigit() or not dst_port.isdigit():
        return ""
    expected = f"USRP/127.0.0.1:{local_port}:{dst_port}"
    matches = [node for node, channel in private.items() if channel.rstrip("/") == expected]
    if len(matches) > 1:
        raise SetupError("More than one Asterisk node matches the existing USRP2M17 ports; clean up the duplicate manually.")
    return matches[0] if matches else ""


def edit_rpt_conf(path: Path, node: str, usrp_local: int, asl_local: int,
                  *, allow_managed_block: bool = False,
                  adopt_existing_node: bool = False,
                  original_channel_out: list[str] | None = None) -> tuple[bool, bool]:
    """Add a marked private-node stanza and local node map without guessing IDs."""
    content = path.read_text(encoding="utf-8")
    channel = f"USRP/127.0.0.1:{usrp_local}:{asl_local}"
    managed_node_block = False
    if BEGIN in content or END in content:
        if not allow_managed_block or content.count(BEGIN) != 1 or content.count(END) != 1:
            raise SetupError("rpt.conf already has an M17 installer block; review the existing installation first.")
        start = content.index(BEGIN)
        finish = content.index(END, start)
        block = content[start:finish]
        header = re.search(r"(?m)^\[(\d{1,8})\]\(node-main\)$", block)
        old_rx = re.search(r"(?m)^rxchannel\s*=\s*.*$", block, re.I)
        if not header or header.group(1) != node or not old_rx:
            raise SetupError("The managed M17 node block was customized; refusing to rewrite it.")
        content = content[:start] + block.replace(old_rx.group(0), f"rxchannel = {channel}", 1) + content[finish:]
        managed_node_block = True
    sections = parse_node_sections(content)
    added_node = managed_node_block
    if node in sections:
        prior_channel = node_channel(sections[node])
        if prior_channel != channel and adopt_existing_node:
            # Change only the reserved node's rxchannel; preserve its other stanza settings.
            section_header = re.search(rf"(?m)^\[\s*{re.escape(node)}\s*\]\s*(?:\([^)]*\))?\s*$", content)
            if not section_header:
                raise SetupError(f"Could not locate the reserved M17 node {node} stanza.")
            next_header = re.search(r"(?m)^\s*\[", content[section_header.end():])
            end = section_header.end() + next_header.start() if next_header else len(content)
            section_text = content[section_header.end():end]
            rx_line = re.search(r"(?im)^(\s*rxchannel\s*=\s*).*?$", section_text)
            if not rx_line:
                raise SetupError(f"Reserved M17 node {node} has no rxchannel setting to update.")
            if original_channel_out is not None and not original_channel_out:
                original_channel_out.append(prior_channel or "")
            section_text = section_text[:rx_line.start()] + rx_line.group(1) + channel + section_text[rx_line.end():]
            content = content[:section_header.end()] + section_text + content[end:]
        elif prior_channel != channel:
            raise SetupError(f"Node {node} already exists with another rxchannel; choose a new node ID or reconcile it first.")
    else:
        separator = "" if not content or content.endswith("\n") else "\n"
        content += (separator + "\n" + BEGIN + f"\n[{node}](node-main)\n"
                    f"rxchannel = {channel}\nduplex = 0\n{END}\n")
        added_node = True
    map_entries = []
    for line in content.splitlines():
        clean = line.split(";", 1)[0].split("#", 1)[0].strip()
        match = re.fullmatch(rf"{re.escape(node)}\s*=\s*(.*?)\s*", clean)
        if match:
            map_entries.append(match.group(1))
    expected_map = f"radio@127.0.0.1:4571/{node},NONE"
    if len(map_entries) > 1:
        raise SetupError(f"rpt.conf defines node {node} more than once in its node map.")
    if map_entries:
        if map_entries[0] != expected_map:
            local_map = re.fullmatch(
                rf"radio@127\.0\.0\.1(?::([0-9]+))?/{re.escape(node)},NONE",
                map_entries[0], re.I)
            valid_local_map = bool(local_map and
                                   (not local_map.group(1) or 1 <= int(local_map.group(1)) <= 65535))
            # Option 7 reserves this node; preserve its valid local IAX mapping and port.
            if not adopt_existing_node or not valid_local_map:
                raise SetupError(f"rpt.conf already maps node {node} differently; review that entry before installing.")
        added_map = False
    else:
        lines = content.splitlines(keepends=True)
        headers = [i for i, line in enumerate(lines)
                   if re.fullmatch(r"\s*\[nodes\]\s*(?:;.*)?\n?", line, re.I)]
        if len(headers) > 1:
            raise SetupError("rpt.conf has multiple [nodes] sections; combine them before installing.")
        mapping = f"{node} = radio@127.0.0.1:4571/{node},NONE {NODE_MAP_MARKER}\n"
        if headers:
            start = headers[0] + 1
            end = next((i for i in range(start, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
            lines.insert(end, mapping)
            content = "".join(lines)
        else:
            content += ("\n" if content and not content.endswith("\n") else "") + f"\n[nodes]\n{mapping}"
        added_map = True
    path.write_text(content, encoding="utf-8")
    return added_node, added_map


def remove_managed_rpt(path: Path, state: dict[str, object]) -> None:
    """Remove only the exact managed node block and marked map line."""
    if not path.is_file():
        return
    content = path.read_text(encoding="utf-8")
    if state.get("rpt_added_node"):
        start = content.find(BEGIN + "\n")
        end = content.find(END + "\n", start) if start >= 0 else -1
        if start >= 0 and end >= 0:
            content = content[:start] + content[end + len(END) + 1:]
        elif BEGIN in content or END in content:
            print("NOTICE: M17 node block was changed after installation; leaving it in rpt.conf.")
    elif state.get("rpt_original_channel"):
        # Restore an adopted node only when its rxchannel still matches this install's value.
        settings = state.get("settings", {})
        if isinstance(settings, dict):
            node = str(settings.get("m17_node", ""))
            installed_channel = f"USRP/127.0.0.1:{settings.get('usrp_local', '')}:{settings.get('asl_local', '')}"
            sections = parse_node_sections(content)
            if node in sections and node_channel(sections[node]) == installed_channel:
                section_header = re.search(rf"(?m)^\[\s*{re.escape(node)}\s*\]\s*(?:\([^)]*\))?\s*$", content)
                if section_header:
                    next_header = re.search(r"(?m)^\s*\[", content[section_header.end():])
                    end = section_header.end() + next_header.start() if next_header else len(content)
                    section_text = content[section_header.end():end]
                    rx_line = re.search(r"(?im)^(\s*rxchannel\s*=\s*).*?$", section_text)
                    if rx_line:
                        section_text = section_text[:rx_line.start()] + rx_line.group(1) + str(state["rpt_original_channel"]) + section_text[rx_line.end():]
                        content = content[:section_header.end()] + section_text + content[end:]
            else:
                print(f"NOTICE: M17 node {node} changed after installation; leaving its rxchannel in rpt.conf.")
    if state.get("rpt_added_map"):
        content = "".join(line for line in content.splitlines(keepends=True)
                          if NODE_MAP_MARKER not in line)
    path.write_text(content, encoding="utf-8")


def make_config(values: dict[str, object]) -> str:
    """Write the configuration fields recognized by USRP2M17."""
    return (
        "# DVSwitch-M17-Bridge managed configuration v1\n"
        "[M17 Network]\n"
        f"Callsign={values['callsign']}\nAddress={values['address']}\n"
        f"Name={values['name']} {values['module']}\n"
        f"LocalPort={values['m17_local']}\nDstPort={values['m17_remote']}\n"
        f"GainAdjustdB={values['m17_gain']}\nDaemon=0\nDebug=0\n\n"
        "[USRP Network]\nAddress=127.0.0.1\n"
        f"DstPort={values['asl_local']}\nLocalPort={values['usrp_local']}\n"
        f"GainAdjustdB={values['usrp_gain']}\nDebug=0\n\n"
        "[Log]\nDisplayLevel=1\nFileLevel=1\n"
        "FilePath=/var/log/usrp2m17\nFileRoot=USRP2M17\n"
    )


def service_text() -> str:
    """Run the bridge under the ASL account and let systemd manage its lifetime."""
    return (
        "# DVSwitch-M17-Bridge managed service v1\n"
        "[Unit]\nDescription=USRP2M17 M17 to ASL bridge\nAfter=network-online.target asterisk.service\n"
        "Wants=network-online.target\n\n[Service]\nType=simple\nUser=asl\nGroup=asl\n"
        f"WorkingDirectory={SOURCE_ROOT / 'USRP2M17'}\nExecStart={BINARY}\n"
        "Restart=on-failure\nRestartSec=5\n\n[Install]\nWantedBy=multi-user.target\n"
    )


def make_backup(paths: list[Path], action: str) -> Path:
    """Snapshot files before install or uninstall so an operator can recover them."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_ROOT / f"{action}-{stamp}"
    suffix = 0
    while target.exists():
        suffix += 1
        target = BACKUP_ROOT / f"{action}-{stamp}-{suffix}"
    target.mkdir(parents=True, mode=0o700)
    for path in paths:
        name = str(path).lstrip("/").replace("/", "__")
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.copytree(path, target / name, symlinks=True)
                status = "directory"
            else:
                shutil.copy2(path, target / name, follow_symlinks=False)
                status = "present"
        else:
            status = "absent"
        (target / f"{name}.state").write_text(status + "\n", encoding="utf-8")
    return target


def patch_fixed_width_integer_includes(project: Path) -> list[Path]:
    """Add direct integer-type includes to affected C++ files in the temporary build tree."""
    patched: list[Path] = []
    integer_type = re.compile(r"\b(?:u?int(?:8|16|32|64)_t)\b")
    integer_header = re.compile(r"(?m)^\s*#\s*include\s*[<\"](?:cstdint|stdint\.h)[>\"]")
    include_line = re.compile(r"(?m)^\s*#\s*include\s+[<\"]")
    for source in project.rglob("*"):
        if source.suffix not in {".h", ".cpp"}:
            continue
        text = source.read_text(encoding="utf-8")
        if not integer_type.search(text) or integer_header.search(text):
            continue
        first_include = include_line.search(text)
        if not first_include:
            raise SetupError(f"Cannot add the fixed-width integer header safely to {source.name}.")
        text = text[:first_include.start()] + "#include <cstdint>\n" + text[first_include.start():]
        source.write_text(text, encoding="utf-8")
        patched.append(source)
    return patched


def ensure_install_root() -> bool:
    marker = INSTALL_ROOT / ".dvswitch-m17-bridge-managed"
    if INSTALL_ROOT.exists():
        if not marker.is_file():
            raise SetupError(f"{INSTALL_ROOT} exists and is not owned by this installer; refusing to change it.")
        return False
    INSTALL_ROOT.mkdir(parents=True, mode=0o755)
    marker.write_text(f"DVSwitch M17 Bridge installer v{VERSION}\n", encoding="utf-8")
    return True


def ensure_source() -> bytes:
    if not SOURCE_ROOT.exists():
        run(["git", "clone", "--depth", "1", "--branch", "master", REPOSITORY, str(SOURCE_ROOT)])
    else:
        origin = run(["git", "-C", str(SOURCE_ROOT), "remote", "get-url", "origin"],
                     capture=True).stdout.strip()
        if origin.rstrip("/") not in {REPOSITORY.rstrip("/"), "https://github.com/nostar/MMDVM_CM"}:
            raise SetupError(f"Existing source has an unexpected Git remote: {origin}")
        tracked_changes = run(["git", "-C", str(SOURCE_ROOT), "status", "--porcelain",
                               "--untracked-files=no"], capture=True).stdout.strip()
        if tracked_changes:
            raise SetupError("The MMDVM_CM source checkout has tracked local changes; save them before updating.")
        project = SOURCE_ROOT / "USRP2M17"
        if (project / "Makefile").is_file():
            # The upstream Makefile clean target removes only its declared compiler outputs.
            # In particular, this removes USRP2M17, the untracked executable from our prior build.
            run(["make", "clean"], cwd=project)
        changes = run(["git", "-C", str(SOURCE_ROOT), "status", "--porcelain",
                       "--untracked-files=all"], capture=True).stdout.strip()
        if changes:
            raise SetupError("The MMDVM_CM source checkout has local changes; save them before updating.")
        run(["git", "-C", str(SOURCE_ROOT), "pull", "--ff-only", "origin", "master"])
    project = SOURCE_ROOT / "USRP2M17"
    if not (project / "Makefile").is_file():
        raise SetupError("The GitHub source does not contain USRP2M17/Makefile.")
    # Build a temporary patched copy so the upstream Git checkout stays clean
    # and later upgrades can still use the installer's fast-forward safety check.
    with tempfile.TemporaryDirectory(prefix="dvswitch-m17-build-") as temporary:
        build_project = Path(temporary) / "USRP2M17"
        shutil.copytree(project, build_project,
                        ignore=shutil.ignore_patterns("*.o", "*.d", "USRP2M17", "*.bak", "*~"))
        source = build_project / "USRP2M17.cpp"
        text = source.read_text(encoding="utf-8")
        activity_logs = {
            'LogMessage("M17 received end of voice transmission, %.1f seconds", float(m_m17Frames) / 25.0F);':
                'LogMessage("M17 received end of voice transmission from %s, %.1f seconds", m_usrpcs.c_str(), float(m_m17Frames) / 25.0F);',
            'LogMessage("USRP received end of voice transmission, %.1f seconds", float(m_usrpFrames) / 50.0F);':
                'LogMessage("USRP received end of voice transmission from %s, %.1f seconds", m_usrpcs.c_str(), float(m_usrpFrames) / 50.0F);',
        }
        for old, new in activity_logs.items():
            if text.count(old) != 1:
                raise SetupError("The checked-out USRP2M17 source has an unsupported activity-log structure; no binary was installed.")
            text = text.replace(old, new, 1)
        source.write_text(text, encoding="utf-8")
        # Keep upstream's checkout clean while fixing missing direct integer headers in the build copy.
        patch_fixed_width_integer_includes(build_project)
        run(["make"], cwd=build_project)
        built = build_project / "USRP2M17"
        if not built.is_file():
            raise SetupError("The build did not produce the USRP2M17 executable.")
        binary = built.read_bytes()
    ensure_service_directory_access()
    return binary


def ensure_service_directory_access() -> None:
    """Allow the unprivileged ASL service account to traverse its working path."""
    # The manager runs with umask 077; make the owned source directories traversable explicitly.
    for directory in (INSTALL_ROOT, SOURCE_ROOT, SOURCE_ROOT / "USRP2M17"):
        if not directory.is_dir():
            raise SetupError(f"USRP2M17 service directory is missing: {directory}")
        directory.chmod(0o755)


def module_loaded() -> bool:
    result = run(["asterisk", "-rx", "module show like chan_usrp.so"], check=False, capture=True)
    return result.returncode == 0 and "chan_usrp.so" in (result.stdout or "") and "Running" in (result.stdout or "")


def collect_values(private: dict[str, str], previous_state: dict[str, object],
                   imported_node: str = "") -> dict[str, object]:
    existing = parse_ini(CONFIG)
    dv_node = private_node_selection(private)
    saved = previous_state.get("settings", {})
    managed_node = str(saved.get("m17_node", "")) if isinstance(saved, dict) else ""
    # Option 7 reserves the M17 node before the bridge adds or adopts its USRP stanza.
    known_node = managed_node or imported_node or configured_m17_node()
    if imported_node:
        print(f"The existing USRP2M17 settings match private node {imported_node}; this setup will adopt it.")
    print("Select the reserved M17 private node; it must differ from the DVSwitch node.")
    while True:
        m17_node = validate_node(prompt("M17 private node number", known_node or None), "M17 private node")
        if known_node and m17_node != known_node:
            raise SetupError("Keep the existing M17 node number during an upgrade. Uninstall first to change it.")
        if m17_node != dv_node and (m17_node not in private or m17_node == known_node):
            break
        print("That node ID is already in use.")
    callsign = prompt("Your amateur radio callsign",
                      existing.get("M17 Network", {}).get("callsign", "")).upper()
    if not re.fullmatch(r"[A-Z0-9]{3,9}", callsign):
        raise SetupError("Enter a callsign containing 3 to 9 letters or digits.")
    name, address, remote_port, module = select_reflector(existing)
    old_usrp = existing.get("USRP Network", {})
    asl_port = validate_port(prompt("Asterisk's M17 private-node UDP port",
                                    old_usrp.get("dstport", "32008")), "Asterisk USRP port")
    usrp_port = validate_port(prompt("USRP2M17's local USRP UDP port",
                                     old_usrp.get("localport", "34008")), "USRP2M17 USRP port")
    if asl_port == usrp_port:
        raise SetupError("The two local USRP ports must be different.")
    for node, channel in private.items():
        if node == known_node:
            continue
        match = re.fullmatch(r"usrp/[^:]+:(\d+):(\d+)", channel, re.I)
        if match and {asl_port, usrp_port} & {int(match.group(1)), int(match.group(2))}:
            raise SetupError(f"Ports conflict with private USRP node {node}; choose two unused ports.")
    current_settings = saved if isinstance(saved, dict) else {}
    # Asterisk already binds the ports named by the reserved M17 rxchannel; those are expected, not conflicts.
    reserved_m17_ports = node_channel_ports(private.get(m17_node, ""))
    def port_available(port: int, setting: str) -> bool:
        configured_value = {
            "asl_local": old_usrp.get("dstport", ""),
            "usrp_local": old_usrp.get("localport", ""),
            "m17_local": existing.get("M17 Network", {}).get("localport", ""),
        }.get(setting, "")
        imported_port = configured_value.isdigit() and int(configured_value) == port
        return (port in reserved_m17_ports or udp_port_free(port)
                or int(current_settings.get(setting, -1)) == port or imported_port)

    if not port_available(asl_port, "asl_local"):
        raise SetupError(f"Asterisk-side USRP port {asl_port} is already occupied; choose another port.")
    if not port_available(usrp_port, "usrp_local"):
        raise SetupError(f"USRP2M17 port {usrp_port} is already occupied; stop that process or choose another port.")
    m17_default = existing.get("M17 Network", {}).get("localport", "")
    if not m17_default.isdigit() or not port_available(int(m17_default), "m17_local"):
        m17_default = str(next_free_port(32010, {asl_port, usrp_port}))
    m17_local = validate_port(prompt("USRP2M17's local M17 network UDP port", m17_default),
                              "M17 local UDP port")
    if m17_local in {asl_port, usrp_port} or not port_available(m17_local, "m17_local"):
        raise SetupError(f"M17 network port {m17_local} is occupied or conflicts with a USRP port.")
    m17_gain = prompt("M17-to-USRP gain adjustment in dB",
                      existing.get("M17 Network", {}).get("gainadjustdb", "3"))
    usrp_gain = prompt("USRP-to-M17 gain adjustment in dB", old_usrp.get("gainadjustdb", "-6"))
    for label, value in (("M17 gain", m17_gain), ("USRP gain", usrp_gain)):
        if not re.fullmatch(r"-?[0-9]{1,2}", value):
            raise SetupError(f"{label} must be a whole number from -99 to 99.")
    print("\nSetup summary")
    for label, value in (("DVSwitch private node", dv_node), ("M17 private node", m17_node),
                         ("Callsign", callsign), ("Reflector", f"{name} {module} ({address}:{remote_port})"),
                         ("Asterisk USRP port", asl_port), ("USRP2M17 USRP port", usrp_port),
                         ("M17 local UDP port", m17_local)):
        print(f"  {label:<23} {value}")
    if not ask_yes_no("Install with these settings?", False):
        raise SetupError("Installation cancelled; no system files were changed.")
    return {"dv_node": dv_node, "m17_node": m17_node, "callsign": callsign,
            "name": name, "address": address, "module": module,
            "m17_remote": remote_port, "m17_local": m17_local,
            "asl_local": asl_port, "usrp_local": usrp_port,
            "m17_gain": m17_gain, "usrp_gain": usrp_gain}


def install() -> None:
    require_root()
    check_only()
    check_platform(allow_package_install=True)
    private = discover_private_nodes(RPT_CONF.read_text(encoding="utf-8"))
    if not private:
        raise SetupError("No private USRP node was found in rpt.conf.")
    if not SUPPORT_INSTALLER.is_file() or not os.access(SUPPORT_INSTALLER, os.R_OK):
        raise SetupError("The M17-owned private-node switching installer is missing from this repository.")
    imported_node = matching_imported_node(private)
    if INSTALL_ROOT.exists() and not (INSTALL_ROOT / ".dvswitch-m17-bridge-managed").is_file():
        raise SetupError(f"{INSTALL_ROOT} exists and is not marked as owned by this installer; refusing to change it.")
    for target in (CONFIG, BINARY, SERVICE):
        if target.exists() or target.is_symlink():
            is_managed = STATE_FILE.is_file() or (target == SERVICE and "DVSwitch-M17-Bridge managed service" in target.read_text(encoding="utf-8", errors="replace"))
            if target == SERVICE and not is_managed:
                raise SetupError(f"{target} already exists and is not a managed USRP2M17 service.")
            if not is_managed and not ask_yes_no(f"{target} already exists. Back it up and let this installer manage it?", False):
                raise SetupError(f"Installation cancelled to protect the existing {target}.")
    previous_state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.is_file() else {}
    values = collect_values(private, previous_state, imported_node)
    legacy_process = (not previous_state and shutil.which("pgrep") is not None and
                      run(["pgrep", "-x", "USRP2M17"], check=False, capture=True).returncode == 0)
    if legacy_process and (shutil.which("pkill") is None or not ask_yes_no(
            "A manually started USRP2M17 process is running. Stop it before enabling the service?", False)):
        raise SetupError("Stop the existing USRP2M17 process, then rerun the installer.")
    backup = Path(previous_state["backup"]) if previous_state.get("backup") else make_backup(
        [CONFIG, BINARY, SERVICE, RPT_CONF], "install")
    rollback_backup = make_backup([CONFIG, BINARY, SERVICE, RPT_CONF], "upgrade") if previous_state else backup
    created_root = ensure_install_root()
    system_changes_started = False
    service_was_active = run(["systemctl", "is-active", "usrp2m17.service"],
                             check=False, capture=True).returncode == 0
    service_was_enabled = run(["systemctl", "is-enabled", "usrp2m17.service"],
                              check=False, capture=True).returncode == 0
    service_activation_attempted = False
    try:
        built_binary = ensure_source()
        if previous_state:
            system_changes_started = True
            run(["systemctl", "stop", "usrp2m17.service"], check=False)
        else:
            system_changes_started = True
        if legacy_process:
            run(["pkill", "-TERM", "-x", "USRP2M17"], check=False)
        fd, binary_tmp = tempfile.mkstemp(prefix='.USRP2M17.', dir=BINARY.parent)
        with os.fdopen(fd, 'wb') as output:
            output.write(built_binary)
        os.chmod(binary_tmp, 0o755)
        os.replace(binary_tmp, BINARY)
        asl = pwd.getpwnam("asl")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.chown(LOG_DIR, asl.pw_uid, asl.pw_gid)
        CONFIG.write_text(make_config(values), encoding="utf-8")
        os.chown(CONFIG, asl.pw_uid, asl.pw_gid)
        SERVICE.write_text(service_text(), encoding="utf-8")
        SERVICE.chmod(0o644)
        original_channel: list[str] = []
        added_node, added_map = edit_rpt_conf(
            RPT_CONF, str(values["m17_node"]), int(values["usrp_local"]),
            int(values["asl_local"]), allow_managed_block=bool(previous_state),
            adopt_existing_node=(str(values["m17_node"]) == configured_m17_node()),
            original_channel_out=original_channel)
        added_node = bool(previous_state.get("rpt_added_node")) or added_node
        added_map = bool(previous_state.get("rpt_added_map")) or added_map
        switch_backup = str(previous_state.get("switch_backup", ""))
        support = run(["bash", str(SUPPORT_INSTALLER), "--install", str(values["m17_node"]), str(values["dv_node"])], capture=True)
        print(support.stdout or "", end="")
        match = re.search(r"Backup: (.+)", support.stdout or "")
        if match and not switch_backup:
            switch_backup = Path(match.group(1)).name
        run(["systemctl", "daemon-reload"])
        service_activation_attempted = True
        run(["systemctl", "enable", "--now", "usrp2m17.service"])
        service_state = run(["systemctl", "is-active", "usrp2m17.service"],
                            check=False, capture=True).stdout.strip()
        if service_state != "active":
            raise SetupError("usrp2m17.service did not become active; review 'journalctl -u usrp2m17.service'.")
        state = {"version": VERSION, "backup": str(backup),
                 "created_root": previous_state.get("created_root", created_root),
                 "rpt_added_node": added_node, "rpt_added_map": added_map,
                 "switch_backup": switch_backup, "settings": values}
        if previous_state.get("rpt_original_channel"):
            state["rpt_original_channel"] = previous_state["rpt_original_channel"]
        elif original_channel:
            state["rpt_original_channel"] = original_channel[0]
        STATE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o755)
        STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print("PASS: USRP2M17 is installed and enabled as usrp2m17.service.")
        print(f"Backup: {backup}")
        print("Restart Asterisk before testing the new private node.")
        if ask_yes_no("Restart Asterisk now? Current links and calls will be interrupted.", False):
            run(["systemctl", "restart", "asterisk"])
        else:
            print("Asterisk was not restarted; schedule a restart before testing.")
    except Exception:
        if system_changes_started:
            # A first-install failure before daemon-reload has no known service unit to disable.
            if previous_state or service_was_active or service_was_enabled or service_activation_attempted:
                run(["systemctl", "disable", "--now", "usrp2m17.service"], check=False)
            for target in (CONFIG, BINARY, SERVICE, RPT_CONF):
                restore_one(target, rollback_backup)
            run(["systemctl", "daemon-reload"], check=False)
            if service_was_enabled:
                run(["systemctl", "enable", "usrp2m17.service"], check=False)
            elif previous_state:
                run(["systemctl", "disable", "usrp2m17.service"], check=False)
            if service_was_active:
                run(["systemctl", "start", "usrp2m17.service"], check=False)
        if created_root and INSTALL_ROOT.exists():
            shutil.rmtree(INSTALL_ROOT)
        print(f"ERROR: installation did not finish. Original files are backed up at {backup}.",
              file=sys.stderr)
        if created_root:
            print(f"Review the partial source checkout at {INSTALL_ROOT}.", file=sys.stderr)
        raise


def restore_one(path: Path, backup: Path) -> None:
    name = str(path).lstrip("/").replace("/", "__")
    state_path = backup / f"{name}.state"
    if not state_path.is_file():
        raise SetupError(f"Backup record is missing for {path}.")
    saved_state = state_path.read_text(encoding="utf-8").strip()
    if saved_state == "absent":
        path.unlink(missing_ok=True)
    elif saved_state == "present":
        source = backup / name
        if not source.exists() and not source.is_symlink():
            raise SetupError(f"Saved copy is missing for {path}.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        shutil.copy2(source, path, follow_symlinks=False)


def uninstall() -> None:
    require_root()
    if not STATE_FILE.is_file():
        raise SetupError("No completed installation record exists; there is nothing to uninstall.")
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    backup = Path(state.get("backup", ""))
    if not backup.is_dir() or not ask_yes_no("Uninstall USRP2M17 and its installer-created node entries?", False):
        print("Uninstall cancelled.")
        return
    recovery = make_backup([CONFIG, BINARY, SERVICE, RPT_CONF], "uninstall")
    run(["systemctl", "disable", "--now", "usrp2m17.service"], check=False)
    remove_managed_rpt(RPT_CONF, state)
    for path in (CONFIG, BINARY, SERVICE):
        restore_one(path, backup)
    run(["systemctl", "daemon-reload"])
    switch_backup = state.get("switch_backup", "")
    if switch_backup and SUPPORT_INSTALLER.is_file():
        run(["bash", str(SUPPORT_INSTALLER), "--restore", switch_backup])
    source_marker = INSTALL_ROOT / ".dvswitch-m17-bridge-managed"
    if source_marker.is_file() and ask_yes_no("Remove the installer-owned MMDVM_CM source checkout?", True):
        shutil.rmtree(INSTALL_ROOT)
    STATE_FILE.unlink(missing_ok=True)
    print("PASS: USRP2M17 service and managed files were uninstalled.")
    print(f"Uninstall recovery backup: {recovery}")
    print("Restart Asterisk if the installer-created private node was removed.")


def check_only() -> None:
    require_root()
    missing = check_platform()
    if not module_loaded():
        raise SetupError("chan_usrp.so is not Running; enable it in Asterisk before installation.")
    private = discover_private_nodes(RPT_CONF.read_text(encoding="utf-8"))
    if not private:
        raise SetupError("No private USRP node was found in rpt.conf.")
    if not SUPPORT_INSTALLER.is_file() or not os.access(SUPPORT_INSTALLER, os.R_OK):
        raise SetupError("The M17-owned private-node switching installer is missing from this repository.")
    if missing:
        print("NOTICE: the guided installer will offer to install: " + ", ".join(missing))
    print("PASS: Debian, Asterisk, chan_usrp, and M17 node-switch support prerequisites are ready. No files changed.")


def menu() -> None:
    print(f"\nUSRP2M17 Bridge installer v{VERSION}\n\n1) Install or upgrade USRP2M17\n2) Uninstall USRP2M17\n0) Exit\n")
    choice = prompt("Choose an option [0/1/2]", "0")
    if choice == "1":
        install()
    elif choice == "2":
        uninstall()
    elif choice != "0":
        raise SetupError("Choose 0, 1, or 2.")


def main(argv: list[str]) -> int:
    try:
        if argv == ["--check"]:
            check_only()
        elif argv == ["--install"]:
            install()
        elif argv == ["--uninstall"]:
            uninstall()
        elif argv in ([], ["--menu"]):
            require_root()
            menu()
        elif argv in (["--help"], ["-h"]):
            print("Usage: sudo ./dvswitch-m17-bridge.py [--check|--install|--uninstall]")
        else:
            raise SetupError("Usage: dvswitch-m17-bridge.py [--check|--install|--uninstall]")
        return 0
    except (SetupError, OSError, subprocess.SubprocessError, configparser.Error, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
