#!/usr/bin/env python3
# Version: 1.0.0
# Created: 2026-11-09T23:19:00-05:00 by KE2HNI
"""Check M17 reflector selection, config preservation, and install script syntax."""

import importlib.util
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECT_PATH = ROOT / 'dashboard/dvswitch-m17-select.py'
SPEC = importlib.util.spec_from_file_location('dvswitch_m17_select', SELECT_PATH)
SELECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECT)


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
        state = root / 'install-state.json'
        backups = root / 'backups'
        functions.write_text('$lastHeard = dvsModsStfuMergeActivity($lastHeard);\n', encoding='utf-8')
        status.write_text('?>\n', encoding='utf-8')
        localtx.write_text('$counter = 0;\nif ($listElem[5] == "LNet" && ($listElem[1] == "STFU")) {\n', encoding='utf-8')
        subprocess.run(['python3', '-c', blocks['PY_INSTALL'], str(functions), str(status), str(localtx), str(state), str(backups)], check=True)
        assert 'dvsM17MergeActivity($lastHeard)' in functions.read_text()
        assert 'dvsM17ShowNetCard()' in status.read_text()
        assert 'dvswitchASL3ShowNetCard' not in status.read_text()
        assert '$listElem[1] == "M17"' in localtx.read_text()
        subprocess.run(['python3', '-c', blocks['PY_UNINSTALL'], str(functions), str(status), str(localtx)], check=True)
        assert 'dvsM17MergeActivity' not in functions.read_text()
        assert 'dvsM17ShowNetCard' not in status.read_text()
        assert '$listElem[1] == "M17"' not in localtx.read_text()
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); catalog=root/'M17Hosts.json'; config=root/'USRP2M17.ini'; history=root/'history.tsv'
        catalog.write_text(json.dumps({'reflectors':[{'designator':'M17-123','name':'Friendly Room','modules':['C']}]}),encoding='utf-8')
        config.write_text('[M17 Network]\nName=M17-123 C\n',encoding='utf-8')
        subprocess.run(['python3','-c',blocks['PY_CURRENT'],str(catalog),str(config),str(history)],check=True)
        assert 'M17-123-C\tFriendly Room C' in history.read_text()
    print('PASS: M17 string/object module validation, config preservation, and installer install/uninstall patching.')


if __name__ == '__main__':
    main()
