# DVSwitch Fixes & Upgrades

A combined repository for the independently installable DVSwitch repairs and dashboard modifications from **DVSwitch-Mods** and **DVSwitch-Mode-Buttons**.

## Repository layout

- `DVSwitch-Mods/` contains the standard repair and modification manager, its standalone Dark Mode and Widescreen Display Layout installers, component scripts, tests, and detailed project documentation.
- `DVSwitch-Mode-Buttons/` contains the seven-mode dashboard controls, favorites editor, helpers, installer, tests, and detailed project documentation.

Both projects stay in separate directories. They contain files with the same names, including `README.md`, `LICENSE`, and `dvswitch-display-layout.sh`; keeping each project intact in its own directory prevents collisions. Their installation state, backups, and uninstall workflows remain separately managed. Mode Buttons can optionally use the DVSwitch-Mods network-history helper when installed, and continues to work without it.

## Quick start

After creating the GitHub repository `ke2hni/DVSwitch-Fixes-Upgrades`, clone it on a configured DVSwitch node:

```bash
cd ~ && git clone https://github.com/ke2hni/DVSwitch-Fixes-Upgrades.git && cd DVSwitch-Fixes-Upgrades
```

Start the combined manager:

```bash
sudo ./DVSwitch-Mods/manage-dvswitch-mods.sh
```

The menu offers:

1. Install or upgrade all standard DVSwitch repairs and modifications.
2. Launch the DVSwitch Mode Buttons installer menu.
3. Launch the Dark Mode dashboard installer.
4. Launch the Widescreen Display Layout installer.
5. Uninstall all manager-recorded standard components.
0. Exit.

Option 5 only uninstalls components recorded by the DVSwitch-Mods manager. The Mode Buttons, Dark Mode, and Widescreen installers keep their own install and restore workflows; use their own uninstall or restore instructions when needed.

The projects can also be used independently from their respective directories. For Mode Buttons, run `sudo ./dvswitch-mode-buttons.sh` from `DVSwitch-Mode-Buttons/`. For the DVSwitch-Mods manager, run `sudo ./manage-dvswitch-mods.sh` from `DVSwitch-Mods/`; its Mode Buttons menu choice requires the sibling directory to be present.

## Project documentation

- [DVSwitch-Mods README](DVSwitch-Mods/README.md)
- [DVSwitch-Mods testing notes](DVSwitch-Mods/TESTING.txt)
- [DVSwitch-Mode-Buttons README](DVSwitch-Mode-Buttons/README.md)

Each subproject contains its own license and tests. Review its README and safety notes before installing on a node.
