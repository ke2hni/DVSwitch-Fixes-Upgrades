<?php
// DVSwitch-M17-Dashboard: M17 Net card v1
// Version: 1.0.0; Created: 2026-11-09T23:19:00-05:00; Created by KE2HNI

function dvsM17ShowNetCard() {
    $configPath = '/etc/USRP2M17.ini';
    if (!is_readable($configPath)) { return; }
    $config = @parse_ini_file($configPath, true, INI_SCANNER_RAW);
    $network = is_array($config) && isset($config['M17 Network']) ? $config['M17 Network'] : array();
    $name = isset($network['Name']) ? trim((string)$network['Name']) : '';
    $room = $name !== '' ? $name : 'M17 reflector';
    if (preg_match('/^(.+)\s+([A-Z0-9])$/', $name, $parts) && is_readable('/var/lib/mmdvm/M17Hosts.json')) {
        $catalog = json_decode((string)file_get_contents('/var/lib/mmdvm/M17Hosts.json'), true);
        foreach (is_array($catalog['reflectors'] ?? null) ? $catalog['reflectors'] : array() as $row) {
            if (!is_array($row) || ($row['designator'] ?? '') !== $parts[1]) { continue; }
            $enabled = is_array($row['enabled_modes'] ?? null) ? array_map('strtoupper', array_filter($row['enabled_modes'], 'is_string')) : array();
            $modules = array();
            foreach (is_array($row['modules'] ?? null) ? $row['modules'] : array() as $item) {
                if (is_string($item)) {
                    $module = strtoupper($item);
                    if ($enabled && !in_array('M17', $enabled, true)) { continue; }
                } elseif (is_array($item) && is_string($item['module'] ?? null)) {
                    $module = strtoupper($item['module']);
                    $mode = strtoupper((string)($item['mode'] ?? ''));
                    if ($mode !== 'M17' && !($mode === 'ALL' && in_array('M17', $enabled, true))) { continue; }
                } else { continue; }
                if (preg_match('/^[A-Z0-9]$/', $module)) { $modules[] = $module; }
            }
            if (in_array($parts[2], $modules, true) && is_string($row['name'] ?? null) && trim($row['name']) !== '') {
                $room = trim($row['name']).' '.$parts[2];
            }
            break;
        }
    }
    $isActive = function_exists('isProcessRunning') ? isProcessRunning('USRP2M17') : false;
    $label = htmlspecialchars($room, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    echo '<br /><table><tr><th colspan="2">M17 Net</th></tr>';
    echo '<tr><td colspan="2" style="background:#ffffed;color:#b5651d;font-weight:bold;white-space:normal;overflow-wrap:anywhere;text-align:center;">Room<br />'.$label.'</td></tr>';
    echo '<tr><td colspan="2" style="background:'.($isActive ? '#0b0' : '#ffffed').';color:'.($isActive ? '#030' : '#b0b0b0').';font-weight:bold;text-align:center;">'.($isActive ? 'Connected' : 'OFFLINE').'</td></tr></table>';
}
?>
