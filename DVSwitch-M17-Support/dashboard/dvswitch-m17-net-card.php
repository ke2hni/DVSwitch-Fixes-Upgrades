<?php
// DVSwitch-M17-Dashboard: M17 Net card v1
// Version: 1.1.1; Created: 2026-11-09T23:19:00-05:00; Created by KE2HNI
// Updated: 2026-11-17T15:05:00-05:00 by KE2HNI — show M17 reflector IDs with friendly names in status and Net cards.
// Updated: 2026-11-17T15:50:00-05:00 by KE2HNI — match both M17 labels to the copper text used by other Net cards.
// Updated: 2026-11-17T21:05:06-05:00 by KE2HNI — use the exact #b5651d copper color in both inline labels for dark and light themes.
// Updated: 2026-11-10T19:16:00-05:00 by KE2HNI — provide the selected M17 target for Analog Bridge status display.
// Updated: 2026-11-14T16:10:00-05:00 by KE2HNI — retain copper in dark theme and let the light-theme overlay darken it.
// Updated: 2026-11-11T11:30:00-05:00 by KE2HNI — read standalone M17 mode state when Mode Buttons is absent.
// Updated: 2026-11-11T15:40:00-05:00 by KE2HNI — only show M17 status when the live Analog_Bridge mode is M17.
// Updated: 2026-11-11T16:20:00-05:00 by KE2HNI — preserve M17 display while Analog_Bridge retains an unrelated previous DV mode.
// Updated: 2026-11-11T23:35:00-05:00 by KE2HNI — treat selected M17 private-node state as authoritative while Analog_Bridge reports ASL.

function dvsM17CurrentDisplayTarget() {
    $target = dvsM17TargetDetails();
    return $target === null ? null : array('mode' => 'M17', 'target' => $target['id']);
}

function dvsM17TargetDetails() {
    $modePath = is_readable('/var/lib/dvswitch-mode-buttons/current-mode')
        ? '/var/lib/dvswitch-mode-buttons/current-mode'
        : '/var/lib/dvswitch-m17-dashboard/current-mode';
    if (!is_readable($modePath) || strtoupper(trim((string)file_get_contents($modePath))) !== 'M17') { return null; }
    // M17 is routed through its own private USRP node, so Analog_Bridge can
    // report ASL while the selected and connected M17 mode is active.
    $config = @parse_ini_file('/etc/USRP2M17.ini', true, INI_SCANNER_RAW);
    $network = is_array($config) && isset($config['M17 Network']) ? $config['M17 Network'] : array();
    $name = isset($network['Name']) ? trim((string)$network['Name']) : '';
    if ($name === '') { return array('id' => 'Not linked', 'room' => 'Not linked'); }
    $identifier = $name;
    if (preg_match('/^(.+)\s+([A-Z0-9])$/', $name, $parts) && is_readable('/var/lib/mmdvm/M17Hosts.json')) {
        $identifier = $parts[1].'-'.$parts[2];
        $catalog = json_decode((string)file_get_contents('/var/lib/mmdvm/M17Hosts.json'), true);
        foreach (is_array($catalog['reflectors'] ?? null) ? $catalog['reflectors'] : array() as $row) {
            if (!is_array($row) || ($row['designator'] ?? '') !== $parts[1]) { continue; }
            if (is_string($row['name'] ?? null) && trim($row['name']) !== '') { $name = trim($row['name']).' '.$parts[2]; }
            break;
        }
    }
    return array('id' => $identifier, 'room' => $name);
}

function dvsM17ShowNetCard() {
    $configPath = '/etc/USRP2M17.ini';
    if (!is_readable($configPath)) { return; }
    $config = @parse_ini_file($configPath, true, INI_SCANNER_RAW);
    $network = is_array($config) && isset($config['M17 Network']) ? $config['M17 Network'] : array();
    $name = isset($network['Name']) ? trim((string)$network['Name']) : '';
    $room = $name !== '' ? $name : 'M17 reflector';
    $identifier = $name;
    if (preg_match('/^(.+)\s+([A-Z0-9])$/', $name, $parts) && is_readable('/var/lib/mmdvm/M17Hosts.json')) {
        $identifier = $parts[1].'-'.$parts[2];
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
    // Keep the stock copper color but omit !important so Light mode can apply its existing contrast override.
    $idLabel = htmlspecialchars($identifier, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    echo '<tr><td colspan="2" style="background:#ffffed;font-weight:bold;white-space:normal;overflow-wrap:anywhere;text-align:center;">Reflector<br /><span style="color:#b5651d;">'.$idLabel.'</span><br /><span style="color:#b5651d;">'.$label.'</span></td></tr>';
    echo '<tr><td colspan="2" style="background:'.($isActive ? '#0b0' : '#ffffed').';color:'.($isActive ? '#030' : '#b0b0b0').';font-weight:bold;text-align:center;">'.($isActive ? 'Connected' : 'OFFLINE').'</td></tr></table>';
}
?>
