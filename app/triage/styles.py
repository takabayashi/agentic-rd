"""Static CSS for the dashboard, kept out of render.py so that module stays
focused on markup. Plain string constants — no template engine, no build step.
"""

DASHBOARD_CSS = """
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
    .meta { margin-top: 3px; font-size: 0.72rem; color: var(--muted); }
    .meta a { color: var(--trivia); text-decoration: none; }
    .meta a:hover { text-decoration: underline; }
    .meta .rev { font-variant-numeric: tabular-nums; }
    .sub .stat { color: var(--text); font-weight: 600; }
    .live { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--substantive);
      margin-right: 5px; vertical-align: middle; }
    .live.off { background: var(--muted); }
    tbody tr.new td { animation: flash 1.2s ease-out; }
    @keyframes flash { from { background: color-mix(in srgb, var(--trivia) 28%, transparent); } to { background: transparent; } }
"""

WARMUP_CSS = """
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
