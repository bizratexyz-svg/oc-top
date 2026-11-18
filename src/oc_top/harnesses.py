"""Multi-harness log loaders for OpenCode, Claude Code, Codex CLI, and Gemini CLI."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class RawSessionRecord:
    """Normalized session record shared across all AI coding harnesses."""

    harness: str  # opencode | claude-code | codex | gemini-cli
    session_id: str
    title: str
    project_name: str
    directory: str
    model_id: str
    provider_id: str
    agent: str
    cost: float
    tokens_input: int
    tokens_output: int
    tokens_reasoning: int
    tokens_cache_read: int
    tokens_cache_write: int
    additions: int
    deletions: int
    created_at: datetime


# Fallback pricing per 1M tokens: (input, output, cache_read, cache_write)
_PRICING_PER_M: list[tuple[str, tuple[float, float, float, float]]] = [
    ("claude-opus-4", (15.0, 75.0, 1.5, 18.75)),
    ("claude-sonnet-4", (3.0, 15.0, 0.3, 3.75)),
    ("claude-3-5-sonnet", (3.0, 15.0, 0.3, 3.75)),
    ("claude-3-7-sonnet", (3.0, 15.0, 0.3, 3.75)),
    ("claude-haiku", (0.8, 4.0, 0.08, 1.0)),
    ("gpt-5", (2.5, 10.0, 0.25, 0.0)),
    ("gpt-4.1", (2.0, 8.0, 0.5, 0.0)),
    ("o3", (2.0, 8.0, 0.5, 0.0)),
    ("o4-mini", (1.1, 4.4, 0.275, 0.0)),
    ("codex", (2.0, 8.0, 0.5, 0.0)),
    ("gemini-2.5-pro", (1.25, 10.0, 0.31, 0.0)),
    ("gemini-2.5-flash", (0.15, 0.60, 0.0375, 0.0)),
    ("gemini-3", (1.25, 10.0, 0.31, 0.0)),
]


def estimate_cost(
    model_id: str,
    tokens_in: int,
    tokens_out: int,
    tokens_cache_read: int = 0,
    tokens_cache_write: int = 0,
) -> float:
    """Estimate USD cost from token counts when a harness does not store cost directly."""
    m = model_id.lower()
    for prefix, (p_in, p_out, p_cr, p_cw) in _PRICING_PER_M:
        if prefix in m:
            return (
                (tokens_in * p_in)
                + (tokens_out * p_out)
                + (tokens_cache_read * p_cr)
                + (tokens_cache_write * p_cw)
            ) / 1_000_000.0
    return 0.0


def _parse_iso_dt(val: object, fallback_ts: float) -> datetime:
    if isinstance(val, (int, float)) and val > 0:
        ts = val / 1000.0 if val > 1e11 else float(val)
        return datetime.fromtimestamp(ts)
    if isinstance(val, str) and val:
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.fromtimestamp(fallback_ts)


def _parse_opencode_model(raw: Optional[str]) -> tuple[str, str]:
    if not raw:
        return ("unknown", "-")
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            return (
                str(obj.get("id") or obj.get("modelID") or "unknown"),
                str(obj.get("providerID") or obj.get("provider") or "-"),
            )
        except json.JSONDecodeError:
            pass
    return (raw, "-")


def _project_label(name: Optional[str], worktree: Optional[str], directory: Optional[str]) -> str:
    if name:
        return name
    path_str = worktree or directory or "global"
    if path_str in ("/", "global", ""):
        return "global"
    return Path(path_str).name or path_str


def load_opencode(db_path: Path, cutoff_ts: Optional[float]) -> tuple[list[RawSessionRecord], float]:
    """Load sessions from OpenCode's opencode.db in read-only mode."""
    if not db_path.exists():
        return ([], 0.0)

    db_size_mb = db_path.stat().st_size / (1024 * 1024)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        where_clause = ""
        params: list[object] = []
        if cutoff_ts is not None:
            where_clause = "WHERE s.time_created >= ?"
            params.append(int(cutoff_ts * 1000))

        rows = conn.execute(
            f"""
            SELECT
                s.id, s.title, s.directory, s.cost,
                s.tokens_input, s.tokens_output, s.tokens_reasoning,
                s.tokens_cache_read, s.tokens_cache_write,
                s.summary_additions, s.summary_deletions,
                s.model, s.agent, s.time_created,
                p.name AS project_name, p.worktree AS project_worktree
            FROM session s
            LEFT JOIN project p ON s.project_id = p.id
            {where_clause}
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    records: list[RawSessionRecord] = []
    for r in rows:
        m_id, prov_id = _parse_opencode_model(r["model"])
        ts_ms = int(r["time_created"] or 0)
        dt = datetime.fromtimestamp(ts_ms / 1000.0) if ts_ms > 0 else datetime.now()
        records.append(
            RawSessionRecord(
                harness="opencode",
                session_id=str(r["id"]),
                title=str(r["title"] or "(untitled)"),
                project_name=_project_label(r["project_name"], r["project_worktree"], r["directory"]),
                directory=str(r["project_worktree"] or r["directory"] or "-"),
                model_id=m_id,
                provider_id=prov_id,
                agent=str(r["agent"] or "opencode"),
                cost=float(r["cost"] or 0.0),
                tokens_input=int(r["tokens_input"] or 0),
                tokens_output=int(r["tokens_output"] or 0),
                tokens_reasoning=int(r["tokens_reasoning"] or 0),
                tokens_cache_read=int(r["tokens_cache_read"] or 0),
                tokens_cache_write=int(r["tokens_cache_write"] or 0),
                additions=int(r["summary_additions"] or 0),
                deletions=int(r["summary_deletions"] or 0),
                created_at=dt,
            )
        )
    return (records, db_size_mb)


def load_claude_code(cutoff_ts: Optional[float]) -> list[RawSessionRecord]:
    """Load sessions from Claude Code (~/.claude/projects/*/*.jsonl)."""
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return []

    records: list[RawSessionRecord] = []
    for jsonl_path in base.glob("*/*.jsonl"):
        try:
            mtime = jsonl_path.stat().st_mtime
            if cutoff_ts is not None and mtime < cutoff_ts:
                continue

            t_in = t_out = t_cr = t_cw = 0
            cost = 0.0
            model_id = "claude-unknown"
            title = jsonl_path.stem[:32]
            first_ts: Optional[datetime] = None

            with jsonl_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if first_ts is None and obj.get("timestamp"):
                        first_ts = _parse_iso_dt(obj.get("timestamp"), mtime)

                    if obj.get("costUSD"):
                        cost += float(obj["costUSD"])

                    msg = obj.get("message")
                    if isinstance(msg, dict):
                        if msg.get("model"):
                            model_id = str(msg["model"])
                        usage = msg.get("usage")
                        if isinstance(usage, dict):
                            t_in += int(usage.get("input_tokens") or 0)
                            t_out += int(usage.get("output_tokens") or 0)
                            t_cr += int(usage.get("cache_read_input_tokens") or 0)
                            t_cw += int(usage.get("cache_creation_input_tokens") or 0)

            if t_in + t_out + t_cr + t_cw == 0:
                continue
            if cost == 0.0:
                cost = estimate_cost(model_id, t_in, t_out, t_cr, t_cw)

            proj_name = jsonl_path.parent.name.lstrip("-").split("-")[-1] or "claude-project"
            records.append(
                RawSessionRecord(
                    harness="claude-code",
                    session_id=jsonl_path.stem,
                    title=title,
                    project_name=proj_name,
                    directory=str(jsonl_path.parent),
                    model_id=model_id,
                    provider_id="claude-code",
                    agent="claude-code",
                    cost=cost,
                    tokens_input=t_in,
                    tokens_output=t_out,
                    tokens_reasoning=0,
                    tokens_cache_read=t_cr,
                    tokens_cache_write=t_cw,
                    additions=0,
                    deletions=0,
                    created_at=first_ts or datetime.fromtimestamp(mtime),
                )
            )
        except OSError:
            continue
    return records


def load_codex(cutoff_ts: Optional[float]) -> list[RawSessionRecord]:
    """Load sessions from OpenAI Codex CLI (~/.codex/sessions/**/*.jsonl)."""
    base = Path.home() / ".codex" / "sessions"
    if not base.exists():
        return []

    records: list[RawSessionRecord] = []
    for jsonl_path in base.rglob("*.jsonl"):
        try:
            mtime = jsonl_path.stat().st_mtime
            if cutoff_ts is not None and mtime < cutoff_ts:
                continue

            t_in = t_out = t_reason = t_cr = 0
            model_id = "codex"
            cwd = "-"
            first_ts: Optional[datetime] = None

            with jsonl_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if first_ts is None and obj.get("timestamp"):
                        first_ts = _parse_iso_dt(obj.get("timestamp"), mtime)

                    payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else obj
                    if payload.get("cwd"):
                        cwd = str(payload["cwd"])
                    if payload.get("model"):
                        model_id = str(payload["model"])

                    # Codex token_count event format
                    info = payload.get("info") if isinstance(payload.get("info"), dict) else None
                    usage = (
                        info.get("total_token_usage")
                        if info and isinstance(info.get("total_token_usage"), dict)
                        else payload.get("usage")
                    )
                    if isinstance(usage, dict):
                        # total_token_usage is cumulative; take max
                        t_in = max(t_in, int(usage.get("input_tokens") or 0))
                        t_out = max(t_out, int(usage.get("output_tokens") or 0))
                        t_reason = max(t_reason, int(usage.get("reasoning_output_tokens") or 0))
                        t_cr = max(t_cr, int(usage.get("cached_input_tokens") or 0))

            if t_in + t_out + t_reason + t_cr == 0:
                continue

            cost = estimate_cost(model_id, t_in, t_out + t_reason, t_cr, 0)
            proj_name = Path(cwd).name if cwd != "-" else "codex"
            records.append(
                RawSessionRecord(
                    harness="codex",
                    session_id=jsonl_path.stem,
                    title=jsonl_path.stem[:36],
                    project_name=proj_name,
                    directory=cwd,
                    model_id=model_id,
                    provider_id="codex-cli",
                    agent="codex",
                    cost=cost,
                    tokens_input=t_in,
                    tokens_output=t_out,
                    tokens_reasoning=t_reason,
                    tokens_cache_read=t_cr,
                    tokens_cache_write=0,
                    additions=0,
                    deletions=0,
                    created_at=first_ts or datetime.fromtimestamp(mtime),
                )
            )
        except OSError:
            continue
    return records


def load_gemini_cli(cutoff_ts: Optional[float]) -> list[RawSessionRecord]:
    """Load sessions from Gemini CLI (~/.gemini/tmp/**/chats/session-*.json)."""
    base = Path.home() / ".gemini" / "tmp"
    if not base.exists():
        return []

    records: list[RawSessionRecord] = []
    for json_path in base.rglob("session-*.json"):
        try:
            mtime = json_path.stat().st_mtime
            if cutoff_ts is not None and mtime < cutoff_ts:
                continue

            obj = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
            messages = obj.get("messages")
            if not isinstance(messages, list):
                continue

            t_in = t_out = t_reason = t_cr = 0
            model_id = "gemini-2.5-pro"
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                if msg.get("model"):
                    model_id = str(msg["model"])
                tok = msg.get("tokens")
                if isinstance(tok, dict):
                    t_in += int(tok.get("input") or 0)
                    t_out += int(tok.get("output") or 0)
                    t_reason += int(tok.get("thoughts") or 0)
                    t_cr += int(tok.get("cached") or 0)

            if t_in + t_out + t_reason + t_cr == 0:
                continue

            cost = estimate_cost(model_id, t_in, t_out + t_reason, t_cr, 0)
            dt = _parse_iso_dt(obj.get("startTime"), mtime)
            records.append(
                RawSessionRecord(
                    harness="gemini-cli",
                    session_id=str(obj.get("sessionId") or json_path.stem),
                    title=json_path.stem[:36],
                    project_name="gemini-cli",
                    directory=str(json_path.parent),
                    model_id=model_id,
                    provider_id="gemini-cli",
                    agent="gemini",
                    cost=cost,
                    tokens_input=t_in,
                    tokens_output=t_out,
                    tokens_reasoning=t_reason,
                    tokens_cache_read=t_cr,
                    tokens_cache_write=0,
                    additions=0,
                    deletions=0,
                    created_at=dt,
                )
            )
        except (OSError, json.JSONDecodeError):
            continue
    return records
