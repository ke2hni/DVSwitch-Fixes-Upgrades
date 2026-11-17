<?php
// Version: 1.0.0; Created: 2026-11-17T15:05:00-05:00 by KE2HNI
// M17-only JSON feed for the dedicated Gateway Activity card.
header('Content-Type: application/json; charset=utf-8');
require_once __DIR__.'/dvswitch-m17-activity.php';
$rows = array();
foreach (dvsM17ActivityRows() as $row) {
    $stamp = DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.v', (string)($row[0] ?? ''), new DateTimeZone('UTC'));
    $rows[] = array(
        'time' => $stamp ? $stamp->setTimezone(new DateTimeZone(date_default_timezone_get()))->format('H:i:s M d') : '',
        'mode' => 'M17', 'node' => (string)($row[11] ?? ''), 'name' => (string)($row[2] ?? ''),
        'target' => (string)($row[4] ?? ''), 'source' => (string)($row[5] ?? ''),
        'duration' => (string)($row[6] ?? '—'), 'loss' => (string)($row[7] ?? '—'), 'ber' => (string)($row[8] ?? '—')
    );
}
echo json_encode(array('ok' => true, 'timezone' => date('T'), 'rows' => $rows), JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
?>
