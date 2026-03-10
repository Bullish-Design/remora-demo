"use strict";

const REMORA = window.REMORA_BASE_URL || "http://localhost:8765";
const MAX_LOG_EVENTS = 50;
const FLASH_DURATION_MS = 900;
const REPLAY_GRAPH_ID = "swarm";

let cy = null;
let eventSource = null;
let replayEvents = [];
let replayIndex = 0;
let isLiveMode = true;

const KNOWN_EVENT_TYPES = [
  "AgentStartEvent",
  "AgentCompleteEvent",
  "AgentErrorEvent",
  "NodeDiscoveredEvent",
  "NodeRemovedEvent",
  "HumanChatEvent",
  "ContentChangedEvent",
  "FileSavedEvent",
  "CursorFocusEvent",
  "AgentMessageEvent",
  "ManualTriggerEvent",
  "ScaffoldRequestEvent",
  "RewriteProposalEvent",
  "RewriteAppliedEvent",
  "RewriteRejectedEvent",
];

document.addEventListener("DOMContentLoaded", async () => {
  initCytoscape();
  attachSidebarClose();
  attachChatForm();

  await loadGraph();
  startEventStream();
  attachReplayControls(REPLAY_GRAPH_ID);
});

function initCytoscape() {
  cy = cytoscape({
    container: document.getElementById("cy"),
    elements: [],
    style: getCyStyles(),
    layout: { name: "preset" },
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: false,
    minZoom: 0.1,
    maxZoom: 5,
  });

  cy.on("tap", "node", (event) => {
    const node = event.target;
    if (node.isParent()) {
      return;
    }
    openSidebar(node.id(), node.data("label") || node.id());
  });

  cy.on("dblclick", (event) => {
    if (event.target === cy) {
      cy.fit(undefined, 40);
    }
  });
}

async function loadGraph() {
  let data;
  try {
    const response = await fetch(`${REMORA}/graph/data`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    data = await response.json();
  } catch (error) {
    console.error("Failed to load graph data:", error);
    addEventToLog({
      type: "ERROR",
      summary: `Graph load failed: ${error.message}`,
    });
    return;
  }

  const nodes = Array.isArray(data.nodes) ? data.nodes : [];
  const edges = Array.isArray(data.edges) ? data.edges : [];

  if (!nodes.length) {
    addEventToLog({
      type: "INFO",
      summary: "No graph nodes yet. Index code in remora and reload.",
    });
    return;
  }

  cy.add(nodes);
  cy.add(edges);

  cy.edges().forEach((edge) => {
    if (!cy.getElementById(edge.data("source")).length || !cy.getElementById(edge.data("target")).length) {
      cy.remove(edge);
    }
  });

  runLayout();
}

function runLayout() {
  const layout = cy.layout({
    name: "cose-bilkent",
    animate: false,
    randomize: true,
    idealEdgeLength: 80,
    nodeRepulsion: 8000,
    gravity: 0.5,
    padding: 30,
  });
  layout.run();
}

function getCyStyles() {
  return [
    {
      selector: "node",
      style: {
        "background-color": "#2563eb",
        label: "data(label)",
        "font-size": "9px",
        "text-valign": "bottom",
        "text-halign": "center",
        color: "#c9d1e3",
        "text-outline-color": "#0f1117",
        "text-outline-width": "2px",
        width: 22,
        height: 22,
        "border-width": 0,
      },
    },
    {
      selector: "node[type = 'module']",
      style: {
        "background-color": "#1e3a5f",
        shape: "rectangle",
        width: 30,
        height: 30,
        "font-size": "10px",
        "font-weight": "bold",
      },
    },
    {
      selector: "node[type = 'class']",
      style: {
        "background-color": "#4c1d95",
        shape: "round-rectangle",
        width: 26,
        height: 26,
      },
    },
    {
      selector: "node[type = 'method']",
      style: {
        "background-color": "#1a3a4a",
        width: 18,
        height: 18,
      },
    },
    {
      selector: "node[status = 'running']",
      style: {
        "background-color": "#d97706",
        "border-width": 2,
        "border-color": "#fbbf24",
      },
    },
    {
      selector: "node[status = 'error']",
      style: {
        "background-color": "#b91c1c",
        "border-width": 2,
        "border-color": "#ef4444",
      },
    },
    {
      selector: "node[status = 'pending_approval']",
      style: {
        "background-color": "#7c3aed",
        "border-width": 2,
        "border-color": "#a78bfa",
      },
    },
    {
      selector: ":parent",
      style: {
        "background-color": "#151820",
        "background-opacity": 0.6,
        "border-color": "#2a2d3a",
        "border-width": 1,
        "font-size": "10px",
        "text-valign": "top",
        padding: "10px",
      },
    },
    {
      selector: "edge",
      style: {
        width: 1,
        "line-color": "#374151",
        "target-arrow-color": "#374151",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        "arrow-scale": 0.7,
        opacity: 0.6,
      },
    },
    {
      selector: "edge[type = 'calls']",
      style: {
        "line-color": "#3c4f6d",
        "target-arrow-color": "#3c4f6d",
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 2,
        "border-color": "#60a5fa",
      },
    },
    {
      selector: ".cursor-focused",
      style: {
        "border-width": 3,
        "border-color": "#fbbf24",
        "background-color": "#78350f",
      },
    },
    { selector: ".flash-AgentStartEvent", style: { "background-color": "#34d399" } },
    { selector: ".flash-AgentCompleteEvent", style: { "background-color": "#60a5fa" } },
    { selector: ".flash-AgentErrorEvent", style: { "background-color": "#f87171" } },
    { selector: ".flash-NodeDiscoveredEvent", style: { "background-color": "#a78bfa" } },
    { selector: ".flash-HumanChatEvent", style: { "background-color": "#fbbf24" } },
    { selector: ".flash-ContentChangedEvent", style: { "background-color": "#34d399" } },
    { selector: ".flash-AgentMessageEvent", style: { "background-color": "#22d3ee" } },
    { selector: ".flash-CursorFocusEvent", style: { "background-color": "#fbbf24" } },
  ];
}

function startEventStream() {
  if (!isLiveMode) {
    return;
  }

  if (eventSource) {
    eventSource.close();
  }

  eventSource = new EventSource(`${REMORA}/events`);

  eventSource.onmessage = (event) => {
    handleRawEvent(event.data);
  };

  eventSource.addEventListener("open", () => {
    addEventToLog({ type: "INFO", summary: "SSE connected" });
  });

  eventSource.onerror = () => {
    if (eventSource) {
      eventSource.close();
    }
    if (isLiveMode) {
      setTimeout(startEventStream, 3000);
    }
  };

  for (const eventType of KNOWN_EVENT_TYPES) {
    eventSource.addEventListener(eventType, (event) => {
      handleRawEvent(event.data, eventType);
    });
  }
}

function handleRawEvent(rawData, explicitType) {
  let data;
  try {
    data = JSON.parse(rawData);
  } catch (_error) {
    return;
  }

  const eventType = explicitType || data.type || data.event_type || data.kind || "event";
  const payload = data.payload && typeof data.payload === "object" ? data.payload : {};
  const agentId = resolveAgentId(data, payload, eventType);

  if (eventType === "NodeDiscoveredEvent" && payload.node_id) {
    ensureNodeExists(payload);
  }
  if (eventType === "NodeRemovedEvent" && payload.node_id) {
    const existing = cy.getElementById(payload.node_id);
    if (existing.length) {
      cy.remove(existing);
    }
  }

  if (agentId && cy) {
    const cyNode = cy.getElementById(agentId);
    if (cyNode.length) {
      cyNode.flashClass(`flash-${eventType}`, FLASH_DURATION_MS);
      const nextStatus = deriveStatus(eventType, payload);
      if (nextStatus) {
        cyNode.data("status", nextStatus);
      }
    }
  }

  if (eventType === "CursorFocusEvent" && cy) {
    const focusedId = payload.focused_agent_id || agentId;
    cy.nodes().removeClass("cursor-focused");
    if (focusedId) {
      const focusedNode = cy.getElementById(focusedId);
      if (focusedNode.length) {
        focusedNode.addClass("cursor-focused");
        cy.animate(
          {
            center: { eles: focusedNode },
            zoom: Math.max(cy.zoom(), 1.5),
          },
          { duration: 300 },
        );
      }
    }
  }

  addEventToLog({
    type: eventType,
    agent_id: agentId,
    summary: data.summary || payload.name || payload.message || "",
    timestamp: data.timestamp || payload.timestamp,
    raw: data,
  });
}

function resolveAgentId(data, payload, eventType) {
  if (typeof data.agent_id === "string" && data.agent_id) {
    return data.agent_id;
  }
  if (typeof payload.agent_id === "string" && payload.agent_id) {
    return payload.agent_id;
  }
  if (eventType === "CursorFocusEvent" && payload.focused_agent_id) {
    return payload.focused_agent_id;
  }
  if (typeof payload.to_agent === "string" && payload.to_agent) {
    return payload.to_agent;
  }
  if (typeof payload.node_id === "string" && payload.node_id) {
    return payload.node_id;
  }
  return "";
}

function deriveStatus(eventType, payload) {
  if (payload && typeof payload.status === "string" && payload.status) {
    return payload.status;
  }
  if (eventType === "AgentStartEvent") {
    return "running";
  }
  if (eventType === "AgentCompleteEvent") {
    return "idle";
  }
  if (eventType === "AgentErrorEvent") {
    return "error";
  }
  return "";
}

function ensureNodeExists(payload) {
  if (!cy || !payload.node_id) {
    return;
  }

  const nodeId = String(payload.node_id);
  const existing = cy.getElementById(nodeId);

  const nodeData = {
    id: nodeId,
    label: payload.name || nodeId,
    type: payload.node_type || "function",
    status: payload.status || "idle",
    file_path: payload.file_path || "",
    full_name: payload.full_name || "",
    ...(payload.parent_id ? { parent: payload.parent_id } : {}),
  };

  if (existing.length) {
    existing.data(nodeData);
    return;
  }

  cy.add({ data: nodeData });
  runLayout();
}

async function openSidebar(nodeId, nodeLabel) {
  setSignal("selectedNodeId", nodeId);
  setSignal("sidebarOpen", true);
  setSignal("sidebarLoading", true);
  setSidebarOpen(true);

  const labelElement = document.getElementById("sidebar-node-label");
  if (labelElement) {
    labelElement.textContent = nodeLabel || nodeId;
  }

  const contentElement = document.getElementById("sidebar-content");
  if (contentElement) {
    contentElement.innerHTML = "";
  }

  const historyElement = document.getElementById("chat-history");
  if (historyElement) {
    historyElement.innerHTML = "";
  }

  try {
    const response = await fetch(`${REMORA}/companion/sidebar/${encodeURIComponent(nodeId)}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    if (contentElement) {
      contentElement.innerHTML = marked.parse(data.markdown || "_No content yet._");
    }
  } catch (error) {
    if (contentElement) {
      contentElement.innerHTML = `<p class="error">Failed to load sidebar: ${escapeHtml(error.message)}</p>`;
    }
  } finally {
    setSignal("sidebarLoading", false);
  }
}

function attachSidebarClose() {
  const closeButton = document.getElementById("sidebar-close");
  if (!closeButton) {
    return;
  }

  closeButton.addEventListener("click", () => {
    setSignal("sidebarOpen", false);
    setSignal("selectedNodeId", "");
    setSidebarOpen(false);
  });
}

function setSidebarOpen(isOpen) {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) {
    return;
  }
  sidebar.classList.toggle("is-open", Boolean(isOpen));
}

function attachChatForm() {
  const form = document.getElementById("chat-form");
  if (!form) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const input = document.getElementById("chat-input");
    const message = (input && input.value ? input.value : "").trim();
    const nodeId = getSignal("selectedNodeId");

    if (!message || !nodeId) {
      return;
    }

    if (input) {
      input.value = "";
    }
    setSignal("chatMessage", "");

    appendChatMessage("user", message);
    setSignal("chatLoading", true);

    try {
      const response = await fetch(`${REMORA}/companion/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_id: nodeId, message }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      appendChatMessage("agent", data.reply || "(no reply)");
    } catch (error) {
      appendChatMessage("agent", `Error: ${error.message}`);
    } finally {
      setSignal("chatLoading", false);
    }
  });
}

function appendChatMessage(role, text) {
  const history = document.getElementById("chat-history");
  if (!history) {
    return;
  }

  const entry = document.createElement("div");
  entry.className = `chat-msg ${role}`;
  entry.innerHTML = `<div class="role">${role === "user" ? "You" : "Agent"}</div><div>${escapeHtml(text)}</div>`;
  history.appendChild(entry);
  history.scrollTop = history.scrollHeight;
}

function addEventToLog(data) {
  const list = document.getElementById("event-list");
  if (!list) {
    return;
  }

  const item = document.createElement("li");
  const eventType = data.type || "unknown";
  item.className = `ev-${eventType}`;

  const timestamp = formatTimestamp(data.timestamp);
  const nodePart = data.agent_id ? ` ${data.agent_id.slice(0, 24)}` : "";
  const summaryPart = data.summary ? ` ${data.summary}` : "";
  item.textContent = `${timestamp} ${eventType}${nodePart}${summaryPart}`.trim();

  if (data.raw) {
    item.title = JSON.stringify(data.raw, null, 2);
  }

  if (data.agent_id) {
    item.addEventListener("click", () => {
      focusNode(data.agent_id);
    });
  }

  list.prepend(item);
  while (list.children.length > MAX_LOG_EVENTS) {
    list.removeChild(list.lastChild);
  }
}

function formatTimestamp(value) {
  if (!value) {
    return "--:--:--";
  }

  const asNumber = Number(value);
  if (!Number.isFinite(asNumber)) {
    return "--:--:--";
  }

  const date = new Date(asNumber < 10_000_000_000 ? asNumber * 1000 : asNumber);
  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }

  return date.toLocaleTimeString();
}

function focusNode(nodeId) {
  if (!cy || !nodeId) {
    return;
  }
  const node = cy.getElementById(nodeId);
  if (!node.length) {
    return;
  }

  cy.nodes().unselect();
  node.select();
  cy.animate(
    {
      center: { eles: node },
      zoom: Math.max(cy.zoom(), 1.2),
    },
    { duration: 250 },
  );
}

function attachReplayControls(graphId) {
  const scrubber = document.getElementById("replay-scrubber");
  const timestamp = document.getElementById("replay-timestamp");
  const playPause = document.getElementById("replay-play-pause");

  if (!scrubber || !timestamp || !playPause) {
    return;
  }

  loadReplayHistory(graphId).catch((error) => {
    addEventToLog({ type: "WARN", summary: `Replay load failed: ${error.message}` });
  });

  scrubber.addEventListener("input", () => {
    replayIndex = parseInt(scrubber.value, 10) || 0;
    isLiveMode = replayIndex >= replayEvents.length;

    if (isLiveMode) {
      timestamp.textContent = "Live";
      playPause.textContent = "||";
      startEventStream();
      return;
    }

    if (eventSource) {
      eventSource.close();
    }

    playPause.textContent = ">";
    const snapshotEvent = replayEvents[Math.max(0, replayIndex - 1)];
    timestamp.textContent = snapshotEvent ? formatTimestamp(snapshotEvent.timestamp) : "Past";
    applyReplaySnapshot(replayIndex);
  });

  playPause.addEventListener("click", () => {
    if (isLiveMode) {
      isLiveMode = false;
      playPause.textContent = ">";
      if (eventSource) {
        eventSource.close();
      }
      if (scrubber.max !== "0") {
        replayIndex = parseInt(scrubber.value, 10) || replayEvents.length;
        if (replayIndex >= replayEvents.length && replayEvents.length > 0) {
          replayIndex = replayEvents.length - 1;
          scrubber.value = String(replayIndex);
        }
        applyReplaySnapshot(replayIndex);
      }
      return;
    }

    isLiveMode = true;
    replayIndex = replayEvents.length;
    scrubber.value = String(replayEvents.length);
    timestamp.textContent = "Live";
    playPause.textContent = "||";
    startEventStream();
  });
}

async function loadReplayHistory(graphId) {
  const response = await fetch(`${REMORA}/replay?graph_id=${encodeURIComponent(graphId)}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Replay response body is empty");
  }

  replayEvents = [];

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const chunk = await reader.read();
    if (chunk.done) {
      break;
    }

    buffer += decoder.decode(chunk.value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";

    for (const frame of frames) {
      const lines = frame.split("\n");
      const dataLine = lines.find((line) => line.startsWith("data:"));
      if (!dataLine) {
        continue;
      }
      const payloadText = dataLine.slice(5).trim();
      if (!payloadText) {
        continue;
      }
      try {
        replayEvents.push(JSON.parse(payloadText));
      } catch (_error) {
        // Ignore malformed replay entries.
      }
    }
  }

  replayIndex = replayEvents.length;

  const scrubber = document.getElementById("replay-scrubber");
  if (scrubber) {
    scrubber.max = String(replayEvents.length);
    scrubber.value = String(replayEvents.length);
  }
}

function applyReplaySnapshot(upToIndex) {
  if (!cy) {
    return;
  }

  cy.nodes().forEach((node) => {
    node.data("status", "idle");
    node.removeClass("cursor-focused");
  });

  const stop = Math.max(0, Math.min(upToIndex, replayEvents.length));
  for (let index = 0; index < stop; index += 1) {
    const event = replayEvents[index];
    const eventType = String(event.event_type || event.event || "");
    const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
    const agentId = resolveReplayAgent(event, payload, eventType);
    const status = deriveStatus(eventType, payload);

    if (!agentId) {
      continue;
    }

    const node = cy.getElementById(agentId);
    if (!node.length) {
      continue;
    }

    if (status) {
      node.data("status", status);
    }

    if (eventType === "CursorFocusEvent") {
      cy.nodes().removeClass("cursor-focused");
      node.addClass("cursor-focused");
    }
  }
}

function resolveReplayAgent(event, payload, eventType) {
  if (event.agent_id) {
    return event.agent_id;
  }
  if (payload.agent_id) {
    return payload.agent_id;
  }
  if (eventType === "CursorFocusEvent" && payload.focused_agent_id) {
    return payload.focused_agent_id;
  }
  if (payload.to_agent) {
    return payload.to_agent;
  }
  if (payload.node_id) {
    return payload.node_id;
  }
  return "";
}

function setSignal(name, value, attempts) {
  const maxAttempts = 60;
  const currentAttempts = typeof attempts === "number" ? attempts : 0;

  if (window.__datastar_store) {
    window.__datastar_store[name] = value;
    return;
  }

  if (currentAttempts >= maxAttempts) {
    return;
  }

  requestAnimationFrame(() => {
    setSignal(name, value, currentAttempts + 1);
  });
}

function getSignal(name) {
  if (!window.__datastar_store) {
    return "";
  }
  return window.__datastar_store[name];
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
