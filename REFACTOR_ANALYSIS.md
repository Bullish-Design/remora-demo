# REFACTOR_ANALYSIS.md

## Overview

This report analyzes the current state of the **remora-demo** frontend library in relation to:
1. The Stario framework patterns and best practices
2. The Remora library's own Stario dashboard implementation
3. The FRONTEND_REFACTOR_GUIDE.md which specifies a file picker implementation

The analysis identifies gaps, anti-patterns, and provides concrete recommendations for achieving a proper Stario/Datastar implementation.

---

## 1. The remora-demo Library

### Purpose
remora-demo is a minimal Stario-based frontend that:
1. Serves a single-page application (SPA) on `/`
2. Proxies Server-Sent Events (SSE) from the hub at `/subscribe` to the browser
3. Proxies API calls to the hub (graph execution, agent responses)

### Current Architecture

```
Browser (Laptop)           Frontend (remora-demo)      Hub (remora)
  Datastar UI            Stario Proxy                 Starlette
```

### Files Analyzed
- `src/remora_demo/frontend/main.py` - 133 lines
- `src/remora_demo/frontend/views.py` - 171 lines

---

## 2. The FRONTEND_REFACTOR_GUIDE.md (Revised)

The guide has been revised to be more concise (304 lines vs original 1208). It provides streamlined instructions for implementing a **file picker** feature.

### Key Updates in Revised Guide

1. **Simpler structure** - 5 main steps instead of 7+ complex iterations
2. **Security first** - Uses `html.escape(name)` to prevent XSS attacks
3. **Hybrid HTML approach** - Uses f-strings for initial modal HTML, `Div` builder for `w.patch()` calls
4. **Cleaner patterns** - Single GET endpoint handles fetch + render + patch + sync

### Guide's Implementation Steps

| Step | File | Description |
|------|------|-------------|
| 1 | `main.py` | Add `/api/files` GET endpoint - proxies to hub, renders HTML, patches DOM, syncs state |
| 2 | `views.py` | Add file picker signals: `filePickerOpen`, `filePickerPath`, `filePickerError` |
| 3 | `views.py` | Add modal HTML with navigation, conditional visibility via `data-show` |
| 4 | `views.py` | Add Browse button to graph launcher form |
| 5 | `style.css` | Add modal styling |

### Key Patterns Emphasized in Revised Guide

| Pattern | Implementation |
|---------|----------------|
| `app.get()` | For fetching data (not POST) |
| `c.req.query.get()` | Reading query params |
| `w.patch(Div(...))` | Replacing HTML fragment in DOM |
| `w.sync({...})` | Updating reactive signals |
| `data.show()` | Conditional visibility |
| `data-on-click` | Event handlers with `@get()` |
| `html.escape()` | Security - escape file names |

---

## 3. Analysis: How Well is remora-demo Doing Things "the Datastar/Stario Way"?

### Current Implementation Assessment

#### ✅ Correct Patterns

| Pattern | Status | Notes |
|---------|--------|-------|
| Handler signature | ✅ Correct | Uses `async def handler(c: Context, w: Writer) -> None` |
| Dataclass signals | ✅ Correct | Uses `@dataclass class ExecuteSignals` |
| `c.signals()` | ✅ Correct | Properly reads client signals |
| `data.signals()` | ✅ Correct | Initializes signals in HTML |
| `data.init(at.get())` | ✅ Correct | Subscribes on page load |
| `data.bind()` | ✅ Correct | Two-way binding on inputs |
| HTML helpers | ✅ Correct | Uses `stario.html` imports |
| Route registration | ✅ Correct | Uses `app.get()`, `app.post()` |

#### ❌ Issues and Deviations

| Issue | Location | Severity | Description |
|-------|----------|----------|-------------|
| Non-standard response | `main.py:41` | **High** | Uses `w.respond(data, content_type, status)` instead of `w.html()` |
| Missing file picker | `views.py` | **High** | No file picker signals, UI, or Browse button - completely missing |
| Missing `/api/files` | `main.py` | **High** | No endpoint to proxy file listing to hub |
| `execute_graph` payload | `main.py:72` | Medium | Only sends `graph_id`, missing optional `bundle`, `target`, `target_path` (used in views.py but not sent) |
| Hub URL hardcoded | `main.py:20` | Low | Should be configurable via environment |

### Specific Code Issues

#### Issue 1: Non-Standard HTTP Response (main.py:41)

**Current:**
```python
async def home(c: Context, w: Writer) -> None:
    html_content = render_home()
    w.respond(html_content.encode(), b"text/html; charset=utf-8", 200)
```

**Recommended (from Stario docs):**
```python
async def home(c: Context, w: Writer) -> None:
    w.html(render_home())
```

The `w.respond()` method is a low-level primitive. The convenience method `w.html()` automatically handles encoding and headers correctly.

#### Issue 2: Incomplete Graph Execution Payload (main.py:66-77)

**Current:**
```python
async def execute_graph(c: Context, w: Writer) -> None:
    signals = await c.signals(ExecuteSignals)
    # Only sends graph_id
    async with session.post(f"{HUB_URL}/graph/execute", json={"graph_id": signals.graph_id}) as resp:
```

**Should include (per views.py:130-133):**
```python
payload = {
    "graph_id": signals.graph_id,
    "bundle": signals.bundle or "default",
}
if signals.target:
    payload["target"] = signals.target
if signals.target_path:
    payload["target_path"] = signals.target_path
```

#### Issue 3: Missing File Picker Implementation

The revised guide specifies adding file picker functionality that is completely missing:

1. **Signals missing** - `views.py:55-60` has:
   ```python
   "graphLauncher": {
       "graphId": "",
       "bundle": "default",
       "target": "",
       "targetPath": "",
   }
   ```
   
   Should include:
   ```python
   "graphLauncher": {
       "graphId": "",
       "bundle": "default",
       "target": "",
       "targetPath": "",
       "filePickerOpen": False,     # Is modal open?
       "filePickerPath": "",        # Current directory path
       "filePickerError": "",       # Error message
   }
   ```

2. **No Browse button** - Current `targetPath` is just a plain `Input`. Should have input + button combo.

3. **No file picker UI** - No modal component with navigation.

4. **No `/api/files` endpoint** - No handler to proxy file listing requests.

5. **Security consideration** - The revised guide uses `html.escape(name)` to prevent XSS when rendering file names.

---

## 4. Reference: Remora Library's Own Dashboard

The Remora library includes its own Stario dashboard at `.context/remora/demo/stario_dashboard/`. This serves as a reference implementation.

### Patterns Used in remora/dashboard

| Pattern | Implementation |
|---------|----------------|
| State management | `DashboardState` dataclass with `get_signals()` method |
| Event streaming | `w.alive(event_bus.stream())` for SSE |
| Initial load | `w.patch(dashboard_view(state))` sends full state on connect |
| Updates | Both `w.patch()` and `w.sync()` for DOM + signals |
| Response handling | Returns JSON with `w.json()` |

### Key Takeaways from Reference

1. **Full state on connect** - The subscribe handler sends the full dashboard view immediately on connection
2. **Signal sync** - Uses `w.sync(dashboard_state.get_signals())` to keep client in sync
3. **Dataclass patterns** - Uses typed dataclasses for signal validation
4. **Proper HTML structure** - Uses component functions like `event_item_view()`, `blocked_card_view()`

---

## 5. Recommendations for Next Steps

### Priority 1: Fix Core Issues

| # | Action | File | Description |
|---|--------|------|-------------|
| 1.1 | Replace `w.respond()` with `w.html()` | `main.py:41` | Use convenience method instead of low-level primitive |
| 1.2 | Fix graph execution payload | `main.py:72` | Include `bundle`, `target`, and `target_path` in request |

### Priority 2: Implement File Picker (per FRONTEND_REFACTOR_GUIDE)

| # | Action | File | Description |
|---|--------|------|-------------|
| 2.1 | Add file picker signals | `views.py` | Add `filePickerOpen`, `filePickerPath`, `filePickerError` to `graphLauncher` |
| 2.2 | Add `/api/files` GET endpoint | `main.py` | Proxy file listing requests to hub |
| 2.3 | Add file picker UI component | `views.py` | Create modal/card with navigation |
| 2.4 | Add Browse button | `views.py` | Replace simple input with input + button combo |
| 2.5 | Add CSS styles | `style.css` | Add modal styling |

### Priority 3: Improve Architecture

| # | Action | Description |
|---|--------|-------------|
| 3.1 | Add dataclass for FileListSignals | Type-safe signal handling |
| 3.2 | Extract components | Create separate view functions (like remora/dashboard) |
| 3.3 | Make HUB_URL configurable | Use environment variable |
| 3.4 | Add security | Use `html.escape()` for file names (per revised guide) |

### Detailed Implementation Steps

Following the revised FRONTEND_REFACTOR_GUIDE.md:

#### Step 1: Fix home() handler

```python
# main.py
async def home(c: Context, w: Writer) -> None:
    """Serve the SPA."""
    w.html(render_home())
```

#### Step 2: Fix execute_graph() to include all fields

```python
# main.py
@dataclass
class ExecuteSignals:
    graph_id: str = ""
    bundle: str = "default"
    target: str = ""
    target_path: str = ""

async def execute_graph(c: Context, w: Writer) -> None:
    signals = await c.signals(ExecuteSignals)
    
    payload = {"graph_id": signals.graph_id}
    if signals.bundle:
        payload["bundle"] = signals.bundle
    if signals.target:
        payload["target"] = signals.target
    if signals.target_path:
        payload["target_path"] = signals.target_path
    
    # ... rest of handler
```

#### Step 3: Add file picker signals (views.py)

```python
data.signals(
    {
        "selectedAgent": None,
        "events": [],
        "blocked": [],
        "agentStates": {},
        "progress": {"total": 0, "completed": 0},
        "results": [],
        "responseDraft": {},
        "graphLauncher": {
            "graphId": "",
            "bundle": "default",
            "target": "",
            "targetPath": "",
            # File picker state (per revised guide)
            "filePickerOpen": False,
            "filePickerPath": "",
            "filePickerError": "",
        },
    },
    ifmissing=True,
),
```

#### Step 4: Add /api/files endpoint (main.py)

Following the revised guide's pattern - single endpoint handles proxy, render, patch, and sync:

```python
import logging
import html
from stario import Context, Writer
from stario.html import Div

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8000")
logger = logging.getLogger(__name__)


async def list_files(c: Context, w: Writer) -> None:
    """Fetch file list from hub and render the file picker UI."""
    path = c.req.query.get("path", "")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{HUB_URL}/api/files",
                params={"path": path} if path else {}
            ) as resp:
                result = await resp.json()
                
                if resp.status >= 400:
                    error = result.get("error", "Unknown error")
                    w.patch(Div({"id": "file-picker-list"}, f"Error: {error}"))
                    w.sync({"filePickerError": error})
                    return
                
                entries = result.get("entries", [])
                current_path = result.get("path", path)
                
                # Render file list items (server-side rendering with security)
                items_html = "".join(
                    _render_file_item(e["name"], e["type"] == "directory", e.get("size"))
                    for e in sorted(entries, key=lambda e: (e["type"] != "directory", e["name"]))
                )
                
                if not items_html:
                    items_html = '<div class="empty-state">No files</div>'
                
                # Patch the list into DOM AND sync navigation state
                w.patch(Div({"id": "file-picker-list"}, items_html))
                w.sync({"filePickerPath": current_path, "filePickerError": ""})
                
    except aiohttp.ClientError as e:
        logger.error(f"Failed to list files: {e}")
        w.patch(Div({"id": "file-picker-list"}, f"Error: {e}"))


def _render_file_item(name: str, is_dir: bool, size: int | None = None) -> str:
    """Render a single file/directory entry. Uses html.escape for security."""
    icon = "📁" if is_dir else "📄"
    size_str = f" ({size})" if size and not is_dir else ""
    safe_name = html.escape(name)
    
    if is_dir:
        return f'''<div class="file-item directory">
            <button type="button" class="file-item-btn" 
                data-on-click="$graphLauncher.filePickerPath = $graphLauncher.filePickerPath 
                    ? $graphLauncher.filePickerPath + '/{safe_name}' 
                    : '{safe_name}';
                @get('/api/files?path=' + $graphLauncher.filePickerPath);">
                {icon} {safe_name}/
            </button>
        </div>'''
    else:
        return f'''<div class="file-item file">
            <button type="button" class="file-item-btn"
                data-on-click="$graphLauncher.targetPath = $graphLauncher.filePickerPath 
                    ? $graphLauncher.filePickerPath + '/{safe_name}' 
                    : '{safe_name}';
                $graphLauncher.filePickerOpen = false;">
                {icon} {safe_name}{size_str}
            </button>
        </div>'''


# Register route in run_app():
async def run_app() -> None:
    with RichTracer() as tracer:
        app = Stario(tracer, compression=CompressionConfig())
        app.assets("/static", "src/remora_demo/static")
        
        app.get("/", home)
        app.get("/subscribe", subscribe)
        app.get("/api/files", list_files)  # NEW
        app.post("/graph/execute", execute_graph)
        app.post("/agent/*", respond)
        
        await app.serve(host="0.0.0.0", port=8001)
```

#### Step 5: Add file picker modal UI (views.py)

Following the revised guide's pattern using f-strings:

```python
def file_picker_modal() -> str:
    """File picker modal - only visible when filePickerOpen is true."""
    return f'''
    <div id="file-picker" class="modal-overlay" data-show="$graphLauncher.filePickerOpen">
        <div class="modal-content card">
            <div class="modal-header">Select File</div>
            <div class="error-message" data-text="$graphLauncher.filePickerError"></div>
            <div class="path-display">
                Path: <span data-text="$graphLauncher.filePickerPath || '/'"></span>
            </div>
            <div class="nav-buttons">
                <button type="button" class="btn btn-small"
                    data-show="$graphLauncher.filePickerPath !== ''"
                    data-on-click="const parts = $graphLauncher.filePickerPath.split('/'); parts.pop(); @get('/api/files?path=' + parts.join('/'));">
                    ⬆ Up
                </button>
            </div>
            <div id="file-picker-list" class="file-list"></div>
            <div class="modal-footer">
                <button type="button" class="btn"
                    data-on-click="$graphLauncher.filePickerOpen = false">
                    Cancel
                </button>
            </div>
        </div>
    </div>'''
```

#### Step 6: Add Browse button to graph launcher

```python
# Replace targetPath input with:
f'''
<div class="form-group input-with-button">
    <input type="text" placeholder="Target file path (optional)" data-bind="graphLauncher.targetPath">
    <button type="button" class="btn" 
        data-on-click="$graphLauncher.filePickerOpen = true; $graphLauncher.filePickerPath = ''; @get('/api/files');">
        Browse
    </button>
</div>'''
```

---

## Summary

The remora-demo library is currently a **minimal, functional proxy** but lacks the file picker feature specified in the FRONTEND_REFACTOR_GUIDE (revised). The core Stario/Datastar patterns are mostly correct, with one significant issue (using `w.respond()` instead of `w.html()`) and several missing features.

### Key Findings from Revised Guide Analysis:

1. **Cleaner patterns** - The revised guide shows a simpler approach: single GET endpoint handles proxy + render + patch + sync
2. **Security emphasis** - Uses `html.escape(name)` to prevent XSS in file names
3. **Hybrid HTML** - Uses f-strings for initial modal, `Div` builder for `w.patch()` calls
4. **Proper separation** - The `/api/files` endpoint is the core of the file picker pattern

### Implementation Priority:

1. **Fix** - Replace `w.respond()` with `w.html()` in home handler
2. **Fix** - Complete `execute_graph` payload to include bundle, target, target_path
3. **Add** - File picker signals, modal UI, Browse button
4. **Add** - `/api/files` endpoint with security (html.escape)
5. **Add** - CSS modal styles

Once these changes are made, remora-demo will fully align with the Stario/Datastar patterns as intended by the Remora library developer.
