![Platform](https://img.shields.io/badge/platform-DVSwitch-24527a)
![Debian](https://img.shields.io/badge/tested-Debian%2012%20%7C%2013-a80030)
![Architectures](https://img.shields.io/badge/MMDVM-ARM64%20%7C%20AMD64%20%7C%20i386-blue)
![License](https://img.shields.io/badge/license-GPLv3-green)

:stop_sign:Not required but highly suggested to install my DVSwitch Repairs & Mods Repository 1st. The reason is DVSwitch has many problems that they have not repaired yet, my DVSwitch Repairs & Mods Repository fixes those problems & together with this mod, makes DVSwitch operate like it should have from the begining.
https://github.com/ke2hni/DVSwitch-Mods

# DVSwitch Mode Buttons

## Optional DVSwitch-Mods integration

When DVSwitch-Mods is also installed, the BM/TGIF switch helper optionally
records a timestamped network-selection event through
`/usr/local/sbin/dvswitch-mods-record-dmr-network` for Gateway Activity
labels. The recorder is checked only after a successful DMR switch; its
absence does not affect Mode Buttons installation or switching. Each
repository remains independently installable.

Seven-mode dashboard selection for DVSwitch: **BM · TGIF · STFU · YSF · P25 · NXDN · D-Star**.

## 🚀 Quick start — install everything

### 1. Download the complete repository

Run this from your home directory:

```bash
cd ~ && git clone https://github.com/ke2hni/DVSwitch-Mode-Buttons.git && cd DVSwitch-Mode-Buttons
```

Already downloaded it? Update it instead:

```bash
cd ~/DVSwitch-Mode-Buttons && git pull --ff-only
```

You can also download one ZIP containing the entire repository from the
green **Code** button on GitHub or use the
**[direct ZIP download](https://github.com/ke2hni/DVSwitch-Mode-Buttons/archive/refs/heads/main.zip)**.
Do not download the scripts individually.

### 2. Install or upgrade

Run the installer without arguments to open its three-option menu:

```bash
sudo ./dvswitch-mode-buttons.sh
```

```text
1) Install / upgrade
2) Uninstall
3) Exit
```

Choose **1** to install the buttons or upgrade an existing installation to the current repository version. During that operation, the installer checks the BM and TGIF passwords in `/var/lib/dvswitch/dvs/var.txt`. If the alternate network's password is missing or still `passw0rd`, it prompts for that password and writes it into the generated `MMDVM_Bridge.<MODE>.ini` preset. `A blank password or the unchanged default stops the install as incomplete; it does not claim success or create a preset using the default credential.` The installer then installs the complete tested mode-button path:

- BM/TGIF MMDVM Bridge and Analog Bridge preset switching through the unified mode helper.
- Per-mode target persistence.
- A single-line dashboard control for tuning the active mode to a talkgroup or reflector ID. The field uses the existing `dvswitch.sh tune` command through a dedicated root helper; it does not use or install the separate DVS Mode Switcher application.
- Mode-specific dashboard Favorites. Only the active mode's entries appear beside Tune; **Edit** opens a scrollable popup with a mode selector and instructions. Add a row for a new favorite, edit its name and TG/reflector ID, or select **Delete** to remove a row. Select **Save** to keep the changes for that mode; **Cancel / Close** or Esc closes the editor and discards unsaved changes. Up to 100 favorites can be saved per mode. Selecting a favorite sends its TG/ref through the same Tune control. **+ Favorite** opens the active mode's editor with the current target prefilled. It also looks up the matching friendly name from the source used by that mode's dashboard card. STFU targets use the BrandMeister talkgroup list, matching the STFU card behavior in DVSwitch-Mods, even if the separate DMR Master card currently shows TGIF. Favorites are stored in `/etc/dvswitch-mode-buttons/favorites.json` and remain available after uninstall/reinstall.
- Standalone DMR Master card rendering for BM and TGIF; while STFU, YSF, P25, NXDN, or D-Star is active, it retains the last BM/TGIF talkgroup instead of displaying another mode’s tune ID.
- Friendly-name wrapping inside the DMR card.
- A saved DMR talkgroup that the dashboard updates only while BM or TGIF is active; STFU and other mode IDs never replace it.
- The responsive DVSwitch dashboard layout, using the separate `dvswitch-display-layout.sh` script. The installer runs its read-only check and then its normal apply action during option 1, so the dashboard width is corrected along with the buttons.

The dashboard mode buttons and inline talkgroup/reflector tuner work whether they are installed before or after the
DVSwitch-Mods RX Monitor position modification. If RX Monitor has already moved
to the left status column, the installer places the mode buttons in the vacated
centered area and preserves the relocated RX Monitor control.

The BM/TGIF DMR Master card is self-contained and does not require the
`DVSwitch-Mods` repository. STFU is not treated as a DMR Master network by
this repository; its separate status and activity card is provided by the
independently installable `dashboard-stfu-activity` component in DVSwitch-Mods.
The BM and TGIF card displays the `Room` label, the current network/talkgroup
name in orange, and the `(TG number)` on a separate orange line below the
name so long room labels do not push the card wider.
Selecting STFU leaves the last BM/TGIF card selection intact. STFU talkgroup persistence remains separate and never overwrites the DMR card target.
The label keeps its light-theme color in the standard dashboard. When the
DVSwitch-Mods Dark Mode overlay is installed, its theme stylesheet changes the
label to a readable light color; this works whether Dark Mode is installed
before or after Mode Buttons.

## Requirements

Run from a configured DVSwitch node as root. The installer requires:

```text
/opt/MMDVM_Bridge/MMDVM_Bridge.ini
/opt/MMDVM_Bridge/dvswitch.sh
/opt/Analog_Bridge/Analog_Bridge.ini
/var/lib/dvswitch/dvs/var.txt
/usr/share/dvswitch/index.php
/usr/share/dvswitch/include/status.php
/usr/share/dvswitch/css/css.php
/usr/share/dvswitch/include/lh.php
/usr/share/dvswitch/include/localtx.php
/usr/share/dvswitch/include/system.php
```

BM/TGIF values are read from `var.txt`; missing credentials are requested interactively and never guessed.

## Read-only check

```bash
cd ~/DVSwitch-Mode-Buttons
sudo ./dvswitch-mode-buttons.sh --check
```

`--check` makes no changes. It validates prerequisites, checks that all files required by the bundled display-layout script are present, confirms the dashboard has either the original RX Monitor anchor or the supported DVSwitch-Mods relocated layout, checks the DMR card's connection-state patch target, including the single state-class occurrence used by the current v9 card, and reports whether either network password in `var.txt` is missing or still the default. The tuner submits only validated IDs and invokes a dedicated helper with no command-line arguments; the helper reads the ID from standard input and runs `dvswitch.sh tune`. Favorites are filtered by the live selected mode. The editor's mode selector loads and saves each mode's own list; names and IDs are validated by a root-owned helper, and saves are atomic. For D-Star, YSF, P25, and NXDN, the tune confirmation and target persistence use DVSwitch's live mode when available, avoiding stale mode state after terminal mode changes. DMR submodes continue to use the saved Mode Buttons state. Version 1.0.0-test23 moves the existing RX Monitor button to the left side of the Favorites dropdown row, before Favorites, Edit, and Tune. Version 1.0.0-test24 bundles the existing responsive display-layout script and applies it during option 1; the installer records only layout substitutions it introduced, and uninstall reverses those substitutions without restoring whole dashboard snapshots. Test25 invokes the helper through Python and the layout installer through Bash so installation does not depend on executable bits surviving ZIP extraction. Test26 upgrades the BM/TGIF DMR Master card by recognizing its marked helper functions structurally, so supported v7 card formatting variants migrate without touching the separate STFU card. Favorites remain mode-specific and the editor can switch modes. It upgrades prior test8–test25 controls blocks. The DMR card remains populated with the current talkgroup while BM/TGIF reconnect and labels the network `Connecting` until MMDVM_Bridge reports a successful login; it also uses `$dmrstat` for the `Closing` and `Connection` checks. `--install` explicitly runs the same install/upgrade action as menu option 1. `--uninstall` explicitly runs menu option 2. Installation validates PHP syntax and restarts Apache. The install-order regression tests are `tests/test-rx-monitor-moved-anchor.py` and `tests/test_display_layout_integration.py`. `tests/test-stfu-dashboard-target-snapshot.py` verifies that the saved STFU target is published to the dashboard as a read-only snapshot while canonical target data remains private.

Version 1.0.0-test27 puts the current BM/TGIF talkgroup number on its own line
beneath the friendly room name. Version 1.0.0-test28 prevents STFU target saves
from overwriting the saved BM/TGIF card target and repairs the known older
saved-target mismatch during upgrade. Version 1.0.0-test29 also makes the DMR
card honor the selected STFU button mode before interpreting the bridge's
generic DMR `ambe_mode`; this prevents an STFU tune from being recorded as a
BM/TGIF talkgroup during dashboard refresh. The DMR card retains its last
BM/TGIF selection while another mode is active.

Version 1.0.0-test30 publishes the saved STFU target as a read-only dashboard
snapshot while keeping the canonical per-mode target file root-only. This lets
DVSwitch-Mods show the remembered STFU room after reboot when STFU is not the
currently selected mode. Nodes without the STFU activity card are unaffected.
Version 1.0.0-test31 lets `--check` recognize the current v9 DMR card's
state-aware Connecting row, as well as the older stock Not Connected row. Version
1.0.0-test32 fixes the v9 check to match the single Connecting-state class the
card emits. Version 1.0.0-test33 fixes the STFU target snapshot newline so DMR tuning cannot overwrite or mask the separately retained STFU target. It also keeps STFU selected during dashboard refresh when
Analog_Bridge reports its generic DMR mode, instead of highlighting BM/TGIF.

Version 1.0.0-test34 skips BM/TGIF preset copies and bridge service restarts
when the selected network is already active and both live bridge INI files
match that network's saved presets. It still selects DMR mode and restores the
saved target. If either INI differs, the existing full switch path runs.

Version 1.0.0-test35 uses the selected BM/TGIF network's Analog_Bridge preset
talkgroup when that mode has no saved target yet, and saves that default for
later returns to the same network. An existing mode-specific target takes
priority.

Version 1.0.0-test36 updates the target-persistence installer to recognize the
test35 helper's shared target-helper command, so upgrades can continue without
trying to apply an obsolete patch a second time.

Version 1.0.0-test37 records the selected BM/TGIF target briefly while the
bridge's live ABInfo catches up. During that transition, the DMR Master card
shows the selected DMR target instead of a stale talkgroup from the mode that
was active just before the switch.

Version 1.0.0-test38 writes the selected BM/TGIF target before issuing the DMR
mode command. The DMR Master card honors that short-lived target while the
previous mode is still recorded, avoiding a stale cross-mode talkgroup flash
during the transition.

Version 1.0.0-test40 corrects STFU friendly-name prefill to use the BrandMeister
talkgroup list, matching the STFU card's established lookup behavior.

## Uninstall

```bash
sudo ./dvswitch-mode-buttons.sh
# Select 2) Uninstall
```

Uninstall removes both mode helpers, the target-state helper, tuner helper, endpoint, sudoers entry, dashboard controls block, presets, and saved state. If an older standalone DMR helper was backed up before consolidation, uninstall restores it. Before removing runtime files, it backs up the dashboard and bridge files and surgically removes only structurally recognized Mode Buttons changes from `index.php`, `status.php`, and `dvswitch.sh`. It also reverts only the responsive width/style substitutions first introduced by Mode Buttons, preserving other content in the five dashboard files. DMR rows are restored to the DVSwitch-Mods implementation when its helper is present, or to the factory rows otherwise. It never restores a whole-file snapshot over changes another installer made. If an owned block is incomplete or ambiguous, uninstall stops before changing shared files or removing helpers.

## Installed state and backups

```text
/etc/dvswitch-mode-buttons/dmr-presets/
/usr/local/sbin/dvswitch-mode-buttons
/usr/local/sbin/dvswitch-mode-targets
/usr/local/sbin/dvswitch-mode-tune
/usr/local/sbin/dvswitch-mode-favorites
/usr/share/dvswitch/dvswitch-mode-favorites.js
/usr/local/sbin/dvswitch-dmr-network -> /usr/local/sbin/dvswitch-mode-buttons (compatibility link)
/var/lib/dvswitch-mode-buttons/
/var/lib/dvswitch-mode-buttons/last-dmr-talkgroup (root-owned, Apache group-writable saved DMR target)
/var/lib/dvswitch-mode-buttons/display-layout-owned.json (layout edits owned by this installation)
/var/backups/dvswitch-mode-buttons/
```

The repository keeps `dvswitch-display-layout.sh` as a separate installer script. It updates `index.php`, `css/css.php`, `include/lh.php`, `include/localtx.php`, and `include/system.php`; the ownership helper stores the specific substitutions made by the Buttons install.

`/etc/dvswitch-mode-buttons/favorites.json` contains separate favorites for BM, TGIF, STFU, YSF, P25, NXDN, and D-Star. Each mode's list is alphabetized by favorite name when saved, with each target ID kept with its name. The installer copies the repository's example `favorites.json` there when the file does not already exist, so the dropdown and Edit screen have sample entries on first install. Upgrades preserve an existing file, and uninstall retains it so a reinstall does not erase the user's lists. Edit or remove the sample entries to match the reflectors and talkgroups you use.

The BM/TGIF network-switch code now lives in the same installed mode helper; the old DMR helper path remains as a compatibility symlink. `dvswitch-mode-targets` remains a separate runtime command because the patched `dvswitch.sh tune` path invokes it directly to save and retrieve targets. The state directory is `755` so Apache can read the card state. The saved DMR target is owned by `root:www-data` with mode `664`, allowing the status page to retain the live DMR talkgroup when the active mode changes. `mode-targets.json` remains private at `600`.

## Safety boundaries

This repository is for a fresh install of DVSwitch which should be configured before installing this repository. This was tested on the following hardware, Raspberry Pi 4 with Dedian 12 (Bookworm) using the last supplied ASL 3 image containing Debian 12 (Bookworm), Raspberry Pi 5 with Dedian 13 (Trixie) using the last supplied ASL 3 image containing Debian 13 (Trixie), Dell Wyse 3040 with Debian 12 (Bookworm). It does not require DVSwitch-Mods to be installed but it is Highly Suggested.

Tested in this order:

```text
pi4test → pi5test → node3040
```

Production testing requires explicit authorization.

## License

See [LICENSE](LICENSE).


<img width="1600" height="852" alt="Screenshot 2026-09-28 223729" src="https://github.com/user-attachments/assets/2dd939b1-a8e2-4071-bfc8-5031b00946d3" />
<img width="1600" height="852" alt="Screenshot 2026-09-28 223748" src="https://github.com/user-attachments/assets/264c340e-9fb7-46af-a9b9-b6f397e107e0" />
<img width="1600" height="852" alt="Screenshot 2026-09-28 223805" src="https://github.com/user-attachments/assets/396a44b9-c021-46c6-9d7c-7c18233d2436" />
<img width="1600" height="852" alt="Screenshot 2026-09-28 223821" src="https://github.com/user-attachments/assets/0b964808-9991-4e91-b399-03bf880682a0" />
<img width="1600" height="852" alt="Screenshot 2026-09-28 235146" src="https://github.com/user-attachments/assets/d6d39e06-4e59-4ae4-95d9-711fe6f75947" />

# Optional DVSwitch-Mods integration

When the separate DVSwitch-Mods repository is installed, the BM/TGIF switch
helper optionally records a timestamped network-selection event through
`/usr/local/sbin/dvswitch-mods-record-dmr-network`. This supports accurate
Gateway Activity labels. The recorder is checked only after a successful DMR
switch; its absence does not affect Mode Buttons installation or switching.

Version 1.0.0-test41 adds D-Star friendly-name lookup from the Pi-Star REF, XRF, DCS, and XLX host files. Module-qualified targets such as `Ref024cl` resolve to the reflector's friendly name.

Version 1.0.0-test42 handles D-Star favorite names without treating hostfile IP addresses as friendly names. It formats a module-qualified tune target such as `ref024cl` as `REF024 C`, matching the D-Star target label displayed on the dashboard.

Version 1.0.0-test43 widens the tune entry field from 10 to 12 character units so module-qualified D-Star targets fit more comfortably.

Version 1.0.0-test44 installs the repository's example `favorites.json` when no favorites file exists yet. It provides starter entries for each supported mode so the dropdown and Edit screen have examples immediately. Reinstalling or upgrading preserves an existing favorites file.

Version 1.0.0-test45 opens the Favorites editor in a scrollable popup and explains how to add, edit, delete, save, and cancel entries. The installer upgrades the previous test44 inline editor in place.

Version 1.0.0-test46 saves each mode's favorites alphabetically by name while keeping the target ID associated with its entry. Run `python3 tests/test_favorites_sort.py` to verify the ordering.

Version 1.0.0-test47 makes the Favorites editor's **Cancel or Esc** instruction bold, labels the button **Cancel / Close**, and states that closing discards unsaved changes. The installer upgrades existing test45 and test46 dashboard controls in place.

Version 1.0.0-test48 raises the per-mode favorites limit from 30 to 100 in both the editor and save handler. The installer upgrades existing test47 dashboard controls in place.
