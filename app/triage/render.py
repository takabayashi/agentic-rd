"""Plain-Python HTML rendering for the dashboard.

No template engine: the UI is one small table plus a warm-up page, so we build
the markup here and escape every untrusted field with ``html.escape``. This is
the load-bearing safety boundary — edit titles, comments, and editors are
attacker-controllable free text, so anything interpolated into markup goes
through ``_esc`` (and diff links are only emitted for http(s) URIs).
"""

import html

from .models import EditView

_STYLE = """
    :root {
      --bg: #0d1117; --panel: #161b22; --border: #30363d;
      --text: #e6edf3; --muted: #8b949e;
      --vandalism: #f85149; --substantive: #3fb950;
      --trivia: #58a6ff; --unclear: #d29922;
      --pos: #3fb950; --neg: #f85149;
    }
    @media (prefers-color-scheme: light) {
      :root { --bg: #f6f8fa; --panel: #fff; --border: #d0d7de; --text: #1c2128; --muted: #57606a; }
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text); }
    header { padding: 20px 24px 10px; max-width: 1200px; margin: 0 auto; }
    h1 { margin: 0 0 2px; font-size: 1.3rem; }
    .sub { color: var(--muted); font-size: 0.85rem; margin: 0 0 14px; }
    .filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
    .filters a { text-decoration: none; font-size: 0.82rem; padding: 4px 12px; border-radius: 999px;
      border: 1px solid var(--border); color: var(--muted); background: var(--panel); }
    .filters a.active { color: var(--text); border-color: var(--text); font-weight: 600; }
    .filters a .n { opacity: 0.65; margin-left: 4px; }
    main { max-width: 1200px; margin: 0 auto; padding: 0 24px 40px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
    th { color: var(--muted); font-weight: 600; font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.04em; }
    tr:hover td { background: var(--panel); }
    .badge { display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 6px;
      text-transform: uppercase; letter-spacing: 0.03em; }
    .badge.vandalism { background: color-mix(in srgb, var(--vandalism) 22%, transparent); color: var(--vandalism); }
    .badge.substantive { background: color-mix(in srgb, var(--substantive) 22%, transparent); color: var(--substantive); }
    .badge.trivia { background: color-mix(in srgb, var(--trivia) 22%, transparent); color: var(--trivia); }
    .badge.unclear { background: color-mix(in srgb, var(--unclear) 22%, transparent); color: var(--unclear); }
    .esc { font-size: 0.68rem; color: var(--unclear); border: 1px solid var(--unclear); border-radius: 5px;
      padding: 0 5px; margin-left: 6px; white-space: nowrap; }
    .conf { font-variant-numeric: tabular-nums; font-weight: 600; }
    .delta.pos { color: var(--pos); } .delta.neg { color: var(--neg); }
    .delta { font-variant-numeric: tabular-nums; }
    td.comment { color: var(--muted); max-width: 380px; }
    a.title { color: var(--text); text-decoration: none; font-weight: 600; }
    a.title:hover { text-decoration: underline; }
    .editor { color: var(--muted); font-size: 0.8rem; }
    .empty { text-align: center; color: var(--muted); padding: 60px 20px; }
    .ts { color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
"""

_WARMUP_STYLE = """
    :root { --bg: #0d1117; --panel: #161b22; --border: #30363d; --text: #e6edf3; --muted: #8b949e; }
    @media (prefers-color-scheme: light) {
      :root { --bg: #f6f8fa; --panel: #fff; --border: #d0d7de; --text: #1c2128; --muted: #57606a; }
    }
    body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text); }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
      padding: 32px 40px; text-align: center; max-width: 460px; }
    h1 { margin: 0 0 8px; font-size: 1.2rem; }
    p { margin: 0; color: var(--muted); font-size: 0.9rem; }
"""


def _esc(value: object) -> str:
    """Escape a value for safe HTML interpolation (text and attribute contexts)."""

    return html.escape(str(value), quote=True)


def _title_cell(edit: EditView) -> str:
    title = _esc(edit.title)
    # Only link out for http(s) URIs — never emit an attacker-supplied
    # javascript:/data: scheme as an href.
    if edit.uri.startswith(("http://", "https://")):
        return (
            f'<a class="title" href="{_esc(edit.uri)}" '
            f'target="_blank" rel="noopener noreferrer">{title}</a>'
        )
    return f'<span class="title">{title}</span>'


def _row(edit: EditView) -> str:
    label = edit.label.value
    escalated = '<span class="esc">escalated</span>' if edit.escalated else ""
    delta_cls = "pos" if edit.size_delta >= 0 else "neg"
    delta_sign = "+" if edit.size_delta >= 0 else ""
    return f"""        <tr>
          <td>
            <span class="badge {label}">{label}</span>
            {escalated}
          </td>
          <td class="conf">{edit.confidence * 100:.0f}%</td>
          <td>{_title_cell(edit)}</td>
          <td class="delta {delta_cls}">{delta_sign}{edit.size_delta}</td>
          <td class="comment">{_esc(edit.comment)}</td>
          <td class="editor">{_esc(edit.editor)}</td>
          <td class="ts">{edit.event_ts.strftime("%Y-%m-%d %H:%M")}</td>
        </tr>"""


def _filter_chip(name: str, count: int, active: str) -> str:
    href = "/" if name == "all" else f"/?label={_esc(name)}"
    cls = "active" if name == active else ""
    return f'<a href="{href}" class="{cls}">{_esc(name)}<span class="n">{count}</span></a>'


def _table(edits: list[EditView]) -> str:
    rows = "\n".join(_row(e) for e in edits)
    return f"""    <table>
      <thead>
        <tr>
          <th>Label</th><th>Conf.</th><th>Article</th><th>Δ bytes</th>
          <th>Comment</th><th>Editor</th><th>Time (UTC)</th>
        </tr>
      </thead>
      <tbody>
{rows}
      </tbody>
    </table>"""


def _empty(active: str) -> str:
    scope = f" for <strong>{_esc(active)}</strong>" if active != "all" else ""
    return f"""    <p class="empty">
      No edits to show{scope}.<br />
      The pipeline may still be warming up, or this filter is empty.
    </p>"""


def render_dashboard(
    edits: list[EditView], filters: list[str], counts: dict[str, int], active: str
) -> str:
    title_suffix = f" · {_esc(active)}" if active != "all" else ""
    chips = "\n      ".join(_filter_chip(f, counts.get(f, 0), active) for f in filters)
    body = _table(edits) if edits else _empty(active)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <!-- Plain auto-refresh: re-requests the same URL (filter preserved) every 15s. -->
  <meta http-equiv="refresh" content="15" />
  <title>Edit Triage{title_suffix}</title>
  <style>{_STYLE}</style>
</head>
<body>
  <header>
    <h1>Wikipedia Edit Triage</h1>
    <p class="sub">{counts.get("all", 0)} classified edits · sorted by confidence · auto-refresh 15s</p>
    <nav class="filters">
      {chips}
    </nav>
  </header>
  <main>
{body}
  </main>
</body>
</html>
"""


def render_warming_up() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="refresh" content="5" />
  <title>Warming up…</title>
  <style>{_WARMUP_STYLE}</style>
</head>
<body>
  <div class="card">
    <h1>Database warming up</h1>
    <p>The data store isn't ready yet. This page retries automatically every few seconds.</p>
  </div>
</body>
</html>
"""
