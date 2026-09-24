use std::env;
use std::io;
use std::process::{self, Command, ExitStatus, Stdio};

fn launcher() -> Command {
  let mut command;
  if cfg!(windows) {
    command = Command::new("powershell.exe");
    command.args(["-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"]);
    command.arg(env::var_os("GHERILA_LAUNCHER").unwrap_or_else(|| "runtime/gherila.ps1".into()));
  } else {
    command = Command::new("/bin/sh");
    command.arg(env::var_os("GHERILA_LAUNCHER").unwrap_or_else(|| "runtime/gherila.sh".into()));
  }
  command
}

// Call this from application setup. Prints the JSON report and propagates errors.
fn install() -> io::Result<ExitStatus> {
  launcher().arg("install").stdin(Stdio::null()).status()
}

fn main() -> io::Result<()> {
  let args: Vec<String> = env::args().skip(1).collect();
  let status = match args.as_slice() {
    [mode] if mode == "install" => install()?,
    [] => launcher().status()?, // Stream JSON requests on stdin, responses on stdout.
    [mode] if mode == "--describe" => launcher().arg(mode).status()?,
    _ => { eprintln!("Usage: gherila-rust [install|--describe]"); process::exit(2); }
  };
  process::exit(status.code().unwrap_or(1));
}
