#!/usr/bin/env python3
"""Exercise widescreen card layout installation and guarded restoration."""
# Version: 1.0.0; Created: 2026-11-15T17:40:00Z by KE2HNI
from pathlib import Path
import os
import subprocess
import tempfile

MODS = Path(__file__).resolve().parents[1]
SCRIPT = MODS / "dvswitch-display-layout.sh"
ASSET = MODS / "dvswitch-display-layout.js"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


with tempfile.TemporaryDirectory(prefix="dvs-display-layout-") as temp:
    root = Path(temp) / "dashboard"
    root.mkdir()
    script_dir = Path(temp) / "installer"
    script_dir.mkdir()
    script_copy = script_dir / SCRIPT.name
    source = SCRIPT.read_text(encoding="utf-8")
    source = source.replace('ROOT="/usr/share/dvswitch"', f'ROOT="{root}"')
    source = source.replace('LOG_FILE="$HOME/dvs-dashboard-display-$STAMP.log"', f'LOG_FILE="{root}/layout.log"')
    source = source.replace('need_root(){\n  if [ "$(id -u)" -ne 0 ]; then\n    die "Run with sudo."\n  fi\n}', 'need_root(){ :; }')
    script_copy.write_text(source, encoding="utf-8")
    asset_copy = script_dir / ASSET.name
    asset_copy.write_bytes(ASSET.read_bytes())
    script_copy.chmod(0o755)

    paths = {
        "index.php": "index.php",
        "css.php": "css/css.php",
        "lh.php": "include/lh.php",
        "localtx.php": "include/localtx.php",
        "system.php": "include/system.php",
    }
    initial = {
        "index.php": '<table style="border:none; border-collapse:collapse; cellspacing:0; cellpadding:0; background-color:#fafafa;"><tr><td valign="top" style="border:none; height: 480px; background-color:#fafafa; width:100%;"></td></tr></table>\n</body>\n',
        "css.php": '.container { width: 900px; white-space: nowrap; }\nwidth : 185px;\n',
        "lh.php": 'width:640px;\n',
        "localtx.php": 'width:640px;\n',
        "system.php": 'width:855px;margin-left:6px;margin-right:0px\n',
    }
    for name, content in initial.items():
        target = root / paths[name]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def run(action: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", str(script_copy), action], text=True, capture_output=True)

    result = run("apply")
    require(result.returncode == 0, f"apply failed: {result.stdout}\n{result.stderr}")
    index = (root / "index.php").read_text(encoding="utf-8")
    require(index.count("display-layout-columns v1.3.8") == 1, "index hook marker missing or duplicated")
    require(index.count("dvswitch-display-layout.js") == 1, "index script tag missing or duplicated")
    require((root / "dvswitch-display-layout.js").read_bytes() == ASSET.read_bytes(), "layout JS asset not installed exactly")
    js = (root / "dvswitch-display-layout.js").read_text(encoding="utf-8")
    require("dvswitch-m17-audio" not in js and "toggleM17Audio" not in js, "generic display layout depends on M17 audio")

    result = run("restore-latest")
    require(result.returncode == 0, f"restore-latest failed: {result.stdout}\n{result.stderr}")
    require(not (root / "dvswitch-display-layout.js").exists(), "restore-latest left a newly installed JS asset")
    for name, content in initial.items():
        require((root / paths[name]).read_text(encoding="utf-8") == content, f"restore-latest failed to restore {name}")

    preexisting_asset = "/* pre-existing dashboard script */\n"
    (root / "dvswitch-display-layout.js").write_text(preexisting_asset, encoding="utf-8")
    result = run("apply")
    require(result.returncode == 0, f"apply with a pre-existing asset failed: {result.stdout}\n{result.stderr}")
    result = run("restore-latest")
    require(result.returncode == 0, f"restore-latest with a pre-existing asset failed: {result.stdout}\n{result.stderr}")
    require((root / "dvswitch-display-layout.js").read_text(encoding="utf-8") == preexisting_asset,
            "restore-latest did not restore the pre-existing JavaScript asset")

    result = run("apply")
    require(result.returncode == 0, f"second apply failed: {result.stdout}\n{result.stderr}")
    (root / "dvswitch-display-layout.js").write_text("/* user customization */\n", encoding="utf-8")
    result = run("restore-original")
    require(result.returncode != 0 and "JavaScript was changed" in result.stdout + result.stderr,
            "restore-original overwrote a customized layout JavaScript asset")
    (root / "dvswitch-display-layout.js").write_bytes(ASSET.read_bytes())
    result = run("restore-original")
    require(result.returncode == 0, f"restore-original failed after removing the user edit: {result.stdout}\n{result.stderr}")
    require(not (root / "dvswitch-display-layout.js").exists(), "restore-original left the newly installed JS asset")

print("PASS: widescreen installer adds generic side-card layout and safely restores its hook and asset")
