<?php
// Version: 1.0.0
declare(strict_types=1);

// ASL Support owns its mode, node-link, and favorite dashboard requests independently of Mode Buttons.
$send = static function (array $data, int $status = 200) {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
};

$run = static function (array $command, string $input = ''): array {
    $pipes = array();
    $process = proc_open($command, array(0 => array('pipe', 'r'), 1 => array('pipe', 'w'), 2 => array('pipe', 'w')), $pipes);
    if (!is_resource($process)) { throw new RuntimeException('Unable to start ASL command.'); }
    fwrite($pipes[0], $input); fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]); fclose($pipes[1]);
    $stderr = stream_get_contents($pipes[2]); fclose($pipes[2]);
    $status = proc_close($process);
    return array($status, trim($stdout), trim($stderr));
};

if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['favorites'])) {
    $path = '/etc/dvswitch-asl3-support/favorites.json';
    $favorites = is_readable($path) ? json_decode((string)file_get_contents($path), true) : array();
    $send(array('ok' => true, 'favorites' => is_array($favorites) ? $favorites : array()));
}
if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['nodeNames'])) {
    $path = is_readable('/var/lib/asterisk/astdb.txt') ? '/var/lib/asterisk/astdb.txt' : '/var/lib/asterisk/astdb';
    $names = array();
    if (is_readable($path)) {
        foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: array() as $line) {
            $fields = explode('|', $line, 4);
            if (count($fields) < 3) { continue; }
            $node = trim($fields[0]);
            $name = trim(preg_replace('/\s+/u', ' ', trim($fields[1] . ' ' . $fields[2])));
            if (preg_match('/^[0-9]{1,8}$/D', $node) && (int)$node > 0 && $name !== '') { $names[$node] = substr($name, 0, 64); }
        }
    }
    $send(array('ok' => true, 'names' => $names));
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || stripos((string)($_SERVER['CONTENT_TYPE'] ?? ''), 'application/json') !== 0) {
    $send(array('ok' => false, 'error' => 'Unsupported request.'), 405);
}
$request = json_decode((string)file_get_contents('php://input'), true);
if (!is_array($request) || !isset($request['action']) || !is_string($request['action'])) {
    $send(array('ok' => false, 'error' => 'Invalid request.'), 400);
}
try {
    if ($request['action'] === 'mode') {
        [$status, $stdout, $stderr] = $run(array('/usr/bin/sudo', '/opt/MMDVM_Bridge/dvswitch.sh', 'mode', 'ASL'));
        if ($status !== 0) { throw new RuntimeException($stderr !== '' ? $stderr : 'DVSwitch could not select ASL mode.'); }
        [$status, $stdout, $stderr] = $run(array('/usr/bin/sudo', '/usr/local/sbin/dvswitch-asl3-node-link'), "ENSURE_BRIDGE\n");
        if ($status !== 0) { throw new RuntimeException($stderr !== '' ? $stderr : 'ASL private-to-public bridge could not be established.'); }
        $send(array('ok' => true, 'mode' => 'ASL', 'message' => 'ASL mode selected.'));
    }
    if ($request['action'] === 'link') {
        $action = strtoupper(trim((string)($request['linkAction'] ?? '')));
        $target = trim((string)($request['node'] ?? ''));
        $disconnect = ($request['disconnectBeforeConnect'] ?? false) === true;
        if (!in_array($action, array('CONNECT', 'DISCONNECT', 'MONITOR', 'LOCAL_MONITOR', 'DISCONNECT_ALL'), true)) {
            throw new InvalidArgumentException('Select an ASL link action.');
        }
        if ($action !== 'DISCONNECT_ALL' && (!preg_match('/^[0-9]{1,8}$/D', $target) || (int)$target < 1)) {
            throw new InvalidArgumentException('Enter a non-zero numeric AllStar node number.');
        }
        $line = $action;
        if ($action !== 'DISCONNECT_ALL') { $line .= "\t" . $target; }
        if ($action === 'CONNECT' && $disconnect) { $line .= "\tDISCONNECT_BEFORE_CONNECT"; }
        [$status, $stdout, $stderr] = $run(array('/usr/bin/sudo', '/usr/local/sbin/dvswitch-asl3-node-link'), $line . "\n");
        if ($status !== 0) { throw new RuntimeException($stderr !== '' ? $stderr : 'ASL link command failed.'); }
        $send(array('ok' => true, 'message' => $stdout));
    }
    if ($request['action'] === 'saveFavorites') {
        [$status, $stdout, $stderr] = $run(array('/usr/bin/sudo', '/usr/local/sbin/dvswitch-asl3-favorites'), json_encode(array('favorites' => $request['favorites'] ?? null)));
        if ($status !== 0) { throw new RuntimeException($stderr !== '' ? $stderr : 'Unable to save ASL favorites.'); }
        $send(array('ok' => true, 'message' => $stdout));
    }
    throw new InvalidArgumentException('Unsupported ASL action.');
} catch (InvalidArgumentException $error) {
    $send(array('ok' => false, 'error' => $error->getMessage()), 400);
} catch (Throwable $error) {
    $send(array('ok' => false, 'error' => $error->getMessage()), 409);
}
