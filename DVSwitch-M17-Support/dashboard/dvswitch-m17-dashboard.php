<?php
// SPDX-License-Identifier: MIT
// Version: 1.0.3; Created: 2026-11-11T11:30:00-05:00 by KE2HNI
// Updated: 2026-11-21T18:20:00-05:00 by KE2HNI — read M17 favorites only from the dedicated M17 file.
// Updated: 2026-11-21T14:10:00-05:00 by KE2HNI — expose catalog reflectors and their selectable M17 modules separately from favorites.
// Updated: 2026-11-17T09:34:00-05:00 by KE2HNI — report live M17 receive activity and prefer the newest selected-mode state.
// M17-owned API for dashboard installs that do not include Mode Buttons.
header('Content-Type: application/json; charset=utf-8');

function m17Reply($ok, $fields = array(), $status = 200) {
    http_response_code($status);
    echo json_encode(array_merge(array('ok' => $ok), $fields), JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
}

function m17Run($command, $input = '') {
    $pipes = array();
    $process = proc_open(array('/usr/bin/sudo', $command), array(0 => array('pipe', 'r'), 1 => array('pipe', 'w'), 2 => array('pipe', 'w')), $pipes);
    if (!is_resource($process)) { m17Reply(false, array('error' => 'Unable to start the M17 dashboard action.'), 500); }
    fwrite($pipes[0], $input); fclose($pipes[0]);
    $output = stream_get_contents($pipes[1]); fclose($pipes[1]);
    $error = stream_get_contents($pipes[2]); fclose($pipes[2]);
    $status = proc_close($process);
    return array($status, trim((string)$output), trim((string)$error));
}

function m17CatalogModules($row) {
    $enabled = array();
    if (isset($row['enabled_modes']) && is_array($row['enabled_modes'])) {
        foreach ($row['enabled_modes'] as $mode) { if (is_string($mode)) { $enabled[] = strtoupper($mode); } }
    }
    $modules = array();
    if (!isset($row['modules']) || !is_array($row['modules'])) { return $modules; }
    foreach ($row['modules'] as $item) {
        if (is_string($item)) {
            $module = $item;
            if (count($enabled) > 0 && !in_array('M17', $enabled, true)) { continue; }
        } elseif (is_array($item) && isset($item['module']) && is_string($item['module'])) {
            $module = $item['module'];
            $itemMode = isset($item['mode']) ? strtoupper((string)$item['mode']) : '';
            if ($itemMode !== 'M17' && !($itemMode === 'ALL' && in_array('M17', $enabled, true))) { continue; }
        } else { continue; }
        $module = strtoupper($module);
        if (preg_match('/^[A-Z0-9]$/D', $module) && !in_array($module, $modules, true)) { $modules[] = $module; }
    }
    sort($modules, SORT_STRING);
    return $modules;
}

if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['catalog'])) {
    $catalogPath = '/var/lib/mmdvm/M17Hosts.json';
    $catalog = is_readable($catalogPath) ? json_decode((string)file_get_contents($catalogPath), true) : null;
    if (!is_array($catalog) || !isset($catalog['reflectors']) || !is_array($catalog['reflectors'])) {
        m17Reply(false, array('error' => 'M17 reflector catalog is unavailable.'), 503);
    }
    $reflectors = array();
    foreach ($catalog['reflectors'] as $row) {
        if (!is_array($row) || !isset($row['designator']) || !is_string($row['designator']) || !preg_match('/^[A-Za-z0-9_-]{1,30}$/D', $row['designator'])) { continue; }
        $address = isset($row['ipv4']) && is_string($row['ipv4']) && $row['ipv4'] !== '' ? $row['ipv4'] : (isset($row['dns']) ? (string)$row['dns'] : '');
        if (!filter_var($address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) { continue; }
        $modules = m17CatalogModules($row);
        if (!$modules) { continue; }
        $name = isset($row['name']) && is_string($row['name']) ? trim($row['name']) : '';
        $sponsor = isset($row['sponsor']) && is_string($row['sponsor']) ? trim($row['sponsor']) : '';
        if ($name === '' || strcasecmp($name, 'null') === 0) { $name = $sponsor; }
        if ($name === '' || strcasecmp($name, 'null') === 0) { $name = $row['designator']; }
        $reflectors[] = array('designator' => $row['designator'], 'name' => $name, 'modules' => $modules);
    }
    usort($reflectors, function ($left, $right) { return strcasecmp($left['name'], $right['name']) ?: strcasecmp($left['designator'], $right['designator']); });
    m17Reply(true, array('reflectors' => $reflectors));
}

$favoritesPath = '/etc/dvswitch-m17-dashboard/favorites.json';
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['favorites'])) {
    $saved = is_readable($favoritesPath) ? json_decode((string)file_get_contents($favoritesPath), true) : null;
    m17Reply(true, array('favorites' => is_array($saved) ? $saved : array()));
}
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['status'])) {
    $modePaths = is_file('/usr/share/dvswitch/dvswitch-mode-buttons.php')
        ? array('/var/lib/dvswitch-mode-buttons/current-mode', '/var/lib/dvswitch-m17-dashboard/current-mode')
        : array('/var/lib/dvswitch-m17-dashboard/current-mode', '/var/lib/dvswitch-mode-buttons/current-mode');
    $mode = '';
    foreach ($modePaths as $modePath) {
        if (!is_readable($modePath) || is_link($modePath)) { continue; }
        $mode = strtoupper(trim((string)file_get_contents($modePath)));
        break;
    }
    $rxPath = '/run/dvswitch-m17-audio-monitor/rx-active';
    $rxModified = is_file($rxPath) && !is_link($rxPath) ? @filemtime($rxPath) : false;
    $rxActive = $mode === 'M17' && $rxModified !== false && time() >= $rxModified && time() - $rxModified <= 2;
    m17Reply(true, array('mode' => $mode, 'rx' => $rxActive));
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { m17Reply(false, array('error' => 'Unsupported request.'), 405); }
$request = json_decode((string)file_get_contents('php://input'), true);
if (!is_array($request) || !isset($request['action']) || !is_string($request['action'])) { m17Reply(false, array('error' => 'Invalid request.'), 400); }
if ($request['action'] === 'activate') {
    list($status, $output, $error) = m17Run('/usr/local/sbin/dvswitch-m17-dashboard-mode');
} elseif ($request['action'] === 'select') {
    $target = isset($request['target']) && is_string($request['target']) ? trim($request['target']) : '';
    if (!preg_match('/^[A-Za-z0-9_-]{1,35}$/D', $target)) { m17Reply(false, array('error' => 'Enter a valid reflector-module target.'), 400); }
    list($status, $output, $error) = m17Run('/usr/local/sbin/dvswitch-m17-select', $target . "\n");
} elseif ($request['action'] === 'save' && isset($request['favorites']) && is_array($request['favorites'])) {
    list($status, $output, $error) = m17Run('/usr/local/sbin/dvswitch-m17-favorites', json_encode($request['favorites']));
} else { m17Reply(false, array('error' => 'Unsupported M17 action.'), 400); }
m17Reply($status === 0, array('message' => $output, 'error' => $error), $status === 0 ? 200 : 400);
?>
