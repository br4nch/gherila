#ifndef GHERILA_H
#define GHERILA_H

/* C99 / C++11. Pass a launcher path or NULL to use GHERILA_LAUNCHER/default.
 * Installation writes one JSON runtime report to stdout and returns its status.
 * Bridge mode inherits stdin/stdout/stderr for the documented JSON protocol.
 * Paths are passed as arguments, never evaluated as shell commands.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#include <wchar.h>
#else
#include <errno.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

static inline int gherila_run(const char *launcher, const char *mode) {
  if (mode && strcmp(mode, "install") && strcmp(mode, "--describe")) {
    fputs("Gherila: expected install, --describe, or no mode.\n", stderr);
    return 2;
  }
#ifdef _WIN32
  wchar_t *path;
  if (launcher && *launcher) {
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, launcher, -1, NULL, 0);
    if (!count) return 1;
    path = (wchar_t *)malloc((size_t)count * sizeof(wchar_t));
    if (!path) return 1;
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, launcher, -1, path, count)) {
      free(path); return 1;
    }
  } else {
    DWORD count = GetEnvironmentVariableW(L"GHERILA_LAUNCHER", NULL, 0);
    const wchar_t *fallback = L"runtime/gherila.ps1";
    size_t length = count ? (size_t)count : wcslen(fallback) + 1;
    path = (wchar_t *)malloc(length * sizeof(wchar_t));
    if (!path) return 1;
    if (count) {
      DWORD written = GetEnvironmentVariableW(L"GHERILA_LAUNCHER", path, count);
      if (!written || written >= count) { free(path); return 1; }
    } else { wcscpy(path, fallback); }
  }
  /* Quotes/newlines are not valid script filenames. A trailing backslash
   * would escape the closing Windows argument quote and denotes a directory. */
  size_t length = wcslen(path);
  if (!length || wcspbrk(path, L"\"\r\n") || path[length - 1] == L'\\') {
    fputs("Gherila: invalid launcher filename.\n", stderr);
    free(path); return 1;
  }
  const wchar_t *suffix = !mode ? L"" : !strcmp(mode, "install") ? L" install" : L" --describe";
  size_t capacity = length + 180;
  wchar_t *command = (wchar_t *)malloc(capacity * sizeof(wchar_t));
  if (!command) { free(path); return 1; }
  int written = swprintf(command, capacity,
    L"powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"%ls\"%ls", path, suffix);
  free(path);
  if (written < 0) { free(command); return 1; }
  STARTUPINFOW startup;
  PROCESS_INFORMATION process;
  ZeroMemory(&startup, sizeof(startup));
  ZeroMemory(&process, sizeof(process));
  startup.cb = sizeof(startup);
  startup.dwFlags = STARTF_USESTDHANDLES;
  startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
  startup.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
  startup.hStdError = GetStdHandle(STD_ERROR_HANDLE);
  BOOL created = CreateProcessW(NULL, command, NULL, NULL, TRUE, 0, NULL, NULL, &startup, &process);
  free(command);
  if (!created) { fprintf(stderr, "Gherila: launcher failed (%lu).\n", GetLastError()); return 1; }
  DWORD status = 1;
  if (WaitForSingleObject(process.hProcess, INFINITE) == WAIT_OBJECT_0) {
    if (!GetExitCodeProcess(process.hProcess, &status)) status = 1;
  }
  CloseHandle(process.hThread);
  CloseHandle(process.hProcess);
  return (int)status;
#else
  if (!launcher || !*launcher) launcher = getenv("GHERILA_LAUNCHER");
  if (!launcher || !*launcher) launcher = "runtime/gherila.sh";
  pid_t child = fork();
  if (child < 0) { perror("Gherila: fork"); return 1; }
  if (child == 0) {
    execl("/bin/sh", "sh", launcher, mode, (char *)NULL);
    perror("Gherila: launcher");
    _exit(127);
  }
  int status;
  while (waitpid(child, &status, 0) < 0) {
    if (errno == EINTR) continue;
    perror("Gherila: waitpid"); return 1;
  }
  return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
#endif
}

static inline int gherila_install(const char *launcher) {
  return gherila_run(launcher, "install");
}

#endif
