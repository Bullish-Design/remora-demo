# Frontend Integration — Decisions

## 1. Package name: `graph`
**Decision**: Use `graph` as the top-level package name.
**Alternatives considered**: `app` (too generic)
**Rationale**: User chose `graph` over `app`. It's descriptive and specific to the graph viewer functionality.

## 2. Views return plain strings
**Decision**: All view functions (shell, graph, sidebar, event_stream) return plain Python strings, not Stario objects.
**Rationale**: Keeps views testable without Stario. SafeString wrapping happens only in app.py handlers.

## 3. SVG as f-strings with SafeString
**Decision**: Build SVG using f-string helper functions, wrapped in SafeString for Stario.
**Rationale**: Stario has no SVG elements. F-strings are simple and fast.

## 4. RelayProtocol for testability
**Decision**: Use a Protocol class (`RelayProtocol`) so DBBridge can be tested with a FakeRelay.
**Rationale**: Avoids importing Stario in tests. Protocol-based dispatch is Pythonic.

## 5. Deferred Stario import
**Decision**: Import Stario inside `_serve()` in `__main__.py`, not at module top level.
**Rationale**: Allows the module to be imported and tested without Stario installed. In practice Stario is available in the devenv, but deferred import is safer.

## 6. create_app returns (app, bridge)
**Decision**: `create_app()` returns a tuple of `(app, bridge)` so the caller can start the bridge task.
**Rationale**: The bridge needs to run as an asyncio task alongside the Stario server. Caller starts it before `app.serve()`.
