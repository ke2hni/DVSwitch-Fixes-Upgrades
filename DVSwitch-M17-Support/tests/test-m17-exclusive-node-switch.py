#!/usr/bin/env python3
# Version: 1.0.0
# Created: 2026-11-10T15:30:00-05:00 by KE2HNI
# DVSwitch-M17-Support: verify exclusive link switching without ASL add-on files.
"""Exercise the M17-owned helper against several private nodes and fake Asterisk."""
from pathlib import Path
import os
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); rpt=root/'rpt.conf'; config=root/'m17.conf'; state=root/'links'; asterisk=root/'asterisk'
        rpt.write_text('[446901](node-main)\nrxchannel = SimpleUSB/446901\n[1970](node-main)\nrxchannel = USRP/127.0.0.1:34001:32001\n[1972](node-main)\nrxchannel = USRP/127.0.0.1:34008:32008\n[1973](node-main)\nrxchannel = USRP/127.0.0.1:34009:32009\n', encoding='utf-8')
        config.write_text('M17_PRIVATE_NODE=1972\nDVSWITCH_PRIVATE_NODE=1970\n', encoding='utf-8')
        state.write_text('1970 127.0.0.1 0 OUT 00:00 ESTABLISHED\n1973 127.0.0.1 0 OUT 00:00 ESTABLISHED\n', encoding='utf-8')
        asterisk.write_text('''#!/bin/sh
cmd="$2"
case "$cmd" in
  "rpt lstats 446901") printf 'NODE PEER RECONNECTS DIRECTION CONNECT TIME CONNECT STATE\\n'; cat "$STATE_FILE" ;;
  "rpt cmd 446901 ilink 1 "*) node=${cmd##* }; sed -i "/^$node /d" "$STATE_FILE"; printf 'disconnected %s\\n' "$node" ;;
  "rpt cmd 446901 ilink 3 "*) node=${cmd##* }; printf '%s 127.0.0.1 0 OUT 00:00 ESTABLISHED\\n' "$node" >> "$STATE_FILE"; printf 'connected %s\\n' "$node" ;;
  *) exit 1 ;;
esac
''', encoding='utf-8'); asterisk.chmod(0o755)
        helper=(ROOT/'dvswitch-m17-node-link').read_text(encoding='utf-8')
        helper=helper.replace('readonly RPT_CONF="/etc/asterisk/rpt.conf"',f'readonly RPT_CONF="{rpt}"').replace('readonly ASTERISK="/usr/sbin/asterisk"',f'readonly ASTERISK="{asterisk}"').replace('readonly M17_CONFIG="/etc/dvswitch-m17-support.conf"',f'readonly M17_CONFIG="{config}"').replace("[[ ${EUID:-$(id -u)} -eq 0 ]] || die 'Run through the dashboard sudo rule.'",':')
        target=root/'helper.sh'; target.write_text(helper,encoding='utf-8'); target.chmod(0o755)
        result=subprocess.run([str(target)],input='SWITCH_PRIVATE\t1972\n',text=True,capture_output=True,check=False,env={**os.environ,'STATE_FILE':str(state)})
        assert result.returncode==0,result.stderr+result.stdout
        active=[line.split()[0] for line in state.read_text().splitlines() if line.endswith('ESTABLISHED')]
        assert active==['1972'],active
        assert '1970' in result.stdout and '1973' in result.stdout
        assert 'external node 1972 is established' in result.stdout
    print('PASS: M17 helper disconnects every alternate private node before connecting its selected node.')
if __name__=='__main__': main()
