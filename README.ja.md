# oc-top

[English](README.md) | **日本語**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**AI コーディングエージェント向けの高速・サイバーパンク風トークン＆コストモニター**

**OpenCode**、**Claude Code**、**Codex CLI**、**Gemini CLI** に標準対応。インタラクティブな **ターミナルダッシュボード（TUI）** と、**フレームレス・半透明・最前面表示のフローティング HUD オーバーレイ** の両方を備えています。

> 読み取り専用の集計クエリにより、数 GB 規模の `opencode.db` ファイルでも爆速で動作します（9GB の DB で約 10ms）。外部 API 呼び出しは一切なし。100% ローカルかつプライベートです。

---

<!-- HUD / TUI のスクリーンショットやデモ GIF をここに配置してください！
![oc-top cyberpunk HUD](assets/demo.gif)
-->

## 主な機能

- **マルチハーネス自動検出**: 以下のツールから使用状況を自動で集計します:
  | ハーネス | ローカルデータソース |
  |---|---|
  | **OpenCode** | `~/.local/share/opencode/opencode.db` |
  | **Claude Code** | `~/.claude/projects/*/*.jsonl` |
  | **Codex CLI** | `~/.codex/sessions/**/*.jsonl` |
  | **Gemini CLI** | `~/.gemini/tmp/**/session-*.json` |
- **サイバーパンク・フローティング HUD (`--overlay`)**:
  - フレームレス・半透明（`--alpha`）・最前面表示のデスクトップオーバーレイ
  - 5 秒ごとの自動更新とライブ脈動インジケーター
  - **予算アラート（`--budget`）**: 動的なゲージ表示（`OK` → `CAUTION` → ネオンレッドで点滅する `OVER BUDGET`）
  - **コンパクト・ミニバー（`m` キー）**: コーディングの邪魔にならない 1 行のフローティングティッカーバーに折りたたみ可能
- **インタラクティブ TUI (`oc-top`)**:
  - KPI カード（総コスト、トークン数、キャッシュヒット率、セッション数＆コード差分）
  - 日別の消費ペース（バーンレート）スパークライン
  - **Models**、**Projects**、**Top Sessions** の内訳タブ
  - 透過ターミナル背景モード（`--transparent` または `t` キー）
- **スクリプト連携向けエクスポート (`--export`)**: 集計結果を `json` または `csv` 形式で出力でき、Slack ボット、Notion、スプレッドシートなどで活用できます。

---

## クイックスタート

Python 3.11 以上と [`uv`](https://docs.astral.sh/uv/) が必要です。

```bash
git clone https://github.com/<your-username>/oc-top.git
cd oc-top

# インタラクティブ TUI を起動
uv run oc-top

# 予算ゲージ $50 を設定してサイバーパンク・フローティング HUD を起動
uv run oc-top --overlay --budget 50

# 透過背景 TUI を起動（Ghostty / iTerm2 / Warp に最適）
uv run oc-top --transparent
```

---

## CLI オプション

```bash
oc-top [OPTIONS]
```

| オプション | 説明 |
|---|---|
| `--overlay` | フレームレス・半透明・最前面表示のサイバーパンク HUD を起動 |
| `--budget <USD>` | ゲージおよび予算超過時のネオンレッド警告用の予算額（USD）を設定 |
| `--alpha <0.35-1.0>` | オーバーレイの不透明度（デフォルト: `0.86`） |
| `--transparent` | TUI モードで背景を透過表示 |
| `--days <N>` | 集計対象の日数（`0` で全期間、デフォルト: `30`） |
| `--source <NAME>` | ハーネスで絞り込み: `all`, `opencode`, `claude`, `codex`, `gemini` |
| `--export <FMT>` | 非インタラクティブに標準出力へエクスポート（`json` または `csv`） |
| `--db <PATH>` | `opencode.db` のカスタムパスを指定 |

### キーボードショートカット

- **HUD オーバーレイ**: `1` / `2` / `3`（7日間 / 30日間 / 全期間） · `m`（ミニバー切替） · `+` / `-`（不透明度調整） · `r`（更新） · `q` / `Esc`（終了）
- **TUI**: `1` / `2` / `3`（7日間 / 30日間 / 全期間） · `m` / `p` / `s`（Models / Projects / Sessions） · `t`（透過切替） · `r`（更新） · `q`（終了）

---

## 出力例

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

## ライセンス

[MIT](LICENSE)
