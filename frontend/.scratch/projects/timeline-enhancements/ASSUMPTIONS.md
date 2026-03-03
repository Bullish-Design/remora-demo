# Assumptions & Constraints — Timeline Enhancements

> Invariants, constraints, and design decisions that shape every implementation choice.
> Load this file before making any design or coding decision.

---

## 1. Mandatory TDD

Every enhancement MUST follow test-driven development:

1. **Write failing tests first** — add test class(es) to the appropriate test file
2. **Run and confirm failure** — `python -m pytest tests/ -q` should show the new tests failing
3. **Implement minimum code** — just enough to make the new tests pass
4. **Run and confirm all pass** — full suite must pass (253 pre-existing + new tests)

Never write implementation code before its corresponding tests exist and are confirmed to fail.

---

## 2. No Stario Imports in `timeline/`

The entire `timeline/` package (`state.py`, `svg.py`, `css.py`, `views.py`) must **never import Stario**. This is a hard architectural constraint:

- `timeline/` functions return **plain Python strings** — HTML, SVG, CSS as `str`
- Only `graph/app.py` imports Stario (for `SafeString`, `Writer`, route decorators)
- Only `graph/app.py` wraps timeline output in `SafeString` before sending to the client
- This separation ensures `timeline/` is fully testable without Stario installed

**Why**: Stario requires Python 3.14 and specific dependencies. Keeping timeline functions as pure string builders means tests can run in any Python 3.13+ environment.

---

## 3. SafeString Wrapping — Only in `app.py`

- View functions (`render_timeline_shell`, `render_event_inspector`, etc.) return `str`
- Route handlers in `graph/app.py` call `SafeString(result)` before passing to `w.patch()`
- **Never** import `SafeString` in timeline modules
- **Never** return `SafeString` from timeline functions

---

## 4. Catppuccin Mocha Design System

All colors MUST come from the Catppuccin Mocha palette. No custom colors, no hex codes that aren't in this table:

| Name | Hex | Usage |
|------|-----|-------|
| Rosewater | `#f5e0dc` | Accent |
| Flamingo | `#f2cdcd` | Accent |
| Pink | `#f5c2e7` | Accent |
| Mauve | `#cba6f7` | Accent |
| Red | `#f38ba8` | AgentError, errors |
| Maroon | `#eba0ac` | Accent |
| Peach | `#fab387` | Warnings, MessageSend |
| Yellow | `#f9e2af` | Search highlights |
| Green | `#a6e3a1` | AgentComplete, success |
| Teal | `#94e2d5` | Accent |
| Sky | `#89dceb` | AgentStart |
| Sapphire | `#74c7ec` | Accent |
| Blue | `#89b4fa` | Primary actions, active states |
| Lavender | `#b4befe` | Focus rings, correlation lines |
| Text | `#cdd6f4` | Primary text |
| Subtext 1 | `#bac2de` | Secondary text |
| Subtext 0 | `#a6adc8` | Muted text |
| Overlay 2 | `#9399b2` | Borders |
| Overlay 1 | `#7f849c` | Subtle borders |
| Overlay 0 | `#6c7086` | Disabled text |
| Surface 2 | `#585b70` | Elevated surfaces |
| Surface 1 | `#45475a` | Card backgrounds |
| Surface 0 | `#313244` | Input backgrounds |
| Base | `#1e1e2e` | Page background |
| Mantle | `#181825` | Darker background |
| Crust | `#11111b` | Darkest background |

Use CSS custom properties defined in `timeline_css()` (e.g. `var(--bg)`, `var(--text)`, `var(--blue)`) rather than raw hex in CSS rules.

---

## 5. HTML Escaping

All user-derived text MUST be escaped with `html_mod.escape()` before embedding in HTML or SVG output:

```python
import html as html_mod

# In SVG/HTML builders
label = html_mod.escape(agent_name)
```

This applies to:
- Agent names
- Event types (could contain user-defined strings)
- Payload content
- Correlation IDs
- Any text that originates from the database

**Import convention**: Import as `html_mod` to avoid shadowing the variable name `html` (which is commonly used for HTML string content).

---

## 6. f-Strings for SVG/HTML Generation

All SVG and HTML is generated via Python f-strings. No template engines, no XML builders, no Stario elements.

```python
# Correct
def render_event_marker(*, event_id: int, x: float, y: float, event_type: str) -> str:
    color = EVENT_TYPE_COLORS.get(event_type, "#cdd6f4")
    return (
        f'<circle class="event-marker" cx="{x}" cy="{y}" r="{MARKER_RADIUS}" '
        f'fill="{color}" data-event-id="{event_id}" data-event-type="{html_mod.escape(event_type)}"/>'
    )

# Wrong — never use template engines or element builders
```

---

## 7. Keyword-Only Arguments

All SVG builder functions use keyword-only arguments (the `*` separator):

```python
# Correct
def render_event_marker(*, event_id: int, x: float, y: float, event_type: str) -> str:

# Wrong — positional args
def render_event_marker(event_id: int, x: float, y: float, event_type: str) -> str:
```

Exception: `_create_db()` and `_insert_event()` in tests — `conn` is positional, the rest are keyword-only.

The `read_timeline_data()` function also uses keyword-only for filter params:

```python
def read_timeline_data(
    conn: sqlite3.Connection,
    *,
    since: float | None = None,
    until: float | None = None,
    agent_ids: list[str] | None = None,
    correlation_id: str | None = None,
    limit: int | None = None,
) -> TimelineData:
```

---

## 8. Type Hints and Docstrings

- **Type hints on ALL function signatures** — parameters and return types
- **Docstrings on ALL public functions** — one-line summary minimum
- Private/helper functions (prefixed with `_`) should still have type hints but docstrings are optional

```python
def render_legend(*, event_types: list[str]) -> str:
    """Render a color-coded legend strip for the given event types."""
    ...
```

---

## 9. Python 3.13+ Compatibility

The `timeline/` package must work on Python 3.13+:

- Use `from __future__ import annotations` at the top of every file
- Use `X | Y` union syntax (works with `__future__` annotations)
- No Python 3.14-only features in `timeline/` code
- Stario (Python 3.14 only) is confined to `graph/app.py` and `graph/__main__.py`

---

## 10. Database Conventions

- SQLite is the data store, using WAL journal mode
- All DB reads in async handlers MUST use `asyncio.to_thread` to avoid blocking
- `read_timeline_data()` is the single entry point for all timeline data queries
- New query parameters are added as keyword-only args to `read_timeline_data()`
- New standalone functions (like `extract_spans()`, `group_agents()`, `diff_timelines()`) go in `timeline/state.py`
- The `events` table schema is fixed — do NOT modify it

---

## 11. Module Boundaries

| Module | Responsibility | May Import |
|--------|---------------|------------|
| `timeline/state.py` | Data reading, query logic | `sqlite3`, `dataclasses`, stdlib only |
| `timeline/svg.py` | SVG element rendering | `timeline.state` (for `TimelineData` type), `html` as `html_mod` |
| `timeline/css.py` | CSS string generation | Nothing (standalone) |
| `timeline/views.py` | Full HTML page assembly | `timeline.state`, `timeline.svg`, `timeline.css` |
| `graph/app.py` | Route handlers, Stario glue | Everything above + Stario |

**Never** create circular imports. The dependency chain is strictly:
```
css.py → (nothing)
state.py → (nothing)
svg.py → state.py
views.py → state.py, svg.py, css.py
app.py → views.py, state.py (+ Stario)
```

---

## 12. JavaScript Conventions

All JavaScript lives inline in `timeline/views.py` inside `<script>` tags in the shell page. There are no external JS files.

- Use vanilla JS — no frameworks, no build tools
- Global state prefixed with `__timeline` (e.g. `__timelineFollowMode`, `__timelineZoom`)
- Datastar attributes for SSE connection: `data-on-load="@get('/timeline/subscribe')"`
- Event delegation where possible (attach handlers to parent containers)
- MutationObserver for reacting to SSE-driven DOM updates

---

## 13. CSS Conventions

All CSS lives in `timeline/css.py` as a single `timeline_css()` function returning a string.

- CSS custom properties for all Catppuccin colors (defined in `:root`)
- BEM-ish class naming: `.timeline-legend`, `.legend-item`, `.event-marker`
- No CSS-in-JS, no external stylesheets
- Transitions/animations for interactive states (hover, focus, active)

---

## 14. No Speculative Features

Follow YAGNI strictly:
- Only implement what the PLAN.md specifies
- Don't add "nice to have" parameters or functions not in the plan
- Don't add configuration options unless the plan calls for them
- Each enhancement should be minimal and focused

---

## 15. Error Handling

- `read_timeline_data()` should never raise on valid inputs — return empty `TimelineData` for no-match queries
- SVG/view functions should handle empty/missing data gracefully (show "No events" or equivalent)
- `html_mod.escape()` handles the XSS vector — no additional sanitization needed
- Division by zero in time calculations must be guarded (single-event timelines where `time_range[0] == time_range[1]`)

---

## 16. Incremental Enhancement Order

Phases MUST be implemented in order (A → B → C → D → E) because:

- Phase A establishes `data-event-type` and `data-correlation-id` attributes that B, C, D depend on
- Phase B adds filter infrastructure that D and E build upon
- Phase C adds minimap that D3 (brush) extends
- Phase E assumes all rendering and filter infrastructure is in place

Within a phase, enhancements can be done in any order (e.g. A1, A2, A3 in any sequence).
