"""Server-side log rotation & system stats — keeps the host lean."""

import logging
import os
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

_BOOT = time.monotonic()


def setup_log_rotation(log_dir: str | None = None, max_bytes: int = 5_242_880, backups: int = 3):
    """Attach a RotatingFileHandler to the root guardianbot logger.
    5 MB per file, 3 backups. Old files get nuked automatically."""
    log_path = Path(log_dir or ".") / "guardianbot.log"
    handler = RotatingFileHandler(
        str(log_path), maxBytes=max_bytes, backupCount=backups, encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logging.getLogger("guardianbot").addHandler(handler)
    return handler


def cleanup_old_logs(directory: str = ".", max_age_days: int = 7):
    """Wipe .log files older than max_age_days to reclaim disk."""
    cutoff = time.time() - (max_age_days * 86400)
    nuked = 0
    for f in Path(directory).glob("guardianbot*.log*"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                nuked += 1
        except OSError:
            pass
    return nuked


def get_server_stats() -> dict:
    """Grab system vitals. Works without psutil — just gives less data."""
    stats = {
        "uptime_seconds": int(time.monotonic() - _BOOT),
        "python": sys.version.split()[0],
        "pid": os.getpid(),
        "platform": sys.platform,
    }

    # uptime as human string
    secs = stats["uptime_seconds"]
    days, rem = divmod(secs, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hrs:
        parts.append(f"{hrs}h")
    parts.append(f"{mins}m")
    stats["uptime"] = " ".join(parts)

    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        stats["mem_rss_mb"] = round(mem.rss / 1048576, 1)
        stats["mem_vms_mb"] = round(mem.vms / 1048576, 1)
        stats["cpu_percent"] = proc.cpu_percent(interval=0.1)
        stats["threads"] = proc.num_threads()
        disk = psutil.disk_usage("/")
        stats["disk_used_gb"] = round(disk.used / 1073741824, 1)
        stats["disk_free_gb"] = round(disk.free / 1073741824, 1)
    except ImportError:
        # psutil not installed — no big deal
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            stats["mem_rss_mb"] = round(usage.ru_maxrss / 1024, 1)
        except (ImportError, AttributeError):
            stats["mem_rss_mb"] = "n/a"

    return stats
