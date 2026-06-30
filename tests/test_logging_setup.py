"""Characterization tests for logging_setup (QA-08).

Exercises the real subprocess streaming primitive (`stream_run`) and its sibling
`run` against a trivial cross-platform child process — NOT mocks — plus the
`tail`, `job_log`/`job_log_path`, and `get_logger`/`configure_logging` helpers.

Note: `logging_setup` derives its log dirs from the module's own location
(`PROJECT_ROOT/logs`), independent of `config.DATA_DIR`, so isolation here
redirects `logging_setup.LOG_DIR`/`JOB_LOG_DIR` (not `config.DATA_DIR`).
"""

import logging
import subprocess
import sys

import pytest

from content_machine import logging_setup


class _ListHandler(logging.Handler):
    """Collects rendered log messages into a list for assertions."""

    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _capture_logger(name="cm_logging_test"):
    """A throwaway logger whose records we can inspect — keeps the subprocess
    helpers (`run`/`stream_run`) off the global `content_machine` logger."""
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = _ListHandler()
    logger.addHandler(handler)
    return logger, handler.messages


@pytest.fixture(autouse=True)
def _isolate_logging(tmp_path, monkeypatch):
    """Redirect the module's log dirs into tmp and force a fresh configuration
    per test, so nothing lands in the real repo `logs/` and global handler
    state never leaks between tests."""
    monkeypatch.setattr(logging_setup, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(logging_setup, "JOB_LOG_DIR", tmp_path / "logs" / "jobs")
    monkeypatch.setattr(logging_setup, "_configured", False)
    cm = logging.getLogger("content_machine")
    saved = cm.handlers[:]
    for h in saved:
        cm.removeHandler(h)
    yield
    for h in cm.handlers[:]:
        cm.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    for h in saved:
        cm.addHandler(h)


# --- stream_run: the subprocess streaming primitive --------------------------

def test_stream_run_fires_on_line_per_output_line_and_returns_zero():
    log, _messages = _capture_logger()
    seen = []
    cmd = [sys.executable, "-c", "import sys; print('hi'); print('e', file=sys.stderr)"]
    rc = logging_setup.stream_run(cmd, log, "echo", on_line=seen.append)
    assert rc == 0
    # stdout and stderr are merged (stderr=STDOUT), so both lines stream through
    assert "hi" in seen
    assert "e" in seen


def test_stream_run_raises_called_process_error_on_nonzero_exit():
    log, _messages = _capture_logger()
    cmd = [sys.executable, "-c", "import sys; sys.exit(3)"]
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        logging_setup.stream_run(cmd, log, "boom")
    assert excinfo.value.returncode == 3


def test_stream_run_swallows_on_line_callback_errors():
    log, _messages = _capture_logger()
    cmd = [sys.executable, "-c", "print('x')"]

    def explode(_line):
        raise ValueError("callback blew up")

    # a buggy progress parser must not break streaming
    assert logging_setup.stream_run(cmd, log, "swallow", on_line=explode) == 0


def test_stream_run_collapses_consecutive_duplicate_lines_in_log():
    log, messages = _capture_logger()
    seen = []
    cmd = [sys.executable, "-c", "print('dup'); print('dup'); print('end')"]
    logging_setup.stream_run(cmd, log, "dedupe", on_line=seen.append)
    # on_line still receives every raw line ...
    assert seen.count("dup") == 2
    # ... but the logger drops the immediately-repeated duplicate
    dup_logged = [m for m in messages if m.strip() == "dup"]
    assert len(dup_logged) == 1


# --- run: capture + return ----------------------------------------------------

def test_run_captures_output_and_returns_completed_process():
    log, _messages = _capture_logger()
    cmd = [sys.executable, "-c", "print('captured-stdout')"]
    proc = logging_setup.run(cmd, log, "capture")
    assert isinstance(proc, subprocess.CompletedProcess)
    assert proc.returncode == 0
    assert "captured-stdout" in proc.stdout


def test_run_raises_and_logs_stderr_on_failure():
    log, messages = _capture_logger()
    cmd = [sys.executable, "-c",
           "import sys; sys.stderr.write('boom-err'); sys.exit(2)"]
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        logging_setup.run(cmd, log, "failing")
    assert excinfo.value.returncode == 2
    assert "boom-err" in (excinfo.value.stderr or "")
    assert any("FAILED" in m for m in messages)


def test_run_raises_file_not_found_for_missing_tool():
    log, messages = _capture_logger()
    with pytest.raises(FileNotFoundError):
        logging_setup.run(["definitely_not_a_real_tool_zzz"], log, "missing")
    assert any("not found" in m for m in messages)


# --- tail ---------------------------------------------------------------------

def test_tail_returns_last_n_lines(tmp_path):
    p = tmp_path / "some.log"
    p.write_text("\n".join(f"line{i}" for i in range(10)), encoding="utf-8")
    assert logging_setup.tail(p, 3) == "line7\nline8\nline9"


def test_tail_returns_all_when_fewer_lines_than_n(tmp_path):
    p = tmp_path / "short.log"
    p.write_text("alpha\nbravo", encoding="utf-8")
    assert logging_setup.tail(p, 100) == "alpha\nbravo"


def test_tail_empty_file_returns_empty_string(tmp_path):
    p = tmp_path / "empty.log"
    p.write_text("", encoding="utf-8")
    assert logging_setup.tail(p) == ""


def test_tail_missing_file_returns_empty_string(tmp_path):
    assert logging_setup.tail(tmp_path / "nope.log") == ""


# --- job_log_path / job_log ---------------------------------------------------

def test_job_log_path_lives_under_job_log_dir(tmp_path):
    # JOB_LOG_DIR is redirected into tmp by the autouse fixture
    assert logging_setup.job_log_path("abc123") == tmp_path / "logs" / "jobs" / "abc123.log"


def test_job_log_writes_log_lines_into_the_job_file():
    job_id = "job-write"
    logger = logging_setup.get_logger("content_machine")
    with logging_setup.job_log(job_id):
        logger.info("inside the job pipeline")
    path = logging_setup.job_log_path(job_id)
    assert path.exists()
    assert "inside the job pipeline" in path.read_text(encoding="utf-8")


def test_job_log_adds_then_removes_exactly_one_handler():
    logging_setup.configure_logging()  # base handlers first
    logger = logging.getLogger("content_machine")
    before = len(logger.handlers)
    with logging_setup.job_log("handler-life"):
        during = len(logger.handlers)
    assert during == before + 1
    assert len(logger.handlers) == before


# --- get_logger / configure_logging ------------------------------------------

def test_get_logger_returns_logger_and_canonicalizes_names():
    assert isinstance(logging_setup.get_logger("content_machine"), logging.Logger)
    assert logging_setup.get_logger().name == "content_machine"
    assert logging_setup.get_logger("__main__").name == "content_machine"
    assert logging_setup.get_logger("").name == "content_machine"
    assert logging_setup.get_logger("content_machine.render").name == "content_machine.render"
    assert logging_setup.get_logger("some.deep.module").name == "content_machine.module"


def test_configure_logging_is_idempotent_and_sets_logger_state():
    logging_setup.configure_logging()
    logger = logging.getLogger("content_machine")
    assert logging_setup._configured is True
    assert logger.propagate is False
    assert logger.level == logging.INFO
    count = len(logger.handlers)
    assert count == 2  # StreamHandler + RotatingFileHandler
    logging_setup.configure_logging()  # second call must not duplicate handlers
    assert len(logger.handlers) == count
