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
  python := os.Getenv("GHERILA_PYTHON")
  if python == "" {
    python = "python3"
    if runtime.GOOS == "windows" { python = "python" }
  }
  request := os.Getenv("GHERILA_REQUEST")
  if request == "" {
    request = `{"id":"example","platform":"github","method":"get_user","kwargs":{"username":"octocat"}}`
  }
  command := exec.Command(python, "-u", "-m", "gherila")
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
