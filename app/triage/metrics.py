"""Prometheus metrics for the dashboard app.

Exposes a ``/metrics`` endpoint (mountable ASGI app) plus a small middleware
that records request counts and latency labelled by method, route template, and
status. Route *template* (not raw path) keeps label cardinality bounded.
"""

import time
from collections.abc import Awaitable, Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

REQUESTS = Counter(
    "triage_http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "triage_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)


def _route_template(request: Request) -> str:
    """The matched route path template (e.g. ``/api/edits``), falling back to a
    constant for unmatched paths so 404 scans can't explode label cardinality."""

    route = request.scope.get("route")
    return getattr(route, "path", None) or "__unmatched__"


async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    path = _route_template(request)
    elapsed = time.perf_counter() - start
    LATENCY.labels(request.method, path).observe(elapsed)
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    return response


def metrics_response() -> Response:
    """Render the Prometheus exposition payload."""

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
