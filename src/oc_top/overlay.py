"""Cyberpunk floating transparent HUD overlay for OpenCode analytics."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Optional

from oc_top.db import DashboardData, load_dashboard_data

# Cyberpunk palette
BG_DARK = "#070b14"
BG_PANEL = "#0d1424"
BORDER_CYAN = "#00f0ff"
NEON_CYAN = "#00f0ff"
NEON_PINK = "#ff2a85"
NEON_GREEN = "#39ff14"
NEON_AMBER = "#ffb800"
NEON_RED = "#ff1744"
TEXT_MAIN = "#e6f1ff"
TEXT_DIM = "#627799"
BAR_BG = "#162038"

FONT_MONO = "Menlo"


def _fmt_cost(cost: float) -> str:
    if cost >= 100:
        return f"${cost:,.2f}"
    if cost >= 1:
        return f"${cost:.3f}"
    return f"${cost:.4f}"


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class CyberOverlayHUD:
    """Frameless, transparent, always-on-top cyberpunk HUD."""

    WIDTH = 360
    HEIGHT = 456
    COMPACT_HEIGHT = 42
    REFRESH_MS = 5000

    def __init__(
        self,
        db_path: Path,
        initial_days: Optional[int] = 30,
        alpha: float = 0.86,
        budget: Optional[float] = None,
    ) -> None:
        self.db_path = db_path
        self.days: Optional[int] = initial_days
        self.alpha = max(0.35, min(1.0, alpha))
        self.budget = budget
        self.compact = False
        self.pulse_on = True
        self._over_budget = False
        self._drag_x = 0
        self._drag_y = 0

        self.root = tk.Tk()
        self.root.title("OC-TOP // HUD")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.alpha)
        self.root.configure(bg=BG_DARK)

        # Position at top-right of screen with margin
        screen_w = self.root.winfo_screenwidth()
        x = max(20, screen_w - self.WIDTH - 24)
        y = 48
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=BG_DARK,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Drag bindings
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)

        # Keyboard bindings
        self.root.bind("<Escape>", lambda _: self.root.destroy())
        self.root.bind("q", lambda _: self.root.destroy())
        self.root.bind("m", lambda _: self._toggle_compact())
        self.root.bind("1", lambda _: self._set_range(7))
        self.root.bind("2", lambda _: self._set_range(30))
        self.root.bind("3", lambda _: self._set_range(None))
        self.root.bind("+", lambda _: self._adjust_alpha(0.05))
        self.root.bind("=", lambda _: self._adjust_alpha(0.05))
        self.root.bind("-", lambda _: self._adjust_alpha(-0.05))
        self.root.bind("r", lambda _: self._refresh())

        self.data: Optional[DashboardData] = None
        self._refresh()
        self._schedule_refresh()
        self._schedule_pulse()

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_move(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _set_range(self, days: Optional[int]) -> None:
        self.days = days
        self._refresh()

    def _adjust_alpha(self, delta: float) -> None:
        self.alpha = max(0.35, min(1.0, self.alpha + delta))
        self.root.attributes("-alpha", self.alpha)
        self._render()

    def _toggle_compact(self) -> None:
        self.compact = not self.compact
        h = self.COMPACT_HEIGHT if self.compact else self.HEIGHT
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.canvas.config(height=h)
        self.root.geometry(f"{self.WIDTH}x{h}+{x}+{y}")
        self._render()

    def _refresh(self) -> None:
        try:
            self.data = load_dashboard_data(self.db_path, days=self.days)
        except Exception:
            self.data = None
        self._render()

    def _schedule_refresh(self) -> None:
        self.root.after(self.REFRESH_MS, self._auto_refresh)

    def _auto_refresh(self) -> None:
        self._refresh()
        self._schedule_refresh()

    def _schedule_pulse(self) -> None:
        self.root.after(900, self._toggle_pulse)

    def _toggle_pulse(self) -> None:
        self.pulse_on = not self.pulse_on
        if self.canvas.find_withtag("live_dot"):
            if self._over_budget:
                color = NEON_RED if self.pulse_on else "#4d0b18"
            else:
                color = NEON_GREEN if self.pulse_on else "#144d14"
            self.canvas.itemconfig("live_dot", fill=color)
        if self._over_budget and self.canvas.find_withtag("alert_border"):
            b_color = NEON_RED if self.pulse_on else "#661122"
            self.canvas.itemconfig("alert_border", fill=b_color)
        self._schedule_pulse()

    def _draw_hud_frame(self, h: int) -> None:
        c = self.canvas
        w = self.WIDTH
        # Subtle cyber scanlines
        for sy in range(4, h - 4, 4):
            c.create_line(2, sy, w - 3, sy, fill="#0a101d", width=1)
        outer = "#4d1122" if self._over_budget else "#18304d"
        c.create_rectangle(1, 1, w - 2, h - 2, outline=outer, width=1)
        L = 14 if self.compact else 16
        c1 = NEON_RED if self._over_budget else BORDER_CYAN
        c2 = NEON_RED if self._over_budget else NEON_PINK
        tag = "alert_border" if self._over_budget else "hud_border"
        # Top-left
        c.create_line(1, 1, L, 1, fill=c1, width=2, tags=tag)
        c.create_line(1, 1, 1, L, fill=c1, width=2, tags=tag)
        # Top-right
        c.create_line(w - L, 1, w - 2, 1, fill=c2, width=2, tags=tag)
        c.create_line(w - 2, 1, w - 2, L, fill=c2, width=2, tags=tag)
        # Bottom-left
        c.create_line(1, h - L, 1, h - 2, fill=c2, width=2, tags=tag)
        c.create_line(1, h - 2, L, h - 2, fill=c2, width=2, tags=tag)
        # Bottom-right
        c.create_line(w - L, h - 2, w - 2, h - 2, fill=c1, width=2, tags=tag)
        c.create_line(w - 2, h - L, w - 2, h - 2, fill=c1, width=2, tags=tag)

    def _render_compact(self) -> None:
        c = self.canvas
        w = self.WIDTH
        h = self.COMPACT_HEIGHT
        self._draw_hud_frame(h)

        dot_color = (NEON_RED if self.pulse_on else "#4d0b18") if self._over_budget else (NEON_GREEN if self.pulse_on else "#144d14")
        c.create_oval(12, 17, 20, 25, fill=dot_color, outline="", tags="live_dot")

        if self.data:
            ov = self.data.overview
            cost_str = _fmt_cost(ov.total_cost)
            if self.budget and self.budget > 0:
                cost_str += f"/{_fmt_cost(self.budget)}"
            top_m = self.data.models[0].model_id if self.data.models else "-"
            if len(top_m) > 15:
                top_m = top_m[:13] + ".."
            c.create_text(
                28, 21,
                text=f"{cost_str}  |  {_fmt_tokens(ov.total_tokens)}  |  {top_m}",
                anchor="w",
                fill=NEON_RED if self._over_budget else NEON_CYAN,
                font=(FONT_MONO, 9, "bold"),
            )
        else:
            c.create_text(28, 21, text="NO SIGNAL", anchor="w", fill=NEON_PINK, font=(FONT_MONO, 9, "bold"))

        # Expand button
        c.create_text(w - 38, 21, text="▢", fill=NEON_CYAN, font=(FONT_MONO, 10, "bold"), tags="btn_compact")
        c.tag_bind("btn_compact", "<Button-1>", lambda _: self._toggle_compact())
        # Close button
        c.create_text(w - 18, 21, text="✕", fill=NEON_PINK, font=(FONT_MONO, 10, "bold"), tags="btn_close")
        c.tag_bind("btn_close", "<Button-1>", lambda _: self.root.destroy())

    def _render(self) -> None:
        c = self.canvas
        c.delete("all")

        if self.data and self.budget and self.budget > 0:
            self._over_budget = self.data.overview.total_cost >= self.budget
        else:
            self._over_budget = False

        if self.compact:
            self._render_compact()
            return

        self._draw_hud_frame(self.HEIGHT)

        w = self.WIDTH

        # Header bar
        c.create_rectangle(8, 8, w - 8, 36, fill=BG_PANEL, outline="#4d1122" if self._over_budget else "#162844")
        dot_color = (NEON_RED if self.pulse_on else "#4d0b18") if self._over_budget else (NEON_GREEN if self.pulse_on else "#144d14")
        c.create_oval(
            16, 18, 24, 26,
            fill=dot_color,
            outline="",
            tags="live_dot",
        )
        c.create_text(
            32, 22,
            text="OC-TOP // ALERT" if self._over_budget else "OC-TOP // NEURAL HUD",
            anchor="w",
            fill=NEON_RED if self._over_budget else NEON_CYAN,
            font=(FONT_MONO, 10, "bold"),
        )

        # Range buttons (clickable)
        ranges = [("7D", 7, 206), ("30D", 30, 238), ("ALL", None, 274)]
        for label, val, bx in ranges:
            active = self.days == val
            fg = BG_DARK if active else TEXT_DIM
            bg = NEON_CYAN if active else BG_DARK
            tag = f"rng_{label}"
            c.create_rectangle(
                bx, 13, bx + 28, 31,
                fill=bg,
                outline=NEON_CYAN if active else "#223654",
                tags=tag,
            )
            c.create_text(
                bx + 14, 22,
                text=label,
                fill=fg,
                font=(FONT_MONO, 8, "bold"),
                tags=tag,
            )
            c.tag_bind(tag, "<Button-1>", lambda _, v=val: self._set_range(v))

        # Mini-mode button
        c.create_text(
            w - 38, 22,
            text="−",
            fill=NEON_CYAN,
            font=(FONT_MONO, 12, "bold"),
            tags="btn_compact",
        )
        c.tag_bind("btn_compact", "<Button-1>", lambda _: self._toggle_compact())

        # Close button
        c.create_text(
            w - 20, 22,
            text="✕",
            fill=NEON_PINK,
            font=(FONT_MONO, 11, "bold"),
            tags="btn_close",
        )
        c.tag_bind("btn_close", "<Button-1>", lambda _: self.root.destroy())

        if not self.data:
            c.create_text(
                w // 2, 200,
                text="NO SIGNAL // DB NOT FOUND",
                fill=NEON_PINK,
                font=(FONT_MONO, 10, "bold"),
            )
            return

        ov = self.data.overview

        # Main KPI Panel
        kpi_bottom = 148 if (self.budget and self.budget > 0) else 124
        c.create_rectangle(10, 44, w - 10, kpi_bottom, fill=BG_PANEL, outline="#4d1122" if self._over_budget else "#18304d")
        c.create_text(
            20, 56,
            text="TOTAL SPEND",
            anchor="w",
            fill=TEXT_DIM,
            font=(FONT_MONO, 8, "bold"),
        )
        c.create_text(
            20, 82,
            text=_fmt_cost(ov.total_cost),
            anchor="w",
            fill=NEON_RED if self._over_budget else NEON_CYAN,
            font=(FONT_MONO, 22, "bold"),
        )
        c.create_text(
            20, 108,
            text=f"SESSIONS: {ov.total_sessions:,}   DIFF: +{ov.additions:,}/-{ov.deletions:,}",
            anchor="w",
            fill=TEXT_DIM,
            font=(FONT_MONO, 8),
        )

        # Right side of KPI panel: Tokens & Cache
        c.create_text(
            w - 20, 56,
            text="TOKENS",
            anchor="e",
            fill=TEXT_DIM,
            font=(FONT_MONO, 8, "bold"),
        )
        c.create_text(
            w - 20, 74,
            text=_fmt_tokens(ov.total_tokens),
            anchor="e",
            fill=NEON_PINK,
            font=(FONT_MONO, 13, "bold"),
        )
        c.create_text(
            w - 20, 94,
            text=f"CACHE {ov.cache_hit_rate:.1f}%",
            anchor="e",
            fill=NEON_GREEN,
            font=(FONT_MONO, 9, "bold"),
        )

        # Optional Budget Gauge inside KPI Panel
        y_off = 0
        if self.budget and self.budget > 0:
            y_off = 24
            pct = (ov.total_cost / self.budget) * 100.0
            if pct >= 100:
                b_col, status = NEON_RED, "OVER BUDGET"
            elif pct >= 70:
                b_col, status = NEON_AMBER, "CAUTION"
            else:
                b_col, status = NEON_GREEN, "OK"

            c.create_text(
                20, 124,
                text=f"BUDGET {_fmt_cost(self.budget)} // {status}",
                anchor="w",
                fill=b_col,
                font=(FONT_MONO, 8, "bold"),
            )
            c.create_text(
                w - 20, 124,
                text=f"{pct:.1f}%",
                anchor="e",
                fill=b_col,
                font=(FONT_MONO, 8, "bold"),
            )
            bx0, bx1 = 20, w - 20
            c.create_rectangle(bx0, 134, bx1, 140, fill=BAR_BG, outline="")
            fill_w = max(2, int((bx1 - bx0) * min(1.0, ov.total_cost / self.budget)))
            c.create_rectangle(bx0, 134, bx0 + fill_w, 140, fill=b_col, outline="")

        # Daily Spend Mini Bar Chart
        c.create_rectangle(10, 132 + y_off, w - 10, 212 + y_off, fill=BG_PANEL, outline="#18304d")
        c.create_text(
            20, 144 + y_off,
            text="DAILY BURN RATE",
            anchor="w",
            fill=TEXT_DIM,
            font=(FONT_MONO, 8, "bold"),
        )
        daily = self.data.daily[-14:]
        if daily:
            max_cost = max((d.cost for d in daily), default=0.0) or 1.0
            peak = max(daily, key=lambda d: d.cost)
            c.create_text(
                w - 20, 144 + y_off,
                text=f"PEAK {_fmt_cost(peak.cost)}",
                anchor="e",
                fill=NEON_AMBER,
                font=(FONT_MONO, 8, "bold"),
            )
            chart_left = 20
            chart_right = w - 20
            chart_bottom = 202 + y_off
            chart_height = 42
            n_bars = len(daily)
            step = (chart_right - chart_left) / max(n_bars, 1)
            bar_w = max(4, step - 4)
            for i, d in enumerate(daily):
                x0 = chart_left + i * step
                bh = max(2, int((d.cost / max_cost) * chart_height)) if d.cost > 0 else 2
                color = NEON_PINK if d.cost == peak.cost and d.cost > 0 else NEON_CYAN
                if d.cost == 0:
                    color = BAR_BG
                c.create_rectangle(
                    x0, chart_bottom - bh, x0 + bar_w, chart_bottom,
                    fill=color,
                    outline="",
                )

        # Top Models Panel
        c.create_rectangle(10, 220 + y_off, w - 10, 396 + y_off, fill=BG_PANEL, outline="#18304d")
        c.create_text(
            20, 233 + y_off,
            text="TOP MODELS // NEURAL CORES",
            anchor="w",
            fill=NEON_CYAN,
            font=(FONT_MONO, 8, "bold"),
        )

        models = self.data.models[:5]
        max_m_cost = max((m.cost for m in models), default=0.0) or 1.0
        y_pos = 252 + y_off
        for m in models:
            name = m.model_id if len(m.model_id) <= 24 else m.model_id[:21] + "..."
            c.create_text(
                20, y_pos,
                text=name,
                anchor="w",
                fill=TEXT_MAIN,
                font=(FONT_MONO, 9),
            )
            c.create_text(
                w - 20, y_pos,
                text=f"{_fmt_cost(m.cost)}  ({_fmt_tokens(m.tokens_total)})",
                anchor="e",
                fill=NEON_AMBER,
                font=(FONT_MONO, 8, "bold"),
            )
            # Progress bar
            bar_x0, bar_x1 = 20, w - 20
            bar_y = y_pos + 11
            c.create_rectangle(bar_x0, bar_y, bar_x1, bar_y + 4, fill=BAR_BG, outline="")
            ratio = (m.cost / max_m_cost) if max_m_cost > 0 else 0.0
            fill_w = max(2, int((bar_x1 - bar_x0) * ratio))
            c.create_rectangle(bar_x0, bar_y, bar_x0 + fill_w, bar_y + 4, fill=NEON_PINK, outline="")
            y_pos += 28

        # Footer
        db_gb = self.data.db_size_mb / 1024.0
        db_str = f"{db_gb:.1f}GB" if db_gb >= 1.0 else f"{self.data.db_size_mb:.0f}MB"
        c.create_text(
            14, self.HEIGHT - 16,
            text=f"DB:{db_str}  ALPHA:{int(self.alpha * 100)}%  [+/-] [1/2/3] [Q]",
            anchor="w",
            fill=TEXT_DIM,
            font=(FONT_MONO, 8),
        )

    def run(self) -> None:
        self.root.mainloop()
