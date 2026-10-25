"""Read-only views of the OS process table, used to find the agent dogear runs under."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator, Protocol

MAX_HOPS = 64


class ProcessTable(Protocol):
    def parent(self, pid: int) -> tuple[int, str] | None:
        """(parent pid, this process's own command path or name), or None if unknown."""

    def open_files(self, pid: int) -> list[str]: ...
    def cwd(self, pid: int) -> str | None: ...
    def start_time(self, pid: int) -> float | None:
        """Process start as epoch seconds."""


# lsof prints bytes that aren't printable in the current locale as \xNN
_LSOF_ESCAPE = re.compile(rb"\\x([0-9a-fA-F]{2})")


def _unescape(m: "re.Match[bytes]") -> bytes:
    return bytes([int(m.group(1), 16)])


INTERPRETERS = {"node", "nodejs", "bun", "deno"}


def _run(args: list[str], c_locale: bool = False) -> str | None:
    """Run a helper; None on any failure. Only `ps -o lstart=` needs the C locale:
    lsof escapes non-ASCII path bytes under it."""
    env = {**os.environ, "LC_ALL": "C"} if c_locale else None
    try:
        r = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=10, env=env)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


class PosixPsTable:
    """macOS / BSD: ps and lsof."""

    def parent(self, pid: int) -> tuple[int, str] | None:
        out = _run(["ps", "-o", "ppid=,comm=", "-p", str(pid)])
        if not out or not out.strip():
            return None
        ppid, _, comm = out.strip().partition(" ")
        try:
            ppid_n = int(ppid)
        except ValueError:
            return None
        comm = comm.strip()
        if _is_interpreter(comm):
            args = _run(["ps", "-o", "args=", "-p", str(pid)])
            if args and args.split():
                comm = effective_command(args.split())
        return ppid_n, comm

    def _lsof_names(self, args: list[str]) -> list[str]:
        # paths are bytes in the filesystem encoding, not the locale's
        try:
            r = subprocess.run(["lsof", "-n", "-P", *args, "-Fn"], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return []
        return [os.fsdecode(_LSOF_ESCAPE.sub(_unescape, line[1:])) for line in r.stdout.splitlines() if line.startswith(b"n")]

    def open_files(self, pid: int) -> list[str]:
        return self._lsof_names(["-p", str(pid)])

    def cwd(self, pid: int) -> str | None:
        names = self._lsof_names(["-a", "-p", str(pid), "-d", "cwd"])
        return names[0] if names else None

    def start_time(self, pid: int) -> float | None:
        out = _run(["ps", "-o", "lstart=", "-p", str(pid)], c_locale=True)
        if not out or not out.strip():
            return None
        try:
            return time.mktime(time.strptime(" ".join(out.split()), "%a %b %d %H:%M:%S %Y"))
        except ValueError:
            return None


class ProcfsTable:
    """Linux: /proc."""

    def _stat(self, pid: int) -> list[str] | None:
        try:
            raw = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            return None
        # comm may contain spaces and parens; fields resume after the last ')'
        return raw[raw.rfind(")") + 2 :].split()

    def parent(self, pid: int) -> tuple[int, str] | None:
        fields = self._stat(pid)
        if not fields:
            return None
        try:
            cmd = os.readlink(f"/proc/{pid}/exe")
        except OSError:
            try:
                cmd = Path(f"/proc/{pid}/comm").read_text().strip()
            except OSError:
                cmd = ""
        if _is_interpreter(cmd):
            try:
                argv = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0")
                cmd = effective_command([a for a in argv if a]) or cmd
            except OSError:
                pass
        return int(fields[1]), cmd

    def open_files(self, pid: int) -> list[str]:
        out = []
        try:
            fds = os.listdir(f"/proc/{pid}/fd")
        except OSError:
            return []
        for fd in fds:
            try:
                out.append(os.readlink(f"/proc/{pid}/fd/{fd}"))
            except OSError:
                pass
        return out

    def cwd(self, pid: int) -> str | None:
        try:
            return os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            return None

    def start_time(self, pid: int) -> float | None:
        fields = self._stat(pid)
        if not fields:
            return None
        try:
            ticks = int(fields[19])  # field 22 overall
            btime = next(
                int(line.split()[1]) for line in Path("/proc/stat").read_text().splitlines() if line.startswith("btime")
            )
            return btime + ticks / os.sysconf("SC_CLK_TCK")
        except (OSError, ValueError, StopIteration, IndexError):
            return None


class WindowsTable:
    """Windows: one CIM query for the whole table (best effort; no open files or cwd)."""

    def __init__(self) -> None:
        self._table: dict[int, tuple[int, str]] | None = None

    def _load(self) -> dict[int, tuple[int, str]]:
        if self._table is None:
            script = (
                "Get-CimInstance Win32_Process | ForEach-Object { "
                '"$($_.ProcessId)`t$($_.ParentProcessId)`t$($_.ExecutablePath)`t$($_.Name)" }'
            )
            out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script]) or ""
            table = {}
            for line in out.splitlines():
                parts = line.rstrip("\r").split("\t")
                if len(parts) == 4 and parts[0].isdigit() and parts[1].isdigit():
                    table[int(parts[0])] = (int(parts[1]), parts[2] or parts[3])
            self._table = table
        return self._table

    def parent(self, pid: int) -> tuple[int, str] | None:
        return self._load().get(pid)

    def open_files(self, pid: int) -> list[str]:
        return []

    def cwd(self, pid: int) -> str | None:
        return None

    def start_time(self, pid: int) -> float | None:
        return None


def effective_command(argv: list[str]) -> str:
    """The program a process really is: for `node /path/cli.js …` that's the script."""
    if not argv:
        return ""
    base = argv[0].replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")
    if base in INTERPRETERS:
        return next((a for a in argv[1:] if not a.startswith("-")), argv[0])
    return argv[0]


def _is_interpreter(cmd: str) -> bool:
    return cmd.replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe") in INTERPRETERS


def default_table() -> ProcessTable:
    if sys.platform == "win32":
        return WindowsTable()
    if sys.platform.startswith("linux"):
        return ProcfsTable()
    return PosixPsTable()


def ancestors(table: ProcessTable, pid: int) -> Iterator[tuple[int, str]]:
    """Yield (pid, command) for each ancestor of pid, nearest first."""
    seen = {pid}
    cur = pid
    for _ in range(MAX_HOPS):
        info = table.parent(cur)
        if info is None:
            return
        ppid = info[0]
        if ppid <= 1 or ppid in seen:
            return
        pinfo = table.parent(ppid)
        if pinfo is None:
            return
        seen.add(ppid)
        yield ppid, pinfo[1]
        cur = ppid
