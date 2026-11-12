# DVSwitch Test Node Uninstaller

<!-- Version: 1.0.0; Created: 2026-11-12T15:45:00Z; Created by KE2HNI -->

This tool is intended for test nodes only. It removes the repository's recorded
DVSwitch-Mods components, Mode Buttons, ASL dashboard add-on, M17 dashboard and
bridge support, plus a fixed allowlist of DVSwitch packages and /opt
application directories. It retains Debian, ASL 3/Asterisk, Allmon3, shared
MMDVM database files other than the repository's M17 reflector catalog, and all
backup directories.

## Review first

Run the read-only plan:

```bash
cd ~/DVSwitch-Fixes-Upgrades
sudo bash ./uninstall-dvswitch-test-node.sh --plan
```

Check the host name, ASL snapshot, installed package list, and application
directories. The uninstaller refuses if ASL 3 is not installed or if it finds
public node 68425 in /etc/asterisk/rpt.conf.

## Remove

After reviewing the plan, start removal:

```bash
sudo bash ./uninstall-dvswitch-test-node.sh --remove
```

It requests the short host name as confirmation. The separate apt-get purge
step also asks APT to confirm the package changes. It never runs autoremove.
The repo-owned /opt application trees and saved favorites/state/catalog data
are archived under /var/backups/dvswitch-mods/repo-uninstall/ before removal.
Installer backups are retained.

The ASL support add-on is restored from its latest recorded install snapshot.
The current versions of those files are saved first under
/var/backups/dvswitch-mods/repo-uninstall/. If the ASL snapshot is missing or
incomplete, removal stops rather than guessing how to edit Asterisk or shared
dashboard configuration.

The tool does not remove Asterisk, ASL 3 packages, Debian packages unrelated to
the explicit DVSwitch allowlist, Allmon3, shared MMDVM data, or user files
outside its listed paths. It is not a substitute for reinstalling Debian if
the node has unrelated modifications.
