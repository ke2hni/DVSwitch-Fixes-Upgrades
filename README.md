# DVSwitch Fixes & Upgrades

A combined repository for the independently installable DVSwitch repairs and dashboard modifications from **DVSwitch-Mods** and **DVSwitch-Mode-Buttons**.

## Repository layout

- `DVSwitch-Mods/` contains the standard repair and modification manager, its standalone Dark Mode and Widescreen Display Layout installers, component scripts, tests, and detailed project documentation.
- `DVSwitch-Mode-Buttons/` contains the dashboard mode controls, favorites editor, helpers, installer, tests, and detailed project documentation.
- `DVSwitch-ASL3-Mod-Support/` contains optional ASL 3 support, the ASL-to-digital mode-switch repair, dashboard support, and its own checks and documentation. It detects ASL 3 first and skips cleanly when ASL is absent.

The three projects stay in separate directories. They contain files with the same names, including `README.md` and `LICENSE`; keeping each project intact in its own directory prevents collisions. Their installation state and backups remain separately managed. Mode Buttons can optionally use the DVSwitch-Mods network-history helper when installed, and continues to work without it. ASL 3 Support skips cleanly when ASL is not installed.

## Quick start

After creating the GitHub repository `ke2hni/DVSwitch-Fixes-Upgrades`, clone it on a configured DVSwitch node:

```bash
cd ~ && git clone https://github.com/ke2hni/DVSwitch-Fixes-Upgrades.git && cd DVSwitch-Fixes-Upgrades
```

Start the combined manager:

```bash
sudo ./DVSwitch-Mods/manage-dvswitch-mods.sh
```

Update Existing Repsoitory Folder

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
6. Install ASL 3 Support (ASL 3 must be installed).
0. Exit.

Option 5 only uninstalls components recorded by the DVSwitch-Mods manager. The Mode Buttons, Dark Mode, and Widescreen installers keep their own install and restore workflows; use their own uninstall or restore instructions when needed.

The projects can also be used independently from their respective directories. For Mode Buttons, run `sudo ./dvswitch-mode-buttons.sh` from `DVSwitch-Mode-Buttons/`. For the DVSwitch-Mods manager, run `sudo ./manage-dvswitch-mods.sh` from `DVSwitch-Mods/`; its Mode Buttons and ASL 3 menu choices require their sibling directories to be present.

## Project documentation

- [DVSwitch-Mods README](DVSwitch-Mods/README.md)
- [DVSwitch-Mods testing notes](DVSwitch-Mods/TESTING.txt)
- [DVSwitch-Mode-Buttons README](DVSwitch-Mode-Buttons/README.md)
- [DVSwitch-ASL3-Mod-Support README](DVSwitch-ASL3-Mod-Support/README.md)

Each subproject contains its own license and tests. Review its README and safety notes before installing on a node.

## Default DVSwitch Dashboard Design & Layout
<img width="1600" height="900" alt="Screenshot 2026-10-25 195335" src="https://github.com/user-attachments/assets/df7ccb60-8dc8-4de8-8794-d7db53535efa" />

## Upgraded DVSwitch Dashboard Design & Layout
<img width="1600" height="900" alt="Screenshot 2026-10-25 202336" src="https://github.com/user-attachments/assets/f2166c94-49d4-4c6c-9b41-d4ee86d395cc" />
<img width="1600" height="900" alt="Screenshot 2026-10-25 202342" src="https://github.com/user-attachments/assets/5208d1e9-523a-4e0a-b11a-a0fec70c74d2" />
<img width="1600" height="900" alt="Screenshot 2026-10-25 203014" src="https://github.com/user-attachments/assets/8a633877-ce14-407d-b7b8-fb434ff56a7f" />

