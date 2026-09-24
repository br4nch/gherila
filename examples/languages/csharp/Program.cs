using System.Diagnostics;
using System.Text;
using System.Text.Json;

var python = Environment.GetEnvironmentVariable("GHERILA_PYTHON");
var launcher = Environment.GetEnvironmentVariable("GHERILA_LAUNCHER");
string executable;
string[] arguments;
if (!string.IsNullOrEmpty(python)) {
  executable = python;
  arguments = new[] { "-u", "-m", "gherila" };
} else if (OperatingSystem.IsWindows()) {
  executable = "powershell.exe";
  arguments = new[] { "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", launcher ?? "runtime/gherila.ps1" };
} else {
  executable = "/bin/sh";
  arguments = new[] { launcher ?? "runtime/gherila.sh" };
}
var request = Environment.GetEnvironmentVariable("GHERILA_REQUEST")
  ?? JsonSerializer.Serialize(new {
    id = "example", platform = "github", method = "get_user", kwargs = new { username = "octocat" }
  });
var info = new ProcessStartInfo(executable) {
  UseShellExecute = false, RedirectStandardInput = true, RedirectStandardOutput = true,
  StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8,
};
foreach (var argument in arguments) info.ArgumentList.Add(argument);
using var process = Process.Start(info) ?? throw new Exception("Could not start Gherila.");
var output = process.StandardOutput.ReadToEndAsync();
await process.StandardInput.WriteLineAsync(request);
process.StandardInput.Close();
await process.WaitForExitAsync();
if (process.ExitCode != 0) throw new Exception($"Gherila exited with {process.ExitCode}");
using var response = JsonDocument.Parse(await output);
if (response.RootElement.TryGetProperty("error", out var error)) throw new Exception(error.GetRawText());
Console.WriteLine(response.RootElement.GetProperty("result").GetRawText());
