# oc-top

**English** | [日本語](README.ja.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**A fast, cyberpunk-styled token & cost monitor for AI coding agents.**

Supports **OpenCode**, **Claude Code**, **Codex CLI**, and **Gemini CLI** out of the box — with both an interactive **Terminal Dashboard (TUI)** and a **frameless, transparent, always-on-top Floating HUD Overlay**.

> Blazingly fast even on multi-GB `opencode.db` files (~10ms on a 9GB DB) using read-only aggregated queries. Zero external API calls. 100% local & private.

---

<!-- Drop your HUD / TUI screenshot or demo GIF here!
![oc-top cyberpunk HUD](assets/demo.gif)
-->

## Features

- **Multi-Harness Auto-Detection**: Automatically aggregates usage across:
  | Harness | Local Data Source |
  |---|---|
  | **OpenCode** | `~/.local/share/opencode/opencode.db` |
  | **Claude Code** | `~/.claude/projects/*/*.jsonl` |
  | **Codex CLI** | `~/.codex/sessions/**/*.jsonl` |
  | **Gemini CLI** | `~/.gemini/tmp/**/session-*.json` |
- **Cyberpunk Floating HUD (`--overlay`)**:
  - Frameless, semi-transparent (`--alpha`), always-on-top desktop overlay
  - Live pulsing indicator with 5-second auto-refresh
  - **Budget Alert (`--budget`)**: Dynamic gauge (`OK` → `CAUTION` → pulsing neon red `OVER BUDGET`)
  - **Compact Mini-Bar (`m` key)**: Collapses into a 1-line floating ticker bar while you code
- **Interactive TUI (`oc-top`)**:
  - KPI cards (Total Spend, Tokens, Cache Hit Rate, Sessions & Code Diff)
  - Daily burn-rate sparkline
  - Breakdown tabs for **Models**, **Projects**, and **Top Sessions**
  - Transparent terminal background mode (`--transparent` or `t` key)
- **Scriptable Export (`--export`)**: Output aggregated stats as `json` or `csv` for Slack bots, Notion, or spreadsheets.

---

## Quick Start

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/<your-username>/oc-top.git
cd oc-top

# Launch interactive TUI
uv run oc-top

# Launch Cyberpunk Floating HUD Overlay with a $50 budget gauge
uv run oc-top --overlay --budget 50

# Launch transparent TUI (great with Ghostty / iTerm2 / Warp)
uv run oc-top --transparent
```

---

## CLI Options

```bash
oc-top [OPTIONS]
```

| Option | Description |
|---|---|
| `--overlay` | Launch frameless, transparent, always-on-top cyberpunk HUD |
| `--budget <USD>` | Set spending budget for gauge & neon red over-budget alert |
| `--alpha <0.35-1.0>` | Overlay opacity (default: `0.86`) |
| `--transparent` | Transparent background for TUI mode |
| `--days <N>` | Lookback window in days (`0` for all time, default: `30`) |
| `--source <NAME>` | Filter by harness: `all`, `opencode`, `claude`, `codex`, `gemini` |
| `--export <FMT>` | Non-interactive export to stdout (`json` or `csv`) |
| `--db <PATH>` | Custom path to `opencode.db` |

### Keyboard Shortcuts

- **HUD Overlay**: `1` / `2` / `3` (7d / 30d / All) · `m` (Mini-bar toggle) · `+` / `-` (Opacity) · `r` (Refresh) · `q` / `Esc` (Quit)
- **TUI**: `1` / `2` / `3` (7d / 30d / All) · `m` / `p` / `s` (Models / Projects / Sessions) · `t` (Transparent toggle) · `r` (Refresh) · `q` (Quit)

---

## Example Output

```bash
$ uv run oc-top --days 7 --export json
```

```json
{
  "range_days": 7,
  "active_sources": ["opencode", "claude-code"],
  "overview": {
    "total_cost_usd": 14.8235,
    "total_sessions": 28,
    "total_tokens": 18420910,
    "cache_hit_rate_pct": 87.4
  },
  "models": [
    {
      "model_id": "claude-sonnet-4-20250514",
      "provider_id": "anthropic",
      "sessions": 21,
      "cost_usd": 11.4021,
      "tokens": 14210500
    },
    {
      "model_id": "gemini-2.5-pro",
      "provider_id": "google",
      "sessions": 7,
      "cost_usd": 3.4214,
      "tokens": 4210410
    }
  ],
  "projects": [
    {
      "name": "oc-top",
      "sessions": 16,
      "cost_usd": 9.1502,
      "tokens": 11804200
    }
  ]
}
```

---

## License

[MIT](LICENSE)
