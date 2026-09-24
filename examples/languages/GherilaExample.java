import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

// Java 11+, using only the standard library. Parse the response with your JSON library.
public class GherilaExample {
  public static void main(String[] args) throws Exception {
    boolean installing = args.length == 1 && args[0].equals("install");
    if (args.length > 0 && !installing) throw new IllegalArgumentException("Expected install or no arguments.");
    String python = System.getenv("GHERILA_PYTHON");
    List<String> command;
    if (!installing && python != null && !python.isEmpty()) {
      command = List.of(python, "-u", "-m", "gherila");
    } else {
      String launcher = System.getenv("GHERILA_LAUNCHER");
      if (System.getProperty("os.name").toLowerCase().contains("win")) {
        command = List.of("powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
          launcher == null ? "runtime/gherila.ps1" : launcher);
      } else {
        command = List.of("/bin/sh", launcher == null ? "runtime/gherila.sh" : launcher);
      }
    }
    if (installing) { command = new ArrayList<>(command); command.add("install"); }
    String request = System.getenv("GHERILA_REQUEST");
    if (request == null) {
      request = "{\"id\":\"example\",\"platform\":\"github\",\"method\":\"get_user\",\"kwargs\":{\"username\":\"octocat\"}}";
    }
    Process process = new ProcessBuilder(command)
      .redirectError(ProcessBuilder.Redirect.INHERIT).start();
    try {
      try (var input = process.getOutputStream()) {
        if (!installing) input.write((request + "\n").getBytes(StandardCharsets.UTF_8));
      }
      String response = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
      int status = process.waitFor();
      if (status != 0) throw new IllegalStateException("Gherila exited with " + status);
      // Provider errors are in the JSON envelope even when the worker exits successfully.
      System.out.print(response);
    } finally {
      process.destroy();
    }
  }
}
