"""Interactive Textual TUI for OpenCode token usage and cost analytics."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Sparkline, Static, TabbedContent, TabPane

from oc_top.db import DashboardData, default_db_path, load_dashboard_data


def fmt_cost(cost: float) -> str:
    if cost >= 100:
        return f"${cost:,.2f}"
    if cost >= 1:
        return f"${cost:.3f}"
    return f"${cost:.4f}"


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class StatCard(Static):
    """Compact KPI card."""

    def __init__(self, title: str, value: str, subtitle: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._value = value
        self._subtitle = subtitle

    def update_stat(self, value: str, subtitle: str = "") -> None:
        self._value = value
        self._subtitle = subtitle
        self.update(self._render_text())

    def _render_text(self) -> str:
        sub = f"\n[dim]{self._subtitle}[/dim]" if self._subtitle else ""
        return f"[bold dim]{self._title}[/bold dim]\n[bold cyan]{self._value}[/bold cyan]{sub}"

    def on_mount(self) -> None:
        self.update(self._render_text())


class OcTopApp(App[None]):
    """OpenCode Token & Cost TUI Dashboard."""

    TITLE = "oc-top"
    SUB_TITLE = "OpenCode Cost & Token Analytics"

    CSS = """
    Screen {
        background: $surface;
    }

    Screen.transparent,
    Screen.transparent #kpi-row,
    Screen.transparent #chart-box,
    Screen.transparent #tabs,
    Screen.transparent TabPane,
    Screen.transparent ContentSwitcher,
    Screen.transparent DataTable,
    Screen.transparent StatCard {
        background: transparent;
    }

    #kpi-row {
        height: 5;
        margin: 1 1 0 1;
    }

    StatCard {
        width: 1fr;
        height: 100%;
        border: round $primary;
        padding: 0 1;
        margin-right: 1;
        content-align: left middle;
    }

    StatCard:last-child {
        margin-right: 0;
    }

    #chart-box {
        height: 6;
        margin: 1 1 0 1;
        border: round $accent;
        padding: 0 1;
    }

    #chart-title {
        height: 1;
        color: $text-muted;
    }

    Sparkline {
        height: 3;
        width: 100%;
    }

    #tabs {
        height: 1fr;
        margin: 1 1 0 1;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("1", "set_range(7)", "7 Days"),
        Binding("2", "set_range(30)", "30 Days"),
        Binding("3", "set_range(0)", "All Time"),
        Binding("m", "show_tab('tab-models')", "Models"),
        Binding("p", "show_tab('tab-projects')", "Projects"),
        Binding("s", "show_tab('tab-sessions')", "Sessions"),
        Binding("t", "toggle_transparent", "Transparent"),
        Binding("r", "refresh_data", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        db_path: Path,
        initial_days: Optional[int] = 30,
        transparent: bool = False,
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.days: Optional[int] = initial_days
        self.transparent = transparent
        self.data: Optional[DashboardData] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="kpi-row"):
            yield StatCard("TOTAL COST", "-", id="card-cost")
            yield StatCard("TOTAL TOKENS", "-", id="card-tokens")
            yield StatCard("CACHE HIT RATE", "-", id="card-cache")
            yield StatCard("SESSIONS / DIFF", "-", id="card-sessions")
        with Vertical(id="chart-box"):
            yield Static("Daily Cost Trend", id="chart-title")
            yield Sparkline([], summary_function=max, id="daily-sparkline")
        with TabbedContent(id="tabs"):
            with TabPane("Models", id="tab-models"):
                yield DataTable(id="table-models", zebra_stripes=True)
            with TabPane("Projects", id="tab-projects"):
                yield DataTable(id="table-projects", zebra_stripes=True)
            with TabPane("Top Sessions", id="tab-sessions"):
                yield DataTable(id="table-sessions", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        if self.transparent:
            self.screen.add_class("transparent")
        self._setup_tables()
        self.action_refresh_data()

    def _setup_tables(self) -> None:
        t_proj = self.query_one("#table-projects", DataTable)
        t_proj.cursor_type = "row"
        t_proj.add_columns("Project", "Sessions", "Cost", "Tokens", "Diff (+/-)")

        t_mod = self.query_one("#table-models", DataTable)
        t_mod.cursor_type = "row"
        t_mod.add_columns("Model", "Provider", "Sessions", "Cost", "Tokens")

        t_ses = self.query_one("#table-sessions", DataTable)
        t_ses.cursor_type = "row"
        t_ses.add_columns("Date", "Project", "Title", "Model", "Cost", "Tokens")

    def action_set_range(self, days: int) -> None:
        self.days = None if days == 0 else days
        self.action_refresh_data()

    def action_show_tab(self, tab_id: str) -> None:
        self.query_one("#tabs", TabbedContent).active = tab_id

    def action_toggle_transparent(self) -> None:
        self.transparent = not self.transparent
        self.screen.set_class(self.transparent, "transparent")

    def action_refresh_data(self) -> None:
        self.data = load_dashboard_data(self.db_path, days=self.days)
        self._render_dashboard()

    def _render_dashboard(self) -> None:
        if not self.data:
            return

        ov = self.data.overview
        range_label = f"Last {self.days}d" if self.days else "All Time"
        db_gb = self.data.db_size_mb / 1024.0
        db_label = f"{db_gb:.1f} GB" if db_gb >= 1.0 else f"{self.data.db_size_mb:.0f} MB"
        self.sub_title = f"{range_label} | DB: {db_label}"

        self.query_one("#card-cost", StatCard).update_stat(
            fmt_cost(ov.total_cost),
            f"Range: {range_label}",
        )
        self.query_one("#card-tokens", StatCard).update_stat(
            fmt_tokens(ov.total_tokens),
            f"In {fmt_tokens(ov.tokens_input)} / Out {fmt_tokens(ov.tokens_output)}",
        )
        self.query_one("#card-cache", StatCard).update_stat(
            f"{ov.cache_hit_rate:.1f}%",
            f"Read {fmt_tokens(ov.tokens_cache_read)}",
        )
        self.query_one("#card-sessions", StatCard).update_stat(
            f"{ov.total_sessions:,}",
            f"+{ov.additions:,} / -{ov.deletions:,} lines",
        )

        # Sparkline
        daily = self.data.daily
        costs = [d.cost for d in daily]
        spark = self.query_one("#daily-sparkline", Sparkline)
        spark.data = costs if any(costs) else [0.0]
        if daily:
            peak = max(daily, key=lambda d: d.cost)
            self.query_one("#chart-title", Static).update(
                f"Daily Cost Trend ({daily[0].date} -> {daily[-1].date}) | Peak: {peak.date} ({fmt_cost(peak.cost)})"
            )

        # Projects table
        t_proj = self.query_one("#table-projects", DataTable)
        t_proj.clear()
        for p in self.data.projects:
            t_proj.add_row(
                p.name,
                str(p.sessions),
                fmt_cost(p.cost),
                fmt_tokens(p.tokens_total),
                f"+{p.additions:,} / -{p.deletions:,}",
            )

        # Models table
        t_mod = self.query_one("#table-models", DataTable)
        t_mod.clear()
        for m in self.data.models:
            t_mod.add_row(
                m.model_id,
                m.provider_id,
                str(m.sessions),
                fmt_cost(m.cost),
                fmt_tokens(m.tokens_total),
            )

        # Top sessions table
        t_ses = self.query_one("#table-sessions", DataTable)
        t_ses.clear()
        for s in self.data.top_sessions:
            title = s.title if len(s.title) <= 44 else s.title[:41] + "..."
            t_ses.add_row(
                s.created_at.strftime("%Y-%m-%d %H:%M"),
                s.project_name,
                title,
                s.model_id,
                fmt_cost(s.cost),
                fmt_tokens(s.tokens_total),
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="oc-top",
        description="Interactive TUI for OpenCode token usage and cost analytics.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db_path(),
        help="Path to opencode.db (default: ~/.local/share/opencode/opencode.db)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Initial lookback window in days (0 for all time, default: 30)",
    )
    parser.add_argument(
        "--transparent",
        action="store_true",
        help="Use transparent background (great with transparent terminals)",
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Launch frameless, transparent, always-on-top cyberpunk HUD overlay",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.86,
        help="Overlay window opacity (0.35 to 1.0, default: 0.86)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Spending budget in USD for visual gauge and over-budget alert (e.g. 50)",
    )
    parser.add_argument(
        "--source",
        choices=["all", "opencode", "claude", "codex", "gemini"],
        default="all",
        help="AI coding harness source to aggregate (default: all)",
    )
    parser.add_argument(
        "--export",
        choices=["json", "csv"],
        default=None,
        help="Export aggregated stats to stdout as JSON or CSV (non-interactive)",
    )
    args = parser.parse_args()
    initial_days = None if args.days == 0 else args.days

    if args.export:
        import csv
        import json
        import sys

        data = load_dashboard_data(args.db, days=initial_days, source=args.source)
        if args.export == "json":
            payload = {
                "range_days": initial_days,
                "active_sources": data.active_sources,
                "db_size_mb": round(data.db_size_mb, 2),
                "overview": {
                    "total_cost_usd": round(data.overview.total_cost, 6),
                    "total_sessions": data.overview.total_sessions,
                    "total_tokens": data.overview.total_tokens,
                    "cache_hit_rate_pct": round(data.overview.cache_hit_rate, 2),
                    "additions": data.overview.additions,
                    "deletions": data.overview.deletions,
                },
                "models": [
                    {
                        "model_id": m.model_id,
                        "provider_id": m.provider_id,
                        "sessions": m.sessions,
                        "cost_usd": round(m.cost, 6),
                        "tokens": m.tokens_total,
                    }
                    for m in data.models
                ],
                "projects": [
                    {
                        "name": p.name,
                        "sessions": p.sessions,
                        "cost_usd": round(p.cost, 6),
                        "tokens": p.tokens_total,
                    }
                    for p in data.projects
                ],
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            writer = csv.writer(sys.stdout)
            writer.writerow(["model_id", "provider_id", "sessions", "cost_usd", "tokens"])
            for m in data.models:
                writer.writerow([m.model_id, m.provider_id, m.sessions, f"{m.cost:.6f}", m.tokens_total])
        return

    if args.overlay:
        from oc_top.overlay import CyberOverlayHUD

        hud = CyberOverlayHUD(
            db_path=args.db,
            initial_days=initial_days,
            alpha=args.alpha,
            budget=args.budget,
        )
        hud.run()
        return

    app = OcTopApp(
        db_path=args.db,
        initial_days=initial_days,
        transparent=args.transparent,
    )
    app.run()


if __name__ == "__main__":
    main()
