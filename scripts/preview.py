"""Preview a radar report as an HTML page in your browser (no server, no deps beyond `markdown`).

  python scripts/preview.py [report.md] [report.html]

The radar itself has no web UI: it writes Markdown. This reuses radar/notify.py's
Markdown->HTML (the one the mail option uses) so the report reads the same way.
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar import notify

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "report.md")
DST = Path(sys.argv[2] if len(sys.argv) > 2 else SRC.with_suffix(".html"))

if not SRC.exists():
    raise SystemExit(f"{SRC} not found: run `python -m radar daily --out {SRC.name}` first")

body = notify.html(SRC.read_text(encoding="utf-8"))
DST.write_text(
    "<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    "<title>New-term radar</title></head>"
    "<body style=\"margin:0;padding:24px;background:#fff\">" + body + "</body></html>",
    encoding="utf-8",
)
print(f"{DST} written")
webbrowser.open(DST.resolve().as_uri())
