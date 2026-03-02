# Stario + Datastar — Skills Reference

Condensed mental model for building web frontends with Stario (Python 3.14) and Datastar (reactive hypermedia).

---

## 1. What Stario Is

Stario is a **real-time hypermedia framework** for Python 3.14+. It combines an async HTTP server with server-sent events (SSE) streaming, HTML element builders, and first-class Datastar integration. Think of it as "htmx on the server side" — the server renders HTML fragments and pushes DOM patches to the browser over SSE.

Key properties:
- **Async-native** — all handlers are `async def`, the server runs on asyncio
- **No templates** — HTML is built with Python function calls (`Div`, `H1`, etc.)
- **SSE-first** — streaming updates to the browser is the primary interaction model
- **Datastar integration** — `data.*` and `at.*` helpers generate Datastar attributes
- **Python 3.14 required** — uses new language features (type parameter syntax, etc.)

---

## 2. Core Handler Pattern

Every route handler has the same signature:

```python
async def handler(c: Context, w: Writer) -> None:
    ...
```

- `c` (Context) — the request: `c.req.path`, `c.req.method`, `c.req.tail` (catch-all remainder), `c.req.query`, headers, body parsing. Also provides `await c.signals(MyDataclass)` for reading Datastar client state, and `c("event_name", {"key": "val"})` for tracing.
- `w` (Writer) — the response: write HTML, JSON, SSE patches, redirects, etc.

**Go-style DI via closures** — dependencies are injected by wrapping handlers in factory functions:

```python
def make_graph_handler(state: GraphState, relay: Relay):
    async def handler(c: Context, w: Writer) -> None:
        snapshot = await asyncio.to_thread(state.snapshot)
        w.html(render_graph(snapshot))
    return handler

# Registration:
app.get("/graph", make_graph_handler(state, relay))
```

This is the idiomatic Stario pattern. No decorators, no DI framework, no magic.

---

## 3. Routing

```python
app = Stario(tracer)

# Exact path match
app.get("/", home_handler)
app.post("/send", send_handler)

# Catch-all — matches /agent/anything/here
app.get("/agent/*", agent_handler)
# Inside handler: c.req.tail gives "anything/here"

# Static assets
app.assets("/static", Path("static"))
```

**No `{param}` syntax.** Stario does not have path parameters like `/user/{id}`. Use catch-all `/*` and parse `c.req.tail` yourself.

**Router for sub-apps:**
```python
from stario import Router

router = Router()
router.get("/detail", detail_handler)
router.post("/update", update_handler)

app.mount("/api", router)
# Routes: /api/detail, /api/update
```

---

## 4. Writer

### One-shot responses (return immediately):
```python
w.html(element)        # Full HTML response (renders element to string)
w.json(data)           # JSON response
w.text("hello")        # Plain text
w.redirect("/path")    # HTTP redirect
w.empty(status=204)    # Empty response with status code
```

### SSE streaming responses (keep connection open):
```python
w.patch(element)       # Push a DOM patch — element MUST have an id attribute
w.sync({"key": "val"}) # Update Datastar signals on the client
w.navigate("/path")    # Client-side navigation
w.remove("#selector")  # Remove a DOM element
w.execute("alert(1)")  # Execute JavaScript on client
```

**Critical rule:** `w.patch(element)` requires the element to have an `id` attribute so Datastar knows which DOM node to replace.

---

## 5. SSE and `w.alive()`

For long-lived SSE connections, use `w.alive()` which yields items from an async iterable and automatically handles cleanup on client disconnect or server shutdown:

```python
async def subscribe(c: Context, w: Writer) -> None:
    async for subject, data in w.alive(relay.subscribe("graph.*")):
        w.patch(render_update(data))
    # Cleanup runs here after disconnect/shutdown
```

`w.alive()` wraps any async iterable. It:
- Yields items as long as the client is connected
- Exits the loop when the client disconnects
- Exits the loop on graceful server shutdown
- Lets you run cleanup code after the loop

This is the standard pattern for SSE endpoints in Stario.

---

## 6. Relay

In-process pub/sub system. No external dependencies (no Redis, no NATS).

```python
from stario import Relay

relay = Relay()

# Publish — synchronous, fire-and-forget
relay.publish("graph.nodes.updated", {"node_id": "abc"})
relay.publish("chat.room.123", {"msg": "hello"})

# Subscribe — async iterator, yields (subject, data) tuples
async for subject, payload in relay.subscribe("graph.*"):
    print(f"Got {subject}: {payload}")
```

**NATS-style subject patterns:**
- `graph.*` — matches `graph.nodes`, `graph.edges` (single level)
- `graph.>` — matches `graph.nodes.updated`, `graph.a.b.c` (multi-level)
- `*` — matches any single-segment subject

**Key properties:**
- `publish()` is sync — safe to call from sync code (e.g., a bridge polling thread)
- `subscribe()` returns an async iterator — use in `async for` or `w.alive()`
- Subscriptions auto-cleanup when the iterator is garbage collected
- Fully in-process — no network, no serialization

---

## 7. HTML Builders

```python
from stario.html import Div, H1, P, Ul, Li, Button, Input, Form, Span, Pre, Code

# Dicts = attributes, everything else = children
Div({"class": "container", "id": "main"}, H1("Title"), P("Body"))

# Multiple dicts merge
Div({"class": "a"}, {"id": "b"}, "content")

# Style as dict
Div({"style": {"color": "red", "font-size": "14px"}}, "styled")

# None and False are ignored (conditional rendering)
Div(H1("Always"), None if not show_extra else P("Extra"))

# Lists unpack as children
Ul(*[Li(item) for item in items])
```

**Rendering:** Elements are rendered to strings automatically by `w.html()` and `w.patch()`. For manual rendering, use `render()`:
```python
from stario.html import render
html_string = render(Div("hello"))
```

---

## 8. SafeString

**Critical for this project.** Views return plain HTML/SVG strings. These must be wrapped in `SafeString` before passing to Stario elements, otherwise they'll be HTML-escaped.

```python
from stario.html import SafeString

# Without SafeString — BAD: Stario escapes the SVG
Div("<svg>...</svg>")  # Renders as literal text "&lt;svg&gt;..."

# With SafeString — GOOD: SVG renders as HTML
Div(SafeString("<svg>...</svg>"))  # Renders as actual SVG
```

**Project convention:** Views (`graph/views/*.py`) return plain strings. `SafeString` wrapping happens only in `app.py` handlers:
```python
async def handler(c: Context, w: Writer) -> None:
    html = render_shell(snapshot)  # Returns plain string
    w.html(SafeString(html))       # Wrap at the boundary
```

The `safe_str` attribute on SafeString instances is the raw string value.

---

## 9. Datastar Helpers

Datastar is a lightweight frontend framework (like htmx but reactive). Stario provides Python helpers that generate the correct `data-*` HTML attributes.

### Signal attributes (`data.*`):
```python
from stario import data

data.signals({"count": 0, "name": ""})        # data-signals='{"count":0,"name":""}'
data.signals({"count": 0}, ifmissing=True)     # Only set if not already on client
data.bind("field_name")                         # data-bind="field_name"
data.text("$count")                             # data-text="$count"
data.on("click", "$count++")                    # data-on-click="$count++"
data.on("click", at.get("/api/action"))         # data-on-click with server roundtrip
data.on("input", at.get("/search"), debounce=0.3)  # Debounced
data.show("$visible")                           # data-show="$visible"
data.init(at.get("/subscribe"))                 # Run on mount (SSE subscription)
data.indicator("loading")                       # Loading indicator signal
data.attr({"disabled": "!$msg"})                # Reactive attribute binding
```

### Server actions (`at.*`):
```python
from stario import at

at.get("/path")        # GET request to server
at.post("/path")       # POST request to server
```

### Reading client signals in handlers:
```python
from dataclasses import dataclass

@dataclass
class SearchSignals:
    query: str = ""

async def search(c: Context, w: Writer) -> None:
    signals = await c.signals(SearchSignals)
    results = do_search(signals.query)
    w.patch(render_results(results))
```

---

## 10. Server

```python
async def main():
    with RichTracer() as tracer:
        app = Stario(tracer)
        # ... register routes ...
        await app.serve(host="127.0.0.1", port=8000, workers=1)
```

- `await app.serve()` — async, blocks until shutdown
- `workers` — number of worker processes (default 1, increase for production)
- Graceful shutdown: `w.alive()` loops exit automatically on shutdown signal
- Background tasks: use `asyncio.create_task()` before `await app.serve()`

---

## 11. Imports Cheatsheet

```python
# Core
from stario import Context, Writer, Stario, RichTracer, Relay, Router, at, data

# HTML elements
from stario.html import (
    Div, H1, H2, H3, P, Span, Pre, Code, Button, Input, Form,
    Ul, Li, Body, Head, Html, Meta, Title, Script, Style, Link,
    SafeString, render
)

# Relay (also available from top-level)
from stario.relay import Relay
```

---

## 12. Reference Locations

| Resource | Path |
|----------|------|
| Stario docs | `.context/stario/docs/` |
| Stario source | `.context/stario/src/stario/` |
| Stario examples (chat app) | `.context/stario/examples/chat/` |
| Stario tests | `.context/stario/tests/` |
| Datastar Python SDK | `.context/datastar-python-develop/` |
| API quick-reference | `.scratch/skills/stario-api-notes.md` |

**Key doc files:**
- `routing.md` — Full routing details
- `handlers.md` — Handler patterns
- `writer.md` — All Writer methods
- `signals_and_patching.md` — SSE reactive patterns
- `datastar_reference.md` — All Datastar attributes
- `context.md` — Context object details
- `html_guide.md` — HTML builder details

