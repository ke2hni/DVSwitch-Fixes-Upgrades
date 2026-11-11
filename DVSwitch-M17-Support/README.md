# DVSwitch M17 Private-Node Switching Support

<!-- Version: 1.3.8; Created: 2026-11-09T00:41:12-05:00 by KE2HNI; Updated: 2026-11-11T14:00:00-05:00 by KE2HNI — equalize side gaps around activity and align the right-card outer edge. -->

This component provides two commands for an ASL node that has an M17 USRP private-node stanza and DVSwitch's Analog_Bridge private-node stanza:

- `m17` disconnects other private USRP links from the public ASL node, then connects the configured M17 private node.
- `dvs-dvswitch` disconnects other private USRP links, then connects the explicitly selected DVSwitch private node.

The commands switch only the local private-node links. They do not install an M17 reflector client, create the M17 Asterisk stanza, or select reflector destinations. The install script prompts for both private node numbers (M17 defaults to `1972`); both values are stored in `/etc/dvswitch-m17-support.conf`. It installs `/usr/local/bin/m17` and `/usr/local/bin/dvs-dvswitch` as symlinks to root-owned command files.

M17 Support owns its node selection and switch helper; it does not require ASL 3 Support or Mode Buttons to be installed. Option 7 asks for the M17 and DVSwitch private node numbers, then installs an M17-owned helper that switches the public ASL node exclusively between them, preventing private-node audio crossfeed. It reads the installed `/etc/asterisk/rpt.conf` and disconnects other private USRP links before connecting the selected node. The installer backs up its config, command links, helper, and wrappers under `/var/backups/dvswitch-mods/m17-private-node-switch/`.

The install output identifies the backup folder. Restore it from the combined repository root with `sudo ./DVSwitch-M17-Support/dvswitch-m17-support.sh --restore install-YYYYMMDD-HHMMSS`; pass the actual folder name reported by your installer. Restore also saves the current files to a `pre-restore-*` recovery folder.

Run `sudo PYTHONDONTWRITEBYTECODE=1 python3 DVSwitch-M17-Support/tests/test-m17-support-installer.py` and `python3 DVSwitch-M17-Support/tests/test-m17-exclusive-node-switch.py` from the combined repository root to exercise the installer's check, fresh-install, upgrade, already-installed, partial-install resume, restore, and collision-guard paths in a temporary tree.

## Full USRP2M17 bridge installation

The command installer above only installs the mode-switch commands. To install the actual M17 network bridge, choose manager option 8 directly; the bridge installer asks which private node is used by DVSwitch and which separate private node is used by M17. The new interactive installer downloads and builds USRP2M17 from the upstream nostar/MMDVM_CM GitHub repository, asks for the M17 node number and port assignments, configures the reflector and Asterisk private node, and creates a systemd service. It also installs or updates the independent M17/DVSwitch exclusive-switch commands.

Follow [INSTALL-USRP2M17.md](INSTALL-USRP2M17.md) for the complete first-time instructions, verification commands, and uninstall procedure. The interactive installer can also be run directly from the combined repository root with `sudo ./DVSwitch-M17-Support/dvswitch-m17-bridge.py`.

## M17 dashboard integration

After USRP2M17 and the M17 private-node commands are installed, choose manager option 9 and select **Install or upgrade M17 dashboard support**. Option 9 is independent of DVSwitch Mode Buttons (option 2): with Mode Buttons installed, M17 uses its shared toolbar and favorites editor; without it, this component supplies its own M17 button, tuning controls, and editable favorites. You can install option 2 before or after option 9. If the bridge was installed before this dashboard release, run manager option 8 and choose **Install or upgrade USRP2M17** once so the bridge logs include callsigns for activity history. The dashboard adds an M17 Net card and M17 events in Gateway Activity and Local Activity. Reflectors are downloaded from the M17 Project's `M17Hosts.json` catalog weekly; catalog refreshes do not rewrite editable favorites. Initial favorites are seeded once with one entry per usable reflector (module A when available, otherwise its first M17 module), and subsequent edits and deletions are kept. To use another module, tune with a `reflector-module` target (for example `URF018-B`) and save it as a favorite.

The install-state directory is set to mode `0755` so Apache can test whether M17 dashboard support is installed and show the M17 mode button in the shared toolbar. The install-state file remains root-only (`0600`). When the shared toolbar is absent, the M17-owned dashboard script renders a standalone M17 control row instead.

When M17 is the selected dashboard mode, the Analog Bridge Info card shows `M17` and the configured M17 reflector/module in its visible mode and target rows. The diagnostic tooltip continues to show Analog_Bridge's actual telemetry.

Selecting a favorite updates `/etc/USRP2M17.ini` and restarts `usrp2m17.service`. Selecting the already-active room does not restart it. The installer makes a dated config backup for each reflector change and restores the prior config if the service fails to restart. M17 uses the private node already configured by manager option 8, and the mode button switches the public node between the selected M17 and DVSwitch private links.

Uninstall dashboard support with manager option 9 and select **Uninstall M17 dashboard support**. This removes its card/history hooks, M17 controls, catalog timer, and dashboard helpers. It preserves USRP2M17, the M17 configuration, reflector catalog, and user favorites.


The M17 dashboard layout places the eight network cards in alphabetical order around Gateway Activity. Each network card keeps a rounded panel outline matching Analog Bridge Info. The first three cards sit in the left status sidebar below Analog Bridge Info and TRX Info; M17 Net and the remaining four cards sit in the right column. Gateway Activity and Local Activity share the same centered width, with equal gaps to the left and right card columns. The side status cards are inset from the dashboard border to match the Networks and Hardware Info panels. Refreshed status data replaces old card renders without making the cards flash or accumulate copies. Mode buttons are alphabetized, and M17 reflector text matches the other cards’ orange label color.
