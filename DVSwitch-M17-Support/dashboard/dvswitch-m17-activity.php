<?php
// SPDX-License-Identifier: MIT
// Version: 1.0.5
// Updated: 2026-11-18T21:49:00-05:00 by KE2HNI — preserve the initial M17 target for older events without prior history.
// Created: 2026-11-09T23:33:00-05:00 by KE2HNI

/** Read active and completed USRP2M17 voice events as rows compatible with DVSwitch history. */
function dvsM17ActivityRows($paths = null, $historyPath = null, $rxHeartbeatPath = null)
{
    if ($paths === null) {
        $paths = glob('/var/log/usrp2m17/USRP2M17*.log') ?: array();
    }
    if ($historyPath === null) {
        $historyPath = '/var/lib/dvswitch-m17-dashboard/reflector-history.tsv';
    }
    if ($rxHeartbeatPath === null) { $rxHeartbeatPath = '/run/dvswitch-m17-audio-monitor/rx-active'; }

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
    $open = array();
    $sequence = 0;
    $paths = (array)$paths;
    sort($paths, SORT_STRING);
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
            if (!preg_match('/^[A-Z]: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\.(\d{1,6}) (M17|USRP) received (start|end) of voice transmission from ([^,\s]+)(?:, ([0-9]+(?:\.[0-9]+)?) seconds)?\s*$/', $line, $match)) { continue; }
            $date = DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u', $match[1].'.'.str_pad($match[2], 6, '0'), new DateTimeZone('UTC'));
            if ($date === false) { continue; }
            $errors = DateTimeImmutable::getLastErrors();
            if (is_array($errors) && ($errors['warning_count'] !== 0 || $errors['error_count'] !== 0)) { continue; }
            $call = trim(preg_replace('/[\x00-\x1F\x7F]/', '', $match[5]));
            if ($call === '' || strlen($call) > 20) { continue; }

            $epoch = (int)$date->format('U');
            $target = 'M17 reflector';
            $reflector = '';
            $firstSelection = null;
            $selectionAtEvent = null;
            foreach ($history as $selection) {
                if ($firstSelection === null || $selection[0] < $firstSelection[0]) { $firstSelection = $selection; }
                if ($selection[0] <= $epoch && ($selectionAtEvent === null || $selection[0] >= $selectionAtEvent[0])) {
                    $selectionAtEvent = $selection;
                }
            }
            // Pre-history events use the first recorded reflector, never today's most recent selection.
            $selected = $selectionAtEvent !== null ? $selectionAtEvent : $firstSelection;
            if ($selected !== null) {
                $reflector = $selected[1];
                $friendly = $selected[2] !== '' ? $selected[2] : $reflector;
                $target = $friendly.' ('.$reflector.')';
            }
            $source = $match[3] === 'M17' ? 'Net' : 'LNet';
            $row = array($date->format('Y-m-d H:i:s.v'), 'M17', $call, '', $target, $source,
                null, '0%', '0.0%', '', '', $reflector);
            if ($match[4] === 'start') {
                $open[$match[3]] = array('row' => $row, 'epoch' => $epoch, 'sequence' => $sequence++);
                continue;
            }
            $row[6] = number_format((float)($match[6] ?? 0), 1, '.', '');
            $events[] = array('row' => $row, 'sequence' => $sequence++);
            unset($open[$match[3]]);
        }
    }

    // Keep an unfinished network transmission visible only while the M17 audio heartbeat is fresh.
    $rxModified = is_string($rxHeartbeatPath) && is_file($rxHeartbeatPath) && !is_link($rxHeartbeatPath)
        ? @filemtime($rxHeartbeatPath) : false;
    $rxActive = $rxModified !== false && time() >= $rxModified && time() - $rxModified <= 5;
    if ($rxActive && isset($open['M17'])) { $events[] = $open['M17']; }

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

/** Retain the legacy feed helper for existing direct consumers; the dashboard no longer installs or requests it. */
function dvsM17LatestGatewayActivity($rows)
{
    $rows = is_array($rows) ? $rows : array();
    usort($rows, function ($left, $right) {
        return strcmp((string)($right[0] ?? ''), (string)($left[0] ?? ''));
    });
    $seen = array();
    $latest = array();
    foreach ($rows as $row) {
        if (!is_array($row) || count($row) < 6 || ($row[1] ?? '') !== 'M17') { continue; }
        $callsign = strtoupper(trim((string)($row[2] ?? '')));
        if ($callsign === '' || isset($seen[$callsign])) { continue; }
        $seen[$callsign] = true;
        $latest[] = $row;
    }
    return $latest;
}

?>
