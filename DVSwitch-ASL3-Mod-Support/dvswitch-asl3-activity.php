<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');

// Use Allmon3's local AMI status data; keep live link listing as a safe fallback.
$statusOutput = array();
$statusCode = 1;
exec('/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-ami-status 2>/dev/null', $statusOutput, $statusCode);
$status = $statusCode === 0 ? json_decode(implode("\n", $statusOutput), true) : null;
$links = array();
if (!is_array($status) || empty($status['ok'])) {
    $publicNode = is_array($status) && isset($status['public_node']) ? (string)$status['public_node'] : '';
    $linkCode = 1;
    exec('/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-node-links 2>/dev/null', $links, $linkCode);
    if ($linkCode !== 0) { $links = array(); }
    $status = array('ok' => false, 'public_node' => $publicNode, 'connected_nodes' => $links);
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
// A user's saved ASL favorite name takes precedence over the ASTDB label for that node.
$favoriteFile = '/etc/dvswitch-asl3-support/favorites.json';
$favoriteNames = is_readable($favoriteFile) ? json_decode((string)file_get_contents($favoriteFile), true) : array();
if (is_array($favoriteNames)) {
    foreach ($favoriteNames as $favorite) {
        if (is_array($favorite) && isset($favorite['node'], $favorite['name']) &&
            preg_match('/^[0-9]{1,8}$/D', (string)$favorite['node']) &&
            is_string($favorite['name']) && trim($favorite['name']) !== '') {
            $names[(string)$favorite['node']] = trim($favorite['name']);
        }
    }
}

$publicNode = isset($status['public_node']) && preg_match('/^[0-9]{1,8}$/D', (string)$status['public_node'])
    ? (string)$status['public_node'] : '';
$rxKeyed = !empty($status['rx_keyed']);
$txKeyed = !empty($status['tx_keyed']);
$txeKeyed = !empty($status['txe_keyed']);
$linkKeying = isset($status['link_keying']) && is_array($status['link_keying']) ? $status['link_keying'] : array();
$keyedNodes = array();
foreach ($linkKeying as $node => $state) {
    if (is_array($state) && !empty($state['ptt'])) { $keyedNodes[] = (string)$node; }
}
$connKeyed = count($keyedNodes) > 0;
$time = date('H:i:s M d');
$timezone = date('T');
$rows = array();
foreach (array_unique(is_array($status['connected_nodes']) ? $status['connected_nodes'] : array()) as $node) {
    $node = trim($node);
    if (!preg_match('/^[0-9]{1,8}$/D', $node) || (int)$node < 1) { continue; }
    $peer = isset($linkKeying[$node]) && is_array($linkKeying[$node]) ? $linkKeying[$node] : array();
    $peerKeyed = !empty($peer['ptt']);
    // Follow Allmon3's RX/TX and connected-node keying classification.
    if (empty($status['ok'])) { $source = 'Status unavailable'; }
    elseif ($rxKeyed && ($txKeyed || !$txeKeyed)) { $source = 'Radio RX'; }
    elseif ($connKeyed && $txKeyed && !$rxKeyed) { $source = $peerKeyed ? 'Node TX' : 'Idle'; }
    elseif ($txKeyed && !$rxKeyed && !$connKeyed) { $source = 'System TX'; }
    elseif (!$txKeyed && !$rxKeyed && !$txeKeyed && $peerKeyed) { $source = 'Node playback'; }
    elseif ($peerKeyed) { $source = 'Node RX'; }
    else { $source = 'Idle'; }
    $rows[] = array(
        'time' => $time,
        'mode' => 'ASL',
        'node' => $node,
        'name' => isset($names[$node]) ? $names[$node] : '',
        'target' => $publicNode,
        'source' => $source,
        'keyed' => !empty($status['ok']) && $source !== 'Idle',
        'duration' => $peerKeyed && isset($peer['seconds_since_key']) ? (int)$peer['seconds_since_key'] : null,
        'loss' => '0%',
        'ber' => '0.0%'
    );
}
echo json_encode(array('ok' => true, 'telemetry' => !empty($status['ok']), 'public_node' => $publicNode,
    'timezone' => $timezone, 'rows' => $rows), JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
