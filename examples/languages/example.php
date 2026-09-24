<?php
// PHP 7.4+ supports argument arrays, avoiding shell quoting on every OS.
$python = getenv('GHERILA_PYTHON');
if ($python) {
  $command = [$python, '-u', '-m', 'gherila'];
} elseif (PHP_OS_FAMILY === 'Windows') {
  $command = ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
    getenv('GHERILA_LAUNCHER') ?: __DIR__ . '/../../runtime/gherila.ps1'];
} else {
  $command = ['/bin/sh', getenv('GHERILA_LAUNCHER') ?: __DIR__ . '/../../runtime/gherila.sh'];
}
$request = getenv('GHERILA_REQUEST') ?: json_encode([
  'id' => 'example', 'platform' => 'github', 'method' => 'get_user',
  'kwargs' => ['username' => 'octocat'],
], JSON_THROW_ON_ERROR);
$process = proc_open($command, [
  0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR,
], $pipes);
if (!is_resource($process)) { throw new RuntimeException('Could not start Gherila.'); }
try {
  $line = $request . "\n";
  for ($offset = 0; $offset < strlen($line); $offset += $written) {
    $written = fwrite($pipes[0], substr($line, $offset));
    if ($written === false || $written === 0) { throw new RuntimeException('Could not write the request.'); }
  }
  fclose($pipes[0]);
  $output = stream_get_contents($pipes[1]);
  fclose($pipes[1]);
} finally {
  foreach ($pipes as $pipe) { if (is_resource($pipe)) { fclose($pipe); } }
  $status = proc_close($process);
}
if ($status !== 0) { throw new RuntimeException("Gherila exited with $status"); }
$response = json_decode($output, true, 512, JSON_THROW_ON_ERROR);
if (array_key_exists('error', $response)) {
  fwrite(STDERR, json_encode($response['error'], JSON_THROW_ON_ERROR) . "\n");
  exit(1);
}
echo json_encode($response['result'], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE) . "\n";
