# DVSwitch ASL 3 Mod Support

Repository: <https://github.com/ke2hni/DVSwitch-Fixes-Upgrades>

This optional component adds ASL 3 support to the combined DVSwitch repository. Manager menu option 6 installs it. ASL 3 and the DVSwitch dashboard must be present. ASL Support owns its ASL mode button, node tuner, link actions, favorites, mode-switch repair, and dashboard cards. It works whether Mode Buttons is installed or not; Mode Buttons provides only the standard digital modes.

It adds its own ASL mode button alongside Mode Buttons when present, or as a standalone ASL control when Mode Buttons is absent. Its numeric node tuner and ASL favorites are owned and stored by ASL Support. The Analog_Bridge target label changes to `Node` while ASL is selected, and an **ASL Net** card to the dashboard's left status column alongside the other network cards. The card reads live established peers from the configured local public node and shows friendly names from `/var/lib/asterisk/astdb.txt` (falling back to `/var/lib/asterisk/astdb`). A saved favorite name overrides the database label, so users can set a short or custom name. Stale event records do not keep a remote node displayed after reboot. When no remote node is connected, it shows `Listening`.

The ASL dashboard script manages only the ASL button's selected state. Standard-mode selection remains with Mode Buttons, so Analog_Bridge's internal `YSFN`/`YSFW` labels cannot clear the `YSF` button highlight.

The **ASL Gateway Activity** section uses the same nine columns as Gateway Activity and lists only currently established external nodes. Its third heading is `Node`. It reads the public node's `XStat` and `SawStat` AMI status, following Allmon3's keying detection for RX, TX, and connected-node PTT. It uses local dashboard time, node IDs and ASTDB friendly names; duration comes from the keyed-link timer or the dashboard's observed keying interval. ASL does not provide the Gateway Activity Loss/BER measurements, so those cells show `0%` and `0.0%`. Keying status uses the local public node's manager credentials from `/etc/allmon3/allmon3.ini`. If that local Allmon3 entry is unavailable, the card still lists live links and marks keying status unavailable.

For HTTPS dashboards, RX Monitor uses a same-origin secure WebSocket route through Apache to the existing Web Proxy on port 8080. This avoids browsers blocking the dashboard's former insecure `ws://` audio connection.

The ASL receive-audio path is internet node → local public ASL node → private ASL node → Asterisk USRP channel → Analog_Bridge `[USRP]` `rxPort` → Web Proxy PCM on `pcmPort` → dashboard RX Monitor. When Mode Buttons is installed, its BM/TGIF network presets update the Analog_Bridge network settings while preserving its live USRP `txPort`/`rxPort` pair, so a DMR network change cannot undo the ASL audio pairing.

ASL link commands use the local public node discovered from `rpt.conf`; selecting ASL establishes and verifies the private-to-public ASL link if it is down. Disconnect All and leaving ASL disconnect external peers individually while preserving that bridge when present. Node IDs and USRP ports are read from each unit's configuration, never fixed values. The installer checks the private node's `USRP/address:remote-port:local-port` channel against `/opt/Analog_Bridge/Analog_Bridge.ini`; when they differ, it backs up the file, sets Analog_Bridge `rxPort` to the Asterisk remote port and `txPort` to its local port, then restarts Analog_Bridge to apply the pairing. When ASL is selected, the ASL-owned node tuner and five checkbox link actions appear in a compact box sized to fit: Connect, Disconnect, Monitor, Local Monitor, and Disconnect All. A separate **Disconnect before Connect** checkbox is checked by default. When enabled, Connect disconnects each external peer on the public node, waits for those links to clear, preserves the private-to-public bridge, and then connects the entered node. The option affects Connect only. Tune requires one link action to be checked; with none checked it sends no link command. The Analog Bridge `Node` label remains in place during the dashboard status refresh, and its value follows the currently connected external node IDs. The installer refuses ambiguous node layouts or existing custom hooks and restores `rpt.conf` and Analog_Bridge.ini if installation fails. It repairs ASL-to-digital mode changes in `dvswitch.sh` versions
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

`--check` makes no changes, reports a clean skip when ASL 3 is absent, identifies a private-node/Analog_Bridge USRP port mismatch, and checks whether Allmon3 keying status is available. Missing Allmon3 telemetry is a notice; it does not block ASL support. `--install` creates a protected timestamped backup before updating the dashboard, matching the USRP ports when needed, configuring the secure Web Proxy route, and repairing the installed `dvswitch.sh`. It validates the patch and rolls files back automatically if an installation step fails. Analog_Bridge restarts only when its USRP ports need correction; Apache restarts to load dashboard and WebSocket proxy changes. The installer does not reload Asterisk. After installing, run `sudo asterisk -rx "module reload app_rpt.so"` to activate the ASL link activity hooks from `rpt.conf`. Dashboard and Analog_Bridge backups are stored under
`/var/backups/dvswitch-mods/asl3-support/`. The standalone mode-switch repair
keeps its own backups under `/var/backups/dvswitch-mods/asl-mode-switch/` and
supports `--restore BACKUP-NAME`.

The 1.0.3 mode-switch repair reads candidate TLV ports once per `dvswitch.sh`
command and caches a live listener snapshot owned by Analog_Bridge. It ignores
same-port sockets owned by MMDVM_Bridge and refreshes the snapshot after an
`rxport` change. It also disconnects external ASL peers before any mode change
leaves ASL, preserving the private-to-public bridge and blocking the change if
external links could not be cleared.

The patchers reject unsupported versions and dashboard structures without
changing installed files. The ASL node check requires one USRP private node and
one other configured node; it refuses ambiguous layouts. From the combined repository root, run
`python3 DVSwitch-ASL3-Mod-Support/tests/test-dvswitch-asl-mode-switch-patcher.py`
and `python3 DVSwitch-ASL3-Mod-Support/tests/test-asl3-dashboard-layout.py` to
check the mode-switch repair and dashboard layout patch.

Version 1.0.1 checks for link and private-bridge state every 250ms while
preserving the existing ten-second verification limit. This reduces the delay
between Asterisk clearing a link and DVSwitch continuing its mode change.

The ASL node-link helper version 1.0.2 verifies Connect requests in
`rpt lstats` on the discovered public node and reports success only when the
requested external node reaches `ESTABLISHED`. It allows up to 30 seconds for
the remote connection and reports an error if the link does not establish.

Dashboard script version 1.0.1 restores short action-based link messages, such
as `Connected to Node 55553`. Its ASL selection clears digital highlights
without clearing its own selected state, including when the button shares the
Mode Buttons row. Version 1.0.2 keeps the RX Monitor button visible in ASL mode
when Mode Buttons hides its Favorites row, and restores it to that row for
digital modes. Version 1.0.4 follows the pre-move transition behavior: a digital
button click does not hide the ASL panel early. The panel changes after the
Mode Buttons command succeeds, and stale ASL status is ignored until the bridge
reports the requested mode. Version 1.0.5 places RX Monitor beside ASL's
Favorites/Tune controls and restores it beside the Mode Buttons controls in
digital modes. Version 1.0.6 keeps a successful digital-mode selection
authoritative while the Analog_Bridge status row still reports stale ASL; the
old 30-second timeout no longer reverts the dashboard to ASL after a successful
switch.
Version 1.0.7 restores the pre-transfer mode source: when Mode Buttons is
installed, ASL Support reads its completed-mode status endpoint instead of
letting a stale Analog_Bridge `Mode` row overwrite the selected mode. If Mode
Buttons is absent, ASL Support falls back to the dashboard row and remains
standalone.
