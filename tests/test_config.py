"""QA-06 characterization tests for content_machine.config.

Pins CURRENT behavior of the path/tool resolvers. Every function reads its
inputs at call time — env via ``os.environ.get`` and the module globals
(``VENDOR_BIN``, ``WHISPER_DIR``, ``DEFAULT_MODEL``) by name — so we drive them
with ``monkeypatch.setattr(config, ...)`` + ``setenv``/``delenv`` and only
``importlib.reload`` for the module-level constants that are baked at import.
"""

import importlib
import os
import shutil
from pathlib import Path

import pytest

from content_machine import config

EXE = ".exe" if os.name == "nt" else ""  # config appends .exe only on Windows


# --- _resolve_binary ---------------------------------------------------------

def test_resolve_binary_env_override_wins(monkeypatch):
    # Override is returned verbatim — no existence/PATH check, even if bogus.
    monkeypatch.setenv("CM_FAKE_BIN", "/custom/path/to/ffmpeg")
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/ffmpeg")  # must be ignored
    assert config._resolve_binary("ffmpeg", "CM_FAKE_BIN") == "/custom/path/to/ffmpeg"


def test_resolve_binary_uses_path_when_no_override(monkeypatch):
    monkeypatch.delenv("CM_FAKE_BIN", raising=False)
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/local/bin/mytool" if n == "mytool" else None)
    assert config._resolve_binary("mytool", "CM_FAKE_BIN") == "/usr/local/bin/mytool"


def test_resolve_binary_uses_vendored_when_present(monkeypatch, tmp_path):
    monkeypatch.delenv("CM_FAKE_BIN", raising=False)
    monkeypatch.setattr(shutil, "which", lambda n: None)  # nothing on PATH
    vbin = tmp_path / "vendor_bin"
    vbin.mkdir()
    exe = vbin / ("ffmpeg" + EXE)
    exe.write_text("x")  # fake vendored binary
    monkeypatch.setattr(config, "VENDOR_BIN", vbin)
    assert config._resolve_binary("ffmpeg", "CM_FAKE_BIN") == str(exe)


def test_resolve_binary_bare_name_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("CM_FAKE_BIN", raising=False)
    monkeypatch.setattr(shutil, "which", lambda n: None)
    monkeypatch.setattr(config, "VENDOR_BIN", tmp_path / "empty")  # no vendored file
    assert config._resolve_binary("ghost", "CM_FAKE_BIN") == "ghost"


# --- _resolve_whisper_cli ----------------------------------------------------

def test_resolve_whisper_cli_env_override(monkeypatch):
    monkeypatch.setenv("CM_WHISPER_CLI", "/x/whisper-cli")
    assert config._resolve_whisper_cli() == Path("/x/whisper-cli")


def test_resolve_whisper_cli_finds_build_bin_candidate(monkeypatch, tmp_path):
    monkeypatch.delenv("CM_WHISPER_CLI", raising=False)
    wdir = tmp_path / "whisper"
    build_bin = wdir / "build" / "bin"
    build_bin.mkdir(parents=True)
    exe = build_bin / "whisper-cli.exe"  # first candidate in the search order
    exe.write_text("x")
    monkeypatch.setattr(config, "WHISPER_DIR", wdir)
    assert config._resolve_whisper_cli() == exe


def test_resolve_whisper_cli_falls_through_to_later_candidate(monkeypatch, tmp_path):
    # Only the last candidate (WHISPER_DIR/main) exists → loop must reach it.
    monkeypatch.delenv("CM_WHISPER_CLI", raising=False)
    wdir = tmp_path / "whisper2"
    wdir.mkdir()
    main = wdir / "main"
    main.write_text("x")
    monkeypatch.setattr(config, "WHISPER_DIR", wdir)
    assert config._resolve_whisper_cli() == main


def test_resolve_whisper_cli_default_fallback(monkeypatch, tmp_path):
    # Nothing built → modern default path under build/bin, even though absent.
    monkeypatch.delenv("CM_WHISPER_CLI", raising=False)
    wdir = tmp_path / "whisper_empty"
    monkeypatch.setattr(config, "WHISPER_DIR", wdir)
    expected = wdir / "build" / "bin" / ("whisper-cli.exe" if os.name == "nt" else "whisper-cli")
    assert config._resolve_whisper_cli() == expected


# --- model_path --------------------------------------------------------------

def test_model_path_default_and_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WHISPER_DIR", tmp_path)
    monkeypatch.setattr(config, "DEFAULT_MODEL", "base.en")
    assert config.model_path() == tmp_path / "models" / "ggml-base.en.bin"
    assert config.model_path("large-v3") == tmp_path / "models" / "ggml-large-v3.bin"
    # falsy model arg falls back to DEFAULT_MODEL (the `model or DEFAULT_MODEL` branch)
    assert config.model_path("") == tmp_path / "models" / "ggml-base.en.bin"


# --- require_tool ------------------------------------------------------------

def test_require_tool_accepts_existing_path(tmp_path):
    f = tmp_path / "tool.exe"
    f.write_text("x")
    assert config.require_tool(f, "install it") is None  # exists → no raise


def test_require_tool_accepts_name_on_path(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/found")
    assert config.require_tool("somename", "hint") is None  # which() hit → no raise


def test_require_tool_raises_with_hint_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda n: None)
    missing = tmp_path / "nope.exe"
    with pytest.raises(FileNotFoundError) as ei:
        config.require_tool(missing, "go install nope")
    msg = str(ei.value)
    assert "go install nope" in msg          # hint is surfaced
    assert "Required tool not found" in msg
    assert str(missing) in msg


# --- module-level constants resolve from env (baked at import) ---------------

def test_module_constants_resolve_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CM_DATA_DIR", str(tmp_path / "d"))
    monkeypatch.setenv("CM_WHISPER_DIR", str(tmp_path / "w"))
    monkeypatch.setenv("CM_WHISPER_MODEL", "tiny.en")
    try:
        importlib.reload(config)
        assert config.DATA_DIR == tmp_path / "d"
        assert config.WHISPER_DIR == tmp_path / "w"
        assert config.DEFAULT_MODEL == "tiny.en"
    finally:
        # restore pristine module state so reload doesn't leak to other tests
        for var in ("CM_DATA_DIR", "CM_WHISPER_DIR", "CM_WHISPER_MODEL"):
            monkeypatch.delenv(var, raising=False)
        importlib.reload(config)


def test_default_model_is_base_en_without_env(monkeypatch):
    monkeypatch.delenv("CM_WHISPER_MODEL", raising=False)
    try:
        importlib.reload(config)
        assert config.DEFAULT_MODEL == "base.en"
    finally:
        importlib.reload(config)
