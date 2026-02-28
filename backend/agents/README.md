# Refactor Swarm Agents

These bundles power the codebase refactor swarm demo. Each bundle maps to a
tree-sitter node type and produces a focused refactor report using a Grail tool.

## Bundles

- `refactor_file`: file-level refactor planner.
- `refactor_class`: class-level design smell analysis.
- `refactor_function`: function-level complexity analysis.
- `refactor_method`: method-level contract and side-effect analysis.
- `common_tools`: shared tools available to all bundles (e.g. `update_file`).

## How the pieces fit

- `backend/remora.yaml` maps node types to these bundles.
- Each bundle has a `tools/` directory with a single Grail tool for output.
- The backend loads tools from each bundle plus `common_tools/`.
- The tool name matches the `.pym` filename; prompts instruct the agent to call it.
