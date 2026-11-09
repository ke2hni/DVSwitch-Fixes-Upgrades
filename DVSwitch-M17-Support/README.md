# DVSwitch M17 Private-Node Switching Support

<!-- Version: 1.1.0; Created: 2026-11-09T00:41:12-05:00; Created by KE2HNI -->

This component provides two commands for an ASL node that has an M17 USRP private-node stanza and DVSwitch's Analog_Bridge private-node stanza:

- `m17` disconnects other private USRP links from the public ASL node, then connects the configured M17 private node.
- `dvs-dvswitch` disconnects other private USRP links, then connects the explicitly selected DVSwitch private node.

The commands switch only the local private-node links. They do not install an M17 reflector client, create the M17 Asterisk stanza, or select reflector destinations. The install script prompts for the M17 private node number (default `1972`); the value is stored in `/etc/dvswitch-m17-support.conf`. It installs `/usr/local/bin/m17` and `/usr/local/bin/dvs-dvswitch` as symlinks to root-owned command files.

The shared ASL node helper must be updated to multi-private-node support before this component can be used. Run manager option 6 first; it asks which private node number is used for DVSwitch and its Analog_Bridge connection to the public ASL node, then saves that choice in `/etc/dvswitch-asl3-support/private-node`. Then choose option 7 to install these commands. From the repository root, run `sudo ./DVSwitch-ASL3-Mod-Support/dvswitch-asl3-mod-support.sh --select-private-node`, then use the returned node number with `--check NODE` and `--install NODE`, followed by the M17 installer's `--check` and `--install`. The M17 installer backs up its config, command links, and wrappers under `/var/backups/dvswitch-mods/m17-private-node-switch/` before installing. It does not modify `rpt.conf`, Analog_Bridge settings, or the M17 service.

The install output identifies the backup folder. Restore it from the combined repository root with `sudo ./DVSwitch-M17-Support/dvswitch-m17-support.sh --restore install-YYYYMMDD-HHMMSS`; pass the actual folder name reported by your installer. Restore also saves the current files to a `pre-restore-*` recovery folder.

Run `sudo PYTHONDONTWRITEBYTECODE=1 python3 DVSwitch-M17-Support/tests/test-m17-support-installer.py` from the combined repository root to exercise the installer's check, fresh-install, upgrade, already-installed, partial-install resume, restore, and collision-guard paths in a temporary tree.
