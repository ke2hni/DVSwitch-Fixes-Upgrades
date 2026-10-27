<?php
// DVSwitch-ASL3-Mod-Support: ASL Net card
if (!function_exists('dvswitchASL3ShowNetCard')) {
    function dvswitchASL3ShowNetCard()
    {
        $connected = array();
        $linksAvailable = false;
        $linkOutput = array();
        $linkStatus = 1;
        exec('/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-node-links 2>/dev/null', $linkOutput, $linkStatus);
        if ($linkStatus === 0) {
            $linksAvailable = true;
            foreach ($linkOutput as $node) {
                $node = trim($node);
                if (preg_match('/^[0-9]{1,8}$/D', $node) && (int)$node > 0) { $connected[$node] = true; }
            }
        }

        $names = array();
        $astdb = is_readable('/var/lib/asterisk/astdb.txt') ? '/var/lib/asterisk/astdb.txt' : '/var/lib/asterisk/astdb';
        if (is_readable($astdb)) {
            foreach (file($astdb, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: array() as $line) {
                $fields = explode('|', $line, 4);
                if (count($fields) < 2) { continue; }
                $node = trim($fields[0]);
                $name = trim($fields[1] . (isset($fields[2]) && trim($fields[2]) !== '' ? ' - ' . trim($fields[2]) : ''));
                if ($node !== '' && $name !== '') { $names[$node] = $name; }
            }
        }

        echo "<br />\n<table>\n<tr><th colspan=\"2\">ASL Net</th></tr>\n";
        if (!$linksAvailable) {
            echo '<tr><td colspan="2" style="background:#ffffed;text-align:center;">Status unavailable</td></tr>' . "\n";
        } elseif (!$connected) {
            echo '<tr><td colspan="2" style="background:#ffffed;text-align:center;">Listening</td></tr>' . "\n";
        } else {
            foreach (array_keys($connected) as $node) {
                $name = isset($names[$node]) ? $names[$node] : 'Node ' . $node;
                echo '<tr><td colspan="2" style="background:#ffffed;text-align:center;">Node<br/><span style="color:#b5651d;font-weight:bold;white-space:normal;overflow-wrap:anywhere;">' . htmlspecialchars($name, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '</span><br/><span style="color:#b5651d;font-weight:bold;">(' . htmlspecialchars($node, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . ')</span></td></tr>' . "\n";
            }
        }
        echo "</table>\n";
    }
}
?>
