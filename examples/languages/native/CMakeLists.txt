cmake_minimum_required(VERSION 3.15)
project(gherila_examples LANGUAGES C CXX)
add_executable(gherila-c ../example.c)
add_executable(gherila-cpp ../example.cpp)
target_compile_features(gherila-c PRIVATE c_std_99)
target_compile_features(gherila-cpp PRIVATE cxx_std_11)
# Keep the examples in one predictable directory on single/multi-config hosts.
set_target_properties(gherila-c gherila-cpp PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/$<0:>")
