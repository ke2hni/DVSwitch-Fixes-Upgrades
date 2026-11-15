#!/usr/bin/env python3
# Version: 1.0.0
# Created: 2026-11-15T12:00:00+00:00 by KE2HNI
# SPDX-License-Identifier: MIT

"""Pre-install validation for private AllStarLink node duplex configuration."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Section:
    parents: list[str] = field(default_factory=list)
    values: dict[str, list[str]] = field(default_factory=dict)


def parse_rpt(text: str) -> dict[str, Section]:
    sections: dict[str, Section] = {}
    private_names: set[int] = set()
    current: Section | None = None
    header = re.compile(r"^\[\s*([^]]+?)\s*\]\s*(?:\(\s*([^)]*)\s*\))?\s*$")
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].split("#", 1)[0].strip()
        match = header.fullmatch(line)
        if match:
            name, parent_text = match.groups()
            parents = [part.strip() for part in (parent_text or "").split(",")
                       if part.strip() and part.strip() != "!"]
            if name.isdigit() and 0 < int(name) < 2000:
                if int(name) in private_names:
                    raise ValueError(f"rpt.conf defines private node stanza [{name}] more than once")
                private_names.add(int(name))
            current = sections.setdefault(name, Section())
            if parents:
                current.parents = parents
            continue
        if not current or "=" not in line:
            continue
        key, value = line.split("=", 1)
        current.values.setdefault(key.strip().lower(), []).append(value.strip())
    return sections


def setting(sections: dict[str, Section], name: str, key: str,
            stack: tuple[str, ...] = ()) -> str | None:
    if name in stack:
        raise ValueError("template inheritance cycle: " + " -> ".join((*stack, name)))
    section = sections.get(name)
    if section is None:
        return None
    direct = section.values.get(key, [])
    if len(direct) > 1:
        raise ValueError(f"[{name}] has multiple active {key}= settings")
    if direct:
        return direct[0]
    inherited = [setting(sections, parent, key, (*stack, name))
                 for parent in section.parents]
    inherited = [value for value in inherited if value is not None]
    if len(set(inherited)) > 1:
        raise ValueError(f"[{name}] inherits conflicting {key}= settings")
    return inherited[0] if inherited else None


def read_support_nodes(path: Path | None) -> dict[str, str]:
    if path is None or (not path.exists() and not path.is_symlink()):
        return {}
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{path} is not a regular, non-symlink config file")
    result: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        match = re.fullmatch(r"(M17_PRIVATE_NODE|DVSWITCH_PRIVATE_NODE)=([0-9]+)", line.strip())
        if match:
            key, node = match.groups()
            if key in result:
                raise ValueError(f"{path} contains duplicate {key} entries")
            result[key] = node
    if any(line.startswith("# DVSwitch-M17-Support:") for line in lines):
        missing = {"M17_PRIVATE_NODE", "DVSWITCH_PRIVATE_NODE"} - result.keys()
        if missing:
            raise ValueError(f"{path} is missing saved node selection(s): {', '.join(sorted(missing))}")
    return result


def inspect(rpt_path: Path, support_path: Path | None) -> list[str]:
    if not rpt_path.is_file():
        return [f"Asterisk node configuration is unavailable: {rpt_path}"]
    try:
        sections = parse_rpt(rpt_path.read_text(encoding="utf-8"))
    except ValueError as error:
        return [f"Cannot safely parse {rpt_path}: {error}."]
    errors: list[str] = []
    private_nodes = [name for name in sections if name.isdigit() and 0 < int(name) < 2000]
    for node in sorted(private_nodes, key=int):
        try:
            duplex = setting(sections, node, "duplex")
            channel = setting(sections, node, "rxchannel")
        except ValueError as error:
            errors.append(f"Private node {node}: {error}.")
            continue
        if duplex is None:
            errors.append(f"Private node {node} has no active duplex= setting in its stanza or inherited template; ASL defaults to mode 2 when omitted.")
        elif not re.fullmatch(r"[0-4]", duplex):
            errors.append(f"Private node {node} has unsupported duplex={duplex!r}; expected 0 through 4.")
        if channel and channel.lower().startswith("usrp/") and duplex != "0":
            errors.append(f"Private USRP node {node} resolves to duplex={duplex!r}; this DVSwitch bridge setup requires duplex=0.")

    try:
        for key, node in read_support_nodes(support_path).items():
            if not 0 < int(node) < 2000:
                errors.append(f"{key}={node} is outside ASL's private-node range (1–1999).")
                continue
            if node not in sections:
                errors.append(f"{key}={node} has no numeric [{node}] stanza in {rpt_path}.")
                continue
            try:
                channel = setting(sections, node, "rxchannel")
                duplex = setting(sections, node, "duplex")
            except ValueError as error:
                errors.append(f"{key}={node}: {error}.")
                continue
            if not channel or not channel.lower().startswith("usrp/"):
                errors.append(f"{key}={node} is not configured with an active USRP rxchannel.")
            if duplex != "0":
                errors.append(f"{key}={node} must resolve to duplex=0; it currently resolves to {duplex!r}.")
    except (OSError, UnicodeError, ValueError) as error:
        errors.append(f"Cannot validate saved DVSwitch/M17 node selections: {error}.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpt-conf", type=Path, default=Path("/etc/asterisk/rpt.conf"))
    parser.add_argument("--support-config", type=Path, default=Path("/etc/dvswitch-m17-support.conf"))
    args = parser.parse_args()
    try:
        errors = inspect(args.rpt_conf, args.support_config)
    except (OSError, UnicodeError, ValueError) as error:
        errors = [f"Cannot read Asterisk node configuration: {error}."]
    if errors:
        print("ERROR: DVSwitch-Mods private-node safety check failed; no installation was started.", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("Review the affected node stanzas in /etc/asterisk/rpt.conf. Set duplex=0 for each DVSwitch/M17 USRP bridge node, then rerun the manager.", file=sys.stderr)
        return 1
    print("PASS: private-node duplex settings are valid; configured USRP bridge nodes resolve to duplex=0. No files changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
