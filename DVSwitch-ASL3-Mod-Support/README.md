# DVSwitch ASL 3 Mod Support

Repository: <https://github.com/ke2hni/DVSwitch-Fixes-Upgrades>

This optional component adds ASL 3 support to the combined DVSwitch repository. Manager menu option 6 installs it. ASL 3 must be installed, and the DVSwitch dashboard files must be present. If Mode Buttons is already installed, this installer refreshes its dashboard controls without entering the DMR preset setup. Otherwise, install Mode Buttons later with manager option 2.

It conditionally adds the ASL mode button when Mode Buttons is installed, uses numeric node numbers for Tune and Favorites, changes the Analog_Bridge target label to `Node` while ASL is selected, and adds an **ASL Net** card to the dashboard's left status column alongside the other network cards. The card reads live established peers from the configured local public node and shows friendly names from `/var/lib/asterisk/astdb.txt` (falling back to `/var/lib/asterisk/astdb`), so stale event records do not keep a remote node displayed after reboot. When no remote node is connected, it shows `Listening`. The ASL Gateway Activity section also reads live peers and lists only nodes that are currently connected; it does not retain past connect/disconnect events. ASL link commands use the local public node discovered from `rpt.conf`; selecting ASL establishes and verifies the private USRP-to-public bridge if it is down. Disconnect All and leaving ASL disconnect external peers individually while preserving that bridge when present. Node IDs are read from each unit's configuration, never fixed values. When ASL is selected, five checkbox link actions appear: Connect, Disconnect, Monitor, Local Monitor, and Disconnect All. The installer refuses ambiguous node layouts or existing custom hooks and restores `rpt.conf` if installation fails. It repairs ASL-to-digital mode changes in `dvswitch.sh` versions
1.6.2 and 1.6.3. The patch routes Analog_Bridge remote-control commands to a
live TLV UDP listener, which avoids using stale listener-port information.

If ASL 3 is not installed, the support installer reports `SKIP` without making
changes, so the DVSwitch tools continue to work without ASL. Run the check
first, then install:

```bash
cd ~/DVSwitch-Fixes-Upgrades/DVSwitch-ASL3-Mod-Support
sudo ./dvswitch-asl3-mod-support.sh --check
sudo ./dvswitch-asl3-mod-support.sh --install
```

`--check` makes no changes and reports a clean skip when ASL 3 is absent.
`--install` creates a protected timestamped backup before updating the
dashboard and the installed `dvswitch.sh`. It validates the patch and rolls
dashboard files back automatically if an installation step fails. Apache is restarted to load the dashboard changes. The installer does not reload Asterisk. After installing, run `sudo asterisk -rx "module reload app_rpt.so"` to activate the ASL link activity hooks from `rpt.conf`. Dashboard backups are stored under
`/var/backups/dvswitch-mods/asl3-support/`. The standalone mode-switch repair
keeps its own backups under `/var/backups/dvswitch-mods/asl-mode-switch/` and
supports `--restore BACKUP-NAME`.

The patchers reject unsupported versions and dashboard structures without
changing installed files. The ASL node check requires one USRP private node and
one other configured node; it refuses ambiguous layouts. From the combined repository root, run
`python3 DVSwitch-ASL3-Mod-Support/tests/test-dvswitch-asl-mode-switch-patcher.py`
and `python3 DVSwitch-ASL3-Mod-Support/tests/test-asl3-dashboard-layout.py` to
check the mode-switch repair and dashboard layout patch.
