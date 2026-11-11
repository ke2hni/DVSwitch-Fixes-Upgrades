<?php
// SPDX-License-Identifier: MIT
// Version: 1.0.0; Created: 2026-11-11T11:30:00-05:00 by KE2HNI
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

$favoritesPath = '/etc/dvswitch-m17-dashboard/favorites.json';
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['favorites'])) {
    $saved = is_readable($favoritesPath) ? json_decode((string)file_get_contents($favoritesPath), true) : null;
    if (!is_array($saved) && is_readable('/etc/dvswitch-mode-buttons/favorites.json')) {
        $shared = json_decode((string)file_get_contents('/etc/dvswitch-mode-buttons/favorites.json'), true);
        $saved = is_array($shared) && isset($shared['M17']) && is_array($shared['M17']) ? $shared['M17'] : array();
    }
    m17Reply(true, array('favorites' => is_array($saved) ? $saved : array()));
}
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['status'])) {
    $modePath = is_readable('/var/lib/dvswitch-mode-buttons/current-mode')
        ? '/var/lib/dvswitch-mode-buttons/current-mode'
        : '/var/lib/dvswitch-m17-dashboard/current-mode';
    $mode = is_readable($modePath) ? strtoupper(trim((string)file_get_contents($modePath))) : '';
    m17Reply(true, array('mode' => $mode));
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
