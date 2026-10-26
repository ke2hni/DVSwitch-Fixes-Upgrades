<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');

$file = '/var/lib/dvswitch-mods/asl3-link-activity.tsv';
$rows = array();
if (is_readable($file)) {
    $lines = file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: array();
    foreach (array_slice(array_reverse($lines), 0, 100) as $line) {
        $fields = explode("\t", $line, 4);
        if (count($fields) !== 4 || !ctype_digit($fields[0]) || !preg_match('/^[0-9]{1,8}$/D', $fields[1]) || !in_array($fields[3], array('Connected', 'Disconnected'), true)) { continue; }
        $node = $fields[1];
        $name = '';
        $astdb = is_readable('/var/lib/asterisk/astdb.txt') ? '/var/lib/asterisk/astdb.txt' : '/var/lib/asterisk/astdb';
        if (is_readable($astdb)) {
            foreach (file($astdb, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: array() as $dbline) {
                $entry = explode('|', $dbline, 4);
                if (count($entry) < 3 || trim($entry[0]) !== $node) { continue; }
                $name = trim($entry[1] . (trim($entry[2]) !== '' ? ' - ' . trim($entry[2]) : ''));
                break;
            }
        }
        $rows[] = array('time' => gmdate('Y-m-d H:i:s', (int)$fields[0]) . ' UTC', 'node' => $node, 'name' => $name, 'activity' => $fields[3]);
    }
}
echo json_encode(array('ok' => true, 'rows' => $rows), JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
