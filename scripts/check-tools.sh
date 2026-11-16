#!/usr/bin/env bash
# Report which toolchains needed for research are installed.
set -u
export PATH="$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$PATH"

check() { # name, command, version-args, needed-for
  if command -v "$2" >/dev/null 2>&1; then
    printf "  ok       %-10s %s\n" "$1" "$("$2" $3 2>&1 | head -1)"
  else
    printf "  MISSING  %-10s needed for: %s\n" "$1" "$4"; missing=$((missing+1))
  fi
}
missing=0
echo "Core"
check git     git     --version  "everything"
check gh      gh      --version  "GitHub"
check gcc     gcc     --version  "MAGPIE, Quackle"
check make    make    --version  "MAGPIE"
echo "Engine toolchains"
check go      go      version    "Macondo"
check cargo   cargo   --version  "wolges"
check cmake   cmake   --version  "Quackle"
check clang   clang   --version  "MAGPIE (optional), sanitizers"
check qmake6  qmake6  --version  "Quackle GUI (qt6-base-dev)"
echo "Closed engines / RE"
check wine    wine    --version  "Elise"
check java    java    --version  "Ghidra"
check ghidra  ghidraRun ""       "reverse engineering"
echo "Benchmarking / ML"
check hyperfine hyperfine --version "benchmarks"
check perf    perf    --version  "profiling"
check uv      uv      --version  "Python / NN experiments"
check docker  docker  --version  "isolated builds"
echo
echo "CPU cores: $(nproc)   RAM: $(free -g | awk '/Mem:/{print $2}') GB"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "GPU: no NVIDIA GPU found"
echo "$missing tool(s) missing"
