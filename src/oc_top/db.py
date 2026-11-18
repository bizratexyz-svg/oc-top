"""Multi-harness analytics aggregation layer (OpenCode, Claude Code, Codex CLI, Gemini CLI)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from oc_top.harnesses import (
    RawSessionRecord,
    load_claude_code,
    load_codex,
    load_gemini_cli,
    load_opencode,
)


def default_db_path() -> Path:
    """Return the default OpenCode SQLite database path."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "opencode" / "opencode.db"
    return Path.home() / ".local" / "share" / "opencode" / "opencode.db"


@dataclass
class OverviewStats:
    total_cost: float
    total_sessions: int
    tokens_input: int
    tokens_output: int
    tokens_reasoning: int
    tokens_cache_read: int
    tokens_cache_write: int
    additions: int
    deletions: int

    @property
    def total_tokens(self) -> int:
        return (
            self.tokens_input
            + self.tokens_output
            + self.tokens_reasoning
            + self.tokens_cache_read
            + self.tokens_cache_write
        )

    @property
    def cache_hit_rate(self) -> float:
        denom = self.tokens_input + self.tokens_cache_read
        if denom == 0:
            return 0.0
        return (self.tokens_cache_read / denom) * 100.0


@dataclass
class DailyStat:
    date: str  # YYYY-MM-DD
    cost: float
    tokens: int
    sessions: int


@dataclass
class ProjectStat:
    name: str
    directory: str
    sessions: int
    cost: float
    tokens_total: int
    additions: int
    deletions: int


@dataclass
class ModelStat:
    model_id: str
    provider_id: str
    sessions: int
    cost: float
    tokens_total: int


@dataclass
class SessionStat:
    session_id: str
    title: str
    project_name: str
    model_id: str
    agent: str
    cost: float
    tokens_total: int
    created_at: datetime


@dataclass
class DashboardData:
    overview: OverviewStats
    daily: list[DailyStat]
    projects: list[ProjectStat]
    models: list[ModelStat]
    top_sessions: list[SessionStat]
    db_size_mb: float
    active_sources: list[str] = field(default_factory=list)


def load_dashboard_data(
    db_path: Path,
    days: Optional[int] = None,
    source: str = "all",
) -> DashboardData:
    """Aggregate usage metrics across all enabled AI coding harnesses."""
    cutoff_ts = (time.time() - days * 86400) if days is not None else None
    records: list[RawSessionRecord] = []
    active_sources: list[str] = []
    db_size_mb = 0.0

    if source in ("all", "opencode"):
        oc_recs, db_size_mb = load_opencode(db_path, cutoff_ts)
        if oc_recs:
            records.extend(oc_recs)
            active_sources.append("opencode")

    if source in ("all", "claude"):
        cc_recs = load_claude_code(cutoff_ts)
        if cc_recs:
            records.extend(cc_recs)
            active_sources.append("claude-code")

    if source in ("all", "codex"):
        cx_recs = load_codex(cutoff_ts)
        if cx_recs:
            records.extend(cx_recs)
            active_sources.append("codex")

    if source in ("all", "gemini"):
        gm_recs = load_gemini_cli(cutoff_ts)
        if gm_recs:
            records.extend(gm_recs)
            active_sources.append("gemini-cli")

    total_cost = 0.0
    t_in = t_out = t_reason = t_cread = t_cwrite = 0
    total_add = total_del = 0

    daily_map: dict[str, dict[str, float | int]] = {}
    proj_map: dict[str, dict[str, float | int | str]] = {}
    model_map: dict[tuple[str, str], dict[str, float | int]] = {}
    sessions_list: list[SessionStat] = []

    for r in records:
        tok_total = (
            r.tokens_input
            + r.tokens_output
            + r.tokens_reasoning
            + r.tokens_cache_read
            + r.tokens_cache_write
        )

        total_cost += r.cost
        t_in += r.tokens_input
        t_out += r.tokens_output
        t_reason += r.tokens_reasoning
        t_cread += r.tokens_cache_read
        t_cwrite += r.tokens_cache_write
        total_add += r.additions
        total_del += r.deletions

        day_key = r.created_at.strftime("%Y-%m-%d")
        if day_key not in daily_map:
            daily_map[day_key] = {"cost": 0.0, "tokens": 0, "sessions": 0}
        daily_map[day_key]["cost"] = float(daily_map[day_key]["cost"]) + r.cost
        daily_map[day_key]["tokens"] = int(daily_map[day_key]["tokens"]) + tok_total
        daily_map[day_key]["sessions"] = int(daily_map[day_key]["sessions"]) + 1

        if r.project_name not in proj_map:
            proj_map[r.project_name] = {
                "directory": r.directory,
                "sessions": 0,
                "cost": 0.0,
                "tokens": 0,
                "add": 0,
                "del": 0,
            }
        proj_map[r.project_name]["sessions"] = int(proj_map[r.project_name]["sessions"]) + 1
        proj_map[r.project_name]["cost"] = float(proj_map[r.project_name]["cost"]) + r.cost
        proj_map[r.project_name]["tokens"] = int(proj_map[r.project_name]["tokens"]) + tok_total
        proj_map[r.project_name]["add"] = int(proj_map[r.project_name]["add"]) + r.additions
        proj_map[r.project_name]["del"] = int(proj_map[r.project_name]["del"]) + r.deletions

        m_key = (r.model_id, r.provider_id)
        if m_key not in model_map:
            model_map[m_key] = {"sessions": 0, "cost": 0.0, "tokens": 0}
        model_map[m_key]["sessions"] = int(model_map[m_key]["sessions"]) + 1
        model_map[m_key]["cost"] = float(model_map[m_key]["cost"]) + r.cost
        model_map[m_key]["tokens"] = int(model_map[m_key]["tokens"]) + tok_total

        sessions_list.append(
            SessionStat(
                session_id=r.session_id,
                title=r.title,
                project_name=r.project_name,
                model_id=r.model_id,
                agent=r.agent,
                cost=r.cost,
                tokens_total=tok_total,
                created_at=r.created_at,
            )
        )

    if days is not None:
        today = datetime.now().date()
        daily_stats: list[DailyStat] = []
        for i in range(days - 1, -1, -1):
            d_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            entry = daily_map.get(d_str)
            daily_stats.append(
                DailyStat(
                    date=d_str,
                    cost=float(entry["cost"]) if entry else 0.0,
                    tokens=int(entry["tokens"]) if entry else 0,
                    sessions=int(entry["sessions"]) if entry else 0,
                )
            )
    else:
        daily_stats = [
            DailyStat(
                date=k,
                cost=float(v["cost"]),
                tokens=int(v["tokens"]),
                sessions=int(v["sessions"]),
            )
            for k, v in sorted(daily_map.items())[-30:]
        ]

    projects = sorted(
        [
            ProjectStat(
                name=k,
                directory=str(v["directory"]),
                sessions=int(v["sessions"]),
                cost=float(v["cost"]),
                tokens_total=int(v["tokens"]),
                additions=int(v["add"]),
                deletions=int(v["del"]),
            )
            for k, v in proj_map.items()
        ],
        key=lambda x: (x.cost, x.tokens_total),
        reverse=True,
    )

    models = sorted(
        [
            ModelStat(
                model_id=k[0],
                provider_id=k[1],
                sessions=int(v["sessions"]),
                cost=float(v["cost"]),
                tokens_total=int(v["tokens"]),
            )
            for k, v in model_map.items()
        ],
        key=lambda x: (x.cost, x.tokens_total),
        reverse=True,
    )

    top_sessions = sorted(
        sessions_list,
        key=lambda x: (x.cost, x.tokens_total),
        reverse=True,
    )[:50]

    overview = OverviewStats(
        total_cost=total_cost,
        total_sessions=len(records),
        tokens_input=t_in,
        tokens_output=t_out,
        tokens_reasoning=t_reason,
        tokens_cache_read=t_cread,
        tokens_cache_write=t_cwrite,
        additions=total_add,
        deletions=total_del,
    )

    return DashboardData(
        overview=overview,
        daily=daily_stats,
        projects=projects,
        models=models,
        top_sessions=top_sessions,
        db_size_mb=db_size_mb,
        active_sources=active_sources,
    )
