#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

"""Ensure the persistence installer recognizes the test35 helper layout."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "install-mode-target-persistence.sh").read_text(encoding="utf-8")


def main() -> None:
    start = INSTALLER.index('python3 - "$MODE_HELPER" <<\'PY\'')
    start = INSTALLER.index("\n", start) + 1
    end = INSTALLER.index("\nPY\n", start)
    patcher = INSTALLER[start:end]
    with tempfile.TemporaryDirectory() as directory:
        helper = Path(directory) / "dvswitch-mode-buttons"
        modern = (
            "#!/usr/bin/env bash\n"
            "TARGET_HELPER=/usr/local/sbin/dvswitch-mode-targets\n"
            'target=$($TARGET_HELPER get "$mode" 2>/dev/null || true)\n'
        )
        helper.write_text(modern, encoding="utf-8")
        result = subprocess.run(
            ["python3", "-c", patcher, str(helper)],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert helper.read_text(encoding="utf-8") == modern

    print("PASS: target-persistence installer accepts the test35 TARGET_HELPER layout unchanged")


if __name__ == "__main__":
    main()
