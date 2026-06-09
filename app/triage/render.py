"""Plain-Python HTML rendering for the dashboard.

No template engine: the UI is one small table plus a warm-up page, so we build
the markup here and escape every untrusted field with ``html.escape``. This is
the load-bearing safety boundary — edit titles, comments, and editors are
attacker-controllable free text, so anything interpolated into markup goes
through ``_esc`` (and links are only emitted for http(s) URIs).

Live updates use a tiny vanilla-JS poller (no external library, no build step)
that re-fetches the server-rendered ``#feed`` fragment every few seconds and
swaps it in, flashing newly-arrived rows. The server stays the single source of
markup — the client never re-implements row rendering. The dashboard CSS/JS are
served as real files from ``app/static`` (mounted at ``/static`` in ``main``);
this module only emits the markup that links them.
"""

import html
from datetime import UTC, datetime
from urllib.parse import quote

from .config import get_settings
from .models import EditView

# Seconds between live-feed refreshes. Passed to the static dashboard.js via a
# ``data-refresh-ms`` body attribute so the value stays owned here in Python
# while the script remains a cacheable static asset.
_REFRESH_SECONDS = 5


def _esc(value: object) -> str:
    """Escape a value for safe HTML interpolation (text and attribute contexts)."""

    return html.escape(str(value), quote=True)


def _relative_time(dt: datetime | None) -> str:
    """Human "Ns/Nm/Nh/Nd ago" so freshness is visible at a glance."""

    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    secs = max((datetime.now(UTC) - dt).total_seconds(), 0)
    if secs < 60:
        return f"{int(secs)}s ago"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def _query(label: str, escalated: bool) -> str:
    """Build a dashboard URL preserving both the label and escalated filters."""

    params = []
    if label and label != "all":
        params.append("label=" + quote(label))
    if escalated:
        params.append("escalated=1")
    return "/?" + "&".join(params) if params else "/"


def _article_url(edit: EditView) -> str | None:
    """The article page link, derived from the (validated http) diff uri so it
    works for any wiki; the title is percent-encoded into the path."""

    if not edit.uri.startswith(("http://", "https://")):
        return None
    base = edit.uri.split("/w/index.php")[0] or "https://en.wikipedia.org"
    return base + "/wiki/" + quote(edit.title, safe="")


def _title_cell(edit: EditView) -> str:
    title = _esc(edit.title)
    # Only link out for http(s) URIs — never emit an attacker-supplied
    # javascript:/data: scheme as an href.
    article = _article_url(edit)
    if article:
        head = (
            f'<a class="title" href="{_esc(article)}" '
            f'target="_blank" rel="noopener noreferrer">{title}</a>'
        )
    else:
        head = f'<span class="title">{title}</span>'
    links = []
    if edit.uri.startswith(("http://", "https://")):
        links.append(
            f'<a href="{_esc(edit.uri)}" target="_blank" rel="noopener noreferrer">diff</a>'
        )
    links.append(f'<span class="rev">#{edit.rev_id}</span>')
    return f'{head}<div class="meta">{" · ".join(links)}</div>'


def _row(edit: EditView) -> str:
    label = edit.label.value
    escalated = '<span class="esc">escalated</span>' if edit.escalated else ""
    # Surface gate decisions: an "empty_diff" row was labelled without a model
    # call (no usable diff), so flag it distinctly from a model-derived label.
    reason = (
        '<span class="reason" title="No usable diff — model skipped, defaulted unclear">'
        "skipped</span>"
        if edit.reason == "empty_diff"
        else ""
    )
    delta_cls = "pos" if edit.size_delta >= 0 else "neg"
    delta_sign = "+" if edit.size_delta >= 0 else ""
    return f"""        <tr data-rev="{edit.rev_id}">
          <td>
            <span class="badge {label}">{label}</span>
            {escalated}{reason}
          </td>
          <td class="conf">{edit.confidence * 100:.0f}%</td>
          <td>{_title_cell(edit)}</td>
          <td class="delta {delta_cls}">{delta_sign}{edit.size_delta}</td>
          <td class="comment">{_esc(edit.comment)}</td>
          <td class="editor">{_esc(edit.editor)}</td>
          <td class="ts">{edit.event_ts.strftime("%Y-%m-%d %H:%M")}</td>
          <td class="ts">{_esc(_relative_time(edit.classified_at))}</td>
        </tr>"""


def _filter_chip(name: str, count: int, active: str, escalated_active: bool) -> str:
    href = _query(name, escalated_active)
    cls = "active" if name == active else ""
    return f'<a href="{_esc(href)}" class="{cls}">{_esc(name)}<span class="n">{count}</span></a>'


def _escalated_chip(count: int, active_label: str, escalated_active: bool) -> str:
    # Toggles the escalated filter while preserving the current label.
    href = _query(active_label, not escalated_active)
    cls = "active" if escalated_active else ""
    return f'<a href="{_esc(href)}" class="{cls}">escalated<span class="n">{count}</span></a>'


def _sentinel_row(next_offset: int | None) -> str:
    """A hidden marker row the infinite-scroll observer watches. ``data-next``
    is the offset of the next page; absent when there's nothing more to load."""

    attr = f' data-next="{next_offset}"' if next_offset is not None else ""
    return f'        <tr id="scroll-sentinel"{attr}><td colspan="8"></td></tr>'


def _rows_html(edits: list[EditView], next_offset: int | None) -> str:
    """Just the ``<tr>`` rows plus the scroll sentinel — the unit the
    infinite-scroll fetch appends into the existing ``<tbody>``."""

    rows = "\n".join(_row(e) for e in edits)
    return rows + "\n" + _sentinel_row(next_offset)


def _table(edits: list[EditView], next_offset: int | None) -> str:
    return f"""    <div class="card-wrap">
    <table>
      <thead>
        <tr>
          <th>Label</th><th>Conf.</th><th>Article</th><th>Δ bytes</th>
          <th>Comment</th><th>Editor</th><th>Edited (UTC)</th><th>Classified</th>
        </tr>
      </thead>
      <tbody>
{_rows_html(edits, next_offset)}
      </tbody>
    </table>
    </div>"""


def _empty(active: str) -> str:
    scope = f" for <strong>{_esc(active)}</strong>" if active != "all" else ""
    return f"""    <p class="empty">
      No edits to show{scope}.<br />
      The pipeline may still be warming up, or this filter is empty.
    </p>"""


def _page_size() -> int:
    return get_settings().feed_page_size


def render_rows(edits: list[EditView], offset: int) -> str:
    """Render one infinite-scroll page: the ``<tr>`` rows for
    ``edits[offset:offset+page]`` plus a sentinel pointing at the next offset
    (or no ``data-next`` when the window is exhausted). ``edits`` is the full,
    already filtered+ordered list."""

    page = _page_size()
    chunk = edits[offset : offset + page]
    next_offset = offset + page if offset + page < len(edits) else None
    return _rows_html(chunk, next_offset)


def render_feed(
    edits: list[EditView],
    filters: list[str],
    counts: dict[str, int],
    active: str,
    *,
    escalated_active: bool = False,
    escalated_count: int = 0,
    newest_classified_at: datetime | None = None,
) -> str:
    """Render the dynamic part of the dashboard (stats + filters + first page).

    This is what the client poller swaps into ``#feed``; it is also embedded in
    the initial page so the dashboard renders fully without JavaScript. ``edits``
    is the full filtered+ordered list; only the first page is rendered here and
    the infinite-scroll observer appends the rest from ``/fragment/rows``.
    """

    page = _page_size()
    first = edits[:page]
    next_offset = page if page < len(edits) else None
    label_chips = "\n      ".join(
        _filter_chip(f, counts.get(f, 0), active, escalated_active) for f in filters
    )
    chips = label_chips + "\n      " + _escalated_chip(escalated_count, active, escalated_active)
    body = _table(first, next_offset) if first else _empty(active)
    showing = (
        f'<span class="stat">{len(first)}</span> of '
        f'<span class="stat">{counts.get("all", 0)}</span> shown · '
    )
    sub = (
        showing + f'<span class="stat">{escalated_count}</span> escalated · '
        f"newest {_esc(_relative_time(newest_classified_at))} · "
        f"auto-refresh {_REFRESH_SECONDS}s"
    )
    return f"""<p class="sub">{sub}</p>
    <nav class="filters">
      {chips}
    </nav>
    <main>
{body}
    </main>"""


def render_dashboard(
    edits: list[EditView],
    filters: list[str],
    counts: dict[str, int],
    active: str,
    *,
    escalated_active: bool = False,
    escalated_count: int = 0,
    newest_classified_at: datetime | None = None,
) -> str:
    title_suffix = f" · {_esc(active)}" if active != "all" else ""
    feed = render_feed(
        edits,
        filters,
        counts,
        active,
        escalated_active=escalated_active,
        escalated_count=escalated_count,
        newest_classified_at=newest_classified_at,
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Edit Triage{title_suffix}</title>
  <link rel="stylesheet" href="/static/dashboard.css" />
</head>
<body data-refresh-ms="{_REFRESH_SECONDS * 1000}">
  <header>
    <h1>Wikipedia Edit Triage <span id="live" class="live" title="live feed"></span></h1>
  </header>
  <div id="feed">
    {feed}
  </div>
  <script src="/static/dashboard.js" defer></script>
</body>
</html>
"""


def render_warming_up() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="refresh" content="{_REFRESH_SECONDS}" />
  <title>Warming up…</title>
  <link rel="stylesheet" href="/static/warmup.css" />
</head>
<body>
  <div class="card">
    <div class="spinner"></div>
    <h1>Database warming up</h1>
    <p>The data store isn't ready yet. This page retries automatically every few seconds.</p>
  </div>
</body>
</html>
"""
