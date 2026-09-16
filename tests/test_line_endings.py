"""Every tracked text file is stored with LF line endings.

.gitattributes normalises on commit for anyone who has it; this test is
for the case it does not cover - a file added through a tool that
bypasses the clean filter, or an editor that writes a bare CR. A CRLF
that slips in turns the next unrelated edit into a whole-file diff.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WINDOWS_NATIVE = {".bat", ".cmd", ".ps1"}
BINARY = {".png", ".jpg", ".gif", ".ico", ".whl", ".pdf"}


def _tracked_text_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z"],
            check=True, capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    names = [n for n in out.decode("utf-8").split("\0") if n]
    return [
        REPO / n for n in names
        if Path(n).suffix not in WINDOWS_NATIVE | BINARY and (REPO / n).is_file()
    ]


def test_tracked_text_files_use_lf_only() -> None:
    offenders = [
        p.relative_to(REPO).as_posix()
        for p in _tracked_text_files()
        if b"\r" in p.read_bytes()
    ]
    assert not offenders, "CR found in: " + ", ".join(offenders)
