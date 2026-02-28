"""HTML views for the demo UI."""

from __future__ import annotations

import time

from stario import asset, at, data
from stario.html import (
    Body,
    Button,
    Div,
    Form,
    Head,
    Html,
    Input,
    Label,
    Link,
    Meta,
    P,
    Script,
    Span,
    Textarea,
    Title,
)

from .state import DemoState, ChatMessage, ToolCall


def page(*children):
    return Html(
        {"lang": "en"},
        Head(
            Meta({"charset": "UTF-8"}),
            Meta(
                {"name": "viewport", "content": "width=device-width, initial-scale=1"}
            ),
            Title("Remora Stario Demo"),
            Link({"rel": "stylesheet", "href": "/static/" + asset("css/style.css")}),
            Script({"type": "module", "src": "/static/" + asset("js/datastar.js")}),
        ),
        Body(*children),
    )


def status_view(state: DemoState):
    status_items = [
        pill("backend", state.backend_connected),
        pill("session", state.session_active),
        pill("stream", state.event_stream_active, neutral_if_false=True),
    ]

    error_content = []
    if state.error_message:
        error_content.append(Div({"class": "error-banner"}, state.error_message))

    if not state.backend_connected:
        error_content.append(
            Div(
                {"class": "info-banner"},
                "Backend not reachable. Start it with: ",
                Span({"class": "code"}, "cd backend && devenv shell && start-backend"),
            )
        )

    return Div(
        {"id": "status-panel"},
        Div({"class": "status-row"}, *status_items),
        *error_content,
    )


def pill(label: str, ok: bool, neutral_if_false: bool = False):
    if ok:
        cls = "pill ok"
        text = f"{label}: online"
    else:
        cls = "pill neutral" if neutral_if_false else "pill warn"
        text = f"{label}: offline"
    return Span({"class": cls}, text)


def workspace_panel(state: DemoState):
    workspace_status = "Ready" if state.workspace_valid else "Needs validation"
    workspace_class = "pill ok" if state.workspace_valid else "pill warn"

    return Div(
        {"class": "panel"},
        Div({"class": "panel-title"}, "Workspace"),
        Div(
            {"class": "form-row"},
            Label({"for": "workspace-path"}, "Workspace path"),
            Input(
                {
                    "id": "workspace-path",
                    "type": "text",
                    "placeholder": "/path/to/project",
                },
                data.bind("workspace_path"),
                data.on("change", at.post("/set-workspace")),
            ),
        ),
        Div(
            {"class": "status-row"}, Span({"class": workspace_class}, workspace_status)
        ),
        Button(
            {"type": "button", "class": "secondary"},
            data.on("click", at.post("/check-backend")),
            "Check backend",
        ),
    )


def config_panel(state: DemoState):
    preset_cards = []
    for preset in state.available_presets:
        key = f"preset_{preset}"
        preset_cards.append(
            Label(
                {"class": "checkbox-card"},
                Input(
                    {"type": "checkbox", "id": key},
                    data.bind(key),
                ),
                Span({}, preset.replace("_", " ")),
            )
        )

    return Div(
        {"class": "panel"},
        Div({"class": "panel-title"}, "Agent setup"),
        Div(
            {"class": "form-row"},
            Label({"for": "system-prompt"}, "System prompt"),
            Textarea(
                {"id": "system-prompt", "placeholder": "Guide the agent..."},
                data.bind("system_prompt"),
            ),
        ),
        Div(
            {"class": "form-row"},
            Label({}, "Tool presets"),
            Div({"class": "checkbox-grid"}, *preset_cards),
        ),
        Div(
            {"class": "form-row"},
            Button(
                {"type": "button", "class": "primary"},
                data.attr({"disabled": "!$workspace_valid || !$backend_connected"}),
                data.on("click", at.post("/start-session")),
                "Start session",
            ),
            Button(
                {"type": "button", "class": "secondary"},
                data.attr({"disabled": "!$session_active"}),
                data.on("click", at.post("/stop-session")),
                "End session",
            ),
        ),
    )


def chat_header_view(state: DemoState):
    session_label = "Active" if state.session_active else "Idle"
    session_class = "pill ok" if state.session_active else "pill neutral"
    return Div(
        {"id": "chat-header", "class": "chat-header"},
        Div(
            {},
            Span({"class": "panel-title"}, "Inbox / Outbox"),
            Span({"class": session_class}, f"session: {session_label}"),
        ),
        Span({"class": "processing"}, "Thinking..." if state.is_processing else ""),
    )


def chat_view(state: DemoState):
    messages = state.messages
    if not messages:
        return Div(
            {"id": "chat-stream", "class": "chat-stream"},
            Div({"class": "chat-empty"}, "No messages yet. Start a session to begin."),
        )

    return Div(
        {"id": "chat-stream", "class": "chat-stream"},
        *[message_card(msg) for msg in messages],
    )


def message_card(msg: ChatMessage):
    label = "Inbox" if msg.role == "user" else "Outbox"
    timestamp = time.strftime("%H:%M", time.localtime(msg.timestamp))
    return Div(
        {"class": f"message-card {msg.role}"},
        Div({"class": "message-meta"}, Span({}, label), Span({}, timestamp)),
        Div({"class": "message-body"}, msg.content or ""),
    )


def chat_input_view(state: DemoState):
    return Form(
        {"class": "chat-input"},
        data.on("submit", "evt.preventDefault()"),
        Textarea(
            {"placeholder": "Ask the agent...", "id": "message-input"},
            data.bind("message_input"),
            data.attr({"disabled": "!$session_active || $is_processing"}),
            data.on(
                "keydown",
                """
                if (evt.key === 'Enter' && !evt.shiftKey && $message_input.trim()) {
                    evt.preventDefault();
                    @post('/send-message');
                    $message_input = '';
                }
                """,
            ),
        ),
        Button(
            {"type": "button", "class": "primary"},
            data.attr(
                {"disabled": "!$session_active || $is_processing || !$message_input"}
            ),
            data.on(
                "click",
                """
                if ($message_input.trim()) {
                    @post('/send-message');
                    $message_input = '';
                    document.getElementById('message-input').focus();
                }
                """,
            ),
            "Send",
        ),
    )


def tool_log_view(state: DemoState):
    if not state.tool_log:
        return Div(
            {"id": "tool-log", "class": "tool-log"},
            Div({"class": "tool-card"}, "Tool events will appear here."),
        )

    cards = []
    for call in state.tool_log[-30:]:
        cards.append(tool_card(call))

    return Div({"id": "tool-log", "class": "tool-log"}, *cards)


def tool_card(call: ToolCall):
    timestamp = time.strftime("%H:%M", time.localtime(call.timestamp))
    card_class = "tool-card error" if call.is_error else "tool-card"
    args_preview = call.arguments or {}
    result_preview = call.result or "(pending)"

    return Div(
        {"class": card_class},
        Div({"class": "tool-title"}, call.name),
        Div({"class": "tool-meta"}, f"{timestamp} | args: {args_preview}"),
        Div({"class": "tool-meta"}, f"result: {result_preview}"),
    )


def home_view(state: DemoState):
    signals = {
        "workspace_path": state.workspace_path,
        "workspace_valid": state.workspace_valid,
        "system_prompt": state.agent_config.system_prompt,
        "message_input": "",
        "is_processing": state.is_processing,
        "session_active": state.session_active,
        "backend_connected": state.backend_connected,
    }

    for preset in state.available_presets:
        key = f"preset_{preset}"
        signals[key] = preset in state.agent_config.enabled_presets

    return page(
        Div(
            {"class": "app"},
            data.signals(signals, ifmissing=True),
            data.init(at.get("/subscribe")),
            Div(
                {"class": "hero"},
                Div({"class": "hero-title"}, "Stario Remora Demo"),
                P(
                    {"class": "hero-subtitle"},
                    "A single-agent workspace chat with live tool telemetry. "
                    "Pick a folder, tune the prompt, and watch the tools fire in real time.",
                ),
            ),
            status_view(state),
            Div(
                {"class": "layout"},
                Div(
                    {"class": "left-column"},
                    workspace_panel(state),
                    config_panel(state),
                    Div(
                        {"class": "panel"},
                        Div({"class": "panel-title"}, "Tool log"),
                        tool_log_view(state),
                    ),
                ),
                Div(
                    {"class": "right-column"},
                    Div(
                        {"class": "panel chat-panel"},
                        chat_header_view(state),
                        chat_view(state),
                        chat_input_view(state),
                    ),
                ),
            ),
        )
    )
