<?php
// SPDX-License-Identifier: MIT
// Version: 1.0.0
// Created: 2026-11-09T23:33:00-05:00 by KE2HNI

/** Read completed USRP2M17 voice events as rows compatible with DVSwitch history. */
function dvsM17ActivityRows($paths = null, $historyPath = null)
{
    if ($paths === null) {
        $paths = glob('/var/log/usrp2m17/USRP2M17*.log') ?: array();
    }
    if ($historyPath === null) {
        $historyPath = '/var/lib/dvswitch-m17-dashboard/reflector-history.tsv';
    }

    $history = array();
    if (is_file($historyPath) && is_readable($historyPath) && !is_link($historyPath)) {
        foreach ((array)file($historyPath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
            $fields = explode("\t", $line, 3);
            if (count($fields) === 3 && ctype_digit($fields[0]) && $fields[1] !== '') {
                $history[] = array((int)$fields[0], $fields[1], trim($fields[2]));
            }
        }
    }

    $events = array();
    $sequence = 0;
    foreach ((array)$paths as $path) {
        if (!is_string($path) || !is_file($path) || !is_readable($path) || is_link($path)) { continue; }
        $handle = @fopen($path, 'rb');
        if ($handle === false) { continue; }
        $size = @filesize($path);
        if (is_int($size) && $size > 1048576) {
            @fseek($handle, $size - 1048576);
            @fgets($handle); // discard a potentially partial line
        }
        $lines = array();
        while (($line = fgets($handle)) !== false) {
            $line = trim($line);
            if ($line !== '') { $lines[] = $line; }
        }
        fclose($handle);
        if (count($lines) > 2000) { $lines = array_slice($lines, -2000); }

        foreach ($lines as $line) {
            if (!preg_match('/^[A-Z]: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\.(\d{1,6}) (M17|USRP) received end of voice transmission from ([^,\s]+), ([0-9]+(?:\.[0-9]+)?) seconds\s*$/', $line, $match)) { continue; }
            $date = DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u', $match[1].'.'.str_pad($match[2], 6, '0'), new DateTimeZone('UTC'));
            if ($date === false) { continue; }
            $errors = DateTimeImmutable::getLastErrors();
            if (is_array($errors) && ($errors['warning_count'] !== 0 || $errors['error_count'] !== 0)) { continue; }
            $call = trim(preg_replace('/[\x00-\x1F\x7F]/', '', $match[4]));
            if ($call === '' || strlen($call) > 20) { continue; }

            $epoch = (int)$date->format('U');
            $target = 'M17 reflector';
            $historyAt = null;
            foreach ($history as $selection) {
                if ($selection[0] <= $epoch && ($historyAt === null || $selection[0] >= $historyAt)) {
                    $target = $selection[2] !== '' ? $selection[2] : $selection[1];
                    $historyAt = $selection[0];
                }
            }
            $source = $match[3] === 'M17' ? 'Net' : 'LNet';
            $row = array($date->format('Y-m-d H:i:s.v'), 'M17', $call, '', $target, $source,
                number_format((float)$match[5], 1, '.', ''), '0%', '0.0%', '', '');
            $events[] = array('row' => $row, 'sequence' => $sequence++);
        }
    }

    usort($events, function ($left, $right) {
        $time = strcmp($right['row'][0], $left['row'][0]);
        return $time !== 0 ? $time : ($right['sequence'] <=> $left['sequence']);
    });
    return array_map(function ($event) { return $event['row']; }, $events);
}

/** Add M17 network and local events, retaining the newest entry per caller/source. */
function dvsM17MergeActivity($rows, $paths = null, $historyPath = null)
{
    $combined = array_merge(is_array($rows) ? $rows : array(), dvsM17ActivityRows($paths, $historyPath));
    usort($combined, function ($left, $right) {
        return strcmp((string)($right[0] ?? ''), (string)($left[0] ?? ''));
    });
    $seen = array();
    $latest = array();
    foreach ($combined as $row) {
        if (!is_array($row) || count($row) < 6) { continue; }
        if (($row[1] ?? '') === 'M17') {
            $key = trim((string)($row[2] ?? '')).'#M17#'.(string)($row[5] ?? '');
            if (isset($seen[$key])) { continue; }
            $seen[$key] = true;
        }
        $latest[] = $row;
    }
    return $latest;
}
?>
