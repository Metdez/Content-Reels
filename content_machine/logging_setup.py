"""Logging — global app log + per-job logs, both stored in the codebase under logs/.

  logs/content_machine.log     rotating app-wide log
  logs/jobs/<job_id>.log       one file per job (surfaced live in the web UI)

Use `get_logger(__name__)` anywhere. Wrap a job's pipeline in `with job_log(id):`
so everything logged during it also lands in that job's file. `run`/`stream_run`
log subprocess commands, durations, and (critically) stderr on failure, and
`stream_run` tees live output so long stages (whisper, ffmpeg) show progress
instead of looking stuck.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
JOB_LOG_DIR = LOG_DIR / "jobs"
FMT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
DATEFMT = "%H:%M:%S"

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    JOB_LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("content_machine")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        fmt = logging.Formatter(FMT, DATEFMT)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        fh = RotatingFileHandler(LOG_DIR / "content_machine.log",
                                 maxBytes=2_000_000, backupCount=3)
        fh.setFormatter(fmt)
        logger.addHandler(ch)
        logger.addHandler(fh)
    _configured = True


def get_logger(name: str = "content_machine") -> logging.Logger:
    configure_logging()
    if name in ("content_machine", "__main__", "") or name is None:
        return logging.getLogger("content_machine")
    short = name.rsplit(".", 1)[-1]
    return logging.getLogger(f"content_machine.{short}")


def job_log_path(job_id: str) -> Path:
    return JOB_LOG_DIR / f"{job_id}.log"


@contextmanager
def job_log(job_id: str):
    """Attach a per-job file handler for the duration of a pipeline run."""
    configure_logging()
    JOB_LOG_DIR.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(job_log_path(job_id))
    fh.setFormatter(logging.Formatter(FMT, DATEFMT))
    logger = logging.getLogger("content_machine")
    logger.addHandler(fh)
    try:
        yield
    finally:
        logger.removeHandler(fh)
        fh.close()


def tail(path: Path, lines: int = 200) -> str:
    if not path.exists():
        return ""
    data = path.read_text(errors="replace").splitlines()
    return "\n".join(data[-lines:])


def run(cmd: list[str], log: logging.Logger, desc: str, **kw) -> subprocess.CompletedProcess:
    """subprocess.run with logging; captures output, logs stderr on failure."""
    log.info("▶ %s", desc)
    log.debug("cmd: %s", " ".join(map(str, cmd)))
    t = time.time()
    try:
        p = subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)
        log.info("✓ %s (%.1fs)", desc, time.time() - t)
        return p
    except subprocess.CalledProcessError as e:
        log.error("✗ %s FAILED (exit %s)\nstderr: %s", desc, e.returncode,
                  (e.stderr or "")[:2000])
        raise
    except FileNotFoundError as e:
        log.error("✗ %s — tool not found: %s", desc, e)
        raise


def stream_run(cmd: list[str], log: logging.Logger, desc: str, **kw) -> int:
    """Run a command, teeing combined stdout/stderr to the log line-by-line so
    long-running stages show live progress. Returns exit code (raises on nonzero)."""
    log.info("▶ %s", desc)
    log.debug("cmd: %s", " ".join(map(str, cmd)))
    t = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, **kw)
    last = ""
    for line in proc.stdout:  # type: ignore[union-attr]
        line = line.rstrip()
        if line and line != last:
            log.info("  %s", line[:300])
            last = line
    proc.wait()
    if proc.returncode != 0:
        log.error("✗ %s FAILED (exit %s)", desc, proc.returncode)
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    log.info("✓ %s (%.1fs)", desc, time.time() - t)
    return proc.returncode
