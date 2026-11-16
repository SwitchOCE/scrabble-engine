#!/usr/bin/env python3
"""Time MAGPIE commands in-process through libmagpie's C API (ctypes).

Every MAGPIE command, console or this library, costs ~70 ms of CPU (even
`shmoves 1`). So the `gen` mode below, which subtracts the cost of `shmoves 1`
from the cost of `generate`, is noise: movegen is far smaller than the jitter
in 70 ms. It is kept only to show that. The `run` mode is what the sim
benchmark uses (a 10 s sim dwarfs 70 ms). Our own code: it only calls the
public magpie_* functions.

Usage:
  magpie_api.py gen  POS.gcg REPS            -> (noise) REPS x `generate` minus REPS x `shmoves 1`
  magpie_api.py run  POS.gcg 'CMD' ['CMD'..] -> run commands once each, timed,
                                                printing their output
Env: MAGPIE_DIR (default reference/magpie), needs bin/libmagpie.so there.
"""
import ctypes
import os
import sys
import time

MAGPIE_DIR = os.environ.get(
    "MAGPIE_DIR", "/home/alex/code/scrabble-engine/reference/magpie")


def open_magpie():
    lib = ctypes.CDLL(os.path.join(MAGPIE_DIR, "bin", "libmagpie.so"))
    lib.magpie_create.restype = ctypes.c_void_p
    lib.magpie_create.argtypes = [ctypes.c_char_p]
    lib.magpie_run_sync.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.magpie_run_sync_human_readable.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.magpie_get_last_command_output.restype = ctypes.c_void_p
    lib.magpie_get_last_command_output.argtypes = [ctypes.c_void_p]
    lib.magpie_get_and_clear_error.restype = ctypes.c_void_p
    lib.magpie_get_and_clear_error.argtypes = [ctypes.c_void_p]
    lib.magpie_free_string.argtypes = [ctypes.c_void_p]
    os.chdir(MAGPIE_DIR)
    mp = lib.magpie_create(b"./data")
    return lib, mp


def take(lib, ptr):
    s = ctypes.string_at(ptr).decode("utf-8", "replace") if ptr else ""
    if ptr:
        lib.magpie_free_string(ptr)
    return s


def run(lib, mp, cmd, human=False):
    f = lib.magpie_run_sync_human_readable if human else lib.magpie_run_sync
    rc = f(mp, cmd.encode())
    if rc != 0:
        raise SystemExit(f"{cmd!r} failed ({rc}): {take(lib, lib.magpie_get_and_clear_error(mp))}")
    return take(lib, lib.magpie_get_last_command_output(mp))


def main():
    mode, pos = sys.argv[1], sys.argv[2]
    lib, mp = open_magpie()
    run(lib, mp, "set -lex CSW24 -threads 1 -savesettings false -autosavegcg false")
    run(lib, mp, f"load {pos}")
    run(lib, mp, "goto end")
    if mode == "gen":
        reps = int(sys.argv[3])
        run(lib, mp, "generate")  # warm-up

        def timed(cmd):
            t0 = time.perf_counter()
            for _ in range(reps):
                run(lib, mp, cmd)
            return time.perf_counter() - t0

        # Every command pays a fixed dispatch cost (~70 ms here); subtract the
        # cost of an equally dispatched no-op-ish command (`shmoves 1`).
        t_gen, t_noop = timed("generate"), timed("shmoves 1")
        us = (t_gen - t_noop) / reps * 1e6
        print(f"magpie\t{os.path.basename(pos)}\t{reps}\t{t_gen:.3f}\t{t_noop:.3f}\t{us:.1f}\t{1e6 / us:.0f}")
    else:
        for cmd in sys.argv[3:]:
            t0 = time.perf_counter()
            out = run(lib, mp, cmd, human=True)
            dt = time.perf_counter() - t0
            print(f"### {cmd}  ({dt:.3f} s)\n{out}")


if __name__ == "__main__":
    main()
