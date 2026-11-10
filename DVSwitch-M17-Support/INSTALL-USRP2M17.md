# Install and Configure the USRP2M17 M17 Bridge

<!-- Version: 1.0.4 | Created: 2026-11-10T19:00:00-05:00 by KE2HNI; Updated: 2026-11-09T23:19:00-05:00 by KE2HNI -->

<!-- Version: 1.0.2; Created: 2026-11-09T18:43:31-05:00; Created by KE2HNI -->

This guide is for a new operator installing the M17-to-ASL bridge on a Debian-based AllStarLink 3 node that already runs DVSwitch. It uses the upstream nostar/MMDVM_CM project and its USRP2M17 program.

USRP2M17 connects an M17 reflector to an AllStar private USRP node. It does not require an M17 radio HAT. The radio or client must support M17 and connect to the selected reflector over the network. The bridge forwards audio through the ASL private node, so the public ASL node must link to only one digital-mode private node at a time.

## Before you start

Have these details ready:

1. Your amateur radio callsign.
2. The private AllStar node number already used by DVSwitch. Do not guess based on node order.
3. A new, unused numeric private node number for M17.
4. Two unused local UDP ports for the M17 node’s USRP audio link. The example defaults are 32008 for Asterisk and 34008 for USRP2M17. The installer checks for conflicts and asks you to confirm or replace them.
5. The M17 reflector and module you want to use. The installer downloads the current M17 host list and lets you select an entry.

The sample port pair on a DVSwitch node is:

| Purpose | Example port | Used by |
| --- | ---: | --- |
| Asterisk side of the M17 USRP link | 32008 | Asterisk |
| USRP2M17 side of the M17 USRP link | 34008 | USRP2M17 |
| M17 network local UDP port | First available port starting at 32010 | USRP2M17 |
| M17 reflector destination port | From the selected host-list entry, commonly 17000 | Remote reflector |

Every private USRP node must have its own local port pair. Never reuse the ports that belong to DVSwitch’s Analog_Bridge connection.

## Add the M17 mode to the DVSwitch dashboard

After the M17 bridge works and the regular DVSwitch Mode Buttons are installed, run the combined manager and select option 9. The bridge installer and private-node switching commands do not require either Mode Buttons or the ASL Support add-on; option 9 is an optional dashboard overlay. If the bridge was installed before this dashboard release, first choose manager option 8 and **Install or upgrade USRP2M17** once to add the source callsigns needed by the new activity history. Then choose option 9 and install or upgrade dashboard support. This adds the M17 button, M17 Net card, separate editable reflector favorites, and M17 rows in Gateway Activity and Local Activity. The reflector catalog refreshes weekly from the M17 Project's `M17Hosts.json`; the refresh does not replace edited favorites. Initial favorites include one entry per usable reflector, using module A when available and otherwise the first M17 module. Enter another `reflector-module` target (for example `URF018-B`) and save it as a favorite to use that module. The selector changes reflectors by updating `/etc/USRP2M17.ini` and restarting `usrp2m17.service`. Re-selecting the current reflector avoids a restart.

The bridge installer builds USRP2M17 from an isolated temporary copy of the GitHub source and adds source-call fields to its end-of-transmission log entries. This leaves `/opt/dvswitch-m17/MMDVM_CM` clean for safe upgrades and gives the dashboard the callsigns needed for the M17 activity history.

## Install

1. Log in to the node with an account that can run sudo.
2. Open the combined repository folder and start the manager:

       cd ~/DVSwitch-Fixes-Upgrades && sudo ./DVSwitch-Mods/manage-dvswitch-mods.sh

3. Choose **8) Install/configure or uninstall the USRP2M17 M17 bridge**.
5. In the USRP2M17 menu, choose **1) Install or upgrade USRP2M17**.
5. Answer each prompt. At the DVSwitch question, enter the actual DVSwitch private node number. Select a different node number for M17. This M17 installer records both choices itself; you do not need to run the ASL Support installer first.
   If an existing USRP2M17 config and executable match a private node's port pair, the installer recognizes that node and offers its number as the default so you can adopt the manual setup. If the old program is running, the installer asks before stopping it.
6. Review the summary. Continue only if the node numbers, reflector, and ports are correct.
7. When asked whether to restart Asterisk, answer **Yes** during a maintenance window. Restarting Asterisk interrupts current calls and links. If you answer **No**, restart Asterisk later before testing the new node.

The installer installs build tools if needed, clones or updates the upstream GitHub source, builds USRP2M17, writes /etc/USRP2M17.ini, configures an Asterisk private node, creates usrp2m17.service, starts the service, and installs the m17 and dvs-dvswitch switching commands. It creates a timestamped backup before changing system files.

## Check the installation

On the node, inspect the service and private-node links:

       sudo systemctl status usrp2m17.service --no-pager --full

       sudo asterisk -rx "rpt localnodes" && sudo asterisk -rx "rpt lstats YOUR_PUBLIC_NODE"

Replace YOUR_PUBLIC_NODE with the local public ASL node number. The M17 private node should appear in rpt localnodes; after switching, the public node’s link table should show the M17 private node as established.

To switch the public node to M17, run:

       sudo m17

To disconnect M17 and return to the DVSwitch private node, run:

       sudo dvs-dvswitch

These commands switch the active private-node connection. They do not bridge M17 receive audio simultaneously into STFU, DMR, YSF, P25, NXDN, or D-Star.

For a direct M17 network check, view the service log:

       sudo journalctl -u usrp2m17.service -n 80 --no-pager

Look for an acknowledgement from the reflector and continuing network activity. If the service is active but no acknowledgement appears, confirm that the reflector and module are correct and that outbound UDP is allowed.

## Uninstall

1. Run the manager and choose option **8**.
2. Choose **2) Uninstall USRP2M17**.
3. Confirm the removal. The uninstaller stops and disables the service, removes installer-managed files and node entries, restores any prior files from the install backup, and saves a separate uninstall recovery backup. A private node that existed before installation is left in Asterisk; its original config and executable are restored.
4. Restart Asterisk if the installer-created private node was removed.

The uninstaller asks whether to delete the installer-owned MMDVM_CM source checkout. The default answer is Yes. Backups remain under /var/backups/dvswitch-mods/usrp2m17/.

## Troubleshooting

- **chan_usrp.so is not Running**: enable the USRP channel driver in ASL/Asterisk, restart Asterisk, and run menu option 8 again.
- **The selected port is occupied**: choose a different unused port. Keep the Asterisk side and USRP2M17 side distinct, and do not duplicate another private USRP node’s pair.
- **A node number already exists**: choose a new unused M17 private node number. The installer does not overwrite an existing node stanza with different settings.
- **The private node does not show after install**: restart Asterisk, then check sudo asterisk -rx "rpt localnodes" and the service log.
- **Service fails with `status=200/CHDIR` or `Permission denied`**: installer v1.0.4 and later fixes access on the source directories. For an existing installation, run `sudo chmod 755 /opt/dvswitch-m17 /opt/dvswitch-m17/MMDVM_CM /opt/dvswitch-m17/MMDVM_CM/USRP2M17`, then restart `usrp2m17.service`.
- **Upgrade reports local changes in MMDVM_CM**: installer v1.0.5 and later cleans the executable and compiler outputs created by its previous build, then checks for remaining changes. If the message persists, inspect `/opt/dvswitch-m17/MMDVM_CM` for your own edits before changing or removing them.
- **The reflector list cannot be downloaded**: confirm Internet access. The installer can continue if you provide the reflector name, numeric IPv4 address, and UDP port from the official M17 host list.

Upstream project: https://github.com/nostar/MMDVM_CM  
M17 host list: https://m17-project.github.io/hostfiles/M17Hosts.txt
