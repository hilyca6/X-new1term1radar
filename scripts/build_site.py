"""Build a one-page static dashboard of the radar's leads, for GitHub Pages.

  python scripts/build_site.py [--state state] [--out _site] [--report report.md] [--days 30]

Reads the leads database (state/radar.db) and, when present, renders the latest
report.md as a second page. Standard library only; the full report page uses
radar/notify.py's Markdown->HTML when the `markdown` package is installed (it is in CI).
No web server: the workflow uploads the output as the Pages artifact.
"""
from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar import config, store  # noqa: E402
from radar.i18n import t  # noqa: E402

KINDS = ["x", "hf", "breakout", "sitemap", "newsite", "usecase", "cosearch", "watch"]


def _esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _kind(k: str) -> str:
    return t(f"kind_{k}") if k in KINDS else k


def _tags(kinds: list[str]) -> str:
    return " ".join(f'<span class="tag">{_esc(_kind(k))}</span>' for k in kinds)


def _verdict(verdict: str | None, days_ahead) -> str:
    if not verdict:
        return '<span class="vd wait">—</span>'
    cls = {"hit": "hit", "miss": "miss"}.get(verdict, "wait")
    ahead = f" · {days_ahead}天前" if days_ahead is not None else ""
    return f'<span class="vd {cls}">{_esc(verdict)}{_esc(ahead)}</span>'


CSS = """
:root{--fg:#1f2328;--mut:#656d76;--line:#d0d7de;--bg:#f6f8fa;--link:#0969da}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--fg);
  font:14px/1.55 -apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif}
header{padding:20px 24px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;
  gap:8px 16px;align-items:baseline}
header h1{font-size:18px;margin:0}
header .meta{color:var(--mut);font-size:12px}
main{padding:20px 24px;max-width:1200px;margin:0 auto}
h2{font-size:15px;margin:28px 0 10px}
.cards{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 8px}
.card{border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:110px;background:var(--bg)}
.card b{display:block;font-size:20px}
.card span{color:var(--mut);font-size:12px}
table{border-collapse:collapse;width:100%;margin:6px 0}
th,td{border:1px solid var(--line);padding:6px 10px;font-size:13px;vertical-align:top;text-align:left}
th{background:var(--bg);white-space:nowrap}
td.term{font-weight:600}
.tag{display:inline-block;background:#eef2f6;border-radius:4px;padding:1px 6px;font-size:12px;white-space:nowrap}
.vd{font-size:12px;padding:1px 6px;border-radius:4px}
.vd.hit{background:#dafbe1;color:#1a7f37}.vd.miss{background:#ffebe9;color:#cf222e}.vd.wait{color:var(--mut)}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
.empty{color:var(--mut);padding:16px;border:1px dashed var(--line);border-radius:8px}
"""


def _row(r: dict) -> str:
    note = _esc(r.get("note") or "")
    score = r.get("name_score")
    score = f"{score:.2f}" if isinstance(score, (int, float)) else "—"
    return (
        "<tr>"
        f'<td class="term">{_esc(r["term"])}</td>'
        f"<td>{_tags(r.get('signals') or [])}</td>"
        f"<td>{score}</td>"
        f'<td>{_esc(r.get("first_seen"))}</td>'
        f'<td>{_esc(r.get("last_seen"))}</td>'
        f'<td>{_verdict(r.get("verdict"), r.get("days_ahead"))}</td>'
        f"<td>{note}</td>"
        "</tr>"
    )


def _hit_cards(summary: dict) -> str:
    by = summary.get("by_signal") or {}
    if not by:
        return f'<div class="empty">{_esc(t("review_none", why="—"))}</div>'
    cards = [f'<div class="card"><b>{summary.get("pending", 0)}</b><span>待复盘</span></div>']
    for k, s in sorted(by.items(), key=lambda kv: KINDS.index(kv[0]) if kv[0] in KINDS else 99):
        rate = f"{s['hit'] / s['checked']:.0%}" if s["checked"] else "—"
        cards.append(f'<div class="card"><b>{rate}</b><span>{_esc(_kind(k))} · {s["hit"]}/{s["checked"]}</span></div>')
    return f'<div class="cards">{"".join(cards)}</div>'


def _report_section(report_path: Path, out: Path) -> str:
    if not report_path.exists():
        return ""
    try:
        from radar import notify

        body = notify.html(report_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — no `markdown`: fall back to the source text
        body = f"<pre>{_esc(report_path.read_text(encoding='utf-8'))}</pre>"
    (out / "report.html").write_text(
        "<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<style>" + CSS + "</style><title>New-term radar · 完整报告</title></head>"
        "<body><header><h1><a href=\"index.html\">← 返回</a></h1></header>"
        "<main>" + body + "</main></body></html>",
        encoding="utf-8",
    )
    return '<a href="report.html">查看完整日报 →</a>'


def build(state: Path, out: Path, report_path: Path, days: int) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    leads, summary = [], {"by_signal": {}, "pending": 0}
    if (state / "radar.db").exists():
        conn = store.connect(state)
        leads = store.leads(conn, days)
        summary = store.summary(conn)
        conn.close()
    if report_path.exists():
        (out / "report.md").write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")

    rows = "".join(_row(r) for r in leads)
    table = (f'<table><thead><tr><th>词</th><th>信号</th><th>名字得分</th><th>首次出现</th>'
             f"<th>最近出现</th><th>复盘</th><th>说明</th></tr></thead><tbody>{rows}</tbody></table>") \
        if rows else f'<div class="empty">还没有记录到候选词。等下一次运行。</div>'

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = (
        '<!doctype html><html lang="zh"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="refresh" content="3600">'
        f"<style>{CSS}</style><title>New-term radar</title></head><body>"
        "<header><h1>新词雷达 · New-term radar</h1>"
        f'<span class="meta">更新于 {generated} · 近 {days} 天 {len(leads)} 个候选词</span></header>'
        f"<main>{_report_section(report_path, out)}"
        f"<h2>各信号命中率（近 {summary.get('window_days', 60)} 天）</h2>{_hit_cards(summary)}"
        f"<h2>候选新词</h2>{table}"
        "</main></body></html>"
    )
    index = out / "index.html"
    index.write_text(page, encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--state", default="state")
    p.add_argument("--out", default="_site")
    p.add_argument("--report", default="report.md")
    p.add_argument("--days", type=int, default=30)
    args = p.parse_args(argv)

    cfg_path = ROOT / "config.json"
    if cfg_path.exists():
        config.load(cfg_path)   # sets the report language for the labels below
    index = build(Path(args.state), Path(args.out), Path(args.report), args.days)
    print(f"{index} written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
