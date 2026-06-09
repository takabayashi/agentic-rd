"""Plain-Python HTML rendering for the dashboard.

No template engine: the UI is one small table plus a warm-up page, so we build
the markup here and escape every untrusted field with ``html.escape``. This is
the load-bearing safety boundary — edit titles, comments, and editors are
attacker-controllable free text, so anything interpolated into markup goes
through ``_esc`` (and links are only emitted for http(s) URIs).

Live updates use a tiny vanilla-JS poller (no external library, no build step)
that re-fetches the server-rendered ``#feed`` fragment every few seconds and
swaps it in, flashing newly-arrived rows. The server stays the single source of
markup — the client never re-implements row rendering.
"""

import html
from datetime import UTC, datetime
from urllib.parse import quote

from .models import EditView
from .styles import DASHBOARD_CSS, WARMUP_CSS

# Seconds between live-feed refreshes (client-side poll interval).
_REFRESH_SECONDS = 5

_POLL_JS = """
(function () {
  var FEED = document.getElementById('feed');
  var LIVE = document.getElementById('live');
  var INTERVAL = __REFRESH_MS__;

  function knownRevs() {
    var s = {};
    FEED.querySelectorAll('tr[data-rev]').forEach(function (tr) { s[tr.dataset.rev] = 1; });
    return s;
  }

  function tick() {
    if (document.hidden) return;
    var before = knownRevs();
    fetch('/fragment/edits' + window.location.search, { headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        FEED.innerHTML = html;
        FEED.querySelectorAll('tr[data-rev]').forEach(function (tr) {
          if (!before[tr.dataset.rev]) tr.classList.add('new');
        });
        if (LIVE) LIVE.classList.remove('off');
      })
      .catch(function () { if (LIVE) LIVE.classList.add('off'); });
  }

  setInterval(tick, INTERVAL);
})();
""".replace("__REFRESH_MS__", str(_REFRESH_SECONDS * 1000))


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
    delta_cls = "pos" if edit.size_delta >= 0 else "neg"
    delta_sign = "+" if edit.size_delta >= 0 else ""
    return f"""        <tr data-rev="{edit.rev_id}">
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


def _table(edits: list[EditView]) -> str:
    rows = "\n".join(_row(e) for e in edits)
    return f"""    <table>
      <thead>
        <tr>
          <th>Label</th><th>Conf.</th><th>Article</th><th>Δ bytes</th>
          <th>Comment</th><th>Editor</th><th>Edited (UTC)</th><th>Classified</th>
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
    """Render the dynamic part of the dashboard (stats + filters + table).

    This is what the client poller swaps into ``#feed``; it is also embedded in
    the initial page so the dashboard renders fully without JavaScript.
    """

    label_chips = "\n      ".join(
        _filter_chip(f, counts.get(f, 0), active, escalated_active) for f in filters
    )
    chips = label_chips + "\n      " + _escalated_chip(escalated_count, active, escalated_active)
    body = _table(edits) if edits else _empty(active)
    sub = (
        f'<span class="stat">{counts.get("all", 0)}</span> classified · '
        f'<span class="stat">{escalated_count}</span> escalated · '
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
  <style>{DASHBOARD_CSS}</style>
</head>
<body>
  <header>
    <h1>Wikipedia Edit Triage <span id="live" class="live" title="live feed"></span></h1>
  </header>
  <div id="feed">
    {feed}
  </div>
  <script>{_POLL_JS}</script>
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
  <style>{WARMUP_CSS}</style>
</head>
<body>
  <div class="card">
    <h1>Database warming up</h1>
    <p>The data store isn't ready yet. This page retries automatically every few seconds.</p>
  </div>
</body>
</html>
"""
