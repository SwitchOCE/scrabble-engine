# Tooling

Run `scripts/check-tools.sh` to see what's installed.

## Needed per engine

| Need | For | Install (Ubuntu) |
| --- | --- | --- |
| gcc, make | MAGPIE | already installed |
| Go ≥ 1.26 | Macondo | `scripts/install-user-toolchains.sh` (installs to `~/.local/go`) |
| Rust (stable) | wolges | `scripts/install-user-toolchains.sh` (rustup, to `~/.cargo`) |
| cmake, clang, Qt 6 | Quackle (+ GUI) | `sudo apt install cmake clang qt6-base-dev` |
| Wine | Elise (Windows) | `sudo apt install wine64` |
| Ghidra (+ JDK 21) | reverse engineering closed engines | `sudo apt install openjdk-21-jdk`, then download Ghidra from ghidra-sre.org |
| hyperfine, perf | benchmarking | `sudo apt install hyperfine linux-tools-generic` |
| Python via uv, PyTorch | NN experiments | `uv` already installed; per-project venv |

## Hardware

6 cores, 14 GB RAM, no NVIDIA GPU. Fine for building engines, matches and small NN
experiments on CPU. Real training needs GPU compute elsewhere.
