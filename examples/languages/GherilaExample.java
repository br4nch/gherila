import java.nio.charset.StandardCharsets;

// Java 11+, using only the standard library. Parse the response with your JSON library.
public class GherilaExample {
  public static void main(String[] args) throws Exception {
    String python = System.getenv("GHERILA_PYTHON");
    if (python == null || python.isEmpty()) {
      python = System.getProperty("os.name").toLowerCase().contains("win") ? "python" : "python3";
    }
    String request = System.getenv("GHERILA_REQUEST");
    if (request == null) {
      request = "{\"id\":\"example\",\"platform\":\"github\",\"method\":\"get_user\",\"kwargs\":{\"username\":\"octocat\"}}";
    }
    Process process = new ProcessBuilder(python, "-u", "-m", "gherila")
      .redirectError(ProcessBuilder.Redirect.INHERIT).start();
    try {
      try (var input = process.getOutputStream()) {
        input.write((request + "\n").getBytes(StandardCharsets.UTF_8));
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
