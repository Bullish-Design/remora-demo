**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**

# E2E Testing Proposal — Graph Viewer

## Table of Contents

1. [Problem Statement](#1-problem-statement) — What the current test suite does and does not cover
2. [Architecture Challenges](#2-architecture-challenges) — Why this app is unusual to E2E test
3. [Tool Comparison](#3-tool-comparison) — Playwright vs Cypress vs Selenium vs httpx/raw SSE
4. [Recommendation](#4-recommendation) — Playwright (Python) with rationale
5. [Test Strategy](#5-test-strategy) — What to test, layers, and the fixture approach
6. [SSE Testing Patterns](#6-sse-testing-patterns) — How to test Datastar SSE DOM morphing
7. [Screenshots and Video](#7-screenshots-and-video) — Capturing visual artifacts
8. [Fixture Architecture](#8-fixture-architecture) — Server lifecycle, DB seeding, Playwright wiring
9. [Proposed Test Cases](#9-proposed-test-cases) — Concrete test list mapped to demo beats
10. [Comparison to Neovim Demo](#10-comparison-to-neovim-demo) — Analogies to asciinema + tmux
11. [Implementation Plan](#11-implementation-plan) — Ordered steps with effort estimates
12. [Dependencies and Environment](#12-dependencies-and-environment) — What to install
13. [Open Questions](#13-open-questions) — Decisions for the user

---

## 1. Problem Statement

### Current coverage (179 tests, all passing)

The existing test suite is thorough at the **unit and integration level**:

| Layer | Tests | What's covered |
|-------|-------|---------------|
| Unit | `test_layout.py`, `test_svg.py`, `test_css.py` | ForceLayout physics, SVG builder output, CSS generation |
| Unit | `test_views.py` | View functions return correct HTML strings |
| Unit | `test_mock_llm.py` (19 tests) | MockLLMClient scripted response matching |
| Integration | `test_bridge.py` (307 lines) | DBBridge fingerprinting, change detection, Relay publishing |
| Integration | `test_integration_graph.py` (517 lines) | Full pipeline: DB -> GraphState -> Layout -> Views |
| Golden path | `test_golden_path.py` (810 lines) | All demo beats 2-9 simulated via DB writes + view assertions |
| Structure | `test_app.py`, `test_entry_points.py` | Module structure, route wiring, Stario import checks |
| Cross-repo | `test_cross_process.py` | Imports remora library directly (fails without it installed) |

### What's NOT covered

None of these tests exercise the **actual browser experience**:

1. **SSE connection lifecycle** — Does the browser actually connect to `/subscribe` and receive Datastar patches?
2. **DOM morphing** — Does Datastar correctly morph the SVG graph when patches arrive?
3. **CSS transitions** — Do the 0.5s ease-out position transitions actually animate?
4. **User interactions** — Clicking a node -> sidebar loads -> clicking Approve/Reject -> command queued
5. **Visual correctness** — Does the graph look right? Are colors correct? Are nodes positioned properly?
6. **Full-stack round trip** — DB change -> bridge poll -> Relay publish -> SSE patch -> DOM update -> visible to user
7. **Multiple concurrent SSE consumers** — Does the app handle multiple browser tabs?
8. **Error states** — What happens when the DB is missing? When the server is slow?

The gap is clear: we test that the right HTML strings are generated, but never that the browser actually renders and reacts to them correctly.

---

## 2. Architecture Challenges

The graph viewer has three properties that make E2E testing non-trivial:

### 2.1 SSE-driven updates (not request/response)

The `/subscribe` endpoint is a long-lived SSE connection. The browser connects once, then receives a stream of `datastar-patch-elements` events. Traditional HTTP testing (request -> assert response) doesn't apply. The test must:
- Wait for the SSE connection to establish
- Inject data changes (by writing to the SQLite DB)
- Wait for the DOM to update (after bridge poll + Relay publish + SSE delivery + Datastar morph)
- Assert on the resulting DOM state

### 2.2 Server-rendered SVG with CSS transitions

The graph is an SVG document rendered server-side. Position changes come as full SVG re-renders via SSE patches. CSS `transition: all 0.5s ease-out` handles the visual animation. This means:
- The DOM changes are **complete replacements** of the `#graph-container` div, not incremental attribute changes
- Testing "did the node move" requires either waiting for the CSS transition to complete, or asserting on the SVG element's `cx`/`cy` attributes before the transition

### 2.3 Stario process lifecycle

The app runs as `python -m graph --db <path>`. Tests need to:
- Start the Stario server as a subprocess (or in-process via asyncio)
- Wait for it to be ready (listening on a port)
- Run browser tests against it
- Shut it down cleanly after tests

---

## 3. Tool Comparison

### 3.1 Playwright (Python) — pytest-playwright

| Aspect | Assessment |
|--------|-----------|
| **Language** | Python — same as the project |
| **pytest integration** | First-class via `pytest-playwright` plugin. `page` fixture auto-provided. |
| **SSE support** | Excellent. `page.on("response")` can monitor SSE connections. `page.wait_for_selector()` and `page.locator().to_be_visible()` wait for DOM changes driven by SSE. No special SSE API needed — Playwright just sees the DOM after Datastar morphs it. |
| **Screenshots** | `page.screenshot(path="...", full_page=True)` — full page or element-level |
| **Video recording** | `record_video_dir="videos/"` on browser context — records WebM per test |
| **Trace viewer** | `--tracing on` — records DOM snapshots, network, console, screenshots at each step. Can replay in GUI. |
| **SVG testing** | Standard CSS selectors work on SVG (`page.locator("circle[data-node-id='load_config']")`). Can read SVG attributes via `element.get_attribute("cx")`. |
| **Async support** | Both sync and async APIs. `pytest-playwright-asyncio` for async fixtures. |
| **Headless/headed** | Both modes. `--headed` for visual debugging. |
| **Browser engines** | Chromium, Firefox, WebKit — useful for cross-browser SVG rendering checks |
| **Installation** | `pip install pytest-playwright && playwright install` |
| **Maturity** | Very mature. Active development by Microsoft. |

### 3.2 Cypress

| Aspect | Assessment |
|--------|-----------|
| **Language** | JavaScript/TypeScript only |
| **pytest integration** | None. Separate test runner (`npx cypress run`). Cannot share fixtures with existing pytest suite. |
| **SSE support** | Poor. Cypress intercepts XHR/fetch but has limited SSE support. Community workarounds exist but are fragile. |
| **Screenshots/Video** | Good built-in support |
| **SVG testing** | Functional but less ergonomic than Playwright |
| **Deal-breaker** | Different language. Cannot share DB fixtures with pytest. Cannot use existing `GraphState`, `MockLLMClient`, etc. |

### 3.3 Selenium (Python)

| Aspect | Assessment |
|--------|-----------|
| **Language** | Python |
| **pytest integration** | Manual setup. No built-in fixtures. |
| **SSE support** | No native support. Must poll DOM manually with explicit waits. |
| **Screenshots** | `driver.save_screenshot()` — basic |
| **Video recording** | None built-in. Requires external tools (ffmpeg, VNC recording). |
| **Trace viewer** | None |
| **Maturity** | Mature but dated. Playwright has largely superseded it. |
| **Deal-breaker** | No video recording. No trace viewer. Verbose API. Slower than Playwright. |

### 3.4 Raw SSE testing (httpx + asyncio)

| Aspect | Assessment |
|--------|-----------|
| **Approach** | Use `httpx` to connect to the SSE endpoint, parse events, assert on HTML fragments |
| **Pros** | No browser needed. Fast. Tests the SSE stream directly. |
| **Cons** | Does NOT test Datastar morphing. Does NOT test CSS transitions. Does NOT test click interactions. Does NOT produce screenshots or video. |
| **Verdict** | Useful as a *complementary* layer (test SSE content without a browser) but does not replace E2E. |

---

## 4. Recommendation

**Playwright (Python)** is the clear winner for this project.

Reasons:
1. **Same language** — Python. Shares the pytest ecosystem with the existing 179 tests.
2. **pytest-playwright** — First-class pytest integration. `page` fixture just works.
3. **SSE + Datastar works transparently** — Playwright doesn't need to understand SSE. It just sees the DOM after Datastar processes the events. `page.locator("#graph-container svg circle").to_have_count(13)` will automatically wait for the SSE patches to arrive and the DOM to update.
4. **Screenshots + video + traces** — All three built-in. This directly answers the user's request for "screen recording/screenshots" as an analog to asciinema.
5. **SVG is just DOM** — Playwright can query SVG elements with CSS selectors, read `cx`/`cy`/`r` attributes, check `fill` colors, etc.
6. **DB fixture sharing** — E2E tests can use the same `_create_demo_db()` helper from `test_golden_path.py` to seed the database.
7. **Headed mode** — `--headed` flag for visual debugging during development.

---

## 5. Test Strategy

### 5.1 Three-layer testing pyramid

```
Layer 3: E2E (Playwright)         ~10-15 tests    [NEW]
  - Real browser, real server, real SSE
  - Verifies the full stack: DB -> bridge -> Relay -> SSE -> Datastar -> DOM
  - Screenshots, video, traces

Layer 2: Integration (existing)    ~60 tests       [DONE]
  - DB -> GraphState -> Layout -> Views (HTML string assertions)
  - Bridge fingerprinting and Relay publishing
  - Golden path beat simulation

Layer 1: Unit (existing)           ~120 tests      [DONE]
  - Layout physics, SVG builders, CSS generation, view functions
  - MockLLM script matching
```

### 5.2 What E2E tests should NOT do

- Duplicate integration-level assertions (e.g., "does the bridge detect a new node?")
- Test MockLLM scripting logic
- Test ForceLayout physics
- Test CSS string generation

### 5.3 What E2E tests SHOULD do

- Verify the full visual experience matches expectations
- Catch regressions in SSE delivery, Datastar morphing, and CSS transitions
- Produce visual artifacts (screenshots, video) for demo validation
- Test user interactions (click, command submission)
- Validate cross-browser SVG rendering (if desired)

---

## 6. SSE Testing Patterns

### 6.1 The key insight: Playwright doesn't need to parse SSE

Datastar connects to `/subscribe`, receives `text/event-stream` events, and morphs the DOM. From Playwright's perspective, the DOM just changes. We wait for DOM changes with locators:

```python
# Wait for nodes to appear in the SVG
page.locator("circle.node").first.wait_for(state="attached", timeout=5000)

# Assert node count after SSE delivers initial graph
expect(page.locator("circle.node")).to_have_count(13)

# Wait for a specific node to appear
expect(page.locator("[data-node-id='load_config']")).to_be_visible()
```

### 6.2 Triggering updates via DB writes

The test injects changes by writing directly to the SQLite DB (same approach as `test_golden_path.py`). The bridge's 300ms polling interval means the DOM update arrives within ~300-600ms:

```python
# 1. Seed initial DB state
# 2. Start server pointing to that DB
# 3. Open browser to http://localhost:PORT
# 4. Wait for initial graph to render
# 5. Write new data to DB (e.g., change node status)
# 6. Wait for DOM to reflect the change (locator auto-waits)
# 7. Assert + screenshot
```

### 6.3 Timing considerations

- Bridge polls every 300ms (configurable via `poll_interval`)
- For tests, use a shorter poll interval (50-100ms) to speed things up
- Playwright's auto-waiting (default 30s timeout) handles the SSE delay gracefully
- CSS transitions take 500ms — if testing visual position, wait 500ms after DOM change

---

## 7. Screenshots and Video

### 7.1 Automated screenshots per beat

Each E2E test can capture a screenshot at key moments:

```python
def test_golden_path_beat2(page, demo_server):
    page.goto(demo_server.url)
    page.locator("circle.node").first.wait_for()
    page.screenshot(path="screenshots/beat2_initial_graph.png", full_page=True)
```

These screenshots serve double duty:
1. **Visual regression detection** — compare against golden screenshots
2. **Demo documentation** — "this is what the graph looks like at beat 2"

### 7.2 Video recording

```python
@pytest.fixture
def video_context(browser):
    context = browser.new_context(
        record_video_dir="videos/",
        record_video_size={"width": 1280, "height": 720},
    )
    yield context
    context.close()  # Video saved on close
```

This produces a WebM video of the entire test — the browser equivalent of asciinema for the terminal.

### 7.3 Trace viewer

```bash
pytest tests/test_e2e.py --tracing on
playwright show-trace test-results/trace.zip
```

The trace viewer is a time-travel debugger: DOM snapshots, network requests, console logs, and screenshots at every action. Far more powerful than video for debugging failures.

---

## 8. Fixture Architecture

### 8.1 Server lifecycle fixture

```python
import asyncio
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DemoServer:
    process: subprocess.Popen
    url: str
    db_path: str
    port: int

@pytest.fixture(scope="function")
def demo_server(tmp_path):
    """Start the graph viewer server with a fresh DB."""
    db_path = str(tmp_path / "indexer.db")
    _create_demo_db(db_path)  # Reuse from test_golden_path.py

    port = _find_free_port()
    proc = subprocess.Popen(
        ["python", "-m", "graph", "--db", db_path, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_for_server(f"http://127.0.0.1:{port}", timeout=10)

    yield DemoServer(process=proc, url=f"http://127.0.0.1:{port}", db_path=db_path, port=port)

    proc.terminate()
    proc.wait(timeout=5)
```

### 8.2 Alternative: in-process server via asyncio

Instead of subprocess, run Stario in-process using `asyncio.create_task()`:

```python
@pytest.fixture
async def demo_server(tmp_path):
    db_path = str(tmp_path / "indexer.db")
    _create_demo_db(db_path)

    app, bridge = create_app(db_path, poll_interval=0.05)
    bridge_task = asyncio.create_task(bridge.run())

    # Start server in background
    server_task = asyncio.create_task(app.serve(host="127.0.0.1", port=0))
    # ... wait for ready ...
```

The subprocess approach is simpler and more realistic (tests the actual entry point). Recommend starting with subprocess.

### 8.3 DB mutation helpers

```python
def add_node(db_path: str, node_id: str, **kwargs) -> None:
    """Insert a node into the DB (triggers bridge detection)."""

def change_status(db_path: str, node_id: str, new_status: str) -> None:
    """Update a node's status."""

def add_event(db_path: str, event_type: str, from_agent: str, **kwargs) -> None:
    """Insert an event into the events table."""

def set_cursor_focus(db_path: str, agent_id: str, file_path: str, line: int) -> None:
    """Update the cursor_focus table."""

def add_proposal(db_path: str, agent_id: str, old_source: str, new_source: str) -> None:
    """Insert a pending proposal."""
```

These are thin wrappers around `sqlite3.connect()` + `INSERT`/`UPDATE`, similar to what `test_golden_path.py` already does inline.

---

## 9. Proposed Test Cases

### 9.1 Core E2E tests (~10 tests)

| Test | Demo Beat | What it verifies |
|------|-----------|-----------------|
| `test_initial_page_load` | - | Server starts, page loads, DOCTYPE + title correct |
| `test_initial_graph_renders` | Beat 2 | All 13 nodes visible as SVG circles, 14 edges as lines |
| `test_node_colors_match_status` | Beat 2 | idle=gray, running=blue, error=red (check SVG `fill`) |
| `test_cursor_focus_highlights_node` | Beat 4 | Write cursor_focus -> node gets blue highlight ring |
| `test_click_node_loads_sidebar` | Beat 4 | Click a node circle -> sidebar shows node details |
| `test_status_change_animates` | Beat 6 | Change status to "running" -> node color changes via SSE |
| `test_new_events_appear_in_stream` | Beat 7 | Add event to DB -> event stream shows new event type |
| `test_proposal_shows_approve_reject` | Beat 9 | Add proposal -> sidebar shows Approve/Reject buttons |
| `test_command_submission` | Beat 5/10 | Fill chat form, submit -> command_queue has new row |
| `test_node_topology_change` | Beat 3 | Add a new node -> it appears in the graph |

### 9.2 Visual artifact tests (~3 tests)

| Test | What it produces |
|------|-----------------|
| `test_screenshot_empty_graph` | Screenshot of the empty state (no nodes) |
| `test_screenshot_full_graph` | Screenshot of the full configlib demo graph |
| `test_screenshot_cascade_sequence` | Multiple screenshots showing the cascade beats 6-9 |

### 9.3 Optional / stretch tests

| Test | What it verifies |
|------|-----------------|
| `test_multiple_tabs` | Two browser tabs both receive SSE updates |
| `test_rapid_db_changes` | Many rapid DB writes -> graph stays consistent |
| `test_server_restart_reconnect` | Server restarts -> SSE reconnects, graph recovers |

---

## 10. Comparison to Neovim Demo

The Neovim demo's testing challenge is similar:

| Aspect | Neovim Demo | Graph Viewer |
|--------|-------------|-------------|
| **Medium** | Terminal (Neovim inside tmux) | Browser |
| **Recording** | asciinema (terminal recorder) | Playwright video + screenshots |
| **Automation** | tmux send-keys (inject keystrokes) | Playwright click/type (inject interactions) |
| **Assertions** | Screen scraping tmux capture-pane | DOM assertions via Playwright locators |
| **State injection** | LSP notifications / DB writes | Direct SQLite DB writes |
| **Replay** | asciinema-player | Playwright trace viewer |

Playwright is the browser equivalent of asciinema + tmux:
- **asciinema** -> `record_video_dir` (records the browser session)
- **tmux send-keys** -> `page.click()`, `page.fill()`, `page.keyboard.press()`
- **tmux capture-pane** -> `page.content()`, `page.locator().text_content()`
- **Terminal screenshots** -> `page.screenshot()`

The analogy is direct. Playwright gives us everything the Neovim demo would get from asciinema + tmux, plus more (trace viewer, cross-browser, auto-waiting).

---

## 11. Implementation Plan

### Phase 1: Infrastructure (1-2 hours)

1. Add `pytest-playwright` to `pyproject.toml` dev dependencies
2. Create `tests/e2e/` directory
3. Create `tests/e2e/conftest.py` with server lifecycle fixture
4. Extract `_create_demo_db()` into a shared helper (or import from `test_golden_path.py`)
5. Create DB mutation helpers
6. Verify basic page load test works

### Phase 2: Core E2E tests (2-3 hours)

7. Write the 10 core tests from section 9.1
8. Add appropriate `data-node-id` and `data-testid` attributes to SVG/HTML output if needed for reliable selectors
9. Tune timeouts and poll intervals for test speed

### Phase 3: Visual artifacts (1 hour)

10. Add screenshot capture tests
11. Configure video recording via `conftest.py`
12. Set up `--tracing retain-on-failure` as default

### Phase 4: CI integration (optional, 30 min)

13. Add Playwright browser install to CI
14. Configure artifact upload for screenshots/videos

**Total estimated effort: 4-6 hours**

---

## 12. Dependencies and Environment

### New dependencies

```toml
[project.optional-dependencies]
e2e = [
    "pytest-playwright",
]
```

### One-time setup

```bash
pip install pytest-playwright
playwright install chromium  # ~150MB download
```

### Running E2E tests

```bash
# Headless (CI)
pytest tests/e2e/ -v

# Headed (development)
pytest tests/e2e/ -v --headed

# With video recording
pytest tests/e2e/ -v --video on

# With screenshots on failure
pytest tests/e2e/ -v --screenshot only-on-failure

# With trace on failure
pytest tests/e2e/ -v --tracing retain-on-failure

# Full artifacts
pytest tests/e2e/ -v --video on --screenshot on --tracing retain-on-failure
```

### Environment notes

- Playwright supports Python 3.8+, so no conflict with Python 3.14
- The devenv.nix may need to add Playwright's system dependencies (handled by `playwright install --with-deps`)
- E2E tests are slower than unit tests (~2-5s each vs ~10ms). Keep them in a separate directory so they can be run independently.

---

## 13. Open Questions

1. **Selector strategy** — Should we add `data-testid` attributes to the HTML/SVG output for more robust selectors? (Recommended: yes, but only where CSS selectors are fragile.)

2. **SVG attribute changes** — The current SVG output doesn't include `data-node-id` attributes on circles. We'd need to add those for reliable node selection. This is a small change to `svg.py`.

3. **Server startup approach** — Subprocess vs in-process? Subprocess is simpler and more realistic. In-process requires managing the asyncio event loop carefully with Playwright's sync API.

4. **Poll interval for tests** — The default 300ms is fine for production but makes tests wait. Using 50ms in test mode would speed things up. Could be a `--poll-interval` CLI flag.

5. **Screenshot golden comparison** — Do we want pixel-diff regression testing (e.g., with `pixelmatch`)? Or are screenshots just for documentation? Start with documentation; add pixel-diff later if needed.

6. **Browser matrix** — Test on Chromium only, or also Firefox/WebKit? Start with Chromium only. SVG rendering is consistent enough across modern browsers.

---

**NEVER use subagents (the Task tool). Do ALL work directly. NO EXCEPTIONS.**
