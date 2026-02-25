"""
Frontend views - using Stario HTML helpers.

These views must match the hub's dashboard_view structure for Datastar
to correctly morph DOM elements by ID.
"""

from stario import asset, at, data
from stario.html import (
    Body,
    Button,
    Div,
    Head,
    Html,
    Input,
    Link,
    Meta,
    SafeString,
    Script,
    Title,
    render,
)


def home_view() -> Html:
    """
    Home page - initializes Datastar signals and subscribes to hub.

    The view structure must match the hub's dashboard_view for Datastar
    to correctly morph DOM elements by ID.
    """
    return Html(
        {"lang": "en"},
        Head(
            Meta({"charset": "UTF-8"}),
            Meta({"name": "viewport", "content": "width=device-width, initial-scale=1.0"}),
            Title("Remora Dashboard"),
            Link({"rel": "stylesheet", "href": "/static/" + asset("css/style.css")}),
            Script(
                {
                    "type": "module",
                    "src": "/static/" + asset("js/datastar.js"),
                }
            ),
        ),
        Body(
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
                        "filePickerOpen": False,
                        "filePickerPath": "",
                        "filePickerError": "",
                    },
                },
            ),
            data.init(at.get("/subscribe")),
            Div(
                {"class": "header"},
                Div({}, "Remora Dashboard"),
                Div({"class": "status connected"}, "Connected to hub"),
            ),
            Div(
                {"class": "main"},
                Div(
                    {"id": "events-panel"},
                    Div({"id": "events-header"}, "Events Stream"),
                    Div({"id": "events-list"}, "Loading..."),
                ),
                Div(
                    {"id": "main-panel"},
                    Div(
                        {"class": "card graph-launcher-card"},
                        Div({}, "Launch Graph"),
                        Div(
                            {"class": "graph-launcher-form"},
                            Input(
                                {
                                    "type": "text",
                                    "placeholder": "Graph ID (required)",
                                    "data-bind": "graphLauncher.graphId",
                                }
                            ),
                            Input(
                                {
                                    "type": "text",
                                    "placeholder": "Bundle (optional)",
                                    "data-bind": "graphLauncher.bundle",
                                }
                            ),
                            Input(
                                {
                                    "type": "text",
                                    "placeholder": "Target description (optional)",
                                    "data-bind": "graphLauncher.target",
                                }
                            ),
                            SafeString(f"""
                            <div class="form-group input-with-button">
                                <input type="text" placeholder="Target file path (optional)" data-bind="graphLauncher.targetPath">
                                <button type="button" class="btn" 
                                    data-on-click="$graphLauncher.filePickerOpen = true; $graphLauncher.filePickerPath = ''; @get('/api/files');">
                                    Browse
                                </button>
                            </div>"""),
                            Button(
                                {
                                    "type": "button",
                                    "data-on-click": """
                                    const graphId = $graphLauncher?.graphId?.trim();
                                    if (!graphId) {
                                        alert('Graph ID is required to launch a graph.');
                                        return;
                                    }
                                    const payload = {
                                        graph_id: graphId,
                                        bundle: $graphLauncher?.bundle?.trim() || 'default',
                                    };
                                    const targetValue = $graphLauncher?.target?.trim();
                                    if (targetValue) {
                                        payload.target = targetValue;
                                    }
                                    const targetPathValue = $graphLauncher?.targetPath?.trim();
                                    if (targetPathValue) {
                                        payload.target_path = targetPathValue;
                                    }
                                    @post('/graph/execute', payload);
                                    $graphLauncher.graphId = '';
                                """,
                                },
                                "Start Graph",
                            ),
                        ),
                    ),
                    Div(
                        {"class": "card"},
                        Div({}, "Blocked Agents"),
                        Div({"id": "blocked-agents"}, "No agents waiting"),
                    ),
                    Div(
                        {"class": "card"},
                        Div({}, "Agent Status"),
                        Div({"id": "agent-status"}, "No agents running"),
                    ),
                    Div(
                        {"class": "card"},
                        Div({}, "Results"),
                        Div({"id": "results"}, "No results yet"),
                    ),
                    Div(
                        {"class": "card"},
                        Div({}, "Graph Execution"),
                        Div({"id": "execution-progress"}, "No execution"),
                    ),
                    SafeString(f"""
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
                    </div>"""),
                ),
            ),
        ),
    )


def render_home() -> str:
    """Render the home page to string."""
    return render(home_view())
