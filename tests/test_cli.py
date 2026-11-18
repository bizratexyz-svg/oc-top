"""Unit tests for oc-top core analytics, SQLite loader, and CLI export."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

from oc_top.app import fmt_cost, fmt_tokens, main
from oc_top.db import OverviewStats, load_dashboard_data
from oc_top.harnesses import estimate_cost, load_opencode


def _create_mock_opencode_db(db_path: Path) -> None:
    """Create a minimal OpenCode SQLite database with sample sessions."""
    now_ms = int(time.time() * 1000)
    old_ms = int((time.time() - 40 * 86400) * 1000)

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE project (
            id TEXT PRIMARY KEY,
            name TEXT,
            worktree TEXT
        );
        CREATE TABLE session (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            title TEXT,
            directory TEXT,
            cost REAL,
            tokens_input INTEGER,
            tokens_output INTEGER,
            tokens_reasoning INTEGER,
            tokens_cache_read INTEGER,
            tokens_cache_write INTEGER,
            summary_additions INTEGER,
            summary_deletions INTEGER,
            model TEXT,
            agent TEXT,
            time_created INTEGER
        );
        """
    )
    conn.execute(
        "INSERT INTO project (id, name, worktree) VALUES (?, ?, ?)",
        ("proj-1", "demo-app", "/tmp/demo-app"),
    )
    conn.execute(
        """
        INSERT INTO session VALUES (
            'sess-1', 'proj-1', 'Implement CLI', '/tmp/demo-app',
            1.25, 10000, 2000, 500, 40000, 1000, 120, 30,
            '{"id": "claude-sonnet-4", "providerID": "anthropic"}',
            'opencode', ?
        )
        """,
        (now_ms,),
    )
    conn.execute(
        """
        INSERT INTO session VALUES (
            'sess-old', 'proj-1', 'Old Session', '/tmp/demo-app',
            5.00, 50000, 10000, 0, 0, 0, 10, 5,
            'gpt-5',
            'opencode', ?
        )
        """,
        (old_ms,),
    )
    conn.commit()
    conn.close()


def test_fmt_cost_and_tokens() -> None:
    assert fmt_cost(0.0123) == "$0.0123"
    assert fmt_cost(2.5) == "$2.500"
    assert fmt_cost(1234.56) == "$1,234.56"

    assert fmt_tokens(512) == "512"
    assert fmt_tokens(2_500) == "2.5K"
    assert fmt_tokens(3_450_000) == "3.45M"
    assert fmt_tokens(1_200_000_000) == "1.20B"


def test_estimate_cost() -> None:
    # claude-sonnet-4: $3/M in, $15/M out, $0.3/M cache_read, $3.75/M cache_write
    cost = estimate_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000, 0, 0)
    assert cost == pytest.approx(18.0)

    assert estimate_cost("unknown-local-model", 100_000, 50_000) == 0.0


def test_overview_stats_properties() -> None:
    stats = OverviewStats(
        total_cost=2.0,
        total_sessions=1,
        tokens_input=200,
        tokens_output=100,
        tokens_reasoning=50,
        tokens_cache_read=800,
        tokens_cache_write=50,
        additions=10,
        deletions=2,
    )
    assert stats.total_tokens == 1200
    assert stats.cache_hit_rate == pytest.approx(80.0)


def test_load_opencode_and_cutoff(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    _create_mock_opencode_db(db_path)

    all_recs, size_mb = load_opencode(db_path, cutoff_ts=None)
    assert len(all_recs) == 2
    assert size_mb > 0

    cutoff = time.time() - 7 * 86400
    recent_recs, _ = load_opencode(db_path, cutoff_ts=cutoff)
    assert len(recent_recs) == 1
    assert recent_recs[0].session_id == "sess-1"
    assert recent_recs[0].model_id == "claude-sonnet-4"
    assert recent_recs[0].provider_id == "anthropic"


def test_load_dashboard_data(tmp_path: Path) -> None:
    db_path = tmp_path / "opencode.db"
    _create_mock_opencode_db(db_path)

    data = load_dashboard_data(db_path, days=7, source="opencode")
    assert data.active_sources == ["opencode"]
    assert data.overview.total_sessions == 1
    assert data.overview.total_cost == pytest.approx(1.25)
    assert len(data.models) == 1
    assert data.models[0].model_id == "claude-sonnet-4"
    assert len(data.projects) == 1
    assert data.projects[0].name == "demo-app"
    assert len(data.daily) == 7


def test_cli_export_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "opencode.db"
    _create_mock_opencode_db(db_path)

    monkeypatch.setattr(
        sys,
        "argv",
        ["oc-top", "--db", str(db_path), "--source", "opencode", "--days", "7", "--export", "json"],
    )
    main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["active_sources"] == ["opencode"]
    assert payload["overview"]["total_sessions"] == 1
    assert payload["overview"]["total_cost_usd"] == pytest.approx(1.25)
    assert payload["models"][0]["model_id"] == "claude-sonnet-4"


def test_cli_export_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "opencode.db"
    _create_mock_opencode_db(db_path)

    monkeypatch.setattr(
        sys,
        "argv",
        ["oc-top", "--db", str(db_path), "--source", "opencode", "--days", "0", "--export", "csv"],
    )
    main()

    captured = capsys.readouterr()
    rows = list(csv.reader(io.StringIO(captured.out)))
    assert rows[0] == ["model_id", "provider_id", "sessions", "cost_usd", "tokens"]
    assert len(rows) == 3  # header + 2 models
