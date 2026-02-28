# Remora.nvim - CST Agent Swarm Neovim Plugin

## Executive Summary

**Remora.nvim** transforms Neovim into an agent-native IDE where every code construct (file, function, class, import) is an autonomous agent. The editor becomes the swarm visualization - navigating treesitter objects IS navigating agents. A sidepanel reveals the current agent's state, inbox, and chat interface.

This design is built on the **simplified swarm architecture**:
- Agents are dormant files (`state.jsonl` + `workspace.db`)
- Message passing via EventStore (SQLite)
- Turn-based execution triggered by file changes or user interaction
- Neovim acts as both UI and trigger source

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ remora.nvim                                                                  │
├──────────────────────────────────────────┬──────────────────────────────────┤
│                                          │  Agent: format_date              │
│  def format_date(dt: datetime) -> str:   │  Type: function                  │
│      """Format datetime for display."""  │  Status: DORMANT                 │
│  ┌─────────────────────────────────────┐ │                                  │
│  │    if dt is None:                   │ │  ─────────────────────────────── │
│  │        return "N/A"                 │ │  INBOX (2)                       │
│  │    return dt.strftime("%Y-%m-%d")   │ │  ├─ test_agent: "add edge case"  │
│  └─────────────────────────────────────┘ │  └─ linter: "line too long"      │
│                                          │                                  │
│  def parse_date(s: str) -> datetime:     │  CHAT                            │
│      """Parse date from string."""       │  ┌──────────────────────────────┐│
│      return datetime.strptime(...)       │  │ > Add timezone support       ││
│                                          │  │                              ││
│                                          │  │ I'll need to import pytz.    ││
│                                          │  │ Requesting from parent...    ││
│                                          │  └──────────────────────────────┘│
│                                          │                                  │
│                                          │  [Run Turn] [View State] [Jj Log]│
└──────────────────────────────────────────┴──────────────────────────────────┘
```

---

## Part 1: Core Concepts

### 1.1 Editor-as-Swarm-Visualization

The code itself IS the visualization. Each syntactic construct is an agent, and navigating code is navigating agents.

| Traditional | Remora.nvim |
|------------|-------------|
| Graph view with agent nodes | Code view with agent highlights |
| Click node to select agent | Navigate treesitter object to select agent |
| Separate agent inspector | Sidepanel reveals current agent |
| External event stream | Inline agent state indicators |

### 1.2 Navigation-as-Selection

Using [nvim-treesitter-textobjects](https://github.com/nvim-treesitter/nvim-treesitter-textobjects), cursor movement through code structures selects agents:

```
Keybindings (example):
  ]f  → Next function (select function agent)
  [f  → Previous function
  ]c  → Next class (select class agent)
  [[  → Parent node (select parent agent)
  ]]  → First child (select child agent)
```

When the cursor enters a treesitter node, that node's agent is selected and the sidepanel updates to show its state.

### 1.3 Turn-Based Agent Execution

Agents are **dormant by default**. Neovim triggers agent turns via:

1. **User Chat** - Type message in sidepanel, agent runs one turn
2. **Manual Trigger** - Press keybind to run agent on current node
3. **Buffer Save** - On `:w`, notify affected agents of file change
4. **Background Poll** - Optional: periodically check for pending messages

```
┌─────────────────────────────────────────────────────────────────┐
│               Neovim as Trigger Source                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Action          →  Neovim Plugin  →  Daemon RPC           │
│  ───────────────────────────────────────────────────────────────│
│  Navigate to function    Update sidepanel   (no daemon call)    │
│  Type chat message       Send to daemon  →  agent.chat(id, msg) │
│  Press <leader>rr        Trigger turn    →  agent.trigger(id)   │
│  Save buffer (:w)        Notify change   →  buffer.changed(path)│
│                                                                  │
│  Daemon Response      →  Neovim Plugin  →  User sees            │
│  ───────────────────────────────────────────────────────────────│
│  Turn complete           Update sidepanel   Chat response       │
│  Content modified        Apply to buffer    Code changes        │
│  New inbox message       Update indicator   [2] badge           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 Agent State Display

The sidepanel shows agent state loaded from `state.jsonl`:

```
╭─────────────────────────────────╮
│ Agent: format_date              │
│ Type: function                  │
│ File: src/utils.py:15-25        │
│ Status: DORMANT                 │
│ Last Run: 2 min ago             │
╰─────────────────────────────────╯

INBOX (2 unread)
─────────────────────────────────
├─ [unread] test_format_date
│  "Function signature changed,
│   please update test cases"
│
└─ [unread] linter_agent
   "Line 18 exceeds 88 chars"

CONNECTIONS (learned)
─────────────────────────────────
├─ parent → file_utils_py
├─ test → test_format_date
└─ User → class_User (models.py)

CHAT HISTORY
─────────────────────────────────
> Add timezone support
< I'll need pytz. Requesting
  import from parent file...

[Run Turn] [Clear Inbox] [View JSON]
```

---

## Part 2: Architecture

### 2.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Neovim                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         remora.nvim (Lua)                            │    │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐   │    │
│  │  │ Navigation    │  │ Sidepanel     │  │ Buffer Sync           │   │    │
│  │  │ (treesitter)  │  │ (agent UI)    │  │ (change detection)    │   │    │
│  │  └───────┬───────┘  └───────┬───────┘  └───────────┬───────────┘   │    │
│  │          │                  │                      │               │    │
│  │  ┌───────┴──────────────────┴──────────────────────┴───────────┐   │    │
│  │  │                    Bridge (JSON-RPC over socket)             │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                         │                                    │
│                                         │ Unix Socket / TCP                  │
│                                         ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       Remora Daemon (Python)                         │    │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐   │    │
│  │  │ SwarmState    │  │ EventStore    │  │ AgentRunner           │   │    │
│  │  │ (agent registry)│ │ (message bus) │  │ (turn executor)       │   │    │
│  │  └───────────────┘  └───────────────┘  └───────────────────────┘   │    │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐   │    │
│  │  │ Workspaces    │  │ Discovery     │  │ Jujutsu Sync          │   │    │
│  │  │ (Cairn .db)   │  │ (tree-sitter) │  │ (optional)            │   │    │
│  │  └───────────────┘  └───────────────┘  └───────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                         │                                    │
│                                         │ HTTP (OpenAI-compatible)           │
│                                         ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         LLM Server (vLLM)                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Breakdown

#### Neovim Plugin (Lua)

| Component | Responsibility |
|-----------|----------------|
| **Navigation Module** | Treesitter object navigation, agent ID computation |
| **Sidepanel** | Agent details, inbox, chat interface, action buttons |
| **Buffer Sync** | Track buffer changes, notify daemon on save |
| **Bridge** | JSON-RPC client to daemon |

#### Remora Daemon (Python)

| Component | Responsibility |
|-----------|----------------|
| **SwarmState** | Agent registry, metadata lookup |
| **EventStore** | Message storage, inbox queries |
| **AgentRunner** | Execute single agent turns |
| **Workspaces** | Cairn CoW workspaces per agent |

### 2.3 Communication Protocol

```
┌─────────────────────────────────────────────────────────────────┐
│                    RPC Protocol (JSON-RPC 2.0)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Neovim → Daemon (Requests)                                     │
│  ─────────────────────────                                      │
│  agent.select(node_id)      → Get agent state for display       │
│  agent.chat(node_id, msg)   → Run turn with user message        │
│  agent.trigger(node_id)     → Run turn (check inbox, react)     │
│  agent.get_inbox(node_id)   → Get pending messages              │
│  buffer.changed(path)       → Notify file was modified          │
│  swarm.status()             → Get swarm overview                │
│                                                                  │
│  Daemon → Neovim (Notifications)                                │
│  ───────────────────────────                                    │
│  agent.turn_complete(id, result)  → Turn finished              │
│  agent.content_changed(id, diff)  → Agent modified code        │
│  agent.inbox_updated(id, count)   → New message arrived        │
│  swarm.agent_spawned(id)          → New agent created          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Neovim Plugin Design

### 3.1 Plugin Structure

```
lua/remora/
├── init.lua              # Plugin entry point, setup()
├── config.lua            # User configuration
├── navigation.lua        # Treesitter navigation, agent ID computation
├── sidepanel.lua         # Agent UI panel
├── chat.lua              # Chat interface within sidepanel
├── indicators.lua        # Inline indicators (inbox badges, status)
├── bridge.lua            # JSON-RPC client to daemon
├── buffer.lua            # Buffer change tracking
└── health.lua            # :checkhealth support
```

### 3.2 Core Modules

#### Navigation (`navigation.lua`)

```lua
local M = {}

-- Compute agent ID from treesitter node (matches daemon's ID generation)
function M.compute_agent_id(node, bufnr)
  local file_path = vim.api.nvim_buf_get_name(bufnr)
  local node_type = node:type()
  local start_row, start_col = node:start()

  -- Extract name if available
  local name = M.extract_node_name(node)

  -- ID format: type_name_file_line (must match daemon)
  return string.format("%s_%s_%s_%d",
    node_type,
    name or "anonymous",
    vim.fn.fnamemodify(file_path, ":t:r"),
    start_row + 1
  )
end

-- Find the "interesting" node at cursor (function, class, etc.)
function M.get_agent_node_at_cursor()
  local ts_utils = require("nvim-treesitter.ts_utils")
  local node = ts_utils.get_node_at_cursor()

  while node do
    if M.is_agent_node_type(node:type()) then
      return node
    end
    node = node:parent()
  end
  return nil
end

function M.is_agent_node_type(node_type)
  local agent_types = {
    "function_definition", "class_definition", "method_definition",
    "import_statement", "import_from_statement", "module",
    "decorated_definition", "async_function_definition",
  }
  return vim.tbl_contains(agent_types, node_type)
end

-- Called on cursor move - update sidepanel if agent changed
function M.on_cursor_moved()
  local node = M.get_agent_node_at_cursor()
  if not node then
    return
  end

  local agent_id = M.compute_agent_id(node, 0)
  if agent_id ~= M.current_agent_id then
    M.current_agent_id = agent_id
    require("remora.sidepanel").show_agent(agent_id)
  end
end

function M.setup()
  vim.api.nvim_create_autocmd("CursorMoved", {
    callback = M.on_cursor_moved,
  })
end

return M
```

#### Sidepanel (`sidepanel.lua`)

```lua
local M = {}

M.win = nil
M.buf = nil
M.current_agent = nil
M.agent_state = nil

function M.setup()
  M.buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_option(M.buf, "buftype", "nofile")
  vim.api.nvim_buf_set_option(M.buf, "filetype", "remora")

  -- Keymaps for sidepanel buffer
  vim.api.nvim_buf_set_keymap(M.buf, "n", "c", "<cmd>lua require('remora.chat').open()<cr>", {})
  vim.api.nvim_buf_set_keymap(M.buf, "n", "r", "<cmd>lua require('remora.sidepanel').run_turn()<cr>", {})
  vim.api.nvim_buf_set_keymap(M.buf, "n", "i", "<cmd>lua require('remora.sidepanel').show_inbox()<cr>", {})
end

function M.toggle()
  if M.win and vim.api.nvim_win_is_valid(M.win) then
    M.close()
  else
    M.open()
  end
end

function M.open()
  vim.cmd("vsplit")
  vim.cmd("wincmd L")
  M.win = vim.api.nvim_get_current_win()
  vim.api.nvim_win_set_buf(M.win, M.buf)
  vim.api.nvim_win_set_width(M.win, 40)

  vim.api.nvim_win_set_option(M.win, "number", false)
  vim.api.nvim_win_set_option(M.win, "signcolumn", "no")
  vim.api.nvim_win_set_option(M.win, "winfixwidth", true)

  vim.cmd("wincmd p")

  if M.current_agent then
    M.render()
  end
end

function M.show_agent(agent_id)
  M.current_agent = agent_id

  -- Request state from daemon
  require("remora.bridge").call("agent.select", { agent_id }, function(state)
    M.agent_state = state
    M.render()
  end)
end

function M.render()
  if not M.win or not vim.api.nvim_win_is_valid(M.win) then
    return
  end

  local state = M.agent_state or {}
  local lines = {}

  -- Header
  table.insert(lines, "╭─────────────────────────────────╮")
  table.insert(lines, string.format("│ Agent: %-25s│", state.name or "?"))
  table.insert(lines, string.format("│ Type: %-26s│", state.node_type or "?"))
  table.insert(lines, string.format("│ Status: %-24s│", state.status or "DORMANT"))
  if state.last_activated then
    local ago = M.time_ago(state.last_activated)
    table.insert(lines, string.format("│ Last Run: %-22s│", ago))
  end
  table.insert(lines, "╰─────────────────────────────────╯")
  table.insert(lines, "")

  -- Inbox
  local inbox_count = #(state.inbox or {})
  table.insert(lines, string.format("INBOX (%d)", inbox_count))
  table.insert(lines, "─────────────────────────────────")
  if inbox_count > 0 then
    for i, msg in ipairs(state.inbox) do
      if i <= 5 then  -- Show max 5
        local prefix = msg.read and "  " or "* "
        table.insert(lines, string.format("%s%s: %s",
          prefix,
          msg.from_agent:sub(1, 15),
          (msg.content.summary or ""):sub(1, 20)
        ))
      end
    end
    if inbox_count > 5 then
      table.insert(lines, string.format("  ... and %d more", inbox_count - 5))
    end
  else
    table.insert(lines, "  (empty)")
  end
  table.insert(lines, "")

  -- Connections
  table.insert(lines, "CONNECTIONS")
  table.insert(lines, "─────────────────────────────────")
  if state.connections and next(state.connections) then
    for name, id in pairs(state.connections) do
      table.insert(lines, string.format("├─ %s → %s", name, id:sub(1, 12)))
    end
  else
    table.insert(lines, "  (none learned)")
  end
  table.insert(lines, "")

  -- Recent chat
  table.insert(lines, "CHAT")
  table.insert(lines, "─────────────────────────────────")
  if state.chat_history and #state.chat_history > 0 then
    -- Show last 2 exchanges
    local start = math.max(1, #state.chat_history - 3)
    for i = start, #state.chat_history do
      local msg = state.chat_history[i]
      local prefix = msg.role == "user" and "> " or "< "
      for _, line in ipairs(vim.split(msg.content:sub(1, 100), "\n")) do
        table.insert(lines, prefix .. line)
        prefix = "  "
      end
    end
  else
    table.insert(lines, "  (no history)")
  end
  table.insert(lines, "")

  -- Actions
  table.insert(lines, "─────────────────────────────────")
  table.insert(lines, " [c]hat  [r]un turn  [i]nbox")

  vim.api.nvim_buf_set_lines(M.buf, 0, -1, false, lines)
end

function M.run_turn()
  if not M.current_agent then
    vim.notify("No agent selected", vim.log.levels.WARN)
    return
  end

  vim.notify("Running agent turn...", vim.log.levels.INFO)

  require("remora.bridge").call("agent.trigger", { M.current_agent }, function(result)
    vim.notify("Turn complete", vim.log.levels.INFO)
    -- Refresh state
    M.show_agent(M.current_agent)

    -- Apply any content changes
    if result.content_changed then
      require("remora.buffer").apply_changes(result.changes)
    end
  end)
end

function M.time_ago(timestamp)
  local diff = os.time() - timestamp
  if diff < 60 then return "just now"
  elseif diff < 3600 then return string.format("%d min ago", diff // 60)
  elseif diff < 86400 then return string.format("%d hrs ago", diff // 3600)
  else return string.format("%d days ago", diff // 86400)
  end
end

return M
```

#### Chat (`chat.lua`)

```lua
local M = {}

function M.open()
  local sidepanel = require("remora.sidepanel")
  if not sidepanel.current_agent then
    vim.notify("No agent selected", vim.log.levels.WARN)
    return
  end

  vim.ui.input({ prompt = "Chat with agent: " }, function(input)
    if input and input ~= "" then
      M.send_message(sidepanel.current_agent, input)
    end
  end)
end

function M.send_message(agent_id, message)
  vim.notify("Sending to agent...", vim.log.levels.INFO)

  require("remora.bridge").call("agent.chat", {
    agent_id = agent_id,
    message = message,
  }, function(response)
    local sidepanel = require("remora.sidepanel")

    -- Update chat history locally for immediate feedback
    sidepanel.agent_state.chat_history = sidepanel.agent_state.chat_history or {}
    table.insert(sidepanel.agent_state.chat_history, {
      role = "user",
      content = message,
    })
    table.insert(sidepanel.agent_state.chat_history, {
      role = "assistant",
      content = response.output or "(no response)",
    })
    sidepanel.render()

    -- Apply content changes if any
    if response.content_changed then
      require("remora.buffer").apply_changes(response.changes)
      vim.notify("Agent modified code", vim.log.levels.INFO)
    end
  end)
end

return M
```

#### Buffer Sync (`buffer.lua`)

```lua
local M = {}

function M.setup()
  -- Notify daemon when buffer is saved
  vim.api.nvim_create_autocmd("BufWritePost", {
    pattern = {"*.py", "*.js", "*.ts", "*.go", "*.rs"},
    callback = function(ev)
      local path = vim.api.nvim_buf_get_name(ev.buf)
      M.notify_change(path)
    end
  })
end

function M.notify_change(path)
  require("remora.bridge").call("buffer.changed", { path = path }, function(result)
    if result.agents_notified and result.agents_notified > 0 then
      vim.notify(
        string.format("%d agents notified of change", result.agents_notified),
        vim.log.levels.INFO
      )
    end
  end)
end

function M.apply_changes(changes)
  -- changes = { path: string, content: string } or list of changes
  if not changes then return end

  if changes.path then
    changes = { changes }
  end

  for _, change in ipairs(changes) do
    local bufnr = vim.fn.bufnr(change.path)
    if bufnr ~= -1 then
      -- Buffer is open - update it
      local lines = vim.split(change.content, "\n")
      vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)
      vim.notify("Updated: " .. vim.fn.fnamemodify(change.path, ":t"), vim.log.levels.INFO)
    end
  end
end

return M
```

#### Bridge (`bridge.lua`)

```lua
local M = {}

M.client = nil
M.callbacks = {}
M.next_id = 1

function M.setup(config)
  local socket_path = config.socket or "/tmp/remora.sock"

  M.client = vim.loop.new_pipe(false)
  M.client:connect(socket_path, function(err)
    if err then
      vim.schedule(function()
        vim.notify("Failed to connect to Remora daemon: " .. err, vim.log.levels.ERROR)
      end)
      return
    end

    M.client:read_start(function(err, data)
      if err then return end
      if data then
        M.handle_response(data)
      end
    end)

    vim.schedule(function()
      vim.notify("Connected to Remora daemon", vim.log.levels.INFO)
    end)
  end)
end

function M.call(method, params, callback)
  local id = M.next_id
  M.next_id = M.next_id + 1

  local msg = vim.fn.json_encode({
    jsonrpc = "2.0",
    id = id,
    method = method,
    params = params,
  })

  if callback then
    M.callbacks[id] = callback
  end

  M.client:write(msg .. "\n")
end

function M.handle_response(data)
  for line in data:gmatch("[^\n]+") do
    local ok, msg = pcall(vim.fn.json_decode, line)
    if ok then
      if msg.id and M.callbacks[msg.id] then
        -- RPC response
        vim.schedule(function()
          M.callbacks[msg.id](msg.result)
          M.callbacks[msg.id] = nil
        end)
      elseif msg.method then
        -- Notification from daemon
        vim.schedule(function()
          M.handle_notification(msg.method, msg.params)
        end)
      end
    end
  end
end

function M.handle_notification(method, params)
  if method == "agent.content_changed" then
    require("remora.buffer").apply_changes(params.changes)
  elseif method == "agent.inbox_updated" then
    require("remora.indicators").update_inbox(params.agent_id, params.count)
  elseif method == "agent.turn_complete" then
    -- Refresh sidepanel if showing this agent
    local sidepanel = require("remora.sidepanel")
    if sidepanel.current_agent == params.agent_id then
      sidepanel.show_agent(params.agent_id)
    end
  end
end

return M
```

#### Indicators (`indicators.lua`)

```lua
local M = {}

M.ns = vim.api.nvim_create_namespace("remora_indicators")
M.inbox_counts = {}  -- agent_id -> count

function M.setup()
  -- Refresh indicators when buffer is displayed
  vim.api.nvim_create_autocmd("BufWinEnter", {
    callback = M.refresh_buffer_indicators,
  })
end

function M.update_inbox(agent_id, count)
  M.inbox_counts[agent_id] = count
  M.refresh_buffer_indicators()
end

function M.refresh_buffer_indicators()
  local bufnr = vim.api.nvim_get_current_buf()
  vim.api.nvim_buf_clear_namespace(bufnr, M.ns, 0, -1)

  -- Get treesitter root
  local parser = vim.treesitter.get_parser(bufnr)
  if not parser then return end

  local tree = parser:parse()[1]
  if not tree then return end

  local root = tree:root()
  local nav = require("remora.navigation")

  -- Walk tree and add indicators for agents with inbox
  M.walk_tree(root, bufnr, function(node)
    if nav.is_agent_node_type(node:type()) then
      local agent_id = nav.compute_agent_id(node, bufnr)
      local count = M.inbox_counts[agent_id]

      if count and count > 0 then
        local row = node:start()
        vim.api.nvim_buf_set_extmark(bufnr, M.ns, row, 0, {
          virt_text = { { string.format(" [%d]", count), "DiagnosticInfo" } },
          virt_text_pos = "eol",
        })
      end
    end
  end)
end

function M.walk_tree(node, bufnr, callback)
  callback(node)
  for child in node:iter_children() do
    M.walk_tree(child, bufnr, callback)
  end
end

return M
```

### 3.3 Keybindings

```lua
local function setup_keymaps()
  local opts = { noremap = true, silent = true }

  -- Sidepanel
  vim.keymap.set("n", "<leader>ra", "<cmd>lua require('remora.sidepanel').toggle()<cr>", opts)

  -- Agent navigation (supplements treesitter-textobjects)
  vim.keymap.set("n", "[[", function()
    require("remora.navigation").go_to_parent()
  end, opts)

  vim.keymap.set("n", "]]", function()
    require("remora.navigation").go_to_first_child()
  end, opts)

  -- Chat with current agent
  vim.keymap.set("n", "<leader>rc", function()
    require("remora.chat").open()
  end, opts)

  -- Run agent turn
  vim.keymap.set("n", "<leader>rr", function()
    require("remora.sidepanel").run_turn()
  end, opts)

  -- View agent state JSON (for debugging)
  vim.keymap.set("n", "<leader>rs", function()
    require("remora.sidepanel").show_raw_state()
  end, opts)
end
```

---

## Part 4: Daemon RPC Server

The daemon exposes a JSON-RPC server for Neovim communication:

```python
# remora/nvim/server.py

import asyncio
import json
from pathlib import Path

class NvimRpcServer:
    """JSON-RPC server for Neovim plugin communication."""

    def __init__(
        self,
        swarm_state: SwarmState,
        event_store: EventStore,
        agent_runner: AgentRunner,
        socket_path: str = "/tmp/remora.sock",
    ):
        self.swarm_state = swarm_state
        self.event_store = event_store
        self.runner = agent_runner
        self.socket_path = socket_path
        self.clients: list[asyncio.StreamWriter] = []

    async def start(self) -> None:
        Path(self.socket_path).unlink(missing_ok=True)
        server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path,
        )
        async with server:
            await server.serve_forever()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.clients.append(writer)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                request = json.loads(line.decode())
                response = await self._handle_request(request)
                if request.get("id"):
                    writer.write(json.dumps(response).encode() + b"\n")
                    await writer.drain()
        finally:
            self.clients.remove(writer)
            writer.close()

    async def _handle_request(self, request: dict) -> dict:
        method = request.get("method", "")
        params = request.get("params", {})

        handlers = {
            "agent.select": self._select_agent,
            "agent.chat": self._chat_with_agent,
            "agent.trigger": self._trigger_agent,
            "agent.get_inbox": self._get_inbox,
            "buffer.changed": self._buffer_changed,
            "swarm.status": self._swarm_status,
        }

        handler = handlers.get(method)
        if handler:
            try:
                result = await handler(params)
                return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": -1, "message": str(e)},
                }
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    async def _select_agent(self, params: dict) -> dict:
        """Get agent state for display."""
        agent_id = params.get("agent_id") or params[0]
        metadata = await self.swarm_state.get_agent(agent_id)
        if not metadata:
            return {"error": "Agent not found"}

        state = AgentState.load(self._state_path(agent_id))
        inbox = [msg async for msg in self.event_store.get_inbox(agent_id)]

        return {
            "id": agent_id,
            "name": metadata.name,
            "node_type": metadata.node_type,
            "file_path": metadata.file_path,
            "status": "DORMANT",  # Always dormant until we run a turn
            "last_activated": state.last_activated,
            "inbox": inbox,
            "connections": state.connections,
            "chat_history": state.chat_history[-10:],  # Last 10 messages
        }

    async def _chat_with_agent(self, params: dict) -> dict:
        """Run agent turn with user message."""
        agent_id = params["agent_id"]
        message = params["message"]

        result = await self.runner.run_turn(
            agent_id,
            TriggerEvent(type="user_chat", message=message)
        )

        # Notify all clients of any content changes
        if result.content_changed:
            await self._notify_all({
                "method": "agent.content_changed",
                "params": {
                    "agent_id": agent_id,
                    "changes": result.changes,
                },
            })

        return {
            "output": result.output,
            "content_changed": result.content_changed,
            "changes": result.changes if result.content_changed else None,
        }

    async def _trigger_agent(self, params: dict) -> dict:
        """Run agent turn (process inbox, react to state)."""
        agent_id = params.get("agent_id") or params[0]

        result = await self.runner.run_turn(
            agent_id,
            TriggerEvent(type="manual_trigger")
        )

        return {
            "output": result.output,
            "content_changed": result.content_changed,
            "changes": result.changes if result.content_changed else None,
        }

    async def _buffer_changed(self, params: dict) -> dict:
        """Handle file change notification from Neovim."""
        path = params["path"]

        # Find agents for this file
        agents = await self.swarm_state.list_agents_for_file(path)

        # Queue notifications (don't run turns automatically)
        for agent in agents:
            await self.event_store.append(
                graph_id=self.swarm_state.swarm_id,
                event=AgentMessageEvent(
                    from_agent="neovim",
                    to_agent=agent.id,
                    action="notify",
                    content={"type": "file_changed", "path": path},
                )
            )

        # Notify Neovim of updated inbox counts
        for agent in agents:
            inbox_count = await self.event_store.get_inbox_count(agent.id)
            await self._notify_all({
                "method": "agent.inbox_updated",
                "params": {"agent_id": agent.id, "count": inbox_count},
            })

        return {"agents_notified": len(agents)}

    async def _notify_all(self, notification: dict) -> None:
        """Send notification to all connected Neovim clients."""
        data = json.dumps(notification).encode() + b"\n"
        for client in self.clients:
            try:
                client.write(data)
                await client.drain()
            except Exception:
                pass
```

---

## Part 5: User Experience

### 5.1 Typical Workflow

```
1. User opens Python file
   → Daemon has already parsed and registered agents
   → Neovim connects, ready to query

2. User navigates to function (]f or cursor move)
   → Sidepanel shows function agent state
   → Inbox count shown inline if > 0

3. User opens chat (<leader>rc)
   → Types: "add timezone support"
   → Agent runs one turn
   → Agent requests pytz import from parent (via EventStore)
   → Agent updates function implementation
   → Buffer updates with new code

4. User saves file (:w)
   → Daemon notified of change
   → Affected agents get inbox message
   → Inbox indicators update in Neovim

5. User triggers agent turn (<leader>rr)
   → Agent processes inbox messages
   → Agent may send responses, update code
   → Sidepanel refreshes with results
```

### 5.2 Visual Feedback

```
Code Buffer                          Sidepanel
───────────────────────────────────  ─────────────────────────
def format_date(dt):  [2]           │ Agent: format_date
    """Format date."""               │ Status: DORMANT
    if dt is None:                   │
        return "N/A"                 │ INBOX (2)
    return dt.strftime(...)          │ ├─ test: sig changed
                                     │ └─ linter: line 18
def parse_date(s):                   │
    ...                              │ [c]hat [r]un [i]nbox
```

The `[2]` indicator shows inbox count inline. Sidepanel shows full details.

### 5.3 Commands

```vim
" Core commands
:RemoraToggle          " Toggle sidepanel
:RemoraStatus          " Show daemon/swarm status
:RemoraConnect         " Reconnect to daemon

" Agent interaction
:RemoraChat            " Open chat with current agent
:RemoraTrigger         " Run current agent's turn
:RemoraInbox           " Show full inbox in floating window

" Navigation
:RemoraParent          " Go to parent agent
:RemoraChildren        " List child agents
```

---

## Part 6: Configuration

### 6.1 Plugin Configuration

```lua
require("remora").setup({
  -- Daemon connection
  socket = "/tmp/remora.sock",
  auto_connect = true,

  -- UI
  sidepanel = {
    position = "right",  -- "right", "left", "float"
    width = 40,
  },

  -- Indicators
  indicators = {
    inbox_badge = true,   -- Show [N] for inbox count
    status_icon = false,  -- Show agent status in signcolumn
  },

  -- Keybindings
  keymaps = {
    toggle = "<leader>ra",
    chat = "<leader>rc",
    trigger = "<leader>rr",
    parent = "[[",
    child = "]]",
  },

  -- Auto behavior
  auto = {
    notify_on_save = true,   -- Notify agents when file saved
    refresh_on_focus = true, -- Refresh sidepanel on window focus
  },
})
```

### 6.2 Daemon Configuration (`remora.yaml`)

```yaml
daemon:
  socket: /tmp/remora.sock
  log_level: info

model:
  base_url: http://localhost:8000/v1
  api_key: EMPTY
  default_model: Qwen/Qwen3-4B

swarm:
  workspace_path: ~/.cache/remora/swarm
  auto_reconcile: true  # Reconcile on startup

jujutsu:
  enabled: false
  auto_commit: false
```

---

## Part 7: Implementation Summary

### What's Needed (Plugin Side)

| Module | Lines | Description |
|--------|-------|-------------|
| `init.lua` | ~30 | Setup, health check |
| `config.lua` | ~40 | Configuration handling |
| `navigation.lua` | ~80 | Treesitter integration, agent ID |
| `sidepanel.lua` | ~150 | Agent UI panel |
| `chat.lua` | ~40 | Chat interface |
| `indicators.lua` | ~60 | Inline badges |
| `bridge.lua` | ~80 | JSON-RPC client |
| `buffer.lua` | ~50 | Change tracking |
| **Total** | **~530** | |

### What's Needed (Daemon Side)

| Module | Lines | Description |
|--------|-------|-------------|
| `nvim/server.py` | ~200 | JSON-RPC server |
| **Total** | **~200** | |

### Dependencies

**Neovim Plugin:**
- `nvim-treesitter` (for parsing)
- `nvim-treesitter-textobjects` (optional, for navigation)

**Daemon:**
- Existing Remora infrastructure
- Swarm components from REMORA_CST_DEMO_ANALYSIS.md

---

## Appendix A: Treesitter Node Types by Language

```lua
local agent_node_types = {
  python = {
    "module", "function_definition", "async_function_definition",
    "class_definition", "decorated_definition",
    "import_statement", "import_from_statement",
  },
  javascript = {
    "program", "function_declaration", "arrow_function",
    "class_declaration", "method_definition", "import_statement",
  },
  typescript = {
    "program", "function_declaration", "arrow_function",
    "class_declaration", "method_definition",
    "interface_declaration", "type_alias_declaration",
    "import_statement",
  },
  go = {
    "source_file", "function_declaration", "method_declaration",
    "type_declaration", "import_declaration",
  },
  rust = {
    "source_file", "function_item", "impl_item",
    "struct_item", "enum_item", "trait_item", "use_declaration",
  },
}
```

---

*Document version: 2.0*
*Status: Simplified Architecture - Ready for Implementation*
