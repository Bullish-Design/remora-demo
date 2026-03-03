"""Timeline CSS — Catppuccin Mocha theme for the swimlane timeline view."""

from __future__ import annotations


def timeline_css() -> str:
    """Return the complete CSS for the timeline viewer.

    Uses Catppuccin Mocha palette, consistent with the graph viewer.
    Timeline-specific styles for swimlanes, markers, inspector panel.
    """
    return """
:root {
    --bg: #1e1e2e;
    --mantle: #181825;
    --surface: #313244;
    --surface2: #45475a;
    --overlay: #585b70;
    --text: #cdd6f4;
    --subtext: #a6adc8;
    --green: #a6e3a1;
    --blue: #89b4fa;
    --yellow: #f9e2af;
    --red: #f38ba8;
    --gray: #6c7086;
    --lavender: #b4befe;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    background: var(--bg);
    color: var(--text);
    overflow: hidden;
    height: 100vh;
}

.app { display: flex; flex-direction: column; height: 100vh; }

/* ---- Header ---- */
.header {
    background: var(--surface);
    padding: 10px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--surface2);
    flex-shrink: 0;
}
.header-title { font-size: 14px; font-weight: 600; letter-spacing: 0.5px; }
.header-nav { display: flex; align-items: center; gap: 12px; }
.header-nav a {
    color: var(--subtext); text-decoration: none; font-size: 12px;
    padding: 4px 8px; border-radius: 4px; transition: all 0.2s;
}
.header-nav a:hover { color: var(--text); background: var(--surface2); }
.header-nav a.active { color: var(--blue); background: var(--surface2); }
.header-status {
    font-size: 11px; color: var(--gray);
    padding: 2px 8px; border-radius: 4px; background: var(--surface2);
}

/* ---- Layout ---- */
.main { display: flex; flex: 1; overflow: hidden; }
.timeline-pane { flex: 1; position: relative; overflow: hidden; }
.timeline-canvas { width: 100%; height: 100%; }

/* ---- SVG elements ---- */
.event-marker {
    cursor: pointer;
    transition: r 0.2s ease, opacity 0.2s ease;
}
.event-marker:hover {
    r: 9;
    opacity: 0.8;
}

.agent-label {
    font-family: 'JetBrains Mono', monospace;
    pointer-events: none;
}

.lane-bg {
    pointer-events: none;
}

.correlation-line {
    pointer-events: none;
    transition: opacity 0.3s ease;
}

.time-axis text {
    font-family: 'JetBrains Mono', monospace;
}

/* ---- Inspector panel ---- */
.inspector {
    width: 350px; background: var(--surface);
    border-left: 1px solid var(--surface2);
    overflow-y: auto; flex-shrink: 0;
}
.inspector-empty {
    padding: 40px 20px; text-align: center;
    color: var(--gray); font-size: 13px;
}

.inspector-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--surface2);
}
.inspector-type {
    font-size: 12px; font-weight: 600;
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    margin-bottom: 6px;
}
.inspector-field {
    padding: 4px 16px;
    font-size: 11px;
}
.inspector-field-label {
    color: var(--subtext); font-weight: 600;
    display: inline-block; width: 100px;
}
.inspector-field-value {
    color: var(--text);
}
.inspector-payload {
    margin: 8px 16px;
    padding: 8px;
    background: var(--bg);
    border: 1px solid var(--surface2);
    border-radius: 4px;
    font-size: 10px;
    overflow-x: auto;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
}

/* ---- Tooltip ---- */
.timeline-tooltip {
    position: absolute;
    background: var(--surface);
    border: 1px solid var(--surface2);
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 11px;
    pointer-events: none;
    z-index: 100;
    max-width: 300px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    display: none;
}

/* ---- Controls bar ---- */
.timeline-controls {
    padding: 6px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--surface2);
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
}
.timeline-controls label { color: var(--subtext); }
.timeline-controls .btn {
    background: var(--surface2); border: none; color: var(--text);
    font-family: inherit; font-size: 10px; padding: 3px 8px;
    border-radius: 3px; cursor: pointer; transition: background 0.2s;
}
.timeline-controls .btn:hover { background: var(--overlay); }
.timeline-controls .btn.active { background: var(--blue); color: #1e1e2e; }
"""
