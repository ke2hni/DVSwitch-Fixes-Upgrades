<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');

$output = array();
$status = 1;
exec('/usr/bin/sudo -n /usr/local/sbin/dvswitch-asl3-node-links 2>/dev/null', $output, $status);
if ($status !== 0) {
    echo json_encode(array('ok' => false, 'rows' => array()), JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
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

$rows = array();
$time = gmdate('Y-m-d H:i:s') . ' UTC';
foreach (array_unique($output) as $node) {
    $node = trim($node);
    if (!preg_match('/^[0-9]{1,8}$/D', $node) || (int)$node < 1) { continue; }
    $rows[] = array('time' => $time, 'node' => $node, 'name' => isset($names[$node]) ? $names[$node] : '', 'activity' => 'Connected');
}
echo json_encode(array('ok' => true, 'rows' => $rows), JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
