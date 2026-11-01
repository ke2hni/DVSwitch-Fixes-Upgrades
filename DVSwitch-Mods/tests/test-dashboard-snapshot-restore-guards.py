#!/usr/bin/env python3
"""Verify full-file dashboard restores reject edits from other components."""
# Version: 1.0.7
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import shlex
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    match = re.search(rf"(?ms)^{re.escape(name)}\(\)\{{.*?^}}", source)
    require(match is not None, f"missing {name}() in {path.name}")
    return match.group(0)


with tempfile.TemporaryDirectory(prefix="dvsm-restore-guards-") as tmp:
    root = Path(tmp)
    die = 'die(){ printf "%s\\n" "$*" >&2; exit 1; }\n'

    snapshot = root / "css.php"
    current = root / "current-css.php"
    # Cover both stock and previously capped snapshots migrating to the fluid width.
    css_overlay = '/* DVSwitch-Mods: responsive column alignment and compact header v1.3.4 */ .nav #modeInfo > fieldset { margin-top:8px !important; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } .nav #modeInfo > span:first-child { position:relative; top:-1px; } body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } body:has(#dvs-asl-activity:not([hidden])) #dvs-asl-activity { position:relative; top:-1px; } .header { padding:0; } .header h2 { margin:8px 0; } .container {'
    snapshot.write_text("width: 900px;\nwhite-space: nowrap;\n.container {\n")
    current.write_text("width: 96vw;\nwhite-space: normal;\n" + css_overlay + "\n")
    layout_function = function_source(ROOT / "dvswitch-display-layout.sh", "check_layout_snapshot_pair")
    harness = root / "layout-check.sh"
    arguments = [
        '"width: 900px;"', '"width: 96vw;"',
        '"width: min(96vw, 1200px);"', '"width: 96vw;"',
        '"white-space: nowrap;"', '"white-space: normal;"',
        shlex.quote('.container {'), shlex.quote(css_overlay),
    ]
    harness.write_text(
        die + layout_function + "\ncheck_layout_snapshot_pair \"$CURRENT\" \"$SNAPSHOT\" "
        + " ".join(arguments) + "\n",
        encoding="utf-8",
    )
    env = os.environ | {"CURRENT": str(current), "SNAPSHOT": str(snapshot)}
    accepted = subprocess.run(["bash", "-e", str(harness)], env=env, text=True, capture_output=True)
    require(accepted.returncode == 0, "display-layout restore guard rejected its own changes")
    snapshot.write_text("width: min(96vw, 1200px);\nwhite-space: normal;\n.container {\n")
    current.write_text("width: 96vw;\nwhite-space: normal;\n" + css_overlay + "\n")
    accepted_legacy = subprocess.run(["bash", "-e", str(harness)], env=env, text=True, capture_output=True)
    require(accepted_legacy.returncode == 0,
            "display-layout restore guard rejected an upgrade from the prior width cap")
    previous_overlay = ('/* DVSwitch-Mods: responsive column alignment and compact header v1.3.3 */ '
                        '.nav #modeInfo > fieldset { margin-top:8px !important; } '
                        'body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > fieldset { margin-top:15px !important; } '
                        'body:has(#dvs-asl-activity:not([hidden])) .nav #modeInfo > span:first-child { position:relative; top:4px; } '
                        '.header { padding:0; } .header h2 { margin:8px 0; } .container {')
    snapshot.write_text("width: 96vw;\nwhite-space: normal;\n" + previous_overlay + "\n")
    current.write_text("width: 96vw;\nwhite-space: normal;\n" + css_overlay + "\n")
    previous_arguments = [
        '"width: 900px;"', '"width: 96vw;"',
        '"width: min(96vw, 1200px);"', '"width: 96vw;"',
        '"white-space: nowrap;"', '"white-space: normal;"',
        shlex.quote(previous_overlay), shlex.quote(css_overlay),
    ]
    harness.write_text(
        die + layout_function + "\ncheck_layout_snapshot_pair \"$CURRENT\" \"$SNAPSHOT\" "
        + " ".join(previous_arguments) + "\n",
        encoding="utf-8",
    )
    accepted_previous_overlay = subprocess.run(
        ["bash", "-e", str(harness)], env=env, text=True, capture_output=True)
    require(accepted_previous_overlay.returncode == 0,
            "display-layout restore guard rejected a v1.3.3-to-v1.3.4 overlay upgrade")
    legacy_overlay = ('/* DVSwitch-Mods: responsive column alignment and compact header v1.3.0 */ '
                      '.nav #modeInfo > fieldset { margin-top:15px !important; } '
                      '.header { padding:0; } .header h2 { margin:8px 0; } .container {')
    snapshot.write_text("width: 96vw;\nwhite-space: normal;\n" + legacy_overlay + "\n")
    previous_arguments = [
        '"width: 900px;"', '"width: 96vw;"',
        '"width: min(96vw, 1200px);"', '"width: 96vw;"',
        '"white-space: nowrap;"', '"white-space: normal;"',
        shlex.quote(legacy_overlay), shlex.quote(css_overlay),
    ]
    harness.write_text(
        die + layout_function + "\ncheck_layout_snapshot_pair \"$CURRENT\" \"$SNAPSHOT\" "
        + " ".join(previous_arguments) + "\n",
        encoding="utf-8",
    )
    accepted_legacy_overlay = subprocess.run(
        ["bash", "-e", str(harness)], env=env, text=True, capture_output=True)
    require(accepted_legacy_overlay.returncode == 0,
            "display-layout restore guard rejected a v1.3.0-to-v1.3.2 overlay upgrade")
    current.write_text(current.read_text() + "/* later component edit */\n")
    refused = subprocess.run(["bash", "-e", str(harness)], env=env, text=True, capture_output=True)
    require(refused.returncode != 0 and "unrelated or customized changes" in refused.stderr,
            "display-layout restore guard accepted a later component edit")

    theme_snapshot = root / "theme-snapshot.php"
    theme_current = root / "theme-current.php"
    theme_snapshot.write_text('''<link href="css/featherlight.css" type="text/css" rel="stylesheet" />
<script src="scripts/featherlight.js" type="text/javascript" charset="utf-8"></script>
''')
    theme_current.write_text('''<link href="css/dvs-theme.css" type="text/css" rel="stylesheet" />
<link href="css/featherlight.css" type="text/css" rel="stylesheet" />
<script src="scripts/featherlight.js" type="text/javascript" charset="utf-8"></script>
    <script src="scripts/dvs-theme.js" type="text/javascript"></script>
''')
    theme_function = function_source(ROOT / "dvswitch-dark-mode.sh", "validate_theme_restore_index")
    theme_harness = root / "theme-check.sh"
    theme_harness.write_text(die + theme_function + '\nvalidate_theme_restore_index "$SNAPSHOT"\n', encoding="utf-8")
    env = os.environ | {"INDEX_FILE": str(theme_current), "SNAPSHOT": str(theme_snapshot)}
    accepted = subprocess.run(["bash", "-e", str(theme_harness)], env=env, text=True, capture_output=True)
    require(accepted.returncode == 0, "dark-mode restore guard rejected its own include edits")
    theme_current.write_text(theme_current.read_text() + "<!-- later component edit -->\n")
    refused = subprocess.run(["bash", "-e", str(theme_harness)], env=env, text=True, capture_output=True)
    require(refused.returncode != 0 and "edits beyond this theme overlay" in refused.stderr,
            "dark-mode restore guard accepted a later component edit")

print("PASS: dark-mode and display-layout snapshot restores reject unrelated dashboard edits")
