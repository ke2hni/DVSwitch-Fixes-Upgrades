# DVSwitch Fixes & Upgrades

<!-- Version: 1.0.2; Created: 2026-10-25T18:39:04-04:00; Created by KE2HNI -->

A combined repository for independently installable DVSwitch repairs, dashboard modifications, ASL 3 support, and M17 private-node switching support.

## Repository layout

- `DVSwitch-Mods/` contains the standard repair and modification manager, its standalone Dark Mode and Widescreen Display Layout installers, component scripts, tests, and detailed project documentation.
- `DVSwitch-Mode-Buttons/` contains the dashboard mode controls, favorites editor, helpers, installer, tests, and detailed project documentation.
- `DVSwitch-ASL3-Mod-Support/` contains optional ASL 3 support, the ASL-to-digital mode-switch repair, dashboard support, and its own checks and documentation. It detects ASL 3 first and skips cleanly when ASL is absent.
- `DVSwitch-M17-Support/` contains the `m17` and `dvs-dvswitch` commands for switching the public ASL node between M17 and DVSwitch private USRP nodes.

The projects stay in separate directories. They contain files with the same names, including `README.md` and `LICENSE`; keeping each project intact in its own directory prevents collisions. Their installation state and backups remain separately managed. Mode Buttons can optionally use the DVSwitch-Mods network-history helper when installed, and continues to work without it. ASL 3 Support skips cleanly when ASL is not installed.

## Quick start

After creating the GitHub repository `ke2hni/DVSwitch-Fixes-Upgrades`, clone it on a configured DVSwitch node:

```bash
cd ~ && git clone https://github.com/ke2hni/DVSwitch-Fixes-Upgrades.git && cd DVSwitch-Fixes-Upgrades
```

Start the combined manager:

```bash
sudo ./DVSwitch-Mods/manage-dvswitch-mods.sh
```

Update Existing Local Repository Folder

```bash
cd DVSwitch-Fixes-Upgrades && git pull --ff-only
```

The menu offers:

1. Install or upgrade all standard DVSwitch repairs and modifications,
   including the STFU logrotate restart repair.
2. Launch the DVSwitch Mode Buttons installer menu.
3. Launch the Dark Mode dashboard installer.
4. Launch the Widescreen Display Layout installer.
5. Uninstall all manager-recorded standard components.
6. Install ASL 3 Support (ASL 3 must be installed; if multiple private USRP
   nodes exist, select the node number used for DVSwitch).
7. Install M17 private-node switch commands.
0. Exit.

Install or upgrade ASL 3 Support with option 6 before using option 7.

Option 5 only uninstalls components recorded by the DVSwitch-Mods manager. The Mode Buttons, Dark Mode, and Widescreen installers keep their own install and restore workflows; use their own uninstall or restore instructions when needed.

The projects can also be used independently from their respective directories. For Mode Buttons, run `sudo ./dvswitch-mode-buttons.sh` from `DVSwitch-Mode-Buttons/`. For the DVSwitch-Mods manager, run `sudo ./manage-dvswitch-mods.sh` from `DVSwitch-Mods/`; its Mode Buttons, ASL 3, and M17 menu choices require their sibling directories to be present.

## Project documentation

- [DVSwitch-Mods README](DVSwitch-Mods/README.md)
- [DVSwitch-Mods testing notes](DVSwitch-Mods/TESTING.txt)
- [DVSwitch-Mode-Buttons README](DVSwitch-Mode-Buttons/README.md)
- [DVSwitch-ASL3-Mod-Support README](DVSwitch-ASL3-Mod-Support/README.md)
- [DVSwitch-M17-Support README](DVSwitch-M17-Support/README.md)

Each subproject contains its own license and tests. Review its README and safety notes before installing on a node.

## Default DVSwitch Dashboard Design & Layout
<img width="1600" height="900" alt="Screenshot 2026-10-25 195335" src="https://github.com/user-attachments/assets/df7ccb60-8dc8-4de8-8794-d7db53535efa" />

## Upgraded DVSwitch Dashboard Design & Layout
<img width="1600" height="900" alt="Screenshot 2026-10-25 202336" src="https://github.com/user-attachments/assets/f2166c94-49d4-4c6c-9b41-d4ee86d395cc" />
<img width="1600" height="900" alt="Screenshot 2026-10-25 202342" src="https://github.com/user-attachments/assets/5208d1e9-523a-4e0a-b11a-a0fec70c74d2" />
<img width="1600" height="900" alt="Screenshot 2026-10-25 203014" src="https://github.com/user-attachments/assets/8a633877-ce14-407d-b7b8-fb434ff56a7f" />
<img width="1600" height="900" alt="Screenshot 2026-11-01 161240" src="https://github.com/user-attachments/assets/b8a0fae4-822d-43cc-8da2-0fad51693052" />
<img width="1600" height="900" alt="Screenshot 2026-11-01 161224" src="https://github.com/user-attachments/assets/b0edf98a-fc09-4991-be26-4c18e14d1aca" />
<img width="1600" height="900" alt="Screenshot 2026-11-01 161054" src="https://github.com/user-attachments/assets/37c09afe-84df-49c3-8d5e-58d939dc533f" />

