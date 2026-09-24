# Local runtime bootstrap shared by every language. Never reads protocol stdin.
param([switch]$PrintPython, [Parameter(ValueFromRemainingArguments=$true)][string[]]$BridgeArgs = @())
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$core = Join-Path $PSScriptRoot 'core'
if (!(Test-Path (Join-Path $core 'pyproject.toml'))) { $core = Split-Path $PSScriptRoot -Parent }
if (!(Test-Path (Join-Path $core 'gherila/bridge.py'))) { throw 'Gherila: bundled Python core is missing.' }

function Get-Sha256([string]$Path) {
  $algorithm = [Security.Cryptography.SHA256]::Create()
  $stream = [IO.File]::OpenRead($Path)
  try { [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
  finally { $stream.Dispose(); $algorithm.Dispose() }
}

$arch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$arch = switch ($arch.ToUpperInvariant()) {
  'AMD64' { 'x86_64' }
  'ARM64' { 'aarch64' }
  default { throw 'Gherila: automatic setup supports x86_64 and ARM64 hosts.' }
}
$target = "$arch-pc-windows-msvc"
$cache = if ($env:GHERILA_CACHE_DIR) { $env:GHERILA_CACHE_DIR } else { Join-Path $env:LOCALAPPDATA 'gherila' }
$null = New-Item -ItemType Directory -Force -Path $cache
$cache = (Resolve-Path $cache).Path
$version = (Get-Content (Join-Path $PSScriptRoot 'uv-version') -Raw).Trim()
$files = @('pyproject.toml', 'setup.py', 'requirements.txt') | ForEach-Object { Join-Path $core $_ }
$files += @(Get-ChildItem (Join-Path $core 'gherila/*.py') | Sort-Object Name | ForEach-Object { $_.FullName })
$files += @('gherila.ps1', 'uv-version', 'uv-checksums.txt') | ForEach-Object { Join-Path $PSScriptRoot $_ }
$hashes = ($files | ForEach-Object { Get-Sha256 $_ }) -join "`n"
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $key = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($hashes))).Replace('-', '').ToLowerInvariant() }
finally { $sha.Dispose() }
$marker = Join-Path $cache "environments/$target-$key.txt"
# Windows PowerShell defaults to ANSI for BOM-less files; markers are UTF-8.
$python = if (Test-Path $marker) { [IO.File]::ReadAllText($marker, [Text.Encoding]::UTF8).Trim() } else { '' }

if (!$python -or !(Test-Path $python)) {
  $uvDir = Join-Path $cache "uv/$version/$target"
  $uv = Join-Path $uvDir 'uv.exe'
  $temp = Join-Path $cache ('setup.' + [Guid]::NewGuid().ToString('N'))
  $null = New-Item -ItemType Directory -Path $temp
  $unfinishedEnv = ''
  try {
    if (!(Test-Path $uv)) {
      if ($env:GHERILA_OFFLINE -eq '1') { throw 'Gherila: runtime is not cached; first setup needs internet access.' }
      $archive = "uv-$target.zip"
      $checksum = Get-Content (Join-Path $PSScriptRoot 'uv-checksums.txt') | Where-Object { ($_ -split '\s+')[1] -eq $archive }
      if (!$checksum) { throw 'Gherila: no verified runtime for this platform.' }
      $expected = ($checksum -split '\s+')[0]
      [Console]::Error.WriteLine('Gherila: preparing a private Python runtime (first use).')
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      $zip = Join-Path $temp 'uv.zip'
      # Use .NET directly: Windows PowerShell can inherit a PSModulePath from
      # PowerShell 7 that does not contain its hashing/web/archive cmdlets.
      $null = [Reflection.Assembly]::LoadWithPartialName('System.Net.Http')
      $web = [Net.Http.HttpClient]::new()
      $web.Timeout = [TimeSpan]::FromSeconds(180)
      try {
        $download = $web.GetByteArrayAsync("https://github.com/astral-sh/uv/releases/download/$version/$archive")
        [IO.File]::WriteAllBytes($zip, $download.GetAwaiter().GetResult())
      } finally { $web.Dispose() }
      if ((Get-Sha256 $zip) -ne $expected) { throw 'Gherila: runtime checksum mismatch; download was not executed.' }
      $null = [Reflection.Assembly]::LoadWithPartialName('System.IO.Compression.FileSystem')
      [IO.Compression.ZipFile]::ExtractToDirectory($zip, (Join-Path $temp 'uv'))
      $binary = Get-ChildItem (Join-Path $temp 'uv') -Filter uv.exe -Recurse | Select-Object -First 1
      if (!$binary) { throw 'Gherila: runtime archive is missing uv.exe.' }
      $null = New-Item -ItemType Directory -Force -Path $uvDir
      try { Move-Item $binary.FullName $uv -ErrorAction Stop }
      catch { if (!(Test-Path $uv)) { throw } }
    }
    $source = Join-Path $cache "sources/$key"
    if (!(Test-Path $source)) {
      $stage = Join-Path $temp 'core'
      $null = New-Item -ItemType Directory -Force -Path (Join-Path $stage 'gherila'), (Join-Path $cache 'sources')
      foreach ($name in @('pyproject.toml', 'setup.py', 'requirements.txt', 'README.md', 'LICENSE')) { Copy-Item (Join-Path $core $name) $stage }
      Copy-Item (Join-Path $core 'gherila/*.py') (Join-Path $stage 'gherila')
      try { [IO.Directory]::Move($stage, $source) }
      catch { if (!(Test-Path $source)) { throw } }
    }
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $cache 'python'
    $env:UV_PYTHON_BIN_DIR = Join-Path $cache 'bin'
    $env:UV_CACHE_DIR = Join-Path $cache 'uv-cache'
    $env:UV_PYTHON_DOWNLOADS = 'automatic'
    $env:UV_NO_PROGRESS = '1'
    $env:UV_NO_CONFIG = '1'
    if ($env:GHERILA_OFFLINE -eq '1') { $env:UV_OFFLINE = '1' }
    function Invoke-Setup([string]$Executable, [string[]]$Arguments) {
      # Setup gets empty stdin; the caller's protocol byte stream stays untouched.
      $setup = [Diagnostics.ProcessStartInfo]::new()
      $setup.FileName = $Executable
      $setup.UseShellExecute = $false
      $setup.RedirectStandardInput = $true
      $setup.RedirectStandardOutput = $true
      $setup.StandardOutputEncoding = [Text.Encoding]::UTF8
      $setup.Arguments = ($Arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
      $installer = [Diagnostics.Process]::Start($setup)
      try {
        $installer.StandardInput.Close()
        [Console]::Error.Write($installer.StandardOutput.ReadToEnd())
        $installer.WaitForExit()
        if ($installer.ExitCode -ne 0) { throw 'Gherila: Python or dependency installation failed; check the setup error above and internet access.' }
      } finally { $installer.Dispose() }
    }
    $null = New-Item -ItemType Directory -Force -Path (Join-Path $cache 'envs')
    $unfinishedEnv = Join-Path $cache ('envs/' + $key + '.' + [Guid]::NewGuid().ToString('N'))
    Invoke-Setup $uv @('venv', '--managed-python', '--python', '3.13', $unfinishedEnv)
    $python = Join-Path $unfinishedEnv 'Scripts/python.exe'
    Invoke-Setup $uv @('pip', 'install', '--python', $python, $source)
    Invoke-Setup $python @('-I', '-X', 'utf8', '-c', 'import gherila.bridge')
    if (!(Test-Path $python)) { throw 'Gherila: runtime setup did not produce a Python executable.' }
    $unfinishedEnv = ''
    $null = New-Item -ItemType Directory -Force -Path (Split-Path $marker -Parent)
    [IO.File]::WriteAllText((Join-Path $temp 'python.txt'), $python, [Text.UTF8Encoding]::new($false))
    Move-Item (Join-Path $temp 'python.txt') $marker -Force
  } finally {
    Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    if ($unfinishedEnv) { Remove-Item $unfinishedEnv -Recurse -Force -ErrorAction SilentlyContinue }
  }
}

if ($PrintPython -or ($BridgeArgs.Count -eq 1 -and $BridgeArgs[0] -eq '--print-python')) {
  [Console]::Out.WriteLine($python)
  exit 0
}
# Inherit the byte streams directly; PowerShell's text pipeline would alter JSON framing.
$start = [Diagnostics.ProcessStartInfo]::new()
$start.FileName = $python
$start.UseShellExecute = $false
$arguments = @('-I', '-X', 'utf8', '-u', '-m', 'gherila') + $BridgeArgs
foreach ($argument in $arguments) {
  if ($argument -match '["\r\n]') { throw 'Gherila: invalid bridge argument.' }
}
$start.Arguments = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
$process = [Diagnostics.Process]::Start($start)
try { $process.WaitForExit(); exit $process.ExitCode }
finally { $process.Dispose() }
