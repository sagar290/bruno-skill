"""Logging helpers with verbosity control."""

import sys

_VERBOSITY = 1  # 0=quiet, 1=normal, 2=verbose


def set_verbosity(level: int) -> None:
    global _VERBOSITY
    _VERBOSITY = max(0, min(2, level))


def print_success(msg: str) -> None:
    if _VERBOSITY >= 1:
        print(f"\033[32m\u2714 {msg}\033[0m")


def print_info(msg: str) -> None:
    if _VERBOSITY >= 1:
        print(f"\033[34m\u2139 {msg}\033[0m")


def print_verbose(msg: str) -> None:
    if _VERBOSITY >= 2:
        print(f"  {msg}")


def print_warning(msg: str) -> None:
    if _VERBOSITY >= 1:
        print(f"\033[33m\u26a0 {msg}\033[0m")


def print_error(msg: str) -> None:
    if _VERBOSITY >= 0:
        print(f"\033[31m\u2718 {msg}\033[0m", file=sys.stderr)