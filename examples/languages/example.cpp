#include "../../bindings/c/gherila.h"

int main(int argc, char **argv) {
  if (argc == 2 && !strcmp(argv[1], "install")) return gherila_install(nullptr);
  if (argc > 2) { fputs("Usage: gherila-cpp [install|--describe]\n", stderr); return 2; }
  return gherila_run(nullptr, argc == 2 ? argv[1] : nullptr);
}
