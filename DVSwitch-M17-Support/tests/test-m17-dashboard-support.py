#!/usr/bin/env python3
# Version: 1.1.0
# Created: 2026-11-09T23:19:00-05:00 by KE2HNI
# Updated: 2026-11-10T16:40:00-05:00 by KE2HNI — cover Apache access to M17 install state under the installer's restrictive umask.
# Updated: 2026-11-10T19:16:00-05:00 by KE2HNI — verify M17 Analog Bridge card display integration and reversal.
# Updated: 2026-11-10T21:35:00-05:00 by KE2HNI — verify dashboard layout hook install and removal.
# Updated: 2026-11-10T22:25:00-05:00 by KE2HNI — cover live-refresh replacement and Analog Bridge-style card frames.
# Updated: 2026-11-11T11:30:00-05:00 by KE2HNI — verify standalone install path and optional Mode Buttons handoff.
# Updated: 2026-11-11T12:35:00-05:00 by KE2HNI — prevent network cards from flashing during status refreshes.
# Updated: 2026-11-11T13:10:00-05:00 by KE2HNI — verify left cards occupy the status sidebar below the status panels.
# Updated: 2026-11-11T13:25:00-05:00 by KE2HNI — verify M17 Net is placed in the right column for visual balance.
# Updated: 2026-11-11T13:45:00-05:00 by KE2HNI — verify centered matching activity panels and consistent side-card insets.
# Updated: 2026-11-11T14:00:00-05:00 by KE2HNI — verify equal activity gaps and right-card edge alignment.
# Updated: 2026-11-11T14:10:00-05:00 by KE2HNI — verify the desktop right card stack is lowered by 20 pixels.
"""Check M17 reflector selection, config preservation, and install script syntax."""

import importlib.util
import io
import json
import os
import re
import stat
import subprocess
import tempfile
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECT_PATH = ROOT / 'dashboard/dvswitch-m17-select.py'
SPEC = importlib.util.spec_from_file_location('dvswitch_m17_select', SELECT_PATH)
SELECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECT)
FAVORITES_SPEC = importlib.util.spec_from_file_location('dvswitch_m17_favorites', ROOT / 'dashboard/dvswitch-m17-favorites.py')
FAVORITES = importlib.util.module_from_spec(FAVORITES_SPEC)
FAVORITES_SPEC.loader.exec_module(FAVORITES)


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        catalog = root / 'M17Hosts.json'
        catalog.write_text(json.dumps({'reflectors': [{
            'designator': 'M17-123', 'name': 'Test Reflector', 'modules': ['A', 'C'],
            'ipv4': '192.0.2.123', 'dns': 'reflector.example', 'port': 17000,
        }, {
            'designator': 'URF-001', 'name': 'Multi Mode', 'enabled_modes': ['DMR', 'M17'],
            'modules': [{'module': 'A', 'mode': 'DMR'}, {'module': 'C', 'mode': 'M17'}],
            'ipv4': '192.0.2.124', 'port': 17000,
        }]}), encoding='utf-8')
        old_catalog = SELECT.CATALOG
        SELECT.CATALOG = catalog
        try:
            item = SELECT.read_catalog_target('M17-123-C')
            assert item == ('M17-123', 'C', '192.0.2.123', 17000, 'Test Reflector C')
            assert SELECT.read_catalog_target('URF-001-C')[1] == 'C'
            try:
                SELECT.read_catalog_target('M17-123-B')
            except ValueError as error:
                assert 'not listed' in str(error)
            else:
                raise AssertionError('unlisted module was accepted')
            try:
                SELECT.read_catalog_target('M17-123-A;systemctl stop asterisk')
            except ValueError:
                pass
            else:
                raise AssertionError('shell-like target was accepted')
        finally:
            SELECT.CATALOG = old_catalog

    original = ('[M17 Network]\nCallsign=KE2HNI\nAddress=192.0.2.1\n'
                'Name=M17-001 A\nLocalPort=32011\nDstPort=17000\n'
                '\n[USRP Network]\nAddress=127.0.0.1\nDstPort=32008\n')
    updated = SELECT.replace_network_values(original, {
        'address': '192.0.2.123', 'name': 'M17-123 C', 'dstport': '17000',
    })
    parser = SELECT.configparser.ConfigParser(interpolation=None)
    parser.read_string(updated)
    assert parser['M17 Network']['Address'] == '192.0.2.123'
    assert parser['M17 Network']['Name'] == 'M17-123 C'
    assert parser['M17 Network']['LocalPort'] == '32011'
    assert parser['USRP Network']['DstPort'] == '32008'

    installer = (ROOT / 'dvswitch-m17-dashboard.sh').read_text(encoding='utf-8')
    assert 'Install DVSwitch Mode Buttons through manager option 2 first' not in installer
    assert "readonly STANDALONE_TARGET=/usr/share/dvswitch/dvswitch-m17-standalone.js" in installer
    assert "readonly ENDPOINT=/usr/share/dvswitch/dvswitch-m17-dashboard.php" in installer
    assert "M17_FAVORITES=/etc/dvswitch-m17-dashboard/favorites.json" in installer
    assert 'DVSwitch Mode Buttons is not installed. Install it separately' not in installer
    blocks = {}
    for marker in ('PY_UNINSTALL', 'PY_INSTALL', 'PY_CURRENT', 'PY_SEED'):
        match = re.search(r"<<'" + marker + r"'\n(.*?)\n" + marker + r"\n", installer, re.S)
        assert match, marker
        compile(match.group(1), marker, 'exec')
        blocks[marker] = match.group(1)
    assert 'm17-favorites-seeded' in installer
    assert 'OnCalendar=Sun *-*-* 03:15:00' in (ROOT / 'dashboard/dvswitch-m17-catalog-update.timer').read_text()
    seed_catalog = {
        'reflectors': [
            {'designator': 'M17-123', 'name': 'String Modules', 'modules': ['C', 'A'],
             'ipv4': '192.0.2.123'},
            {'designator': 'URF-001', 'name': 'Mixed Modules', 'enabled_modes': ['DMR', 'M17'],
             'modules': [{'module': 'A', 'mode': 'DMR'}, {'module': 'C', 'mode': 'M17'},
                         {'module': 'D', 'mode': 'All'}], 'ipv4': '192.0.2.124'},
            {'designator': 'URF-002', 'name': 'DMR Only', 'enabled_modes': ['DMR'],
             'modules': [{'module': 'A', 'mode': 'All'}], 'ipv4': '192.0.2.125'},
        ]
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        catalog = root / 'M17Hosts.json'
        favorites = root / 'favorites.json'
        marker = root / 'seeded'
        catalog.write_text(json.dumps(seed_catalog), encoding='utf-8')
        favorites.write_text(json.dumps({'M17': []}), encoding='utf-8')
        subprocess.run(['python3', '-c', blocks['PY_SEED'], str(catalog), str(favorites), str(marker)], check=True)
        seeded = json.loads(favorites.read_text(encoding='utf-8'))['M17']
        targets = {item['target'] for item in seeded}
        assert targets == {'M17-123-A', 'URF-001-C'}, targets
        edited = {'M17': [{'name': 'My saved room', 'target': 'M17-123-C'}]}
        favorites.write_text(json.dumps(edited), encoding='utf-8')
        subprocess.run(['python3', '-c', blocks['PY_SEED'], str(catalog), str(favorites), str(marker)], check=True)
        assert json.loads(favorites.read_text(encoding='utf-8')) == edited

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        functions = root / 'functions.php'
        status = root / 'status.php'
        localtx = root / 'localtx.php'
        index = root / 'index.php'
        state = root / 'install-state.json'
        backups = root / 'backups'
        functions.write_text('$lastHeard = dvsModsStfuMergeActivity($lastHeard);\n', encoding='utf-8')
        status.write_text('''<?php
if (file_exists('/tmp/ABInfo_'.ABINFO.'.json')) {
    $abinfo = getABInfo('/tmp/ABInfo_'.ABINFO.'.json');
    $txValue = $abinfo['digital']['tg'];
    if ($abinfo['tlv']['ambe_mode'] == "DSTAR") {
        $txValue = getDSTARLinks();
    }
    echo "<table style=\"margin-top:4px;\">\n";
    echo "<tr><th width=50%>Mode</th><td style=\"background: #f9f9f9;font-weight: bold;color:#b44010;\">".$abinfo['tlv']['ambe_mode']."</td></tr>\n";
    echo "<tr><th width=50%>Mode</th><td style=\"background: #f9f9f9;font-weight: bold;color:#b44010;\">".$abinfo['tlv']['ambe_mode']."</td></tr>\n";
    echo "<tr><th width=50%>Tx TG/Ref</th><td style=\"background: #f9f9f9;font-weight: bold;color:#ef7215;\">".$txValue."</td></tr>\n";
    echo "<tr><th width=50%>Tx TG/Ref</th><td style=\"background: #f9f9f9;font-weight: bold;color:#ef7215;\">".$txValue."</td></tr>\n";

}
?>
''', encoding='utf-8')
        localtx.write_text('$counter = 0;\nif ($listElem[5] == "LNet" && ($listElem[1] == "STFU")) {\n', encoding='utf-8')
        index.write_text('<html><body></body></html>\n', encoding='utf-8')
        subprocess.run(['python3', '-c', blocks['PY_INSTALL'], str(functions), str(status), str(localtx), str(index), str(state), str(backups)], check=True,
                       preexec_fn=lambda: os.umask(0o077))
        assert stat.S_IMODE(state.parent.stat().st_mode) == 0o755
        assert stat.S_IMODE(state.stat().st_mode) == 0o600
        state.parent.chmod(0o700)
        subprocess.run(['python3', '-c', blocks['PY_INSTALL'], str(functions), str(status), str(localtx), str(index), str(state), str(backups)], check=True,
                       preexec_fn=lambda: os.umask(0o077))
        assert stat.S_IMODE(state.parent.stat().st_mode) == 0o755
        assert stat.S_IMODE(state.stat().st_mode) == 0o600
        assert 'dvsM17MergeActivity($lastHeard)' in functions.read_text()
        assert 'dvsM17ShowNetCard()' in status.read_text()
        patched_status=status.read_text()
        assert 'dvsM17CurrentDisplayTarget()' in patched_status
        assert "htmlspecialchars($m17Display['target']" in patched_status
        assert patched_status.count('$displayMode') == 4
        assert patched_status.count('$displayTarget') == 4
        assert 'dvswitchASL3ShowNetCard' not in status.read_text()
        assert '$listElem[1] == "M17"' in localtx.read_text()
        assert '<script src="/dvswitch/dvswitch-m17-layout.js"></script>' in index.read_text()
        assert '<script src="/dvswitch/dvswitch-m17-standalone.js"></script>' in index.read_text()
        subprocess.run(['python3', '-c', blocks['PY_UNINSTALL'], str(functions), str(status), str(localtx), str(index)], check=True)
        assert 'dvsM17MergeActivity' not in functions.read_text()
        assert 'dvsM17ShowNetCard' not in status.read_text()
        assert 'dvsM17CurrentDisplayTarget' not in status.read_text()
        assert "$abinfo['tlv']['ambe_mode']" in status.read_text()
        assert '$listElem[1] == "M17"' not in localtx.read_text()
        assert 'dvswitch-m17-layout.js' not in index.read_text()
        assert 'dvswitch-m17-standalone.js' not in index.read_text()
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); catalog=root/'M17Hosts.json'; config=root/'USRP2M17.ini'; history=root/'history.tsv'
        catalog.write_text(json.dumps({'reflectors':[{'designator':'M17-123','name':'Friendly Room','modules':['C']}]}),encoding='utf-8')
        config.write_text('[M17 Network]\nName=M17-123 C\n',encoding='utf-8')
        subprocess.run(['python3','-c',blocks['PY_CURRENT'],str(catalog),str(config),str(history)],check=True)
        assert 'M17-123-C\tFriendly Room C' in history.read_text()
    layout = (ROOT / 'dashboard/dvswitch-m17-layout.js').read_text(encoding='utf-8')
    card = (ROOT / 'dashboard/dvswitch-m17-net-card.php').read_text(encoding='utf-8')
    assert all(name in layout for name in ('ASL Net', 'DMR TGIF Master', 'D-Star Net', 'M17 Net', 'NXDN Net', 'P25 Net', 'STFU Net', 'YSF Net'))
    assert 'dvs-network-cards-left' in layout and 'dvs-network-cards-right' in layout
    assert "info.parentNode.insertBefore(host, info.nextSibling)" in layout
    assert "host.id = 'dvs-network-sidebar-cards'" in layout
    assert "index < 3 && card.name !== 'M17 Net'" in layout
    assert "center.appendChild(localActivity)" in layout
    assert "grid-template-columns:minmax(0,1fr) minmax(180px,220px)" in layout
    assert "#dvs-gateway-activity #lastHerd fieldset,#dvs-gateway-activity #localTxs fieldset" in layout
    assert "width:calc(100% - 16px);justify-self:start" in layout
    assert "margin:8px 0 0 24px" in layout
    assert ".dvs-network-cards-right{padding:20px 32px 0 0" in layout
    assert "dvs-network-layout-spacer" not in layout
    assert 'left.replaceChildren()' not in layout and 'right.replaceChildren()' not in layout
    assert 'if (observer) observer.disconnect();' in layout
    assert 'if (observer) observer.observe(info, { childList: true, subtree: true });' in layout
    assert 'item.dataset.cardName === card.name' in layout
    assert "document.createElement('fieldset')" in layout and 'dvs-network-card-panel' in layout
    assert 'alignLeftCards' not in layout
    assert 'window.setInterval(start' not in layout
    assert 'color:#b5651d!important' in card
    standalone = (ROOT / 'dashboard/dvswitch-m17-standalone.js').read_text(encoding='utf-8')
    api = (ROOT / 'dashboard/dvswitch-m17-dashboard.php').read_text(encoding='utf-8')
    favorites_helper = (ROOT / 'dashboard/dvswitch-m17-favorites.py').read_text(encoding='utf-8')
    assert "if (document.getElementById('dvs-mode-buttons')" in standalone
    assert 'dvs-m17-edit' in standalone and 'dvs-m17-add' in standalone
    assert "'/usr/local/sbin/dvswitch-m17-dashboard-mode'" in api
    assert "'/usr/local/sbin/dvswitch-m17-select'" in api
    assert '/etc/dvswitch-m17-dashboard/favorites.json' in api
    assert 'at most 250 entries' in favorites_helper
    with tempfile.TemporaryDirectory() as directory:
        favorite_path = Path(directory) / 'favorites.json'
        FAVORITES.DEST = favorite_path
        with patch('os.geteuid', return_value=0), patch('os.chown'), patch('sys.stdin', io.StringIO('[{"name":"Room A","target":"M17-001-A"}]')):
            FAVORITES.main()
        assert json.loads(favorite_path.read_text(encoding='utf-8')) == [{'name': 'Room A', 'target': 'M17-001-A'}]
        with patch('os.geteuid', return_value=0), patch('os.chown'), patch('sys.stdin', io.StringIO('[{"name":"One","target":"M17-001-A"},{"name":"Two","target":"M17-001-A"}]')):
            try:
                FAVORITES.main()
            except SystemExit as error:
                assert 'duplicate M17 target' in str(error)
            else:
                raise AssertionError('duplicate favorite target was accepted')
    manager = (ROOT.parent / 'DVSwitch-Mods/manage-dvswitch-mods.sh').read_text(encoding='utf-8')
    manager_hook = manager[manager.index('run_m17_dashboard_installer()'):manager.index('\nshow_menu()')]
    assert 'dvswitch-mode-buttons.sh' not in manager_hook
    assert 'if [[ ! -f /usr/share/dvswitch/dvswitch-mode-buttons.php ]]' not in manager_hook
    print('PASS: M17 reflector, dashboard install/uninstall hooks, and eight-card layout.')


if __name__ == '__main__':
    main()
