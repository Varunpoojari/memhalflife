"""Volatility 3 runner + chain-of-custody manifest.

Nothing here touches the image except to read it. Hashes are computed before
analysis and appended to an append-only JSONL custody log.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

WINDOWS_PLUGINS = [
    "windows.info.Info",
    "windows.pslist.PsList",
    "windows.pstree.PsTree",
    "windows.cmdline.CmdLine",
    "windows.dlllist.DllList",
    "windows.malware.malfind.Malfind",
    "windows.malware.hollowprocesses.HollowProcesses",
    "windows.malware.suspicious_threads.SuspiciousThreads",
    "windows.malware.ldrmodules.LdrModules",
    "windows.netscan.NetScan",
    "windows.netstat.NetStat",
    "windows.handles.Handles",
    "windows.privileges.Privs",
    "windows.vadinfo.VadInfo",
    "windows.envars.Envars",
    "windows.scheduled_tasks.ScheduledTasks",
]

LINUX_PLUGINS = [
    "linux.pslist.PsList",
    "linux.pstree.PsTree",
    "linux.psaux.PsAux",
    "linux.bash.Bash",
    "linux.sockstat.Sockstat",
    "linux.lsof.Lsof",
    "linux.proc.Maps",
    "linux.elfs.Elfs",
    "linux.envars.Envars",
    "linux.malfind.Malfind",
]

PLUGINS = {"windows": WINDOWS_PLUGINS, "linux": LINUX_PLUGINS}
YARA_PLUGIN = {"windows": "windows.vadyarascan.VadYaraScan", "linux": "linux.vmayarascan.VmaYaraScan"}


def sha256_file(path: str | Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def custody_record(image: str | Path, **extra) -> dict:
    p = Path(image)
    return {
        "image": p.name,
        "size_bytes": p.stat().st_size,
        "sha256": sha256_file(p),
        "recorded_utc": utc_now(),
        **extra,
    }


def append_custody(log: str | Path, record: dict) -> None:
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with Path(log).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def build_command(vol: str, image: str | Path, plugin: str, extra: list[str] | None = None) -> list[str]:
    # -q quiet, -r json renderer; extra plugin args (e.g. --yara-file) come after the plugin name
    return [*vol.split(), "-q", "-r", "json", "-f", str(image), plugin, *(extra or [])]


@dataclass
class PluginRun:
    plugin: str
    ok: bool
    seconds: float
    detail: str = ""


def run_plugin(
    vol: str,
    image: str | Path,
    plugin: str,
    out_dir: Path,
    extra: list[str] | None = None,
    timeout: int = 3600,
) -> PluginRun:
    import time

    out_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            build_command(vol, image, plugin, extra),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        (out_dir / f"{plugin}.error.txt").write_text(str(exc))
        return PluginRun(plugin, False, time.monotonic() - start, str(exc))
    secs = time.monotonic() - start
    if proc.returncode != 0 or not proc.stdout.strip():
        (out_dir / f"{plugin}.error.txt").write_text(proc.stderr[-4000:] or "empty output")
        return PluginRun(plugin, False, secs, (proc.stderr or "empty output")[-200:])
    try:
        json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        (out_dir / f"{plugin}.error.txt").write_text(f"non-JSON output: {exc}")
        return PluginRun(plugin, False, secs, "non-JSON output")
    (out_dir / f"{plugin}.json").write_text(proc.stdout, encoding="utf-8")
    return PluginRun(plugin, True, secs)


def analyse_image(
    image: str | Path,
    os_name: str,
    out_dir: Path,
    vol: str = "vol",
    yara_file: str | None = None,
    timeout: int = 3600,
) -> list[PluginRun]:
    if os_name not in PLUGINS:
        raise ValueError(f"unsupported os {os_name!r}")
    if shutil.which(vol.split()[0]) is None:
        raise FileNotFoundError(
            f"Volatility 3 command {vol!r} not found. Install with `pip install volatility3` "
            "or pass --vol 'python3 /path/to/vol.py'."
        )
    runs = [run_plugin(vol, image, p, out_dir, timeout=timeout) for p in PLUGINS[os_name]]
    if yara_file:
        runs.append(
            run_plugin(vol, image, YARA_PLUGIN[os_name], out_dir, ["--yara-file", yara_file], timeout)
        )
    return runs
