"""HTML views for the refactor swarm demo UI."""

from __future__ import annotations

import time

from pathlib import Path as FsPath

from stario import asset, at, data
from stario.html import (
    Body,
    Button,
    Defs,
    Div,
    Head,
    Html,
    Input,
    Label,
    Link,
    Marker,
    Meta,
    Option,
    P,
    Path as SvgPath,
    Polygon,
    Script,
    Select,
    Span,
    Svg,
    Title,
)

from .state import RefactorState


def page(*children):
    return Html(
        {"lang": "en"},
        Head(
            Meta({"charset": "UTF-8"}),
            Meta({"name": "viewport", "content": "width=device-width, initial-scale=1"}),
            Title("Remora Refactor Swarm"),
            Link({"rel": "stylesheet", "href": "/static/" + asset("css/style.css")}),
            Link({"rel": "stylesheet", "href": "/static/" + asset("css/refactor.css")}),
            Script({"type": "module", "src": "/static/" + asset("js/datastar.js")}),
        ),
        Body(*children),
    )


def status_view(state: RefactorState):
    pills = [
        _pill("backend", state.backend_connected),
        _pill("stream", state.event_stream_active, neutral_if_false=True),
        _pill("running", state.running, neutral_if_false=True),
    ]
    error = []
    if state.error_message:
        error.append(Div({"class": "error-banner"}, state.error_message))
    return Div({"id": "status-panel"}, Div({"class": "status-row"}, *pills), *error)


def _pill(label: str, ok: bool, neutral_if_false: bool = False):
    if ok:
        cls = "pill ok"
        text = f"{label}: on"
    else:
        cls = "pill neutral" if neutral_if_false else "pill warn"
        text = f"{label}: off"
    return Span({"class": cls}, text)


def control_panel_view(state: RefactorState):
    bundle_labels = {
        "file": "Files (planner)",
        "class": "Classes (design)",
        "function": "Functions (complexity)",
        "method": "Methods (behavior)",
    }
    bundle_options = [Option({"value": ""}, "All bundles")]
    for bundle in state.available_bundles:
        attrs = {"value": bundle}
        if bundle == state.bundle_filter:
            attrs["selected"] = True
        label = bundle_labels.get(bundle, bundle)
        bundle_options.append(Option(attrs, label))

    shortcuts = [
        ("backend", "Backend root"),
        ("backend/backend_app", "Backend app"),
        ("frontend", "Frontend root"),
        ("frontend/refactor_app", "Refactor UI"),
        ("frontend/app", "Chat UI"),
    ]
    shortcut_buttons = []
    for path, label in shortcuts:
        shortcut_buttons.append(
            Button(
                {"type": "button", "class": "shortcut"},
                data.on(
                    "click",
                    f"$target_path='{path}'; @post('/plan-graph');",
                ),
                label,
            )
        )

    return Div(
        {"id": "control-panel", "class": "panel"},
        Div({"class": "panel-title"}, "Run control"),
        Div(
            {"class": "form-row"},
            Label({"for": "target-path"}, "Target path"),
            Input(
                {
                    "id": "target-path",
                    "type": "text",
                    "placeholder": "backend_app/ or frontend/",
                },
                data.bind("target_path"),
            ),
        ),
        Div(
            {"class": "form-row"},
            Label({"for": "bundle-filter"}, "Bundle preset"),
            Select(
                {"id": "bundle-filter"},
                data.bind("bundle_filter"),
                *bundle_options,
            ),
        ),
        Div(
            {"class": "form-row"},
            Label({}, "Quick targets"),
            Div({"class": "target-shortcuts"}, *shortcut_buttons),
        ),
        Div(
            {"class": "form-row button-row"},
            Button(
                {"type": "button", "class": "secondary"},
                data.attr({"disabled": "!$backend_connected"}),
                data.on("click", at.post("/plan-graph")),
                "Plan graph",
            ),
            Button(
                {"type": "button", "class": "primary"},
                data.attr({"disabled": "!$backend_connected"}),
                data.on("click", at.post("/run-graph")),
                "Run swarm",
            ),
            Button(
                {"type": "button", "class": "ghost"},
                data.on("click", at.post("/check-backend")),
                "Check backend",
            ),
        ),
    )


def graph_view(state: RefactorState):
    if not state.plan_nodes:
        return Div(
            {"id": "graph-panel", "class": "panel"},
            Div({"class": "panel-title"}, "Dependency graph"),
            Div(
                {"class": "graph-empty"},
                "No plan loaded yet. Choose a target path and click Plan graph.",
            ),
        )

    lanes = {}
    for node in state.plan_nodes:
        lanes.setdefault(node.lane, []).append(node)

    card_width = 320
    card_height = 180
    col_gap = 28
    row_gap = 32
    label_height = 22
    top_padding = 40
    left_padding = 24
    lane_count = max(len(lanes), 1)
    max_cols = max((len(nodes) for nodes in lanes.values()), default=1)
    graph_width = left_padding + max_cols * card_width + max(max_cols - 1, 0) * col_gap + 20
    graph_height = (
        top_padding
        + lane_count * (card_height + label_height)
        + max(lane_count - 1, 0) * row_gap
        + 20
    )

    lane_rows = []
    coords = {}
    for lane, nodes in sorted(lanes.items()):
        lane_index = len(lane_rows)
        cards = []
        nodes_sorted = sorted(nodes, key=lambda n: (-n.priority, n.name))
        for col_index, node in enumerate(nodes_sorted):
            x = left_padding + col_index * (card_width + col_gap) + card_width / 2
            y = (
                top_padding
                + lane_index * (card_height + label_height + row_gap)
                + label_height
                + card_height / 2
            )
            coords[node.id] = (x, y)
            status = state.node_status.get(node.id, "idle")
            upstream = ", ".join(node.upstream[:3])
            if len(node.upstream) > 3:
                upstream = f"{upstream} +{len(node.upstream) - 3}"
            inbox_key = f"inbox_{node.id}"
            send_action = f"""
if (${inbox_key}.trim()) {{
  @post('/agent-ask', {{payload: {{'agent_id': '{node.id}', 'message': ${inbox_key}, 'target_path': $target_path, 'bundle': $bundle_filter}}}});
  ${inbox_key} = '';
}}
"""
            title = node.name or node.id
            if node.file_path:
                file_name = FsPath(node.file_path).name
                if node.node_type == "file" or title == "unknown":
                    title = file_name or title
            cards.append(
                Div(
                    {"class": "graph-node", "data-state": status},
                    Span({"class": "node-title"}, title),
                    Span({"class": "node-meta"}, f"{node.node_type} · {status}"),
                    Span({"class": "node-path"}, node.file_path),
                    Span({"class": "node-upstream"}, f"upstream: {upstream or 'none'}"),
                    Div(
                        {"class": "node-inbox"},
                        Input(
                            {"type": "text", "placeholder": "Ask this node..."},
                            data.bind(inbox_key),
                        ),
                        Button(
                            {"type": "button", "class": "mini"},
                            data.on("click", send_action),
                            "Ask",
                        ),
                    ),
                )
            )
        lane_rows.append(
            Div(
                {"class": "graph-lane-row"},
                Span({"class": "lane-title"}, f"Lane {lane + 1}"),
                Div({"class": "graph-row-cards"}, *cards),
            )
        )

    edges = []
    for node in state.plan_nodes:
        if node.id not in coords:
            continue
        x2, y2 = coords[node.id]
        for upstream_id in node.upstream:
            if upstream_id not in coords:
                continue
            x1, y1 = coords[upstream_id]
            bend = max(abs(y2 - y1) * 0.4, 40)
            d = (
                f"M{x1:.1f},{y1:.1f} "
                f"C{x1:.1f},{y1 + bend:.1f} {x2:.1f},{y2 - bend:.1f} {x2:.1f},{y2:.1f}"
            )
            edges.append(
                SvgPath(
                    {
                        "d": d,
                        "class": "edge",
                        "fill": "none",
                        "stroke": "rgba(31, 42, 48, 0.25)",
                        "stroke-width": "1.4",
                        "stroke-linecap": "round",
                        "marker-end": "url(#arrowhead)",
                    }
                )
            )

    progress = state.progress
    progress_text = (
        f"{progress['completed']}/{progress['total']} done · "
        f"{progress['running']} running · {progress['failed']} failed"
    )

    return Div(
        {"id": "graph-panel", "class": "panel"},
        Div(
            {"class": "panel-title"},
            "Dependency graph",
            Span({"class": "panel-subtitle"}, progress_text),
        ),
        Div(
            {"class": "graph-scroll"},
            Div(
                {
                    "class": "graph-wrap",
                    "style": f"width:{graph_width}px; height:{graph_height}px; position:relative;",
                },
                Svg(
                    {
                        "class": "graph-edges",
                        "width": str(graph_width),
                        "height": str(graph_height),
                        "viewBox": f"0 0 {graph_width} {graph_height}",
                        "aria-hidden": "true",
                        "style": "position:absolute; inset:0; pointer-events:none;",
                    },
                    Defs(
                        Marker(
                            {
                                "id": "arrowhead",
                                "markerWidth": "10",
                                "markerHeight": "6",
                                "refX": "8",
                                "refY": "3",
                                "orient": "auto",
                            },
                            Polygon(
                                {
                                    "points": "0 0, 10 3, 0 6",
                                    "class": "edge-arrow",
                                    "fill": "rgba(31, 42, 48, 0.35)",
                                }
                            ),
                        )
                    ),
                    *edges,
                ),
                Div(
                    {
                        "class": "graph-lanes",
                        "style": f"width:{graph_width}px; min-height:{graph_height}px;",
                    },
                    *lane_rows,
                ),
            ),
        ),
    )


def events_view(state: RefactorState):
    if not state.events:
        return Div(
            {"id": "events-panel", "class": "panel"},
            Div({"class": "panel-title"}, "Event feed"),
            Div({"class": "events-empty"}, "Event feed will populate during runs."),
        )

    items = []
    for event in list(state.events)[:40]:
        timestamp = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
        items.append(
            Div(
                {"class": "event-row"},
                Span({"class": "event-time"}, timestamp),
                Span({"class": "event-type"}, event.event_type),
                Span({"class": "event-message"}, event.message),
                P({"class": "event-payload"}, event.payload or ""),
            )
        )

    return Div(
        {"id": "events-panel", "class": "panel"},
        Div({"class": "panel-title"}, "Event feed"),
        Div({"class": "event-list"}, *items),
    )


def results_view(state: RefactorState):
    if not state.results:
        return Div(
            {"id": "results-panel", "class": "panel"},
            Div({"class": "panel-title"}, "Agent results"),
            Div({"class": "results-empty"}, "Agent summaries appear here."),
        )

    cards = []
    for result in list(state.results)[:20]:
        timestamp = time.strftime("%H:%M:%S", time.localtime(result.timestamp))
        cards.append(
            Div(
                {"class": "result-card"},
                Span({"class": "result-title"}, result.agent_name),
                Span({"class": "result-id"}, result.agent_id),
                Span({"class": "result-time"}, timestamp),
                P({"class": "result-summary"}, result.summary),
            )
        )

    return Div(
        {"id": "results-panel", "class": "panel"},
        Div({"class": "panel-title"}, "Agent results"),
        Div({"class": "result-grid"}, *cards),
    )


def blocked_view(state: RefactorState):
    if not state.blocked:
        return Div(
            {"id": "blocked-panel", "class": "panel"},
            Div({"class": "panel-title"}, "Blocked inputs"),
            Div({"class": "blocked-empty"}, "No human inputs requested."),
        )

    blocks = []
    for blocked in state.blocked.values():
        options = ""
        if blocked.options:
            options = " | options: " + ", ".join(blocked.options)
        blocks.append(
            Div(
                {"class": "blocked-card"},
                Span({"class": "blocked-agent"}, blocked.agent_id),
                Span({"class": "blocked-question"}, blocked.question + options),
                Div(
                    {"class": "blocked-actions"},
                    Input(
                        {"type": "text", "placeholder": "Your response..."},
                        data.bind(f"reply_{blocked.request_id}"),
                    ),
                    Button(
                        {"type": "button", "class": "primary"},
                        data.on(
                            "click",
                            at.post("/submit-input", payload={"request_id": blocked.request_id}),
                        ),
                        "Send",
                    ),
                ),
            )
        )

    return Div(
        {"id": "blocked-panel", "class": "panel"},
        Div({"class": "panel-title"}, "Blocked inputs"),
        Div({"class": "blocked-list"}, *blocks),
    )


def home_view(state: RefactorState):
    signals = {
        "target_path": state.target_path,
        "bundle_filter": state.bundle_filter,
        "backend_connected": state.backend_connected,
    }
    for blocked in state.blocked.values():
        signals[f"reply_{blocked.request_id}"] = ""
    for node in state.plan_nodes:
        signals[f"inbox_{node.id}"] = ""

    return page(
        Div(
            {"class": "app"},
            data.signals(signals, ifmissing=True),
            data.init(at.get("/subscribe")),
            Div(
                {"class": "hero"},
                Div({"class": "hero-title"}, "Refactor Swarm"),
                P(
                    {"class": "hero-subtitle"},
                    "Plan and execute a dependency-aware refactor swarm across a codebase. "
                    "Nodes run in parallel by lane, and you can watch the graph evolve live.",
                ),
            ),
            status_view(state),
            Div(
                {"class": "layout refactor-layout"},
                Div(
                    {"class": "graph-stack"},
                    Div(
                        {"class": "control-row"},
                        control_panel_view(state),
                        blocked_view(state),
                        results_view(state),
                    ),
                    graph_view(state),
                    events_view(state),
                ),
            ),
        )
    )
