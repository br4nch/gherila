package main

import (
  "bytes"
  "encoding/json"
  "fmt"
  "os"
  "os/exec"
  "runtime"
)

// Any operation from docs/bridge.md works here, with no Go dependencies.
func main() {
  executable := os.Getenv("GHERILA_PYTHON")
  arguments := []string{"-u", "-m", "gherila"}
  if executable == "" {
    launcher := os.Getenv("GHERILA_LAUNCHER")
    if runtime.GOOS == "windows" {
      if launcher == "" { launcher = "runtime/gherila.ps1" }
      executable = "powershell.exe"
      arguments = []string{"-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", launcher}
    } else {
      if launcher == "" { launcher = "runtime/gherila.sh" }
      executable = "/bin/sh"
      arguments = []string{launcher}
    }
  }
  request := os.Getenv("GHERILA_REQUEST")
  if request == "" {
    request = `{"id":"example","platform":"github","method":"get_user","kwargs":{"username":"octocat"}}`
  }
  command := exec.Command(executable, arguments...)
  command.Stdin = bytes.NewBufferString(request + "\n")
  command.Stderr = os.Stderr
  output, err := command.Output()
  if err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
  var response struct { Result json.RawMessage `json:"result"`; Error json.RawMessage `json:"error"` }
  if err = json.Unmarshal(output, &response); err != nil {
    fmt.Fprintln(os.Stderr, err); os.Exit(1)
  }
  if response.Error != nil { fmt.Fprintln(os.Stderr, string(response.Error)); os.Exit(1) }
  fmt.Println(string(response.Result))
}
