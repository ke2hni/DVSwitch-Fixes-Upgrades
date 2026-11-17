<?php
// Version: 1.0.1; Created: 2026-11-17T15:05:00-05:00 by KE2HNI
// Updated: 2026-11-17T16:15:00-05:00 by KE2HNI — load the activity helper from the installed include directory.
// M17-only JSON feed for the dedicated Gateway Activity card.
header('Content-Type: application/json; charset=utf-8');
$activityHelper = __DIR__.'/include/dvswitch-m17-activity.php';
if (!is_file($activityHelper)) { $activityHelper = __DIR__.'/dvswitch-m17-activity.php'; }
if (!is_file($activityHelper) || !is_readable($activityHelper)) {
    http_response_code(500);
    echo json_encode(array('ok' => false, 'error' => 'M17 activity helper is unavailable.'));
    exit;
}
require_once $activityHelper;
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
