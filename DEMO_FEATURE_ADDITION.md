# Demo Feature Addition
# Demo Feature Addition

This document explains how to update the remora-demo frontend so it matches the new Hub dashboard experience (adds the ``Launch Graph`` card and keeps the DOM structure aligned for Datastar updates).

## Context
- The Hub now renders a ``graphLauncher`` card before the blocked/status/results cards (see ``src/remora/hub/views.py``). The frontend must mirror that structure so it can render the same patches without DOM mismatches.
- Datastar expects certain signal keys to exist, so the frontend needs to surface the same ``graphLauncher`` data along with the existing ``events``, ``blocked``, ``agentStates``, etc.
- The card includes a small form that posts to ``/graph/execute`` (via Datastar ``@post``) so users can kick off new graphs from the UI.

## Step-by-step guide
1. **Extend the initial signal state.** In ``.context/remora-demo/src/remora_demo/frontend/views.py`` inside ``home_view`` update the ``data.signals`` block to include a ``graphLauncher`` key:
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
           },
       },
       ifmissing=True,
   ),
   ```
   This keeps Datastar aware of the new form state before any SSE patch arrives.

2. **Insert the Launch Graph card.** Still in ``home_view``, import any missing helpers you need (e.g., ``Input`` and ``Button`` from ``stario.html``) and, inside the ``main-panel`` ``Div``, add a new card before the existing blocked/status/results/progress cards that matches the Hub’s markup. An example structure:
   ```python
   Div(
       {"class": "card graph-launcher-card"},
       Div({}, "Launch Graph"),
       Div(
           {"class": "graph-launcher-form"},
           Input({"type": "text", "placeholder": "Graph ID (required)", "data-bind": "graphLauncher.graphId"}),
           Input({"type": "text", "placeholder": "Bundle (optional)", "data-bind": "graphLauncher.bundle"}),
           Input({"type": "text", "placeholder": "Target (optional)", "data-bind": "graphLauncher.target"}),
           Button({
               "type": "button",
               "data-on": "click",
               "data-on-click": "...",
           }, "Start Graph"),
       ),
   ),
   ```
   Replace the placeholder ``Button`` markup with a real Stario ``Div``/``Button`` combo that issues the ``@post('/graph/execute')`` call in the same way the Hub view does (gathering ``graphId``, ``bundle``, and optional ``target``/resetting ``graphId`` after the post). Keep the ``data-bind`` values in sync with the signals defined above.

3. **Wire the button click payload.** The button should gather values from ``$graphLauncher`` (Datastar signal scope) and call ``@post('/graph/execute', payload)`` exactly like the Hub view, e.g.:
   ```js
   const graphId = $graphLauncher?.graphId?.trim();
   if (!graphId) {
       alert('Graph ID is required to launch a graph.');
       return;
   }
   const payload = { graph_id: graphId, bundle: $graphLauncher?.bundle?.trim() || 'default' };
   const targetValue = $graphLauncher?.target?.trim();
   if (targetValue) payload.target = targetValue;
   @post('/graph/execute', payload);
   $graphLauncher.graphId = '';
   ```
   The frontend should keep this logic inline on the button so it matches the Hub's SSE payload generation.

4. **Update the CSS.** Copy the new ``.graph-launcher-form`` styles from ``src/remora/hub/static/style.css`` into ``.context/remora-demo/src/remora_demo/static/css/style.css`` (including the button hover state) so the launcher card matches the Hub's UI.

5. **Verify the DOM order.** Because Datastar diffs match elements by ``id`` and ``class``, ensure the new card appears before the existing blocked/status/results cards inside ``#main-panel`` (just like the hub version). Any mismatch could cause missing patches when the hub stream updates.

6. **Smoke test the frontend.** Run the frontend via ``python -m remora_demo.frontend.main`` while the hub runs locally on ``http://localhost:8000``. Visit ``http://localhost:8001`` to ensure the launcher card renders, fill in a graph ID (e.g., ``demo-1``), and hit "Start Graph" to confirm the POST is proxied to the hub and the dashboard updates via SSE.

7. **Optional sanity checks.** Watch the network tab for the ``/subscribe`` stream to confirm it still receives chunks, and check the logs for any ``aiohttp.ClientError`` messages from the proxy handlers.

If you need any of the Hub-side patch details, refer to ``src/remora/hub/views.py`` for the updated layout and ``src/remora/hub/static/style.css`` for the exact CSS rules.
