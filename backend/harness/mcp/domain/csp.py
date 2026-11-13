"""The Content-Security-Policy an MCP app's iframe renders under."""

from __future__ import annotations

from urllib.parse import urlsplit

_CSP_DEFAULT_SOURCES = {
    "script-src": ["'unsafe-inline'"],
    "style-src": ["'unsafe-inline'"],
    "img-src": ["data:", "blob:"],
    "font-src": ["data:"],
    "media-src": ["data:", "blob:"],
    "connect-src": [],
    "frame-src": [],
}
_CSP_DOMAIN_KEYS = {
    "resourceDomains": ("script-src", "style-src", "img-src", "font-src", "media-src"),
    "connectDomains": ("connect-src",),
    "frameDomains": ("frame-src",),
}


def build_csp(meta: dict | None) -> str:
    """The Content-Security-Policy for one app's iframe, from the resource's `_meta`."""
    sources = {directive: list(values) for directive, values in _CSP_DEFAULT_SOURCES.items()}
    ui = meta.get("ui") if isinstance(meta, dict) else None
    csp = ui.get("csp") if isinstance(ui, dict) else None
    if isinstance(csp, dict):
        for key, directives in _CSP_DOMAIN_KEYS.items():
            for origin in _origins(csp.get(key)):
                for directive in directives:
                    sources[directive].append(origin)
    directives = ["default-src 'none'", "object-src 'none'", "base-uri 'none'"]
    for directive, values in sources.items():
        directives.append(f"{directive} {' '.join(values)}" if values else f"{directive} 'none'")
    return "; ".join(directives)


def _origins(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    origins: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        parts = urlsplit(value)
        if parts.scheme in ("https", "wss") and parts.hostname and parts.hostname != "*":
            origins.append(f"{parts.scheme}://{parts.netloc}")
    return origins
